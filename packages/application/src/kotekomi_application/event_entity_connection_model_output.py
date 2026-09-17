"""Finite model-output contract for one contrastive Event candidate inventory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EntityInvolvementAnswerValue(StrEnum):
    """One model answer whose target is fixed by its candidate-vector position."""

    YES = "Y"
    NO = "N"
    UNCERTAIN = "U"


@dataclass(frozen=True)
class EntityInvolvementAnswerBatch:
    """One ordered finite answer for every model-routed candidate of one Event."""

    values: tuple[EntityInvolvementAnswerValue, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("Entity involvement answer batch must not be empty.")


def parse_entity_involvement_answer_batch(raw_output: bytes) -> EntityInvolvementAnswerBatch:
    """Parse one unspaced `Y`, `N`, or `U` answer per ordered candidate."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Entity involvement answer batch must be UTF-8 text.") from error
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
        raise ValueError("Entity involvement answer batch requires exactly one trimmed line.")
    try:
        values = tuple(EntityInvolvementAnswerValue(value) for value in lines[0])
    except ValueError as error:
        raise ValueError("Every entity involvement answer must be Y, N, or U.") from error
    return EntityInvolvementAnswerBatch(values)


def entity_involvement_answer_batch_schema_bytes() -> bytes:
    """Return the pinned ordered-vector output contract."""
    return (
        b"Return exactly one non-empty line containing only Y, N, or U, with one character "
        b"per candidate in the supplied order and no separators.\n"
    )
