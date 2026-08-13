from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from kotekomi_devtools.receipt_chain_status import (
    ReceiptSpec,
    build_receipt_chain_status,
    sha256_file,
)


def _write_receipt(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_file(path)


def test_receipt_chain_status_reports_complete_chain(tmp_path: Path) -> None:
    receipt = tmp_path / "spec-commit.json"
    digest = _write_receipt(receipt, {"result": "spec_ready"})

    payload = build_receipt_chain_status(
        task_id="h15-fixture",
        phase="spec",
        receipts=[ReceiptSpec("spec-commit", receipt, digest)],
        required_names=["spec-commit"],
    )

    assert payload["status"] == "ready"
    assert payload["missing_required_records"] == []
    assert payload["diagnostics"] == []
    receipts_value = payload["receipts"]
    assert isinstance(receipts_value, list)
    receipts = cast(list[dict[str, object]], receipts_value)
    assert receipts[0]["name"] == "spec-commit"
    assert receipts[0]["sha256"] == digest


def test_receipt_chain_status_fails_closed_for_missing_required_record() -> None:
    payload = build_receipt_chain_status(
        task_id="h15-fixture",
        phase="candidate",
        receipts=[],
        required_names=["candidate-ci"],
    )

    assert payload["status"] == "blocked"
    assert payload["missing_required_records"] == ["candidate-ci"]
    diagnostics_value = payload["diagnostics"]
    assert isinstance(diagnostics_value, list)
    diagnostics = cast(list[dict[str, object]], diagnostics_value)
    assert diagnostics[0]["code"] == "receipt_chain_status.missing_receipt"


def test_receipt_chain_status_fails_closed_for_digest_mismatch(tmp_path: Path) -> None:
    receipt = tmp_path / "candidate-ci.json"
    actual_digest = _write_receipt(receipt, {"result": "candidate_ci_success"})
    expected_digest = "0" * 64
    assert actual_digest != expected_digest

    payload = build_receipt_chain_status(
        task_id="h15-fixture",
        phase="candidate",
        receipts=[ReceiptSpec("candidate-ci", receipt, expected_digest)],
        required_names=["candidate-ci"],
    )

    assert payload["status"] == "blocked"
    receipts_value = payload["receipts"]
    assert isinstance(receipts_value, list)
    receipts = cast(list[dict[str, object]], receipts_value)
    assert receipts[0]["status"] == "digest_mismatch"
    diagnostics_value = payload["diagnostics"]
    assert isinstance(diagnostics_value, list)
    diagnostics = cast(list[dict[str, object]], diagnostics_value)
    assert diagnostics[0]["code"] == "receipt_chain_status.digest_mismatch"
