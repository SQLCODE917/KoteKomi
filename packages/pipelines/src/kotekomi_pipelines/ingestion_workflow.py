"""One fresh-ingestion workflow shared by every Pipeline interface.

The workflow composes two Application Layer use cases in order: user ingestion,
then the derived composition pass. Interfaces keep their own presentation and
call this workflow instead of calling ingestion directly, so presentation mode
cannot change the persisted composition outcomes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from kotekomi_application import (
    EventCompositionRecord,
    IngestionRunIdFactory,
    LinguisticAnalyzer,
)
from kotekomi_application.ingestion_inspection import (
    HybridParagraphProgress,
    HybridParagraphStageProgress,
)
from kotekomi_application.ingestion_runs import Uuid4IngestionRunIdFactory

from kotekomi_pipelines.hybrid_document_ingestion import build_linguistic_analyzer
from kotekomi_pipelines.ingestion_composition_pass import compose_ingested_run
from kotekomi_pipelines.model_runtime import build_model_task_runtime


@dataclass(frozen=True)
class IngestionWorkflowResult:
    """Terminal result of one fresh-ingestion workflow."""

    ingestion_code: int
    ingestion_run_id: str | None
    composition_records: tuple[EventCompositionRecord, ...]
    composition_error: str | None


class _RecordingRunIdFactory:
    """Return the wrapped factory's identity once and remember it."""

    def __init__(self, wrapped: IngestionRunIdFactory) -> None:
        self._wrapped = wrapped
        self.identity: str | None = None

    def new_ingestion_run_id(self) -> str:
        identity = self._wrapped.new_ingestion_run_id()
        self.identity = identity
        return identity


def run_ingestion_workflow(
    *,
    config_path: Path | None,
    source_file_path: Path,
    source_url: str,
    stdout: TextIO,
    stderr: TextIO,
    stage_progress: Callable[[HybridParagraphStageProgress], None] | None = None,
    paragraph_progress: Callable[[HybridParagraphProgress], None] | None = None,
    ingestion_run_id_factory: IngestionRunIdFactory | None = None,
    analyzer: LinguisticAnalyzer | None = None,
    on_composed: Callable[[tuple[EventCompositionRecord, ...]], None] | None = None,
) -> IngestionWorkflowResult:
    """Ingest the source, then derive composition bound to the assigned run.

    The derived pass never changes the ingestion exit code. A derived failure
    reports one diagnostic line on the caller's error stream.
    """
    from kotekomi_pipelines.cli import ingest_user_file

    recorder = _RecordingRunIdFactory(ingestion_run_id_factory or Uuid4IngestionRunIdFactory())
    code = ingest_user_file(
        config_path=config_path,
        source_file_path=source_file_path,
        source_url=source_url,
        stage_progress=stage_progress,
        paragraph_progress=paragraph_progress,
        stdout=stdout,
        stderr=stderr,
        ingestion_run_id_factory=recorder,
    )
    identity = recorder.identity
    if code != 0:
        # A failure before admission legitimately has no assigned IngestionRun.
        return IngestionWorkflowResult(code, identity, (), None)
    if identity is None:
        raise RuntimeError("Ingestion reported success without assigning an identity.")
    try:
        records = _compose_assigned_run(
            config_path=config_path, ingestion_run_id=identity, analyzer=analyzer
        )
    except Exception as error:
        stderr.write(f"Composition pass failed: {error}\n")
        return IngestionWorkflowResult(code, identity, (), str(error))
    if on_composed is not None:
        on_composed(records)
    return IngestionWorkflowResult(code, identity, records, None)


def _compose_assigned_run(
    *,
    config_path: Path | None,
    ingestion_run_id: str,
    analyzer: LinguisticAnalyzer | None,
) -> tuple[EventCompositionRecord, ...]:
    from kotekomi_pipelines.config import load_config

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )
    configured_analyzer = analyzer or build_linguistic_analyzer(
        config, build_model_task_runtime(config.model_execution)
    )
    return compose_ingested_run(
        ledger_path=config.ledger_path,
        archive_path=config.archive_path,
        analyzer=configured_analyzer,
        ingestion_run_id=ingestion_run_id,
    )
