"""Run the PHP-1 H1 held-out prompt-calibration replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_php1_packet import run_h1, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    result = run_h1(arguments.config)
    if arguments.output is not None:
        arguments.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    **summary(result),
                    "h1_scorecard": result["h1_scorecard"],
                    "output": str(arguments.output),
                },
                sort_keys=True,
            )
        )
        return
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
