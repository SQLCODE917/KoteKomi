"""Verify DR-6.1D evidence graph dimensions and Score with the locked deposited PDF."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ArgumentEdge, ArgumentEdgeRelation
from verify_dr5_canonical import command_json, config_text, fixture_path, read_json, run_command
from verify_dr6_1c_canonical import (
    ROOT,
    ConformanceError,
    approve,
    complete,
    seed_temporal_correction,
    verify_contexts,
)

type JsonObject = dict[str, Any]


def run() -> dict[str, Any]:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr6-1d-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        config_path = root / "kotekomi.toml"
        config_path.write_text(config_text(ledger_path, root / "archive"), encoding="utf-8")
        run_command(
            "--config", str(config_path), "ledger", "init", "--ledger-path", str(ledger_path)
        )
        ingest = command_json(
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(fixture),
            "--source-url",
            str(scenario["source"]["normalized_url"]),
            "--format",
            "json",
        )
        representation_id = str(ingest["representation_id"])
        seed = read_json(
            ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/ledger-temporal-seed-v1.json"
        )
        targets = seed_temporal_correction(ledger_path, representation_id, seed)
        with sqlite_ledger_transaction(ledger_path) as ledger:
            approve(
                ledger,
                "pcg_dimension_contradiction",
                ArgumentEdge(
                    id="arg_dimension_contradiction",
                    from_assertion_id="ast_policy_requirement_initial",
                    to_assertion_id="ast_policy_requirement_corrected",
                    relation=ArgumentEdgeRelation.CONTRADICTS,
                    rationale="The earlier policy wording conflicts with the corrected wording.",
                    evidence_target_ids=("etg_policy_directive",),
                    confidence=0.9,
                    created_at=datetime(2026, 8, 21, 9, tzinfo=UTC),
                ),
                datetime(2026, 8, 21, 9, tzinfo=UTC),
            )
        built = command_json(
            "retrieval",
            "build-graph-evidence",
            "--ledger-path",
            str(ledger_path),
            "--format",
            "json",
        )
        complete(built, "dimension_graph_build_failed")
        explanation = command_json(
            "retrieval",
            "explain-graph-relationship",
            "--ledger-path",
            str(ledger_path),
            "--relationship-id",
            "rel_policy_requirement_corrected",
            "--context-profile",
            "retrieval-validation-v1",
            "--format",
            "json",
        )
        complete(explanation, "dimension_graph_explain_failed")
        score_raw = explanation.get("score")
        dimensions_raw = explanation.get("dimensions")
        if not isinstance(score_raw, dict):
            raise ConformanceError(
                "dimension_score_invalid", "Expected a contested evidence Score."
            )
        score = cast(JsonObject, score_raw)
        if score.get("value") != "contested":
            raise ConformanceError(
                "dimension_score_invalid", "Expected a contested evidence Score."
            )
        if not isinstance(dimensions_raw, list):
            raise ConformanceError("dimension_records_missing", "Explanation omitted Dimensions.")
        dimension_items = cast(list[object], dimensions_raw)
        if not all(isinstance(item, dict) for item in dimension_items):
            raise ConformanceError("dimension_records_missing", "Explanation omitted Dimensions.")
        dimensions = tuple(cast(JsonObject, item) for item in dimension_items)
        values = {str(item.get("name")): item.get("value") for item in dimensions}
        if values != {
            "validated_evidence": "present",
            "contradiction": "present",
            "source_lineage": "unknown",
        }:
            raise ConformanceError(
                "dimension_values_invalid", "Explanation returned wrong Dimensions."
            )
        verify_contexts(
            ledger_path,
            explanation["context_results"],
            "all lawful purposes",
            (targets["etg_policy_lawful_purposes"].node_ids[0],),
        )
        rebuilt = command_json(
            "retrieval",
            "build-graph-evidence",
            "--ledger-path",
            str(ledger_path),
            "--rebuild",
            "--format",
            "json",
        )
        complete(rebuilt, "dimension_graph_rebuild_failed")
        repeated = command_json(
            "retrieval",
            "explain-graph-relationship",
            "--ledger-path",
            str(ledger_path),
            "--relationship-id",
            "rel_policy_requirement_corrected",
            "--context-profile",
            "retrieval-validation-v1",
            "--format",
            "json",
        )
        complete(repeated, "dimension_graph_reexplain_failed")
        if repeated.get("score") != score or tuple(repeated.get("dimensions", ())) != dimensions:
            raise ConformanceError(
                "dimension_rebuild_mismatch",
                "Rebuild changed Dimensions or Score.",
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "projection_manifest_id": explanation["projection_manifest_id"],
            "score_id": score["score_id"],
            "score_value": score["value"],
            "dimension_ids": score["dimension_ids"],
        }


if __name__ == "__main__":
    import json

    print(json.dumps(run(), sort_keys=True))
