from __future__ import annotations

from enum import Enum
from typing import List, Optional, Union, Dict, Any

from pydantic import BaseModel, Field, model_validator

# ============================================================
# Импорт из ontol-v3
# ============================================================

import sys, os

# Добавляем путь к ontol-v3, если его нет
_ontol_v3_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "ontol-v3",
)
if _ontol_v3_path not in sys.path:
    sys.path.insert(0, _ontol_v3_path)

from uml_dsl.models import (
    Class,
    Attribute,
    Operation,
    Parameter,
    Classifier,
    Multiplicity,
    MultiplicityRange,
    TaggedValue,
    TemplateParameter,
    Visibility,
    Scope,
    Stereotype,
    ParamDirection,
    Concurrency,
    Changeability,
    PRIMITIVE_TYPE_MAP,
)
from uml_dsl.relationships import (
    Association,
    AssociationEnd,
    AggregationEnd,
    Dependency,
    Generalization,
    Realization,
    TemplateBinding,
    AggregationKind,
    DependencyStereotype,
    CollectionKind,
)
from uml_dsl.diagram import ClassDiagram, ClassPosition
from uml_dsl.enums import (
    Visibility,
    Scope,
    Changeability,
    ParamDirection,
    Concurrency,
    CollectionKind,
    Stereotype,
    DependencyStereotype,
    AggregationKind,
)


# ============================================================
# Функция создания UML диаграммы для CIAO
# ============================================================

def create_ciao_uml_diagram() -> ClassDiagram:
    """
    Создает UML Class Diagram для языка CIAO.
    
    Returns:
        ClassDiagram: Готовая UML диаграмма классов CIAO
    """
    diagram = ClassDiagram(
        title="CIAO Language Meta-Model",
        classifiers={},
        associations=[],
        generalizations=[],
        dependencies=[],
    )
    
    # ============================================================
    # 1. Основные классы
    # ============================================================
    
    # CIAO_Prog - корневой класс
    ciao_prog = Class(
        name="CIAO_Prog",
        visibility=Visibility.PUBLIC,
        stereotype=Stereotype.DATA_TYPE,
        attributes=[
            Attribute(
                name="automaton_objects",
                type_="Auto_Obj[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE
            )
        ]
    )
    diagram.add_classifier(ciao_prog)
    
    # Auto_Obj - объект-автомат
    auto_obj = Class(
        name="Auto_Obj",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="s",
                type_="String",
                visibility=Visibility.PRIVATE,
                initial_value="\"initial\""
            ),
            Attribute(
                name="V",
                type_="Var[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE
            ),
            Attribute(
                name="P",
                type_="Interface[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE
            ),
            Attribute(
                name="S",
                type_="State[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE
            )
        ]
    )
    diagram.add_classifier(auto_obj)
    
    # Var - переменная
    var = Class(
        name="Var",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="v",
                type_="Any",
                visibility=Visibility.PRIVATE,
                description="Текущее значение"
            ),
            Attribute(
                name="t",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Тип переменной"
            ),
            Attribute(
                name="r",
                type_="Boolean",
                visibility=Visibility.PRIVATE,
                initial_value="false",
                description="Флаг инициализации"
            )
        ]
    )
    diagram.add_classifier(var)
    
    # Interface - интерфейс
    interface = Class(
        name="Interface",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="kind",
                type_="I_Kind",
                visibility=Visibility.PRIVATE
            ),
            Attribute(
                name="sort",
                type_="I_Sort",
                visibility=Visibility.PRIVATE
            ),
            Attribute(
                name="link",
                type_="Link",
                multiplicity=MultiplicityRange(lower=0, upper=1),
                visibility=Visibility.PRIVATE
            )
        ]
    )
    diagram.add_classifier(interface)
    
    # Link - ссылка на связанный интерфейс
    link = Class(
        name="Link",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="a",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя связанного Auto_Obj"
            ),
            Attribute(
                name="p",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя связанного интерфейса"
            )
        ]
    )
    diagram.add_classifier(link)
    
    # ============================================================
    # 2. Состояния и переходы
    # ============================================================
    
    # State - состояние
    state = Class(
        name="State",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="transitions",
                type_="Transition[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE
            )
        ]
    )
    diagram.add_classifier(state)
    
    # Transition - переход
    transition = Class(
        name="Transition",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="t",
                type_="Trigger",
                visibility=Visibility.PRIVATE
            ),
            Attribute(
                name="m",
                type_="TransitionCase",
                visibility=Visibility.PRIVATE
            )
        ]
    )
    diagram.add_classifier(transition)
    
    # TransitionCase - вариант перехода (абстрактный)
    transition_case = Class(
        name="TransitionCase",
        visibility=Visibility.PUBLIC,
        is_abstract=True,
        attributes=[
            Attribute(
                name="tag",
                type_="TransitionTag",
                visibility=Visibility.PROTECTED
            )
        ]
    )
    diagram.add_classifier(transition_case)
    
    # Loop - циклический переход
    loop = Class(
        name="Loop",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="b",
                type_="BoolExpr",
                visibility=Visibility.PRIVATE,
                description="Утверждение (тело цикла)"
            )
        ]
    )
    diagram.add_classifier(loop)
    
    # Direct - прямой переход
    direct = Class(
        name="Direct",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="f",
                type_="Effect",
                visibility=Visibility.PRIVATE,
                description="Эффект перехода"
            ),
            Attribute(
                name="s",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Целевое состояние"
            )
        ]
    )
    diagram.add_classifier(direct)
    
    # Choice - условный переход
    choice = Class(
        name="Choice",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="c",
                type_="BoolExpr",
                visibility=Visibility.PRIVATE,
                description="Условие-страж"
            ),
            Attribute(
                name="f1",
                type_="Effect",
                visibility=Visibility.PRIVATE,
                description="Эффект ветки then"
            ),
            Attribute(
                name="s1",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Целевое состояние ветки then"
            ),
            Attribute(
                name="f0",
                type_="Effect",
                visibility=Visibility.PRIVATE,
                description="Эффект ветки else"
            ),
            Attribute(
                name="s0",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Целевое состояние ветки else"
            )
        ]
    )
    diagram.add_classifier(choice)
    
    # ============================================================
    # 3. Триггеры и эффекты
    # ============================================================
    
    # Trigger - триггер
    trigger = Class(
        name="Trigger",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="i",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя интерфейса"
            ),
            Attribute(
                name="n",
                type_="Integer",
                visibility=Visibility.PRIVATE,
                description="Арность"
            ),
            Attribute(
                name="X",
                type_="String[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE,
                description="Имена переменных"
            )
        ]
    )
    diagram.add_classifier(trigger)
    
    # BoolExpr - булево выражение
    bool_expr = Class(
        name="BoolExpr",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="expr",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Текстовое представление"
            )
        ]
    )
    diagram.add_classifier(bool_expr)
    
    # Effect - эффект
    effect = Class(
        name="Effect",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="n",
                type_="Integer",
                visibility=Visibility.PRIVATE,
                description="Количество действий"
            ),
            Attribute(
                name="A",
                type_="Action[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE,
                description="Последовательность действий"
            )
        ]
    )
    diagram.add_classifier(effect)
    
    # ============================================================
    # 4. Действия (Action - абстрактный)
    # ============================================================
    
    # Action - действие (абстрактный)
    action = Class(
        name="Action",
        visibility=Visibility.PUBLIC,
        is_abstract=True,
        attributes=[
            Attribute(
                name="tag",
                type_="ActionTag",
                visibility=Visibility.PROTECTED
            )
        ]
    )
    diagram.add_classifier(action)
    
    # Call - вызов интерфейса
    call = Class(
        name="Call",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="i",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя интерфейса"
            ),
            Attribute(
                name="n",
                type_="Integer",
                visibility=Visibility.PRIVATE,
                description="Арность"
            ),
            Attribute(
                name="X",
                type_="String[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE,
                description="Параметры (выражения)"
            )
        ]
    )
    diagram.add_classifier(call)
    
    # Assign - присваивание
    assign = Class(
        name="Assign",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(
                name="v",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя переменной (LHS)"
            ),
            Attribute(
                name="x",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Выражение (RHS)"
            )
        ]
    )
    diagram.add_classifier(assign)
    
    # ============================================================
    # 5. Событие
    # ============================================================
    
    # Event - событие
    event = Class(
        name="Event",
        visibility=Visibility.PUBLIC,
        stereotype=Stereotype.DATA_TYPE,
        attributes=[
            Attribute(
                name="e",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя события"
            ),
            Attribute(
                name="a",
                type_="String",
                visibility=Visibility.PRIVATE,
                description="Имя объекта-автомата"
            ),
            Attribute(
                name="n",
                type_="Integer",
                visibility=Visibility.PRIVATE,
                description="Арность"
            ),
            Attribute(
                name="X",
                type_="Any[]",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                visibility=Visibility.PRIVATE,
                description="Аргументы (значения)"
            )
        ]
    )
    diagram.add_classifier(event)
    
    # ============================================================
    # 6. Отношения обобщения (Generalization)
    # ============================================================
    
    # TransitionCase -> Loop, Direct, Choice
    diagram.add_generalization("Loop", "TransitionCase")
    diagram.add_generalization("Direct", "TransitionCase")
    diagram.add_generalization("Choice", "TransitionCase")
    
    # Action -> Call, Assign
    diagram.add_generalization("Call", "Action")
    diagram.add_generalization("Assign", "Action")
    
    # ============================================================
    # 7. Отношения композиции (Composition)
    # ============================================================
    
    # CIAO_Prog -> Auto_Obj (1..*)
    diagram.add_aggregation(
        whole="CIAO_Prog",
        part="Auto_Obj",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=None),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="automaton_objects"
    )
    
    # Auto_Obj -> Var (0..*)
    diagram.add_aggregation(
        whole="Auto_Obj",
        part="Var",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=None),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="V"
    )
    
    # Auto_Obj -> Interface (0..*)
    diagram.add_aggregation(
        whole="Auto_Obj",
        part="Interface",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=None),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="P"
    )
    
    # Auto_Obj -> State (0..*)
    diagram.add_aggregation(
        whole="Auto_Obj",
        part="State",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=None),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="S"
    )
    
    # State -> Transition (0..*)
    diagram.add_aggregation(
        whole="State",
        part="Transition",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=None),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="transitions"
    )
    
    # Transition -> Trigger (1..1)
    diagram.add_aggregation(
        whole="Transition",
        part="Trigger",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="t"
    )
    
    # Transition -> TransitionCase (1..1)
    diagram.add_aggregation(
        whole="Transition",
        part="TransitionCase",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="m"
    )
    
    # Direct -> Effect (1..1)
    diagram.add_aggregation(
        whole="Direct",
        part="Effect",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="f"
    )
    
    # Choice -> Effect (2 - f1 и f0)
    # Создаем отдельные связи для f1 и f0
    diagram.add_aggregation(
        whole="Choice",
        part="Effect",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=2, upper=2),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="effects"
    )
    
    # Effect -> Action (0..*)
    diagram.add_aggregation(
        whole="Effect",
        part="Action",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=None),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="A"
    )
    
    # ============================================================
    # 8. Отношения агрегации (Aggregation)
    # ============================================================
    
    # Interface -> Link (0..1)
    diagram.add_aggregation(
        whole="Interface",
        part="Link",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=0, upper=1),
        aggregation_kind=AggregationKind.AGGREGATION,
        name="link"
    )
    
    # ============================================================
    # 9. Дополнительные связи (Association)
    # ============================================================
    
    # Auto_Obj ссылается на себя через s (текущее состояние)
    # Это отношение показываем как зависимость
    diagram.add_dependency(
        client="Auto_Obj",
        supplier="State",
        stereotype=DependencyStereotype.USE
    )
    
    # Loop использует BoolExpr
    diagram.add_dependency(
        client="Loop",
        supplier="BoolExpr",
        stereotype=DependencyStereotype.USE
    )
    
    # Choice использует BoolExpr
    diagram.add_dependency(
        client="Choice",
        supplier="BoolExpr",
        stereotype=DependencyStereotype.USE
    )
    
    # ============================================================
    # 10. Валидация диаграммы
    # ============================================================
    
    try:
        diagram.validate_all()
        print("✅ UML диаграмма CIAO успешно создана и валидна")
    except ValueError as e:
        print(f"⚠️ Предупреждение при валидации: {e}")
    
    return diagram


def create_handler_storage_instance_diagram() -> ClassDiagram:
    """
    Создает UML диаграмму для Handler & Storage (с картинки),
    используя CIAO метамодель через стереотип 'instanceOf'.
    """
    # 1. Получаем готовую базовую метамодель CIAO
    diagram = create_ciao_uml_diagram()

    # ============================================================
    # 1. Создаем конкретные классы-экземпляры (Instance Classes)
    # ============================================================

    # --- Хранилище (Storage) ---
    # Storage является экземпляром Auto_Obj из метамодели
    storage = Class(
        name="Storage",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(name="auto_objs", type_="Auto_Obj[]", visibility=Visibility.PRIVATE),
            Attribute(name="current_ao", type_="Auto_Obj", visibility=Visibility.PRIVATE)
        ]
    )
    diagram.add_classifier(storage)

    # --- Обработчик (Handler) ---
    # Handler тоже является экземпляром Auto_Obj (он тоже автомат)
    handler = Class(
        name="Handler",
        visibility=Visibility.PUBLIC,
        attributes=[
            Attribute(name="i", type_="Integer", visibility=Visibility.PRIVATE),
            Attribute(name="f", type_="Effect", visibility=Visibility.PRIVATE)
        ]
    )
    diagram.add_classifier(handler)

    # --- Состояния автомата Handler (States) ---
    # Каждое состояние - экземпляр State из метамодели
    state_idle = Class(name="Idle", visibility=Visibility.PUBLIC)
    state_trigger = Class(name="Trigger", visibility=Visibility.PUBLIC)
    state_cond1 = Class(name="Cond1", visibility=Visibility.PUBLIC)
    state_cond2 = Class(name="Cond2", visibility=Visibility.PUBLIC)
    state_choice = Class(name="Choice", visibility=Visibility.PUBLIC)
    state_direct = Class(name="Direct", visibility=Visibility.PUBLIC)
    state_effect = Class(name="EffectState",
                         visibility=Visibility.PUBLIC)  # Переименовано, чтобы не путать с метамоделью Effect
    state_action = Class(name="ActionState", visibility=Visibility.PUBLIC)
    state_call = Class(name="CallState", visibility=Visibility.PUBLIC)
    state_assign = Class(name="AssignState", visibility=Visibility.PUBLIC)

    for state_cls in [state_idle, state_trigger, state_cond1, state_cond2,
                      state_choice, state_direct, state_effect, state_action,
                      state_call, state_assign]:
        diagram.add_classifier(state_cls)

    # --- Переходы (Transitions) ---
    # Экземпляры TransitionCase из метамодели
    trans_direct = Class(name="DirectTransition", visibility=Visibility.PUBLIC)
    trans_choice = Class(name="ChoiceTransition", visibility=Visibility.PUBLIC)
    trans_loop = Class(name="LoopTransition", visibility=Visibility.PUBLIC)

    diagram.add_classifier(trans_direct)
    diagram.add_classifier(trans_choice)
    diagram.add_classifier(trans_loop)

    # --- Триггеры (Triggers) ---
    # Экземпляры Trigger
    trig_handle = Class(name="Trigger_Handle", visibility=Visibility.PUBLIC)
    trig_tick = Class(name="Trigger_Tick", visibility=Visibility.PUBLIC)
    diagram.add_classifier(trig_handle)
    diagram.add_classifier(trig_tick)

    # ============================================================
    # 2. Добавляем связи instanceOf (Dependency)
    # ============================================================

    # Storage является экземпляром Auto_Obj
    diagram.add_dependency(
        client="Storage", supplier="Auto_Obj",
        stereotype=DependencyStereotype.INSTANCE_OF
    )

    # Handler является экземпляром Auto_Obj
    diagram.add_dependency(
        client="Handler", supplier="Auto_Obj",
        stereotype=DependencyStereotype.INSTANCE_OF
    )

    # Все состояния Handler являются экземплярами State
    for state_name in ["Idle", "Trigger", "Cond1", "Cond2", "Choice", "Direct",
                       "EffectState", "ActionState", "CallState", "AssignState"]:
        diagram.add_dependency(
            client=state_name, supplier="State",
            stereotype=DependencyStereotype.INSTANCE_OF
        )

    # Переходы (Direct, Choice, Loop) являются экземплярами TransitionCase
    for trans_name in ["DirectTransition", "ChoiceTransition", "LoopTransition"]:
        diagram.add_dependency(
            client=trans_name, supplier="TransitionCase",
            stereotype=DependencyStereotype.INSTANCE_OF
        )

    # Триггеры являются экземплярами Trigger
    for trig_name in ["Trigger_Handle", "Trigger_Tick"]:
        diagram.add_dependency(
            client=trig_name, supplier="Trigger",
            stereotype=DependencyStereotype.INSTANCE_OF
        )

    # ============================================================
    # 3. Описываем структуру Handler (Composition/Aggregation)
    # ============================================================

    # Handler имеет атрибут i (Integer). В метамодели это не агрегация, а просто атрибут.
    # Но визуально на схеме Handler владеет состояниями.
    # В CIAO метамодели: Auto_Obj -> State (композиция).
    # Мы создаем эту связь для Handler (как экземпляра Auto_Obj).

    # Handler -> Idle (композиция)
    diagram.add_aggregation(
        whole="Handler", part="Idle",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="current_state_idle"
    )

    # Handler -> Trigger (композиция)
    diagram.add_aggregation(
        whole="Handler", part="Trigger",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="current_state_trigger"
    )

    # Аналогично можно добавить связи для Cond1, Cond2, Choice и т.д.
    # Для краткости опустим их все, так как логика ясна.

    # ============================================================
    # 4. Связь Handler с Storage (Association / Dependency)
    # ============================================================

    # Handler использует Storage для вызова методов (getArgsNum, getTrTag и т.д.)
    diagram.add_dependency(
        client="Handler", supplier="Storage",
        stereotype=DependencyStereotype.USE
    )

    # ============================================================
    # 5. Описываем логику переходов через метамодель (пример)
    # ============================================================

    # На картинке: Cond1 -> [getTrTag(e) == "direct"] -> Direct
    # В терминах метамодели это значит:
    # Состояние Cond1 владеет переходом, у которого Trigger = getTrTag, а TransitionCase = DirectTransition

    # Добавляем конкретные переходы (экземпляры Transition)
    trans_cond1_to_direct = Class(name="Trans_Cond1_Direct", visibility=Visibility.PUBLIC)
    diagram.add_classifier(trans_cond1_to_direct)

    # Этот переход является экземпляром метамодели Transition
    diagram.add_dependency(
        client="Trans_Cond1_Direct", supplier="Transition",
        stereotype=DependencyStereotype.INSTANCE_OF
    )

    # У перехода есть Триггер (экземпляр Trigger)
    diagram.add_aggregation(
        whole="Trans_Cond1_Direct", part="Trigger_Handle",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="tr"
    )

    # У перехода есть Вариант перехода (экземпляр DirectTransition)
    diagram.add_aggregation(
        whole="Trans_Cond1_Direct", part="DirectTransition",
        whole_multiplicity=MultiplicityRange(lower=1, upper=1),
        part_multiplicity=MultiplicityRange(lower=1, upper=1),
        aggregation_kind=AggregationKind.COMPOSITION,
        name="case"
    )

    # ============================================================
    # 6. Финальная валидация
    # ============================================================

    try:
        diagram.validate_all()
        print("✅ UML диаграмма с instanceOf для Handler & Storage создана")
    except ValueError as e:
        print(f"⚠️ Предупреждение: {e}")

    return diagram


# ============================================================
# Пример использования
# ============================================================

if __name__ == "__main__":
    # Создаем UML диаграмму для CIAO
    diagram = create_handler_storage_instance_diagram()
    
    print("\n📊 Создана UML диаграмма для языка CIAO")
    print(f"📦 Классификаторов: {len(diagram.classifiers)}")
    print(f"🔗 Ассоциаций: {len(diagram.associations)}")
    print(f"📈 Обобщений: {len(diagram.generalizations)}")
    print(f"🔀 Зависимостей: {len(diagram.dependencies)}")
    
    print("\n📋 Список классов:")
    for name, cls in diagram.classifiers.items():
        attrs = len(cls.attributes)
        ops = len(cls.operations)
        abstract = " (abstract)" if cls.is_abstract else ""
        print(f"  - {name}{abstract}: {attrs} атрибутов, {ops} операций")
    
    # Генерация SVG (опционально)
    svg = diagram.to_svg(width=2000, height=1400, theme="light")
    with open("ciao_uml_diagram.svg", "w") as f:
        f.write(svg)
    # print("\n✅ SVG диаграмма сохранена в 'ciao_uml_diagram.svg'")