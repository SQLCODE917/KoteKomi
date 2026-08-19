"""Command-line entrypoint for repository-local agent tooling."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kotekomi_devtools.candidate_verifier import verify_candidate
from kotekomi_devtools.evidence_catalog import (
    read_index,
    state_root,
    write_canonical_record,
)
from kotekomi_devtools.feature_branch_reconciliation import (
    FeatureBranchReconciliationError,
    reconcile_merged_feature_branch,
)
from kotekomi_devtools.goal_accountability import GoalAccountabilityError, write_goal_report
from kotekomi_devtools.lifecycle_evidence import (
    LifecycleEvidenceError,
    create_feature_branch,
    record_branch_cleanup,
    record_candidate_ci,
    record_candidate_commit,
    record_main_ci,
    record_main_promotion,
)
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
from kotekomi_devtools.tdd_binding import TddBindingError, bind_tdd
from kotekomi_devtools.tdd_metrics import tdd_metrics
from kotekomi_devtools.tdd_scorecards import compare_scorecards, compare_tdds, tdd_score
from kotekomi_devtools.tdd_workflow import implement_tdd
from kotekomi_devtools.verification_plan import VerificationPlanError, write_verification_plan

type JsonObject = dict[str, Any]
type CommandHandler = Callable[[argparse.Namespace], "CliResponse | int"]


@dataclass(frozen=True)
class CliResponse:
    """A command result with its CLI serialization policy."""

    exit_code: int
    output: JsonObject
    ensure_ascii: bool = False
    sort_keys: bool = False


def main(argv: list[str] | None = None) -> int:
    """Run the agent harness command selected by ``argv``."""
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = _build_parser()
    try:
        if raw_argv[:1] == ["run-check"] and "--" in raw_argv:
            response: CliResponse | int = _run_delimited_run_check(raw_argv)
        else:
            response = _dispatch_command(parser.parse_args(raw_argv))
    except StepScriptError as error:
        return _render_error(error)
    except ReceiptWriterError as error:
        return _render_error(error)
    except TddBindingError as error:
        return _render_error(error)
    except TaskRetrospectiveError as error:
        return _render_error(error)
    except GoalAccountabilityError as error:
        return _render_error(error)
    except LifecycleEvidenceError as error:
        return _render_error(error)
    except FeatureBranchReconciliationError as error:
        return _render_error(error)
    except VerificationPlanError as error:
        return _render_error(error)
    except TaskLedgerError as error:
        print(json.dumps(error.as_json(), ensure_ascii=False, separators=(",", ":")))
        return 1 if error.code == "h9.task.goals_unmet" else 2
    except Exception:
        print("kotekomi-agent: internal error", file=sys.stderr)
        return 70

    if isinstance(response, int):
        return response
    return _render_response(response)


def _dispatch_command(arguments: argparse.Namespace) -> CliResponse | int:
    handlers: dict[str, CommandHandler] = {
        "validate-task": _handle_task_command,
        "preflight-task": _handle_task_command,
        "budget-audit": _handle_task_command,
        "scope-audit": _handle_task_command,
        "lifecycle-check": _handle_task_command,
        "step-preflight": _handle_step_command,
        "record-step-failure": _handle_step_command,
        "receipt-chain-status": _handle_receipt_command,
        "write-receipt": _handle_receipt_command,
        "tdd-bind": _handle_tdd_command,
        "evidence-index": _handle_tdd_command,
        "implement-tdd": _handle_tdd_command,
        "tdd-metrics": _handle_tdd_command,
        "tdd-score": _handle_tdd_command,
        "tdd-compare": _handle_tdd_command,
        "task-retrospective": _handle_reporting_command,
        "goal-check": _handle_reporting_command,
        "run-check": _handle_verification_command,
        "verify-checks": _handle_verification_command,
        "verification-plan": _handle_verification_command,
        "verify-candidate": _handle_verification_command,
        "task-ledger": _handle_ledger_command,
        "record-candidate-commit": _handle_lifecycle_evidence_command,
        "record-candidate-ci": _handle_lifecycle_evidence_command,
        "record-main-promotion": _handle_lifecycle_evidence_command,
        "record-main-ci": _handle_lifecycle_evidence_command,
        "record-branch-cleanup": _handle_lifecycle_evidence_command,
        "create-feature-branch": _handle_lifecycle_evidence_command,
        "reconcile-merged-feature-branch": _handle_feature_branch_reconciliation_command,
    }
    return handlers[arguments.command](arguments)


def _handle_task_command(arguments: argparse.Namespace) -> CliResponse:
    if arguments.command == "validate-task":
        result = validate_task_manifest(arguments.path)
        return CliResponse(0 if result.valid else 1, result.as_json())
    if arguments.command == "preflight-task":
        result = preflight_task(arguments.path)
        return CliResponse(0 if result.ready else 1, result.as_json())
    if arguments.command == "budget-audit":
        result = audit_task_budget(
            arguments.path,
            base_revision=arguments.base,
            head_revision=arguments.head,
            worktree=arguments.worktree,
        )
        return CliResponse(result.exit_code, result.as_json())
    if arguments.command == "scope-audit":
        result = audit_task_scope(
            arguments.path,
            base_revision=arguments.base,
            head_revision=arguments.head,
            worktree=arguments.worktree,
        )
        return CliResponse(result.exit_code, result.as_json())
    return _handle_lifecycle_check(arguments)


def _handle_lifecycle_check(arguments: argparse.Namespace) -> CliResponse:
    result = check_task_lifecycle(
        arguments.path,
        phase=arguments.phase,
        base_revision=arguments.base,
        head_revision=arguments.head,
        worktree=arguments.worktree,
        records_dir=arguments.records_dir,
        main_base_revision=arguments.main_base,
        verified_revision=arguments.verified,
    )
    output = result.as_json()
    if arguments.run:
        if not arguments.task_id:
            raise ValueError("lifecycle-check --run requires --task-id")
        evidence_type = (
            "candidate_lifecycle" if arguments.phase == "candidate" else "main_lifecycle"
        )
        output = output | {"ready": result.status == "ready"}
        write_canonical_record(
            state_root(arguments.state_root),
            arguments.task_id,
            arguments.run,
            phase="candidate" if evidence_type == "candidate_lifecycle" else "main",
            evidence_type=evidence_type,
            subject_id="candidate" if evidence_type == "candidate_lifecycle" else "main",
            payload=output,
            producer_command="lifecycle-check",
        )
    return CliResponse(result.exit_code, output)


def _handle_step_command(arguments: argparse.Namespace) -> CliResponse:
    if arguments.command == "step-preflight":
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
        return CliResponse(0 if output.get("status") == "ready" else 1, output)
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
    return CliResponse(0, output)


def _handle_receipt_command(arguments: argparse.Namespace) -> CliResponse | int:
    if arguments.command == "receipt-chain-status":
        return run_receipt_chain_status_command(arguments)
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
    return CliResponse(0, result.as_json())


def _handle_tdd_command(arguments: argparse.Namespace) -> CliResponse:
    if arguments.command == "tdd-bind":
        result = bind_tdd(
            arguments.tdd_path, output=arguments.output, state_root=arguments.state_root
        )
        return CliResponse(result.exit_code, result.as_json())
    if arguments.command == "evidence-index":
        output = read_index(state_root(arguments.state_root), arguments.task_id, arguments.run)
        if arguments.output:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(
                json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n"
            )
        return CliResponse(0, output)
    if arguments.command == "implement-tdd":
        code, output = implement_tdd(
            arguments.tdd_path,
            state_root_path=arguments.state_root,
            output=arguments.output,
            markdown=arguments.markdown,
            new_run=arguments.new_run,
            abandon_run=arguments.abandon_run,
        )
        return CliResponse(code, output)
    if arguments.command == "tdd-metrics":
        code, output = tdd_metrics(
            arguments.tdd_path,
            state_root_path=arguments.state_root,
            run_id=arguments.run,
            latest=arguments.latest,
            output=arguments.output,
            markdown=arguments.markdown,
        )
        return CliResponse(code, output)
    if arguments.command == "tdd-score":
        code, output = tdd_score(
            arguments.tdd_path,
            state_root_path=arguments.state_root,
            run_id=arguments.run,
            latest=arguments.latest,
            output=arguments.output,
            markdown=arguments.markdown,
        )
        return CliResponse(code, output)
    return _handle_tdd_compare(arguments)


def _handle_tdd_compare(arguments: argparse.Namespace) -> CliResponse:
    if arguments.scorecard and arguments.tdd_path:
        return CliResponse(
            1,
            {
                "schema_version": 1,
                "status": "blocked",
                "diagnostics": [
                    {
                        "code": "compare.selector",
                        "location": "/",
                        "rule": "scorecard_and_tdd_path_mutually_exclusive",
                    }
                ],
            },
        )
    if arguments.scorecard:
        code, output = compare_scorecards(
            [Path(item) for item in arguments.scorecard],
            output=arguments.output,
            markdown=arguments.markdown,
            state_root_path=arguments.state_root,
        )
        return CliResponse(code, output)
    code, output = compare_tdds(
        arguments.tdd_path,
        output=arguments.output,
        markdown=arguments.markdown,
        state_root_path=arguments.state_root,
    )
    return CliResponse(code, output)


def _handle_reporting_command(arguments: argparse.Namespace) -> CliResponse:
    if arguments.command == "task-retrospective":
        result = write_task_retrospective(
            arguments.records_dir,
            output=arguments.output,
            markdown=arguments.markdown,
            task_id=arguments.task_id,
            allow_incomplete=arguments.allow_incomplete,
        )
        return CliResponse(0, result.as_json())
    result = write_goal_report(
        arguments.goals_file,
        arguments.records_dir,
        output=arguments.output,
        markdown=arguments.markdown,
    )
    return CliResponse(0 if result.ready else 1, result.as_json())


def _handle_verification_command(arguments: argparse.Namespace) -> CliResponse:
    if arguments.command == "verify-candidate":
        result = verify_candidate(
            arguments.manifest,
            base_revision=arguments.base,
            specification_revision=arguments.specification,
            candidate_revision=arguments.candidate,
            profile=arguments.profile,
            task_id=arguments.task_id,
            run_id=arguments.run,
            state_root_path=arguments.state_root,
        )
        return CliResponse(result.exit_code, result.as_json())
    if arguments.command == "run-check":
        command_argv = tuple(arguments.argv)
        if command_argv[:1] == ("--",):
            command_argv = command_argv[1:]
        return _run_check_response(arguments, command_argv)
    if arguments.command == "verify-checks":
        return _handle_verify_checks(arguments)
    return _handle_verification_plan(arguments)


def _run_delimited_run_check(raw_argv: list[str]) -> CliResponse:
    separator = raw_argv.index("--")
    parser = argparse.ArgumentParser(prog="kotekomi-agent run-check")
    parser.add_argument("check_id", metavar="CHECK_ID")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--run")
    parser.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
    arguments = parser.parse_args(raw_argv[1:separator])
    if arguments.run and not arguments.task_id:
        parser.error("--run requires --task-id")
    return _run_check_response(arguments, tuple(raw_argv[separator + 1 :]))


def _run_check_response(
    arguments: argparse.Namespace, command_argv: tuple[str, ...]
) -> CliResponse:
    from .verification_execution import run_check

    record = run_check(
        arguments.check_id,
        output=Path(arguments.output),
        log=Path(arguments.log),
        argv=command_argv,
    )
    if arguments.run:
        if not arguments.task_id:
            raise ValueError("run-check --run requires --task-id")
        write_canonical_record(
            state_root(arguments.state_root),
            arguments.task_id,
            arguments.run,
            phase="verification",
            evidence_type="run_check",
            subject_id=record.check_id,
            payload=record.as_json() | {"outcome": record.status, "diagnostics": []},
            producer_command="run-check",
        )
    return CliResponse(record.exit_code, record.as_json(), ensure_ascii=True, sort_keys=True)


def _handle_verify_checks(arguments: argparse.Namespace) -> CliResponse:
    from .verification_execution import verify_check_records

    report = verify_check_records(
        Path(arguments.plan_json),
        run_records=tuple(Path(item) for item in arguments.run_record),
        output=Path(arguments.output),
        markdown=Path(arguments.markdown),
    )
    if arguments.run:
        if not arguments.task_id:
            raise ValueError("verify-checks --run requires --task-id")
        report_payload = report.as_json()
        records = report_payload["records"]
        payload = report_payload | {
            "planned_check_count": len(report_payload["planned_check_ids"]),
            "executed_check_count": len(records),
            "verified_check_count": len(report_payload["completed_check_ids"]),
            "failed_check_count": sum(
                1 for record in records if record["status"] != "passed" or record["exit_code"] != 0
            ),
        }
        write_canonical_record(
            state_root(arguments.state_root),
            arguments.task_id,
            arguments.run,
            phase="verification",
            evidence_type="verify_checks",
            subject_id="verify-checks",
            payload=payload,
            producer_command="verify-checks",
        )
    return CliResponse(report.exit_code, report.as_json(), ensure_ascii=True, sort_keys=True)


def _handle_verification_plan(arguments: argparse.Namespace) -> CliResponse:
    result = write_verification_plan(
        arguments.path,
        base_revision=arguments.base,
        head_revision=arguments.head,
        output=arguments.output,
        markdown=arguments.markdown,
    )
    output = result.as_json()
    if arguments.run:
        if not arguments.task_id:
            raise ValueError("verification-plan --run requires --task-id")
        output = output | {"planned_checks": output["checks"]}
        write_canonical_record(
            state_root(arguments.state_root),
            arguments.task_id,
            arguments.run,
            phase="verification",
            evidence_type="verification_plan",
            subject_id="plan",
            payload=output,
            producer_command="verification-plan",
        )
    return CliResponse(result.exit_code, output)


def _handle_ledger_command(arguments: argparse.Namespace) -> CliResponse:
    if arguments.task_ledger_command == "current":
        output = current_task(arguments.ledger_file)
    elif arguments.task_ledger_command == "next":
        output = next_task(arguments.ledger_file)
    elif arguments.task_ledger_command == "status":
        output = task_status(arguments.ledger_file, arguments.task_id)
    else:
        output = update_task_ledger(
            arguments.ledger_file,
            arguments.task_id,
            status=arguments.status,
            evidence=arguments.evidence,
            output=arguments.output,
        ).as_json()
    return CliResponse(0, output)


def _handle_lifecycle_evidence_command(arguments: argparse.Namespace) -> CliResponse:
    common = {
        "task_id": arguments.task_id,
        "run_id": arguments.run,
        "state_root_path": arguments.state_root,
        "output": arguments.output,
        "markdown": arguments.markdown,
    }
    if arguments.command == "record-candidate-commit":
        result = record_candidate_commit(revision=arguments.commit, **common)
    elif arguments.command == "create-feature-branch":
        result = create_feature_branch(
            specification_revision=arguments.specification_revision,
            manifest_sha256=arguments.manifest_sha256,
            **common,
        )
    elif arguments.command == "record-candidate-ci":
        result = record_candidate_ci(ci_result=arguments.ci_result, **common)
    elif arguments.command == "record-main-promotion":
        result = record_main_promotion(revision=arguments.commit, **common)
    elif arguments.command == "record-main-ci":
        result = record_main_ci(ci_result=arguments.ci_result, **common)
    else:
        result = record_branch_cleanup(branches=tuple(arguments.branch), **common)
    return CliResponse(0, result.as_json())


def _handle_feature_branch_reconciliation_command(arguments: argparse.Namespace) -> CliResponse:
    result = reconcile_merged_feature_branch(
        task_id=arguments.task_id,
        run_id=arguments.run,
        promotion=arguments.promotion,
        final_main=arguments.final_main,
        ci_result=arguments.ci_result,
        state_root_path=arguments.state_root,
        output=arguments.output,
        markdown=arguments.markdown,
    )
    return CliResponse(0, result.as_json())


def _render_response(response: CliResponse) -> int:
    print(
        json.dumps(
            response.output,
            ensure_ascii=response.ensure_ascii,
            separators=(",", ":"),
            sort_keys=response.sort_keys,
        )
    )
    return response.exit_code


def _render_error(error: Exception) -> int:
    print(f"kotekomi-agent: {error}", file=sys.stderr)
    return 2


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
    lifecycle_check.add_argument("--task-id")
    lifecycle_check.add_argument("--run")
    lifecycle_check.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
    _add_lifecycle_evidence_parsers(subparsers)
    receipt_chain_status = subparsers.add_parser(
        "receipt-chain-status",
        help="Report deterministic receipt-chain status.",
    )
    receipt_chain_status.add_argument("--task-id", required=True)
    receipt_chain_status.add_argument("--phase", required=True)
    receipt_chain_status.add_argument("--receipt", action="append", default=[])
    receipt_chain_status.add_argument("--expect", action="append", default=[])
    receipt_chain_status.add_argument("--required", action="append", default=[])
    receipt_chain_status.add_argument("--run")
    receipt_chain_status.add_argument("--state-root", default="~/.local/state/kotekomi")
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
    tdd_bind = subparsers.add_parser(
        "tdd-bind", help="Create or read a canonical binding for one local TDD."
    )
    tdd_bind.add_argument("tdd_path", type=Path, metavar="TDD_PATH")
    tdd_bind.add_argument("--output", type=Path, metavar="BINDING_JSON")
    tdd_bind.add_argument(
        "--state-root",
        type=Path,
        default=Path("~/.local/state/kotekomi"),
        metavar="STATE_ROOT",
    )
    evidence_index = subparsers.add_parser(
        "evidence-index", help="Read one canonical run evidence index."
    )
    evidence_index.add_argument("--task-id", required=True)
    evidence_index.add_argument("--run", required=True)
    evidence_index.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
    evidence_index.add_argument("--output", type=Path)
    implement = subparsers.add_parser("implement-tdd", help="Resolve TDD implementation status.")
    implement.add_argument("tdd_path", type=Path)
    mode = implement.add_mutually_exclusive_group()
    mode.add_argument("--new-run", action="store_true")
    mode.add_argument("--abandon-run")
    implement.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
    implement.add_argument("--output", type=Path)
    implement.add_argument("--markdown", type=Path)
    for command, help_text in (
        ("tdd-metrics", "Generate TDD implementation metrics."),
        ("tdd-score", "Generate TDD scorecards."),
    ):
        parser_item = subparsers.add_parser(command, help=help_text)
        parser_item.add_argument("tdd_path", type=Path, nargs="?")
        selector = parser_item.add_mutually_exclusive_group()
        selector.add_argument("--run")
        selector.add_argument("--latest", action="store_true")
        parser_item.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
        parser_item.add_argument("--output", type=Path)
        parser_item.add_argument("--markdown", type=Path)
    compare = subparsers.add_parser("tdd-compare", help="Compare TDD scorecards.")
    compare.add_argument("tdd_path", nargs="*")
    compare.add_argument("--scorecard", action="append", default=[])
    compare.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
    compare.add_argument("--output", type=Path)
    compare.add_argument("--markdown", type=Path)
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
    verification_plan.add_argument("--task-id")
    verification_plan.add_argument("--run")
    verification_plan.add_argument(
        "--state-root", type=Path, default=Path("~/.local/state/kotekomi")
    )
    verify_candidate = subparsers.add_parser(
        "verify-candidate",
        help="Verify one frozen candidate and commit an immutable receipt.",
    )
    verify_candidate.add_argument("--manifest", type=Path, required=True)
    verify_candidate.add_argument("--base", required=True)
    verify_candidate.add_argument("--specification", required=True)
    verify_candidate.add_argument("--candidate", required=True)
    verify_candidate.add_argument(
        "--profile", required=True, choices=("portable-local", "authoritative-linux")
    )
    verify_candidate.add_argument("--task-id")
    verify_candidate.add_argument("--run")
    verify_candidate.add_argument("--state-root", type=Path)
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
    run_check_parser.add_argument("--task-id")
    run_check_parser.add_argument("--run")
    run_check_parser.add_argument(
        "--state-root", type=Path, default=Path("~/.local/state/kotekomi")
    )
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
    verify_checks_parser.add_argument("--task-id")
    verify_checks_parser.add_argument("--run")
    verify_checks_parser.add_argument(
        "--state-root", type=Path, default=Path("~/.local/state/kotekomi")
    )

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


def _add_lifecycle_evidence_parsers(subparsers: Any) -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--task-id", required=True)
    common.add_argument("--run", required=True)
    common.add_argument("--state-root", type=Path, default=Path("~/.local/state/kotekomi"))
    common.add_argument("--output", type=Path)
    common.add_argument("--markdown", type=Path)
    candidate_commit = subparsers.add_parser(
        "record-candidate-commit",
        parents=[common],
        help="Record one candidate commit as canonical evidence.",
    )
    candidate_commit.add_argument("--commit", required=True)
    feature_branch = subparsers.add_parser(
        "create-feature-branch",
        parents=[common],
        help="Create and push the canonical task feature branch.",
    )
    feature_branch.add_argument("manifest", type=Path)
    feature_branch.add_argument("--specification-revision", required=True)
    feature_branch.add_argument("--manifest-sha256", required=True)
    candidate_ci = subparsers.add_parser(
        "record-candidate-ci",
        parents=[common],
        help="Record one candidate CI result as canonical evidence.",
    )
    candidate_ci.add_argument("--ci-result", type=Path, required=True)
    main_promotion = subparsers.add_parser(
        "record-main-promotion",
        parents=[common],
        help="Record one main promotion as canonical evidence.",
    )
    main_promotion.add_argument("--commit", required=True)
    main_ci = subparsers.add_parser(
        "record-main-ci", parents=[common], help="Record one main CI result as canonical evidence."
    )
    main_ci.add_argument("--ci-result", type=Path, required=True)
    cleanup = subparsers.add_parser(
        "record-branch-cleanup",
        parents=[common],
        help="Record requested candidate branch cleanup evidence.",
    )
    cleanup.add_argument("--branch", action="append", default=[])
    reconciliation = subparsers.add_parser(
        "reconcile-merged-feature-branch",
        parents=[common],
        help="Close one eligible feature branch that already reached main.",
    )
    reconciliation.add_argument("--promotion", required=True)
    reconciliation.add_argument("--final-main", required=True)
    reconciliation.add_argument("--ci-result", type=Path, required=True)
