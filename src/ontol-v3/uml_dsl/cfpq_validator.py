from __future__ import annotations
from typing import List, Set, Dict, Tuple

# Импорты алгоритмов CFPQ из ваших файлов
from .cfpq_matrix import Grammar, LabeledGraph, cfpq_matrix
from .grammar_utils import to_wcnf

# Имп.орты моделей для тестового запуска
from .diagram import ClassDiagram
from .models import Class
from .enums import DependencyStereotype

def validate_uml_cycles(diagram: ClassDiagram) -> list[str]:
    """
    Выполняет валидацию циклических зависимостей в UML-диаграмме с использованием CFPQ.
    """
    errors: list[str] = []
    
    # Извлекаем элементы из ClassDiagram (проверяем разные варианты имён для надёжности)
    classes = getattr(diagram, 'classifiers', []) or getattr(diagram, 'classes', [])
    generalizations = getattr(diagram, 'generalizations', [])
    dependencies = getattr(diagram, 'dependencies', [])
    associations = getattr(diagram, 'associations', [])
    realizations = getattr(diagram, 'realizations', [])
    
    # Собираем все уникальные имена классов для построения индексов графа
    class_names_set: Set[str] = set()
    for c in classes:
        if hasattr(c, 'name') and c.name:
            class_names_set.add(c.name)
            
    # Дособираем имена из связей на случай, если класс не был явно добавлен в диаграмму
    for g in generalizations:
        if hasattr(g.specific, 'name'): class_names_set.add(g.specific.name)
        if hasattr(g.general, 'name'): class_names_set.add(g.general.name)
    for d in dependencies:
        if hasattr(d.client, 'name'): class_names_set.add(d.client.name)
        if hasattr(d.supplier, 'name'): class_names_set.add(d.supplier.name)
    for r in realizations:
        if hasattr(r.implementer, 'name'): class_names_set.add(r.implementer.name)
        if hasattr(r.interface_, 'name'): class_names_set.add(r.interface_.name)
    for a in associations:
        if hasattr(a, 'ends'):
            for end in a.ends:
                if hasattr(end.participant, 'name'):
                    class_names_set.add(end.participant.name)
                    
    class_names = sorted(list(class_names_set))
    if not class_names:
        return errors
        
    name_to_id: Dict[str, int] = {name: idx for idx, name in enumerate(class_names)}
    edges = []
    
    # 1. Рёбра для Наследования (Generalization) -> метки 'subclassOf' и 'a'
    for g in generalizations:
        u = name_to_id.get(g.specific.name)
        v = name_to_id.get(g.general.name)
        if u is not None and v is not None:
            edges.append((u, "subclassOf", v))
            edges.append((u, "a", v))
                
    # 2. Рёбра для Зависимостей (Dependency) -> метка 'b'
    for d in dependencies:
        u = name_to_id.get(d.client.name)
        v = name_to_id.get(d.supplier.name)
        if u is not None and v is not None:
            edges.append((u, "b", v))
                
    # 3. Рёбра для Реализаций (Realization) -> метка 'b'
    for r in realizations:
        u = name_to_id.get(r.implementer.name)
        v = name_to_id.get(r.interface_.name)
        if u is not None and v is not None:
            edges.append((u, "b", v))
                
    # 4. Рёбра для Ассоциаций (Association) -> метка 'b'
    for a in associations:
        if hasattr(a, 'ends') and len(a.ends) >= 2:
            for i in range(len(a.ends)):
                for j in range(len(a.ends)):
                    if i != j:
                        p1 = a.ends[i].participant
                        p2 = a.ends[j].participant
                        u = name_to_id.get(p1.name)
                        v = name_to_id.get(p2.name)
                        if u is not None and v is not None:
                            edges.append((u, "b", v))
                                
    # Создаём LabeledGraph для вычислений
    graph = LabeledGraph(num_nodes=len(class_names), edges=edges)
    
    # -------------------------------------------------------------------------
    # Проверка 1: Циклы наследования (subclassof_cnf.txt)
    # -------------------------------------------------------------------------
    subclassof_grammar_raw = Grammar.from_text("S -> S S\nS -> subclassOf")
    subclassof_grammar = to_wcnf(subclassof_grammar_raw)
    subclassof_res = cfpq_matrix(graph, subclassof_grammar, use_sparse=True)
    
    if "S" in subclassof_res:
        for i, j in subclassof_res["S"]:
            if i == j:
                errors.append(f"Обнаружен цикл наследования для класса '{class_names[i]}'")
                
    # -------------------------------------------------------------------------
    # Проверка 2: Сложный циклический антипаттерн (abab_cnf.txt)
    # -------------------------------------------------------------------------
    abab_grammar_text = (
        "S -> Ap1 MidMid\n"
        "MidMid -> Bk1 RightRight\n"
        "RightRight -> Ap2 Bp2\n"
        "Ap1 -> a\n"
        "Ap1 -> A_term Ap1\n"
        "Bk1 -> b\n"
        "Bk1 -> B_term Bk1\n"
        "Ap2 -> a\n"
        "Ap2 -> A_term Ap2\n"
        "Bp2 -> b\n"
        "Bp2 -> B_term Bp2\n"
        "A_term -> a\n"
        "B_term -> b"
    )
    abab_grammar_raw = Grammar.from_text(abab_grammar_text)
    abab_grammar = to_wcnf(abab_grammar_raw)
    abab_res = cfpq_matrix(graph, abab_grammar, use_sparse=True)
    
    if "S" in abab_res:
        for i, j in abab_res["S"]:
            if i == j:
                errors.append(
                    f"Обнаружен циклический архитектурный антипаттерн взаимосвязи иерархий (a^+ b^+ a^+ b^+) "
                    f"для класса '{class_names[i]}'"
                )
                
    return errors


# ═══════════════════════════════════════════════════════════════════════════
# БЛОК ЗАПУСКА И ТЕСТИРОВАНИЯ (Заменяет внешние TDL-файлы)
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=== ЗАПУСК ВАЛИДАЦИИ UML ДИАГРАММ ЧЕРЕЗ CFPQ ===")

    # -------------------------------------------------------------------------
    # Сценарий 1: Корректная диаграмма (Ошибок быть не должно)
    # -------------------------------------------------------------------------
    print("\nТест 1: Валидация корректной диаграммы...")
    d_correct = ClassDiagram()
    d_correct.add_classifier(Class(name="Animal"))
    d_correct.add_classifier(Class(name="Dog"))
    d_correct.add_generalization(specific="Dog", general="Animal") # Dog -> Animal
    
    errors_1 = validate_uml_cycles(d_correct)
    print(f"Результат: {'[FAIL] ' + str(errors_1) if errors_1 else '[OK] Ошибок не обнаружено.'}")

    # -------------------------------------------------------------------------
    # Сценарий 2: Цикл наследования (Должен сработать subclassof_cnf)
    # -------------------------------------------------------------------------
    print("\nТест 2: Валидация диаграммы с циклом наследования...")
    d_cycle = ClassDiagram()
    d_cycle.add_classifier(Class(name="ClassA"))
    d_cycle.add_classifier(Class(name="ClassB"))
    
    # Цикл: ClassA -> ClassB -> ClassA
    d_cycle.add_generalization(specific="ClassA", general="ClassB")
    d_cycle.add_generalization(specific="ClassB", general="ClassA")
    
    errors_2 = validate_uml_cycles(d_cycle)
    if errors_2:
        print("[OK] Алгоритм успешно обнаружил ошибку:")
        for err in errors_2:
            print(f"  - {err}")
    else:
        print("[FAIL] Алгоритм пропустил цикл наследования!")

    # -------------------------------------------------------------------------
    # Сценарий 3: Сложный антипаттерн (Должен сработать abab_cnf)
    # Цепочка: A --(a)--> B --(b)--> C --(a)--> D --(b)--> A
    # -------------------------------------------------------------------------
    print("\nТест 3: Валидация сложного циклического антипаттерна (abab)...")
    d_abab = ClassDiagram()
    d_abab.add_classifier(Class(name="A"))
    d_abab.add_classifier(Class(name="B"))
    d_abab.add_classifier(Class(name="C"))
    d_abab.add_classifier(Class(name="D"))
    
    # Наследования (a)
    d_abab.add_generalization(specific="A", general="B")
    d_abab.add_generalization(specific="C", general="D")
    
    # Зависимости (b)
    d_abab.add_dependency(client="B", supplier="C", stereotype=DependencyStereotype.USE)
    d_abab.add_dependency(client="D", supplier="A", stereotype=DependencyStereotype.USE)
    
    errors_3 = validate_uml_cycles(d_abab)
    if errors_3:
        print("[OK] Алгоритм успешно обнаружил сложный антипаттерн:")
        for err in errors_3:
            print(f"  - {err}")
    else:
        print("[FAIL] Алгоритм пропустил антипаттерн abab!")