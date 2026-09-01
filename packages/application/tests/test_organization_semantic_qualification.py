from __future__ import annotations

import hashlib

import pytest
from kotekomi_application.organization_mention_boundary_reconciliation import (
    reconcile_organization_mention_boundaries,
)
from kotekomi_application.organization_mention_qualification import (
    MentionProposalObservation,
    fuse_mention_proposals,
)
from kotekomi_application.organization_semantic_qualification import (
    ContextualOrganizationTypeEvidence,
    GoldOrganizationSpan,
    OrganizationQualificationEligibility,
    OrganizationQualificationExecutionStatus,
    OrganizationQualificationJudgment,
    build_organization_qualification_decision,
    classify_qualification_candidate,
    map_contextual_type_evidence,
    parse_organization_qualification_output,
    qualification_candidates_from_reconciliation,
)


def _candidate_values(source: str):
    observations = (
        MentionProposalObservation("qwen", "Northstar", 0, 9, model_run_id="mrn_1"),
        MentionProposalObservation("gliner", "Northstar", 0, 9, score=0.91),
        MentionProposalObservation("gliner", "Northstar's", 0, 11, score=0.72),
    )
    candidates = fuse_mention_proposals(source, "src_1", observations)
    reconciliation = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="src_1",
        candidates=candidates,
    )
    return candidates, reconciliation


def _type_evidence(**overrides: object) -> ContextualOrganizationTypeEvidence:
    values: dict[str, object] = {
        "candidate_id": "mnc_1",
        "returned_text": "Northstar",
        "start": 0,
        "end": 9,
        "coarse_type": "MENTION",
        "coarse_mention_type": "ORG",
        "predicted_entity": None,
        "entity_linking_score": None,
        "top_k_entities": (),
        "predicted_entity_types": (),
        "failed_class_check": None,
    }
    values.update(overrides)
    return ContextualOrganizationTypeEvidence(**values)  # type: ignore[arg-type]


def test_reconciliation_candidates_preserve_every_boundary_and_lineage() -> None:
    source = "Northstar's technology reached customers."
    candidates, reconciliation = _candidate_values(source)

    qualified = qualification_candidates_from_reconciliation(
        source_text=source,
        candidates=candidates,
        reconciliation=reconciliation,
    )

    assert [(item.text, item.start, item.end) for item in qualified] == [
        ("Northstar", 0, 9),
        ("Northstar's", 0, 11),
    ]
    assert {item.boundary_status.value for item in qualified} == {"resolved"}
    assert {item.boundary_rule_id for item in qualified} == {"terminal_possessive_suffix_v1"}
    assert all(item.boundary_decision_id == reconciliation.decisions[0].id for item in qualified)


def test_candidate_catalog_rejects_source_drift() -> None:
    source = "Northstar's technology reached customers."
    candidates, reconciliation = _candidate_values(source)

    with pytest.raises(ValueError, match="source digest"):
        qualification_candidates_from_reconciliation(
            source_text=source + " Drift",
            candidates=candidates,
            reconciliation=reconciliation,
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("organization", OrganizationQualificationJudgment.ORGANIZATION),
        ("not_organization", OrganizationQualificationJudgment.NOT_ORGANIZATION),
        ("ambiguous", OrganizationQualificationJudgment.AMBIGUOUS),
    ],
)
def test_qwen_output_contract_is_exact(
    raw: str, expected: OrganizationQualificationJudgment
) -> None:
    assert parse_organization_qualification_output(raw) is expected


@pytest.mark.parametrize("raw", ["organization\n", " organization", "ORG", "", "ambiguous\nwhy"])
def test_qwen_output_contract_rejects_every_other_shape(raw: str) -> None:
    with pytest.raises(ValueError, match="exactly one qualification literal"):
        parse_organization_qualification_output(raw)


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (_type_evidence(coarse_mention_type="ORG"), OrganizationQualificationJudgment.ORGANIZATION),
        (
            _type_evidence(coarse_mention_type="PERSON"),
            OrganizationQualificationJudgment.NOT_ORGANIZATION,
        ),
        (_type_evidence(coarse_mention_type=None), OrganizationQualificationJudgment.AMBIGUOUS),
        (
            _type_evidence(coarse_mention_type="ORG", failed_class_check=True),
            OrganizationQualificationJudgment.AMBIGUOUS,
        ),
    ],
)
def test_refined_mapping_is_explicit(
    evidence: ContextualOrganizationTypeEvidence,
    expected: OrganizationQualificationJudgment,
) -> None:
    assert map_contextual_type_evidence(evidence) is expected


def test_decision_cannot_change_candidate_boundary() -> None:
    source = "Northstar's technology reached customers."
    candidates, reconciliation = _candidate_values(source)
    qualification_candidate = qualification_candidates_from_reconciliation(
        source_text=source,
        candidates=candidates,
        reconciliation=reconciliation,
    )[0]

    decision = build_organization_qualification_decision(
        candidate=qualification_candidate,
        producer_id="refined-v1",
        judgment=OrganizationQualificationJudgment.ORGANIZATION,
        execution_status=OrganizationQualificationExecutionStatus.COMPLETED,
        evidence_record_id="oqe_1",
        execution_record_ids=("rfx_1",),
        terminal_trace_id="xst_0123456789abcdef01234567",
        mapping_policy_id="refined_coarse_mention_type_v1",
    )

    assert decision.candidate_id == qualification_candidate.id
    assert decision.candidate_text == "Northstar"
    assert (decision.candidate_start, decision.candidate_end) == (0, 9)
    assert decision.source_text_sha256 == hashlib.sha256(source.encode()).hexdigest()


def test_noncompleted_decision_has_no_semantic_judgment() -> None:
    source = "Northstar's technology reached customers."
    candidates, reconciliation = _candidate_values(source)
    qualification_candidate = qualification_candidates_from_reconciliation(
        source_text=source,
        candidates=candidates,
        reconciliation=reconciliation,
    )[0]

    with pytest.raises(ValueError, match="cannot carry a semantic judgment"):
        build_organization_qualification_decision(
            candidate=qualification_candidate,
            producer_id="qwen",
            judgment=OrganizationQualificationJudgment.ORGANIZATION,
            execution_status=OrganizationQualificationExecutionStatus.INVALID_OUTPUT,
            evidence_record_id="oqe_2",
            execution_record_ids=("mrn_2",),
            terminal_trace_id="xst_0123456789abcdef01234567",
            mapping_policy_id="qwen_qualification_v2",
            diagnostics=("invalid_output",),
        )


@pytest.mark.parametrize(
    ("gold_spans", "expected_eligibility", "expected_judgment"),
    [
        (
            (GoldOrganizationSpan("Northstar", 0, 9),),
            OrganizationQualificationEligibility.EXACT_GOLD,
            OrganizationQualificationJudgment.ORGANIZATION,
        ),
        (
            (GoldOrganizationSpan("customers", 31, 40),),
            OrganizationQualificationEligibility.DISJOINT_GOLD,
            OrganizationQualificationJudgment.NOT_ORGANIZATION,
        ),
        (
            (GoldOrganizationSpan("Northstar's", 0, 11),),
            OrganizationQualificationEligibility.BOUNDARY_CASE,
            None,
        ),
    ],
)
def test_gold_classification_separates_semantics_from_boundary_errors(
    gold_spans: tuple[GoldOrganizationSpan, ...],
    expected_eligibility: OrganizationQualificationEligibility,
    expected_judgment: OrganizationQualificationJudgment | None,
) -> None:
    source = "Northstar's technology reached customers."
    candidates, reconciliation = _candidate_values(source)
    candidate = qualification_candidates_from_reconciliation(
        source_text=source,
        candidates=candidates,
        reconciliation=reconciliation,
    )[0]

    classification = classify_qualification_candidate(candidate, gold_spans)

    assert classification.eligibility is expected_eligibility
    assert classification.expected_judgment is expected_judgment
