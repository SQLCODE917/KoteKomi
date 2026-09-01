"""Generic source-span proposal boundary for hybrid extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kotekomi_application.context_planning import SourceSegment


@dataclass(frozen=True)
class MentionProposalInput:
    """The exact SourceSegments and broad labels supplied to one proposer."""

    source_segments: tuple[SourceSegment, ...]
    type_hints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_segments:
            raise ValueError("Mention proposal input requires at least one SourceSegment.")
        labels = tuple(segment.label for segment in self.source_segments)
        if len(set(labels)) != len(labels):
            raise ValueError("Mention proposal SourceSegment labels must be distinct.")
        if not self.type_hints or tuple(sorted(set(self.type_hints))) != self.type_hints:
            raise ValueError("Mention proposal type hints must be ordered and distinct.")


@dataclass(frozen=True)
class MentionProposal:
    """One fallible, task-local source-span proposal."""

    source_segment_label: str
    text: str
    start: int
    end: int
    type_hints: tuple[str, ...]
    score: float | None = None

    def __post_init__(self) -> None:
        if not self.source_segment_label or not self.text:
            raise ValueError("Mention proposal identity must be complete.")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("Mention proposal positions must be integers.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Mention proposal positions are invalid.")
        if not self.type_hints or tuple(sorted(set(self.type_hints))) != self.type_hints:
            raise ValueError("Mention proposal type hints must be ordered and distinct.")
        if self.score is not None and (
            type(self.score) is not float or not 0.0 <= self.score <= 1.0
        ):
            raise ValueError("Mention proposal score must be between zero and one.")


@dataclass(frozen=True)
class MentionProposalBatch:
    """One complete, tool-attributed proposer result."""

    proposer_id: str
    model_id: str
    model_revision: str
    configuration: tuple[tuple[str, str | float], ...]
    load_elapsed_milliseconds: int
    inference_elapsed_milliseconds: int
    proposals: tuple[MentionProposal, ...]

    def __post_init__(self) -> None:
        if not self.proposer_id or not self.model_id or not self.model_revision:
            raise ValueError("Mention proposal batch identity must be complete.")
        keys = tuple(item[0] for item in self.configuration)
        if tuple(sorted(set(keys))) != keys:
            raise ValueError("Mention proposal configuration must be ordered and distinct.")
        for elapsed in (self.load_elapsed_milliseconds, self.inference_elapsed_milliseconds):
            if type(elapsed) is not int or elapsed < 0:
                raise ValueError("Mention proposal elapsed time must be non-negative.")


class MentionProposer(Protocol):
    """Propose broad spans without owning source or ontology authority."""

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch: ...
