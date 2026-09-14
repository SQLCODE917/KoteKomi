"""Finite model-output contract for one Event-entity involvement judgment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EntityInvolvementAnswerValue(StrEnum):
    """One model answer whose target pair is fixed by the invocation."""

    YES = "Y"
    NO = "N"
    UNCERTAIN = "U"


@dataclass(frozen=True)
class EntityInvolvementAnswer:
    """One validated finite answer for an Event-entity pair."""

    value: EntityInvolvementAnswerValue


def parse_entity_involvement_answer(raw_output: bytes) -> EntityInvolvementAnswer:
    """Parse exactly one `Y`, `N`, or `U` answer."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Entity involvement answer must be UTF-8 text.") from error
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
        raise ValueError("Entity involvement answer requires exactly one trimmed line.")
    try:
        value = EntityInvolvementAnswerValue(lines[0])
    except ValueError as error:
        raise ValueError("Entity involvement answer must be Y, N, or U.") from error
    return EntityInvolvementAnswer(value)


def entity_involvement_answer_schema_bytes() -> bytes:
    """Return the pinned literal output contract."""
    return b"Return exactly one character: Y, N, or U.\n"
