from __future__ import annotations

import pytest

from uml_dsl.enums import AggregationKind, Changeability, DependencyStereotype, Scope, Stereotype, Visibility
from uml_dsl.models import DataType, Interface, Template
from uml_dsl.relationships import TemplateBinding
from uml_dsl.tdl_lexer import LexerError, TokenKind, lex
from uml_dsl.tdl_parser import ParseError, parse_tdl

from tests.helpers import (
    ASSOCIATION,
    ATTRS,
    CLASS,
    COMPOSITION,
    DATA_TYPE,
    DEPENDENCY,
    END,
    GENERALIZATION,
    INTERFACE,
    NAME,
    OPS,
    PARAMETERS,
    REALIZATION,
    TEMPLATE,
    TEMPLATE_BINDING,
    class_block,
    build,
    data_type_block,
    enum_block,
    interface_block,
    template_block,
)


def test_lexer_recognizes_tdl_keywords_and_relation_tokens():
    tokens = lex(
        f"{CLASS} Store\n{END} {CLASS}\n"
        f"{INTERFACE} Readable\n{END} {INTERFACE}\n"
        f"{DATA_TYPE} Money\n{END} {DATA_TYPE}\n"
        f"{TEMPLATE} Box\n{PARAMETERS}\nT\n{END} {TEMPLATE}\n"
        f"{TEMPLATE_BINDING} StringBox -> Box {{ T = String }}\n"
        f"{ASSOCIATION} Store -- Item\n"
    )
    kinds = [token.kind for token in tokens]

    assert TokenKind(CLASS) in kinds
    assert TokenKind(INTERFACE) in kinds
    assert TokenKind(DATA_TYPE) in kinds
    assert TokenKind(TEMPLATE) in kinds
    assert TokenKind(PARAMETERS) in kinds
    assert TokenKind(TEMPLATE_BINDING) in kinds
    assert TokenKind(END) in kinds
    assert TokenKind(ASSOCIATION) in kinds
    assert TokenKind.DASH in kinds
    assert kinds[-1] == TokenKind.EOF


def test_lexer_reports_unknown_symbols_with_position():
    with pytest.raises(LexerError) as error:
        lex("@")

    assert error.value.line == 1
    assert error.value.column == 1


def test_parser_reports_bad_association_operator():
    tdl = class_block("A") + class_block("B") + f"{ASSOCIATION} A - B\n"

    with pytest.raises(ParseError):
        parse_tdl(lex(tdl))


def test_builds_classes_enum_features_and_relationships():
    tdl = (
        class_block(
            "Store",
            f"""
{ATTRS}
  + items [0..*] : Item
  - title : String = "Main"
{OPS}
  + add(item: Item): int
""",
            abstract=True,
        )
        + class_block("Item")
        + enum_block("Color", ["RED", "GREEN"])
        + f"{ASSOCIATION} Store [1] : owner -- Item [0..*] : items {NAME} \"contains\"\n"
        + f"{COMPOSITION} Store -- Item\n"
        + f"{DEPENDENCY} Store -> Color use\n"
    )

    diagram = build(tdl)
    diagram.validate_all()

    assert set(diagram.classifiers) == {"Store", "Item", "Color"}
    assert diagram.classifiers["Store"].is_abstract is True
    assert diagram.classifiers["Color"].stereotype == Stereotype.ENUMERATION

    store = diagram.classifiers["Store"]
    assert len(store.attributes) == 2
    assert store.attributes[0].visibility == Visibility.PUBLIC
    assert store.attributes[0].type_ == "Item"
    assert str(store.attributes[0].multiplicity) == "0..*"
    assert store.attributes[1].visibility == Visibility.PRIVATE
    assert store.attributes[1].initial_value == "Main"

    assert len(store.operations) == 1
    assert store.operations[0].name == "add"
    assert store.operations[0].parameters[0].type_ == "Item"
    assert store.operations[0].return_type == "int"

    named_assoc = diagram.associations[0]
    assert named_assoc.name == "contains"
    assert named_assoc.ends[0].role == "owner"
    assert str(named_assoc.ends[0].multiplicity) == "1"
    assert named_assoc.ends[1].role == "items"
    assert str(named_assoc.ends[1].multiplicity) == "0..*"

    composition = diagram.associations[1]
    assert composition.ends[0].aggregation == AggregationKind.COMPOSITION
    assert diagram.dependencies[0].stereotype == DependencyStereotype.USE


def test_builds_interface_and_realization():
    tdl = (
        class_block("Repository")
        + interface_block(
            "Readable",
            f"""
{OPS}
  + get(id: int): String
""",
        )
        + f"{REALIZATION} Repository -> Readable\n"
    )

    diagram = build(tdl)
    diagram.validate_all()

    readable = diagram.classifiers["Readable"]
    assert isinstance(readable, Interface)
    assert readable.stereotype == Stereotype.INTERFACE
    assert readable.is_abstract is True
    assert readable.operations[0].is_abstract is True
    assert diagram.realizations[0].interface_.name == "Readable"


def test_realization_requires_interface_target():
    tdl = class_block("Repository") + class_block("Readable") + f"{REALIZATION} Repository -> Readable\n"

    with pytest.raises(ValueError, match="интерфейс"):
        build(tdl)


def test_builds_data_type_and_allows_references_to_it():
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

    diagram = build(tdl)
    diagram.validate_all()

    money = diagram.classifiers["Money"]
    assert isinstance(money, DataType)
    assert money.stereotype == Stereotype.DATA_TYPE
    assert money.operations[0].is_query is True
    assert money.operations[0].scope == Scope.CLASSIFIER
    assert diagram.classifiers["Invoice"].attributes[0].type_ == "Money"


def test_builds_template_and_allows_parameter_type_references():
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
  + replace(value : T) : T
""",
        )
        + class_block("User", f"{ATTRS}\n  + name : String")
        + class_block("UserBox", f"{ATTRS}\n  + value : User")
        + f"{TEMPLATE_BINDING} UserBox -> Box {{ T = User }}\n"
    )

    diagram = build(tdl)
    diagram.validate_all()

    box = diagram.classifiers["Box"]
    assert isinstance(box, Template)
    assert box.template_parameters[0].name == "T"
    assert box.attributes[0].type_ == "T"
    assert box.operations[0].return_type == "T"
    assert box.operations[1].parameters[0].type_ == "T"
    assert len(diagram.template_bindings) == 1
    binding = diagram.template_bindings[0]
    assert isinstance(binding, TemplateBinding)
    assert binding.bound_element.name == "UserBox"
    assert binding.template.name == "Box"
    assert binding.substitutions == {"T": "User"}


def test_validation_rejects_inheritance_cycles():
    tdl = (
        class_block("A")
        + class_block("B")
        + f"{GENERALIZATION} A -> B\n"
        + f"{GENERALIZATION} B -> A\n"
    )

    with pytest.raises(ValueError):
        build(tdl).validate_all()


def test_validation_rejects_unknown_attribute_type():
    tdl = class_block("A", f"{ATTRS}\n  + ref : Missing")

    with pytest.raises(ValueError, match="Missing"):
        build(tdl).validate_all()


def test_validation_rejects_multiple_inheritance_type_conflict():
    tdl = (
        class_block("Left", f"{ATTRS}\n  + code : String")
        + class_block("Right", f"{ATTRS}\n  + code : int")
        + class_block("Child")
        + f"{GENERALIZATION} Child -> Left\n"
        + f"{GENERALIZATION} Child -> Right\n"
    )

    with pytest.raises(ValueError, match="code"):
        build(tdl).validate_all()


def test_validation_rejects_part_in_two_compositions():
    tdl = (
        class_block("WholeA")
        + class_block("WholeB")
        + class_block("Part")
        + f"{COMPOSITION} WholeA -- Part\n"
        + f"{COMPOSITION} WholeB -- Part\n"
    )

    with pytest.raises(ValueError, match="Part"):
        build(tdl).validate_all()


def test_readonly_attribute_modifier_is_mapped_to_changeability():
    readonly = "\u0442\u043e\u043b\u044c\u043a\u043e_\u0447\u0442\u0435\u043d\u0438\u0435"
    tdl = class_block("A", f"{ATTRS}\n  + id : int {{ {readonly} }}")

    diagram = build(tdl)

    assert diagram.classifiers["A"].attributes[0].changeability == Changeability.READ_ONLY
