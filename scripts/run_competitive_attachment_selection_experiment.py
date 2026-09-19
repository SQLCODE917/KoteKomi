#!/usr/bin/env python3
"""Run the model-free CEA-1.3 bounded hybrid selection diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentReviewVerificationManifest,
    AttachmentReviewVerificationReport,
    AttachmentReviewVerificationStatus,
    AttachmentSelectionPolicyManifest,
    AttachmentSelectionPolicyReport,
    AttachmentSelectionPolicyStatus,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
)
from kotekomi_pipelines.competitive_attachment_selection import (
    attachment_selection_policy_summary,
    build_attachment_selection_policy_report,
    canonical_attachment_selection_json,
    render_attachment_selection_policy_handoff,
    render_attachment_selection_policy_review,
)
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
    load_connection_gold_catalog,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    load_proposition_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
TDD_PATH = (
    REPOSITORY_ROOT / "docs/2026-09-18-competitive-event-attachment-bounded-hybrid-selection.md"
)


@dataclass(frozen=True)
class _Cea1Evidence:
    root: Path
    report: CompetitiveAttachmentPhaseReport
    inputs: tuple[EventEntityExperimentInput, ...]
    matrices: tuple[CompetitiveAttachmentMatrix, ...]
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]
    bindings: dict[str, str]


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-selection-policy")
    verify.add_argument("--development-run-root", type=Path, required=True)
    verify.add_argument("--validation-run-root", type=Path, required=True)
    verify.add_argument("--review-run-root", type=Path, required=True)
    verify.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    verify.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    return _verify_selection_policy(args)


def _verify_selection_policy(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("CEA-1.3 requires an absent or empty output root.")
    output_root.mkdir(parents=True, exist_ok=True)
    development = _validated_cea1_evidence(
        args.development_run_root.resolve(),
        expected_phase="development",
    )
    validation = _validated_cea1_evidence(
        args.validation_run_root.resolve(),
        expected_phase="validation",
    )
    review_root = args.review_run_root.resolve()
    review_report = _validated_review_evidence(review_root)
    gold_path = args.gold.resolve()
    gold_catalog = load_proposition_gold_catalog(
        gold_path,
        repository_root=REPOSITORY_ROOT,
    )
    if gold_catalog.review_status.value != "approved":
        raise ValueError("CEA-1.3 requires approved Proposition Gold.")
    entity_occurrences_by_event = {
        evidence.bindings[gold_event_id]: occurrences
        for phase, evidence in (
            ("development", development),
            ("validation", validation),
        )
        for gold_event_id, occurrences in _entity_occurrences(
            gold_catalog,
            cast(Literal["development", "validation"], phase),
        ).items()
    }
    input_references = tuple(
        sorted(
            (
                _file_reference(
                    "cea1_development_bindings", development.root / "gold-bindings.json"
                ),
                _file_reference("cea1_development_inputs", development.root / "inputs.jsonl"),
                _file_reference("cea1_development_matrices", development.root / "matrices.json"),
                _file_reference("cea1_development_oracle", development.root / "oracle.json"),
                _file_reference("cea1_development_report", development.root / "report.json"),
                _directory_reference("cea1_development_run_root", development.root),
                _file_reference("cea1_validation_bindings", validation.root / "gold-bindings.json"),
                _file_reference("cea1_validation_inputs", validation.root / "inputs.jsonl"),
                _file_reference("cea1_validation_matrices", validation.root / "matrices.json"),
                _file_reference("cea1_validation_oracle", validation.root / "oracle.json"),
                _file_reference("cea1_validation_report", validation.root / "report.json"),
                _directory_reference("cea1_validation_run_root", validation.root),
                _file_reference("cea12_manifest", review_root / "manifest.json"),
                _file_reference("cea12_report", review_root / "report.json"),
                _file_reference("gold_catalog", gold_path),
                _file_reference(
                    "selection_application",
                    REPOSITORY_ROOT / "packages/application/src/kotekomi_application/"
                    "competitive_attachment_selection.py",
                ),
                _file_reference(
                    "selection_pipeline",
                    REPOSITORY_ROOT / "packages/pipelines/src/kotekomi_pipelines/"
                    "competitive_attachment_selection.py",
                ),
                _file_reference("selection_runner", Path(__file__).resolve()),
            ),
            key=lambda item: item.label,
        )
    )
    report = build_attachment_selection_policy_report(
        input_references=input_references,
        development_report=development.report,
        development_matrices=development.matrices,
        development_oracle=development.oracle,
        development_inputs=development.inputs,
        development_bindings=development.bindings,
        validation_report=validation.report,
        validation_matrices=validation.matrices,
        validation_oracle=validation.oracle,
        validation_inputs=validation.inputs,
        validation_bindings=validation.bindings,
        review_report=review_report,
        gold_catalog=gold_catalog,
        entity_occurrences_by_event=entity_occurrences_by_event,
    )
    report_path = output_root / "report.json"
    review_path = output_root / "review.md"
    summary_path = output_root / "summary.json"
    handoff_path = output_root / "handoff.md"
    status_path = output_root / "status.json"
    manifest_path = output_root / "manifest.json"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        render_attachment_selection_policy_review(report),
        encoding="utf-8",
    )
    _write_json(summary_path, attachment_selection_policy_summary(report))
    handoff_path.write_text(
        render_attachment_selection_policy_handoff(report),
        encoding="utf-8",
    )
    _validate_primary_outputs(
        report=report,
        report_path=report_path,
        review_path=review_path,
        summary_path=summary_path,
        handoff_path=handoff_path,
    )
    status = AttachmentSelectionPolicyStatus(
        outcome=report.outcome,
        result_fingerprint=report.result_fingerprint,
        report_path=report_path.name,
        review_path=review_path.name,
        summary_path=summary_path.name,
        handoff_path=handoff_path.name,
    )
    _write_json(status_path, status.model_dump(mode="json"))
    AttachmentSelectionPolicyStatus.model_validate_json(status_path.read_bytes())
    outputs = tuple(
        sorted(
            (
                _file_reference("handoff", handoff_path, relative_to=output_root),
                _file_reference("report", report_path, relative_to=output_root),
                _file_reference("review", review_path, relative_to=output_root),
                _file_reference("status", status_path, relative_to=output_root),
                _file_reference("summary", summary_path, relative_to=output_root),
            ),
            key=lambda item: item.label,
        )
    )
    manifest = AttachmentSelectionPolicyManifest(
        tdd=_file_reference("tdd", TDD_PATH),
        inputs=input_references,
        outputs=outputs,
        result_fingerprint=report.result_fingerprint,
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    AttachmentSelectionPolicyManifest.model_validate_json(manifest_path.read_bytes())
    print(
        json.dumps(
            {
                "handoff": str(handoff_path),
                "manifest": str(manifest_path),
                "outcome": report.outcome.value,
                "report": str(report_path),
                "review": str(review_path),
                "status": "complete",
                "status_file": str(status_path),
                "summary": str(summary_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _validated_cea1_evidence(
    root: Path,
    *,
    expected_phase: Literal["development", "validation"],
) -> _Cea1Evidence:
    metadata = _read_json(root / "run.json")
    if (
        metadata.get("schema_version") != "competitive_attachment_experiment_run_v1"
        or metadata.get("status") != "finalized"
        or metadata.get("phase") != expected_phase
        or metadata.get("repetition") != 1
    ):
        raise ValueError(f"CEA-1.3 requires finalized {expected_phase} CEA-1 evidence.")
    static_paths = {
        "canonical_state_sha256": root / "canonical-state.json",
        "inputs_sha256": root / "inputs.jsonl",
        "matrices_sha256": root / "matrices.json",
        "bindings_sha256": root / "gold-bindings.json",
        "oracle_sha256": root / "oracle.json",
        "baseline_sha256": root / "baseline.json",
        "preflight_sha256": root / "preflight.json",
        "diagnostic_catalog_sha256": root / "diagnostic-catalog.json",
    }
    gold_path = _stored_path(metadata.get("gold_path"))
    static_paths["gold_sha256"] = gold_path
    prompt_path = REPOSITORY_ROOT / "prompts/competitive_event_attachment_v1.md"
    static_paths["prompt_sha256"] = prompt_path
    for field, path in static_paths.items():
        if not path.is_file() or metadata.get(field) != _sha(path.read_bytes()):
            raise ValueError(f"CEA-1.3 CEA-1 input digest changed: {field}.")
    report_path = root / "report.json"
    review_path = root / "review.md"
    report = CompetitiveAttachmentPhaseReport.model_validate_json(report_path.read_bytes())
    manifest = _read_json(root / "manifest.json")
    expected_manifest = {
        "schema_version": "competitive_attachment_manifest_v1",
        "phase": expected_phase,
        "repetition": 1,
        "report_sha256": _sha(report_path.read_bytes()),
        "review_sha256": _sha(review_path.read_bytes()),
        "result_fingerprint": report.result_fingerprint,
        "model_execution_count": report.model_execution_count,
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
    }
    if manifest != expected_manifest:
        raise ValueError(f"CEA-1.3 {expected_phase} CEA-1 manifest is invalid.")
    if expected_phase == "validation":
        finalized = root / "FINALIZED"
        if not finalized.is_file() or finalized.read_text(encoding="utf-8") != _sha(
            _canonical_json(manifest)
        ):
            raise ValueError("CEA-1.3 validation finalization receipt is invalid.")
    inputs = _load_inputs(root / "inputs.jsonl")
    matrices = _load_matrices(root / "matrices.json")
    oracle = _load_oracle(root / "oracle.json")
    bindings_value = _read_json(root / "gold-bindings.json")
    bindings = {str(key): str(value) for key, value in bindings_value.items()}
    if report.phase != expected_phase or len(report.cases) != sum(
        len(item.candidates) for item in matrices
    ):
        raise ValueError("CEA-1.3 CEA-1 report inventory drifted.")
    return _Cea1Evidence(
        root=root,
        report=report,
        inputs=inputs,
        matrices=matrices,
        oracle=oracle,
        bindings=bindings,
    )


def _validated_review_evidence(root: Path) -> AttachmentReviewVerificationReport:
    report_path = root / "report.json"
    status_path = root / "status.json"
    manifest_path = root / "manifest.json"
    report = AttachmentReviewVerificationReport.model_validate_json(report_path.read_bytes())
    status = AttachmentReviewVerificationStatus.model_validate_json(status_path.read_bytes())
    manifest = AttachmentReviewVerificationManifest.model_validate_json(manifest_path.read_bytes())
    if (
        status.result_fingerprint != report.result_fingerprint
        or manifest.result_fingerprint != report.result_fingerprint
    ):
        raise ValueError("CEA-1.3 CEA-1.2 result fingerprint chain is invalid.")
    _require_historical_reference(manifest.tdd, base=root)
    for reference in manifest.inputs:
        if reference.label in {
            "review_policy_application",
            "review_policy_pipeline",
            "review_policy_predicate_arguments",
            "review_policy_runner",
            "second_opinion",
        }:
            _require_historical_reference(reference, base=root)
        else:
            _validate_reference(reference, base=root)
    for reference in manifest.outputs:
        _validate_reference(reference, base=root)
    return report


def _require_historical_reference(
    reference: AttachmentEvidenceReference,
    *,
    base: Path,
) -> None:
    path = _reference_path(reference, base=base)
    if not path.exists():
        raise ValueError(f"CEA-1.3 historical evidence path is missing: {path}.")


def _validate_reference(reference: AttachmentEvidenceReference, *, base: Path) -> None:
    path = _reference_path(reference, base=base)
    if path.is_dir():
        observed = _directory_sha(path)
    elif path.is_file():
        observed = _sha(path.read_bytes())
    else:
        raise ValueError(f"CEA-1.3 referenced evidence is missing: {path}.")
    if observed != reference.sha256:
        raise ValueError(f"CEA-1.3 referenced evidence digest changed: {reference.label}.")


def _reference_path(reference: AttachmentEvidenceReference, *, base: Path) -> Path:
    path = Path(reference.path)
    if path.is_absolute():
        return path
    repository_path = REPOSITORY_ROOT / path
    return repository_path if repository_path.exists() else base / path


def _validate_primary_outputs(
    *,
    report: AttachmentSelectionPolicyReport,
    report_path: Path,
    review_path: Path,
    summary_path: Path,
    handoff_path: Path,
) -> None:
    AttachmentSelectionPolicyReport.model_validate_json(report_path.read_bytes())
    if (
        report_path.read_bytes()
        != canonical_attachment_selection_json(report.model_dump(mode="json")) + b"\n"
    ):
        raise ValueError("CEA-1.3 report serialization is not canonical.")
    if not review_path.read_text(encoding="utf-8").startswith(
        "# CEA-1.3 Bounded Hybrid Selection Review\n"
    ):
        raise ValueError("CEA-1.3 review output is invalid.")
    summary = _read_json(summary_path)
    if (
        summary.get("result_fingerprint") != report.result_fingerprint
        or summary.get("model_execution_count") != 0
        or summary.get("production_integration") != "not_activated"
    ):
        raise ValueError("CEA-1.3 summary output is invalid.")
    if not handoff_path.read_text(encoding="utf-8").startswith(
        "# CEA-1.3 Bounded Hybrid Selection Handoff\n"
    ):
        raise ValueError("CEA-1.3 handoff output is invalid.")


def _entity_occurrences(
    catalog: PropositionGoldCatalog,
    phase: Literal["development", "validation"],
) -> dict[str, tuple[tuple[int, int], ...]]:
    connection_path = (REPOSITORY_ROOT / catalog.connection_gold_path).resolve()
    connection, _, _ = load_connection_gold_catalog(
        connection_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    return {
        item.event_id: tuple(
            sorted(
                {
                    (occurrence.start, occurrence.end)
                    for entity in item.expected_entities
                    for occurrence in entity.accepted_source_occurrences
                }
            )
        )
        for item in connection.events
        if item.phase == phase
    }


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line
    )


def _load_matrices(path: Path) -> tuple[CompetitiveAttachmentMatrix, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1.3 matrix evidence must be a JSON array.")
    records = cast(list[object], value)
    return tuple(
        CompetitiveAttachmentMatrix.model_validate_json(_canonical_json(item)) for item in records
    )


def _load_oracle(
    path: Path,
) -> dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]:
    value = _read_json(path)
    return {
        str(matrix_id): tuple(
            CompetitiveAttachmentGoldDecision.model_validate_json(_canonical_json(item))
            for item in cast(list[object], decisions)
        )
        for matrix_id, decisions in value.items()
    }


def _file_reference(
    label: str,
    path: Path,
    *,
    relative_to: Path | None = None,
) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.3 evidence file is missing: {resolved}.")
    stored = (
        str(resolved.relative_to(relative_to.resolve()))
        if relative_to is not None
        else _relative_or_absolute(resolved)
    )
    return AttachmentEvidenceReference(
        label=label,
        path=stored,
        sha256=_sha(resolved.read_bytes()),
    )


def _directory_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_directory_sha(resolved),
    )


def _directory_sha(path: Path) -> str:
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"CEA-1.3 evidence directory is empty: {path}.")
    inventory = tuple(
        {"path": str(item.relative_to(path)), "sha256": _sha(item.read_bytes())} for item in files
    )
    return _sha(_canonical_json(inventory))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(value) + b"\n")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _stored_path(value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("CEA-1.3 stored path must be a string.")
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(path)


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
