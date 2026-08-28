"""Run or summarize the policy-aligned PHP-1 corrected baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from php1_corrected_baseline import compact_baseline_summary, run_corrected_baseline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--span-input", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    arguments = parser.parse_args()
    span_comparison = (
        json.loads(arguments.span_input.read_text(encoding="utf-8"))
        if arguments.span_input is not None
        else None
    )
    result = run_corrected_baseline(arguments.config, span_comparison=span_comparison)
    report_bytes = (json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    arguments.output.write_bytes(report_bytes)
    if result["status"] == "completed":
        summary = compact_baseline_summary(result, report_bytes)
        arguments.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(arguments.output),
                "summary": str(arguments.summary),
            },
            sort_keys=True,
        )
    )
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
