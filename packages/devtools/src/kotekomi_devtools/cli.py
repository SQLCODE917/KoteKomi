"""Command-line entrypoint for repository-local agent tooling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kotekomi_devtools.task_manifest import validate_task_manifest
from kotekomi_devtools.task_preflight import preflight_task


def main(argv: list[str] | None = None) -> int:
    """Run the agent harness command selected by ``argv``."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "validate-task":
            result = validate_task_manifest(arguments.path)
            output = result.as_json()
            exit_code = 0 if result.valid else 1
        else:
            result = preflight_task(arguments.path)
            output = result.as_json()
            exit_code = 0 if result.ready else 1
    except Exception:
        print("kotekomi-agent: internal error", file=sys.stderr)
        return 70

    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return exit_code


def entrypoint() -> None:
    """Run the console command and provide its process exit status."""
    raise SystemExit(main())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kotekomi-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_task = subparsers.add_parser("validate-task", help="Validate one Task Manifest.")
    validate_task.add_argument("path", type=Path)
    preflight_task_parser = subparsers.add_parser(
        "preflight-task", help="Check whether one Task Manifest is ready to begin."
    )
    preflight_task_parser.add_argument("path")
    return parser
