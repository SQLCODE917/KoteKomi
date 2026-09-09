"""Literal model-output contract for one bounded semantic-reference challenge."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticReferenceChallengeSelection:
    antecedent_candidate_id: str | None
    ambiguous: bool
    reason: str

    def __post_init__(self) -> None:
        if self.antecedent_candidate_id is not None and self.ambiguous:
            raise ValueError("A reference challenge cannot select and remain ambiguous.")
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
    if any(character.isspace() for character in value):
        raise ValueError("Semantic-reference challenge candidate ID cannot contain whitespace.")
    return SemanticReferenceChallengeSelection(value, False, reason)


def semantic_reference_challenge_schema_bytes() -> bytes:
    return (
        b"antecedent: <supplied_candidate_id>|ambiguous|unresolved\n"
        b"reason: <one non-empty sentence>\n"
    )
