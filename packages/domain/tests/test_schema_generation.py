from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator
from kotekomi_domain.schemas import DOMAIN_SCHEMA_MODELS, schema_for


def test_all_domain_models_have_json_schema() -> None:
    schema_names = set(DOMAIN_SCHEMA_MODELS)

    assert "assertion.schema.json" in schema_names
    assert "proposed_change.schema.json" in schema_names
    assert "evidence_span.schema.json" in schema_names


def test_assertion_sample_validates_against_json_schema() -> None:
    schema = schema_for(DOMAIN_SCHEMA_MODELS["assertion.schema.json"])
    sample = {
        "id": "ast_release_review",
        "assertion_type": "source_claim",
        "subject_entity_id": "act_person_a",
        "predicate": "negotiated_release",
        "object_entity_id": "org_lab_a",
        "status": "reported",
        "source_report_confidence": 0.9,
        "extraction_confidence": 0.8,
        "world_truth_confidence": 0.6,
        "source_ids": ["src_article_a"],
        "evidence_span_ids": ["evs_article_a_release"],
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
