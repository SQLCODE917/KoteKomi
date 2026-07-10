import json
from pathlib import Path
from typing import cast

import pytest
from kotekomi_application import (
    model_proposal_batch_json_schema,
    parse_model_proposal_batch_json,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)


def test_model_proposal_batch_schema_dispatches_every_supported_record_type() -> None:
    schema = model_proposal_batch_json_schema()
    definitions = cast(dict[str, object], schema["$defs"])

    assert {
        "_ActorProposal",
        "_ArgumentEdgeProposal",
        "_AssertionProposal",
        "_EventProposal",
        "_EvidenceSpanProposal",
        "_OrganizationProposal",
        "_OutcomeProposal",
        "_RelationshipProposal",
    }.issubset(definitions)


def test_parse_model_proposal_batch_uses_domain_records_as_boundary_contract() -> None:
    proposals = parse_model_proposal_batch_json(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(proposals) == 16
    assert proposals[0].record_type == "Organization"
    assert proposals[0].record["id"] == "org_anthropic"


def test_parse_model_proposal_batch_rejects_unsupported_record_type() -> None:
    payload = json.dumps(
        {
            "proposals": [
                {
                    "record_type": "Place",
                    "stable_label": "washington",
                    "record": {"id": "plc_washington", "name": "Washington"},
                    "evidence": {
                        "selector_type": "exact_text",
                        "exact_text": "Washington",
                        "source_id": "src_article_a",
                        "document_id": "doc_article_a",
                    },
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="Input tag 'Place'"):
        parse_model_proposal_batch_json(payload)
