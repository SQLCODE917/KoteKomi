from __future__ import annotations

from kotekomi_application import (
    AttachmentNestedTransferDecision,
    AttachmentNestedTransferEvaluation,
    AttachmentNestedTransferOutcome,
    AttachmentNestedTransferSelectorCatalog,
    AttachmentNestedTransferSubmission,
    classify_attachment_nested_transfer_outcome,
)

EvaluationTuple = tuple[AttachmentNestedTransferEvaluation, ...]


def test_selector_catalog_requires_twenty_ordered_answer_free_cases() -> None:
    selectors = tuple(
        {
            "case_id": f"NET-{index:03d}",
            "source_segment_id": f"src_{index:024x}",
            "candidate_text": f"candidate {index}",
            "target_event_text": f"event {index}",
            "contained_event_texts": (f"contained {index}",),
        }
        for index in range(1, 21)
    )

    catalog = AttachmentNestedTransferSelectorCatalog.model_validate(
        {
            "schema_version": "attachment_nested_transfer_selector_catalog_v1",
            "source_catalog_path": "docs/organization-mention-held-out-gold-v1.json",
            "source_catalog_sha256": "a" * 64,
            "selectors": selectors,
        }
    )

    assert len(catalog.selectors) == 20
    assert not any("answer" in item.model_fields_set for item in catalog.selectors)


def test_blind_submission_requires_six_labels_from_each_decided_class() -> None:
    decisions = tuple(
        AttachmentNestedTransferDecision(
            case_id=f"ntc_{index:024x}",
            answer="Y" if index <= 14 else "N",
            rationale="Exact semantic judgment.",
        )
        for index in range(1, 21)
    )

    submission = AttachmentNestedTransferSubmission(
        reviewer="reviewer",
        decisions=decisions,
    )

    assert sum(item.answer == "Y" for item in submission.decisions) == 14
    assert sum(item.answer == "N" for item in submission.decisions) == 6


def test_transfer_outcome_distinguishes_supported_mixed_falsified_and_inconclusive() -> None:
    def evaluations(*, correct_count: int, unresolved: bool = False) -> EvaluationTuple:
        error_order = (9, 19, 8, 18, 7, 17, 6, 16, 5, 15, 4, 14, 3, 13, 2, 12, 1, 11, 0, 10)
        wrong_indices = set(error_order[: 20 - correct_count])
        values: list[AttachmentNestedTransferEvaluation] = []
        for index in range(20):
            expected = AttachmentNestedTransferDecision(
                case_id=f"ntc_{index + 1:024x}",
                answer="Y" if index < 10 else "N",
                rationale="Reviewed.",
            )
            values.append(
                AttachmentNestedTransferEvaluation.model_construct(
                    case=None,
                    expected=expected,
                    observation=None,
                    complete=not (unresolved and index == 0),
                    correct=index not in wrong_indices,
                )
            )
        return tuple(values)

    assert (
        classify_attachment_nested_transfer_outcome(evaluations=evaluations(correct_count=18))
        is AttachmentNestedTransferOutcome.SUPPORTED
    )
    assert (
        classify_attachment_nested_transfer_outcome(evaluations=evaluations(correct_count=17))
        is AttachmentNestedTransferOutcome.MIXED
    )
    assert (
        classify_attachment_nested_transfer_outcome(evaluations=evaluations(correct_count=14))
        is AttachmentNestedTransferOutcome.FALSIFIED
    )
    assert (
        classify_attachment_nested_transfer_outcome(
            evaluations=evaluations(correct_count=20, unresolved=True)
        )
        is AttachmentNestedTransferOutcome.INCONCLUSIVE
    )
