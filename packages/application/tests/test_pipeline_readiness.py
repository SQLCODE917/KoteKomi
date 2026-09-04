# pyright: reportPrivateUsage=false

from kotekomi_application import (
    PipelineExecutionClass,
    PipelineStage,
    PipelineStatusInput,
    pipeline_command_plan_to_json,
)
from kotekomi_application.pipeline_readiness import (
    _briefing_generate_plan,
    _review_next_plan,
    _source_ingest_plan,
)


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
    assert ready.execution_class is PipelineExecutionClass.LONG_RUNNING
    assert ready.completion_probe_argv == (
        "pipeline",
        "status",
        "--ledger-path",
        "data/kotekomi.db",
        "--archive-path",
        "data/archive",
        "--format",
        "json",
    )
    assert ready.evidence_argv == ready.completion_probe_argv
    assert ready.expected_record_types == (
        "Source",
        "Document",
        "DocumentRepresentationBundle",
        "ProvenanceActivity",
    )
    assert pipeline_command_plan_to_json(ready)["execution_class"] == "long_running"
    assert missing_url.completion_probe_argv == ()
    assert missing_url.evidence_argv == ()
    assert missing_url.expected_record_types == ()


def test_review_and_briefing_plans_expose_bounded_inspection_commands() -> None:
    pipeline_input = PipelineStatusInput(
        ledger_path="data/kotekomi.db",
        archive_path="data/archive",
        briefing_title="Daily Briefing",
    )

    review = _review_next_plan(PipelineStage.REVIEW_REQUIRED, pipeline_input, ())
    briefing = _briefing_generate_plan(PipelineStage.READY_FOR_BRIEFING, pipeline_input)

    assert review.execution_class is PipelineExecutionClass.INTERACTIVE
    assert review.completion_probe_argv == (
        "review",
        "readiness",
        "--ledger-path",
        "data/kotekomi.db",
        "--format",
        "json",
    )
    assert review.evidence_argv == review.completion_probe_argv
    assert review.expected_record_types == ("ProvenanceActivity",)
    assert briefing.execution_class is PipelineExecutionClass.LONG_RUNNING
    assert briefing.completion_probe_argv == (
        "pipeline",
        "status",
        "--ledger-path",
        "data/kotekomi.db",
        "--archive-path",
        "data/archive",
        "--format",
        "json",
    )
    assert briefing.evidence_argv == briefing.completion_probe_argv
    assert briefing.expected_record_types == ("Briefing", "ProvenanceActivity")
