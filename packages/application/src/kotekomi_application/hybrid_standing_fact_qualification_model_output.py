"""Literal model-output contract for standing-fact semantic qualification."""

from __future__ import annotations

from dataclasses import dataclass

from kotekomi_domain import StandingFactQualificationOutcome


@dataclass(frozen=True)
class StandingFactQualificationOutput:
    outcome: StandingFactQualificationOutcome
    reason: str


def parse_standing_fact_qualification_output(
    raw_output: bytes,
) -> StandingFactQualificationOutput:
    try:
        lines = raw_output.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Standing Fact qualification output must be UTF-8.") from error
    if len(lines) != 2 or any(not line or line != line.strip() for line in lines):
        raise ValueError("Standing Fact qualification requires exactly two trimmed lines.")
    if not lines[0].startswith("outcome: ") or not lines[1].startswith("reason: "):
        raise ValueError("Standing Fact qualification fields are missing or out of order.")
    try:
        outcome = StandingFactQualificationOutcome(lines[0].removeprefix("outcome: "))
    except ValueError as error:
        raise ValueError("Standing Fact qualification outcome is unsupported.") from error
    reason = lines[1].removeprefix("reason: ")
    if not reason:
        raise ValueError("Standing Fact qualification reason must be non-empty.")
    return StandingFactQualificationOutput(outcome, reason)


def standing_fact_qualification_schema_bytes() -> bytes:
    outcomes = " | ".join(item.value for item in StandingFactQualificationOutcome)
    return f"outcome: <{outcomes}>\nreason: <one source-based sentence>\n".encode()
