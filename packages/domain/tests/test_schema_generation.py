from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator
from kotekomi_domain.schemas import DOMAIN_SCHEMA_MODELS, schema_for


def test_all_domain_models_have_json_schema() -> None:
    schema_names = set(DOMAIN_SCHEMA_MODELS)

    assert "assertion.schema.json" in schema_names
    assert "proposed_change.schema.json" in schema_names
    assert "evidence_target.schema.json" in schema_names
    assert "briefing.schema.json" in schema_names


def test_assertion_sample_validates_against_json_schema() -> None:
    schema = schema_for(DOMAIN_SCHEMA_MODELS["assertion.schema.json"])
    sample = {
        "id": "ast_release_review",
        "assertion_type": "source_claim",
        "epistemic_scope": "source_report",
        "subject_entity_id": "act_person_a",
        "predicate": "negotiated_release",
        "object_entity_id": "org_lab_a",
        "status": "reported",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_report_confidence": 0.9,
        "extraction_confidence": 0.8,
        "world_truth_confidence": 0.6,
        "source_ids": ["src_article_a"],
        "evidence_target_ids": ["evt_article_a_release"],
        "provenance_activity_ids": ["prv_human_review"],
        "created_at": datetime(2026, 7, 8, tzinfo=UTC).isoformat(),
        "updated_at": datetime(2026, 7, 8, tzinfo=UTC).isoformat(),
    }

    validator: Any = Draft202012Validator(schema)
    validator.validate(sample)


def test_proposed_change_sample_validates_against_json_schema() -> None:
    schema = schema_for(DOMAIN_SCHEMA_MODELS["proposed_change.schema.json"])
    sample = {
        "id": "pcg_model_output_a",
        "review_status": "pending",
        "proposed_json": {"kind": "Assertion", "id": "ast_release_review"},
        "document_id": "doc_article_a",
        "model_name": "local-extraction-model",
        "prompt_id": "propose_assertions",
        "created_at": datetime(2026, 7, 8, tzinfo=UTC).isoformat(),
        "updated_at": datetime(2026, 7, 8, tzinfo=UTC).isoformat(),
    }

    validator: Any = Draft202012Validator(schema)
    validator.validate(sample)


def test_briefing_sample_validates_against_json_schema() -> None:
    schema = schema_for(DOMAIN_SCHEMA_MODELS["briefing.schema.json"])
    sample = {
        "id": "brf_daily",
        "title": "Daily Briefing",
        "previous_briefing_id": None,
        "entity_ids": ["ent_actor_a"],
        "actor_ids": ["act_person_a"],
        "organization_ids": ["org_lab_a"],
        "place_ids": ["plc_event_hall"],
        "event_ids": ["evt_model_forum"],
        "document_ids": ["doc_article_a"],
        "assertion_ids": ["ast_release_review"],
        "relationship_ids": ["rel_person_a_lab_a"],
        "argument_edge_ids": ["arg_release_support"],
        "outcome_ids": ["out_release_review"],
        "source_ids": ["src_article_a"],
        "evidence_target_ids": ["evt_article_a_release"],
        "analytic_inference_assertion_ids": ["ast_release_review"],
        "provenance_activity_id": "prv_human_review",
        "markdown_path": "briefings/daily/brf_daily.md",
        "generated_at": datetime(2026, 7, 8, tzinfo=UTC).isoformat(),
    }

    validator: Any = Draft202012Validator(schema)
    validator.validate(sample)
