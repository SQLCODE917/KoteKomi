"""Literal output contract for one bounded antecedent-candidate validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SemanticReferenceCandidateVerdict(StrEnum):
    """A model's bounded judgment about one supplied antecedent candidate."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class SemanticReferenceCandidateValidation:
    verdict: SemanticReferenceCandidateVerdict
    reason: str

    def __post_init__(self) -> None:
        if not self.reason or self.reason != self.reason.strip():
            raise ValueError("A reference-candidate validation requires one trimmed reason.")


def parse_semantic_reference_candidate_validation_output(
    raw_output: bytes,
) -> SemanticReferenceCandidateValidation:
    try:
        lines = raw_output.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Reference-candidate validation output must be UTF-8 text.") from error
    if (
        len(lines) != 2
        or any(not line or line != line.strip() for line in lines)
        or not lines[0].startswith("verdict: ")
        or not lines[1].startswith("reason: ")
    ):
        raise ValueError("Reference-candidate validation requires two fixed-order lines.")
    verdict_value = lines[0].removeprefix("verdict: ")
    reason = lines[1].removeprefix("reason: ")
    if not reason:
        raise ValueError("Reference-candidate validation reason must not be empty.")
    try:
        verdict = SemanticReferenceCandidateVerdict(verdict_value)
    except ValueError as error:
        raise ValueError(
            "Reference-candidate validation verdict must be supported, unsupported, or unclear."
        ) from error
    return SemanticReferenceCandidateValidation(verdict, reason)


def semantic_reference_candidate_validation_schema_bytes() -> bytes:
    return (
        b"Choose exactly one verdict: supported, unsupported, or unclear.\n"
        b"Return exactly two lines.\n"
        b"The first line starts with verdict: followed by the chosen verdict.\n"
        b"The second line starts with reason: followed by one concise explanation.\n"
    )
