"""Run the PHP-1 H2 mention and relationship diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_php1_packet import expectation_catalog, packet_cases, render_h2_prompt_reports, run_h2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--mention-report", type=Path, default=None)
    parser.add_argument("--pair-report", type=Path, default=None)
    arguments = parser.parse_args()
    if (arguments.output is None) == (arguments.input is None):
        parser.error("Specify exactly one of --output or --input.")
    if (arguments.mention_report is None) != (arguments.pair_report is None):
        parser.error("Specify both --mention-report and --pair-report together.")
    if arguments.input is not None:
        result = json.loads(arguments.input.read_text(encoding="utf-8"))
    else:
        result = run_h2(arguments.config)
        assert arguments.output is not None
        arguments.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    if arguments.mention_report is not None:
        assert arguments.pair_report is not None
        mention_report, pair_report = render_h2_prompt_reports(
            result,
            expectation_catalog(packet_cases()),
        )
        arguments.mention_report.write_text(mention_report, encoding="utf-8")
        arguments.pair_report.write_text(pair_report, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(arguments.output) if arguments.output is not None else None,
                "input": str(arguments.input) if arguments.input is not None else None,
                "mention_report": str(arguments.mention_report)
                if arguments.mention_report is not None
                else None,
                "pair_report": str(arguments.pair_report)
                if arguments.pair_report is not None
                else None,
            },
            sort_keys=True,
        )
    )
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
