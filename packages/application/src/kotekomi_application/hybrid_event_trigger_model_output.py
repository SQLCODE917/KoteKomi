"""Simple model-answer contracts for source-bound Event head judgment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EventHeadAnswerValue(StrEnum):
    """The model's bounded judgment about one target expression."""

    EVENT = "EVENT"
    NOT_EVENT = "NOT_EVENT"


@dataclass(frozen=True)
class EventHeadAnswer:
    """One validated model answer for one invocation-bound target."""

    value: EventHeadAnswerValue


class EventVerbRoleAnswerValue(StrEnum):
    """The role of one invocation-bound verb in its exact sentence."""

    EVENT = "EVENT"
    STANDING = "STANDING"
    HELPER = "HELPER"


@dataclass(frozen=True)
class EventVerbRoleAnswer:
    """One validated three-way answer for a marked verb."""

    value: EventVerbRoleAnswerValue


class BinarySemanticAnswerValue(StrEnum):
    """One invocation-bound yes/no semantic judgment."""

    YES = "YES"
    NO = "NO"


@dataclass(frozen=True)
class BinarySemanticAnswer:
    """One validated answer whose meaning is supplied by its task schema."""

    value: BinarySemanticAnswerValue


def parse_event_head_answer(raw_output: bytes) -> EventHeadAnswer:
    """Parse exactly one target-bound Event judgment."""
    answer = _single_answer(raw_output)
    try:
        value = {
            "E": EventHeadAnswerValue.EVENT,
            "N": EventHeadAnswerValue.NOT_EVENT,
        }[answer]
    except KeyError as error:
        raise ValueError("Event head answer must be E or N.") from error
    return EventHeadAnswer(value)


def parse_event_verb_role_answer(raw_output: bytes) -> EventVerbRoleAnswer:
    """Parse exactly one target-bound verb-role judgment."""
    answer = _single_answer(raw_output)
    try:
        value = {
            "E": EventVerbRoleAnswerValue.EVENT,
            "S": EventVerbRoleAnswerValue.STANDING,
            "H": EventVerbRoleAnswerValue.HELPER,
        }[answer]
    except KeyError as error:
        raise ValueError("Event verb role answer must be E, S, or H.") from error
    return EventVerbRoleAnswer(value)


def parse_binary_semantic_answer(raw_output: bytes) -> BinarySemanticAnswer:
    """Parse exactly one task-bound binary semantic judgment."""
    answer = _single_answer(raw_output)
    try:
        value = {"Y": BinarySemanticAnswerValue.YES, "N": BinarySemanticAnswerValue.NO}[answer]
    except KeyError as error:
        raise ValueError("Binary semantic answer must be Y or N.") from error
    return BinarySemanticAnswer(value)


def event_head_answer_schema_bytes() -> bytes:
    return b"Return exactly one character: E or N.\n"


def event_verb_role_answer_schema_bytes() -> bytes:
    return b"Return exactly one character: E, S, or H.\n"


def binary_semantic_answer_schema_bytes() -> bytes:
    return b"Return exactly one character: Y or N.\n"


def _single_answer(raw_output: bytes) -> str:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Event head answer must be UTF-8 text.") from error
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
        raise ValueError("Event head answer requires exactly one trimmed line.")
    return lines[0]
