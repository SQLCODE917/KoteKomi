#!/usr/bin/env python3
"""Run the model-free CEA-1.20 exact Event self-attachment evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import run_competitive_attachment_dependency_head_routing as cea118
import run_competitive_attachment_structural_route_safety as cea119
from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentSelfRoutingOutcome,
    AttachmentSelfRoutingReport,
    AttachmentStructuralSafetyReport,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
)
from kotekomi_pipelines.competitive_attachment_exact_self_routing import (
    build_attachment_self_routing_report,
    render_attachment_self_routing_handoff,
    render_attachment_self_routing_review,
)
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transfer-root", type=Path, required=True)
    parser.add_argument("--safety-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    return _run(parser.parse_args())


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.20 requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    transfer_root = args.transfer_root.resolve()
    safety_root = args.safety_root.resolve()
    residual_transfer = cea118.validate_attachment_residual_transfer_package(transfer_root)
    structural_safety = cea119.validate_attachment_structural_safety_package(safety_root)
    development_inputs_path = _input_path(structural_safety, "development_inputs")
    development_matrices_path = _input_path(structural_safety, "development_matrices")
    development_oracle_path = _input_path(structural_safety, "development_oracle")
    validation_inputs_path = _input_path(structural_safety, "validation_inputs")
    validation_matrices_path = _input_path(structural_safety, "validation_matrices")
    validation_oracle_path = _input_path(structural_safety, "validation_oracle")
    development_inputs = _load_inputs(development_inputs_path)
    validation_inputs = _load_inputs(validation_inputs_path)
    evidence = tuple(
        sorted(
            (
                _reference("cea117_claude_review", transfer_root / "claude-opus-review.md"),
                _reference("cea117_report", transfer_root / "report.json"),
                _reference("cea119_claude_review", safety_root / "claude-opus-review.md"),
                _reference("cea119_report", safety_root / "report.json"),
                _reference("development_inputs", development_inputs_path),
                _reference("development_matrices", development_matrices_path),
                _reference("development_oracle", development_oracle_path),
                _reference("validation_inputs", validation_inputs_path),
                _reference("validation_matrices", validation_matrices_path),
                _reference("validation_oracle", validation_oracle_path),
            ),
            key=lambda item: item.label,
        )
    )
    report = build_attachment_self_routing_report(
        evidence=evidence,
        residual_transfer=residual_transfer,
        structural_safety=structural_safety,
        development_matrices=_load_matrices(development_matrices_path),
        development_oracle=_load_oracle(development_oracle_path),
        development_source_text_by_event=_source_text_by_event(development_inputs),
        validation_matrices=_load_matrices(validation_matrices_path),
        validation_oracle=_load_oracle(validation_oracle_path),
        validation_source_text_by_event=_source_text_by_event(validation_inputs),
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    status_path = root / "status.json"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_attachment_self_routing_review(report), encoding="utf-8")
    package_files = (
        *evidence,
        _reference(
            "application_contract",
            ROOT / "packages/application/src/kotekomi_application/"
            "competitive_attachment_exact_self_routing.py",
        ),
        _reference(
            "pipeline_policy",
            ROOT / "packages/pipelines/src/kotekomi_pipelines/"
            "competitive_attachment_exact_self_routing.py",
        ),
        _reference("report", report_path),
        _reference("review", review_path),
        _reference("runner", Path(__file__)),
        _reference(
            "tdd",
            ROOT / "docs/2026-09-21-competitive-attachment-exact-self-routing.md",
        ),
    )
    handoff_path.write_text(
        render_attachment_self_routing_handoff(
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
            "schema_version": "attachment_self_routing_status_v1",
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


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.20 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_sha_file(resolved),
    )


def validate_attachment_self_routing_package(root: Path) -> AttachmentSelfRoutingReport:
    """Validate one completed corrected CEA-1.20 package."""
    status = _read_json(root / "status.json")
    if (
        status.get("schema_version") != "attachment_self_routing_status_v1"
        or status.get("status") != "complete"
    ):
        raise ValueError("CEA-1.21 requires a complete CEA-1.20 package.")
    for field, path in (
        ("report_sha256", root / "report.json"),
        ("review_sha256", root / "comparison-review.md"),
        ("handoff_sha256", root / "second-opinion-handoff.md"),
    ):
        if status.get(field) != _sha_file(path):
            raise ValueError(f"CEA-1.20 package digest drifted: {field}.")
    report = AttachmentSelfRoutingReport.model_validate_json((root / "report.json").read_bytes())
    if (
        report.outcome is not AttachmentSelfRoutingOutcome.SUPPORTED
        or status.get("outcome") != report.outcome.value
        or status.get("result_fingerprint") != report.result_fingerprint
        or report.all_edge_count != 935
        or report.exact_self_count != 40
        or report.unequal_range_count != 895
    ):
        raise ValueError("CEA-1.20 outcome, fingerprint, or inventory is invalid.")
    for reference in report.inputs:
        path = Path(reference.path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file() or _sha_file(path) != reference.sha256:
            raise ValueError(f"CEA-1.20 input drifted: {reference.label}.")
    return report


def _input_path(report: AttachmentStructuralSafetyReport, label: str) -> Path:
    matches = tuple(item for item in report.inputs if item.label == label)
    if len(matches) != 1:
        raise ValueError(f"CEA-1.20 requires one CEA-1.19 {label} reference.")
    path = Path(matches[0].path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file() or _sha_file(path) != matches[0].sha256:
        raise ValueError(f"CEA-1.20 CEA-1.19 input drifted: {label}.")
    return path.resolve()


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line
    )


def _load_matrices(path: Path) -> tuple[CompetitiveAttachmentMatrix, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1.20 matrix evidence must be a JSON array.")
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


def _source_text_by_event(
    inputs: tuple[EventEntityExperimentInput, ...],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in inputs:
        previous = values.setdefault(item.event.id, item.source_text)
        if previous != item.source_text:
            raise ValueError("CEA-1.20 Event source text is not stable.")
    return values


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"CEA-1.20 expected a JSON object: {path}.")
    return cast(dict[str, Any], value)


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
