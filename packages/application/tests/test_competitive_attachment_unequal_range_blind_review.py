from __future__ import annotations

import pytest
from kotekomi_application import (
    AttachmentBlindReviewDecision,
    AttachmentBlindReviewOutcome,
    AttachmentBlindReviewSubmission,
    AttachmentSourceRange,
    AttachmentUnequalRangeRelation,
    classify_attachment_blind_review_outcome,
    classify_attachment_unequal_range_relation,
)


@pytest.mark.parametrize(
    ("candidate", "event", "expected"),
    (
        ((0, 12), (3, 8), AttachmentUnequalRangeRelation.CANDIDATE_CONTAINS_EVENT),
        ((3, 8), (0, 12), AttachmentUnequalRangeRelation.EVENT_CONTAINS_CANDIDATE),
        ((0, 6), (4, 10), AttachmentUnequalRangeRelation.PARTIAL_OVERLAP),
        ((0, 3), (5, 8), AttachmentUnequalRangeRelation.DISJOINT),
    ),
)
def test_unequal_range_relation_is_exact_interval_algebra(
    candidate: tuple[int, int],
    event: tuple[int, int],
    expected: AttachmentUnequalRangeRelation,
) -> None:
    source = "abcdefghijkl"

    assert (
        classify_attachment_unequal_range_relation(
            AttachmentSourceRange(
                start=candidate[0],
                end=candidate[1],
                text=source[candidate[0] : candidate[1]],
            ),
            AttachmentSourceRange(
                start=event[0],
                end=event[1],
                text=source[event[0] : event[1]],
            ),
        )
        is expected
    )


def test_equal_ranges_are_outside_unequal_range_contract() -> None:
    value = AttachmentSourceRange(start=0, end=3, text="abc")

    with pytest.raises(ValueError, match="cannot accept equal ranges"):
        classify_attachment_unequal_range_relation(value, value)


@pytest.mark.parametrize(
    ("selected_no", "selected_unclear", "excluded_yes", "excluded_unclear", "expected"),
    (
        (0, 0, 0, 0, AttachmentBlindReviewOutcome.SUPPORTED),
        (0, 0, 1, 0, AttachmentBlindReviewOutcome.MIXED),
        (1, 0, 0, 0, AttachmentBlindReviewOutcome.FALSIFIED),
        (0, 1, 0, 0, AttachmentBlindReviewOutcome.INCONCLUSIVE),
        (0, 0, 0, 1, AttachmentBlindReviewOutcome.INCONCLUSIVE),
    ),
)
def test_blind_review_terminal_outcome(
    selected_no: int,
    selected_unclear: int,
    excluded_yes: int,
    excluded_unclear: int,
    expected: AttachmentBlindReviewOutcome,
) -> None:
    assert (
        classify_attachment_blind_review_outcome(
            selected_no_count=selected_no,
            selected_unclear_count=selected_unclear,
            excluded_yes_count=excluded_yes,
            excluded_unclear_count=excluded_unclear,
        )
        is expected
    )


def test_blind_submission_rejects_duplicate_case_ids() -> None:
    decision = AttachmentBlindReviewDecision(
        case_id="ubr_" + "1" * 24,
        answer="Y",
        rationale="The complete Candidate describes the Event.",
    )

    with pytest.raises(ValueError, match="must be distinct"):
        AttachmentBlindReviewSubmission(
            schema_version="attachment_blind_review_submission_v1",
            reviewer="reviewer",
            decisions=(decision, decision),
        )
