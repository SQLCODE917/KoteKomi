from datetime import UTC, datetime
from typing import Any

import pytest
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    Outcome,
    ProposedAssertion,
    Relationship,
    SourceAuthority,
)
from pydantic import ValidationError


def valid_assertion_kwargs() -> dict[str, Any]:
    return {
        "id": "ast_release_review",
        "assertion_type": AssertionType.SOURCE_CLAIM,
        "epistemic_scope": EpistemicScope.SOURCE_REPORT,
        "subject_entity_id": "act_person_a",
        "predicate": "negotiated_release",
        "object_entity_id": "org_lab_a",
        "status": AssertionStatus.REPORTED,
        "source_authority": SourceAuthority.SECONDARY,
        "attribution_basis": AttributionBasis.REPORTED_BY_SOURCE,
        "source_report_confidence": 0.9,
        "extraction_confidence": 0.8,
        "world_truth_confidence": 0.6,
        "source_ids": ("src_article_a",),
        "evidence_target_ids": ("etg_article_a_release",),
        "provenance_activity_ids": ("prv_human_review",),
        "created_at": datetime(2026, 7, 8, tzinfo=UTC),
        "updated_at": datetime(2026, 7, 8, tzinfo=UTC),
    }


def test_accepts_source_backed_assertion_with_evidence_and_provenance() -> None:
    assertion = Assertion(**valid_assertion_kwargs())

    assert assertion.id == "ast_release_review"
    assert assertion.epistemic_scope is EpistemicScope.SOURCE_REPORT
    assert assertion.source_authority is SourceAuthority.SECONDARY
    assert assertion.attribution_basis is AttributionBasis.REPORTED_BY_SOURCE
    assert assertion.source_ids == ("src_article_a",)
    assert assertion.evidence_target_ids == ("etg_article_a_release",)


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


def test_rejects_source_backed_accepted_assertion_without_evidence_target() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["evidence_target_ids"] = ()

    with pytest.raises(ValidationError, match="EvidenceTarget"):
        Assertion(**kwargs)


def test_rejects_direct_assertion_without_source_basis_before_review() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["status"] = AssertionStatus.PROPOSED
    kwargs["source_authority"] = SourceAuthority.NOT_APPLICABLE
    kwargs["attribution_basis"] = AttributionBasis.NOT_APPLICABLE
    kwargs["source_ids"] = ()
    kwargs["evidence_target_ids"] = ()
    kwargs["provenance_activity_ids"] = ()

    with pytest.raises(ValidationError, match="Direct Assertion"):
        Assertion(**kwargs)


def test_rejects_missing_epistemic_scope() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs.pop("epistemic_scope")

    with pytest.raises(ValidationError, match="epistemic_scope"):
        Assertion(**kwargs)


def test_accepts_primary_source_attributed_statement_with_authority_evidence() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs.update(
        {
            "assertion_type": AssertionType.DIRECT_QUOTE,
            "epistemic_scope": EpistemicScope.ATTRIBUTED_STATEMENT,
            "source_authority": SourceAuthority.PRIMARY,
            "attribution_basis": AttributionBasis.DIRECT_DOCUMENT,
            "attributed_to_id": "org_lab_a",
            "authority_source_ids": ("src_article_a",),
            "authority_evidence_target_ids": ("etg_article_a_release",),
        }
    )

    assertion = Assertion(**kwargs)

    assert assertion.attributed_to_id == "org_lab_a"
    assert assertion.source_authority is SourceAuthority.PRIMARY


def test_rejects_attributed_statement_without_attributed_entity() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["epistemic_scope"] = EpistemicScope.ATTRIBUTED_STATEMENT

    with pytest.raises(ValidationError, match="attributed_to_id"):
        Assertion(**kwargs)


def test_rejects_primary_source_authority_without_authority_evidence() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["source_authority"] = SourceAuthority.PRIMARY

    with pytest.raises(ValidationError, match="authority evidence"):
        Assertion(**kwargs)


def test_rejects_authority_evidence_outside_assertion_evidence() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs.update(
        {
            "source_authority": SourceAuthority.PRIMARY,
            "authority_source_ids": ("src_other",),
            "authority_evidence_target_ids": ("etg_article_a_release",),
        }
    )

    with pytest.raises(ValidationError, match="authority_source_ids"):
        Assertion(**kwargs)


def test_rejects_analytic_inference_without_matching_epistemic_scope() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["assertion_type"] = AssertionType.ANALYTIC_INFERENCE

    with pytest.raises(ValidationError, match="epistemic_scope"):
        Assertion(**kwargs)


def test_accepts_analytic_inference_with_supporting_assertion() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs.update(
        {
            "assertion_type": AssertionType.ANALYTIC_INFERENCE,
            "epistemic_scope": EpistemicScope.ANALYTIC_INFERENCE,
            "source_authority": SourceAuthority.NOT_APPLICABLE,
            "attribution_basis": AttributionBasis.NOT_APPLICABLE,
            "source_ids": (),
            "evidence_target_ids": (),
            "supporting_assertion_ids": ("ast_source_claim",),
        }
    )

    assertion = Assertion(**kwargs)

    assert assertion.source_authority is SourceAuthority.NOT_APPLICABLE


def test_rejects_analytic_inference_without_supporting_assertion() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs.update(
        {
            "assertion_type": AssertionType.ANALYTIC_INFERENCE,
            "epistemic_scope": EpistemicScope.ANALYTIC_INFERENCE,
            "source_authority": SourceAuthority.NOT_APPLICABLE,
            "attribution_basis": AttributionBasis.NOT_APPLICABLE,
            "source_ids": (),
            "evidence_target_ids": (),
        }
    )

    with pytest.raises(ValidationError, match="supporting Assertions"):
        Assertion(**kwargs)


def test_rejects_relationship_without_an_assertion_basis() -> None:
    with pytest.raises(ValidationError, match="one or more Assertions"):
        Relationship(
            id="rel_anthropic_defense",
            subject_id="org_anthropic",
            predicate="is_subject_to_policy",
            object_id="org_us_department_of_defense",
        )


def test_rejects_outcome_without_an_assertion_basis() -> None:
    with pytest.raises(ValidationError, match="one or more Assertions"):
        Outcome(id="out_policy_requirement", description="A policy requirement exists.")


def test_rejects_causal_inference_without_causal_confidence() -> None:
    kwargs = valid_assertion_kwargs()
    kwargs["assertion_type"] = AssertionType.ANALYTIC_INFERENCE
    kwargs["epistemic_scope"] = EpistemicScope.ANALYTIC_INFERENCE
    kwargs["qualifiers"] = {"causal": True}
    kwargs["source_authority"] = SourceAuthority.NOT_APPLICABLE
    kwargs["attribution_basis"] = AttributionBasis.NOT_APPLICABLE
    kwargs["source_ids"] = ()
    kwargs["evidence_target_ids"] = ()
    kwargs["supporting_assertion_ids"] = ("ast_source_claim",)

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


@pytest.mark.parametrize("predicate", ["is_policy_conflict_with", "reported_2026_event"])
def test_accepts_canonical_assertion_predicate(predicate: str) -> None:
    assertion = Assertion.model_validate(valid_assertion_kwargs() | {"predicate": predicate})

    assert assertion.predicate == predicate


@pytest.mark.parametrize("predicate", ["Policy conflict", "has-policy-conflict", "_starts_bad"])
def test_rejects_noncanonical_assertion_predicate(predicate: str) -> None:
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        Assertion.model_validate(valid_assertion_kwargs() | {"predicate": predicate})


def test_proposed_assertion_retains_relation_label_without_accepted_state_fields() -> None:
    values = valid_assertion_kwargs()
    values.pop("predicate")
    values.pop("status")
    values.pop("provenance_activity_ids")
    values.pop("created_at")
    values.pop("updated_at")
    proposed = ProposedAssertion.model_validate(
        values | {"relation_label": "has a policy conflict with"}
    )

    assert proposed.relation_label == "has a policy conflict with"


def test_proposed_assertion_applies_direct_assertion_evidence_rules() -> None:
    values = valid_assertion_kwargs()
    values.pop("predicate")
    values.pop("status")
    values.pop("provenance_activity_ids")
    values.pop("created_at")
    values.pop("updated_at")
    values["source_ids"] = ()
    values["evidence_target_ids"] = ()
    values["source_authority"] = SourceAuthority.NOT_APPLICABLE
    values["attribution_basis"] = AttributionBasis.NOT_APPLICABLE

    with pytest.raises(ValidationError, match="Direct Assertion"):
        ProposedAssertion.model_validate(values | {"relation_label": "reports a conflict"})
