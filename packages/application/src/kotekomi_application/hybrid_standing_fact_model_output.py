"""Literal model-output contract for HP-10 standing facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_LOCAL_CANDIDATE = re.compile(r"^c[1-9][0-9]*$")


class StandingFactObjectKind(StrEnum):
    ENTITY = "entity"
    LITERAL = "literal"


@dataclass(frozen=True)
class StandingFactProposal:
    subject_label: str
    relation_label: str
    object_kind: StandingFactObjectKind
    object_value: str


@dataclass(frozen=True)
class StandingFactLineRejection:
    line_number: int
    raw_line: str
    reason: str


@dataclass(frozen=True)
class StandingFactProposalBatch:
    proposals: tuple[StandingFactProposal, ...]
    rejections: tuple[StandingFactLineRejection, ...] = ()


@dataclass(frozen=True)
class StandingFactAbstention:
    reason: str


def parse_standing_fact_output(
    raw_output: bytes,
) -> StandingFactProposalBatch | StandingFactAbstention:
    """Parse each fact independently while retaining invalid model observations."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Standing Fact output must be UTF-8 text.") from error
    raw_lines = text.splitlines()
    if not raw_lines or any(not line or line != line.strip() for line in raw_lines):
        raise ValueError("Standing Fact output requires trimmed non-empty lines.")
    if len(raw_lines) == 1 and raw_lines[0].startswith("abstain: "):
        reason = raw_lines[0].removeprefix("abstain: ")
        if not reason:
            raise ValueError("Standing Fact abstention requires a reason.")
        return StandingFactAbstention(reason)
    if any(line.startswith("abstain:") for line in raw_lines):
        raise ValueError("Standing Fact output cannot mix facts and abstention.")

    proposals: list[StandingFactProposal] = []
    rejections: list[StandingFactLineRejection] = []
    seen: set[StandingFactProposal] = set()
    for line_number, raw_line in enumerate(raw_lines, start=1):
        try:
            proposal = _parse_fact_line(raw_line)
            if proposal in seen:
                raise ValueError("duplicate fact")
        except ValueError as error:
            rejections.append(StandingFactLineRejection(line_number, raw_line, str(error)))
            continue
        proposals.append(proposal)
        seen.add(proposal)
    return StandingFactProposalBatch(tuple(proposals), tuple(rejections))


def standing_fact_schema_bytes() -> bytes:
    return (
        b"fact: cN | <ordinary-language relation label> | entity | cN\n"
        b"fact: cN | <ordinary-language relation label> | literal | <exact source literal>\n"
        b"... one line per distinct standing fact\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


def _parse_fact_line(line: str) -> StandingFactProposal:
    if not line.startswith("fact: "):
        raise ValueError("fact lines must begin with 'fact: '")
    parts = line.removeprefix("fact: ").split(" | ")
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("fact lines require subject, relation, object kind, and object")
    subject, relation, kind_text, object_value = parts
    if not _LOCAL_CANDIDATE.fullmatch(subject):
        raise ValueError("subject must use one local candidate label")
    if "|" in relation or len(relation) > 160:
        raise ValueError("relation label is invalid")
    try:
        kind = StandingFactObjectKind(kind_text)
    except ValueError as error:
        raise ValueError("object kind must be entity or literal") from error
    if kind is StandingFactObjectKind.ENTITY and not _LOCAL_CANDIDATE.fullmatch(object_value):
        raise ValueError("entity object must use one local candidate label")
    return StandingFactProposal(subject, relation, kind, object_value)
