"""Command-line entrypoint for repository-local agent tooling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kotekomi_devtools.goal_accountability import GoalAccountabilityError, write_goal_report
from kotekomi_devtools.receipt_writer import ReceiptWriterError, write_receipt
from kotekomi_devtools.task_budget import audit_task_budget
from kotekomi_devtools.task_ledger import (
    TaskLedgerError,
    current_task,
    next_task,
    task_status,
    update_task_ledger,
)
from kotekomi_devtools.task_lifecycle import check_task_lifecycle
from kotekomi_devtools.task_manifest import validate_task_manifest
from kotekomi_devtools.task_preflight import preflight_task
from kotekomi_devtools.task_retrospective import TaskRetrospectiveError, write_task_retrospective
from kotekomi_devtools.task_scope import audit_task_scope


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
        elif arguments.command == "scope-audit":
            result = audit_task_scope(
                arguments.path,
                base_revision=arguments.base,
                head_revision=arguments.head,
                worktree=arguments.worktree,
            )
            output = result.as_json()
            exit_code = result.exit_code
        elif arguments.command == "lifecycle-check":
            result = check_task_lifecycle(
                arguments.path, phase=arguments.phase, base_revision=arguments.base,
                head_revision=arguments.head, worktree=arguments.worktree,
                records_dir=arguments.records_dir, main_base_revision=arguments.main_base,
                verified_revision=arguments.verified,
            )
            output = result.as_json()
            exit_code = result.exit_code
        elif arguments.command == "write-receipt":
            result = write_receipt(
                task_id=arguments.task_id,
                record_kind=arguments.record_kind,
                result=arguments.result,
                output=arguments.output,
                input_records=arguments.input_record,
                artifacts=arguments.artifact,
                fields=arguments.field,
                force=arguments.force,
            )
            output = result.as_json()
            exit_code = 0
        elif arguments.command == "task-retrospective":
            result = write_task_retrospective(
                arguments.records_dir,
                output=arguments.output,
                markdown=arguments.markdown,
                task_id=arguments.task_id,
                allow_incomplete=arguments.allow_incomplete,
            )
            output = result.as_json()
            exit_code = 0
        elif arguments.command == "goal-check":
            result = write_goal_report(
                arguments.goals_file,
                arguments.records_dir,
                output=arguments.output,
                markdown=arguments.markdown,
            )
            output = result.as_json()
            exit_code = 0 if result.ready else 1
        elif arguments.command == "task-ledger":
            if arguments.task_ledger_command == "current":
                output = current_task(arguments.ledger_file)
            elif arguments.task_ledger_command == "next":
                output = next_task(arguments.ledger_file)
            elif arguments.task_ledger_command == "status":
                output = task_status(arguments.ledger_file, arguments.task_id)
            else:
                result = update_task_ledger(
                    arguments.ledger_file,
                    arguments.task_id,
                    status=arguments.status,
                    evidence=arguments.evidence,
                    output=arguments.output,
                )
                output = result.as_json()
            exit_code = 0
        else:
            result = audit_task_budget(
                arguments.path,
                base_revision=arguments.base,
                head_revision=arguments.head,
                worktree=arguments.worktree,
            )
            output = result.as_json()
            exit_code = result.exit_code
    except ReceiptWriterError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except TaskRetrospectiveError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except GoalAccountabilityError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except TaskLedgerError as error:
        print(
            json.dumps(error.as_json(), ensure_ascii=False, separators=(",", ":"))
        )
        return 1 if error.code == "h9.task.goals_unmet" else 2
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
    scope_audit = subparsers.add_parser(
        "scope-audit", help="Audit one Task Manifest candidate's scope and protected artifacts."
    )
    scope_audit.add_argument("path", type=Path)
    scope_audit.add_argument("--base", required=True)
    mode = scope_audit.add_mutually_exclusive_group(required=True)
    mode.add_argument("--head")
    mode.add_argument("--worktree", action="store_true")
    lifecycle_check = subparsers.add_parser(
        "lifecycle-check", help="Check which task lifecycle checks are currently valid."
    )
    lifecycle_check.add_argument("path", type=Path)
    lifecycle_check.add_argument("--phase", required=True, metavar="{spec,candidate,verified,main}")
    lifecycle_check.add_argument("--base")
    lifecycle_check.add_argument("--head")
    lifecycle_check.add_argument("--worktree", action="store_true")
    lifecycle_check.add_argument("--records-dir", type=Path)
    lifecycle_check.add_argument("--main-base")
    lifecycle_check.add_argument("--verified")
    write_receipt = subparsers.add_parser(
        "write-receipt", help="Write one deterministic task lifecycle receipt."
    )
    write_receipt.add_argument("--task-id", required=True)
    write_receipt.add_argument("--record-kind", required=True)
    write_receipt.add_argument("--result", required=True)
    write_receipt.add_argument("--output", type=Path, required=True)
    write_receipt.add_argument("--input-record", action="append", default=[], metavar="NAME=PATH")
    write_receipt.add_argument("--artifact", action="append", default=[], metavar="NAME=PATH")
    write_receipt.add_argument("--field", action="append", default=[], metavar="KEY=VALUE")
    write_receipt.add_argument("--force", action="store_true")
    task_retrospective = subparsers.add_parser(
        "task-retrospective", help="Write deterministic metrics for task lifecycle records."
    )
    task_retrospective.add_argument("records_dir", type=Path, metavar="RECORDS_DIR")
    task_retrospective.add_argument("--output", type=Path, required=True, metavar="JSON")
    task_retrospective.add_argument("--markdown", type=Path, required=True, metavar="MARKDOWN")
    task_retrospective.add_argument("--task-id")
    task_retrospective.add_argument("--allow-incomplete", action="store_true")
    goal_check = subparsers.add_parser("goal-check", help="Check deterministic goal coverage.")
    goal_check.add_argument("goals_file", type=Path, metavar="GOALS_FILE")
    goal_check.add_argument("--records-dir", type=Path, required=True, metavar="RECORDS_DIR")
    goal_check.add_argument("--output", type=Path, required=True, metavar="JSON")
    goal_check.add_argument("--markdown", type=Path, required=True, metavar="MARKDOWN")
    task_ledger = subparsers.add_parser(
        "task-ledger", help="Read and update deterministic task state."
    )
    task_ledger_commands = task_ledger.add_subparsers(dest="task_ledger_command", required=True)
    current = task_ledger_commands.add_parser("current", help="Print the current task.")
    current.add_argument("ledger_file", type=Path, metavar="LEDGER_FILE")
    next_task_parser = task_ledger_commands.add_parser("next", help="Print the next planned task.")
    next_task_parser.add_argument("ledger_file", type=Path, metavar="LEDGER_FILE")
    status = task_ledger_commands.add_parser("status", help="Print task status and next action.")
    status.add_argument("ledger_file", type=Path, metavar="LEDGER_FILE")
    status.add_argument("task_id", metavar="TASK_ID")
    update = task_ledger_commands.add_parser("update", help="Write one validated task transition.")
    update.add_argument("ledger_file", type=Path, metavar="LEDGER_FILE")
    update.add_argument("task_id", metavar="TASK_ID")
    update.add_argument("--status", required=True)
    update.add_argument("--evidence", type=Path, required=True, metavar="EVIDENCE")
    update.add_argument("--output", type=Path, required=True, metavar="LEDGER_FILE")
    return parser
