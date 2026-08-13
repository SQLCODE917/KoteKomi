from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class ReceiptSpec:
    name: str
    path: str | Path
    expected_sha256: str | None = None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_specs(
    task_id: str,
    phase: str,
    state_root: Path,
) -> tuple[ReceiptSpec, ...]:
    root = state_root.expanduser() / task_id
    defaults = {
        "spec": (
            ("spec-commit", "spec/spec-commit.json"),
            ("spec-ci", "spec/spec-ci.json"),
        ),
        "candidate": (
            ("candidate-commit", "candidate-01/candidate-commit.json"),
            ("candidate-lifecycle", "candidate-01/candidate-lifecycle.json.receipt"),
            ("verification-plan", "candidate-01/verification-plan-receipt.json"),
            ("verify-checks", "candidate-01/verify-checks-receipt.json"),
            ("candidate-ci", "candidate-01/candidate-ci.json"),
        ),
        "main": (
            ("main-lifecycle", "main/main-lifecycle.json.receipt"),
            ("main-merge", "main/main-merge.json"),
            ("main-ci", "main/main-ci.json"),
        ),
    }
    return tuple(
        ReceiptSpec(name, root / relative_path)
        for name, relative_path in defaults.get(phase, ())
    )


def _diagnostic(code: str, location: str, message: str) -> dict[str, str]:
    return {"code": code, "location": location, "message": message}


def build_receipt_chain_status(
    *,
    task_id: str,
    phase: str,
    receipts: Sequence[ReceiptSpec],
    required_names: Sequence[str] = (),
) -> dict[str, object]:
    diagnostics: list[dict[str, str]] = []
    by_name = {receipt.name: receipt for receipt in receipts}
    required = tuple(required_names) or tuple(by_name)
    names = sorted(set(by_name) | set(required))
    entries: list[dict[str, object]] = []
    missing: list[str] = []

    if len(by_name) != len(receipts):
        diagnostics.append(
            _diagnostic(
                "receipt_chain_status.duplicate_receipt",
                "/receipts",
                "duplicate receipt names are not allowed",
            )
        )

    for name in names:
        spec = by_name.get(name)
        if spec is None:
            missing.append(name)
            diagnostics.append(
                _diagnostic(
                    "receipt_chain_status.missing_receipt",
                    f"/required/{name}",
                    f"required receipt {name!r} was not supplied",
                )
            )
            entries.append({"name": name, "exists": False, "status": "missing"})
            continue

        path = Path(spec.path).expanduser()
        entry: dict[str, object] = {
            "exists": path.exists(),
            "name": name,
            "path": str(path),
        }
        if not path.is_file():
            if name in required:
                missing.append(name)
                diagnostics.append(
                    _diagnostic(
                        "receipt_chain_status.missing_receipt",
                        f"/receipts/{name}",
                        f"required receipt {name!r} does not exist",
                    )
                )
            entry["status"] = "missing"
            entries.append(entry)
            continue

        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            diagnostics.append(
                _diagnostic(
                    "receipt_chain_status.invalid_receipt",
                    f"/receipts/{name}",
                    f"receipt {name!r} is not readable JSON: {error}",
                )
            )
            entry["status"] = "invalid"
            entries.append(entry)
            continue

        digest = sha256_file(path)
        entry["sha256"] = digest
        if spec.expected_sha256:
            entry["expected_sha256"] = spec.expected_sha256
        if spec.expected_sha256 and spec.expected_sha256 != digest:
            diagnostics.append(
                _diagnostic(
                    "receipt_chain_status.digest_mismatch",
                    f"/receipts/{name}/sha256",
                    f"receipt {name!r} SHA-256 did not match expected digest",
                )
            )
            entry["status"] = "digest_mismatch"
        else:
            entry["status"] = "ready"
        entries.append(entry)

    return {
        "diagnostics": diagnostics,
        "missing_required_records": sorted(set(missing)),
        "phase": phase,
        "receipts": entries,
        "schema_version": 1,
        "status": "ready" if not diagnostics else "blocked",
        "task_id": task_id,
    }


def markdown_status(payload: dict[str, object]) -> str:
    lines = [
        f"# Receipt chain status: {payload['task_id']}",
        "",
        f"- Phase: `{payload['phase']}`",
        f"- Status: `{payload['status']}`",
        "",
        "| Record | Status | SHA-256 | Path |",
        "| --- | --- | --- | --- |",
    ]
    receipts_value = payload.get("receipts", [])
    if isinstance(receipts_value, list):
        receipts = cast(list[dict[str, object]], receipts_value)
        for receipt in receipts:
            lines.append(
                f"| `{receipt.get('name', '')}` | "
                f"`{receipt.get('status', '')}` | "
                f"`{receipt.get('sha256', '')}` | "
                f"`{receipt.get('path', '')}` |"
            )

    diagnostics_value = payload.get("diagnostics", [])
    if isinstance(diagnostics_value, list) and diagnostics_value:
        diagnostics = cast(list[dict[str, object]], diagnostics_value)
        lines += ["", "## Diagnostics", ""]
        for diagnostic in diagnostics:
            lines.append(
                f"- `{diagnostic.get('code', '')}` at "
                f"`{diagnostic.get('location', '')}`: "
                f"{diagnostic.get('message', '')}"
            )
    return "\n".join(lines) + "\n"


def _name_value(raw: str, option: str) -> tuple[str, str]:
    if "=" not in raw:
        raise ValueError(f"{option} requires NAME=VALUE")
    name, value = raw.split("=", 1)
    if not name or not value:
        raise ValueError(f"{option} requires non-empty NAME=VALUE")
    return name, value


def run_receipt_chain_status_command(arguments: argparse.Namespace) -> int:
    try:
        expectations = dict(
            _name_value(raw, "--expect") for raw in (arguments.expect or ())
        )
        pairs = (
            _name_value(raw, "--receipt") for raw in (arguments.receipt or ())
        )
        receipts = [
            ReceiptSpec(name, path, expectations.pop(name, None))
            for name, path in pairs
        ]
        receipts += [
            ReceiptSpec(name, Path("__missing_expected_receipt__"), digest)
            for name, digest in sorted(expectations.items())
        ]
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if not receipts:
        receipts = list(
            _default_specs(arguments.task_id, arguments.phase, Path(arguments.state_root))
        )
    payload = build_receipt_chain_status(
        task_id=arguments.task_id,
        phase=arguments.phase,
        receipts=receipts,
        required_names=arguments.required or (),
    )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        Path(arguments.output).write_text(text, encoding="utf-8")
    if arguments.markdown:
        Path(arguments.markdown).write_text(markdown_status(payload), encoding="utf-8")
    print(text, end="")
    return 0 if payload["status"] == "ready" else 1

