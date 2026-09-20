from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentCalibrationDiagnosticOutcome,
    AttachmentMeasurementDecision,
    AttachmentMeasurementRuleAnswer,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentReviewClaimVerdict,
    AttachmentReviewClaimVerification,
    AttachmentSourceRange,
    attachment_pool_edge_id,
)


def test_r1_strict_decision_preserves_a_gold_positive_loss() -> None:
    source, edge = _contained_edge()

    decision = AttachmentMeasurementDecision(
        phase="development",
        edge=edge,
        source_text=source,
        expected_answer="Y",
        rule_answer=AttachmentMeasurementRuleAnswer.REJECT,
        gold_positive_loss=True,
        gold_negative_removal=False,
    )

    assert decision.edge.candidate_range.text == "announced acquisition"
    assert decision.edge.event_range.text == "acquisition"
    assert decision.gold_positive_loss is True


def test_r1_strict_decision_rejects_a_non_source_exact_range() -> None:
    source, edge = _contained_edge()

    with pytest.raises(ValueError, match="source digest"):
        AttachmentMeasurementDecision(
            phase="development",
            edge=edge,
            source_text=source.replace("acquisition", "purchase"),
            expected_answer="Y",
            rule_answer=AttachmentMeasurementRuleAnswer.REJECT,
            gold_positive_loss=True,
            gold_negative_removal=False,
        )


def test_calibration_outcomes_distinguish_ranking_from_separability() -> None:
    assert tuple(item.value for item in AttachmentCalibrationDiagnosticOutcome) == (
        "calibratable",
        "ranking_unstable",
        "not_separable",
        "inconclusive",
    )


def test_material_review_claim_requires_evidence() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        AttachmentReviewClaimVerification(
            claim_id="unsafe_rule",
            claim_text="R1-strict is unsafe.",
            verdict=AttachmentReviewClaimVerdict.CONFIRMED,
            evidence=(),
            rationale="The audit records Gold-positive losses.",
        )


def _contained_edge() -> tuple[str, AttachmentPoolEdge]:
    source = "Acme announced acquisition."
    digest = hashlib.sha256(source.encode()).hexdigest()
    values = {
        "phase": "development",
        "source_segment_id": "seg_fixture",
        "source_text_sha256": digest,
        "candidate_id": "cac_" + "1" * 24,
        "source_grounded_event_id": "sge_" + "2" * 24,
        "candidate_start": 5,
        "candidate_end": 26,
        "event_start": 15,
        "event_end": 26,
    }
    return source, AttachmentPoolEdge(
        id=attachment_pool_edge_id(**values),
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id="cac_" + "1" * 24,
        source_grounded_event_id="sge_" + "2" * 24,
        candidate_range=AttachmentSourceRange(
            start=5,
            end=26,
            text="announced acquisition",
        ),
        event_range=AttachmentSourceRange(start=15, end=26, text="acquisition"),
        origins=(AttachmentProposalOrigin.QWEN,),
        syntax_arms=(),
    )
