from __future__ import annotations

import pytest
from kotekomi_application import (
    OrganizationMentionProposal,
    OrganizationMentionProposalBatch,
    OrganizationMentionProposalInput,
    propose_validated_organization_mentions,
)


class FakeProposer:
    def __init__(self, batch: OrganizationMentionProposalBatch) -> None:
        self.batch = batch

    def propose(
        self, proposal_input: OrganizationMentionProposalInput
    ) -> OrganizationMentionProposalBatch:
        del proposal_input
        return self.batch


def _batch(*proposals: OrganizationMentionProposal) -> OrganizationMentionProposalBatch:
    return OrganizationMentionProposalBatch(
        "fake-proposer",
        "fake-model",
        "revision-1",
        0.5,
        10,
        2,
        proposals,
    )


def test_validated_mentions_preserve_overlaps_and_sort_by_source_position() -> None:
    source = OrganizationMentionProposalInput("Northstar Research Institute")
    batch = _batch(
        OrganizationMentionProposal("Research Institute", 10, 28, 0.7),
        OrganizationMentionProposal("Northstar Research Institute", 0, 28, 0.9),
    )

    result = propose_validated_organization_mentions(source, FakeProposer(batch))

    assert result.proposals == (
        OrganizationMentionProposal("Northstar Research Institute", 0, 28, 0.9),
        OrganizationMentionProposal("Research Institute", 10, 28, 0.7),
    )


@pytest.mark.parametrize(
    "batch",
    (
        _batch(OrganizationMentionProposal("Elsewhere", 0, 9, 0.5)),
        _batch(OrganizationMentionProposal("Northstar", 0, 40, 0.5)),
        _batch(
            OrganizationMentionProposal("Northstar", 0, 9, 0.5),
            OrganizationMentionProposal("Northstar", 0, 9, 0.6),
        ),
    ),
)
def test_invalid_proposal_rejects_the_complete_batch(
    batch: OrganizationMentionProposalBatch,
) -> None:
    with pytest.raises(ValueError):
        propose_validated_organization_mentions(
            OrganizationMentionProposalInput("Northstar Research Institute"),
            FakeProposer(batch),
        )


def test_batch_validation_preserves_proposer_score_as_metadata() -> None:
    batch = _batch(OrganizationMentionProposal("Northstar", 0, 9, 0.51))

    result = propose_validated_organization_mentions(
        OrganizationMentionProposalInput("Northstar"),
        FakeProposer(batch),
    )

    assert result.proposals[0].score == 0.51
