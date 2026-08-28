"""Typed boundary for fallible Organization mention proposers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OrganizationMentionProposalInput:
    """One exact Source segment supplied to a Mention proposer."""

    source_text: str

    def __post_init__(self) -> None:
        if not self.source_text:
            raise ValueError("Organization mention proposal input requires source text.")


@dataclass(frozen=True)
class OrganizationMentionProposal:
    """One fallible Organization span proposal."""

    text: str
    start: int
    end: int
    score: float

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Organization mention proposal text must be non-empty.")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("Organization mention proposal positions must be integers.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Organization mention proposal positions are invalid.")
        if type(self.score) is not float or not 0.0 <= self.score <= 1.0:
            raise ValueError("Organization mention proposal score must be between zero and one.")


@dataclass(frozen=True)
class OrganizationMentionProposalBatch:
    """One tool-attributed proposal batch."""

    proposer_id: str
    model_id: str
    model_revision: str
    threshold: float
    load_elapsed_milliseconds: int
    inference_elapsed_milliseconds: int
    proposals: tuple[OrganizationMentionProposal, ...]

    def __post_init__(self) -> None:
        if not self.proposer_id or not self.model_id or not self.model_revision:
            raise ValueError("Organization mention proposal batch identity must be complete.")
        if type(self.threshold) is not float or not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                "Organization mention proposal threshold must be between zero and one."
            )
        for elapsed in (self.load_elapsed_milliseconds, self.inference_elapsed_milliseconds):
            if type(elapsed) is not int or elapsed < 0:
                raise ValueError("Organization mention proposal elapsed time must be non-negative.")


class OrganizationMentionProposer(Protocol):
    """Propose Organization spans without owning source authority."""

    def propose(
        self, proposal_input: OrganizationMentionProposalInput
    ) -> OrganizationMentionProposalBatch: ...


def propose_validated_organization_mentions(
    proposal_input: OrganizationMentionProposalInput,
    proposer: OrganizationMentionProposer,
) -> OrganizationMentionProposalBatch:
    """Reject a proposal batch unless every span matches the exact Source segment."""
    batch = proposer.propose(proposal_input)
    seen: set[tuple[int, int]] = set()
    for proposal in batch.proposals:
        key = (proposal.start, proposal.end)
        if key in seen:
            raise ValueError("Organization mention proposal batch repeats a source span.")
        seen.add(key)
        if proposal.end > len(proposal_input.source_text):
            raise ValueError("Organization mention proposal exceeds the Source segment.")
        if proposal_input.source_text[proposal.start : proposal.end] != proposal.text:
            raise ValueError("Organization mention proposal text does not match its source span.")
    ordered = tuple(sorted(batch.proposals, key=lambda item: (item.start, item.end, item.text)))
    return OrganizationMentionProposalBatch(
        batch.proposer_id,
        batch.model_id,
        batch.model_revision,
        batch.threshold,
        batch.load_elapsed_milliseconds,
        batch.inference_elapsed_milliseconds,
        ordered,
    )
