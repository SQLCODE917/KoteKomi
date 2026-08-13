"""Command-line entrypoint for repository-local agent tooling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kotekomi_devtools.goal_accountability import GoalAccountabilityError, write_goal_report
from kotekomi_devtools.receipt_chain_status import run_receipt_chain_status_command
from kotekomi_devtools.receipt_writer import ReceiptWriterError, write_receipt
from kotekomi_devtools.step_scripts import (
    StepScriptError,
    record_step_failure,
    step_preflight_payload,
    write_step_json,
)
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
from kotekomi_devtools.verification_plan import VerificationPlanError, write_verification_plan


def main(argv: list[str] | None = None) -> int:
    """Run the agent harness command selected by ``argv``."""
    raw_argv = list(argv) if argv is not None else None
    if raw_argv is None:
        import sys as _sys

        raw_argv = _sys.argv[1:]
    if raw_argv[:1] == ["run-check"] and "--" in raw_argv:
        separator = raw_argv.index("--")
        import json as _json

        from .verification_execution import run_check

        run_parser = argparse.ArgumentParser(prog="kotekomi-agent run-check")
        run_parser.add_argument("check_id", metavar="CHECK_ID")
        run_parser.add_argument("--output", type=Path, required=True)
        run_parser.add_argument("--log", type=Path, required=True)
        run_args = run_parser.parse_args(raw_argv[1:separator])
        record = run_check(
            run_args.check_id,
            output=run_args.output,
            log=run_args.log,
            argv=tuple(raw_argv[separator + 1 :]),
        )
        print(_json.dumps(record.as_json(), separators=(",", ":"), sort_keys=True))
        return record.exit_code

    parser = _build_parser()
    arguments = parser.parse_args(raw_argv)
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
        elif arguments.command == "step-preflight":
            output = step_preflight_payload(
                task_id=arguments.task_id,
                base=arguments.base,
                branch=arguments.branch,
                expected_origin_main=arguments.expected_origin_main,
                origin_main_ref=arguments.origin_main_ref,
                remote_branches=arguments.remote_branch,
                state_file=arguments.state_file,
                cwd=arguments.cwd,
                recover_candidate=arguments.recover_candidate,
                allow_dirty_main=arguments.allow_dirty_main,
            )
            write_step_json(output, arguments.output, force=True)
            exit_code = 0 if output.get("status") == "ready" else 1
        elif arguments.command == "record-step-failure":
            output = record_step_failure(
                task_id=arguments.task_id,
                step=arguments.step,
                reason=arguments.reason,
                output=arguments.output,
                log=arguments.log,
                state_file=arguments.state_file,
                cwd=arguments.cwd,
                origin_main_ref=arguments.origin_main_ref,
                force=arguments.force,
            )
            exit_code = 0
        elif arguments.command == "receipt-chain-status":
            return run_receipt_chain_status_command(arguments)
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
        elif arguments.command == "run-check":
            import json as _json
            from pathlib import Path as _Path

            from .verification_execution import run_check

            command_argv = tuple(arguments.argv)
            if command_argv[:1] == ("--",):
                command_argv = command_argv[1:]
            record = run_check(
                arguments.check_id,
                output=_Path(arguments.output),
                log=_Path(arguments.log),
                argv=command_argv,
            )
            print(_json.dumps(record.as_json(), separators=(",", ":"), sort_keys=True))
            return record.exit_code
        elif arguments.command == "verify-checks":
            import json as _json
            from pathlib import Path as _Path

            from .verification_execution import verify_check_records

            report = verify_check_records(
                _Path(arguments.plan_json),
                run_records=tuple(_Path(item) for item in arguments.run_record),
                output=_Path(arguments.output),
                markdown=_Path(arguments.markdown),
            )
            print(_json.dumps(report.as_json(), separators=(",", ":"), sort_keys=True))
            return report.exit_code
        elif arguments.command == "verification-plan":
            result = write_verification_plan(
                arguments.path,
                base_revision=arguments.base,
                head_revision=arguments.head,
                output=arguments.output,
                markdown=arguments.markdown,
            )
            output = result.as_json()
            exit_code = result.exit_code
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
    except StepScriptError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except ReceiptWriterError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except TaskRetrospectiveError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except GoalAccountabilityError as error:
        print(f"kotekomi-agent: {error}", file=sys.stderr)
        return 2
    except VerificationPlanError as error:
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
    receipt_chain_status = subparsers.add_parser(
        "receipt-chain-status",
        help="Report deterministic receipt-chain status.",
    )
    receipt_chain_status.add_argument("--task-id", required=True)
    receipt_chain_status.add_argument("--phase", required=True)
    receipt_chain_status.add_argument("--receipt", action="append", default=[])
    receipt_chain_status.add_argument("--expect", action="append", default=[])
    receipt_chain_status.add_argument("--required", action="append", default=[])
    receipt_chain_status.add_argument("--state-root", default="~/.local/state/kotekomi/experiments")
    receipt_chain_status.add_argument("--output")
    receipt_chain_status.add_argument("--markdown")

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
    verification_plan = subparsers.add_parser(
        "verification-plan", help="Plan deterministic local checks for one revision range."
    )
    verification_plan.add_argument("path", type=Path, metavar="MANIFEST")
    verification_plan.add_argument("--base", required=True, metavar="BASE")
    verification_plan.add_argument("--head", required=True, metavar="HEAD")
    verification_plan.add_argument("--output", type=Path, required=True, metavar="JSON")
    verification_plan.add_argument("--markdown", type=Path, required=True, metavar="MARKDOWN")
    step_preflight = subparsers.add_parser(
        "step-preflight", help="Record deterministic local step preflight state."
    )
    step_preflight.add_argument("--task-id", required=True)
    step_preflight.add_argument("--base", required=True)
    step_preflight.add_argument("--branch", required=True)
    step_preflight.add_argument("--expected-origin-main")
    step_preflight.add_argument("--origin-main-ref", default="origin/main")
    step_preflight.add_argument("--remote-branch", action="append", default=[])
    step_preflight.add_argument("--state-file", type=Path)
    step_preflight.add_argument("--output", type=Path)
    step_preflight.add_argument("--cwd", type=Path, default=Path("."))
    step_preflight.add_argument("--recover-candidate", action="store_true")
    step_preflight.add_argument("--allow-dirty-main", action="store_true")

    record_step_failure_parser = subparsers.add_parser(
        "record-step-failure",
        help="Write a deterministic failed local generated-step record.",
    )
    record_step_failure_parser.add_argument("--task-id", required=True)
    record_step_failure_parser.add_argument("--step", required=True)
    record_step_failure_parser.add_argument("--reason", required=True)
    record_step_failure_parser.add_argument("--output", type=Path, required=True)
    record_step_failure_parser.add_argument("--log", type=Path)
    record_step_failure_parser.add_argument("--state-file", type=Path)
    record_step_failure_parser.add_argument(
        "--cwd",
        type=Path,
        default=Path("."),
    )
    record_step_failure_parser.add_argument(
        "--origin-main-ref",
        default="origin/main",
    )
    record_step_failure_parser.add_argument("--force", action="store_true")

    run_check_parser = subparsers.add_parser(
        "run-check",
        help="Run one verification check and record its execution.",
    )
    run_check_parser.add_argument("check_id", metavar="CHECK_ID")
    run_check_parser.add_argument("--output", required=True, help="Path to check record JSON.")
    run_check_parser.add_argument("--log", required=True, help="Path to combined check log.")
    run_check_parser.add_argument("argv", nargs="*", metavar="COMMAND")

    verify_checks_parser = subparsers.add_parser(
        "verify-checks",
        help="Verify check run records against a verification plan.",
    )
    verify_checks_parser.add_argument("plan_json", metavar="PLAN_JSON")
    verify_checks_parser.add_argument(
        "--run-record",
        action="append",
        default=[],
        help="Path to one check run record JSON.",
    )
    verify_checks_parser.add_argument("--output", required=True, help="Path to JSON report.")
    verify_checks_parser.add_argument("--markdown", required=True, help="Path to Markdown report.")

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
