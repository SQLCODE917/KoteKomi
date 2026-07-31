"""Command-line entrypoint for repository-local agent tooling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kotekomi_devtools.task_budget import audit_task_budget
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
        elif arguments.command == "preflight-task":
            result = preflight_task(arguments.path)
            output = result.as_json()
            exit_code = 0 if result.ready else 1
        else:
            result = audit_task_budget(
                arguments.path,
                base_revision=arguments.base,
                head_revision=arguments.head,
                worktree=arguments.worktree,
            )
            output = result.as_json()
            exit_code = result.exit_code
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
    budget_audit = subparsers.add_parser(
        "budget-audit", help="Audit one Task Manifest candidate against its task budget."
    )
    budget_audit.add_argument("path", type=Path)
    budget_audit.add_argument("--base", required=True)
    mode = budget_audit.add_mutually_exclusive_group(required=True)
    mode.add_argument("--head")
    mode.add_argument("--worktree", action="store_true")
    return parser
