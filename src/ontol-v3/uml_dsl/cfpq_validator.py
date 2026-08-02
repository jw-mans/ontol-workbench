from __future__ import annotations

# Ищем циклы наследования и антипаттерн a+ b+ a+ b+. Оба шаблона регулярны,
# поэтому берём линейный RPQ-детектор из rpq_cycles вместо матричного CFPQ.
# Матричная версия (cfpq_matrix, grammar_utils) осталась под КС-шаблоны.

from .rpq_cycles import (
    abab_cycle_vertices,
    association_cycle_vertices,
    dependency_cycle_vertices,
    diagram_to_labeled_graph,
    inheritance_cycle_vertices,
    realization_cycle_vertices,
)


def validate_uml_cycles(diagram) -> tuple[list[str], list[str]]:
    """Вернуть (ошибки, предупреждения) по циклам зависимостей.

    Циклы наследования, зависимостей, ассоциаций и реализаций — жёсткие ошибки.
    Антипаттерн a^+ c^+ a^+ c^+ — предупреждение: это архитектурный smell, а не
    ошибка, и он естественно возникает, например, из пары обобщение+ассоциация.
    """
    errors: list[str] = []
    warnings: list[str] = []

    class_names, edges = diagram_to_labeled_graph(diagram)
    n = len(class_names)
    if n == 0:
        return errors, warnings

    for i in sorted(inheritance_cycle_vertices(n, edges)):
        errors.append(f"Обнаружен цикл наследования для класса '{class_names[i]}'")

    for i in sorted(dependency_cycle_vertices(n, edges)):
        errors.append(f"Обнаружен цикл зависимостей для класса '{class_names[i]}'")

    for i in sorted(association_cycle_vertices(n, edges)):
        errors.append(f"Обнаружен цикл ассоциаций для класса '{class_names[i]}'")

    for i in sorted(realization_cycle_vertices(n, edges)):
        errors.append(f"Обнаружен цикл реализаций для класса '{class_names[i]}'")

    for i in sorted(abab_cycle_vertices(n, edges)):
        warnings.append(
            f"Обнаружен циклический архитектурный антипаттерн взаимосвязи иерархий (a^+ c^+ a^+ c^+) "
            f"для класса '{class_names[i]}'"
        )

    return errors, warnings


if __name__ == "__main__":
    # Локальные импорты: на уровне модуля они дают цикл с diagram.py.
    from .diagram import ClassDiagram
    from .models import Class
    from .enums import DependencyStereotype

    # 1) чистая диаграмма — ошибок быть не должно
    d_correct = ClassDiagram()
    d_correct.add_classifier(Class(name="Animal"))
    d_correct.add_classifier(Class(name="Dog"))
    d_correct.add_generalization(specific="Dog", general="Animal")
    print("чистая:", validate_uml_cycles(d_correct))  # ([], [])

    # 2) цикл наследования ClassA <-> ClassB (ошибка)
    d_cycle = ClassDiagram()
    d_cycle.add_classifier(Class(name="ClassA"))
    d_cycle.add_classifier(Class(name="ClassB"))
    d_cycle.add_generalization(specific="ClassA", general="ClassB")
    d_cycle.add_generalization(specific="ClassB", general="ClassA")
    print("цикл наследования (ошибки, предупр.):", validate_uml_cycles(d_cycle))

    # 3) антипаттерн: A -a-> B -b-> C -a-> D -b-> A
    d_abab = ClassDiagram()
    for name in ("A", "B", "C", "D"):
        d_abab.add_classifier(Class(name=name))
    d_abab.add_generalization(specific="A", general="B")
    d_abab.add_generalization(specific="C", general="D")
    d_abab.add_dependency(client="B", supplier="C", stereotype=DependencyStereotype.USE)
    d_abab.add_dependency(client="D", supplier="A", stereotype=DependencyStereotype.USE)
    print("антипаттерн (ошибки, предупр.):", validate_uml_cycles(d_abab))
