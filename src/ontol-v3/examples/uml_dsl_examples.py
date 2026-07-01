"""
Примеры использования UML DSL, соответствующие иллюстрациям из книги
«Моделирование на UML» (Новиков, Иванов), разделы 3.1–3.3.

Каждый пример создаёт модель и экспортирует её в интерактивный HTML/SVG.
"""
from pathlib import Path
from uml_dsl import (
    AggregationKind,
    Association,
    AssociationClass,
    AssociationEnd,
    Attribute,
    Changeability,
    ClassDiagram,
    ClassPosition,
    Class,
    CollectionKind,
    Concurrency,
    Dependency,
    DependencyStereotype,
    Generalization,
    GeneralizationSet,
    Multiplicity,
    MultiplicityRange,
    Operation,
    Parameter,
    ParamDirection,
    Realization,
    Scope,
    Stereotype,
    TaggedValue,
    TemplateParameter,
    Visibility,
)

OUT_DIR = Path(__file__).parent / "09_02" / "generated"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def save(diagram: ClassDiagram, filename: str) -> None:
    html = diagram.to_html(width=1400, height=900)
    path = OUT_DIR / filename
    path.write_text(html, encoding="utf-8")
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 1: Типичная нотация класса (pict_3_4)
# §3.2.1 — Класс Person с атрибутами и операциями
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_4():
    """Типичная нотация класса — класс Person (§3.2.1).

    Цитата: «Нотация классов очень проста — это всегда прямоугольник.
    Если секций более одной, то внутренность прямоугольника делится
    горизонтальными линиями на части, соответствующие секциям.»
    """
    person = Class(
        name="Person",
        attributes=[
            # «name — минимальное описание, только имя»
            Attribute(name="name"),
            # «+name — имя + видимость public»
            Attribute(name="namePublic", visibility=Visibility.PUBLIC),
            # «-name : String — имя, тип, видимость private»
            Attribute(name="nameTyped", visibility=Visibility.PRIVATE, type_="String"),
            # «-name[1..3] : String — с кратностью»
            Attribute(
                name="nameParts", visibility=Visibility.PRIVATE,
                type_="String",
                multiplicity=MultiplicityRange(lower=1, upper=3),
            ),
            # «-name : String = "Novikov" — с начальным значением»
            Attribute(
                name="surname", visibility=Visibility.PRIVATE,
                type_="String", initial_value='"Novikov"',
            ),
            # «+name : String {readOnly} — только для чтения»
            Attribute(
                name="displayName", visibility=Visibility.PUBLIC,
                type_="String", changeability=Changeability.READ_ONLY,
            ),
        ],
        operations=[
            # «move() — минимальное описание»
            Operation(name="move"),
            # «+move(in from, in to) — видимость, направление, имена»
            Operation(
                name="transfer", visibility=Visibility.PUBLIC,
                parameters=[
                    Parameter(name="from", direction=ParamDirection.IN),
                    Parameter(name="to", direction=ParamDirection.IN),
                ],
            ),
            # «+move(in from:Department, in to:Department) — полная сигнатура»
            Operation(
                name="relocate", visibility=Visibility.PUBLIC,
                parameters=[
                    Parameter(name="from", type_="Department"),
                    Parameter(name="to", type_="Department"),
                ],
            ),
            # «+getName():String {isQuery} — функция без побочных эффектов»
            Operation(
                name="getName", visibility=Visibility.PUBLIC,
                return_type="String", is_query=True,
            ),
        ],
    )

    d = ClassDiagram(title="pict_3_4 — Типичная нотация класса")
    d.add_classifier(person)
    d.auto_layout()
    save(d, "pict_3_4.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 2: Служба (utility) (pict_3_5)
# §3.2.1 — Стереотип «utility»
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_5():
    """Секция имени службы — стереотип «utility» (§3.2.1).

    Цитата: «Служба (utility) — классификатор, не имеющий экземпляров
    (кратность 0). Все составляющие службы имеют областью действия
    классификатор.»
    """
    math_lib = Class(
        name="MathLib",
        stereotype=Stereotype.UTILITY,
        attributes=[
            Attribute(
                name="PI", visibility=Visibility.PUBLIC,
                type_="double", initial_value="3.14159",
                scope=Scope.CLASSIFIER,
                changeability=Changeability.READ_ONLY,
            ),
        ],
        operations=[
            Operation(
                name="sin", visibility=Visibility.PUBLIC,
                parameters=[Parameter(name="x", type_="double")],
                return_type="double", is_query=True, scope=Scope.CLASSIFIER,
            ),
            Operation(
                name="cos", visibility=Visibility.PUBLIC,
                parameters=[Parameter(name="x", type_="double")],
                return_type="double", is_query=True, scope=Scope.CLASSIFIER,
            ),
        ],
    )

    d = ClassDiagram(title="pict_3_5 — Служба «utility»")
    d.add_classifier(math_lib)
    d.auto_layout()
    save(d, "pict_3_5.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 3: Перечисление (pict_3_6)
# §3.2.4 — Стереотип «enumeration»
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_6():
    """Перечислимый тип данных 3Logic (§3.2.4).

    Цитата: ««enumeration» — все возможные значения перечислены
    (например, Boolean с true/false).»
    """
    logic3 = Class(
        name="3Logic",
        stereotype=Stereotype.ENUMERATION,
        attributes=[
            Attribute(name="true", scope=Scope.CLASSIFIER),
            Attribute(name="false", scope=Scope.CLASSIFIER),
            Attribute(name="unknown", scope=Scope.CLASSIFIER),
        ],
        operations=[
            Operation(
                name="not", visibility=Visibility.PUBLIC,
                parameters=[Parameter(name="a", type_="3Logic")],
                return_type="3Logic", is_query=True, scope=Scope.CLASSIFIER,
            ),
            Operation(
                name="and", visibility=Visibility.PUBLIC,
                parameters=[
                    Parameter(name="a", type_="3Logic"),
                    Parameter(name="b", type_="3Logic"),
                ],
                return_type="3Logic", is_query=True, scope=Scope.CLASSIFIER,
            ),
            Operation(
                name="or", visibility=Visibility.PUBLIC,
                parameters=[
                    Parameter(name="a", type_="3Logic"),
                    Parameter(name="b", type_="3Logic"),
                ],
                return_type="3Logic", is_query=True, scope=Scope.CLASSIFIER,
            ),
        ],
    )

    d = ClassDiagram(title="pict_3_6 — Перечисление «enumeration»")
    d.add_classifier(logic3)
    d.auto_layout()
    save(d, "pict_3_6.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 4: Тип данных Real (pict_3_7)
# §3.2.4 — Стереотип «dataType»
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_7():
    """Тип данных Real (§3.2.4).

    Цитата: «Тип данных (в UML) — классификатор, экземпляры которого
    не обладают индивидуальностью (identity).»
    """
    real_type = Class(
        name="Real",
        stereotype=Stereotype.DATA_TYPE,
        operations=[
            Operation(
                name="add", visibility=Visibility.PUBLIC,
                parameters=[
                    Parameter(name="a", type_="Real"),
                    Parameter(name="b", type_="Real"),
                ],
                return_type="Real", is_query=True, scope=Scope.CLASSIFIER,
            ),
            Operation(
                name="sub", visibility=Visibility.PUBLIC,
                parameters=[
                    Parameter(name="a", type_="Real"),
                    Parameter(name="b", type_="Real"),
                ],
                return_type="Real", is_query=True, scope=Scope.CLASSIFIER,
            ),
        ],
    )

    d = ClassDiagram(title="pict_3_7 — Тип данных «dataType»")
    d.add_classifier(real_type)
    d.auto_layout()
    save(d, "pict_3_7.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 5: Шаблон (template) с привязкой (pict_3_8)
# §3.2.5 — Явное и неявное связывание шаблона
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_8():
    """Явное и неявное связывание шаблона (§3.2.5).

    Цитата: «Шаблон — это сущность (чаще всего классификатор) с параметрами.
    Нотация: стандартный прямоугольник с пунктирным прямоугольником
    в верхнем правом углу.»
    """
    # Шаблон
    container = Classifier(
        name="Container",
        template_parameters=[
            TemplateParameter(name="T"),
            TemplateParameter(name="N", type_="int"),
        ],
        operations=[
            Operation(name="add", parameters=[Parameter(name="item", type_="T")]),
            Operation(name="get", parameters=[Parameter(name="index", type="int")],
                      return_type="T"),
        ],
    )

    # Явная привязка — класс со стереотипом «bind»
    address_list = Classifier(name="AddressList")

    d = ClassDiagram(title="pict_3_8 — Шаблон и привязка")
    d.add_classifier(container)
    d.add_classifier(address_list)
    d.add_dependency(
        "AddressList", "Container",
        stereotype=DependencyStereotype.BIND,
    )
    d.auto_layout()
    save(d, "pict_3_8.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 6: Интерфейс и реализация (pict_3_10)
# §3.3.1 — Отношения реализации и использования интерфейсов
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_10():
    """Отношения реализации и использования интерфейсов (§3.3.1).

    Цитата: «Никаких ограничений на использование отношения реализации
    не накладывается: класс может реализовывать много интерфейсов,
    и наоборот, интерфейс может быть реализован многими классами.»
    """
    i_printable = Classifier(
        name="IPrintable",
        stereotype=Stereotype.INTERFACE,
        is_abstract=True,
        operations=[
            Operation(name="print", is_abstract=True),
            Operation(name="preview", is_abstract=True),
        ],
    )
    document = Classifier(
        name="Document",
        attributes=[
            Attribute(name="content", visibility=Visibility.PRIVATE, type="String"),
        ],
        operations=[
            Operation(name="print"),
            Operation(name="preview"),
        ],
    )

    d = ClassDiagram(title="pict_3_10 — Реализация интерфейса")
    d.add_classifier(i_printable)
    d.add_classifier(document)
    d.add_realization("Document", "IPrintable")
    d.auto_layout()
    save(d, "pict_3_10.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 7: Обобщение (generalization) (pict_3_12)
# §3.3.2 — Отношение обобщения
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_12():
    """Отношение обобщения (§3.3.2).

    Цитата: «Принцип подстановки Лисков: экземпляр подкласса может
    использоваться везде, где используется экземпляр суперкласса.»

    Цитата: «Обобщения в модели должны образовывать строгий частичный порядок.»
    """
    shape = Classifier(
        name="Shape",
        is_abstract=True,
        operations=[
            Operation(name="draw", is_abstract=True),
            Operation(name="area", return_type="double", is_abstract=True),
        ],
    )
    circle = Classifier(
        name="Circle",
        attributes=[
            Attribute(name="radius", visibility=Visibility.PRIVATE, type="double"),
        ],
        operations=[
            Operation(name="draw"),
            Operation(name="area", return_type="double"),
        ],
    )
    rectangle = Classifier(
        name="Rectangle",
        attributes=[
            Attribute(name="width", visibility=Visibility.PRIVATE, type="double"),
            Attribute(name="height", visibility=Visibility.PRIVATE, type="double"),
        ],
        operations=[
            Operation(name="draw"),
            Operation(name="area", return_type="double"),
        ],
    )

    d = ClassDiagram(title="pict_3_12 — Обобщение")
    d.add_classifier(shape)
    d.add_classifier(circle)
    d.add_classifier(rectangle)
    d.add_generalization("Circle", "Shape")
    d.add_generalization("Rectangle", "Shape")
    d.auto_layout(cols=3)
    save(d, "pict_3_12.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 8: Набор обобщений (pict_3_13)
# §3.3.2 — Подмножества обобщений
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_13():
    """Подмножества обобщений (§3.3.2).

    Цитата: «{complete} — все возможные подтипы определены.
    {disjoint} — подклассы взаимно исключают друг друга.
    Значения по умолчанию — {incomplete, disjoint}.»
    """
    person = Class(name="Person")
    male = Class(name="Male")
    female = Class(name="Female")
    student = Class(name="Student")
    employee = Class(name="Employee")

    d = ClassDiagram(title="pict_3_13 — Наборы обобщений")
    for c in [person, male, female, student, employee]:
        d.add_classifier(c)

    # Набор по полу: complete, disjoint
    gs_gender = GeneralizationSet(
        name=person,
        generalizations=[
            Generalization(specific=male, general=person),
            Generalization(specific=female, general=person),
        ],
        is_complete=True,
        is_disjoint=True,
    )
    # Набор по роли: incomplete, overlapping
    gs_role = GeneralizationSet(
        name=person,
        generalizations=[
            Generalization(specific=student, general=person),
            Generalization(specific=employee, general=person),
        ],
        is_complete=False,
        is_disjoint=False,
    )
    d.generalization_sets = [gs_gender, gs_role]
    d.auto_layout(cols=5, spacing_x=240)
    save(d, "pict_3_13.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 9: Ассоциация с именем и кратностью (pict_3_15, pict_3_16)
# §3.3.4 — Дополнения ассоциации
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_15_16():
    """Ассоциация с именем, направлением чтения, кратностью (§3.3.4).

    Цитата: «Имя ассоциации — текстовая строка рядом с линией ассоциации.»
    Цитата: «Кратность полюса указывает, сколько объектов на этом конце
    участвуют в связи.»
    """
    person = Classifier(
        name="Person",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
        ],
    )
    position = Classifier(
        name="Position",
        attributes=[
            Attribute(name="title", visibility=Visibility.PRIVATE, type="String"),
        ],
    )

    d = ClassDiagram(title="pict_3_15/3_16 — Ассоциация")
    d.add_classifier(person)
    d.add_classifier(position)
    d.add_association(Association(
        name="occupies",
        ends=[
            AssociationEnd(
                classifier="Person",
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Position",
                multiplicity=MultiplicityRange(lower=0, upper=None),
            ),
        ],
    ))
    d.auto_layout(cols=2)
    save(d, "pict_3_15_16.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 10: Агрегация (pict_3_18)
# §3.3.5 — Отношение агрегации
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_18():
    """Агрегация (§3.3.5).

    Цитата: «Агрегация — это ассоциация между классом A (часть) и классом B
    (целое), которая означает, что экземпляры класса A входят в состав
    экземпляра класса B.»
    Нотация: пустой ромб на стороне целого.
    """
    department = Classifier(
        name="Department",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
        ],
    )
    person = Classifier(
        name="Person",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
        ],
    )

    d = ClassDiagram(title="pict_3_18 — Агрегация")
    d.add_classifier(department)
    d.add_classifier(person)
    d.add_association(Association(
        name="works in",
        ends=[
            AssociationEnd(
                classifier="Department",
                aggregation=AggregationKind.AGGREGATION,
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Person",
                multiplicity=MultiplicityRange(lower=0, upper=None),
            ),
        ],
    ))
    d.auto_layout(cols=2)
    save(d, "pict_3_18.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 11: Композиция (pict_3_19)
# §3.3.5 — Отношение композиции
# ═══════════════════════════════════════════════════════════════════════════


import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def example_pict_3_19():
    """Композиция (§3.3.5).

    Цитата: «Композиция — ассоциация, которая дополнительно накладывает
    более сильные ограничения в сравнении с агрегацией: композиционно
    часть может входить только в одно целое, часть существует, только пока
    существует целое.»
    Нотация: закрашенный ромб.
    """
    window = Classifier(
        name="Window",
        attributes=[
            Attribute(name="title", visibility=Visibility.PRIVATE, type="String"),
        ],
    )
    button = Classifier(
        name="Button",
        attributes=[
            Attribute(name="label", visibility=Visibility.PRIVATE, type="String"),
        ],
    )
    text_field = Classifier(
        name="TextField",
        attributes=[
            Attribute(name="text", visibility=Visibility.PRIVATE, type="String"),
        ],
    )

    d = ClassDiagram(title="pict_3_19 — Композиция")
    d.add_classifier(window)
    d.add_classifier(button)
    d.add_classifier(text_field)
    d.add_association(Association(
        ends=[
            AssociationEnd(
                classifier="Window",
                aggregation=AggregationKind.COMPOSITION,
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Button",
                multiplicity=MultiplicityRange(lower=0, upper=None),
            ),
        ],
    ))
    d.add_association(Association(
        ends=[
            AssociationEnd(
                classifier="Window",
                aggregation=AggregationKind.COMPOSITION,
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="TextField",
                multiplicity=MultiplicityRange(lower=0, upper=None),
            ),
        ],
    ))
    d.auto_layout(cols=3)
    save(d, "pict_3_19.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 12: Основная диаграмма ИС ОК (pict_3_20)
# §3.3.5 — Структура связей ИС отдела кадров
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_20():
    """Структура связей классов информационной системы отдела кадров (§3.3.5).

    Классы: Person, Department, Position.
    Ассоциации: Person occupies Position (1 к 0..*),
                Department contains Position (1 к 1..*),
                Department contains Person (агрегация).
    """
    person = Classifier(
        name="Person",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
            Attribute(name="birthDate", visibility=Visibility.PRIVATE, type="Date"),
        ],
        operations=[
            Operation(name="hire", visibility=Visibility.PUBLIC),
            Operation(name="fire", visibility=Visibility.PUBLIC),
        ],
    )
    department = Classifier(
        name="Department",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
        ],
        operations=[
            Operation(name="create", visibility=Visibility.PUBLIC),
            Operation(name="eliminate", visibility=Visibility.PUBLIC),
        ],
    )
    position = Classifier(
        name="Position",
        attributes=[
            Attribute(name="title", visibility=Visibility.PRIVATE, type="String"),
            Attribute(name="salary", visibility=Visibility.PRIVATE, type="double"),
        ],
        operations=[
            Operation(name="createVacancy", visibility=Visibility.PUBLIC),
            Operation(name="reducePosition", visibility=Visibility.PUBLIC),
        ],
    )

    d = ClassDiagram(title="pict_3_20 — ИС Отдел кадров")
    d.add_classifier(person)
    d.add_classifier(department)
    d.add_classifier(position)

    # Person occupies Position
    d.add_association(Association(
        name="occupies",
        ends=[
            AssociationEnd(
                classifier="Person",
                multiplicity=MultiplicityRange(lower=1, upper=1),
                role="employee",
            ),
            AssociationEnd(
                classifier="Position",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                role="position",
            ),
        ],
    ))

    # Department contains Position (composition)
    d.add_association(Association(
        ends=[
            AssociationEnd(
                classifier="Department",
                aggregation=AggregationKind.COMPOSITION,
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Position",
                multiplicity=MultiplicityRange(lower=1, upper=None),
            ),
        ],
    ))

    # Department – Person (aggregation)
    d.add_association(Association(
        name="employs",
        ends=[
            AssociationEnd(
                classifier="Department",
                aggregation=AggregationKind.AGGREGATION,
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Person",
                multiplicity=MultiplicityRange(lower=0, upper=None),
            ),
        ],
    ))

    d.auto_layout(cols=3, spacing_x=350)
    save(d, "pict_3_20.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 13: Навигация (pict_3_30)
# §3.3.6 — Навигация
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_30():
    """Использование направлений навигации (§3.3.6).

    Цитата: «Стрелка → = navigable, X = not navigable.»
    """
    order = Classifier(
        name="Order",
        attributes=[Attribute(name="id", type="int")],
    )
    customer = Classifier(
        name="Customer",
        attributes=[Attribute(name="name", type="String")],
    )

    d = ClassDiagram(title="pict_3_30 — Навигация")
    d.add_classifier(order)
    d.add_classifier(customer)
    d.add_association(Association(
        name="places",
        ends=[
            AssociationEnd(
                classifier="Customer",
                navigable=False,
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Order",
                navigable=True,
                multiplicity=MultiplicityRange(lower=0, upper=None),
            ),
        ],
    ))
    d.auto_layout(cols=2)
    save(d, "pict_3_30.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 14: Многополюсная ассоциация (pict_3_32)
# §3.3.6 — N-арные ассоциации
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_32():
    """Многополюсная ассоциация (§3.3.6).

    Цитата: «Многополюсная ассоциация — с формальной точки зрения излишняя,
    но практически незаменимая.»
    Person × Position × Project
    """
    person = Classifier(name="Person")
    position = Classifier(name="Position")
    project = Classifier(name="Project")

    d = ClassDiagram(title="pict_3_32 — N-арная ассоциация")
    d.add_classifier(person)
    d.add_classifier(position)
    d.add_classifier(project)
    d.add_association(Association(
        name="Assignment",
        ends=[
            AssociationEnd(participant="Person",
                           multiplicity=MultiplicityRange(lower=1, upper=None)),
            AssociationEnd(participant="Position",
                           multiplicity=MultiplicityRange(lower=1, upper=1)),
            AssociationEnd(participant="Project",
                           multiplicity=MultiplicityRange(lower=1, upper=None)),
        ],
    ))
    d.auto_layout(cols=3)
    save(d, "pict_3_32.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 15: Класс ассоциации (pict_3_39)
# §3.3.8
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_39():
    """Класс ассоциации (§3.3.8).

    Цитата: «Класс ассоциации — сущность, которая является ассоциацией,
    но также имеет в своём составе составляющие класса.»
    """
    person = Classifier(name="Person")
    project = Classifier(name="Project")
    job = Classifier(
        name="Job",
        attributes=[
            Attribute(name="salary", type="double"),
            Attribute(name="startDate", type="Date"),
        ],
    )

    d = ClassDiagram(title="pict_3_39 — Класс ассоциации")
    d.add_classifier(person)
    d.add_classifier(project)
    d.add_classifier(job)
    d.association_classes.append(AssociationClass(
        name="works on",
        associated_classifier=job,
        ends=[
            AssociationEnd(
                classifier="Person",
                multiplicity=MultiplicityRange(lower=1, upper=None),
            ),
            AssociationEnd(
                classifier="Project",
                multiplicity=MultiplicityRange(lower=1, upper=None),
            ),
        ],
    ))
    d.auto_layout(cols=3)
    save(d, "pict_3_39.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 16: Упорядоченность и изменяемость (pict_3_35)
# §3.3.7
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_35():
    """Упорядоченность и изменяемость множества объектов на полюсе (§3.3.7).

    Цитата: «По умолчанию {set} — неупорядоченное, уникальное.
    {ordered} — упорядоченное, уникальное.
    {bag} — неупорядоченное, неуникальное.
    {sequence} — упорядоченное, неуникальное.»
    """
    polygon = Classifier(name="Polygon")
    point = Classifier(name="Point",
                        attributes=[
                            Attribute(name="x", type="double"),
                            Attribute(name="y", type="double"),
                        ])

    d = ClassDiagram(title="pict_3_35 — Упорядоченность")
    d.add_classifier(polygon)
    d.add_classifier(point)
    d.add_association(Association(
        name="vertices",
        ends=[
            AssociationEnd(
                classifier="Polygon",
                multiplicity=MultiplicityRange(lower=1, upper=1),
            ),
            AssociationEnd(
                classifier="Point",
                multiplicity=MultiplicityRange(lower=3, upper=None),
                collection_kind=CollectionKind.ORDERED,
                changeability=Changeability.READ_ONLY,
            ),
        ],
    ))
    d.auto_layout(cols=2)
    save(d, "pict_3_35.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 17: Полная диаграмма ИС ОК (pict_3_43)
# §3.3.8 — Итоговая диаграмма
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_43():
    """Основная диаграмма классов ИС ОК (§3.3, итог).

    Классы: Person, Department, Position.
    Включает все типы отношений: ассоциации с ролями, кратностями,
    агрегацию, композицию, навигацию.
    """
    person = Classifier(
        name="Person",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
            Attribute(name="birthDate", visibility=Visibility.PRIVATE, type="Date"),
            Attribute(name="address", visibility=Visibility.PRIVATE, type="String"),
        ],
        operations=[
            Operation(name="hire", visibility=Visibility.PUBLIC,
                      parameters=[Parameter(name="pos", type="Position")]),
            Operation(name="fire", visibility=Visibility.PUBLIC),
            Operation(name="transfer", visibility=Visibility.PUBLIC,
                      parameters=[
                          Parameter(name="from", type="Department"),
                          Parameter(name="to", type="Department"),
                      ]),
        ],
    )
    department = Classifier(
        name="Department",
        attributes=[
            Attribute(name="name", visibility=Visibility.PRIVATE, type="String"),
            Attribute(name="code", visibility=Visibility.PRIVATE, type="int"),
        ],
        operations=[
            Operation(name="create", visibility=Visibility.PUBLIC),
            Operation(name="eliminate", visibility=Visibility.PUBLIC),
        ],
    )
    position = Classifier(
        name="Position",
        attributes=[
            Attribute(name="title", visibility=Visibility.PRIVATE, type="String"),
            Attribute(name="salary", visibility=Visibility.PRIVATE, type="double"),
            Attribute(name="isVacant", visibility=Visibility.PRIVATE, type="Boolean"),
        ],
        operations=[
            Operation(name="createVacancy", visibility=Visibility.PUBLIC),
            Operation(name="reducePosition", visibility=Visibility.PUBLIC),
        ],
    )
    position_history = Classifier(
        name="PositionHistory",
        attributes=[
            Attribute(name="startDate", type="Date"),
            Attribute(name="endDate", type="Date"),
        ],
    )

    d = ClassDiagram(title="pict_3_43 — Основная диаграмма ИС ОК")
    d.add_classifier(person)
    d.add_classifier(department)
    d.add_classifier(position)
    d.add_classifier(position_history)

    # Person – Position (many-to-many through history)
    d.add_association(Association(
        name="occupies",
        ends=[
            AssociationEnd(participant="Person",
                           role="employee",
                           multiplicity=MultiplicityRange(lower=0, upper=None),
                           navigable=True),
            AssociationEnd(participant="Position",
                           role="position",
                           multiplicity=MultiplicityRange(lower=0, upper=None),
                           navigable=True),
        ],
    ))

    # Department ◆── Position (composition)
    d.add_association(Association(
        ends=[
            AssociationEnd(participant="Department",
                           aggregation=AggregationKind.COMPOSITION,
                           multiplicity=MultiplicityRange(lower=1, upper=1)),
            AssociationEnd(participant="Position",
                           multiplicity=MultiplicityRange(lower=1, upper=None)),
        ],
    ))

    # Department ◇── Person (aggregation)
    d.add_association(Association(
        name="employs",
        ends=[
            AssociationEnd(participant="Department",
                           aggregation=AggregationKind.AGGREGATION,
                           multiplicity=MultiplicityRange(lower=1, upper=1)),
            AssociationEnd(participant="Person",
                           multiplicity=MultiplicityRange(lower=0, upper=None)),
        ],
    ))

    # Position hierarchy (self-association)
    d.add_association(Association(
        name="supervises",
        ends=[
            AssociationEnd(participant="Position", role="supervisor",
                           multiplicity=MultiplicityRange(lower=0, upper=1)),
            AssociationEnd(participant="Position", role="subordinate",
                           multiplicity=MultiplicityRange(lower=0, upper=None)),
        ],
    ))

    # PositionHistory linked to occupies
    d.add_association(Association(
        ends=[
            AssociationEnd(participant="Person",
                           multiplicity=MultiplicityRange(lower=1, upper=1)),
            AssociationEnd(participant="PositionHistory",
                           multiplicity=MultiplicityRange(lower=0, upper=None)),
        ],
    ))

    d.positions = {
        "Person": ClassPosition(classifier_name="Person", x=40, y=40,
                                 width=250, height=140),
        "Department": ClassPosition(classifier_name="Department", x=500, y=40,
                                     width=220, height=120),
        "Position": ClassPosition(classifier_name="Position", x=500, y=300,
                                   width=240, height=140),
        "PositionHistory": ClassPosition(classifier_name="PositionHistory",
                                          x=40, y=350, width=200, height=90),
    }
    save(d, "pict_3_43.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 18: Метамодель классификатора (pict_3_3)
# §3.1.3 — Часть метамодели
# ═══════════════════════════════════════════════════════════════════════════

def example_pict_3_3():
    """Часть метамодели классификатора (§3.1.3).

    Иерархия: Classifier → Class, Interface, DataType, Association,
    UseCase, Actor, Component, Node, Artifact.
    """
    classifier = Classifier(name="Classifier", is_abstract=True)
    cls = Classifier(name="Class")
    interface = Classifier(name="Interface")
    data_type = Classifier(name="DataType")
    association = Classifier(name="Association")
    use_case = Classifier(name="UseCase")
    actor = Classifier(name="Actor")
    component = Classifier(name="Component")
    node = Classifier(name="Node")
    artifact = Classifier(name="Artifact")

    d = ClassDiagram(title="pict_3_3 — Метамодель классификатора")
    for c in [classifier, cls, interface, data_type, association,
              use_case, actor, component, node, artifact]:
        d.add_classifier(c)

    for sub in ["Class", "Interface", "DataType", "Association",
                "UseCase", "Actor", "Component", "Node", "Artifact"]:
        d.add_generalization(sub, "Classifier")

    d.positions = {
        "Classifier": ClassPosition(classifier_name="Classifier",
                                     x=400, y=30, width=130, height=60),
        "Class": ClassPosition(classifier_name="Class",
                                x=40, y=200, width=100, height=50),
        "Interface": ClassPosition(classifier_name="Interface",
                                    x=160, y=200, width=100, height=50),
        "DataType": ClassPosition(classifier_name="DataType",
                                   x=280, y=200, width=100, height=50),
        "Association": ClassPosition(classifier_name="Association",
                                      x=400, y=200, width=120, height=50),
        "UseCase": ClassPosition(classifier_name="UseCase",
                                  x=540, y=200, width=100, height=50),
        "Actor": ClassPosition(classifier_name="Actor",
                                x=660, y=200, width=90, height=50),
        "Component": ClassPosition(classifier_name="Component",
                                    x=160, y=300, width=120, height=50),
        "Node": ClassPosition(classifier_name="Node",
                               x=400, y=300, width=90, height=50),
        "Artifact": ClassPosition(classifier_name="Artifact",
                                   x=540, y=300, width=100, height=50),
    }
    save(d, "pict_3_3.html")


# ═══════════════════════════════════════════════════════════════════════════
# Пример 19: Зависимость с стереотипом (pict_3_14 — часть)
# ═══════════════════════════════════════════════════════════════════════════

def example_dependency():
    """Зависимости с различными стереотипами (§3.3.1)."""
    a = Classifier(name="Application")
    b = Classifier(name="Logger")
    c = Classifier(name="Config")

    d = ClassDiagram(title="Зависимости")
    d.add_classifier(a)
    d.add_classifier(b)
    d.add_classifier(c)
    d.add_dependency("Application", "Logger", stereotype=DependencyStereotype.USE)
    d.add_dependency("Application", "Config", stereotype=DependencyStereotype.INSTANTIATE)
    d.auto_layout(cols=3)
    save(d, "dependencies.html")


# ═══════════════════════════════════════════════════════════════════════════
# Запуск всех примеров
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("Генерация примеров UML DSL → SVG/HTML …")
    print()
    example_pict_3_4()
    example_pict_3_5()
    example_pict_3_6()
    example_pict_3_7()
    example_pict_3_8()
    example_pict_3_10()
    example_pict_3_12()
    example_pict_3_13()
    example_pict_3_15_16()
    example_pict_3_18()
    example_pict_3_19()
    example_pict_3_20()
    example_pict_3_30()
    example_pict_3_32()
    example_pict_3_39()
    example_pict_3_35()
    example_pict_3_43()
    example_pict_3_3()
    example_dependency()
    print()
    print(f"Все примеры сохранены в {OUT_DIR}")
    print("Откройте любой HTML файл в браузере для интерактивного просмотра.")
    print()
    print("Интерактивные возможности:")
    print("  • Перетаскивание классов мышкой (drag & drop)")
    print("  • Двойной клик на стрелке → добавить точку изгиба (ломаная)")
    print("  • Правый клик у конца стрелки → привязать к стороне класса")
    print("  • Перетаскивание точек изгиба")


if __name__ == "__main__":
    main()
