"""HP-2 orchestration over one immutable HP-1 Preview."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from kotekomi_domain import DocumentRepresentationBundle

from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    build_hybrid_reference_preview,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_sha256,
)
from kotekomi_application.hybrid_mention_interpretation import (
    PreviewStore,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
)


class HybridReferenceLedger(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class HybridReferenceArchive(PreviewStore, Protocol):
    def put_hybrid_reference_preview(
        self,
        preview: HybridReferencePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes: ...


@dataclass(frozen=True)
class HybridReferencePreviewCommand:
    parent_preview_id: str


@dataclass(frozen=True)
class HybridReferencePreviewResult:
    preview: HybridReferencePreview
    sha256: str
    archive_path: str


def run_hybrid_reference_preview(
    *,
    command: HybridReferencePreviewCommand,
    ledger: HybridReferenceLedger,
    archive: HybridReferenceArchive,
) -> HybridReferencePreviewResult:
    """Run deterministic HP-2 resolution and publish one immutable Preview."""
    parent_payload = archive.read_hybrid_extraction_preview(command.parent_preview_id)
    parent = hybrid_extraction_preview_from_bytes(parent_payload)
    if parent.id != command.parent_preview_id:
        raise ValueError("HP-2 parent Preview identity does not match its Archive path.")
    if canonical_hybrid_extraction_preview_bytes(parent) != parent_payload:
        raise ValueError("HP-2 parent Preview does not use canonical encoding.")
    parent_sha256 = hashlib.sha256(parent_payload).hexdigest()
    bundle = ledger.get_document_representation_bundle(parent.representation_id)
    if bundle is None:
        raise ValueError("HP-2 parent Preview references a missing representation.")
    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=parent_sha256,
        bundle=bundle,
    )
    payload = canonical_hybrid_reference_preview_bytes(preview)
    digest = hybrid_reference_preview_sha256(preview)
    archive.put_hybrid_reference_preview(preview, payload, digest)
    return HybridReferencePreviewResult(
        preview=preview,
        sha256=digest,
        archive_path=f"extraction/reference-previews/{preview.id}.json",
    )
