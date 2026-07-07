from __future__ import annotations


def validate_step_limit(value: int | None) -> int | None:
    if value is not None and value <= 0:
        raise ValueError(f"step_limit must be > 0, got {value}")
    return value
