"""Spawn entry point composing the existing ingestion Pipeline with inspection."""

from __future__ import annotations

import os
from contextlib import redirect_stderr, redirect_stdout
from multiprocessing.connection import Connection
from pathlib import Path

from kotekomi_adapters.extraction_view.execution import ProcessOutput, send_event
from kotekomi_application.ingestion_execution import (
    AssignedIngestionRunIdFactory,
    FinishedEvent,
    IngestionProcessRequest,
    ParagraphEvent,
)
from kotekomi_application.ingestion_inspection import InspectionContext, ParagraphSnapshot


def run_ingestion_worker(request: IngestionProcessRequest, connection: Connection) -> None:
    """Spawn entry point; owns all expensive runtime resources in its process group."""
    from kotekomi_pipelines.cli import ingest_user_file
    from kotekomi_pipelines.replay_reader.live import create_inspection_session

    if os.name == "posix":
        os.setsid()
    # Revalidate the process request before opening canonical state.
    request = IngestionProcessRequest.model_validate_json(request.model_dump_json())
    out, err = ProcessOutput(connection), ProcessOutput(connection, is_error=True)

    def publish(snapshot: ParagraphSnapshot) -> None:
        send_event(connection, ParagraphEvent(snapshot=snapshot))

    try:
        presenter = create_inspection_session(
            Path(request.ledger_path),
            on_snapshot=publish,
            select_ordinal=request.paragraph_ordinal,
            context=InspectionContext(
                request.ingestion_run_id, str(Path(request.ledger_path).parent)
            ),
        )
        with redirect_stdout(out), redirect_stderr(err):
            code = ingest_user_file(
                config_path=Path(request.config_path),
                source_file_path=Path(request.source_path),
                source_url=request.source_url,
                stage_progress=presenter.on_stage_progress,
                paragraph_progress=presenter.on_paragraph_progress,
                stdout=out,
                stderr=err,
                ingestion_run_id_factory=AssignedIngestionRunIdFactory(request.ingestion_run_id),
            )
            if code == 0:
                try:
                    _compose_ingested_run(request)
                except Exception as compose_error:
                    # Derived composition failure never changes ingestion success.
                    err.write(f"Composition pass failed: {compose_error}\n")
    except Exception as error:
        err.write(f"Ingestion worker failed: {error}\n")
        code = 1
    finally:
        out.flush()
        err.flush()
    send_event(connection, FinishedEvent(code=code))
    connection.close()


def _compose_ingested_run(request: IngestionProcessRequest) -> None:
    """Run the composition pass after normal ingestion finalizes."""
    from kotekomi_pipelines.config import load_config
    from kotekomi_pipelines.hybrid_document_ingestion import build_linguistic_analyzer
    from kotekomi_pipelines.ingestion_composition_pass import compose_ingested_run
    from kotekomi_pipelines.model_runtime import build_model_task_runtime

    config = load_config(
        config_path=Path(request.config_path),
        ledger_path_override=None,
        archive_path_override=None,
    )
    runtime = build_model_task_runtime(config.model_execution)
    compose_ingested_run(
        ledger_path=config.ledger_path,
        archive_path=config.archive_path,
        analyzer=build_linguistic_analyzer(config, runtime),
        ingestion_run_id=request.ingestion_run_id,
    )
