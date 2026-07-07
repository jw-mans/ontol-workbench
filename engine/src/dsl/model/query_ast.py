from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, TypeAlias


def _snake_case(name: str) -> str:
    parts: list[str] = []
    for char in name:
        if char.isupper() and parts:
            parts.append("_")
        parts.append(char.lower())
    return "".join(parts)


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        result = {"type": _snake_case(type(value).__name__)}
        for field in fields(value):
            result[field.name] = _serialize(getattr(value, field.name))
        return result
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class RegexLiteral(Serializable):
    pattern: str
    flags: str = ""


DslValue: TypeAlias = str | int | bool | None | RegexLiteral


@dataclass(slots=True)
class FieldRef(Serializable):
    parts: list[str]

    @property
    def path(self) -> str:
        return ".".join(self.parts)


@dataclass(slots=True)
class CountConstraint(Serializable):
    operator: str
    value: int


@dataclass(slots=True)
class SpanSpec(Serializable):
    entity_name: str
    constraint: CountConstraint


@dataclass(slots=True)
class WithinConstraint(Serializable):
    entity_name: str
    constraint: CountConstraint


@dataclass(slots=True)
class Selector(Serializable):
    entity_name: str
    predicate: Expression | None = None


PatternSource: TypeAlias = str | RegexLiteral | Selector
Argument: TypeAlias = Selector | FieldRef | SpanSpec | DslValue


@dataclass(slots=True)
class Pattern(Serializable):
    source: PatternSource
    alias: str | None = None


@dataclass(slots=True)
class DistanceReturn(Serializable):
    entity_name: str


ReturnItem: TypeAlias = str | DistanceReturn


@dataclass(slots=True)
class PairLimit(Serializable):
    mode: str
    value: int | None = None


@dataclass(slots=True)
class ComparisonExpression(Serializable):
    left: FieldRef
    operator: str
    right: DslValue


@dataclass(slots=True)
class FunctionExpression(Serializable):
    name: str
    arguments: list[Argument]


@dataclass(slots=True)
class NotExpression(Serializable):
    operand: Expression


@dataclass(slots=True)
class BinaryExpression(Serializable):
    operator: str
    left: Expression
    right: Expression


Expression: TypeAlias = ComparisonExpression | FunctionExpression | NotExpression | BinaryExpression


@dataclass(slots=True)
class Query(Serializable):
    # target/window/patterns/limit заполнены только для своего kind, см. rbnf.
    # source.predicate у CONTEXT всегда None - скобки там это window, не условие.
    kind: str
    source: Selector
    target: Selector | None = None
    window: CountConstraint | None = None
    patterns: list[Pattern] | None = None
    within: list[WithinConstraint] = field(default_factory=list)
    where: Expression | None = None
    limit: PairLimit | None = None
    returns: list[ReturnItem] | None = None


DslQuery: TypeAlias = Query
