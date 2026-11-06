"""Validate IPI operator measurements and decide the declared acceptance route.

This entrypoint is thin: the deterministic behavior lives in
`kotekomi_devtools.ipi_measurement`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kotekomi_devtools.ipi_measurement import (
    MeasurementError,
    compare,
    load_condition_result,
    measure,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipi_measure",
        description="Validate one IPI measurement result or compare two conditions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Validate one condition result file.")
    check.add_argument("--result", type=Path, required=True)
    compare_parser = subparsers.add_parser(
        "compare", help="Compare one baseline and one final condition result."
    )
    compare_parser.add_argument("--baseline", type=Path, required=True)
    compare_parser.add_argument("--final", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "check":
            result = load_condition_result(arguments.result)
            print(
                json.dumps(
                    {
                        "partition": result.partition,
                        "condition": result.condition,
                        "revision": result.revision,
                        "measures": measure(result).as_json(),
                    },
                    sort_keys=True,
                )
            )
            return 0
        baseline = load_condition_result(arguments.baseline)
        final = load_condition_result(arguments.final)
        decision = compare(baseline, final)
        print(
            json.dumps(
                {
                    "baseline": measure(baseline).as_json(),
                    "final": measure(final).as_json(),
                    "decision": decision.as_json(),
                },
                sort_keys=True,
            )
        )
        return 0 if decision.passed else 2
    except MeasurementError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
