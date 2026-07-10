import json
from pathlib import Path
from typing import Any, cast

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ProposedChange, ReviewStatus
from kotekomi_pipelines.cli import main

from packages.pipelines.tests.review_helpers import approve_proposed_changes_in_review_order

SOURCE_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
MODEL_OUTPUT_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)


def test_pipeline_status_and_next_walk_fixture_article_pipeline(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"

    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()

    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "ready_for_source_ingest"
    assert status["next_command"] == "kotekomi source add-file <path>"
    assert status["next_command_plan"]["ready_to_execute"] is False
    assert status["next_command_plan"]["missing_inputs"][0]["name"] == "source_file_path"
    next_step = pipeline_next_json(ledger_path, capsys)
    assert next_step["command"] == "kotekomi source add-file <path>"
    assert next_step["blocked"] is False
    assert next_step["command_plan"]["ready_to_execute"] is False

    next_step = pipeline_next_json(
        ledger_path,
        capsys,
        archive_path=archive_path,
        source_file_path=SOURCE_FIXTURE_PATH,
    )
    assert next_step["command_plan"]["ready_to_execute"] is True
    assert next_step["command_plan"]["argv"] == [
        "source",
        "add-file",
        str(SOURCE_FIXTURE_PATH.resolve()),
        "--ledger-path",
        str(ledger_path.resolve()),
        "--archive-path",
        str(archive_path.resolve()),
    ]

    assert main(source_add_file_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "ready_for_assertion_proposal"
    assert status["document_count"] == 1
    assert status["candidate_document_ids"] == ["doc_aa67767133655af72fbcf0a8"]
    assert status["next_command_plan"]["ready_to_execute"] is True
    next_step = pipeline_next_json(
        ledger_path,
        capsys,
        archive_path=archive_path,
        model_output_fixture_path=MODEL_OUTPUT_FIXTURE_PATH,
    )
    assert next_step["command_plan"]["ready_to_execute"] is True
    assert next_step["command_plan"]["argv"] == [
        "--runtime-profile",
        "macbook",
        "source",
        "propose-assertions",
        "--document-id",
        "doc_aa67767133655af72fbcf0a8",
        "--model-output-fixture",
        str(MODEL_OUTPUT_FIXTURE_PATH.resolve()),
        "--ledger-path",
        str(ledger_path.resolve()),
        "--archive-path",
        str(archive_path.resolve()),
    ]

    with sqlite_ledger_transaction(ledger_path) as repository:
        document = repository.list_documents()[0]
    assert main(propose_assertions_args(ledger_path, archive_path, document.id)) == 0
    capsys.readouterr()
    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "review_required"
    assert status["review_required"] is True
    assert status["pending_count"] == 16
    assert status["blocked_commands"] == [
        "kotekomi graph project",
        "kotekomi graph mine",
        "kotekomi briefing generate --title <title>",
    ]
    assert status["next_command_plan"]["ready_to_execute"] is True
    assert status["next_command_plan"]["argv"] == [
        "review",
        "next",
        "--ledger-path",
        str(ledger_path.resolve()),
    ]
    next_step = pipeline_next_json(ledger_path, capsys)
    assert next_step["command"] == "kotekomi review next"
    assert next_step["requires_human_review"] is True

    with sqlite_ledger_transaction(ledger_path) as repository:
        initial_changes = repository.list_proposed_changes()
    approve_pending(ledger_path, initial_changes, capsys)

    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "ready_for_graph_mining"
    assert status["next_command"] == "kotekomi graph mine"
    assert status["safe_commands"] == ["kotekomi graph project", "kotekomi graph mine"]
    assert status["next_command_plan"]["ready_to_execute"] is True
    assert status["next_command_plan"]["argv"] == [
        "graph",
        "mine",
        "--ledger-path",
        str(ledger_path.resolve()),
    ]

    assert main(graph_mine_args(ledger_path)) == 0
    capsys.readouterr()
    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "review_required"
    assert status["pending_count"] > 0

    with sqlite_ledger_transaction(ledger_path) as repository:
        mined_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
    approve_pending(ledger_path, mined_changes, capsys)

    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "ready_for_briefing"
    assert status["next_command"] == "kotekomi briefing generate --title <title>"
    assert status["next_command_plan"]["ready_to_execute"] is False
    assert status["next_command_plan"]["missing_inputs"][0]["name"] == "briefing_title"
    next_step = pipeline_next_json(
        ledger_path,
        capsys,
        archive_path=archive_path,
        briefing_title="Daily Briefing",
    )
    assert next_step["command_plan"]["ready_to_execute"] is True
    assert next_step["command_plan"]["argv"] == [
        "briefing",
        "generate",
        "--title",
        "Daily Briefing",
        "--ledger-path",
        str(ledger_path.resolve()),
        "--archive-path",
        str(archive_path.resolve()),
    ]

    assert main(briefing_generate_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    status = pipeline_status_json(ledger_path, capsys)
    assert status["stage"] == "briefing_current"
    assert status["next_command"] is None
    assert status["briefing_count"] == 1
    assert status["next_command_plan"]["ready_to_execute"] is False
    assert status["next_command_plan"]["argv"] == []
    next_step = pipeline_next_json(ledger_path, capsys)
    assert next_step["command"] is None
    assert next_step["blocked"] is True
    assert next_step["command_plan"]["command"] is None


def test_pipeline_status_text_is_human_readable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"

    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()

    assert main(pipeline_status_args(ledger_path)) == 0
    status_text = capsys.readouterr().out
    assert "Pipeline stage: ready_for_source_ingest" in status_text
    assert "Next command: kotekomi source add-file <path>" in status_text
    assert "Safe commands:" in status_text

    assert main(pipeline_next_args(ledger_path)) == 0
    next_text = capsys.readouterr().out
    assert "Pipeline stage: ready_for_source_ingest" in next_text
    assert "Reason: No Source records exist in the Ledger." in next_text


def test_pipeline_run_next_executes_exactly_one_planned_fixture_step(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"

    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()

    exit_code, result = pipeline_run_next_json(ledger_path, archive_path, capsys)
    assert exit_code == 2
    assert result["executed"] is False
    assert result["command_plan"]["missing_inputs"][0]["name"] == "source_file_path"

    exit_code, result = pipeline_run_next_json(
        ledger_path,
        archive_path,
        capsys,
        source_file_path=SOURCE_FIXTURE_PATH,
        dry_run=True,
    )
    assert exit_code == 0
    assert result["dry_run"] is True
    assert result["executed"] is False
    assert result["command_plan"]["ready_to_execute"] is True
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.list_sources() == ()

    exit_code, result = pipeline_run_next_json(
        ledger_path,
        archive_path,
        capsys,
        source_file_path=SOURCE_FIXTURE_PATH,
    )
    assert exit_code == 0
    assert result["executed"] is True
    assert result["stdout_lines"][0].startswith("Source created: src_")
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = repository.list_documents()[0]

    exit_code, result = pipeline_run_next_json(
        ledger_path,
        archive_path,
        capsys,
        model_output_fixture_path=MODEL_OUTPUT_FIXTURE_PATH,
    )
    assert exit_code == 0
    assert result["executed"] is True
    assert "ProposedChanges: 16" in result["stdout_lines"]
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_proposed_changes()) == 16

    exit_code, result = pipeline_run_next_json(ledger_path, archive_path, capsys)
    assert exit_code == 0
    assert result["executed"] is True
    assert result["stage"] == "review_required"
    assert result["command_plan"]["argv"] == [
        "review",
        "next",
        "--ledger-path",
        str(ledger_path.resolve()),
    ]
    assert result["stdout_lines"][0].startswith("Next ProposedChange:")
    with sqlite_ledger_transaction(ledger_path) as repository:
        initial_changes = repository.list_proposed_changes()
        pending_initial_changes = tuple(
            change
            for change in initial_changes
            if change.review_status is ReviewStatus.PENDING
        )
        assert len(pending_initial_changes) == 16
    approve_pending(ledger_path, initial_changes, capsys)

    exit_code, result = pipeline_run_next_json(ledger_path, archive_path, capsys)
    assert exit_code == 0
    assert result["executed"] is True
    assert result["stage"] == "ready_for_graph_mining"
    assert "ProposedChanges: 5" in result["stdout_lines"]
    with sqlite_ledger_transaction(ledger_path) as repository:
        mined_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
    assert len(mined_changes) == 5

    exit_code, result = pipeline_run_next_json(ledger_path, archive_path, capsys)
    assert exit_code == 0
    assert result["executed"] is True
    assert result["stage"] == "review_required"
    assert result["stdout_lines"][0].startswith("Next ProposedChange:")
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(
            tuple(
                change
                for change in repository.list_proposed_changes()
                if change.review_status is ReviewStatus.PENDING
            )
        ) == 5
    approve_pending(ledger_path, mined_changes, capsys)

    exit_code, result = pipeline_run_next_json(ledger_path, archive_path, capsys)
    assert exit_code == 2
    assert result["executed"] is False
    assert result["command_plan"]["missing_inputs"][0]["name"] == "briefing_title"

    exit_code, result = pipeline_run_next_json(
        ledger_path,
        archive_path,
        capsys,
        briefing_title="Daily Briefing",
    )
    assert exit_code == 0
    assert result["executed"] is True
    assert result["stage"] == "ready_for_briefing"
    assert result["stdout_lines"][0].startswith("Briefing: brf_")
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_briefings()) == 1

    exit_code, result = pipeline_run_next_json(ledger_path, archive_path, capsys)
    assert exit_code == 0
    assert result["executed"] is False
    assert result["stage"] == "briefing_current"
    assert result["command"] is None
    assert result["command_plan"]["argv"] == []
    assert document.id == "doc_aa67767133655af72fbcf0a8"


def approve_pending(
    ledger_path: Path,
    proposed_changes: tuple[ProposedChange, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=proposed_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )


def pipeline_status_json(
    ledger_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    archive_path: Path | None = None,
    source_file_path: Path | None = None,
    model_output_fixture_path: Path | None = None,
    document_id: str | None = None,
    briefing_title: str | None = None,
) -> dict[str, Any]:
    assert (
        main(
            pipeline_status_json_args(
                ledger_path,
                archive_path=archive_path,
                source_file_path=source_file_path,
                model_output_fixture_path=model_output_fixture_path,
                document_id=document_id,
                briefing_title=briefing_title,
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def pipeline_next_json(
    ledger_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    archive_path: Path | None = None,
    source_file_path: Path | None = None,
    model_output_fixture_path: Path | None = None,
    document_id: str | None = None,
    briefing_title: str | None = None,
) -> dict[str, Any]:
    assert (
        main(
            pipeline_next_json_args(
                ledger_path,
                archive_path=archive_path,
                source_file_path=source_file_path,
                model_output_fixture_path=model_output_fixture_path,
                document_id=document_id,
                briefing_title=briefing_title,
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def pipeline_run_next_json(
    ledger_path: Path,
    archive_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    source_file_path: Path | None = None,
    model_output_fixture_path: Path | None = None,
    document_id: str | None = None,
    briefing_title: str | None = None,
    dry_run: bool = False,
) -> tuple[int, dict[str, Any]]:
    exit_code = main(
        pipeline_run_next_json_args(
            ledger_path,
            archive_path,
            source_file_path=source_file_path,
            model_output_fixture_path=model_output_fixture_path,
            document_id=document_id,
            briefing_title=briefing_title,
            dry_run=dry_run,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    return exit_code, cast(dict[str, Any], payload)


def ledger_init_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def source_add_file_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "source",
        "add-file",
        str(SOURCE_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def propose_assertions_args(
    ledger_path: Path,
    archive_path: Path,
    document_id: str,
) -> list[str]:
    return [
        "source",
        "propose-assertions",
        "--document-id",
        document_id,
        "--model-output-fixture",
        str(MODEL_OUTPUT_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def review_approve_args(ledger_path: Path, proposed_change_id: str) -> list[str]:
    return [
        "review",
        "approve",
        "--proposed-change-id",
        proposed_change_id,
        "--reviewer",
        "analyst",
        "--ledger-path",
        str(ledger_path),
    ]


def graph_mine_args(ledger_path: Path) -> list[str]:
    return [
        "graph",
        "mine",
        "--ledger-path",
        str(ledger_path),
    ]


def briefing_generate_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "briefing",
        "generate",
        "--title",
        "Daily Briefing",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def pipeline_status_args(ledger_path: Path) -> list[str]:
    return [
        "pipeline",
        "status",
        "--ledger-path",
        str(ledger_path),
    ]


def pipeline_status_json_args(
    ledger_path: Path,
    *,
    archive_path: Path | None = None,
    source_file_path: Path | None = None,
    model_output_fixture_path: Path | None = None,
    document_id: str | None = None,
    briefing_title: str | None = None,
) -> list[str]:
    args = [
        "pipeline",
        "status",
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
    ]
    return _with_planning_args(
        args,
        archive_path=archive_path,
        source_file_path=source_file_path,
        model_output_fixture_path=model_output_fixture_path,
        document_id=document_id,
        briefing_title=briefing_title,
    )


def pipeline_next_args(ledger_path: Path) -> list[str]:
    return [
        "pipeline",
        "next",
        "--ledger-path",
        str(ledger_path),
    ]


def pipeline_next_json_args(
    ledger_path: Path,
    *,
    archive_path: Path | None = None,
    source_file_path: Path | None = None,
    model_output_fixture_path: Path | None = None,
    document_id: str | None = None,
    briefing_title: str | None = None,
) -> list[str]:
    args = [
        "pipeline",
        "next",
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
    ]
    return _with_planning_args(
        args,
        archive_path=archive_path,
        source_file_path=source_file_path,
        model_output_fixture_path=model_output_fixture_path,
        document_id=document_id,
        briefing_title=briefing_title,
    )


def pipeline_run_next_json_args(
    ledger_path: Path,
    archive_path: Path,
    *,
    source_file_path: Path | None = None,
    model_output_fixture_path: Path | None = None,
    document_id: str | None = None,
    briefing_title: str | None = None,
    dry_run: bool = False,
) -> list[str]:
    args = [
        "pipeline",
        "run-next",
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]
    if dry_run:
        args.append("--dry-run")
    return _with_planning_args(
        args,
        archive_path=None,
        source_file_path=source_file_path,
        model_output_fixture_path=model_output_fixture_path,
        document_id=document_id,
        briefing_title=briefing_title,
    )


def _with_planning_args(
    args: list[str],
    *,
    archive_path: Path | None,
    source_file_path: Path | None,
    model_output_fixture_path: Path | None,
    document_id: str | None,
    briefing_title: str | None,
) -> list[str]:
    if archive_path is not None:
        args.extend(("--archive-path", str(archive_path)))
    if source_file_path is not None:
        args.extend(("--source-file-path", str(source_file_path)))
    if model_output_fixture_path is not None:
        args.extend(("--model-output-fixture", str(model_output_fixture_path)))
    if document_id is not None:
        args.extend(("--document-id", document_id))
    if briefing_title is not None:
        args.extend(("--briefing-title", briefing_title))
    return args
