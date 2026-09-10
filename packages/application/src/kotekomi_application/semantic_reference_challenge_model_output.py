"""Literal model-output contract for one bounded semantic-reference challenge."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ANTECEDENT_LABEL_PATTERN = re.compile(r"a[1-9][0-9]*")


@dataclass(frozen=True)
class SemanticReferenceChallengeSelection:
    antecedent_candidate_label: str | None
    ambiguous: bool
    reason: str

    def __post_init__(self) -> None:
        if self.antecedent_candidate_label is not None and self.ambiguous:
            raise ValueError("A reference challenge cannot select and remain ambiguous.")
        if (
            self.antecedent_candidate_label is not None
            and _ANTECEDENT_LABEL_PATTERN.fullmatch(self.antecedent_candidate_label) is None
        ):
            raise ValueError("A reference challenge requires a task-local antecedent label.")
        if not self.reason or self.reason != self.reason.strip():
            raise ValueError("A reference challenge requires one trimmed reason.")


def parse_semantic_reference_challenge_output(
    raw_output: bytes,
) -> SemanticReferenceChallengeSelection:
    try:
        lines = raw_output.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Semantic-reference challenge output must be UTF-8 text.") from error
    if (
        len(lines) != 2
        or any(not line or line != line.strip() for line in lines)
        or not lines[0].startswith("antecedent: ")
        or not lines[1].startswith("reason: ")
    ):
        raise ValueError("Semantic-reference challenge requires two fixed-order lines.")
    value = lines[0].removeprefix("antecedent: ")
    reason = lines[1].removeprefix("reason: ")
    if not value or not reason:
        raise ValueError("Semantic-reference challenge fields must not be empty.")
    if value == "ambiguous":
        return SemanticReferenceChallengeSelection(None, True, reason)
    if value == "unresolved":
        return SemanticReferenceChallengeSelection(None, False, reason)
    if _ANTECEDENT_LABEL_PATTERN.fullmatch(value) is None:
        raise ValueError("Semantic-reference challenge requires a task-local antecedent label.")
    return SemanticReferenceChallengeSelection(value, False, reason)


def semantic_reference_challenge_schema_bytes() -> bytes:
    return (
        b"Choose one value listed under legal_outcomes.\n"
        b"Return exactly two lines.\n"
        b"The first line starts with antecedent: followed by the chosen value.\n"
        b"The second line starts with reason: followed by one concise explanation.\n"
    )
