"""Literal model-output contracts for HP-4 event framing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from kotekomi_application.hybrid_event_frames import (
    EventModality,
    EventPolarity,
    EventQualifierKind,
)

_LOCAL_EVENT = re.compile(r"^e[1-9][0-9]*$")
_LOCAL_CANDIDATE = re.compile(r"^c[1-9][0-9]*$")
_LOCAL_SEGMENT = re.compile(r"^s[1-9][0-9]*$")
_OPEN_LABEL = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$")


@dataclass(frozen=True)
class EventTriggerProposal:
    event_label: str
    source_segment_label: str
    trigger_text: str
    event_type_label: str


@dataclass(frozen=True)
class EventTriggerProposalBatch:
    proposals: tuple[EventTriggerProposal, ...]


@dataclass(frozen=True)
class EventTriggerAbstention:
    reason: str


@dataclass(frozen=True)
class EventArgumentProposal:
    candidate_label: str
    role_label: str
    support_segment_label: str


@dataclass(frozen=True)
class EventQualifierProposal:
    kind: EventQualifierKind
    source_segment_label: str
    literal_text: str


@dataclass(frozen=True)
class EventFrameProposal:
    event_label: str
    polarity: EventPolarity
    modality: EventModality
    attribution_candidate_labels: tuple[str, ...]
    source_narrator_attribution: bool
    arguments: tuple[EventArgumentProposal, ...]
    qualifiers: tuple[EventQualifierProposal, ...]


@dataclass(frozen=True)
class EventFrameAbstention:
    reason: str


def parse_event_trigger_output(
    raw_output: bytes,
) -> EventTriggerProposalBatch | EventTriggerAbstention:
    lines = _strict_lines(raw_output, "Event trigger")
    if len(lines) == 1 and lines[0].startswith("abstain: "):
        reason = lines[0].removeprefix("abstain: ")
        if not reason:
            raise ValueError("Event trigger abstention requires a reason.")
        return EventTriggerAbstention(reason)
    proposals: list[EventTriggerProposal] = []
    for index, line in enumerate(lines, start=1):
        if not line.startswith("event: "):
            raise ValueError("Event trigger lines must begin with 'event: '.")
        parts = line.removeprefix("event: ").split(" | ")
        if len(parts) != 4 or any(not part for part in parts):
            raise ValueError("Event trigger lines require event, segment, literal, and type.")
        event_label, segment_label, trigger_text, event_type_label = parts
        if event_label != f"e{index}":
            raise ValueError("Event trigger labels must be contiguous from e1.")
        _require_label(segment_label, _LOCAL_SEGMENT, "SourceSegment")
        _require_label(event_type_label, _OPEN_LABEL, "event type")
        proposals.append(
            EventTriggerProposal(
                event_label,
                segment_label,
                trigger_text,
                event_type_label,
            )
        )
    if len(set(proposals)) != len(proposals):
        raise ValueError("Event trigger output repeats a proposal.")
    return EventTriggerProposalBatch(tuple(proposals))


def parse_event_frame_output(raw_output: bytes) -> EventFrameProposal | EventFrameAbstention:
    lines = _strict_lines(raw_output, "Event frame")
    if len(lines) == 1 and lines[0].startswith("abstain: "):
        reason = lines[0].removeprefix("abstain: ")
        if not reason:
            raise ValueError("Event frame abstention requires a reason.")
        return EventFrameAbstention(reason)
    if len(lines) < 4:
        raise ValueError("Event frame output requires four scalar lines.")
    event_label = _scalar(lines[0], "event")
    _require_label(event_label, _LOCAL_EVENT, "event")
    try:
        polarity = EventPolarity(_scalar(lines[1], "polarity"))
        modality = EventModality(_scalar(lines[2], "modality"))
    except ValueError as error:
        raise ValueError("Event frame polarity or modality is unknown.") from error
    attribution = _scalar(lines[3], "attribution")
    source_narrator = attribution == "source_narrator"
    attribution_labels: tuple[str, ...] = ()
    if not source_narrator:
        attribution_labels = tuple(attribution.split(","))
        if not attribution_labels or any(not item for item in attribution_labels):
            raise ValueError("Event frame attribution labels are invalid.")
        if len(set(attribution_labels)) != len(attribution_labels):
            raise ValueError("Event frame attribution labels must be distinct.")
        for item in attribution_labels:
            _require_label(item, _LOCAL_CANDIDATE, "attribution candidate")
    arguments: list[EventArgumentProposal] = []
    qualifiers: list[EventQualifierProposal] = []
    saw_qualifier = False
    for line in lines[4:]:
        if line.startswith("argument: "):
            if saw_qualifier:
                raise ValueError("Event frame arguments must precede qualifiers.")
            parts = line.removeprefix("argument: ").split(" | ")
            if len(parts) != 3 or any(not item for item in parts):
                raise ValueError("Event arguments require candidate, role, and support.")
            candidate_label, role_label, support_label = parts
            _require_label(candidate_label, _LOCAL_CANDIDATE, "argument candidate")
            _require_label(role_label, _OPEN_LABEL, "argument role")
            _require_label(support_label, _LOCAL_SEGMENT, "argument support")
            arguments.append(EventArgumentProposal(candidate_label, role_label, support_label))
            continue
        if line.startswith("qualifier: "):
            saw_qualifier = True
            parts = line.removeprefix("qualifier: ").split(" | ")
            if len(parts) != 3 or any(not item for item in parts):
                raise ValueError("Event qualifiers require kind, segment, and literal.")
            kind_text, segment_label, literal_text = parts
            try:
                kind = EventQualifierKind(kind_text)
            except ValueError as error:
                raise ValueError("Event qualifier kind is unknown.") from error
            _require_label(segment_label, _LOCAL_SEGMENT, "qualifier SourceSegment")
            qualifiers.append(EventQualifierProposal(kind, segment_label, literal_text))
            continue
        raise ValueError("Event frame output contains an unknown line.")
    if len(set(arguments)) != len(arguments):
        raise ValueError("Event frame output repeats an argument.")
    if len(set(qualifiers)) != len(qualifiers):
        raise ValueError("Event frame output repeats a qualifier.")
    return EventFrameProposal(
        event_label,
        polarity,
        modality,
        attribution_labels,
        source_narrator,
        tuple(arguments),
        tuple(qualifiers),
    )


def event_trigger_schema_bytes() -> bytes:
    return (
        b"event: eN | sN | <exact trigger literal> | <open_event_label>\n"
        b"... one line per event, with contiguous event labels from e1\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


def event_frame_schema_bytes() -> bytes:
    return (
        b"event: eN\n"
        b"polarity: affirmed|negated\n"
        b"modality: actual|planned|possible|uncertain|recommended|hypothetical\n"
        b"attribution: source_narrator|cN[,cN...]\n"
        b"argument: cN | <open_role_label> | sN\n"
        b"... zero or more argument lines\n"
        b"qualifier: time|place | sN | <exact literal>\n"
        b"... zero or more qualifier lines\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


def _strict_lines(raw_output: bytes, label: str) -> list[str]:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} output must be UTF-8 text.") from error
    raw_lines = text.splitlines()
    if not raw_lines or any(line and line != line.strip() for line in raw_lines):
        raise ValueError(f"{label} output requires trimmed lines.")
    lines = [line for line in raw_lines if line]
    if not lines:
        raise ValueError(f"{label} output requires at least one non-empty line.")
    return lines


def _scalar(line: str, key: str) -> str:
    prefix = f"{key}: "
    if not line.startswith(prefix):
        raise ValueError(f"Event frame expected '{key}' in fixed order.")
    value = line.removeprefix(prefix)
    if not value:
        raise ValueError(f"Event frame {key} requires a value.")
    return value


def _require_label(value: str, pattern: re.Pattern[str], label: str) -> None:
    if pattern.fullmatch(value) is None:
        raise ValueError(f"HP-4 {label} label is invalid: {value}")
