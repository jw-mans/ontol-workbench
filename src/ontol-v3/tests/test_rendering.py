from __future__ import annotations

import subprocess
import sys

from uml_dsl import (
    Association,
    AssociationClass,
    AssociationEnd,
    Attribute,
    Class,
    ClassDiagram,
    DataType,
    Interface,
    Multiplicity,
    MultiplicityRange,
    Operation,
    Parameter,
    TaggedValue,
    Template,
    TemplateBinding,
    TemplateParameter,
)
from uml_dsl.graphviz_render import available_svg_themes
from uml_dsl.svg_parser import parse_svg_to_diagram
from uml_dsl.tdl_run import tdl_to_svg
from uml_dsl.enums import Changeability, CollectionKind, ParamDirection, Scope, Visibility

from tests.helpers import (
    AGGREGATION,
    ASSOCIATION,
    ATTRS,
    DEPENDENCY,
    GENERALIZATION,
    NAME,
    OPS,
    PARAMETERS,
    REALIZATION,
    TEMPLATE,
    TEMPLATE_BINDING,
    association_class_block,
    class_block,
    data_type_block,
    enum_block,
    interface_block,
    template_block,
)


def relation_rich_tdl() -> str:
    return (
        class_block("A")
        + class_block("B")
        + class_block("C")
        + interface_block("I")
        + f"{ASSOCIATION} A [1] : owner -- B [0..*] : items {NAME} \"owns\"\n"
        + f"{AGGREGATION} A -- C\n"
        + f"{DEPENDENCY} B -> C use\n"
        + f"{GENERALIZATION} B -> A\n"
        + f"{REALIZATION} C -> I\n"
    )


def test_available_themes_are_light_and_yellow_only():
    assert available_svg_themes() == ["light", "yellow"]


def test_render_embeds_theme_edges_markers_and_multiplicities(require_dot):
    svg = tdl_to_svg(relation_rich_tdl(), theme="yellow")

    assert svg.lstrip().startswith("<svg")
    assert 'class="uml-diagram"' in svg
    assert 'data-theme="yellow"' in svg
    assert 'id="uml-theme-yellow"' in svg
    assert 'data-type="association"' in svg
    assert 'data-name="owns"' in svg
    assert 'data-end1-multiplicity="1"' in svg
    assert 'data-end2-multiplicity="0..*"' in svg
    assert 'data-class-kind="interface"' in svg
    assert 'uml-kind-badge-i' in svg
    assert 'marker-end="url(#triangle-empty)"' in svg
    assert 'marker-end="url(#arrow-filled)"' in svg
    assert 'marker-start="url(#diamond-empty)"' in svg
    assert '<path class="uml-edge-line"' in svg
    assert '>1</text>' in svg
    assert '>0..*</text>' in svg


def test_unknown_theme_falls_back_to_light(require_dot):
    svg = tdl_to_svg(class_block("A"), theme="../dark")

    assert 'data-theme="light"' in svg
    assert 'id="uml-theme-light"' in svg


def test_rendered_svg_can_be_parsed_back_to_diagram(require_dot):
    svg = tdl_to_svg(relation_rich_tdl())
    result = parse_svg_to_diagram(svg)

    assert result.success, result.errors
    assert result.diagram is not None
    assert {"A", "B", "C", "I"} <= set(result.diagram.classifiers)
    assert isinstance(result.diagram.classifiers["I"], Interface)
    assert len(result.diagram.associations) == 2
    assert len(result.diagram.dependencies) == 1
    assert len(result.diagram.generalizations) == 1
    assert len(result.diagram.realizations) == 1
    assert set(result.diagram.positions) == {"A", "B", "C", "I"}
    result.diagram.validate_all()


def test_rendered_svg_roundtrip_preserves_class_features_and_validation(require_dot):
    readonly = "\u0442\u043e\u043b\u044c\u043a\u043e_\u0447\u0442\u0435\u043d\u0438\u0435"
    query = "\u0437\u0430\u043f\u0440\u043e\u0441"
    leaf = "\u043b\u0438\u0441\u0442"
    tdl = (
        class_block(
            "Store",
            f"""
{ATTRS}
  + items [0..*] : Item
  - title : String = "Main"
  # code : int = 7 {{ {readonly} }}
{OPS}
  + add(item: Item, count: int = 1): int {{ {query}, {leaf} }}
""",
            abstract=True,
        )
        + class_block("Item")
        + enum_block("Color", ["RED", "GREEN"])
        + f"{ASSOCIATION} Store [1] : owner -- Item [0..*] : items {NAME} \"contains\"\n"
        + f"{DEPENDENCY} Store -> Color use\n"
    )

    result = parse_svg_to_diagram(tdl_to_svg(tdl))

    assert result.success, result.errors
    assert result.diagram is not None
    assert result.diagram.title == "\u0414\u0438\u0430\u0433\u0440\u0430\u043c\u043c\u0430 TDL"
    assert result.diagram.manual_layout is True

    store = result.diagram.classifiers["Store"]
    assert store.is_abstract is True
    assert len(store.attributes) == 3
    assert store.attributes[0].name == "items"
    assert store.attributes[0].visibility == Visibility.PUBLIC
    assert store.attributes[0].type_ == "Item"
    assert str(store.attributes[0].multiplicity) == "0..*"
    assert store.attributes[1].initial_value == "Main"
    assert store.attributes[2].initial_value == 7
    assert store.attributes[2].changeability == Changeability.READ_ONLY

    assert len(store.operations) == 1
    operation = store.operations[0]
    assert operation.name == "add"
    assert operation.return_type == "int"
    assert operation.is_query is True
    assert operation.is_leaf is True
    assert [param.name for param in operation.parameters] == ["item", "count"]
    assert operation.parameters[0].type_ == "Item"
    assert operation.parameters[1].type_ == "int"
    assert operation.parameters[1].default == 1

    color = result.diagram.classifiers["Color"]
    assert [attribute.name for attribute in color.attributes] == ["RED", "GREEN"]

    association = result.diagram.associations[0]
    assert association.name == "contains"
    assert association.ends[0].role == "owner"
    assert association.ends[1].role == "items"
    assert str(association.ends[1].multiplicity) == "0..*"

    result.diagram.validate_all()


def test_rendered_svg_roundtrip_preserves_data_type(require_dot):
    tdl = (
        data_type_block(
            "Money",
            f"""
{ATTRS}
  + amount : Float
  + currency : String
{OPS}
  + add(other : Money) : Money
""",
        )
        + class_block("Invoice", f"{ATTRS}\n  + total : Money")
    )

    svg = tdl_to_svg(tdl)
    result = parse_svg_to_diagram(svg)

    assert 'data-class-kind="dataType"' in svg
    assert 'data-stereotype="dataType"' in svg
    assert 'uml-kind-badge-d' in svg
    assert result.success, result.errors
    assert result.diagram is not None

    money = result.diagram.classifiers["Money"]
    assert isinstance(money, DataType)
    assert money.operations[0].is_query is True
    assert result.diagram.classifiers["Invoice"].attributes[0].type_ == "Money"
    result.diagram.validate_all()


def test_rendered_svg_roundtrip_preserves_template(require_dot):
    tdl = (
        template_block(
            "Box",
            f"""
{PARAMETERS}
  T
{ATTRS}
  + value : T
{OPS}
  + get() : T
""",
        )
        + class_block("User", f"{ATTRS}\n  + name : String")
        + class_block("UserBox", f"{ATTRS}\n  + value : User")
        + f"{TEMPLATE_BINDING} UserBox -> Box {{ T = User }}\n"
    )

    svg = tdl_to_svg(tdl)
    result = parse_svg_to_diagram(svg)

    assert 'data-class-kind="template"' in svg
    assert 'data-type="template-parameter"' in svg
    assert 'data-type="template-binding"' in svg
    assert 'data-formal="T"' in svg
    assert 'data-actual="User"' in svg
    assert 'data-template-parameters-count="1"' in svg
    assert result.success, result.errors
    assert result.diagram is not None

    box = result.diagram.classifiers["Box"]
    assert isinstance(box, Template)
    assert box.template_parameters[0].name == "T"
    assert box.attributes[0].type_ == "T"
    assert box.operations[0].return_type == "T"
    assert len(result.diagram.template_bindings) == 1
    binding = result.diagram.template_bindings[0]
    assert isinstance(binding, TemplateBinding)
    assert binding.bound_element.name == "UserBox"
    assert binding.template.name == "Box"
    assert binding.substitutions == {"T": "User"}
    result.diagram.validate_all()


def test_rendered_svg_roundtrip_preserves_association_class(require_dot):
    tdl = (
        class_block("Student")
        + class_block("Course")
        + association_class_block(
            "Enrollment",
            f"""
{ASSOCIATION} Student [0..*] : student -- Course [0..*] : course {NAME} "enrolls"
{ATTRS}
  + enrolledAt : String
  + grade : String
{OPS}
  + confirm() : Boolean
""",
        )
    )

    svg = tdl_to_svg(tdl)
    result = parse_svg_to_diagram(svg)

    assert 'data-type="association-class"' in svg
    assert 'data-associated-classifier="Enrollment"' in svg
    assert 'uml-association-class-segment' not in svg
    assert 'uml-association-class-link' in svg
    assert 'uml-association-class-anchor' in svg
    assert '<line class="uml-edge-line uml-association-class-link"' not in svg
    assert '__ontol_v3_association_class_anchor' not in svg
    assert result.success, result.errors
    assert result.diagram is not None
    assert len(result.diagram.associations) == 0
    assert len(result.diagram.association_classes) == 1

    assoc_class = result.diagram.association_classes[0]
    assert isinstance(assoc_class, AssociationClass)
    assert assoc_class.name == "enrolls"
    assert assoc_class.associated_classifier.name == "Enrollment"
    assert assoc_class.associated_classifier.attributes[1].name == "grade"
    assert assoc_class.ends[0].participant.name == "Student"
    assert assoc_class.ends[1].role == "course"
    result.diagram.validate_all()


def test_svg_parser_rejects_svg_without_v3_data_attributes():
    result = parse_svg_to_diagram('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert result.success is False
    assert result.errors


def test_svg_parser_returns_model_errors_without_raising():
    svg = """<svg xmlns="http://www.w3.org/2000/svg">
<g data-type="class" data-id="A" data-name="A" transform="translate(0,0)">
  <rect class="uml-bbox" width="120" height="60"/>
</g>
<g data-type="dependency" data-src="A" data-tgt="A" data-stereotype="bad"/>
</svg>"""

    result = parse_svg_to_diagram(svg)

    assert result.success is False
    assert result.errors


def test_svg_roundtrip_preserves_hidden_model_metadata(require_dot):
    item = Class(name="Item")
    box = Template(
        name="Box",
        visibility=Visibility.PUBLIC,
        multiplicity=Multiplicity(ranges=[MultiplicityRange(lower=1, upper=1)]),
        attributes=[
            Attribute(
                name="value",
                visibility=Visibility.PRIVATE,
                scope=Scope.CLASSIFIER,
                type_="Item",
                multiplicity=MultiplicityRange(lower=0, upper=None),
                changeability=Changeability.READ_ONLY,
                redefines="oldValue",
            )
        ],
        operations=[
            Operation(
                name="get",
                visibility=Visibility.PUBLIC,
                scope=Scope.CLASSIFIER,
                parameters=[
                    Parameter(
                        name="fallback",
                        type_="Item",
                        direction=ParamDirection.IN,
                    )
                ],
                return_type="Item",
            )
        ],
        tagged_values=[TaggedValue(name="version", value=2)],
        template_parameters=[TemplateParameter(name="T", type_="Item", default_value="Item")],
    )
    end1 = AssociationEnd(
        participant=box,
        role="boxes",
        role_visibility=Visibility.PUBLIC,
        collection_kind=CollectionKind.ORDERED,
        changeability=Changeability.READ_ONLY,
        qualifiers=[Attribute(name="key", type_="String")],
        is_union=True,
        redefines="oldBoxes",
        role_type=item,
    )
    end2 = AssociationEnd(participant=item, role="item")
    end1.subsets = end2

    diagram = ClassDiagram(title="Metadata")
    diagram.add_classifier(box)
    diagram.add_classifier(item)
    diagram.add_association(Association(name="typed", ends=[end1, end2]))

    result = parse_svg_to_diagram(diagram.to_svg())

    assert result.success, result.errors
    assert result.diagram is not None
    parsed_box = result.diagram.classifiers["Box"]
    assert isinstance(parsed_box, Template)
    assert parsed_box.visibility == Visibility.PUBLIC
    assert str(parsed_box.multiplicity) == "1"
    assert parsed_box.tagged_values[0].name == "version"
    assert parsed_box.tagged_values[0].value == 2
    assert parsed_box.template_parameters[0].name == "T"
    assert parsed_box.attributes[0].scope == Scope.CLASSIFIER
    assert parsed_box.attributes[0].redefines == "oldValue"
    assert parsed_box.operations[0].parameters[0].type_ == "Item"

    parsed_end = result.diagram.associations[0].ends[0]
    assert parsed_end.role_visibility == Visibility.PUBLIC
    assert parsed_end.collection_kind == CollectionKind.ORDERED
    assert parsed_end.changeability == Changeability.READ_ONLY
    assert parsed_end.qualifiers[0].name == "key"
    assert parsed_end.is_union is True
    assert parsed_end.redefines == "oldBoxes"
    assert parsed_end.role_type.name == "Item"
    assert parsed_end.subsets.role == "item"


def test_cli_writes_svg_file(tmp_path, require_dot):
    source = tmp_path / "diagram.tdl"
    target = tmp_path / "diagram.svg"
    source.write_text(class_block("A") + class_block("B") + f"{ASSOCIATION} A -- B\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "uml_dsl.tdl_run", str(source), str(target)],
        cwd=source.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert target.exists()
    assert target.read_text(encoding="utf-8").lstrip().startswith("<svg")
