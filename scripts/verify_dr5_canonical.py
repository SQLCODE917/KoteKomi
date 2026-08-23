"""Verify DR-5 with a locked deposited PDF and declarative Ledger seed."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_application import ReviewProposedChangeInput, approve_proposed_change
from kotekomi_domain import (
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ProposedChange,
    ReviewStatus,
    canonical_evidence_target_digest,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json"
SUITE_PATH = ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/suites/dr-5-v1.json"
SEED_SCHEMA_PATH = ROOT / ".agent/schemas/ledger-retrieval-seed-v1.schema.json"
SUITE_SCHEMA_PATH = ROOT / ".agent/schemas/ledger-retrieval-suite-v1.schema.json"
QUERY_CASE_SCHEMA_PATH = ROOT / ".agent/schemas/ledger-retrieval-query-case-v1.schema.json"
NOW = datetime(2026, 8, 23, tzinfo=UTC)
type JsonObject = dict[str, Any]


class ConformanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def run() -> JsonObject:
    scenario = _read(SCENARIO_PATH)
    suite = _read(SUITE_PATH)
    _validate_json(suite, SUITE_SCHEMA_PATH, "suite_schema_invalid")
    seed = _read(ROOT / str(suite["seed_path"]))
    _validate_seed(seed)
    query_cases = _query_cases(suite)
    fixture = _fixture(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr5-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(_config(ledger_path, archive_path), encoding="utf-8")
        _run("--config", str(config_path), "ledger", "init")
        ingest = _json(
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(fixture),
            "--source-url",
            scenario["source"]["normalized_url"],
            "--format",
            "json",
        )
        representation_id = _required(ingest, "representation_id")
        _seed_ledger(ledger_path, representation_id, seed)
        build = _json(
            "retrieval", "build-ledger", "--ledger-path", str(ledger_path), "--format", "json"
        )
        _complete(build, "ledger_build_failed")
        results = {
            str(case["query_id"]): _run_query_case(ledger_path, case) for case in query_cases
        }
        rebuilt = _json(
            "retrieval",
            "build-ledger",
            "--ledger-path",
            str(ledger_path),
            "--rebuild",
            "--format",
            "json",
        )
        _complete(rebuilt, "ledger_rebuild_failed")
        exact_case = next(case for case in query_cases if case["query_id"] == "dr5-current-exact")
        repeated = _run_query_case(ledger_path, exact_case)
        if repeated["selected_record_ids"] != results["dr5-current-exact"]["selected_record_ids"]:
            raise ConformanceError(
                "ledger_rebuild_mismatch", "Rebuilt Ledger index changed exact behavior."
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "index_manifest_id": build["index_manifest_id"],
            "query_record_ids": {
                query_id: result["retrieval_query_id"] for query_id, result in results.items()
            },
        }


def _query_cases(suite: JsonObject) -> tuple[JsonObject, ...]:
    cases: list[JsonObject] = []
    for relative_path in cast(list[str], suite["query_pack_paths"]):
        path = ROOT / relative_path
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = cast(JsonObject, json.loads(line))
            _validate_json(case, QUERY_CASE_SCHEMA_PATH, "query_case_schema_invalid")
            cases.append(case)
    return tuple(cases)


def _run_query_case(ledger_path: Path, case: JsonObject) -> JsonObject:
    arguments: list[str] = []
    for key, flag in (
        ("query_text", "--query"),
        ("record_id", "--record-id"),
        ("record_type", "--record-type"),
        ("subject_id", "--subject-id"),
        ("predicate", "--predicate"),
    ):
        value = case.get(key)
        if isinstance(value, str):
            arguments.extend((flag, value))
    for status in cast(list[str], case.get("assertion_statuses", [])):
        arguments.extend(("--assertion-status", status))
    arguments.extend(("--policy", str(case["policy"])))
    result = _query(ledger_path, *arguments)
    _complete(result, f"{case['query_id']}_failed")
    selected = set(cast(list[str], result["selected_record_ids"]))
    required = set(cast(list[str], case["required_selected_record_ids"]))
    if not required.issubset(selected):
        raise ConformanceError(
            "required_record_missing",
            f"{case['query_id']} did not select required records: {sorted(required - selected)}",
        )
    if case["require_context"] and not all(
        isinstance(item.get("context_manifest_id"), str) and item.get("status") == "ready"
        for item in cast(list[JsonObject], result["context_results"])
    ):
        raise ConformanceError(
            "context_manifest_missing",
            f"{case['query_id']} did not produce ready authoritative context.",
        )
    expected_lineage = case.get("expected_lineage")
    if isinstance(expected_lineage, dict):
        lineage = cast(JsonObject, expected_lineage)
        expected_record_id = next(iter(required))
        hit = next(
            item
            for item in cast(list[JsonObject], result["hits"])
            if item["source_record_id"] == expected_record_id
        )
        if hit["lineage_predecessor_id"] != lineage.get("predecessor_id") or hit[
            "lineage_successor_id"
        ] != lineage.get("successor_id"):
            raise ConformanceError(
                "lineage_mismatch", f"{case['query_id']} returned unexpected Assertion lineage."
            )
    return result


def _seed_ledger(ledger_path: Path, representation_id: str, seed: JsonObject) -> None:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(representation_id)
        if bundle is None:
            raise ConformanceError(
                "representation_missing", "Ingest did not persist a representation."
            )
        anchor = str(seed["evidence_anchor"])
        normalized_anchor = _normalize(anchor)
        node = next(
            (
                item
                for item in bundle.nodes
                if normalized_anchor in _normalize(_node_text(item.id, bundle))
            ),
            None,
        )
        if node is None:
            raise ConformanceError("anchor_missing", f"Representation omits seed anchor: {anchor}")
        text = _node_text(node.id, bundle)
        view = next(item for item in bundle.text_views if item.id == node.text_view_id)
        document = ledger.get_document(bundle.representation.document_id)
        if document is None:
            raise ConformanceError("document_missing", "Representation document is missing.")
        evidence = EvidenceTarget(
            id="etg_directive",
            source_id=document.source_id,
            document_id=document.id,
            representation_id=representation_id,
            text_view_id=view.id,
            text_view_digest=view.content_digest,
            start_char=node.start_char,
            end_char=node.end_char,
            exact_text=text,
            normalization_policy=view.normalization_policy,
            node_ids=(node.id,),
        )
        for organization in cast(list[JsonObject], seed["organizations"]):
            _approve(ledger, f"pcg_{organization['id']}", "Organization", organization)
        _approve(ledger, "pcg_evidence", "EvidenceTarget", evidence.model_dump(mode="json"))
        validation = EvidenceValidationAttempt(
            id="eva_directive",
            evidence_target_id=evidence.id,
            target_digest=canonical_evidence_target_digest(evidence),
            validator_version="dr5_canonical_v1",
            status=EvidenceValidationAttemptStatus.SUCCEEDED,
            attempted_at=NOW,
        )
        ledger.save_evidence_validation_attempt(validation)
        for item in cast(list[JsonObject], seed["direct_assertions"]):
            record = _direct_assertion(item, seed, document.source_id, evidence.id)
            _approve(ledger, f"pcg_{record['id']}", "Assertion", record, evidence.id)
        analytic = _analytic_assertion(cast(JsonObject, seed["analytic_assertion"]), seed)
        _approve(ledger, f"pcg_{analytic['id']}", "Assertion", analytic)
        relationship = dict(cast(JsonObject, seed["relationship"]))
        _approve(ledger, f"pcg_{relationship['id']}", "Relationship", relationship)
        outcome = dict(cast(JsonObject, seed["outcome"]))
        _approve(ledger, f"pcg_{outcome['id']}", "Outcome", outcome)


def _approve(
    ledger: Any,
    change_id: str,
    record_type: str,
    record: JsonObject,
    evidence_id: str | None = None,
) -> None:
    proposed: JsonObject = {"record_type": record_type, "stable_label": change_id, "record": record}
    if evidence_id is not None:
        proposed["evidence_links"] = [
            {
                "evidence_target_id": evidence_id,
                "validation_attempt_id": "eva_directive",
                "role": "direct_support",
                "polarity": "supports",
                "necessity": "required",
            }
        ]
    ledger.save_proposed_change(
        ProposedChange(
            id=change_id,
            review_status=ReviewStatus.PENDING,
            proposed_json=proposed,
            provenance_activity_id="prv_dr5_seed",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    approve_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=change_id,
            reviewer="dr5-canonical",
            reviewed_at=NOW,
        ),
        ledger,
    )


def _direct_assertion(
    item: JsonObject, seed: JsonObject, source_id: str, evidence_id: str
) -> JsonObject:
    return {
        **item,
        "assertion_type": "source_claim",
        "epistemic_scope": "source_report",
        "subject_entity_id": "org_anthropic",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_ids": [source_id],
        "evidence_target_ids": [evidence_id],
        "provenance_activity_ids": [],
    }


def _analytic_assertion(item: JsonObject, seed: JsonObject) -> JsonObject:
    return {
        **item,
        "assertion_type": "analytic_inference",
        "epistemic_scope": "analytic_inference",
        "subject_entity_id": "org_anthropic",
        "source_authority": "not_applicable",
        "attribution_basis": "not_applicable",
        "provenance_activity_ids": [],
    }


def _query(ledger_path: Path, *arguments: str) -> JsonObject:
    return _json(
        "retrieval",
        "query-ledger",
        "--ledger-path",
        str(ledger_path),
        *arguments,
        "--maximum-hits",
        "5",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )


def _fixture(scenario: JsonObject) -> Path:
    fixture = ROOT / scenario["fixture"]["repository_path"]
    lock = scenario["fixture"]["fixture_lock"]
    if not fixture.is_file():
        raise ConformanceError("fixture_missing", f"Canonical fixture is missing: {fixture}")
    if _sha256(fixture) != lock["sha256"] or _page_count(fixture) != lock["page_count"]:
        raise ConformanceError("fixture_digest_mismatch", "Fixture does not match its lock.")
    return fixture


def _node_text(node_id: str, bundle: Any) -> str:
    node = next(item for item in bundle.nodes if item.id == node_id)
    view = next(item for item in bundle.text_views if item.id == node.text_view_id)
    return view.text[node.start_char : node.end_char]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _read(path: Path) -> JsonObject:
    return cast(JsonObject, json.loads(path.read_text(encoding="utf-8")))


def _validate_seed(seed: JsonObject) -> None:
    _validate_json(seed, SEED_SCHEMA_PATH, "seed_schema_invalid")


def _validate_json(payload: JsonObject, schema_path: Path, failure_code: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),  # pyright: ignore[reportUnknownMemberType]
        key=lambda item: item.json_path,
    )
    if errors:
        raise ConformanceError(failure_code, errors[0].message)


def _run(*arguments: str) -> None:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise ConformanceError("public_command_failed", completed.stderr.strip())


def _json(*arguments: str) -> JsonObject:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments], cwd=ROOT, capture_output=True, text=True, check=False
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ConformanceError("public_command_invalid", completed.stderr.strip()) from exc
    if completed.returncode != 0 or not isinstance(payload, dict):
        raise ConformanceError(
            "public_command_failed",
            " ".join(arguments) + ": " + (completed.stdout.strip() or completed.stderr.strip()),
        )
    return cast(JsonObject, payload)


def _complete(payload: JsonObject, code: str) -> None:
    if payload.get("status") != "complete":
        raise ConformanceError(code, str(payload.get("failure")))


def _required(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ConformanceError("public_command_invalid", f"Missing string field: {key}")
    return value


def _config(ledger_path: Path, archive_path: Path) -> str:
    return "\n".join(
        (
            f'ledger_path = "{ledger_path}"',
            f'archive_path = "{archive_path}"',
            "[processing.build_identity]",
            'package_version = "dr5-canonical"',
            'source_revision = "dr5-canonical"',
            f'artifact_digest = "{"0" * 64}"',
            'representation_policy_version = "dr5-canonical"',
            "",
        )
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page_count(path: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        raise ConformanceError("pdfinfo_missing", "pdfinfo is required.")
    output = subprocess.run(
        [pdfinfo, str(path)], capture_output=True, text=True, check=False
    ).stdout
    return int(
        next(
            line.partition(":")[2].strip()
            for line in output.splitlines()
            if line.startswith("Pages:")
        )
    )


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(
            json.dumps(
                {"status": "failed", "failure": error.code, "message": str(error)}, sort_keys=True
            )
        )
        raise SystemExit(1) from None
