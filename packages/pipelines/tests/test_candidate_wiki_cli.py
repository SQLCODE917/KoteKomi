from datetime import UTC, datetime
from pathlib import Path

import kotekomi_pipelines.cli as cli
import pytest
from kotekomi_domain import IngestionRun, IngestionRunStatus

NOW = datetime(2026, 9, 4, tzinfo=UTC)


def test_public_candidate_wiki_command_dispatches_without_domain_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_build(*, config_path: Path | None, filename: str, candidate: bool) -> int:
        received.update(
            config_path=config_path,
            filename=filename,
            candidate=candidate,
        )
        return 0

    monkeypatch.setattr(cli, "build_candidate_wiki", fake_build)

    result = cli.main(
        [
            "--config",
            "/tmp/kotekomi.toml",
            "wiki",
            "build",
            "report.pdf",
            "--candidate",
        ]
    )

    assert result == 0
    assert received == {
        "config_path": Path("/tmp/kotekomi.toml"),
        "filename": "report.pdf",
        "candidate": True,
    }


def test_public_candidate_wiki_audit_command_dispatches_with_stable_record_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_audit(
        *,
        config_path: Path | None,
        build_id: str,
        record_id: str,
        output_format: str,
    ) -> int:
        received.update(
            config_path=config_path,
            build_id=build_id,
            record_id=record_id,
            output_format=output_format,
        )
        return 0

    monkeypatch.setattr(cli, "audit_candidate_wiki", fake_audit)

    result = cli.main(
        [
            "--config",
            "/tmp/kotekomi.toml",
            "wiki",
            "audit",
            "--build-id",
            "wkb_example",
            "--record-id",
            "evt_example",
            "--format",
            "json",
        ]
    )

    assert result == 0
    assert received == {
        "config_path": Path("/tmp/kotekomi.toml"),
        "build_id": "wkb_example",
        "record_id": "evt_example",
        "output_format": "json",
    }


def test_duplicate_ingestion_selector_uses_human_number_not_domain_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    newer = _run("igr_newer", NOW)
    older = _run("igr_older", datetime(2026, 9, 3, tzinfo=UTC))

    def select_second(_: str) -> str:
        return "2"

    monkeypatch.setattr("builtins.input", select_second)

    selected = cli.choose_candidate_ingestion((newer, older))

    assert selected.id == "igr_older"


def _run(record_id: str, started_at: datetime) -> IngestionRun:
    return IngestionRun(
        id=record_id,
        requested_path="/input/report.pdf",
        display_filename="report.pdf",
        requested_source_url="https://example.test/report",
        normalized_source_url="https://example.test/report",
        status=IngestionRunStatus.CAPTURED,
        started_at=started_at,
        completed_at=NOW,
        source_id="src_example",
        document_id="doc_example",
        representation_id="rep_example",
        provenance_activity_id="prv_example",
        analysis_run_id="arn_example",
        ingestion_change_set_id="ics_example",
    )
