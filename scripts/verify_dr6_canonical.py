"""Verify DR-6 graph traversal with the locked deposited PDF."""

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
    validate_json,
)

type JsonObject = dict[str, Any]

SUITE_SCHEMA_PATH = ROOT / ".agent/schemas/knowledge-graph-retrieval-suite-v1.schema.json"
QUERY_CASE_SCHEMA_PATH = ROOT / ".agent/schemas/knowledge-graph-retrieval-query-case-v1.schema.json"


class VerificationTokenizer:
    tokenizer_id = "retrieval_validation_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def run() -> JsonObject:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    seed = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/ledger-seed-v1.json")
    suite = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/suites/dr-6-v1.json")
    validate_json(suite, SUITE_SCHEMA_PATH, "graph_suite_schema_invalid")
    cases = _query_cases(suite)
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr6-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(config_text(ledger_path, archive_path), encoding="utf-8")
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
        seed_ledger(ledger_path, representation_id, seed)
        build = command_json(
            "retrieval", "build-graph", "--ledger-path", str(ledger_path), "--format", "json"
        )
        _complete(build, "graph_build_failed")
        results = {str(case["query_id"]): _query(ledger_path, case) for case in cases}
        for case in cases:
            result = results[str(case["query_id"])]
            _validate_graph_result(result, case)
            _verify_contexts(ledger_path, cast(list[JsonObject], result["context_results"]))
        rebuilt = command_json(
            "retrieval",
            "build-graph",
            "--ledger-path",
            str(ledger_path),
            "--rebuild",
            "--format",
            "json",
        )
        _complete(rebuilt, "graph_rebuild_failed")
        first_case = cases[0]
        repeated = _query(ledger_path, first_case)
        if (
            repeated["selected_record_ids"]
            != results[str(first_case["query_id"])]["selected_record_ids"]
        ):
            raise ConformanceError(
                "graph_rebuild_mismatch", "Rebuilt graph changed traversal selections."
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "index_manifest_id": build["index_manifest_id"],
            "query_record_ids": {
                query_id: result["retrieval_query_id"] for query_id, result in results.items()
            },
        }


def _query(ledger_path: Path, case: JsonObject) -> JsonObject:
    result = command_json(
        "retrieval",
        "query-graph",
        "--ledger-path",
        str(ledger_path),
        "--seed",
        str(case["seed_text"]),
        "--maximum-hops",
        str(case["maximum_hops"]),
        "--maximum-hits",
        "5",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(result, "graph_query_failed")
    return result


def _validate_graph_result(result: JsonObject, case: JsonObject) -> None:
    candidates = cast(list[JsonObject], result["seed_candidates"])
    if len(candidates) != 1:
        raise ConformanceError(
            "graph_seed_resolution_failed", f"Seed did not resolve: {case['seed_text']}"
        )
    selected = set(cast(list[str], result["selected_record_ids"]))
    required = set(cast(list[str], case["required_selected_record_ids"]))
    if not required.issubset(selected):
        raise ConformanceError(
            "graph_path_missing", "Graph traversal did not select the expected accepted records."
        )
    for hit in cast(list[JsonObject], result["hits"]):
        path = cast(JsonObject, hit["traversal_path"])
        if not path["edge_ids"] or not hit["terminal_evidence_target_ids"]:
            raise ConformanceError(
                "graph_provenance_missing", "Graph hit omitted its path or terminal evidence."
            )
    contexts = cast(list[JsonObject], result["context_results"])
    if not contexts or any(item["status"] != "ready" for item in contexts):
        raise ConformanceError(
            "graph_context_missing", "Graph traversal did not create ready source context."
        )


def _verify_contexts(ledger_path: Path, contexts: list[JsonObject]) -> None:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for context in contexts:
            manifest_id = context.get("context_manifest_id")
            if not isinstance(manifest_id, str):
                raise ConformanceError("graph_context_missing", "ContextManifest ID is missing.")
            verify_context_manifest(
                manifest_id,
                ledger,
                VerificationTokenizer(),
                b"Use only the supplied original source evidence.",
                b'{"type":"object"}',
            )


def _complete(payload: JsonObject, code: str) -> None:
    if payload.get("status") != "complete":
        raise ConformanceError(code, str(payload.get("failure")))


def _query_cases(suite: JsonObject) -> tuple[JsonObject, ...]:
    cases: list[JsonObject] = []
    for relative_path in cast(list[str], suite["query_pack_paths"]):
        for line in (ROOT / relative_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = cast(JsonObject, json.loads(line))
                validate_json(case, QUERY_CASE_SCHEMA_PATH, "graph_query_case_schema_invalid")
                cases.append(case)
    return tuple(cases)


def _required(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ConformanceError("graph_public_command_invalid", f"Missing string field: {key}")
    return value


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
