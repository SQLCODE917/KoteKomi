"""Command-line entrypoint for repository-local agent tooling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kotekomi_devtools.task_manifest import validate_task_manifest


def main(argv: list[str] | None = None) -> int:
    """Run the agent harness command selected by ``argv``."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        result = validate_task_manifest(arguments.path)
    except Exception:
        print("kotekomi-agent: internal error", file=sys.stderr)
        return 70

    print(json.dumps(result.as_json(), ensure_ascii=False, separators=(",", ":")))
    return 0 if result.valid else 1


def entrypoint() -> None:
    """Run the console command and provide its process exit status."""
    raise SystemExit(main())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kotekomi-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_task = subparsers.add_parser("validate-task", help="Validate one Task Manifest.")
    validate_task.add_argument("path", type=Path)
    return parser
