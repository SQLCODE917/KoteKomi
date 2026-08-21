"""Unit tests for canonical retrieval-scenario validation."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path

import pytest
from kotekomi_devtools import retrieval_scenarios


def test_exact_anchor_loss_reports_primary_text_fidelity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner blocks source-text loss without rewriting primary-parser output."""

    def query(*_arguments: str) -> dict[str, object]:
        return {
            "status": "complete",
            "authoritative_nodes": [
                {
                    "text": "Anthropic-United States Department of Defense dispute",
                }
            ],
        }

    monkeypatch.setattr(retrieval_scenarios, "_product_json", query)

    with pytest.raises(retrieval_scenarios.RetrievalScenarioError) as raised:
        retrieval_scenarios.validate_ingest_anchors(
            {
                "required_text_anchors": [
                    {
                        "anchor_id": "title",
                        "text": "Anthropic–United States Department of Defense dispute",
                        "match_mode": "exact_substring",
                        "minimum_occurrences": 1,
                    }
                ]
            },
            "rep_test",
            Path("ledger.sqlite"),
        )

    assert raised.value.code == "primary_text_fidelity_failed"
    assert "does not normalize or patch" in str(raised.value)


def test_exact_anchor_validation_uses_exact_retrieval_whitespace_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def query(*_arguments: str) -> dict[str, object]:
        return {
            "status": "complete",
            "authoritative_nodes": [{"text": "Directive  3000.09"}],
        }

    monkeypatch.setattr(retrieval_scenarios, "_product_json", query)

    retrieval_scenarios.validate_ingest_anchors(
        {
            "required_text_anchors": [
                {
                    "anchor_id": "directive-3000-09",
                    "text": "Directive 3000.09",
                    "match_mode": "exact_substring",
                    "minimum_occurrences": 1,
                }
            ]
        },
        "rep_test",
        Path("ledger.sqlite"),
    )


def test_prepare_fresh_scenario_state_replaces_only_prior_scenario_outputs(tmp_path: Path) -> None:
    scenario_root = tmp_path / "retrieval-scenarios" / "fixture" / "digest"
    scenario_root.mkdir(parents=True)
    (scenario_root / "ledger.sqlite").write_text("stale", encoding="utf-8")
    (scenario_root / "ingest-receipt.json").write_text("stale", encoding="utf-8")

    retrieval_scenarios._prepare_fresh_scenario_state(scenario_root)

    assert scenario_root.is_dir()
    assert tuple(scenario_root.iterdir()) == ()


def test_query_case_requires_the_selected_node_authoritative_section_path() -> None:
    case = {
        "query_id": "wrong-section",
        "required_channels": ["lexical"],
        "expected_hits": [
            {
                "anchor_text": "preliminary injunction",
                "section_path_suffix": ["Lawsuits"],
                "maximum_rank": 1,
                "must_be_unique_exact": False,
                "expected_node_types": ["list_item"],
            }
        ],
        "context_expectations": {
            "required_anchor_texts": ["preliminary injunction"],
            "forbidden_projection_kinds": [],
        },
    }
    query = {
        "status": "complete",
        "context_manifest_id": "ctx_test",
        "context_manifest_rendered_input": "preliminary injunction Lawsuits",
        "hits": [
            {
                "authoritative_node_ids": ["nod_test"],
                "final_rank": 1,
                "channel_observations": [{"channel": "lexical"}],
            }
        ],
        "authoritative_nodes": [
            {
                "node_id": "nod_test",
                "node_type": "list_item",
                "section_path": ["References"],
                "text": "ORDER GRANTING MOTION FOR PRELIMINARY INJUNCTION",
            }
        ],
    }

    with pytest.raises(retrieval_scenarios.RetrievalScenarioError, match="Missing expected anchor"):
        retrieval_scenarios._validate_query_case(case, query)


def test_dr3_cumulative_scenario_assets_validate() -> None:
    suite = retrieval_scenarios._load_validated(
        retrieval_scenarios.REPOSITORY_ROOT
        / ".agent/scenarios/anthropic-dod-dispute-v1/suites/dr-3-v1.json",
        "retrieval-query-suite-v3.schema.json",
        "query_suite_invalid",
    )

    cases = retrieval_scenarios._load_cases(suite)

    dr3_cases = [case for case in cases if case["schema_version"] == "retrieval-query-case-v3"]
    assert [case["query_id"] for case in dr3_cases] == [
        "dr3-unique-directive",
        "dr3-nonunique-fascsa",
    ]
