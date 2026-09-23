import pytest
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    EvidenceGraphDimension,
    EvidenceGraphDimensionName,
    EvidenceGraphDimensionValue,
    ProposedChange,
    ReviewStatus,
)
from pydantic import ValidationError


def test_argument_edge_accepts_controlled_relation() -> None:
    edge = ArgumentEdge(
        id="arg_supporting_quote",
        from_assertion_id="ast_quote_a",
        to_assertion_id="ast_claim_a",
        relation=ArgumentEdgeRelation.SUPPORTS,
        rationale="The quote repeats the claim.",
        confidence=0.7,
    )

    assert edge.relation is ArgumentEdgeRelation.SUPPORTS


def _support_dimension(value: EvidenceGraphDimensionValue) -> EvidenceGraphDimension:
    return EvidenceGraphDimension(
        dimension_id="egd_test_support",
        projection_manifest_id="egm_test_support",
        relationship_id="rel_test_support",
        name=EvidenceGraphDimensionName.SUPPORT,
        value=value,
        policy_id="policy_test_support",
        input_ids=("ast_test_support",),
    )


def test_evidence_graph_dimension_accepts_support_present() -> None:
    dimension = _support_dimension(EvidenceGraphDimensionValue.PRESENT)

    assert dimension.name is EvidenceGraphDimensionName.SUPPORT
    assert dimension.value is EvidenceGraphDimensionValue.PRESENT


def test_evidence_graph_dimension_accepts_support_absent() -> None:
    dimension = _support_dimension(EvidenceGraphDimensionValue.ABSENT)

    assert dimension.value is EvidenceGraphDimensionValue.ABSENT


def test_evidence_graph_dimension_rejects_support_unknown() -> None:
    with pytest.raises(ValidationError, match="does not match its name"):
        _support_dimension(EvidenceGraphDimensionValue.UNKNOWN)


def test_argument_edge_rejects_unknown_relation() -> None:
    with pytest.raises(ValidationError):
        ArgumentEdge.model_validate(
            {
                "id": "arg_supporting_quote",
                "from_assertion_id": "ast_quote_a",
                "to_assertion_id": "ast_claim_a",
                "relation": "confirms",
                "rationale": "The quote repeats the claim.",
                "confidence": 0.7,
            }
        )


def test_proposed_change_defaults_to_pending() -> None:
    change = ProposedChange(
        id="pcg_model_output_a",
        proposed_json={"kind": "Assertion", "id": "ast_claim_a"},
    )

    assert change.review_status is ReviewStatus.PENDING


def test_edited_proposed_change_stores_original_and_accepted_json() -> None:
    change = ProposedChange(
        id="pcg_model_output_a",
        review_status=ReviewStatus.EDITED,
        proposed_json={"kind": "Assertion", "id": "ast_claim_a"},
        original_proposed_json={"kind": "Assertion", "id": "ast_claim_a"},
        accepted_json={"kind": "Assertion", "id": "ast_claim_a_edited"},
    )

    assert change.accepted_json == {"kind": "Assertion", "id": "ast_claim_a_edited"}


def test_edited_proposed_change_rejects_missing_original_json() -> None:
    with pytest.raises(ValidationError, match="original proposed JSON"):
        ProposedChange(
            id="pcg_model_output_a",
            review_status=ReviewStatus.EDITED,
            proposed_json={"kind": "Assertion", "id": "ast_claim_a"},
            accepted_json={"kind": "Assertion", "id": "ast_claim_a_edited"},
        )
