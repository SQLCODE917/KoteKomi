"""Verify DR-4 against the locked local deposited PDF without Harness state."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_application import load_context_manifest
from kotekomi_domain import DocumentNode, DocumentRepresentationBundle, DocumentRetrievalUnit

type JsonObject = dict[str, Any]

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / ".agent" / "scenarios" / "anthropic-dod-dispute-v1" / "scenario.json"
QUERY = "all lawful purposes"


class ConformanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def run() -> JsonObject:
    scenario = _read_object(SCENARIO_PATH)
    fixture, fixture_digest, page_count = _verify_fixture(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr4-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(_processing_config(ledger_path, archive_path), encoding="utf-8")
        _run_text("--config", str(config_path), "ledger", "init")
        ingest = _run_json(
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(fixture),
            "--source-url",
            _required_str(_object(scenario["source"], "source"), "normalized_url"),
            "--format",
            "json",
        )
        representation_id = _required_str(ingest, "representation_id")
        build = _run_json(
            "retrieval",
            "build-document",
            "--representation-id",
            representation_id,
            "--ledger-path",
            str(ledger_path),
            "--channel",
            "exact-lexical",
            "--format",
            "json",
        )
        _require_complete(build, "retrieval_build_failed")
        query = _run_json(
            "retrieval",
            "query",
            "--representation-id",
            representation_id,
            "--query",
            QUERY,
            "--maximum-hits",
            "1",
            "--context-profile",
            "retrieval-validation-v1",
            "--ledger-path",
            str(ledger_path),
            "--channel",
            "exact-lexical",
            "--format",
            "json",
        )
        _require_complete(query, "retrieval_query_failed")
        _verify_hierarchy(ledger_path, representation_id, query)
        return {
            "status": "passed",
            "fixture_sha256": fixture_digest,
            "page_count": page_count,
            "representation_id": representation_id,
            "index_manifest_id": _required_str(build, "index_manifest_id"),
            "retrieval_query_id": _required_str(query, "retrieval_query_id"),
            "context_manifest_id": _required_str(query, "context_manifest_id"),
        }


def _verify_fixture(scenario: JsonObject) -> tuple[Path, str, int]:
    fixture_value = _object(scenario.get("fixture"), "fixture")
    lock = _object(fixture_value.get("fixture_lock"), "fixture_lock")
    if lock.get("state") != "locked":
        raise ConformanceError("fixture_unlocked", "DR-4 requires a locked canonical fixture.")
    fixture = ROOT / _required_str(fixture_value, "repository_path")
    if not fixture.is_file():
        raise ConformanceError("fixture_missing", f"Canonical fixture is missing: {fixture}")
    digest = _sha256_file(fixture)
    expected_digest = _required_str(lock, "sha256")
    page_count = _pdf_page_count(fixture)
    expected_page_count = lock.get("page_count")
    if digest != expected_digest or page_count != expected_page_count:
        raise ConformanceError(
            "fixture_digest_mismatch", "Fixture does not match the canonical lock."
        )
    return fixture, digest, page_count


def _verify_hierarchy(ledger_path: Path, representation_id: str, query: JsonObject) -> None:
    hits = _object_list(query.get("hits"))
    if len(hits) != 1:
        raise ConformanceError("retrieval_query_failed", "DR-4 query must select one hit.")
    retrieval_unit_id = _required_str(hits[0], "retrieval_unit_id")
    selected_node_ids = _string_list(query.get("selected_node_ids"))
    if len(selected_node_ids) != 1:
        raise ConformanceError("retrieval_query_failed", "DR-4 query must select one focal node.")
    focus_node_id = selected_node_ids[0]
    with sqlite_ledger_transaction(ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(representation_id)
        if bundle is None:
            raise ConformanceError(
                "representation_missing", "Ingest did not persist its representation."
            )
        manifest = load_context_manifest(_required_str(query, "context_manifest_id"), ledger)
        expected_ancestors = _ancestor_node_ids(focus_node_id, bundle)
        expected_headings = tuple(
            node_id
            for node_id in expected_ancestors
            if _node_by_id(node_id, bundle).node_type == "heading"
        )
        selected_candidates = tuple(candidate.node_id for candidate in manifest.selected_candidates)
        if focus_node_id not in selected_candidates:
            raise ConformanceError(
                "context_focus_missing", "ContextManifest omits the selected focus node."
            )
        if not set(expected_headings).issubset(selected_candidates):
            raise ConformanceError(
                "context_heading_missing",
                "ContextManifest omits an authoritative heading ancestor.",
            )
        document_root_id = next(node.id for node in bundle.nodes if node.node_type == "document")
        if document_root_id in selected_candidates:
            raise ConformanceError(
                "context_root_included", "ContextManifest includes the document root."
            )
        nonheading_ancestors = {
            node_id
            for node_id in expected_ancestors
            if _node_by_id(node_id, bundle).node_type not in {"document", "heading"}
        }
        if nonheading_ancestors.intersection(selected_candidates):
            raise ConformanceError(
                "context_parent_body_included",
                "ContextManifest includes a non-heading ancestor body.",
            )
        focus = _node_by_id(focus_node_id, bundle)
        sibling_candidates = tuple(
            candidate
            for candidate in manifest.selected_candidates
            if candidate.node_id != focus_node_id
            and _node_by_id(candidate.node_id, bundle).parent_node_id == focus.parent_node_id
        )
        dependency_reason_codes = {
            "acronym_definition",
            "table_annotation",
            "table_header_ancestry",
        }
        if any(
            candidate.reason_code not in dependency_reason_codes for candidate in sibling_candidates
        ):
            raise ConformanceError(
                "context_sibling_included", "ContextManifest includes a sibling node."
            )
    unit = _load_unit(ledger_path, retrieval_unit_id)
    if unit.node_ids != (focus_node_id,):
        raise ConformanceError(
            "unit_focus_mismatch", "Selected unit does not identify the focus node."
        )
    if (
        unit.ancestor_node_ids != expected_ancestors
        or unit.parent_node_id != expected_ancestors[-1]
    ):
        raise ConformanceError(
            "unit_hierarchy_mismatch", "Stored unit does not match bundle ancestry."
        )


def _load_unit(ledger_path: Path, retrieval_unit_id: str) -> DocumentRetrievalUnit:
    index_path = ledger_path.with_suffix(".retrieval.sqlite")
    with sqlite3.connect(index_path) as connection:
        row = connection.execute(
            "SELECT unit_json FROM retrieval_units WHERE retrieval_unit_id = ?",
            (retrieval_unit_id,),
        ).fetchone()
    if row is None:
        raise ConformanceError("retrieval_unit_missing", "Derived index omits the selected unit.")
    return DocumentRetrievalUnit.model_validate_json(cast(str, row[0]))


def _ancestor_node_ids(node_id: str, bundle: DocumentRepresentationBundle) -> tuple[str, ...]:
    ancestors: list[str] = []
    node = _node_by_id(node_id, bundle)
    while node.parent_node_id is not None:
        ancestors.append(node.parent_node_id)
        node = _node_by_id(node.parent_node_id, bundle)
    if not ancestors:
        raise ConformanceError(
            "unit_hierarchy_mismatch", "Selected focus node has no parent chain."
        )
    return tuple(reversed(ancestors))


def _node_by_id(node_id: str, bundle: DocumentRepresentationBundle) -> DocumentNode:
    for node in bundle.nodes:
        if node.id == node_id:
            return node
    raise ConformanceError("unit_hierarchy_mismatch", f"Representation omits node: {node_id}")


def _run_json(*arguments: str) -> JsonObject:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ConformanceError("public_command_invalid", completed.stderr.strip()) from exc
    if completed.returncode != 0 or not isinstance(payload, dict):
        raise ConformanceError("public_command_failed", completed.stderr.strip())
    return cast(JsonObject, payload)


def _run_text(*arguments: str) -> None:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ConformanceError("public_command_failed", completed.stderr.strip())


def _processing_config(ledger_path: Path, archive_path: Path) -> str:
    return "\n".join(
        (
            f'ledger_path = "{ledger_path}"',
            f'archive_path = "{archive_path}"',
            "[processing]",
            'representation_policy_version = "dr4-canonical"',
            "",
        )
    )


def _pdf_page_count(path: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        raise ConformanceError("pdfinfo_missing", "pdfinfo is required for fixture validation.")
    completed = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, check=False)
    pages = next(
        (
            line.partition(":")[2].strip()
            for line in completed.stdout.splitlines()
            if line.startswith("Pages:")
        ),
        None,
    )
    if completed.returncode != 0 or pages is None or not pages.isdigit() or int(pages) <= 0:
        raise ConformanceError(
            "fixture_page_count_invalid", "Could not determine fixture page count."
        )
    return int(pages)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _require_complete(payload: JsonObject, code: str) -> None:
    if payload.get("status") != "complete":
        raise ConformanceError(code, f"Public command failed: {payload}")


def _read_object(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConformanceError("scenario_invalid", f"Cannot read {path}") from exc
    if not isinstance(value, dict):
        raise ConformanceError("scenario_invalid", f"Expected JSON object: {path}")
    return cast(JsonObject, value)


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ConformanceError("scenario_invalid", f"Expected JSON object: {name}")
    return cast(JsonObject, value)


def _required_str(value: JsonObject, key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise ConformanceError("scenario_invalid", f"Expected nonempty string: {key}")
    return candidate


def _object_list(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    if not all(isinstance(item, dict) for item in values):
        return []
    return cast(list[JsonObject], values)


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    values = cast(list[object], value)
    if not all(isinstance(item, str) for item in values):
        return ()
    return tuple(cast(list[str], values))


def main() -> None:
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as exc:
        print(json.dumps({"status": "failed", "failure": exc.code, "message": str(exc)}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
