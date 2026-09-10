"""Deterministic local choices over authoritative source characters."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SOURCE_OCCURRENCE = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class SourceOccurrence:
    """One KoteKomi-owned token-like span over exact source characters."""

    occurrence_id: str
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if re.fullmatch(r"o[1-9][0-9]*", self.occurrence_id) is None:
            raise ValueError("SourceOccurrence requires one ordered local ID.")
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("SourceOccurrence range does not match its text.")


def source_occurrences(source_text: str) -> tuple[SourceOccurrence, ...]:
    """Build an ordered model-choice catalog over exact source characters."""
    return tuple(
        SourceOccurrence(
            occurrence_id=f"o{ordinal}",
            text=match.group(),
            start=match.start(),
            end=match.end(),
        )
        for ordinal, match in enumerate(_SOURCE_OCCURRENCE.finditer(source_text), start=1)
    )
