"""Verify DR-7 Cross-plane orchestration with the locked deposited PDF."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_application import verify_context_manifest
from verify_dr5_canonical import (
    ROOT,
    ConformanceError,
    command_json,
    config_text,
    fixture_path,
    read_json,
    run_command,
    seed_ledger,
)

type JsonObject = dict[str, Any]


class VerificationTokenizer:
    tokenizer_id = "retrieval_validation_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def run() -> JsonObject:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    seed = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/ledger-seed-v1.json")
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr7-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        config_path = root / "kotekomi.toml"
        config_path.write_text(config_text(ledger_path, root / "archive"), encoding="utf-8")
        run_command("--config", str(config_path), "ledger", "init")
        ingest = command_json(
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(fixture),
            "--source-url",
            str(cast(JsonObject, scenario["source"])["normalized_url"]),
            "--format",
            "json",
        )
        representation_id = _required(ingest, "representation_id")
        seed_ledger(ledger_path, representation_id, seed)
        first = _query(ledger_path)
        _validate(first, ledger_path)
        ledger_path.with_suffix(".retrieval.sqlite").unlink()
        ledger_path.with_suffix(".knowledge-graph.sqlite").unlink()
        rebuilt = _query(ledger_path)
        _validate(rebuilt, ledger_path)
        if (
            first["selected_record_ids"] != rebuilt["selected_record_ids"]
            or first["terminal_evidence_target_ids"] != rebuilt["terminal_evidence_target_ids"]
        ):
            raise ConformanceError(
                "cross_plane_rebuild_mismatch", "Rebuilt projections changed Cross-plane selection."
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "cross_plane_query_id": first["cross_plane_query_id"],
            "selected_record_ids": first["selected_record_ids"],
            "terminal_evidence_target_ids": first["terminal_evidence_target_ids"],
        }


def _query(ledger_path: Path) -> JsonObject:
    return command_json(
        "retrieval",
        "query-cross-plane",
        "--ledger-path",
        str(ledger_path),
        "--query",
        "Anthropic",
        "--format",
        "json",
    )


def _validate(result: JsonObject, ledger_path: Path) -> None:
    if result.get("status") != "complete":
        raise ConformanceError("cross_plane_query_failed", str(result.get("failure")))
    phases = [item["phase"] for item in cast(list[JsonObject], result["transitions"])]
    if phases != ["ledger_discovery", "graph_expansion", "document_evidence", "context_planning"]:
        raise ConformanceError(
            "cross_plane_transition_invalid", "Cross-plane transition order changed."
        )
    selected = set(cast(list[str], result["selected_record_ids"]))
    if not {"rel_anthropic_policy", "out_policy_requirement"}.issubset(selected):
        raise ConformanceError(
            "cross_plane_graph_missing", "Cross-plane query missed Graph-selected records."
        )
    if result["terminal_evidence_target_ids"] != ["etg_directive"]:
        raise ConformanceError(
            "cross_plane_evidence_invalid", "Cross-plane query did not retain terminal evidence."
        )
    contexts = cast(list[JsonObject], result["context_results"])
    if not contexts or any(item["status"] != "ready" for item in contexts):
        raise ConformanceError(
            "cross_plane_context_missing", "Cross-plane query has no ready source context."
        )
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for context in contexts:
            manifest_id = context.get("context_manifest_id")
            if not isinstance(manifest_id, str):
                raise ConformanceError(
                    "cross_plane_context_missing", "ContextManifest ID is missing."
                )
            verify_context_manifest(
                manifest_id,
                ledger,
                VerificationTokenizer(),
                b"Use only the supplied original source evidence.",
                b'{"type":"object"}',
            )


def _required(value: JsonObject, key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ConformanceError("cross_plane_ingest_invalid", f"Missing string field: {key}")
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
