from __future__ import annotations


class DslSyntaxError(ValueError):
    def __init__(
            self,
            message: str,
            *,
            offset: int,
            line: int,
            column: int,
    ) -> None:
        super().__init__(message)
        self.offset = offset
        self.line = line
        self.column = column

    def __str__(self) -> str:
        return f"{super().__str__()} at line {self.line}, column {self.column}"
