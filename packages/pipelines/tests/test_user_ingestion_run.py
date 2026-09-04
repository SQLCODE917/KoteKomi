import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from kotekomi_adapters import SQLiteLedgerRepository, sqlite_ledger_transaction
from kotekomi_application import (
    HYBRID_STAGE_ORDER,
    ModelTaskRequest,
    ModelTaskResponse,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
)
from kotekomi_domain import (
    AnalysisRunState,
    IngestionChangeSet,
    IngestionChangeSetOrigin,
    IngestionRunStatus,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.model_runtime import FixtureModelTaskRuntime

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
SOURCE_URL = "https://example.test/articles/anthropic-review"
PDF_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "tests"
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)


def _config(tmp_path: Path) -> Path:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f'''
ledger_path = "{(tmp_path / "state" / "kotekomi.db").as_posix()}"
archive_path = "{(tmp_path / "state" / "archive").as_posix()}"

runtime_profile = "fixture"

[processing]
representation_policy_version = "deposited-source-v1"
'''.lstrip(),
        encoding="utf-8",
    )
    return config_path


def test_user_ingest_auto_initializes_storage_and_records_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)

    assert (
        main(["--config", str(config_path), "ingest", str(FIXTURE_PATH), "--url", SOURCE_URL]) == 0
    )
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("Ingestion run: igr_")
    assert "src_" not in captured.out
    run_line, captured_row, summary = captured.out.splitlines()
    assert summary == ("Extraction: 0 proposed changes; 0/0 paragraphs complete; 0 gaps; 0 reused")
    assert main(["--config", str(config_path), "ingestions", "list"]) == 0
    history = capsys.readouterr()
    assert history.err == ""
    assert history.out.startswith(
        f"{run_line.removeprefix('Ingestion run: ')}\t"
        f"{captured_row.split(chr(9), maxsplit=1)[0]}\t[CAPTURED]\t"
    )
    assert history.out.count("\t") == 3


def test_user_ingest_retry_creates_two_runs_and_reuses_capture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)
    command = ["--config", str(config_path), "ingest", str(FIXTURE_PATH), "--url", SOURCE_URL]

    assert main(command) == 0
    capsys.readouterr()
    assert main(command) == 0
    capsys.readouterr()
    ledger_path = tmp_path / "state" / "kotekomi.db"
    with sqlite_ledger_transaction(ledger_path) as repository:
        runs = repository.list_ingestion_runs()
        sources = repository.list_sources()
        documents = repository.list_documents()
        change_set_ids = tuple(run.ingestion_change_set_id for run in runs)
        assert all(change_set_id is not None for change_set_id in change_set_ids)
        change_sets = tuple(
            repository.get_ingestion_change_set(change_set_id)
            for change_set_id in change_set_ids
            if change_set_id is not None
        )

    assert len(runs) == 2
    assert all(run.status is IngestionRunStatus.CAPTURED for run in runs)
    assert runs[0].source_id == runs[1].source_id
    assert runs[0].document_id == runs[1].document_id
    assert runs[0].analysis_run_id == runs[1].analysis_run_id
    assert len(change_sets) == len(runs)
    assert all(change_set is not None for change_set in change_sets)
    assert {change_set.analysis_origin for change_set in change_sets if change_set is not None} == {
        IngestionChangeSetOrigin.EXECUTED,
        IngestionChangeSetOrigin.REUSED,
    }
    assert len(sources) == 1
    assert len(documents) == 1


def test_user_ingest_accepts_project_pdf_and_text_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)
    text_path = tmp_path / "deposited.txt"
    text_path.write_text("A deposited text fixture.\n", encoding="utf-8")

    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingest",
                str(PDF_FIXTURE_PATH),
                "--url",
                "https://example.test/articles/community-health-plan",
            ]
        )
        == 0
    )
    assert "[CAPTURED]" in capsys.readouterr().out
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        extraction_tasks = repository.list_extraction_tasks()
        context_manifests = repository.list_context_manifest_artifacts_for_representation(
            repository.list_document_representations()[0].id
        )
    assert extraction_tasks
    assert "paragraph_hypothesis_segment_v3" not in {task.prompt_id for task in extraction_tasks}
    assert {task.prompt_id for task in extraction_tasks} >= {
        "hybrid_gliner_labels_v1",
        "hybrid_mention_task_v1",
    }
    assert context_manifests
    assert "paragraph_hypothesis_segment_v3" not in {
        str(cast(dict[str, object], manifest.payload["integrity"])["prompt_id"])
        for manifest in context_manifests
    }
    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingest",
                str(text_path),
                "--url",
                "https://example.test/articles/deposited-text",
            ]
        )
        == 0
    )
    assert "[CAPTURED]" in capsys.readouterr().out


def test_user_ingest_checkpoints_and_reuses_the_complete_hybrid_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _config(tmp_path)
    command = [
        "--config",
        str(config_path),
        "ingest",
        str(PDF_FIXTURE_PATH),
        "--url",
        "https://example.test/articles/hybrid-replay",
    ]

    assert main(command) == 0
    first_output = capsys.readouterr()
    assert first_output.err == ""
    assert "paragraphs complete; 0 gaps; 0 reused" in first_output.out

    archive_root = tmp_path / "state" / "archive"
    coverage_paths = tuple((archive_root / "extraction" / "document-coverage").glob("*.json"))
    receipt_paths = tuple((archive_root / "extraction" / "paragraph-receipts").glob("*.json"))
    assert len(coverage_paths) == 1
    report = hybrid_document_coverage_report_from_bytes(coverage_paths[0].read_bytes())
    receipts = tuple(
        hybrid_paragraph_receipt_from_bytes(path.read_bytes()) for path in receipt_paths
    )
    assert report.required_paragraph_count == len(receipts) > 1
    assert report.complete_paragraph_count == report.required_paragraph_count
    assert report.gap_paragraph_count == 0
    assert all(
        tuple(stage.stage_id for stage in receipt.stages) == HYBRID_STAGE_ORDER
        for receipt in receipts
    )

    ledger_path = tmp_path / "state" / "kotekomi.db"
    with sqlite_ledger_transaction(ledger_path) as repository:
        first_task_ids = tuple(item.id for item in repository.list_extraction_tasks())
        first_model_run_ids = tuple(item.id for item in repository.list_model_runs())
        first_ingestion = repository.list_ingestion_runs()[0]
        assert first_ingestion.analysis_run_id is not None
        first_analysis = repository.get_analysis_run(first_ingestion.analysis_run_id)
        planned_items = repository.list_planned_items_for_analysis_run(
            first_ingestion.analysis_run_id
        )
        item_attempts = repository.list_analysis_item_attempts_for_items(
            tuple(item.id for item in planned_items)
        )
    assert first_analysis is not None
    assert first_analysis.state is AnalysisRunState.COMPLETE
    assert {item.model_run_id for item in item_attempts if item.model_run_id is not None} == set(
        first_model_run_ids
    )

    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingestions",
                "show",
                first_ingestion.id,
                "--format",
                "json",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["ingestion_run_id"] == first_ingestion.id
    assert summary["analysis_state"] == "complete"
    assert summary["required_paragraph_count"] == report.required_paragraph_count
    assert summary["model_run_count"] == len(first_model_run_ids)
    assert "source_text" not in summary

    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingestions",
                "artifacts",
                first_ingestion.id,
                "--format",
                "jsonl",
            ]
        )
        == 0
    )
    evidence = tuple(json.loads(line) for line in capsys.readouterr().out.splitlines() if line)
    assert any(item["record_type"] == "HybridDocumentCoverageReport" for item in evidence)
    assert any(item["record_type"] == "ModelRunOutput" for item in evidence)

    assert (
        main(
            [
                "--config",
                str(config_path),
                "model",
                "runs",
                "--ingestion-run",
                first_ingestion.id,
                "--format",
                "json",
            ]
        )
        == 0
    )
    model_history = json.loads(capsys.readouterr().out)
    assert len(model_history["model_runs"]) == len(first_model_run_ids)

    assert (
        main(
            [
                "--config",
                str(config_path),
                "extraction",
                "traces",
                "--ingestion-run",
                first_ingestion.id,
                "--format",
                "jsonl",
            ]
        )
        == 0
    )
    traces = tuple(json.loads(line) for line in capsys.readouterr().out.splitlines() if line)
    assert traces
    assert all(item["authority"] == "derived_diagnostic" for item in traces)

    def adapter_must_not_start(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("A fully reused HP-8 document started an Adapter.")

    monkeypatch.setattr(
        "kotekomi_pipelines.hybrid_document_ingestion.GlinerMentionProposer",
        adapter_must_not_start,
    )
    monkeypatch.setattr(
        "kotekomi_pipelines.hybrid_document_ingestion.RefinedEntityLinkingAdapter",
        adapter_must_not_start,
    )
    assert main(command) == 0
    replay_output = capsys.readouterr()
    assert replay_output.err == ""
    assert replay_output.out.count("(reused)") == report.required_paragraph_count
    assert f"{report.required_paragraph_count} reused" in replay_output.out
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert tuple(item.id for item in repository.list_extraction_tasks()) == first_task_ids
        assert tuple(item.id for item in repository.list_model_runs()) == first_model_run_ids
        runs = repository.list_ingestion_runs()
        replay_change_sets = tuple(
            repository.get_ingestion_change_set(change_set_id)
            for run in runs
            if (change_set_id := run.ingestion_change_set_id) is not None
        )
    assert all(item is not None for item in replay_change_sets)
    assert {item.analysis_origin for item in replay_change_sets if item is not None} == {
        IngestionChangeSetOrigin.EXECUTED,
        IngestionChangeSetOrigin.REUSED,
    }
    assert runs[0].analysis_run_id == runs[1].analysis_run_id


def test_user_ingest_rejects_corrupt_hybrid_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)
    command = [
        "--config",
        str(config_path),
        "ingest",
        str(PDF_FIXTURE_PATH),
        "--url",
        "https://example.test/articles/hybrid-corruption",
    ]
    assert main(command) == 0
    capsys.readouterr()
    receipt_path = next(
        (tmp_path / "state" / "archive" / "extraction" / "paragraph-receipts").glob("*.json")
    )
    receipt_path.write_bytes(b"corrupt checkpoint")

    assert main(command) == 1
    output = capsys.readouterr()
    assert "hpr_" not in output.out
    assert "src_" not in output.out
    assert output.err == "Automatic extraction could not complete.\n"
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        runs = repository.list_ingestion_runs()
    assert len(runs) == 2
    assert {run.status for run in runs} == {
        IngestionRunStatus.CAPTURED,
        IngestionRunStatus.ERROR,
    }


def test_user_ingest_continues_after_one_proposer_fails_and_closes_with_gaps(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = FixtureModelTaskRuntime.run_model_task

    def invalid_mention_output(
        self: FixtureModelTaskRuntime, task: ModelTaskRequest
    ) -> ModelTaskResponse:
        result = original(self, task)
        if task.task_type == "hybrid_mention_proposal":
            return replace(result, raw_output=b"invalid fixture output\n")
        return result

    monkeypatch.setattr(FixtureModelTaskRuntime, "run_model_task", invalid_mention_output)
    config_path = _config(tmp_path)

    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingest",
                str(PDF_FIXTURE_PATH),
                "--url",
                "https://example.test/articles/hybrid-gaps",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    assert output.err == ""
    assert "0/15 paragraphs complete; 15 gaps" in output.out
    coverage_path = next(
        (tmp_path / "state" / "archive" / "extraction" / "document-coverage").glob("*.json")
    )
    report = hybrid_document_coverage_report_from_bytes(coverage_path.read_bytes())
    assert report.gap_paragraph_count == report.required_paragraph_count == 15
    receipt_paths = tuple(
        (tmp_path / "state" / "archive" / "extraction" / "paragraph-receipts").glob("*.json")
    )
    receipts = tuple(
        hybrid_paragraph_receipt_from_bytes(path.read_bytes()) for path in receipt_paths
    )
    assert len(receipts) == 15
    assert all(receipt.stages[0].terminal_status == "partial" for receipt in receipts)
    assert all(
        "qwen_proposer_failed:invalid_output" in receipt.stages[0].diagnostics
        for receipt in receipts
    )
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        ingestion = repository.list_ingestion_runs()[0]
        assert ingestion.analysis_run_id is not None
        analysis = repository.get_analysis_run(ingestion.analysis_run_id)
    assert analysis is not None
    assert analysis.state is AnalysisRunState.COMPLETE_WITH_GAPS


def test_user_ingest_rolls_back_the_complete_closure_transaction(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_change_set(self: SQLiteLedgerRepository, record: IngestionChangeSet) -> None:
        del self, record
        raise sqlite3.OperationalError("fixture closure fault")

    monkeypatch.setattr(SQLiteLedgerRepository, "save_ingestion_change_set", fail_change_set)
    config_path = _config(tmp_path)
    ledger_path = tmp_path / "state" / "kotekomi.db"

    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingest",
                str(PDF_FIXTURE_PATH),
                "--url",
                "https://example.test/articles/hybrid-rollback",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert output.err == "Automatic extraction could not complete.\n"
    with sqlite3.connect(ledger_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM planned_analysis_items").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM proposed_changes").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM ingestion_change_sets").fetchone() == (0,)
    with sqlite_ledger_transaction(ledger_path) as repository:
        runs = repository.list_ingestion_runs()
    assert len(runs) == 1
    assert runs[0].status is IngestionRunStatus.ERROR


@pytest.mark.parametrize(
    ("path", "url", "message"),
    [
        ("missing.md", SOURCE_URL, "not found"),
        ("unsupported.docx", SOURCE_URL, "not supported"),
        (str(FIXTURE_PATH), "http://example.test/not-https", "absolute HTTPS URL"),
    ],
)
def test_user_ingest_persists_expected_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    path: str,
    url: str,
    message: str,
) -> None:
    config_path = _config(tmp_path)

    assert main(["--config", str(config_path), "ingest", path, "--url", url]) == 1
    output = capsys.readouterr()
    assert output.out.startswith("Ingestion run: igr_")
    assert output.out.count("\n") == 1
    assert message in output.err
    assert "src_" not in output.err
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        runs = repository.list_ingestion_runs()
    assert len(runs) == 1
    assert runs[0].status is IngestionRunStatus.ERROR


def test_user_ingest_syntax_failure_creates_no_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(["--config", str(config_path), "ingest", str(FIXTURE_PATH)])

    assert error.value.code == 2
    assert not (tmp_path / "state" / "kotekomi.db").exists()
    assert "--url" in capsys.readouterr().err


def test_user_ingest_records_unexpected_capture_failure_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _config(tmp_path)

    def raise_capture_failure(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("internal source text must not be displayed")

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.commit_authoritative_capture", raise_capture_failure
    )

    assert (
        main(["--config", str(config_path), "ingest", str(FIXTURE_PATH), "--url", SOURCE_URL]) == 1
    )
    output = capsys.readouterr()
    assert output.out.startswith("Ingestion run: igr_")
    assert output.out.count("\n") == 1
    assert "could not be captured" in output.err
    assert "internal source text" not in output.err
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        runs = repository.list_ingestion_runs()
    assert runs[0].status is IngestionRunStatus.ERROR
