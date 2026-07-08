from datetime import UTC, datetime
from typing import Any

import pytest
from kotekomi_domain import Assertion, AssertionStatus, AssertionType
from pydantic import ValidationError


def valid_assertion_kwargs() -> dict[str, Any]:
    return {
        "id": "ast_release_review",
        "assertion_type": AssertionType.SOURCE_CLAIM,
        "subject_entity_id": "act_person_a",
        "predicate": "negotiated_release",
        "object_entity_id": "org_lab_a",
        "status": AssertionStatus.REPORTED,
        "source_report_confidence": 0.9,
        "extraction_confidence": 0.8,
        "world_truth_confidence": 0.6,
        "source_ids": ("src_article_a",),
        "evidence_span_ids": ("evs_article_a_release",),
        "provenance_activity_ids": ("prv_human_review",),
        "created_at": datetime(2026, 7, 8, tzinfo=UTC),
        "updated_at": datetime(2026, 7, 8, tzinfo=UTC),
    }


def test_accepts_source_backed_assertion_with_evidence_and_provenance() -> None:
    assertion = Assertion(**valid_assertion_kwargs())

    assert assertion.id == "ast_release_review"
    assert assertion.source_ids == ("src_article_a",)
    assert assertion.evidence_span_ids == ("evs_article_a_release",)


def test_rejects_assertion_without_object_entity_or_object_value() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs.pop("object_entity_id")

    with pytest.raises(ValidationError, match="exactly one object"):
        Assertion(**kwargs)


def test_rejects_assertion_with_object_entity_and_object_value() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["object_value"] = "Model X"

    with pytest.raises(ValidationError, match="exactly one object"):
        Assertion(**kwargs)


def test_rejects_accepted_assertion_without_provenance_activity() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["provenance_activity_ids"] = ()

    with pytest.raises(ValidationError, match="ProvenanceActivity"):
        Assertion(**kwargs)


def test_rejects_source_backed_accepted_assertion_without_evidence_span() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["evidence_span_ids"] = ()

    with pytest.raises(ValidationError, match="EvidenceSpan"):
        Assertion(**kwargs)


def test_allows_proposed_assertion_before_review() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["status"] = AssertionStatus.PROPOSED
    kwargs["source_ids"] = ()
    kwargs["evidence_span_ids"] = ()
    kwargs["provenance_activity_ids"] = ()

    assertion = Assertion(**kwargs)

    assert assertion.status is AssertionStatus.PROPOSED


def test_rejects_causal_inference_without_causal_confidence() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["assertion_type"] = AssertionType.ANALYTIC_INFERENCE
    kwargs["qualifiers"] = {"causal": True}

    with pytest.raises(ValidationError, match="causal_confidence"):
        Assertion(**kwargs)


def test_rejects_unknown_fields() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["unexpected"] = "value"

    with pytest.raises(ValidationError, match="Extra inputs"):
        Assertion(**kwargs)


def test_rejects_bad_id_prefix() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["id"] = "bad_release_review"

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        Assertion(**kwargs)
