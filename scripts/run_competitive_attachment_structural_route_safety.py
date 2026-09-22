#!/usr/bin/env python3
"""Run the model-free CEA-1.19 Structural Route safety sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_dependency_head_routing as cea118
import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentStructuralSafetyOutcome,
    AttachmentStructuralSafetyReport,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
)
from kotekomi_pipelines.competitive_attachment_structural_route_safety import (
    build_attachment_structural_safety_report,
    render_attachment_structural_safety_handoff,
    render_attachment_structural_safety_review,
    validate_attachment_structural_safety_frozen_inventory,
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
        raise ValueError("CEA-1.19 requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    transfer_root = args.transfer_root.resolve()
    development_root = args.development_root.resolve()
    validation_root = args.validation_root.resolve()
    predecessor = cea118.validate_attachment_residual_transfer_package(transfer_root)
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
    development_matrices = _load_matrices(development_root / "matrices.json")
    validation_matrices = _load_matrices(validation_root / "matrices.json")
    development_oracle = _load_oracle(development_root / "oracle.json")
    validation_oracle = _load_oracle(validation_root / "oracle.json")
    input_references = tuple(
        sorted(
            (
                _reference("cea117_report", transfer_root / "report.json"),
                _reference(
                    "cea117_gold", ROOT / "docs/cea117-residual-ownership-transfer-gold-v1.json"
                ),
                _reference("development_inputs", development_root / "inputs.jsonl"),
                _reference("development_matrices", development_root / "matrices.json"),
                _reference("development_oracle", development_root / "oracle.json"),
                _reference("development_run", development_root / "run.json"),
                _reference("validation_inputs", validation_root / "inputs.jsonl"),
                _reference("validation_matrices", validation_root / "matrices.json"),
                _reference("validation_oracle", validation_root / "oracle.json"),
                _reference("validation_run", validation_root / "run.json"),
            ),
            key=lambda item: item.label,
        )
    )
    report = build_attachment_structural_safety_report(
        evidence=input_references,
        predecessor=predecessor,
        development_matrices=development_matrices,
        development_oracle=development_oracle,
        development_inputs=development_inputs,
        validation_matrices=validation_matrices,
        validation_oracle=validation_oracle,
        validation_inputs=validation_inputs,
    )
    validate_attachment_structural_safety_frozen_inventory(report)
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    status_path = root / "status.json"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        render_attachment_structural_safety_review(report),
        encoding="utf-8",
    )
    package_files = (
        *input_references,
        _reference(
            "application_contract",
            ROOT / "packages/application/src/kotekomi_application/"
            "competitive_attachment_structural_route_safety.py",
        ),
        _reference(
            "pipeline_policy",
            ROOT / "packages/pipelines/src/kotekomi_pipelines/"
            "competitive_attachment_structural_route_safety.py",
        ),
        _reference("report", report_path),
        _reference("review", review_path),
        _reference("runner", Path(__file__)),
        _reference(
            "tdd",
            ROOT / "docs/2026-09-21-competitive-attachment-structural-route-safety.md",
        ),
    )
    handoff_path.write_text(
        render_attachment_structural_safety_handoff(
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
            "schema_version": "attachment_structural_safety_status_v1",
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


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line
    )


def validate_attachment_structural_safety_package(
    root: Path,
) -> AttachmentStructuralSafetyReport:
    """Validate one completed CEA-1.19 package and its independent review."""
    status = _read_json(root / "status.json")
    if (
        status.get("schema_version") != "attachment_structural_safety_status_v1"
        or status.get("status") != "complete"
    ):
        raise ValueError("CEA-1.20 requires a complete CEA-1.19 package.")
    for field, path in (
        ("report_sha256", root / "report.json"),
        ("review_sha256", root / "comparison-review.md"),
        ("handoff_sha256", root / "second-opinion-handoff.md"),
    ):
        if status.get(field) != _sha_file(path):
            raise ValueError(f"CEA-1.19 package digest drifted: {field}.")
    independent_review = root / "claude-opus-review.md"
    if not independent_review.is_file() or not independent_review.read_text().strip():
        raise ValueError("CEA-1.20 requires the completed CEA-1.19 independent review.")
    report = AttachmentStructuralSafetyReport.model_validate_json(
        (root / "report.json").read_bytes()
    )
    validate_attachment_structural_safety_frozen_inventory(report)
    if (
        report.outcome is not AttachmentStructuralSafetyOutcome.SUPPORTED
        or status.get("outcome") != report.outcome.value
        or status.get("result_fingerprint") != report.result_fingerprint
    ):
        raise ValueError("CEA-1.19 outcome or fingerprint chain is invalid.")
    for reference in report.inputs:
        path = Path(reference.path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file() or _sha_file(path) != reference.sha256:
            raise ValueError(f"CEA-1.19 input drifted: {reference.label}.")
    return report


def _load_matrices(path: Path) -> tuple[CompetitiveAttachmentMatrix, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1.19 matrix evidence must be a JSON array.")
    return tuple(
        CompetitiveAttachmentMatrix.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
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


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.19 evidence file is missing: {resolved}.")
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


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


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
