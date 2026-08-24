"""Verify CIR-1 User Ingestion Run MVP against the locked deposited PDF."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import sqlite_ledger_transaction

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json"
type JsonObject = dict[str, Any]


class ConformanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def run() -> JsonObject:
    scenario = _read(SCENARIO_PATH)
    fixture = _locked_fixture(scenario)
    source_url = str(cast(JsonObject, scenario["source"])["normalized_url"])
    with tempfile.TemporaryDirectory(prefix="kotekomi-cir1-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        config_path = root / "kotekomi.toml"
        config_path.write_text(_config(ledger_path, root / "archive"), encoding="utf-8")
        first = _run("--config", str(config_path), "ingest", str(fixture), "--url", source_url)
        second = _run("--config", str(config_path), "ingest", str(fixture), "--url", source_url)
        missing = _run(
            "--config",
            str(config_path),
            "ingest",
            str(root / "missing.pdf"),
            "--url",
            source_url,
            expected_returncode=1,
        )
        history = _run("--config", str(config_path), "ingestions", "list")
        _validate_output(first, "[CAPTURED]")
        _validate_output(second, "[CAPTURED]")
        if missing.stdout:
            raise ConformanceError("error_stdout_not_empty", "Failed ingestion wrote a result row.")
        if "not found" not in missing.stderr:
            raise ConformanceError(
                "missing_file_failure_invalid", "Missing-file explanation changed."
            )
        rows = tuple(line for line in history.stdout.splitlines() if line)
        if len(rows) != 3 or sum("[CAPTURED]" in row for row in rows) != 2 or sum(
            "[ERROR]" in row for row in rows
        ) != 1:
            raise ConformanceError(
                "history_shape_invalid", "History does not contain two captures and one error."
            )
        if any(
            _contains_domain_id(value) for value in (first.stdout, second.stdout, history.stdout)
        ):
            raise ConformanceError(
                "domain_id_exposed", "Default User CLI output exposed a canonical ID."
            )
        with sqlite_ledger_transaction(ledger_path) as repository:
            runs = repository.list_ingestion_runs()
        captures = tuple(run for run in runs if run.status.value == "captured")
        if len(captures) != 2 or captures[0].source_id != captures[1].source_id:
            raise ConformanceError(
                "source_reuse_invalid", "Repeated ingest did not reuse the Source."
            )
        if captures[0].document_id != captures[1].document_id:
            raise ConformanceError(
                "document_reuse_invalid", "Repeated ingest did not reuse the Document."
            )
        return {
            "status": "passed",
            "ingestion_run_count": len(runs),
            "captured_run_count": len(captures),
            "error_run_count": len(runs) - len(captures),
        }


def _run(*arguments: str, expected_returncode: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["uv", "run", "kotekomi", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != expected_returncode:
        raise ConformanceError(
            "public_command_failed", completed.stdout.strip() or completed.stderr.strip()
        )
    return completed


def _validate_output(result: subprocess.CompletedProcess[str], status: str) -> None:
    if _user_stderr(result.stderr) or not re.fullmatch(
        rf"[^\t]+\t\{status}\t\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}\n", result.stdout
    ):
        raise ConformanceError("captured_output_invalid", "Captured User CLI row changed.")


def _locked_fixture(scenario: JsonObject) -> Path:
    fixture_data = cast(JsonObject, scenario["fixture"])
    fixture = ROOT / str(fixture_data["repository_path"])
    lock = cast(JsonObject, fixture_data["fixture_lock"])
    if not fixture.is_file():
        raise ConformanceError("fixture_missing", f"Canonical fixture is missing: {fixture}")
    if _sha256(fixture) != lock["sha256"] or _page_count(fixture) != lock["page_count"]:
        raise ConformanceError("fixture_digest_mismatch", "Fixture does not match its lock.")
    return fixture


def _read(path: Path) -> JsonObject:
    return cast(JsonObject, json.loads(path.read_text(encoding="utf-8")))


def _config(ledger_path: Path, archive_path: Path) -> str:
    return "\n".join(
        (
            f'ledger_path = "{ledger_path}"',
            f'archive_path = "{archive_path}"',
            "[processing.build_identity]",
            'package_version = "cir1-canonical"',
            'source_revision = "cir1-canonical"',
            f'artifact_digest = "{"0" * 64}"',
            'representation_policy_version = "cir1-canonical"',
            "",
        )
    )


def _contains_domain_id(value: str) -> bool:
    return re.search(r"\b(?:src|doc|rep|prv|igr)_[A-Za-z0-9_-]+", value) is not None


def _user_stderr(value: str) -> str:
    return "\n".join(
        line
        for line in value.splitlines()
        if not line.startswith("warning: The `UV_NATIVE_TLS` environment variable is deprecated")
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page_count(path: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        raise ConformanceError("pdfinfo_missing", "pdfinfo is required.")
    result = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, check=False)
    output = result.stdout
    for line in output.splitlines():
        if line.startswith("Pages:"):
            return int(line.partition(":")[2].strip())
    raise ConformanceError("pdfinfo_invalid", "pdfinfo did not report page count.")


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
