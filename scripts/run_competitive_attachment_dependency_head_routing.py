#!/usr/bin/env python3
"""Run the model-free CEA-1.18 dependency-head routing diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentResidualTransferOutcome,
    AttachmentResidualTransferPreflight,
    AttachmentResidualTransferReport,
)
from kotekomi_pipelines.competitive_attachment_dependency_head_routing import (
    build_dependency_head_routing_report,
    render_dependency_head_routing_handoff,
    render_dependency_head_routing_review,
)
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transfer-root", type=Path, required=True)
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    return _run(parser.parse_args())


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.18 requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    transfer_root = args.transfer_root.resolve()
    development_root = args.development_root.resolve()
    validation_root = args.validation_root.resolve()
    predecessor = validate_attachment_residual_transfer_package(transfer_root)
    for phase, evidence_root in (
        ("development", development_root),
        ("validation", validation_root),
    ):
        cea14.validate_competitive_attachment_phase_evidence(
            evidence_root,
            expected_phase=cast(Literal["development", "validation"], phase),
        )
    development_inputs = _load_inputs(development_root / "inputs.jsonl")
    validation_inputs = _load_inputs(validation_root / "inputs.jsonl")
    input_references = tuple(
        sorted(
            (
                _reference("cea117_claude_review", transfer_root / "claude-opus-review.md"),
                _reference("cea117_preflight", transfer_root / "preflight.json"),
                _reference("cea117_report", transfer_root / "report.json"),
                _reference("cea117_review", transfer_root / "comparison-review.md"),
                _reference("development_run", development_root / "run.json"),
                _reference("development_inputs", development_root / "inputs.jsonl"),
                _reference("development_state", development_root / "canonical-state.json"),
                _reference("validation_run", validation_root / "run.json"),
                _reference("validation_inputs", validation_root / "inputs.jsonl"),
                _reference("validation_state", validation_root / "canonical-state.json"),
            ),
            key=lambda item: item.label,
        )
    )
    report = build_dependency_head_routing_report(
        inputs=input_references,
        predecessor=predecessor,
        development_inputs=development_inputs,
        validation_inputs=validation_inputs,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    status_path = root / "status.json"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_dependency_head_routing_review(report), encoding="utf-8")
    package_files = (
        *input_references,
        _reference(
            "application_contract",
            ROOT / "packages/application/src/kotekomi_application/"
            "competitive_attachment_dependency_head_routing.py",
        ),
        _reference(
            "pipeline_policy",
            ROOT / "packages/pipelines/src/kotekomi_pipelines/"
            "competitive_attachment_dependency_head_routing.py",
        ),
        _reference("report", report_path),
        _reference("review", review_path),
        _reference("runner", Path(__file__)),
        _reference(
            "tdd", ROOT / "docs/2026-09-21-competitive-attachment-dependency-head-routing.md"
        ),
    )
    handoff_path.write_text(
        render_dependency_head_routing_handoff(
            report,
            package_files=package_files,
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_git_revision(),
        ),
        encoding="utf-8",
    )
    _write_json(
        status_path,
        {
            "schema_version": "attachment_head_routing_status_v1",
            "status": "complete",
            "outcome": report.outcome.value,
            "result_fingerprint": report.result_fingerprint,
            "report": str(report_path),
            "report_sha256": _sha_file(report_path),
            "review": str(review_path),
            "review_sha256": _sha_file(review_path),
            "handoff": str(handoff_path),
            "handoff_sha256": _sha_file(handoff_path),
            "claude_review": str(root / "claude-opus-review.md"),
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "outcome": report.outcome.value,
                "run_root": str(root),
                "report": str(report_path),
                "review": str(review_path),
                "handoff": str(handoff_path),
                "claude_review": str(root / "claude-opus-review.md"),
                "model_execution_count": report.model_execution_count,
            },
            sort_keys=True,
        )
    )
    return 0


def validate_attachment_residual_transfer_package(
    root: Path,
) -> AttachmentResidualTransferReport:
    metadata = _read_json(root / "run.json")
    if (
        metadata.get("schema_version") != "attachment_residual_transfer_run_v1"
        or metadata.get("status") != "complete"
    ):
        raise ValueError("CEA-1.18 requires a complete CEA-1.17 run.")
    paths = {
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
        "preflight_file_sha256": root / "preflight.json",
    }
    for field, path in paths.items():
        if metadata.get(field) != _sha_file(path):
            raise ValueError(f"CEA-1.17 package digest drifted: {field}.")
    review_path = root / "claude-opus-review.md"
    if not review_path.is_file() or not review_path.read_text(encoding="utf-8").strip():
        raise ValueError("CEA-1.18 requires the completed CEA-1.17 independent review.")
    preflight = AttachmentResidualTransferPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentResidualTransferReport.model_validate_json(
        (root / "report.json").read_bytes()
    )
    if (
        report.outcome is not AttachmentResidualTransferOutcome.MIXED
        or report.preflight_fingerprint != preflight.result_fingerprint
        or metadata.get("preflight_fingerprint") != preflight.result_fingerprint
        or metadata.get("report_fingerprint") != report.result_fingerprint
    ):
        raise ValueError("CEA-1.17 fingerprint or outcome chain is invalid.")
    for reference in (*report.inputs, preflight.prompt):
        _validate_reference(reference)
    for reference in preflight.inputs:
        if reference.label == "tdd":
            if not Path(reference.path).is_file():
                raise ValueError("CEA-1.17 historical TDD path is missing.")
            continue
        _validate_reference(reference)
    return report


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line
    )


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file() or _sha_file(path) != reference.sha256:
        raise ValueError(f"CEA-1.18 input drifted: {reference.label}.")


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.18 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_sha_file(resolved),
    )


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
