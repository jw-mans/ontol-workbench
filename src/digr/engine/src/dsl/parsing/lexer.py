from __future__ import annotations

from .errors import DslSyntaxError
from .token import DslToken
from .token_kind import TokenKind

_KEYWORDS = {
    "CONTEXT": TokenKind.CONTEXT,
    "FIND": TokenKind.FIND,
    "DISTANCE": TokenKind.DISTANCE,
    "FOR": TokenKind.FOR,
    "TO": TokenKind.TO,
    "WITHIN": TokenKind.WITHIN,
    "LIMIT_PAIRS": TokenKind.LIMIT_PAIRS,
    "WHERE": TokenKind.WHERE,
    "RETURN": TokenKind.RETURN,
    "AND": TokenKind.AND,
    "OR": TokenKind.OR,
    "NOT": TokenKind.NOT,
    "TRUE": TokenKind.TRUE,
    "FALSE": TokenKind.FALSE,
    "NULL": TokenKind.NULL,
}

_OPERATORS = {
    "!~=": TokenKind.NOT_MATCH,
    "<=": TokenKind.LTE,
    ">=": TokenKind.GTE,
    "!=": TokenKind.NE,
    "~=": TokenKind.MATCH,
    "=": TokenKind.EQ,
    "<": TokenKind.LT,
    ">": TokenKind.GT,
}

_PUNCTUATION = {
    "[": TokenKind.LBRACKET,
    "]": TokenKind.RBRACKET,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    ",": TokenKind.COMMA,
    ":": TokenKind.COLON,
    ".": TokenKind.DOT,
    ";": TokenKind.SEMICOLON,
}


class DslLexer:
    def tokenize(self, source: str) -> list[DslToken]:
        self._source = source
        self._length = len(source)
        self._index = 0
        self._line = 1
        self._column = 1

        tokens: list[DslToken] = []
        while self._index < self._length:
            char = self._peek()
            if char.isspace():
                self._advance()
                continue
            if char.isalpha() or char == "_":
                tokens.append(self._read_identifier())
                continue
            if char.isdigit():
                tokens.append(self._read_integer())
                continue
            if char == '"':
                tokens.append(self._read_string())
                continue
            if char == "/":
                tokens.append(self._read_regex())
                continue

            operator = self._match_operator()
            if operator is not None:
                tokens.append(operator)
                continue

            token_kind = _PUNCTUATION.get(char)
            if token_kind is not None:
                tokens.append(self._single_char_token(token_kind))
                continue

            raise self._error(f"Unexpected character {char!r}")

        tokens.append(DslToken(TokenKind.EOF, "", None, self._index, self._line, self._column))
        return tokens

    def _peek(self, offset: int = 0) -> str:
        position = self._index + offset
        if position >= self._length:
            return "\0"
        return self._source[position]

    def _advance(self) -> str:
        char = self._source[self._index]
        self._index += 1
        if char == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1
        return char

    def _single_char_token(self, token_kind: TokenKind) -> DslToken:
        start_index = self._index
        start_line = self._line
        start_column = self._column
        lexeme = self._advance()
        return DslToken(token_kind, lexeme, lexeme, start_index, start_line, start_column)

    def _read_identifier(self) -> DslToken:
        start_index = self._index
        start_line = self._line
        start_column = self._column
        chars: list[str] = []
        while True:
            char = self._peek()
            if not (char.isalnum() or char == "_"):
                break
            chars.append(self._advance())

        lexeme = "".join(chars)
        token_kind = _KEYWORDS.get(lexeme.upper(), TokenKind.IDENTIFIER)
        return DslToken(token_kind, lexeme, lexeme, start_index, start_line, start_column)

    def _read_integer(self) -> DslToken:
        start_index = self._index
        start_line = self._line
        start_column = self._column
        chars: list[str] = []
        while self._peek().isdigit():
            chars.append(self._advance())
        lexeme = "".join(chars)
        return DslToken(TokenKind.INTEGER, lexeme, int(lexeme), start_index, start_line, start_column)

    def _read_string(self) -> DslToken:
        start_index = self._index
        start_line = self._line
        start_column = self._column
        self._advance()
        chars: list[str] = []
        while True:
            char = self._peek()
            if char == "\0":
                raise self._error("Unterminated string literal", start_index, start_line, start_column)
            if char == '"':
                self._advance()
                break
            if char == "\\":
                chars.append(self._read_string_escape())
                continue
            chars.append(self._advance())

        lexeme = self._source[start_index:self._index]
        return DslToken(TokenKind.STRING, lexeme, "".join(chars), start_index, start_line, start_column)

    def _read_string_escape(self) -> str:
        start_line = self._line
        start_column = self._column
        self._advance()
        escape_char = self._peek()
        if escape_char == "\0":
            raise self._error("Unterminated escape sequence", self._index, start_line, start_column)
        self._advance()
        escape_map = {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }
        if escape_char not in escape_map:
            raise self._error(f"Unsupported escape sequence \\{escape_char}", self._index - 1, start_line, start_column)
        return escape_map[escape_char]

    def _read_regex(self) -> DslToken:
        start_index = self._index
        start_line = self._line
        start_column = self._column
        self._advance()
        chars: list[str] = []
        while True:
            char = self._peek()
            if char == "\0":
                raise self._error("Unterminated regex literal", start_index, start_line, start_column)
            if char == "/":
                self._advance()
                break
            if char == "\\":
                backslash = self._advance()
                next_char = self._peek()
                if next_char == "\0":
                    raise self._error("Unterminated regex literal", start_index, start_line, start_column)
                chars.append(backslash + self._advance())
                continue
            chars.append(self._advance())

        flags: list[str] = []
        while self._peek().isalpha():
            flag = self._peek()
            if flag not in {"i", "m", "s", "u"}:
                raise self._error(f"Unsupported regex flag {flag!r}")
            flags.append(self._advance())

        lexeme = self._source[start_index:self._index]
        return DslToken(
            TokenKind.REGEX,
            lexeme,
            {"pattern": "".join(chars), "flags": "".join(flags)},
            start_index,
            start_line,
            start_column,
        )

    def _match_operator(self) -> DslToken | None:
        start_index = self._index
        start_line = self._line
        start_column = self._column
        for text, token_kind in sorted(_OPERATORS.items(), key=lambda item: len(item[0]), reverse=True):
            if self._source.startswith(text, self._index):
                for _ in text:
                    self._advance()
                return DslToken(token_kind, text, text, start_index, start_line, start_column)
        return None

    def _error(
            self,
            message: str,
            offset: int | None = None,
            line: int | None = None,
            column: int | None = None,
    ) -> DslSyntaxError:
        return DslSyntaxError(
            message,
            offset=self._index if offset is None else offset,
            line=self._line if line is None else line,
            column=self._column if column is None else column,
        )
