from __future__ import annotations

from enum import Enum, auto


class TokenKind(Enum):
    EOF = auto()
    IDENTIFIER = auto()
    STRING = auto()
    REGEX = auto()
    INTEGER = auto()

    CONTEXT = auto()
    FIND = auto()
    DISTANCE = auto()
    FOR = auto()
    TO = auto()
    WITHIN = auto()
    LIMIT_PAIRS = auto()
    WHERE = auto()
    RETURN = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()

    LBRACKET = auto()
    RBRACKET = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    SEMICOLON = auto()

    EQ = auto()
    NE = auto()
    MATCH = auto()
    NOT_MATCH = auto()
    LT = auto()
    LTE = auto()
    GT = auto()
    GTE = auto()
