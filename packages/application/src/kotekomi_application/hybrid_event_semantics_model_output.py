"""Literal model-output contracts for HP-6 semantic tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from kotekomi_domain import TemporalRelation

from kotekomi_application.hybrid_event_semantics import (
    SupportOutcome,
)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?$")
_CANDIDATE_SELECTOR = re.compile(r"^c[1-9][0-9]*$")
_SOURCE_SELECTOR = re.compile(r"^o[1-9][0-9]*(?:-o[1-9][0-9]*)?$")


@dataclass(frozen=True)
class EventSemanticArgumentProposal:
    frame_role_id: str
    target_value: str


@dataclass(frozen=True)
class EventSemanticQualifierProposal:
    kind: Literal["place", "time"]
    literal_text: str
    temporal_relation: TemporalRelation | None = None


@dataclass(frozen=True)
class EventSemanticQualifierSelection:
    kind: Literal["place", "time"]
    source_selector: str
    temporal_relation: TemporalRelation | None = None


@dataclass(frozen=True)
class EventSemanticProposal:
    frame_id: str | None
    polarity: str
    modality: str
    attribution_value: str
    arguments: tuple[EventSemanticArgumentProposal, ...]
    qualifiers: tuple[EventSemanticQualifierProposal, ...]
    reason: str


@dataclass(frozen=True)
class EventFrameSelection:
    frame_id: str | None
    reason: str


@dataclass(frozen=True)
class EventPresentationSelection:
    polarity: str
    modality: str
    attribution_selector: str
    qualifiers: tuple[EventSemanticQualifierSelection, ...]
    reason: str


@dataclass(frozen=True)
class EventPresentationParseResult:
    selection: EventPresentationSelection
    rejections: tuple[EventSemanticLineRejection, ...]


@dataclass(frozen=True)
class EventSemanticLineRejection:
    line_number: int
    line: str
    code: str


@dataclass(frozen=True)
class EventSemanticRoleTargetProposal:
    target_selector: str | None
    reason: str


@dataclass(frozen=True)
class SemanticSupportModelJudgment:
    outcome: SupportOutcome
    reason: str


def parse_event_frame_selection_output(raw_output: bytes) -> EventFrameSelection:
    lines = _strict_lines(raw_output, "Event-frame selection")
    if len(lines) != 2:
        raise ValueError("Event-frame selection requires exactly two lines.")
    frame_value = _scalar(lines[0], "frame")
    reason = _scalar(lines[1], "reason")
    if frame_value == "unresolved":
        return EventFrameSelection(None, reason)
    _require_identifier(frame_value, "event frame")
    return EventFrameSelection(frame_value, reason)


def parse_event_presentation_output(raw_output: bytes) -> EventPresentationParseResult:
    lines = _strict_lines(raw_output, "Event-presentation")
    if len(lines) < 4:
        raise ValueError("Event-presentation output requires four envelope lines.")
    polarity = _scalar(lines[0], "polarity")
    modality = _scalar(lines[1], "modality")
    attribution = _scalar(lines[2], "attribution")
    if polarity not in {"affirmed", "negated"}:
        raise ValueError("Event-presentation polarity is unknown.")
    if modality not in {
        "actual",
        "planned",
        "possible",
        "uncertain",
        "recommended",
        "hypothetical",
    }:
        raise ValueError("Event-presentation modality is unknown.")
    if attribution not in {"source_narrator", "unresolved"}:
        _target_selector(attribution, "attribution")
    if not lines[-1].startswith("reason: "):
        raise ValueError("Event-presentation output requires reason last.")
    reason = lines[-1].removeprefix("reason: ")
    if not reason:
        raise ValueError("Event-presentation reason requires text.")
    qualifiers: list[EventSemanticQualifierSelection] = []
    rejections: list[EventSemanticLineRejection] = []
    qualifier_keys: set[tuple[str, str, str]] = set()
    for line_number, line in enumerate(lines[3:-1], start=4):
        try:
            parts = line.removeprefix("qualifier: ").split(" | ")
            if not line.startswith("qualifier: "):
                raise ValueError("unknown_optional_line")
            if len(parts) == 3 and parts[0] == "time":
                relation = TemporalRelation(parts[1])
                selector = _source_selector(parts[2], "qualifier source selector")
                proposal = EventSemanticQualifierSelection("time", selector, relation)
            elif len(parts) == 2 and parts[0] == "place":
                selector = _source_selector(parts[1], "qualifier source selector")
                proposal = EventSemanticQualifierSelection("place", selector)
            else:
                raise ValueError("invalid_qualifier_shape")
            key = (
                proposal.kind,
                proposal.temporal_relation.value if proposal.temporal_relation else "",
                proposal.source_selector,
            )
            if key in qualifier_keys:
                raise ValueError("duplicate_qualifier")
            qualifier_keys.add(key)
            qualifiers.append(proposal)
        except ValueError as error:
            rejections.append(EventSemanticLineRejection(line_number, line, str(error)))
    return EventPresentationParseResult(
        EventPresentationSelection(
            polarity,
            modality,
            attribution,
            tuple(qualifiers),
            reason,
        ),
        tuple(rejections),
    )


def parse_event_semantic_role_target_output(
    raw_output: bytes,
) -> EventSemanticRoleTargetProposal:
    lines = _strict_lines(raw_output, "Event-semantic role-target")
    if len(lines) != 2:
        raise ValueError("Event-semantic role-target output requires exactly two lines.")
    if not lines[0].startswith("target: ") or not lines[1].startswith("reason: "):
        raise ValueError("Event-semantic role-target fields require fixed order.")
    target = lines[0].removeprefix("target: ")
    reason = lines[1].removeprefix("reason: ")
    if not reason:
        raise ValueError("Event-semantic role-target reason requires text.")
    if target == "absent":
        return EventSemanticRoleTargetProposal(None, reason)
    return EventSemanticRoleTargetProposal(
        _target_selector(target, "role target"),
        reason,
    )


def parse_semantic_support_output(raw_output: bytes) -> SemanticSupportModelJudgment:
    lines = _strict_lines(raw_output, "Semantic-support")
    if len(lines) != 2:
        raise ValueError("Semantic-support output requires exactly two lines.")
    if not lines[0].startswith("outcome: ") or not lines[1].startswith("reason: "):
        raise ValueError("Semantic-support fields require fixed order.")
    outcome_value = lines[0].removeprefix("outcome: ")
    reason = lines[1].removeprefix("reason: ")
    if not reason:
        raise ValueError("Semantic-support reason requires text.")
    try:
        outcome = SupportOutcome(outcome_value)
    except ValueError as error:
        raise ValueError("Semantic-support outcome is unknown.") from error
    return SemanticSupportModelJudgment(outcome, reason)


def event_frame_selection_schema_bytes() -> bytes:
    return b"frame: <supplied_frame_id>|unresolved\nreason: <one non-empty sentence>\n"


def event_presentation_schema_bytes() -> bytes:
    return (
        b"polarity: affirmed|negated\n"
        b"modality: actual|planned|possible|uncertain|recommended|hypothetical\n"
        b"attribution: source_narrator|<supplied cN or oN[-oN] selector>|unresolved\n"
        b"qualifier: time | before|during|after|at | <supplied oN[-oN] selector>\n"
        b"qualifier: place | <supplied oN[-oN] selector>\n"
        b"... zero or more qualifier lines\n"
        b"reason: <one non-empty sentence>\n"
    )


def event_semantic_role_target_schema_bytes() -> bytes:
    return (
        b"target: <supplied cN or oN[-oN] selector, or absent>\nreason: <one non-empty sentence>\n"
    )


def semantic_support_schema_bytes() -> bytes:
    return (
        b"outcome: directly_supported|partially_supported|unsupported|contradicted|ambiguous\n"
        b"reason: <one non-empty sentence>\n"
    )


def _strict_lines(raw_output: bytes, label: str) -> list[str]:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} output must be UTF-8 text.") from error
    lines = text.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        raise ValueError(f"{label} output requires non-empty trimmed lines.")
    return lines


def _literal(value: str, label: str) -> str:
    if not value:
        raise ValueError(f"Event-semantic {label} must not be empty.")
    return value


def _require_identifier(value: str, label: str) -> None:
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"Event-semantic {label} is invalid.")


def _target_selector(value: str, label: str) -> str:
    if _CANDIDATE_SELECTOR.fullmatch(value) is None:
        return _source_selector(value, label)
    return value


def _source_selector(value: str, label: str) -> str:
    if _SOURCE_SELECTOR.fullmatch(value) is None:
        raise ValueError(f"Event-semantic {label} is not a supplied source selector.")
    return value


def _scalar(line: str, key: str) -> str:
    prefix = f"{key}: "
    if not line.startswith(prefix):
        raise ValueError(f"Event-semantic output expected {key} in fixed order.")
    return _literal(line.removeprefix(prefix), key)
