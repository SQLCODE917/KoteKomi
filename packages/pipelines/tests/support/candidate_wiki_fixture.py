"""Captured Wiki input for public-command tests and manual UAT; no inference setup."""

from pathlib import Path

from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_domain import (
    AnalysisPlanArtifact,
    AnalysisRun,
    Document,
    DocumentRepresentationBundle,
    IngestionChangeSet,
    IngestionRun,
    IngestionRunStatus,
    ProcessingTaskFingerprint,
    ProvenanceActivity,
    RawBlob,
    Source,
)
from pydantic import BaseModel


class CapturedWikiInput(BaseModel):
    source: Source
    document: Document
    raw_blob: RawBlob
    fingerprint: ProcessingTaskFingerprint
    representation: DocumentRepresentationBundle
    analysis_plan: AnalysisPlanArtifact
    provenance: ProvenanceActivity
    analyses: tuple[AnalysisRun, ...]
    change_sets: tuple[IngestionChangeSet, ...]
    ingestions: tuple[IngestionRun, ...]


def seed_wiki_example(root: Path, *, single_ingestion: bool = False) -> Path:
    """Load domain-valid captured inputs through storage APIs into a fresh directory."""
    fixture = Path(__file__).parents[1] / "fixtures/candidate_wiki/closed_ingestions.json"
    captured = CapturedWikiInput.model_validate_json(fixture.read_text())
    root.mkdir(parents=True, exist_ok=True)
    ledger = root / "kotekomi.db"
    if ledger.exists():
        raise ValueError("Use a fresh directory; existing Ledger contents are preserved.")
    SQLiteLedgerInitializer(ledger).initialize()
    with sqlite_ledger_transaction(ledger) as repository:
        repository.save_source(captured.source)
        repository.save_document(captured.document)
        repository.save_raw_blob(captured.raw_blob)
        repository.ensure_processing_task_fingerprint(captured.fingerprint)
        repository.commit_document_representation_bundle(captured.representation)
        repository.save_analysis_plan_artifact(captured.analysis_plan)
        repository.save_provenance_activity(captured.provenance)
        for index, (analysis, change_set, ingestion) in enumerate(
            zip(captured.analyses, captured.change_sets, captured.ingestions, strict=True)
        ):
            if single_ingestion and index:
                break
            repository.save_analysis_run(analysis)
            repository.create_ingestion_run(
                IngestionRun(
                    id=ingestion.id,
                    requested_path=ingestion.requested_path,
                    display_filename=ingestion.display_filename,
                    requested_source_url=ingestion.requested_source_url,
                    status=IngestionRunStatus.RUNNING,
                    started_at=ingestion.started_at,
                )
            )
            repository.save_ingestion_change_set(change_set)
            if not repository.complete_ingestion_run_if_running(ingestion):
                raise AssertionError("Could not persist captured fixture ingestion")
        unclosed = captured.ingestions[0].model_dump()
        unclosed.update(id="igr_unclosed", analysis_run_id=None, ingestion_change_set_id=None)
        repository.create_ingestion_run(IngestionRun.model_validate(unclosed))
    config = root / "kotekomi.toml"
    config.write_text(
        f'ledger_path = "{ledger.as_posix()}"\n'
        f'archive_path = "{(root / "archive").as_posix()}"\n'
        'runtime_profile = "fixture"\n[processing]\n'
        'representation_policy_version = "deposited-source-v1"\n'
    )
    return config


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(seed_wiki_example(parser.parse_args().directory))
