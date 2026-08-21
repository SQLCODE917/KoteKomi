"""Public-CLI canonical scenario runner for derived document retrieval."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from kotekomi_devtools.receipt_writer import write_receipt

type JsonObject = dict[str, Any]

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class RetrievalScenarioError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def test_ingest(
    scenario_id: str, *, lock_fixture: bool, scenario_state_root: Path
) -> JsonObject:
    scenario_path = _scenario_path(scenario_id)
    scenario = _load_validated(
        scenario_path, "retrieval-scenario-v1.schema.json", "scenario_schema_invalid"
    )
    fixture = _fixture_path(scenario)
    if not fixture.is_file():
        raise RetrievalScenarioError(
            "fixture_missing", f"Canonical fixture is missing: {fixture}"
        )
    fixture_digest = _sha256_file(fixture)
    page_count = _pdf_page_count(fixture)
    lock = scenario["fixture"]["fixture_lock"]
    if lock["state"] == "unlocked":
        if not lock_fixture:
            raise RetrievalScenarioError(
                "fixture_unlocked", "Fixture is unlocked; use --lock-fixture."
            )
        scenario["fixture"]["fixture_lock"] = {
            "state": "locked",
            "sha256": fixture_digest,
            "page_count": page_count,
        }
        scenario_path.write_text(
            json.dumps(scenario, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    elif lock["sha256"] != fixture_digest or lock["page_count"] != page_count:
        raise RetrievalScenarioError(
            "fixture_digest_mismatch", "Fixture bytes do not match the locked scenario."
        )
    expectations_path = REPOSITORY_ROOT / scenario["paths"]["ingest_expectations"]
    expectations = _load_validated(
        expectations_path,
        "retrieval-ingest-expectations-v1.schema.json",
        "scenario_schema_invalid",
    )
    scenario_root = _scenario_state_root(scenario_state_root, scenario_id, fixture_digest)
    _prepare_fresh_scenario_state(scenario_root)
    ledger_path = scenario_root / "ledger.sqlite"
    archive_path = scenario_root / "archive"
    config_path = scenario_root / "kotekomi.toml"
    config_path.write_text(_processing_config(ledger_path, archive_path), encoding="utf-8")
    _product_text("--config", str(config_path), "ledger", "init")
    first = _product_json(
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
    if first.get("status") not in {"created", "reused"} or not first.get("representation_id"):
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "Public source add-file did not create a representation."
        )
    representation_id = _required_str(first, "representation_id")
    build = _product_json(
        "retrieval",
        "build-document",
        "--representation-id",
        representation_id,
        "--ledger-path",
        str(ledger_path),
        "--format",
        "json",
    )
    if build.get("status") != "complete" or int(build.get("unit_count", 0)) <= 0:
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "Persisted representation could not reload for build."
        )
    validate_ingest_anchors(expectations, representation_id, ledger_path)
    second = _product_json(
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
    if second.get("status") != "reused" or second.get("representation_id") != representation_id:
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "Identical re-ingest did not reuse canonical records."
        )
    result = {
        "scenario_id": scenario_id,
        "fixture_sha256": fixture_digest,
        "page_count": page_count,
        "ledger_path": str(ledger_path),
        "archive_path": str(archive_path),
        "representation_id": representation_id,
        "representation_digest": build["content_fingerprint"],
        "source_id": first["source_id"],
        "document_id": first["document_id"],
        "idempotent_reingest": True,
    }
    result_path = scenario_root / "ingest-result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt = write_receipt(
        task_id=scenario_id,
        record_kind="canonical_ingest",
        result="passed",
        output=scenario_root / "ingest-receipt.json",
        artifacts=(f"ingest_result={result_path}",),
        fields=(
            f"representation_id={representation_id}",
            f"fixture_sha256={fixture_digest}",
        ),
        force=True,
    )
    return {**result, **receipt.as_json()}


def test_query(scenario_id: str, *, suite_id: str, scenario_state_root: Path) -> JsonObject:
    scenario_path = _scenario_path(scenario_id)
    scenario = _load_validated(
        scenario_path, "retrieval-scenario-v1.schema.json", "scenario_schema_invalid"
    )
    lock = scenario["fixture"]["fixture_lock"]
    if lock["state"] != "locked":
        raise RetrievalScenarioError(
            "fixture_unlocked", "Canonical fixture must be locked before query."
        )
    fixture = _fixture_path(scenario)
    if not fixture.is_file():
        raise RetrievalScenarioError(
            "fixture_missing", f"Canonical fixture is missing: {fixture}"
        )
    if _sha256_file(fixture) != lock["sha256"]:
        raise RetrievalScenarioError(
            "fixture_digest_mismatch", "Fixture bytes do not match the locked scenario."
        )
    scenario_root = _scenario_state_root(scenario_state_root, scenario_id, lock["sha256"])
    ingest_path = scenario_root / "ingest-result.json"
    if not ingest_path.is_file():
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "No verified ingest receipt is available."
        )
    ingest = _read_object(ingest_path)
    suite_path = REPOSITORY_ROOT / scenario["paths"]["suite_directory"] / f"{suite_id}.json"
    suite = _load_validated(
        suite_path, "retrieval-query-suite-v1.schema.json", "query_suite_invalid"
    )
    if suite["scenario_id"] != scenario_id:
        raise RetrievalScenarioError(
            "query_suite_invalid", "Query suite belongs to another scenario."
        )
    ledger_path = Path(_required_str(ingest, "ledger_path"))
    representation_id = _required_str(ingest, "representation_id")
    build = _product_json(
        "retrieval",
        "build-document",
        "--representation-id",
        representation_id,
        "--ledger-path",
        str(ledger_path),
        "--format",
        "json",
    )
    if build.get("status") != "complete":
        raise RetrievalScenarioError("canonical_query_failed", "Public retrieval build failed.")
    cases = _load_cases(suite)
    outcomes, baseline_observations = _run_query_cases(
        cases, representation_id, ledger_path, suite["policy_ids"]["context_profile_id"]
    )
    rebuilt = _product_json(
        "retrieval",
        "build-document",
        "--representation-id",
        representation_id,
        "--ledger-path",
        str(ledger_path),
        "--format",
        "json",
        "--rebuild",
    )
    if (
        rebuilt.get("status") != "complete"
        or rebuilt.get("content_fingerprint") != build.get("content_fingerprint")
    ):
        raise RetrievalScenarioError(
            "canonical_query_failed", "Derived index did not rebuild equivalently."
        )
    _, rebuilt_observations = _run_query_cases(
        cases, representation_id, ledger_path, suite["policy_ids"]["context_profile_id"]
    )
    if rebuilt_observations != baseline_observations:
        raise RetrievalScenarioError(
            "canonical_query_failed", "Delete-and-rebuild changed observable query behavior."
        )
    result = {
        "scenario_id": scenario_id,
        "suite_id": suite_id,
        "representation_id": representation_id,
        "index_manifest_id": build["index_manifest_id"],
        "content_fingerprint": build["content_fingerprint"],
        "query_outcomes": outcomes,
        "rebuild_equivalent": True,
    }
    result_path = scenario_root / "query-result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt = write_receipt(
        task_id=scenario_id,
        record_kind="canonical_query",
        result="passed",
        output=scenario_root / "query-receipt.json",
        input_records=(f"ingest_result={ingest_path}",),
        artifacts=(f"query_result={result_path}",),
        fields=(f"suite_id={suite_id}", f"representation_id={representation_id}"),
        force=True,
    )
    return {**result, **receipt.as_json()}


def _run_query_cases(
    cases: Sequence[JsonObject],
    representation_id: str,
    ledger_path: Path,
    context_profile_id: str,
) -> tuple[list[JsonObject], dict[str, JsonObject]]:
    outcomes: list[JsonObject] = []
    observations: dict[str, JsonObject] = {}
    for case in cases:
        query = _product_json(
            "retrieval",
            "query",
            "--representation-id",
            representation_id,
            "--query",
            case["query_text"],
            "--maximum-hits",
            "10",
            "--context-profile",
            context_profile_id,
            "--ledger-path",
            str(ledger_path),
            "--format",
            "json",
        )
        _validate_query_case(case, query)
        query_id = _required_str(case, "query_id")
        outcomes.append({"query_id": query_id, "retrieval_query_id": query["retrieval_query_id"]})
        observations[query_id] = {
            "hits": query["hits"],
            "selected_node_ids": query["selected_node_ids"],
            "authoritative_nodes": query["authoritative_nodes"],
            "context_manifest_rendered_input": query["context_manifest_rendered_input"],
        }
    return outcomes, observations


def validate_ingest_anchors(
    expectations: JsonObject, representation_id: str, ledger_path: Path
) -> None:
    for expectation in expectations["required_text_anchors"]:
        query = _product_json(
            "retrieval",
            "query",
            "--representation-id",
            representation_id,
            "--query",
            expectation["text"],
            "--maximum-hits",
            "10",
            "--context-profile",
            "retrieval-validation-v1",
            "--ledger-path",
            str(ledger_path),
            "--format",
            "json",
        )
        text = expectation["text"]
        nodes = _object_list(query.get("authoritative_nodes", []))
        normalized_text = _normalize_anchor_text(text)
        found = sum(
            (
                _normalize_anchor_text(str(node.get("text", ""))).casefold().count(
                    normalized_text.casefold()
                )
                if expectation["match_mode"] == "casefold_substring"
                else _normalize_anchor_text(str(node.get("text", ""))).count(normalized_text)
            )
            for node in nodes
        )
        if query.get("status") != "complete" or found < expectation["minimum_occurrences"]:
            raise _primary_text_fidelity_failure(expectation)


def _normalize_anchor_text(value: str) -> str:
    """Match exact retrieval whitespace without changing authoritative node text."""
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", normalized).strip()


def _primary_text_fidelity_failure(expectation: JsonObject) -> RetrievalScenarioError:
    """Report that the sole authoritative text producer lost required source text."""
    anchor_id = _required_str(expectation, "anchor_id")
    text = _required_str(expectation, "text")
    match_mode = _required_str(expectation, "match_mode")
    return RetrievalScenarioError(
        "primary_text_fidelity_failed",
        "Authoritative representation text is missing required "
        f"{match_mode} anchor {anchor_id!r}: {text!r}. "
        "KoteKomi does not normalize or patch primary-parser text.",
    )


def _validate_query_case(case: JsonObject, query: JsonObject) -> None:
    if query.get("status") != "complete" or not query.get("context_manifest_id"):
        raise RetrievalScenarioError(
            "canonical_query_failed", f"Query failed: {case['query_id']}"
        )
    hits_value = query.get("hits")
    if not isinstance(hits_value, list):
        raise RetrievalScenarioError(
            "canonical_query_failed", "Query did not return hit observations."
        )
    hits = _object_list(cast(list[object], hits_value))
    nodes = _object_list(query.get("authoritative_nodes", []))
    ranks = {
        node_id: hit.get("final_rank")
        for hit in hits
        for node_id in _string_list(hit.get("authoritative_node_ids", []))
    }
    required_channels = set(case["required_channels"])
    available_channels = {
        observation.get("channel")
        for hit in hits
        for observation in _object_list(hit.get("channel_observations", []))
    }
    if not required_channels.issubset(available_channels):
        raise RetrievalScenarioError(
            "canonical_query_failed", f"Missing required channel: {case['query_id']}"
        )
    rendered = str(query.get("context_manifest_rendered_input") or "")
    for expected in case["expected_hits"]:
        normalized_anchor = _normalize_anchor_text(expected["anchor_text"])
        matching_nodes = [
            node
            for node in nodes
            if normalized_anchor.casefold()
            in _normalize_anchor_text(str(node.get("text", ""))).casefold()
            and str(node.get("node_type")) in expected.get("expected_node_types", [])
            and _node_rank_is_at_most(node, ranks, expected["maximum_rank"])
            and _path_suffix_matches(
                _string_list(node.get("section_path", [])), expected["section_path_suffix"]
            )
        ]
        normalized_rendered = _normalize_anchor_text(rendered).casefold()
        required_sections = _string_list(expected["section_path_suffix"])
        if (
            not matching_nodes
            or normalized_anchor.casefold() not in normalized_rendered
            or any(
                _normalize_anchor_text(section).casefold() not in normalized_rendered
                for section in required_sections
            )
        ):
            raise RetrievalScenarioError(
                "canonical_query_failed", f"Missing expected anchor: {case['query_id']}"
            )
        if expected["must_be_unique_exact"]:
            first: JsonObject = hits[0] if hits else {}
            observed = {
                item.get("channel")
                for item in _object_list(first.get("channel_observations", []))
            }
            if first.get("final_rank") != 1 or "exact" not in observed:
                raise RetrievalScenarioError(
                    "canonical_query_failed", f"Exact precedence failed: {case['query_id']}"
                )
    for forbidden in case["context_expectations"]["forbidden_projection_kinds"]:
        if forbidden in rendered:
            raise RetrievalScenarioError(
                "canonical_query_failed", f"Projection text leaked: {forbidden}"
            )


def _load_cases(suite: JsonObject) -> list[JsonObject]:
    cases: list[JsonObject] = []
    for relative_path in suite["query_pack_paths"]:
        path = REPOSITORY_ROOT / relative_path
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = json.loads(line)
                _validate(
                    case, "retrieval-query-case-v1.schema.json", "query_suite_invalid"
                )
                cases.append(case)
    return cases


def _product_json(*arguments: str) -> JsonObject:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RetrievalScenarioError(
            "canonical_ingest_failed", f"Public command did not return JSON: {completed.stderr}"
        ) from exc
    if not isinstance(payload, dict):
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "Public command JSON must be an object."
        )
    return cast(JsonObject, payload)


def _product_text(*arguments: str) -> None:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RetrievalScenarioError(
            "canonical_ingest_failed", f"Public command failed: {completed.stderr}"
        )


def _scenario_path(scenario_id: str) -> Path:
    path = REPOSITORY_ROOT / ".agent" / "scenarios" / scenario_id / "scenario.json"
    if not path.is_file():
        raise RetrievalScenarioError(
            "scenario_schema_invalid", f"Unknown scenario: {scenario_id}"
        )
    return path


def _fixture_path(scenario: JsonObject) -> Path:
    return REPOSITORY_ROOT / scenario["fixture"]["repository_path"]


def _scenario_state_root(root: Path, scenario_id: str, digest: str) -> Path:
    return root.expanduser().resolve() / "retrieval-scenarios" / scenario_id / digest


def _prepare_fresh_scenario_state(scenario_root: Path) -> None:
    """Replace only the deterministic scenario-owned state before a canonical ingest."""
    if scenario_root.exists():
        shutil.rmtree(scenario_root)
    scenario_root.mkdir(parents=True)


def _load_validated(path: Path, schema_name: str, error_code: str) -> JsonObject:
    value = _read_object(path)
    _validate(value, schema_name, error_code)
    return value


def _validate(value: JsonObject, schema_name: str, error_code: str) -> None:
    schema = _read_object(REPOSITORY_ROOT / ".agent" / "schemas" / schema_name)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(value))  # type: ignore[reportUnknownMemberType]
    if errors:
        raise RetrievalScenarioError(error_code, errors[0].message)


def _read_object(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RetrievalScenarioError(
            "scenario_schema_invalid", f"Cannot read JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RetrievalScenarioError(
            "scenario_schema_invalid", f"JSON object required: {path}"
        )
    return cast(JsonObject, value)


def _object_list(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    if not all(isinstance(item, dict) for item in values):
        return []
    return [cast(JsonObject, item) for item in values]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [item for item in values if isinstance(item, str)]


def _path_suffix_matches(path: list[str], suffix: object) -> bool:
    required = _string_list(suffix)
    return not required or path[-len(required) :] == required


def _node_rank_is_at_most(
    node: JsonObject, ranks: Mapping[str, object], maximum: object
) -> bool:
    node_id = node.get("node_id")
    rank = ranks.get(node_id) if isinstance(node_id, str) else None
    return isinstance(rank, int) and isinstance(maximum, int) and rank <= maximum


def _pdf_page_count(path: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "pdfinfo is required to lock PDF fixtures."
        )
    completed = subprocess.run(
        [pdfinfo, str(path)], capture_output=True, text=True, check=False
    )
    match = next(
        (
            line.partition(":")[2].strip()
            for line in completed.stdout.splitlines()
            if line.startswith("Pages:")
        ),
        None,
    )
    if completed.returncode != 0 or match is None or not match.isdigit() or int(match) <= 0:
        raise RetrievalScenarioError(
            "canonical_ingest_failed", "Could not determine PDF page count."
        )
    return int(match)


def _processing_config(ledger_path: Path, archive_path: Path) -> str:
    return "\n".join(
        (
            f'ledger_path = "{ledger_path}"',
            f'archive_path = "{archive_path}"',
            "[processing.build_identity]",
            'package_version = "canonical-scenario-v1"',
            'source_revision = "canonical-scenario-v1"',
            f'artifact_digest = "{"0" * 64}"',
            'representation_policy_version = "canonical-scenario-v1"',
            "",
        )
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _required_str(value: JsonObject, key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise RetrievalScenarioError("canonical_ingest_failed", f"Missing required field: {key}")
    return candidate
