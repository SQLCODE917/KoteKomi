"""Finite model-output contract for proposition-fragment membership."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PropositionFragmentAnswerValue(StrEnum):
    """One answer about one invocation-bound exact source fragment."""

    YES = "Y"
    NO = "N"
    UNCERTAIN = "U"


@dataclass(frozen=True)
class PropositionFragmentAnswer:
    """One validated proposition-fragment membership answer."""

    value: PropositionFragmentAnswerValue


def parse_proposition_fragment_answer(raw_output: bytes) -> PropositionFragmentAnswer:
    """Parse exactly one `Y`, `N`, or `U` answer."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Proposition fragment answer must be UTF-8 text.") from error
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
        raise ValueError("Proposition fragment answer requires exactly one trimmed line.")
    try:
        value = PropositionFragmentAnswerValue(lines[0])
    except ValueError as error:
        raise ValueError("Proposition fragment answer must be Y, N, or U.") from error
    return PropositionFragmentAnswer(value)


def proposition_fragment_answer_schema_bytes() -> bytes:
    """Return the pinned finite output contract."""
    return b"Return exactly one character: Y, N, or U.\n"
