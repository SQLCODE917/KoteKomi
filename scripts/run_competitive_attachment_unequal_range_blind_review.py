#!/usr/bin/env python3
"""Prepare and evaluate the CEA-1.21 unequal-range blind review."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import run_competitive_attachment_exact_self_routing as cea120
import run_competitive_attachment_structural_route_safety as cea119
from kotekomi_application import (
    AttachmentBlindReviewCatalog,
    AttachmentBlindReviewSubmission,
    AttachmentEvidenceReference,
)
from kotekomi_pipelines.competitive_attachment_unequal_range_blind_review import (
    build_attachment_blind_review_catalog,
    build_attachment_blind_review_report,
    render_attachment_blind_review_comparison,
    render_attachment_blind_review_handoff,
    render_attachment_blind_review_request,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--safety-root", type=Path, required=True)
    prepare.add_argument("--exact-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--run-root", type=Path, required=True)
    evaluate.add_argument("--response", type=Path)
    args = parser.parse_args()
    return {"prepare": _prepare, "evaluate": _evaluate}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.21 requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    safety_root = args.safety_root.resolve()
    exact_root = args.exact_root.resolve()
    structural = cea119.validate_attachment_structural_safety_package(safety_root)
    exact = cea120.validate_attachment_self_routing_package(exact_root)
    if exact.head_aligned_unequal_range_count != 18:
        raise ValueError("CEA-1.21 predecessor unequal-range inventory drifted.")
    inputs = tuple(
        sorted(
            (
                _reference("cea119_claude_review", safety_root / "claude-opus-review.md"),
                _reference("cea119_report", safety_root / "report.json"),
                _reference("cea120_handoff", exact_root / "second-opinion-handoff.md"),
                _reference("cea120_report", exact_root / "report.json"),
            ),
            key=lambda item: item.label,
        )
    )
    catalog = build_attachment_blind_review_catalog(
        inputs=inputs,
        structural_safety=structural,
    )
    observed = (
        catalog.case_count,
        catalog.selected_count,
        catalog.excluded_count,
        catalog.candidate_contains_event_count,
        catalog.event_contains_candidate_count,
        catalog.partial_overlap_count,
        catalog.disjoint_count,
    )
    expected = (18, 13, 5, 16, 1, 1, 0)
    if observed != expected:
        raise ValueError("CEA-1.21 registered blind-review inventory drifted.")
    catalog_path = root / "catalog.json"
    request_path = root / "blind-review-request.md"
    schema_path = root / "blind-review-response.schema.json"
    status_path = root / "status.json"
    _write_json(catalog_path, catalog.model_dump(mode="json"))
    request_path.write_text(render_attachment_blind_review_request(catalog), encoding="utf-8")
    _write_json(schema_path, AttachmentBlindReviewSubmission.model_json_schema())
    _write_json(
        status_path,
        {
            "schema_version": "attachment_blind_review_status_v1",
            "status": "prepared",
            "catalog": str(catalog_path),
            "catalog_sha256": _sha_file(catalog_path),
            "catalog_fingerprint": catalog.catalog_fingerprint,
            "request": str(request_path),
            "request_sha256": _sha_file(request_path),
            "response_schema": str(schema_path),
            "response_schema_sha256": _sha_file(schema_path),
            "response": str(root / "blind-review-response.json"),
        },
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(root),
                "case_count": catalog.case_count,
                "request": str(request_path),
                "response": str(root / "blind-review-response.json"),
            },
            sort_keys=True,
        )
    )
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    status_path = root / "status.json"
    status = _read_json(status_path)
    if (
        status.get("schema_version") != "attachment_blind_review_status_v1"
        or status.get("status") != "prepared"
    ):
        raise ValueError("CEA-1.21 evaluation requires one prepared package.")
    catalog_path = root / "catalog.json"
    request_path = root / "blind-review-request.md"
    schema_path = root / "blind-review-response.schema.json"
    for field, path in (
        ("catalog_sha256", catalog_path),
        ("request_sha256", request_path),
        ("response_schema_sha256", schema_path),
    ):
        if status.get(field) != _sha_file(path):
            raise ValueError(f"CEA-1.21 prepared evidence drifted: {field}.")
    catalog = AttachmentBlindReviewCatalog.model_validate_json(catalog_path.read_bytes())
    if status.get("catalog_fingerprint") != catalog.catalog_fingerprint:
        raise ValueError("CEA-1.21 catalog fingerprint drifted.")
    response_path = (
        args.response.resolve()
        if args.response is not None
        else root / "blind-review-response.json"
    )
    if not response_path.is_file():
        raise ValueError(f"CEA-1.21 blind response is missing: {response_path}.")
    submission = AttachmentBlindReviewSubmission.model_validate_json(response_path.read_bytes())
    report_inputs = (
        *catalog.inputs,
        _reference("blind_request", request_path),
        _reference("blind_response", response_path),
        _reference("catalog", catalog_path),
    )
    report = build_attachment_blind_review_report(
        inputs=tuple(report_inputs),
        catalog=catalog,
        submission=submission,
        response_sha256=_sha_file(response_path),
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_attachment_blind_review_comparison(report), encoding="utf-8")
    package_files = (
        *report_inputs,
        _reference(
            "application_contract",
            ROOT / "packages/application/src/kotekomi_application/"
            "competitive_attachment_unequal_range_blind_review.py",
        ),
        _reference(
            "pipeline_policy",
            ROOT / "packages/pipelines/src/kotekomi_pipelines/"
            "competitive_attachment_unequal_range_blind_review.py",
        ),
        _reference("report", report_path),
        _reference("review", review_path),
        _reference("runner", Path(__file__)),
        _reference(
            "tdd",
            ROOT / "docs/2026-09-21-competitive-attachment-unequal-range-blind-review.md",
        ),
    )
    handoff_path.write_text(
        render_attachment_blind_review_handoff(
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
            "schema_version": "attachment_blind_review_status_v1",
            "status": "complete",
            "outcome": report.outcome.value,
            "result_fingerprint": report.result_fingerprint,
            "catalog": str(catalog_path),
            "catalog_sha256": _sha_file(catalog_path),
            "catalog_fingerprint": catalog.catalog_fingerprint,
            "request": str(request_path),
            "request_sha256": _sha_file(request_path),
            "response": str(response_path),
            "response_sha256": _sha_file(response_path),
            "report": str(report_path),
            "report_sha256": _sha_file(report_path),
            "review": str(review_path),
            "review_sha256": _sha_file(review_path),
            "handoff": str(handoff_path),
            "handoff_sha256": _sha_file(handoff_path),
            "second_opinion_review": str(root / "claude-opus-review.md"),
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
            },
            sort_keys=True,
        )
    )
    return 0


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.21 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_sha_file(resolved),
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"CEA-1.21 expected a JSON object: {path}.")
    return cast(dict[str, Any], value)


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
