from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from kotekomi_application import (
    AttachmentEvidenceReference,
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


def test_status_reports_handoff_and_review_paths_without_a_launcher(tmp_path: Path) -> None:
    runner = _runner()
    report = SimpleNamespace(outcome=AttachmentMeasurementOutcome.UNSAFE)

    status = runner._status(
        tmp_path,
        package_status=AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION,
        report=report,
    )

    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.review_path == str(tmp_path / "claude-opus-review.md")
    assert not (tmp_path / "run-claude-second-opinion.sh").exists()


def test_gold_authority_is_embedded_byte_for_byte(tmp_path: Path) -> None:
    runner = _runner()
    source_root = tmp_path / "sources"
    output_root = tmp_path / "package"
    source_root.mkdir()
    output_root.mkdir()
    inputs: list[AttachmentEvidenceReference] = []
    for label in ("development_oracle", "selection_report", "validation_oracle"):
        path = source_root / f"{label}.json"
        path.write_text(f'{{"label":"{label}"}}\n', encoding="utf-8")
        inputs.append(runner._file_reference(label, path))

    embedded = runner._embed_gold_authority(output_root, tuple(inputs))

    assert tuple(item.label for item in embedded) == (
        "attachment_gold_development_oracle",
        "attachment_gold_selection_report",
        "attachment_gold_validation_oracle",
    )
    assert (output_root / "attachment-gold-development-oracle.json").read_bytes() == (
        source_root / "development_oracle.json"
    ).read_bytes()
    assert (output_root / "attachment-gold-selection-report.json").read_bytes() == (
        source_root / "selection_report.json"
    ).read_bytes()
    assert (output_root / "attachment-gold-validation-oracle.json").read_bytes() == (
        source_root / "validation_oracle.json"
    ).read_bytes()


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

    assert (
        runner._record_second_opinion(argparse.Namespace(output_root=root, reported_exit_code=0))
        == 0
    )
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
        "attachment-gold-development-oracle.json": "{}\n",
        "attachment-gold-selection-report.json": "{}\n",
        "attachment-gold-validation-oracle.json": "{}\n",
        "audit-report.json": "{}\n",
        "audit-review.md": "# Audit\n",
        "diagnostic-controls.json": "{}\n",
        "second-opinion-handoff.md": "# Handoff\n",
        "claude-opus-review.md": "# Independent review\n",
    }
    for name, value in files.items():
        (root / name).write_text(value, encoding="utf-8")
    status = runner._status(
        root,
        package_status=AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION,
        report=report,
    )
    runner._write_json(root / "status.json", status.model_dump(mode="json"))
