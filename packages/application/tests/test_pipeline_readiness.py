# pyright: reportPrivateUsage=false

from kotekomi_application import PipelineStage, PipelineStatusInput
from kotekomi_application.pipeline_readiness import _source_ingest_plan


def test_source_ingest_plan_requires_and_emits_source_url() -> None:
    missing_url = _source_ingest_plan(
        PipelineStage.READY_FOR_SOURCE_INGEST,
        PipelineStatusInput(
            source_file_path="raw/article.pdf",
            ledger_path="data/kotekomi.db",
            archive_path="data/archive",
        ),
    )
    ready = _source_ingest_plan(
        PipelineStage.READY_FOR_SOURCE_INGEST,
        PipelineStatusInput(
            source_file_path="raw/article.pdf",
            source_url="https://example.test/articles/article",
            ledger_path="data/kotekomi.db",
            archive_path="data/archive",
        ),
    )

    assert missing_url.ready_to_execute is False
    assert [item.name for item in missing_url.missing_inputs] == ["source_url"]
    assert ready.ready_to_execute is True
    assert ready.argv == (
        "source",
        "add-file",
        "raw/article.pdf",
        "--source-url",
        "https://example.test/articles/article",
        "--ledger-path",
        "data/kotekomi.db",
        "--archive-path",
        "data/archive",
    )
