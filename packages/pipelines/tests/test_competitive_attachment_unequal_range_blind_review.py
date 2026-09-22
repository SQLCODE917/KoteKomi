from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentBlindReviewCase,
    AttachmentBlindReviewCatalog,
    AttachmentBlindReviewSubmission,
    AttachmentGoldAuthority,
    AttachmentSourceRange,
    AttachmentUnequalRangeRelation,
    attachment_blind_review_case_id,
    attachment_blind_review_fingerprint,
)
from kotekomi_pipelines.competitive_attachment_unequal_range_blind_review import (
    build_attachment_blind_review_report,
    render_attachment_blind_review_request,
)


def test_blind_request_omits_every_evaluation_authority() -> None:
    catalog = _catalog()

    result = render_attachment_blind_review_request(catalog)

    assert catalog.cases[0].id in result
    assert 'Candidate: `"Alpha targeted"`' in result
    assert 'Event: `"targeted"`' in result
    assert "Original Gold" not in result
    assert "Reviewed Gold" not in result
    assert "Effective Gold" not in result
    assert "Structural Selection" not in result
    assert "candidate_contains_event" not in result
    assert "sge_666666666666666666666666" not in result


def test_evaluation_rejects_incomplete_response() -> None:
    catalog = _catalog()
    submission = AttachmentBlindReviewSubmission(
        schema_version="attachment_blind_review_submission_v1",
        reviewer="reviewer",
        decisions=(),
    )

    with pytest.raises(ValueError, match="response inventory drifted"):
        build_attachment_blind_review_report(
            inputs=(),
            catalog=catalog,
            submission=submission,
            response_sha256="7" * 64,
        )


def _catalog() -> AttachmentBlindReviewCatalog:
    source = "Alpha targeted Beta."
    digest = hashlib.sha256(source.encode()).hexdigest()
    case_id = attachment_blind_review_case_id(
        phase="development",
        matrix_id="cam_" + "1" * 24,
        candidate_id="cac_" + "2" * 24,
        event_id="sge_" + "3" * 24,
    )
    case = AttachmentBlindReviewCase(
        id=case_id,
        phase="development",
        matrix_id="cam_" + "1" * 24,
        source_text=source,
        source_text_sha256=digest,
        candidate_id="cac_" + "2" * 24,
        event_id="sge_" + "3" * 24,
        candidate_range=AttachmentSourceRange(start=0, end=14, text="Alpha targeted"),
        event_range=AttachmentSourceRange(start=6, end=14, text="targeted"),
        relation=AttachmentUnequalRangeRelation.CANDIDATE_CONTAINS_EVENT,
        foreign_event_ids=("sge_" + "6" * 24,),
        structural_selected=False,
        original_gold="N",
        reviewed_gold="Y",
        effective_gold="Y",
        gold_authority=AttachmentGoldAuthority.REVIEWED,
    )
    draft = AttachmentBlindReviewCatalog.model_construct(
        inputs=(),
        cases=(case,),
        case_count=1,
        selected_count=0,
        excluded_count=1,
        candidate_contains_event_count=1,
        event_contains_candidate_count=0,
        partial_overlap_count=0,
        disjoint_count=0,
        catalog_fingerprint="0" * 64,
    )
    return AttachmentBlindReviewCatalog(
        **draft.model_dump(exclude={"catalog_fingerprint"}),
        catalog_fingerprint=attachment_blind_review_fingerprint(draft),
    )
