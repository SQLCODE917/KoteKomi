"""SQLite/Archive implementations of inspection read Ports."""

import hashlib
from pathlib import Path

from kotekomi_application.hybrid_document_orchestration import (
    HybridStageId,
    read_hybrid_stage_output,
)
from kotekomi_application.ingestion_inspection import ArtifactHandle
from kotekomi_domain import DocumentRepresentationBundle

from kotekomi_adapters.local_archive import LocalArchiveStore
from kotekomi_adapters.sqlite_ledger import sqlite_ledger_transaction


class InspectionSourceLoader:
    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        with sqlite_ledger_transaction(self.ledger_path) as ledger:
            return ledger.get_document_representation_bundle(record_id)


class InspectionArtifactLoader:
    def __init__(self, archive: LocalArchiveStore) -> None:
        self.archive = archive

    def describe_stage(self, stage: HybridStageId, output_id: str) -> ArtifactHandle:
        raw, parsed = read_hybrid_stage_output(stage, output_id, self.archive)
        if getattr(parsed, "id", None) != output_id:
            raise ValueError("Inspection artifact identity does not match its archived path.")
        return ArtifactHandle(
            stage.value,
            output_id,
            "archive/" + self.archive.ingestion_evidence_path(stage.value, output_id),
            hashlib.sha256(raw).hexdigest(),
        )
