"""Run the PHP-1 H2.3 monotonic GLiNER rescue experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from php1_monotonic_gliner_rescue import (
    compact_rescue_summary,
    render_rescue_review_report,
    run_monotonic_rescue,
    validate_baseline_binding,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--review-report", type=Path, required=True)
    arguments = parser.parse_args()
    baseline_bytes = arguments.baseline.read_bytes()
    baseline = json.loads(baseline_bytes)
    baseline_summary = json.loads(arguments.baseline_summary.read_text(encoding="utf-8"))
    validate_baseline_binding(baseline, baseline_summary, baseline_bytes)
    result = run_monotonic_rescue(
        baseline,
        str(baseline_summary["full_report_sha256"]),
        arguments.config,
    )
    report_bytes = (json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    arguments.output.write_bytes(report_bytes)
    if result["status"] == "completed":
        arguments.summary.write_text(
            json.dumps(
                compact_rescue_summary(result, report_bytes),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        arguments.review_report.write_text(
            render_rescue_review_report(result),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": result["status"],
                "selection_status": result.get("selection_status"),
                "output": str(arguments.output),
                "summary": str(arguments.summary),
                "review_report": str(arguments.review_report),
            },
            sort_keys=True,
        )
    )
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
