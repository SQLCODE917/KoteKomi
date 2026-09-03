"""Literal model-output contracts for HP-6 semantic tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from kotekomi_application.hybrid_event_semantics import (
    SupportOutcome,
)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?$")


@dataclass(frozen=True)
class EventSemanticArgumentProposal:
    frame_role_id: str
    target_value: str


@dataclass(frozen=True)
class EventSemanticQualifierProposal:
    qualifier_label: str


@dataclass(frozen=True)
class EventSemanticProposal:
    frame_id: str | None
    arguments: tuple[EventSemanticArgumentProposal, ...]
    qualifiers: tuple[EventSemanticQualifierProposal, ...]
    reason: str


@dataclass(frozen=True)
class EventSemanticRoleTargetProposal:
    target_value: str | None
    reason: str


@dataclass(frozen=True)
class SemanticSupportModelJudgment:
    outcome: SupportOutcome
    reason: str


def parse_event_semantic_output(raw_output: bytes) -> EventSemanticProposal:
    lines = _strict_lines(raw_output, "Event-semantic")
    if not lines[0].startswith("frame: ") or not lines[-1].startswith("reason: "):
        raise ValueError("Event-semantic output requires frame first and reason last.")
    frame_value = lines[0].removeprefix("frame: ")
    reason = lines[-1].removeprefix("reason: ")
    if not reason:
        raise ValueError("Event-semantic reason requires text.")
    if frame_value == "unresolved":
        if len(lines) != 2:
            raise ValueError("An unresolved frame cannot contain semantic fields.")
        return EventSemanticProposal(None, (), (), reason)
    _require_identifier(frame_value, "event frame")
    arguments: list[EventSemanticArgumentProposal] = []
    qualifiers: list[EventSemanticQualifierProposal] = []
    for line in lines[1:-1]:
        if line.startswith("argument: "):
            parts = line.removeprefix("argument: ").split(" | ", maxsplit=1)
            if len(parts) != 2:
                raise ValueError("Event-semantic argument requires two fields.")
            role_id, target = parts
            _require_identifier(role_id, "frame role")
            _literal(target, "argument target")
            arguments.append(EventSemanticArgumentProposal(role_id, target))
            continue
        if line.startswith("qualifier: "):
            label = _literal(line.removeprefix("qualifier: "), "qualifier label")
            qualifiers.append(EventSemanticQualifierProposal(label))
            continue
        raise ValueError("Event-semantic output contains an unknown line.")
    if len(set(arguments)) != len(arguments):
        raise ValueError("Event-semantic output repeats an argument.")
    if len(set(qualifiers)) != len(qualifiers):
        raise ValueError("Event-semantic output repeats a qualifier.")
    return EventSemanticProposal(
        frame_value,
        tuple(arguments),
        tuple(qualifiers),
        reason,
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
        _literal(target, "role target"),
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


def event_semantic_schema_bytes() -> bytes:
    return (
        b"frame: <supplied_frame_id>\n"
        b"argument: <supplied_frame_role_id> | <supplied label or source literal>\n"
        b"... zero or more argument lines\n"
        b"qualifier: <supplied_qualifier_label>\n"
        b"... zero or more qualifier lines\n"
        b"reason: <one non-empty sentence>\n\n"
        b"or\n\n"
        b"frame: unresolved\n"
        b"reason: <one non-empty sentence>\n"
    )


def event_semantic_role_target_schema_bytes() -> bytes:
    return (
        b"target: <supplied cN or eN label, exact source literal, or absent>\n"
        b"reason: <one non-empty sentence>\n"
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
