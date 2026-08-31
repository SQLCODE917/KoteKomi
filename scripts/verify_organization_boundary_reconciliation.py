"""Run ORG-R1 reconciliation over one pinned proposal report and Gold catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from organization_boundary_reconciliation_evaluation import (
    canonical_evaluation_json,
    evaluate_boundary_reconciliation,
    render_boundary_review,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEVELOPMENT_CATALOG = ROOT / "docs/php1-organization-mention-gold-v1.json"
DEFAULT_HELD_OUT_CATALOG = ROOT / "docs/organization-mention-held-out-gold-v1.json"


def run(
    proposal_report_path: Path,
    catalog_path: Path,
    *,
    phase: str,
) -> dict[str, Any]:
    proposal_bytes = proposal_report_path.read_bytes()
    catalog_bytes = catalog_path.read_bytes()
    proposal = cast(dict[str, Any], json.loads(proposal_bytes))
    catalog = cast(dict[str, Any], json.loads(catalog_bytes))
    catalog_sha256 = hashlib.sha256(catalog_bytes).hexdigest()
    if proposal.get("catalog_sha256") != catalog_sha256:
        raise ValueError("Proposal report catalog digest does not match the selected Gold catalog.")
    bound_segments = proposal.get("catalog")
    if not isinstance(bound_segments, list):
        raise ValueError("Proposal report must preserve its source-bound Gold catalog mapping.")
    raw_bound_segments = cast(list[object], bound_segments)
    if any(not isinstance(segment, dict) for segment in raw_bound_segments):
        raise ValueError("Proposal report Gold catalog segments must be objects.")
    evaluation_catalog: dict[str, Any] = {
        **catalog,
        "segments": cast(list[dict[str, Any]], raw_bound_segments),
    }
    return evaluate_boundary_reconciliation(
        proposal,
        evaluation_catalog,
        phase=phase,
        proposal_report_sha256=hashlib.sha256(proposal_bytes).hexdigest(),
        catalog_sha256=catalog_sha256,
    )


def ensure_output_available(output_path: Path, phase: str) -> None:
    if phase == "held_out" and output_path.exists():
        raise FileExistsError(
            "Held-out ORG-R1 output already exists; the sealed evaluation cannot be overwritten."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("development", "held_out"), required=True)
    parser.add_argument("--proposal-report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-report", type=Path, required=True)
    arguments = parser.parse_args()
    catalog = arguments.catalog or (
        DEFAULT_DEVELOPMENT_CATALOG
        if arguments.phase == "development"
        else DEFAULT_HELD_OUT_CATALOG
    )
    ensure_output_available(arguments.output, arguments.phase)
    result = run(arguments.proposal_report, catalog, phase=arguments.phase)
    arguments.output.write_text(canonical_evaluation_json(result), encoding="utf-8")
    arguments.review_report.write_text(render_boundary_review(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "selection_status": result["selection_status"],
                "output": str(arguments.output),
                "review_report": str(arguments.review_report),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
