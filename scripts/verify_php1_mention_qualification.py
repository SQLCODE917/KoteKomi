"""Run the PHP-1 H2.2 Organization mention qualification evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from php1_diagnostic_support import run_qwen_qualifications_for_packet
from php1_mention_qualification_evaluation import (
    assemble_report,
    build_fused_candidate_runs,
    render_review_report,
)
from verify_php1_packet import expectation_catalog, packet_cases
from verify_php1_span_proposers import run as run_span_comparison


def _write_checkpoint(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(
    config_path: Path | None = None,
    comparison_input: Path | None = None,
    qualification_input: Path | None = None,
    qualification_checkpoint: Path | None = None,
) -> dict[str, Any]:
    cases = packet_cases()
    comparison = (
        json.loads(comparison_input.read_text(encoding="utf-8"))
        if comparison_input is not None
        else run_span_comparison(config_path)
    )
    if comparison["status"] != "completed":
        return comparison
    if comparison.get("schema_version") != "php1_span_proposer_comparison_v1":
        raise ValueError("H2.2 comparison input schema does not match H2.1.")
    representation_value = comparison.get("representations")
    if not isinstance(representation_value, dict):
        raise ValueError("H2.2 comparison input lacks representation identities.")
    representations = {
        str(key): str(value) for key, value in cast(dict[str, object], representation_value).items()
    }
    candidate_runs = build_fused_candidate_runs(comparison, representations)
    qualification = (
        json.loads(qualification_input.read_text(encoding="utf-8"))
        if qualification_input is not None
        else run_qwen_qualifications_for_packet(
            config_path,
            cases,
            expectation_catalog(cases),
            candidate_runs,
            checkpoint=(lambda value: _write_checkpoint(qualification_checkpoint, value))
            if qualification_checkpoint is not None
            else None,
        )
    )
    return assemble_report(
        comparison,
        tuple(cast(list[dict[str, Any]], comparison["catalog"])),
        qualification,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--comparison-input", type=Path, default=None)
    parser.add_argument("--qualification-input", type=Path, default=None)
    parser.add_argument("--qualification-checkpoint", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-report", type=Path, required=True)
    arguments = parser.parse_args()
    qualification_checkpoint = arguments.qualification_checkpoint
    if qualification_checkpoint is None and arguments.qualification_input is None:
        qualification_checkpoint = arguments.output.with_suffix(".qualification.json")
    result = run(
        arguments.config,
        arguments.comparison_input,
        arguments.qualification_input,
        qualification_checkpoint,
    )
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if result["status"] == "completed":
        arguments.review_report.write_text(render_review_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "selection_status": result.get("selection_status"),
                "output": str(arguments.output),
                "review_report": str(arguments.review_report),
            },
            sort_keys=True,
        )
    )
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
