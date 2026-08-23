"""Verify DR-6.1A evidence graph explanations with the locked deposited PDF."""

from __future__ import annotations

import json
import re
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

SUITE_SCHEMA_PATH = ROOT / ".agent/schemas/evidence-graph-query-suite-v1.schema.json"
QUERY_CASE_SCHEMA_PATH = ROOT / ".agent/schemas/evidence-graph-query-case-v1.schema.json"
PROMPT_BYTES = b"Use only the supplied original source evidence."
SCHEMA_BYTES = b'{"type":"object"}'


class VerificationTokenizer:
    tokenizer_id = "retrieval_validation_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def run() -> JsonObject:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    suite = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/suites/dr-6-1a-v1.json")
    validate_json(suite, SUITE_SCHEMA_PATH, "evidence_graph_suite_schema_invalid")
    seed = read_json(ROOT / str(suite["seed_path"]))
    cases = _query_cases(suite)
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr6-1-") as temporary:
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
        _complete(
            command_json(
                "retrieval", "build-graph", "--ledger-path", str(ledger_path), "--format", "json"
            ),
            "graph_build_failed",
        )
        _complete(
            command_json(
                "retrieval",
                "build-graph-evidence",
                "--ledger-path",
                str(ledger_path),
                "--format",
                "json",
            ),
            "evidence_graph_build_failed",
        )
        results = {str(case["query_id"]): _explain_case(ledger_path, case) for case in cases}
        rebuilt = command_json(
            "retrieval",
            "build-graph-evidence",
            "--ledger-path",
            str(ledger_path),
            "--rebuild",
            "--format",
            "json",
        )
        _complete(rebuilt, "evidence_graph_rebuild_failed")
        first_case = cases[0]
        repeated = _explain_case(ledger_path, first_case)
        initial = results[str(first_case["query_id"])]
        if (
            initial["edge"] != repeated["edge"]
            or initial["contributions"] != repeated["contributions"]
        ):
            raise ConformanceError(
                "evidence_graph_rebuild_mismatch",
                "Rebuilding the sidecar changed the evidence graph explanation.",
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "projection_manifest_id": rebuilt["projection_manifest_id"],
            "explanation_ids": {
                query_id: result["explanation_id"] for query_id, result in results.items()
            },
        }


def _query_cases(suite: JsonObject) -> tuple[JsonObject, ...]:
    cases: list[JsonObject] = []
    for relative_path in cast(list[str], suite["query_pack_paths"]):
        for line in (ROOT / relative_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = cast(JsonObject, json.loads(line))
                validate_json(case, QUERY_CASE_SCHEMA_PATH, "evidence_graph_case_schema_invalid")
                cases.append(case)
    if not cases:
        raise ConformanceError("evidence_graph_cases_missing", "The suite has no query cases.")
    return tuple(cases)


def _explain_case(ledger_path: Path, case: JsonObject) -> JsonObject:
    graph = command_json(
        "retrieval",
        "query-graph",
        "--ledger-path",
        str(ledger_path),
        "--seed",
        str(case["graph_seed"]),
        "--maximum-hops",
        "2",
        "--maximum-hits",
        "5",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(graph, "graph_query_failed")
    relationship_id = str(case["relationship_id"])
    if relationship_id not in cast(list[str], graph["selected_record_ids"]):
        raise ConformanceError(
            "relationship_not_selected",
            "The public graph query did not select the requested Relationship.",
        )
    explanation = command_json(
        "retrieval",
        "explain-graph-relationship",
        "--ledger-path",
        str(ledger_path),
        "--relationship-id",
        relationship_id,
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(explanation, "evidence_graph_explain_failed")
    edge = cast(JsonObject, explanation["edge"])
    if edge.get("relationship_id") != relationship_id:
        raise ConformanceError(
            "edge_relationship_mismatch", "The explanation returned another Relationship."
        )
    contributions = cast(list[JsonObject], explanation["contributions"])
    if not contributions:
        raise ConformanceError("contribution_missing", "The explanation has no Contributions.")
    terminal_ids = {
        value for item in contributions for value in cast(list[str], item["terminal_assertion_ids"])
    }
    target_ids = {
        value for item in contributions for value in cast(list[str], item["evidence_target_ids"])
    }
    if not set(cast(list[str], case["required_terminal_assertion_ids"])).issubset(terminal_ids):
        raise ConformanceError(
            "terminal_assertion_missing", "The explanation omitted a terminal Assertion."
        )
    if not set(cast(list[str], case["required_evidence_target_ids"])).issubset(target_ids):
        raise ConformanceError(
            "evidence_target_missing", "The explanation omitted required source evidence."
        )
    _verify_contexts(ledger_path, cast(list[JsonObject], explanation["context_results"]))
    return explanation


def _verify_contexts(ledger_path: Path, contexts: list[JsonObject]) -> None:
    if not contexts or any(item.get("status") != "ready" for item in contexts):
        raise ConformanceError(
            "evidence_graph_context_missing", "The explanation has no ready source context."
        )
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for context in contexts:
            manifest_id = context.get("context_manifest_id")
            if not isinstance(manifest_id, str):
                raise ConformanceError(
                    "context_manifest_missing", "The result omitted a ContextManifest ID."
                )
            manifest = verify_context_manifest(
                manifest_id,
                ledger,
                VerificationTokenizer(),
                PROMPT_BYTES,
                SCHEMA_BYTES,
            ).manifest
            if "directive 3000.09" not in _normalize(manifest.rendered_input.decode("utf-8")):
                raise ConformanceError(
                    "context_anchor_missing",
                    "The source ContextManifest omitted the required Directive 3000.09 anchor.",
                )


def _complete(payload: JsonObject, code: str) -> None:
    if payload.get("status") != "complete":
        raise ConformanceError(code, str(payload.get("failure")))


def _required(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ConformanceError("public_command_invalid", f"Missing string field: {key}")
    return value


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
