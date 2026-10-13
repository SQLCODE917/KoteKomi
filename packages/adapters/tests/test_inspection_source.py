"""Source and artifact Adapter implementations satisfy the Application read Ports."""

import hashlib
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore
from kotekomi_adapters.extraction_view import source
from kotekomi_application.hybrid_document_orchestration import HybridStageId
from kotekomi_application.hybrid_mention_interpretation import (
    canonical_hybrid_extraction_preview_bytes,
)
from kotekomi_application.ingestion_inspection import InspectionArtifactPort, InspectionSourcePort
from kotekomi_domain import DocumentRepresentationBundle

from packages.application.tests.test_hybrid_document_references import (
    _bundle,  # pyright: ignore[reportPrivateUsage]
    _parent_preview,  # pyright: ignore[reportPrivateUsage]
)


def test_source_port_opens_the_selected_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _bundle(("Acme acted.",))

    class Ledger:
        def get_document_representation_bundle(
            self, record_id: str
        ) -> DocumentRepresentationBundle | None:
            return bundle if record_id == bundle.representation.id else None

    @contextmanager
    def transaction(path: Path) -> Generator[Ledger, None, None]:
        assert path == Path("selected.db")
        yield Ledger()

    monkeypatch.setattr(source, "sqlite_ledger_transaction", transaction)
    adapter: InspectionSourcePort = source.InspectionSourceLoader(Path("selected.db"))
    assert adapter.get_document_representation_bundle(bundle.representation.id) == bundle
    assert adapter.get_document_representation_bundle("missing") is None


def test_artifact_port_describes_validated_bytes(tmp_path: Path) -> None:
    archive = LocalArchiveStore(tmp_path / "archive")
    bundle = _bundle(("Acme acted.",))
    preview = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Acme",))
    payload = canonical_hybrid_extraction_preview_bytes(preview)
    digest = hashlib.sha256(payload).hexdigest()
    archive.put_hybrid_extraction_preview(preview, payload, digest)
    adapter: InspectionArtifactPort = source.InspectionArtifactLoader(archive)
    handle = adapter.describe_stage(HybridStageId.HP1_MENTIONS, preview.id)
    assert handle.sha256 == digest and handle.output_id == preview.id
    assert (tmp_path / handle.path).read_bytes() == payload
    with pytest.raises(FileNotFoundError):
        adapter.describe_stage(HybridStageId.HP1_MENTIONS, "hxp_" + "a" * 24)
