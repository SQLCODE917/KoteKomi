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
    """Parse one finite answer while retaining raw framing in execution evidence."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Proposition fragment answer must be UTF-8 text.") from error
    answer = text.strip(" \t\r\n")
    try:
        value = PropositionFragmentAnswerValue(answer)
    except ValueError as error:
        raise ValueError(
            "Proposition fragment answer payload must be exactly Y, N, or U."
        ) from error
    return PropositionFragmentAnswer(value)


def proposition_fragment_answer_schema_bytes() -> bytes:
    """Return the pinned finite output contract."""
    return (
        b"Return exactly one answer character: Y, N, or U. "
        b"Surrounding ASCII whitespace is framing only.\n"
    )
