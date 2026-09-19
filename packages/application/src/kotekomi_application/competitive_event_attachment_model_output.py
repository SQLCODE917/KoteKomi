"""Finite model-output contract for competitive Event attachment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class CompetitiveAttachmentAnswerKind(StrEnum):
    """Semantic meaning of one finite competitive-attachment answer."""

    ATTACHED = "attached"
    NONE = "none"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class CompetitiveAttachmentAnswer:
    """One validated set of task-local Event labels."""

    kind: CompetitiveAttachmentAnswerKind
    event_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is CompetitiveAttachmentAnswerKind.ATTACHED:
            if not self.event_labels:
                raise ValueError("An attached answer requires at least one Event label.")
        elif self.event_labels:
            raise ValueError("NONE and UNCLEAR answers cannot contain Event labels.")


def parse_competitive_attachment_answer(
    raw_output: bytes,
    *,
    allowed_event_labels: tuple[str, ...] | None = None,
) -> CompetitiveAttachmentAnswer:
    """Parse one ordered task-local label set while preserving raw transport evidence."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Competitive attachment answer must be UTF-8 text.") from error
    payload = text.strip(" \t\r\n")
    if payload == "NONE":
        return CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.NONE)
    if payload == "UNCLEAR":
        return CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.UNCLEAR)
    labels = tuple(payload.split(","))
    if not labels or any(re.fullmatch(r"E[1-9][0-9]*", item) is None for item in labels):
        raise ValueError(
            "Competitive attachment answer must be NONE, UNCLEAR, or ordered Event labels."
        )
    if len(set(labels)) != len(labels):
        raise ValueError("Competitive attachment answer cannot repeat an Event label.")
    if allowed_event_labels is not None:
        positions = {label: index for index, label in enumerate(allowed_event_labels)}
        if any(label not in positions for label in labels):
            raise ValueError("Competitive attachment answer contains an unknown Event label.")
        if tuple(sorted(labels, key=positions.__getitem__)) != labels:
            raise ValueError("Competitive attachment Event labels must use supplied order.")
    else:
        ordinals = tuple(int(label[1:]) for label in labels)
        if tuple(sorted(ordinals)) != ordinals:
            raise ValueError("Competitive attachment Event labels must use numeric order.")
    return CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.ATTACHED, labels)


def competitive_attachment_answer_schema_bytes(event_labels: tuple[str, ...]) -> bytes:
    """Return the invocation-bound finite output contract."""
    if not event_labels or any(
        label != f"E{ordinal}" for ordinal, label in enumerate(event_labels, start=1)
    ):
        raise ValueError("Competitive attachment schema requires contiguous Event labels.")
    labels = ",".join(event_labels)
    return (
        "Return exactly NONE, UNCLEAR, or a comma-separated subset of these Event labels "
        f"in supplied order: {labels}. Surrounding ASCII whitespace is framing only.\n"
    ).encode()
