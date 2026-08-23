"""Verify automatic retrieval projection readiness with the locked deposited PDF."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, cast

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


def run() -> JsonObject:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    seed = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/ledger-seed-v1.json")
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-projection-readiness-") as temporary:
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
            str(cast(JsonObject, scenario["source"])["normalized_url"]),
            "--format",
            "json",
        )
        representation_id = _required(ingest, "representation_id")
        document = _document_query(ledger_path, representation_id)
        seed_ledger(ledger_path, representation_id, seed)
        ledger = _ledger_query(ledger_path)
        graph = _graph_query(ledger_path)
        evidence = _evidence_graph_explanation(ledger_path)
        first = {
            "document_nodes": document["selected_node_ids"],
            "ledger_records": ledger["selected_record_ids"],
            "graph_records": graph["selected_record_ids"],
            "evidence_targets": _evidence_target_ids(evidence),
        }
        _delete_sidecars(ledger_path)
        repeated = {
            "document_nodes": _document_query(ledger_path, representation_id)["selected_node_ids"],
            "ledger_records": _ledger_query(ledger_path)["selected_record_ids"],
            "graph_records": _graph_query(ledger_path)["selected_record_ids"],
            "evidence_targets": _evidence_target_ids(_evidence_graph_explanation(ledger_path)),
        }
        if repeated != first:
            raise ConformanceError(
                "projection_rebuild_mismatch",
                "Automatic projection rebuild changed canonical retrieval selections.",
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "document_index_manifest_ids": document["index_manifest_ids"],
            "ledger_index_manifest_id": ledger["index_manifest_id"],
            "graph_index_manifest_id": graph["index_manifest_id"],
            "evidence_projection_manifest_id": evidence["projection_manifest_id"],
            "selections": first,
        }


def _document_query(ledger_path: Path, representation_id: str) -> JsonObject:
    result = command_json(
        "retrieval",
        "query",
        "--ledger-path",
        str(ledger_path),
        "--representation-id",
        representation_id,
        "--query",
        "Directive 3000.09",
        "--maximum-hits",
        "3",
        "--context-profile",
        "retrieval-validation-v1",
        "--channel",
        "exact-lexical",
        "--format",
        "json",
    )
    _complete(result, "document_readiness_failed")
    if not result["selected_node_ids"] or not result["context_manifest_id"]:
        raise ConformanceError(
            "document_context_missing", "Document query omitted authoritative context."
        )
    return result


def _ledger_query(ledger_path: Path) -> JsonObject:
    result = command_json(
        "retrieval",
        "query-ledger",
        "--ledger-path",
        str(ledger_path),
        "--query",
        "Directive 3000.09",
        "--policy",
        "current-relevance",
        "--maximum-hits",
        "5",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(result, "ledger_readiness_failed")
    if "ast_directive_current" not in result["selected_record_ids"]:
        raise ConformanceError(
            "ledger_selection_missing", "Ledger query omitted the current Assertion."
        )
    return result


def _graph_query(ledger_path: Path) -> JsonObject:
    result = command_json(
        "retrieval",
        "query-graph",
        "--ledger-path",
        str(ledger_path),
        "--seed",
        "Anthropic",
        "--maximum-hops",
        "2",
        "--maximum-hits",
        "5",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(result, "graph_readiness_failed")
    if "rel_anthropic_policy" not in result["selected_record_ids"]:
        raise ConformanceError(
            "graph_selection_missing", "Graph query omitted the expected Relationship."
        )
    return result


def _evidence_graph_explanation(ledger_path: Path) -> JsonObject:
    result = command_json(
        "retrieval",
        "explain-graph-relationship",
        "--ledger-path",
        str(ledger_path),
        "--relationship-id",
        "rel_anthropic_policy",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(result, "evidence_graph_readiness_failed")
    if not _evidence_target_ids(result):
        raise ConformanceError(
            "evidence_graph_selection_missing",
            "Evidence graph explanation omitted EvidenceTargets.",
        )
    return result


def _evidence_target_ids(result: JsonObject) -> list[str]:
    contributions = cast(list[JsonObject], result["contributions"])
    return sorted(
        {
            target_id
            for item in contributions
            for target_id in cast(list[str], item["evidence_target_ids"])
        }
    )


def _delete_sidecars(ledger_path: Path) -> None:
    for path in (
        ledger_path.with_suffix(".retrieval.sqlite"),
        ledger_path.with_suffix(".knowledge-graph.sqlite"),
    ):
        path.unlink(missing_ok=True)


def _complete(result: JsonObject, code: str) -> None:
    if result.get("status") != "complete":
        raise ConformanceError(code, str(result.get("failure")))


def _required(result: JsonObject, key: str) -> str:
    value = result.get(key)
    if not isinstance(value, str):
        raise ConformanceError("public_command_invalid", f"Missing string field: {key}")
    return value


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
