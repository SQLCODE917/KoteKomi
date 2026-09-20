from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from kotekomi_application import (
    AttachmentMeasurementManifest,
    AttachmentMeasurementOutcome,
    AttachmentMeasurementPackageStatus,
    AttachmentMeasurementStatus,
    AttachmentReviewClaimVerdict,
    AttachmentReviewClaimVerification,
    AttachmentReviewVerification,
    AttachmentSecondOpinionReceipt,
    attachment_measurement_fingerprint,
)

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_measurement_authority")


def test_claude_launcher_uses_stdin_stdout_and_separate_diagnostics(tmp_path: Path) -> None:
    runner = _runner()

    launcher = runner._claude_launcher(tmp_path)

    assert '< "$RUN_ROOT/second-opinion-handoff.md"' in launcher
    assert '> "$RUN_ROOT/claude-opus-review.md"' in launcher
    assert '2> "$RUN_ROOT/claude-opus-review.stderr.log"' in launcher
    assert '"$RUN_ROOT/claude-opus-review.status.json"' in launcher
    assert '--add-dir "$RUN_ROOT"' in launcher


def test_review_receipt_and_claim_verification_close_the_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner()
    root = tmp_path / "package"
    root.mkdir()
    report = SimpleNamespace(
        inputs=(),
        outcome=AttachmentMeasurementOutcome.UNSAFE,
        result_fingerprint=DIGEST,
    )

    def fake_load_report(_root: Path) -> SimpleNamespace:
        return report

    monkeypatch.setattr(runner, "_load_report", fake_load_report)
    _write_initial_package(runner, root, report)

    assert runner._record_second_opinion(argparse.Namespace(output_root=root)) == 0
    receipt = AttachmentSecondOpinionReceipt.model_validate_json(
        (root / "second-opinion-receipt.json").read_bytes()
    )
    recorded_status = AttachmentMeasurementStatus.model_validate_json(
        (root / "status.json").read_bytes()
    )
    assert recorded_status.status is AttachmentMeasurementPackageStatus.REVIEW_RECORDED
    assert receipt.review_byte_count == len((root / "claude-opus-review.md").read_bytes())

    evidence = runner._file_reference(
        "audit_report",
        root / "audit-report.json",
        relative_to=root,
    )
    claim = AttachmentReviewClaimVerification(
        claim_id="r1_rule_is_unsafe",
        claim_text="R1-strict removes Gold-positive attachments.",
        verdict=AttachmentReviewClaimVerdict.CONFIRMED,
        evidence=(evidence,),
        rationale="The occurrence-level audit preserves positive losses.",
    )
    draft = AttachmentReviewVerification.model_construct(
        reviewer="fixture-reviewer",
        review_sha256=receipt.review.sha256,
        review_fully_covered=True,
        claims=(claim,),
        result_fingerprint="0" * 64,
    )
    verification = AttachmentReviewVerification(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_measurement_fingerprint(draft),
    )
    verification_path = root / "verification-input.json"
    runner._write_json(verification_path, verification.model_dump(mode="json"))

    assert (
        runner._finalize(
            argparse.Namespace(
                output_root=root,
                claim_verification=verification_path,
            )
        )
        == 0
    )
    status = AttachmentMeasurementStatus.model_validate_json((root / "status.json").read_bytes())
    manifest = AttachmentMeasurementManifest.model_validate_json(
        (root / "manifest.json").read_bytes()
    )
    assert status.status is AttachmentMeasurementPackageStatus.COMPLETE
    assert manifest.status is AttachmentMeasurementPackageStatus.COMPLETE
    assert manifest.model_execution_count == 0
    assert manifest.proposed_change_count == 0
    assert manifest.accepted_ledger_change_count == 0


def _write_initial_package(runner: Any, root: Path, report: Any) -> None:
    files = {
        "audit-report.json": "{}\n",
        "audit-review.md": "# Audit\n",
        "diagnostic-controls.json": "{}\n",
        "second-opinion-handoff.md": "# Handoff\n",
        "claude-opus-review.md": "# Independent review\n",
        "claude-opus-review.stderr.log": "",
    }
    for name, value in files.items():
        (root / name).write_text(value, encoding="utf-8")
    launcher = root / "run-claude-second-opinion.sh"
    launcher.write_text(runner._claude_launcher(root), encoding="utf-8")
    runner._write_json(root / "claude-opus-review.status.json", {"exit_code": 0})
    status = runner._status(
        root,
        package_status=AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION,
        report=report,
    )
    runner._write_json(root / "status.json", status.model_dump(mode="json"))
