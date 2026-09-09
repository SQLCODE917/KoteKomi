"""Source-occurrence selection contract for HP-4 event trigger discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LOCAL_OCCURRENCE = re.compile(r"^o[1-9][0-9]*$")
_OPEN_LABEL = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$")


@dataclass(frozen=True)
class EventTriggerProposal:
    """One model selection from a KoteKomi-owned source-occurrence catalog."""

    line_number: int
    occurrence_id: str
    event_type_label: str


@dataclass(frozen=True)
class EventTriggerLineRejection:
    """One malformed event line isolated from otherwise valid selections."""

    line_number: int
    line: str
    code: str


@dataclass(frozen=True)
class EventTriggerProposalBatch:
    proposals: tuple[EventTriggerProposal, ...]
    rejections: tuple[EventTriggerLineRejection, ...] = ()


@dataclass(frozen=True)
class EventTriggerAbstention:
    reason: str


def parse_event_trigger_output(
    raw_output: bytes,
) -> EventTriggerProposalBatch | EventTriggerAbstention:
    """Parse event lines independently so one malformed line cannot erase another."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Event trigger output must be UTF-8 text.") from error
    lines = text.splitlines()
    if not lines:
        raise ValueError("Event trigger output requires at least one line.")
    if len(lines) == 1 and lines[0].startswith("abstain: "):
        reason = lines[0].removeprefix("abstain: ")
        if not reason or reason != reason.strip():
            raise ValueError("Event trigger abstention requires one trimmed reason.")
        return EventTriggerAbstention(reason)

    proposals: list[EventTriggerProposal] = []
    rejections: list[EventTriggerLineRejection] = []
    selected_occurrences: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        try:
            proposal = _parse_event_line(line_number, line)
            if proposal.occurrence_id in selected_occurrences:
                raise ValueError("duplicate_occurrence")
        except ValueError as error:
            rejections.append(EventTriggerLineRejection(line_number, line, str(error)))
            continue
        selected_occurrences.add(proposal.occurrence_id)
        proposals.append(proposal)
    return EventTriggerProposalBatch(tuple(proposals), tuple(rejections))


def event_trigger_schema_bytes() -> bytes:
    return (
        b"event: <supplied_oN> | <open_event_label>\n"
        b"... one line per selected source occurrence\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


def _parse_event_line(line_number: int, line: str) -> EventTriggerProposal:
    if not line or line != line.strip():
        raise ValueError("untrimmed_or_empty_line")
    if not line.startswith("event: "):
        raise ValueError("unknown_line")
    parts = line.removeprefix("event: ").split(" | ")
    if len(parts) != 2 or any(not part for part in parts):
        raise ValueError("invalid_event_shape")
    occurrence_id, event_type_label = parts
    if _LOCAL_OCCURRENCE.fullmatch(occurrence_id) is None:
        raise ValueError("invalid_occurrence_id")
    if _OPEN_LABEL.fullmatch(event_type_label) is None:
        raise ValueError("invalid_event_label")
    return EventTriggerProposal(line_number, occurrence_id, event_type_label)
