import pytest
from kotekomi_domain import ArgumentEdge, ArgumentEdgeRelation, ProposedChange, ReviewStatus
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
