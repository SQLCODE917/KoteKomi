#!/usr/bin/env python3
"""Build and close the model-free CEA-1.6 attachment measurement package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_application import (
    AttachmentCalibrationObservation,
    AttachmentCalibrationPromptArm,
    AttachmentCalibrationPromptResult,
    AttachmentEvidenceReference,
    AttachmentExpectedExactProfile,
    AttachmentMeasurementAuditReport,
    AttachmentMeasurementManifest,
    AttachmentMeasurementPackageStatus,
    AttachmentMeasurementStatus,
    AttachmentReviewVerification,
    AttachmentSecondOpinionReceipt,
    AttachmentSelectionPolicyReport,
    attachment_measurement_fingerprint,
)
from kotekomi_pipelines.competitive_attachment_edge_filter_calibration import (
    build_calibration_prompt_result,
)
from kotekomi_pipelines.competitive_attachment_measurement_authority import (
    audit_r1_strict_phase,
    authoritative_attachment_gold_sets,
    build_attachment_measurement_audit,
    build_attachment_measurement_controls,
    render_attachment_measurement_handoff,
    render_attachment_measurement_review,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-measurement-authority.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run")
    run.add_argument("--calibration-root", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)

    record = commands.add_parser("record-second-opinion")
    record.add_argument("--output-root", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--claim-verification", type=Path, required=True)

    args = parser.parse_args()
    return {
        "run": _run,
        "record-second-opinion": _record_second_opinion,
        "finalize": _finalize,
    }[args.command](args)


def _run(args: argparse.Namespace) -> int:
    calibration_root = args.calibration_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("CEA-1.6 run requires an absent or empty output root.")
    output_root.mkdir(parents=True, exist_ok=True)
    metadata = _validated_calibration_metadata(calibration_root)
    selection_path = _metadata_root(metadata, "selection_run_root") / "report.json"
    selection = AttachmentSelectionPolicyReport.model_validate_json(selection_path.read_bytes())
    development = cea14.reload_prepared_attachment_edge_filter_phase(
        calibration_root, metadata, "development"
    )
    validation = cea14.reload_prepared_attachment_edge_filter_phase(
        calibration_root, metadata, "validation"
    )
    for phase, prepared, expected_count in (
        ("development", development, 162),
        ("validation", validation, 179),
    ):
        authoritative = authoritative_attachment_gold_sets(
            phase=cast(Literal["development", "validation"], phase),
            original_decisions=tuple(
                decision
                for decisions in prepared.evidence.oracle.values()
                for decision in decisions
            ),
            normalization_changes=selection.normalization_changes,
            expected_candidate_count=expected_count,
        )
        if authoritative != prepared.gold_sets:
            raise ValueError(f"CEA-1.6 {phase} Gold differs from the sealed prepared phase.")
    calibration_results = {
        arm: _reclassify_prompt(calibration_root, arm) for arm in AttachmentCalibrationPromptArm
    }
    inputs = _input_references(calibration_root, metadata)
    development_report = audit_r1_strict_phase(
        phase="development",
        edges=development.edges,
        tasks=development.tasks,
        gold_sets=development.gold_sets,
    )
    validation_report = audit_r1_strict_phase(
        phase="validation",
        edges=validation.edges,
        tasks=validation.tasks,
        gold_sets=validation.gold_sets,
    )
    report = build_attachment_measurement_audit(
        inputs=inputs,
        v8_outcome=calibration_results[AttachmentCalibrationPromptArm.V8].outcome,
        v9_outcome=calibration_results[AttachmentCalibrationPromptArm.V9].outcome,
        development=development_report,
        validation=validation_report,
    )
    predecessor_catalog = _file_reference(
        "predecessor_catalog",
        calibration_root / "diagnostic-catalog.json",
    )
    controls = build_attachment_measurement_controls(
        predecessor_catalog=predecessor_catalog,
        development=development_report,
    )
    _write_json(output_root / "audit-report.json", report.model_dump(mode="json"))
    (output_root / "audit-review.md").write_text(
        render_attachment_measurement_review(report), encoding="utf-8"
    )
    _write_json(
        output_root / "diagnostic-controls.json",
        controls.model_dump(mode="json"),
    )
    (output_root / "second-opinion-handoff.md").write_text(
        render_attachment_measurement_handoff(report, controls), encoding="utf-8"
    )
    launcher = output_root / "run-claude-second-opinion.sh"
    launcher.write_text(_claude_launcher(output_root), encoding="utf-8")
    launcher.chmod(0o755)
    status = _status(
        output_root,
        package_status=AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION,
        report=report,
    )
    _write_json(output_root / "status.json", status.model_dump(mode="json"))
    manifest = _manifest(
        output_root,
        package_status=AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION,
        report=report,
        inputs=inputs,
        receipt=None,
        verification=None,
    )
    _write_json(output_root / "manifest.json", manifest.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "audit_report": str(output_root / "audit-report.json"),
                "claude_launcher": str(launcher),
                "controls": str(output_root / "diagnostic-controls.json"),
                "handoff": str(output_root / "second-opinion-handoff.md"),
                "outcome": report.outcome.value,
                "output_root": str(output_root),
                "status": status.status.value,
            },
            sort_keys=True,
        )
    )
    return 0


def _record_second_opinion(args: argparse.Namespace) -> int:
    root = args.output_root.resolve()
    report = _load_report(root)
    current = AttachmentMeasurementStatus.model_validate_json((root / "status.json").read_bytes())
    if current.status is not AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION:
        raise ValueError("CEA-1.6 second opinion is not awaiting review.")
    claude_status_path = root / "claude-opus-review.status.json"
    value = _read_object(claude_status_path)
    if value.get("exit_code") != 0:
        raise ValueError("CEA-1.6 Claude review did not exit successfully.")
    review_path = root / "claude-opus-review.md"
    review_bytes = review_path.read_bytes()
    if not review_bytes.strip():
        raise ValueError("CEA-1.6 Claude review is empty.")
    handoff_path = root / "second-opinion-handoff.md"
    stderr_path = root / "claude-opus-review.stderr.log"
    draft = AttachmentSecondOpinionReceipt.model_construct(
        handoff=_file_reference("second_opinion_handoff", handoff_path, relative_to=root),
        review=_file_reference("claude_opus_review", review_path, relative_to=root),
        stderr_log=_file_reference("claude_stderr", stderr_path, relative_to=root),
        claude_status=_file_reference("claude_status", claude_status_path, relative_to=root),
        exit_code=0,
        review_byte_count=len(review_bytes),
        result_fingerprint="0" * 64,
    )
    receipt = AttachmentSecondOpinionReceipt(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_measurement_fingerprint(draft),
    )
    _write_json(root / "second-opinion-receipt.json", receipt.model_dump(mode="json"))
    status = _status(
        root,
        package_status=AttachmentMeasurementPackageStatus.REVIEW_RECORDED,
        report=report,
        receipt=receipt,
    )
    _write_json(root / "status.json", status.model_dump(mode="json"))
    manifest = _manifest(
        root,
        package_status=AttachmentMeasurementPackageStatus.REVIEW_RECORDED,
        report=report,
        inputs=report.inputs,
        receipt=receipt,
        verification=None,
    )
    _write_json(root / "manifest.json", manifest.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "receipt": str(root / "second-opinion-receipt.json"),
                "review_sha256": receipt.review.sha256,
                "status": status.status.value,
            },
            sort_keys=True,
        )
    )
    return 0


def _finalize(args: argparse.Namespace) -> int:
    root = args.output_root.resolve()
    report = _load_report(root)
    current = AttachmentMeasurementStatus.model_validate_json((root / "status.json").read_bytes())
    if current.status is not AttachmentMeasurementPackageStatus.REVIEW_RECORDED:
        raise ValueError("CEA-1.6 review must be recorded before finalization.")
    receipt = AttachmentSecondOpinionReceipt.model_validate_json(
        (root / "second-opinion-receipt.json").read_bytes()
    )
    _validate_reference(receipt.handoff, root)
    _validate_reference(receipt.review, root)
    _validate_reference(receipt.stderr_log, root)
    _validate_reference(receipt.claude_status, root)
    verification_path = args.claim_verification.resolve()
    verification = AttachmentReviewVerification.model_validate_json(verification_path.read_bytes())
    if verification.review_sha256 != receipt.review.sha256:
        raise ValueError("CEA-1.6 claim verification belongs to another review.")
    for claim in verification.claims:
        for reference in claim.evidence:
            _validate_reference(reference, root)
    stored_verification = root / "claim-verification.json"
    if verification_path != stored_verification:
        stored_verification.write_bytes(verification_path.read_bytes())
    status = _status(
        root,
        package_status=AttachmentMeasurementPackageStatus.COMPLETE,
        report=report,
        receipt=receipt,
        verification=verification,
    )
    _write_json(root / "status.json", status.model_dump(mode="json"))
    manifest = _manifest(
        root,
        package_status=AttachmentMeasurementPackageStatus.COMPLETE,
        report=report,
        inputs=report.inputs,
        receipt=receipt,
        verification=verification,
    )
    _write_json(root / "manifest.json", manifest.model_dump(mode="json"))
    _validate_manifest_references(manifest, root)
    print(
        json.dumps(
            {
                "manifest": str(root / "manifest.json"),
                "outcome": report.outcome.value,
                "status": status.status.value,
                "verified_claim_count": len(verification.claims),
            },
            sort_keys=True,
        )
    )
    return 0


def _validated_calibration_metadata(root: Path) -> dict[str, Any]:
    metadata = _read_object(root / "run.json")
    if metadata.get("schema_version") != "attachment_calibration_run_v1":
        raise ValueError("CEA-1.6 requires a CEA-1.5 calibration root.")
    if metadata.get("status") != "diagnostic_complete":
        raise ValueError("CEA-1.6 requires the closed CEA-1.5 diagnostic.")
    if (
        metadata.get("proposed_change_count") != 0
        or metadata.get("accepted_ledger_change_count") != 0
    ):
        raise ValueError("CEA-1.5 evidence reports canonical intelligence writes.")
    for filename, digest_key in (
        ("pool-development.json", "development_pool_sha256"),
        ("pool-validation.json", "validation_pool_sha256"),
        ("tasks-development.json", "development_tasks_sha256"),
        ("tasks-validation.json", "validation_tasks_sha256"),
        ("diagnostic-catalog.json", "diagnostic_catalog_sha256"),
        ("expected-exact-development.json", "expected_exact_development_sha256"),
        ("expected-exact-validation.json", "expected_exact_validation_sha256"),
    ):
        path = root / filename
        if _sha(path.read_bytes()) != _required_str(metadata, digest_key):
            raise ValueError(f"CEA-1.6 sealed calibration evidence drifted: {filename}.")
    return metadata


def _reclassify_prompt(
    root: Path,
    arm: AttachmentCalibrationPromptArm,
) -> AttachmentCalibrationPromptResult:
    value = _read_object(root / "diagnostic" / arm.value / "report.json")
    observations_value = value.get("observations")
    if not isinstance(observations_value, list):
        raise ValueError("CEA-1.6 calibration observations are missing.")
    observations_value = cast(list[object], observations_value)
    observations = tuple(
        AttachmentCalibrationObservation.model_validate_json(_canonical_json(item))
        for item in observations_value
    )
    development_profile = AttachmentExpectedExactProfile.model_validate_json(
        (root / "expected-exact-development.json").read_bytes()
    )
    validation_profile = AttachmentExpectedExactProfile.model_validate_json(
        (root / "expected-exact-validation.json").read_bytes()
    )
    return build_calibration_prompt_result(
        prompt_arm=arm,
        prompt_sha256=_required_str(value, "prompt_sha256"),
        observations=observations,
        development_profile=development_profile,
        validation_profile=validation_profile,
    )


def _input_references(
    root: Path,
    metadata: dict[str, Any],
) -> tuple[AttachmentEvidenceReference, ...]:
    paths = {
        "calibration_diagnostic_catalog": root / "diagnostic-catalog.json",
        "calibration_run": root / "run.json",
        "calibration_v8_report": root / "diagnostic/v8/report.json",
        "calibration_v9_report": root / "diagnostic/v9/report.json",
        "development_oracle": _metadata_root(metadata, "development_run_root") / "oracle.json",
        "development_pool": root / "pool-development.json",
        "development_tasks": root / "tasks-development.json",
        "proposition_gold": _metadata_path(metadata, "gold_path"),
        "selection_report": _metadata_root(metadata, "selection_run_root") / "report.json",
        "validation_oracle": _metadata_root(metadata, "validation_run_root") / "oracle.json",
        "validation_pool": root / "pool-validation.json",
        "validation_tasks": root / "tasks-validation.json",
    }
    return tuple(_file_reference(label, path) for label, path in sorted(paths.items()))


def _manifest(
    root: Path,
    *,
    package_status: AttachmentMeasurementPackageStatus,
    report: AttachmentMeasurementAuditReport,
    inputs: tuple[AttachmentEvidenceReference, ...],
    receipt: AttachmentSecondOpinionReceipt | None,
    verification: AttachmentReviewVerification | None,
) -> AttachmentMeasurementManifest:
    output_paths = {
        "audit_report": root / "audit-report.json",
        "audit_review": root / "audit-review.md",
        "claude_launcher": root / "run-claude-second-opinion.sh",
        "diagnostic_controls": root / "diagnostic-controls.json",
        "package_status": root / "status.json",
        "second_opinion_handoff": root / "second-opinion-handoff.md",
    }
    if receipt is not None:
        output_paths.update(
            {
                "claude_opus_review": root / "claude-opus-review.md",
                "claude_status": root / "claude-opus-review.status.json",
                "claude_stderr": root / "claude-opus-review.stderr.log",
                "second_opinion_receipt": root / "second-opinion-receipt.json",
            }
        )
    if verification is not None:
        output_paths["claim_verification"] = root / "claim-verification.json"
    outputs = tuple(
        _file_reference(label, path, relative_to=root)
        for label, path in sorted(output_paths.items())
    )
    draft = AttachmentMeasurementManifest.model_construct(
        status=package_status,
        tdd=_file_reference("tdd", TDD_PATH),
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        outputs=outputs,
        audit_result_fingerprint=report.result_fingerprint,
        second_opinion_receipt_fingerprint=(
            receipt.result_fingerprint if receipt is not None else None
        ),
        review_verification_fingerprint=(
            verification.result_fingerprint if verification is not None else None
        ),
        production_integration="not_activated",
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint="0" * 64,
    )
    return AttachmentMeasurementManifest(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_measurement_fingerprint(draft),
    )


def _status(
    root: Path,
    *,
    package_status: AttachmentMeasurementPackageStatus,
    report: AttachmentMeasurementAuditReport,
    receipt: AttachmentSecondOpinionReceipt | None = None,
    verification: AttachmentReviewVerification | None = None,
) -> AttachmentMeasurementStatus:
    return AttachmentMeasurementStatus(
        status=package_status,
        outcome=report.outcome,
        report_path=str(root / "audit-report.json"),
        controls_path=str(root / "diagnostic-controls.json"),
        handoff_path=str(root / "second-opinion-handoff.md"),
        launcher_path=str(root / "run-claude-second-opinion.sh"),
        manifest_path=str(root / "manifest.json"),
        second_opinion_receipt_path=(
            str(root / "second-opinion-receipt.json") if receipt is not None else None
        ),
        review_verification_path=(
            str(root / "claim-verification.json") if verification is not None else None
        ),
    )


def _claude_launcher(root: Path) -> str:
    quoted_root = shlex.quote(str(root))
    return f"""#!/usr/bin/env bash
set -uo pipefail

RUN_ROOT={quoted_root}
CLAUDE_STATUS=1

finish() {{
  jq -n --argjson exit_code "$CLAUDE_STATUS" \\
    '{{exit_code: $exit_code}}' > "$RUN_ROOT/claude-opus-review.status.json"
  printf 'CLAUDE_STATUS=%s\\n' "$CLAUDE_STATUS"
  printf 'REVIEW=%s\\n' "$RUN_ROOT/claude-opus-review.md"
  printf 'STDERR_LOG=%s\\n' "$RUN_ROOT/claude-opus-review.stderr.log"
  printf 'STATUS_FILE=%s\\n' "$RUN_ROOT/claude-opus-review.status.json"
}}
trap finish EXIT

claude -p --model opus --effort high --add-dir "$RUN_ROOT" \\
  < "$RUN_ROOT/second-opinion-handoff.md" \\
  > "$RUN_ROOT/claude-opus-review.md" \\
  2> "$RUN_ROOT/claude-opus-review.stderr.log"
CLAUDE_STATUS=$?
exit "$CLAUDE_STATUS"
"""


def _load_report(root: Path) -> AttachmentMeasurementAuditReport:
    return AttachmentMeasurementAuditReport.model_validate_json(
        (root / "audit-report.json").read_bytes()
    )


def _validate_manifest_references(manifest: AttachmentMeasurementManifest, root: Path) -> None:
    _validate_reference(manifest.tdd, root)
    for reference in (*manifest.inputs, *manifest.outputs):
        _validate_reference(reference, root)


def _validate_reference(reference: AttachmentEvidenceReference, root: Path) -> None:
    path = Path(reference.path)
    resolved = path if path.is_absolute() else root / path
    if not resolved.is_file() or _sha(resolved.read_bytes()) != reference.sha256:
        raise ValueError(f"CEA-1.6 evidence reference drifted: {reference.label}.")


def _file_reference(
    label: str,
    path: Path,
    *,
    relative_to: Path | None = None,
) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.6 evidence file is missing: {resolved}.")
    stored = str(resolved.relative_to(relative_to.resolve())) if relative_to else str(resolved)
    return AttachmentEvidenceReference(
        label=label,
        path=stored,
        sha256=_sha(resolved.read_bytes()),
    )


def _metadata_root(metadata: dict[str, Any], key: str) -> Path:
    return Path(_required_str(metadata, key)).resolve()


def _metadata_path(metadata: dict[str, Any], key: str) -> Path:
    path = Path(_required_str(metadata, key))
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()


def _required_str(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"CEA-1.6 {key} must be a non-empty string.")
    return result


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"CEA-1.6 expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(value) + b"\n")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
