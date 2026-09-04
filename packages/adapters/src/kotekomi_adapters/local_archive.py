"""Local filesystem implementation of the ArchiveStore Port."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Literal

from kotekomi_application import (
    ArchiveObject,
    ArchivePutDisposition,
    ArchivePutOutcome,
    StagedArchiveObject,
)
from kotekomi_application.candidate_wiki import (
    CandidateWikiPublishResult,
    RenderedCandidateWiki,
    WikiBuildManifest,
    canonical_wiki_citations_bytes,
    canonical_wiki_manifest_bytes,
    wiki_build_manifest_from_bytes,
    wiki_citation_registry_from_bytes,
)
from kotekomi_application.document_entity_reconciliation import (
    DocumentEntityReconciliationPreview,
    ReconciledDocumentProposalPlan,
    canonical_document_entity_reconciliation_preview_bytes,
    canonical_reconciled_document_proposal_plan_bytes,
    document_entity_reconciliation_preview_from_bytes,
    reconciled_document_proposal_plan_from_bytes,
)
from kotekomi_application.hybrid_atomic_claims import (
    HybridAtomicClaimPreview,
    canonical_hybrid_atomic_claim_preview_bytes,
    hybrid_atomic_claim_preview_from_bytes,
)
from kotekomi_application.hybrid_document_orchestration import (
    HybridDocumentCoverageReport,
    HybridParagraphReceipt,
    HybridPipelinePolicyManifest,
    HybridStageId,
    canonical_hybrid_document_coverage_report_bytes,
    canonical_hybrid_paragraph_receipt_bytes,
    canonical_hybrid_pipeline_policy_manifest_bytes,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_entity_grounding import (
    HybridEntityGroundingPreview,
    canonical_hybrid_entity_grounding_preview_bytes,
    hybrid_entity_grounding_preview_from_bytes,
)
from kotekomi_application.hybrid_event_frames import (
    HybridEventFramePreview,
    canonical_hybrid_event_frame_preview_bytes,
    hybrid_event_frame_preview_from_bytes,
)
from kotekomi_application.hybrid_event_semantics import (
    HybridEventSemanticsPreview,
    canonical_hybrid_event_semantics_preview_bytes,
    hybrid_event_semantics_preview_from_bytes,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
)
from kotekomi_application.hybrid_proposed_changes import (
    HybridProposalPlan,
    canonical_hybrid_proposal_plan_bytes,
    hybrid_proposal_plan_from_bytes,
)

ARCHIVE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
RAW_SOURCE_DIR = Path("sources/raw")
ATTACHMENTS_DIR = Path("attachments")
BRIEFING_DAILY_DIR = Path("briefings/daily")
MODEL_RUNS_DIR = Path("model-runs")
HYBRID_EXTRACTION_PREVIEWS_DIR = Path("extraction/previews")
HYBRID_REFERENCE_PREVIEWS_DIR = Path("extraction/reference-previews")
HYBRID_ENTITY_GROUNDING_PREVIEWS_DIR = Path("extraction/entity-grounding-previews")
HYBRID_EVENT_FRAME_PREVIEWS_DIR = Path("extraction/event-frame-previews")
HYBRID_ATOMIC_CLAIM_PREVIEWS_DIR = Path("extraction/atomic-claim-previews")
HYBRID_EVENT_SEMANTICS_PREVIEWS_DIR = Path("extraction/event-semantic-previews")
HYBRID_PROPOSAL_PLANS_DIR = Path("extraction/proposal-plans")
HYBRID_DOCUMENT_POLICIES_DIR = Path("extraction/document-policies")
HYBRID_PARAGRAPH_RECEIPTS_DIR = Path("extraction/paragraph-receipts")
HYBRID_DOCUMENT_COVERAGE_DIR = Path("extraction/document-coverage")
DOCUMENT_ENTITY_RECONCILIATION_PREVIEWS_DIR = Path("extraction/entity-reconciliation-previews")
RECONCILED_DOCUMENT_PROPOSAL_PLANS_DIR = Path("extraction/document-proposal-plans")
PDF_TRANSFORMATIONS_DIR = Path("transformations")
REVIEW_DIR = Path("review")
WIKI_BUILDS_DIR = REVIEW_DIR / "wiki-builds"
ACTIVE_WIKI_PATH = REVIEW_DIR / "wiki"
STAGING_DIR = Path(".staging")


class LocalArchiveStore:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = archive_root

    def initialize(self) -> None:
        for relative_dir in (
            RAW_SOURCE_DIR,
            ATTACHMENTS_DIR,
            BRIEFING_DAILY_DIR,
            MODEL_RUNS_DIR,
            HYBRID_EXTRACTION_PREVIEWS_DIR,
            HYBRID_REFERENCE_PREVIEWS_DIR,
            HYBRID_ENTITY_GROUNDING_PREVIEWS_DIR,
            HYBRID_EVENT_FRAME_PREVIEWS_DIR,
            HYBRID_ATOMIC_CLAIM_PREVIEWS_DIR,
            HYBRID_EVENT_SEMANTICS_PREVIEWS_DIR,
            HYBRID_PROPOSAL_PLANS_DIR,
            HYBRID_DOCUMENT_POLICIES_DIR,
            HYBRID_PARAGRAPH_RECEIPTS_DIR,
            HYBRID_DOCUMENT_COVERAGE_DIR,
            DOCUMENT_ENTITY_RECONCILIATION_PREVIEWS_DIR,
            RECONCILED_DOCUMENT_PROPOSAL_PLANS_DIR,
            PDF_TRANSFORMATIONS_DIR,
            WIKI_BUILDS_DIR,
        ):
            self._absolute_path(relative_dir).mkdir(parents=True, exist_ok=True)

    def publish_candidate_wiki(
        self, rendered_wiki: RenderedCandidateWiki
    ) -> CandidateWikiPublishResult:
        """Validate, immutably publish, then atomically activate one Wiki build."""
        manifest, files = _validated_candidate_wiki_payload(rendered_wiki)
        disposition = self._publish_candidate_wiki_build(manifest.build_id, files)
        self._activate_candidate_wiki_build(manifest.build_id)
        return CandidateWikiPublishResult(
            build_id=manifest.build_id,
            active_relative_path="review/wiki/",
            disposition=disposition,
        )

    def _publish_candidate_wiki_build(
        self, build_id: str, files: dict[str, bytes]
    ) -> Literal["created", "reused"]:
        final_path = self._absolute_path(WIKI_BUILDS_DIR / build_id)
        if final_path.exists():
            _validate_existing_wiki_build(final_path, files)
            return "reused"
        stage_path = self._absolute_path(STAGING_DIR / f"wiki-{uuid.uuid4().hex}")
        stage_path.mkdir(parents=True)
        try:
            _write_wiki_build(stage_path, files)
            _validate_existing_wiki_build(stage_path, files)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage_path, final_path)
        finally:
            if stage_path.exists():
                shutil.rmtree(stage_path)
        return "created"

    def _activate_candidate_wiki_build(self, build_id: str) -> None:
        review_path = self.archive_root.resolve() / REVIEW_DIR
        review_path.mkdir(parents=True, exist_ok=True)
        active_path = review_path / ACTIVE_WIKI_PATH.name
        if active_path.exists() and not active_path.is_symlink():
            raise ValueError("Candidate Wiki active path exists and is not a symlink.")
        temporary_link = review_path / f".wiki-{uuid.uuid4().hex}.tmp"
        try:
            os.symlink((Path("wiki-builds") / build_id).as_posix(), temporary_link)
            os.replace(temporary_link, active_path)
        finally:
            temporary_link.unlink(missing_ok=True)

    def put_if_absent_or_identical(
        self,
        object_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> ArchivePutOutcome:
        actual_digest = hashlib.sha256(payload).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError("Archive payload does not match expected digest.")
        relative_path = RAW_SOURCE_DIR / f"{_validate_archive_id(object_id)}.bin"
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if hashlib.sha256(existing).hexdigest() != expected_digest:
                raise ValueError("Archive object conflicts with its expected digest.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        return ArchivePutOutcome(
            ArchivePutDisposition.CREATED,
            self._write_bytes(relative_path, absolute_path, payload),
        )

    def read_raw_source(self, source_id: str) -> bytes:
        relative_path = RAW_SOURCE_DIR / f"{_validate_archive_id(source_id)}.bin"
        return self._absolute_path(relative_path).read_bytes()

    def put_pdf_transformation_blob(
        self,
        object_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> ArchivePutOutcome:
        actual_digest = hashlib.sha256(payload).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError("PDF transformation payload does not match expected digest.")
        relative_path = PDF_TRANSFORMATIONS_DIR / f"{_validate_archive_id(object_id)}.bin"
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if hashlib.sha256(existing).hexdigest() != expected_digest:
                raise ValueError("PDF transformation object conflicts with its expected digest.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        return ArchivePutOutcome(
            ArchivePutDisposition.CREATED,
            self._write_bytes(relative_path, absolute_path, payload),
        )

    def read_pdf_transformation_blob(self, object_id: str) -> bytes:
        relative_path = PDF_TRANSFORMATIONS_DIR / f"{_validate_archive_id(object_id)}.bin"
        return self._absolute_path(relative_path).read_bytes()

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> ArchivePutOutcome:
        actual_digest = hashlib.sha256(payload).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError("ModelRun output does not match expected digest.")
        relative_path = MODEL_RUNS_DIR / f"{_validate_archive_id(model_run_id)}.json"
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if hashlib.sha256(existing).hexdigest() != expected_digest:
                raise ValueError("ModelRun output conflicts with its expected digest.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        return ArchivePutOutcome(
            ArchivePutDisposition.CREATED,
            self._write_bytes(relative_path, absolute_path, payload),
        )

    def read_model_run_output(self, model_run_id: str) -> bytes:
        relative_path = MODEL_RUNS_DIR / f"{_validate_archive_id(model_run_id)}.json"
        return self._absolute_path(relative_path).read_bytes()

    def put_hybrid_extraction_preview(
        self,
        preview: HybridExtractionPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_extraction_preview_from_bytes(payload)
        if parsed != preview or canonical_hybrid_extraction_preview_bytes(parsed) != payload:
            raise ValueError("HybridExtractionPreview payload is not its canonical DTO encoding.")
        actual_digest = hashlib.sha256(payload).hexdigest()
        if actual_digest != expected_sha256:
            raise ValueError("HybridExtractionPreview payload does not match expected digest.")
        relative_path = HYBRID_EXTRACTION_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview.id)}.json"
        )
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError("HybridExtractionPreview conflicts with its immutable identity.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridExtractionPreview conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes:
        relative_path = HYBRID_EXTRACTION_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        preview = hybrid_extraction_preview_from_bytes(payload)
        if (
            preview.id != preview_id
            or canonical_hybrid_extraction_preview_bytes(preview) != payload
        ):
            raise ValueError("Stored HybridExtractionPreview failed canonical validation.")
        return payload

    def put_hybrid_reference_preview(
        self,
        preview: HybridReferencePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_reference_preview_from_bytes(payload)
        if parsed != preview or canonical_hybrid_reference_preview_bytes(parsed) != payload:
            raise ValueError("HybridReferencePreview payload is not its canonical DTO encoding.")
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("HybridReferencePreview payload does not match expected digest.")
        relative_path = HYBRID_REFERENCE_PREVIEWS_DIR / (f"{_validate_archive_id(preview.id)}.json")
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError("HybridReferencePreview conflicts with its immutable identity.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridReferencePreview conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes:
        relative_path = HYBRID_REFERENCE_PREVIEWS_DIR / (f"{_validate_archive_id(preview_id)}.json")
        payload = self._absolute_path(relative_path).read_bytes()
        preview = hybrid_reference_preview_from_bytes(payload)
        if preview.id != preview_id or canonical_hybrid_reference_preview_bytes(preview) != payload:
            raise ValueError("Stored HybridReferencePreview failed canonical validation.")
        return payload

    def put_hybrid_entity_grounding_preview(
        self,
        preview: HybridEntityGroundingPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_entity_grounding_preview_from_bytes(payload)
        if parsed != preview or canonical_hybrid_entity_grounding_preview_bytes(parsed) != payload:
            raise ValueError(
                "HybridEntityGroundingPreview payload is not its canonical DTO encoding."
            )
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("HybridEntityGroundingPreview payload does not match expected digest.")
        relative_path = HYBRID_ENTITY_GROUNDING_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview.id)}.json"
        )
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridEntityGroundingPreview conflicts with its immutable identity."
                )
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridEntityGroundingPreview conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_entity_grounding_preview(self, preview_id: str) -> bytes:
        relative_path = HYBRID_ENTITY_GROUNDING_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        preview = hybrid_entity_grounding_preview_from_bytes(payload)
        if (
            preview.id != preview_id
            or canonical_hybrid_entity_grounding_preview_bytes(preview) != payload
        ):
            raise ValueError("Stored HybridEntityGroundingPreview failed canonical validation.")
        return payload

    def put_hybrid_event_frame_preview(
        self,
        preview: HybridEventFramePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_event_frame_preview_from_bytes(payload)
        if parsed != preview or canonical_hybrid_event_frame_preview_bytes(parsed) != payload:
            raise ValueError("HybridEventFramePreview payload is not its canonical DTO encoding.")
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("HybridEventFramePreview payload does not match expected digest.")
        relative_path = HYBRID_EVENT_FRAME_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview.id)}.json"
        )
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError("HybridEventFramePreview conflicts with its immutable identity.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridEventFramePreview conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_event_frame_preview(self, preview_id: str) -> bytes:
        relative_path = HYBRID_EVENT_FRAME_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        preview = hybrid_event_frame_preview_from_bytes(payload)
        if (
            preview.id != preview_id
            or canonical_hybrid_event_frame_preview_bytes(preview) != payload
        ):
            raise ValueError("Stored HybridEventFramePreview failed canonical validation.")
        return payload

    def put_hybrid_atomic_claim_preview(
        self,
        preview: HybridAtomicClaimPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_atomic_claim_preview_from_bytes(payload)
        if parsed != preview or canonical_hybrid_atomic_claim_preview_bytes(parsed) != payload:
            raise ValueError("HybridAtomicClaimPreview payload is not its canonical DTO encoding.")
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("HybridAtomicClaimPreview payload does not match expected digest.")
        relative_path = HYBRID_ATOMIC_CLAIM_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview.id)}.json"
        )
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError("HybridAtomicClaimPreview conflicts with its immutable identity.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridAtomicClaimPreview conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_atomic_claim_preview(self, preview_id: str) -> bytes:
        relative_path = HYBRID_ATOMIC_CLAIM_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        preview = hybrid_atomic_claim_preview_from_bytes(payload)
        if (
            preview.id != preview_id
            or canonical_hybrid_atomic_claim_preview_bytes(preview) != payload
        ):
            raise ValueError("Stored HybridAtomicClaimPreview failed canonical validation.")
        return payload

    def put_hybrid_event_semantics_preview(
        self,
        preview: HybridEventSemanticsPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_event_semantics_preview_from_bytes(payload)
        if parsed != preview or canonical_hybrid_event_semantics_preview_bytes(parsed) != payload:
            raise ValueError(
                "HybridEventSemanticsPreview payload is not its canonical DTO encoding."
            )
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("HybridEventSemanticsPreview payload does not match expected digest.")
        relative_path = HYBRID_EVENT_SEMANTICS_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview.id)}.json"
        )
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridEventSemanticsPreview conflicts with its immutable identity."
                )
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridEventSemanticsPreview conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_event_semantics_preview(self, preview_id: str) -> bytes:
        relative_path = HYBRID_EVENT_SEMANTICS_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        preview = hybrid_event_semantics_preview_from_bytes(payload)
        if (
            preview.id != preview_id
            or canonical_hybrid_event_semantics_preview_bytes(preview) != payload
        ):
            raise ValueError("Stored HybridEventSemanticsPreview failed canonical validation.")
        return payload

    def put_hybrid_proposal_plan(
        self,
        plan: HybridProposalPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_proposal_plan_from_bytes(payload)
        if parsed != plan or canonical_hybrid_proposal_plan_bytes(parsed) != payload:
            raise ValueError("HybridProposalPlan payload is not its canonical DTO encoding.")
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("HybridProposalPlan payload does not match expected digest.")
        relative_path = HYBRID_PROPOSAL_PLANS_DIR / f"{_validate_archive_id(plan.id)}.json"
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError("HybridProposalPlan conflicts with its immutable identity.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(
                    "HybridProposalPlan conflicts with its immutable identity."
                ) from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def read_hybrid_proposal_plan(self, plan_id: str) -> bytes:
        relative_path = HYBRID_PROPOSAL_PLANS_DIR / f"{_validate_archive_id(plan_id)}.json"
        payload = self._absolute_path(relative_path).read_bytes()
        plan = hybrid_proposal_plan_from_bytes(payload)
        if plan.id != plan_id or canonical_hybrid_proposal_plan_bytes(plan) != payload:
            raise ValueError("Stored HybridProposalPlan failed canonical validation.")
        return payload

    def put_hybrid_pipeline_policy_manifest(
        self,
        manifest: HybridPipelinePolicyManifest,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_pipeline_policy_manifest_from_bytes(payload)
        if parsed != manifest or canonical_hybrid_pipeline_policy_manifest_bytes(parsed) != payload:
            raise ValueError("Hybrid Pipeline Policy payload is not its canonical DTO encoding.")
        return self._put_hybrid_evidence(
            HYBRID_DOCUMENT_POLICIES_DIR,
            manifest.id,
            payload,
            expected_sha256,
            "Hybrid Pipeline Policy",
        )

    def read_hybrid_pipeline_policy_manifest(self, manifest_id: str) -> bytes:
        relative_path = HYBRID_DOCUMENT_POLICIES_DIR / (f"{_validate_archive_id(manifest_id)}.json")
        payload = self._absolute_path(relative_path).read_bytes()
        manifest = hybrid_pipeline_policy_manifest_from_bytes(payload)
        if (
            manifest.id != manifest_id
            or canonical_hybrid_pipeline_policy_manifest_bytes(manifest) != payload
        ):
            raise ValueError("Stored Hybrid Pipeline Policy failed canonical validation.")
        return payload

    def put_hybrid_paragraph_receipt(
        self,
        receipt: HybridParagraphReceipt,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_paragraph_receipt_from_bytes(payload)
        if parsed != receipt or canonical_hybrid_paragraph_receipt_bytes(parsed) != payload:
            raise ValueError("Paragraph Receipt payload is not its canonical DTO encoding.")
        return self._put_hybrid_evidence(
            HYBRID_PARAGRAPH_RECEIPTS_DIR,
            receipt.id,
            payload,
            expected_sha256,
            "Paragraph Receipt",
        )

    def read_hybrid_paragraph_receipt(self, receipt_id: str) -> bytes:
        relative_path = HYBRID_PARAGRAPH_RECEIPTS_DIR / (f"{_validate_archive_id(receipt_id)}.json")
        payload = self._absolute_path(relative_path).read_bytes()
        receipt = hybrid_paragraph_receipt_from_bytes(payload)
        if receipt.id != receipt_id or canonical_hybrid_paragraph_receipt_bytes(receipt) != payload:
            raise ValueError("Stored Paragraph Receipt failed canonical validation.")
        return payload

    def put_hybrid_document_coverage_report(
        self,
        report: HybridDocumentCoverageReport,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = hybrid_document_coverage_report_from_bytes(payload)
        if parsed != report or canonical_hybrid_document_coverage_report_bytes(parsed) != payload:
            raise ValueError("Hybrid coverage payload is not its canonical DTO encoding.")
        return self._put_hybrid_evidence(
            HYBRID_DOCUMENT_COVERAGE_DIR,
            report.id,
            payload,
            expected_sha256,
            "Hybrid coverage report",
        )

    def read_hybrid_document_coverage_report(self, report_id: str) -> bytes:
        relative_path = HYBRID_DOCUMENT_COVERAGE_DIR / (f"{_validate_archive_id(report_id)}.json")
        payload = self._absolute_path(relative_path).read_bytes()
        report = hybrid_document_coverage_report_from_bytes(payload)
        if (
            report.id != report_id
            or canonical_hybrid_document_coverage_report_bytes(report) != payload
        ):
            raise ValueError("Stored Hybrid coverage report failed canonical validation.")
        return payload

    def put_document_entity_reconciliation_preview(
        self,
        preview: DocumentEntityReconciliationPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = document_entity_reconciliation_preview_from_bytes(payload)
        if (
            parsed != preview
            or canonical_document_entity_reconciliation_preview_bytes(parsed) != payload
        ):
            raise ValueError("HP-9 Preview payload is not its canonical DTO encoding.")
        return self._put_hybrid_evidence(
            DOCUMENT_ENTITY_RECONCILIATION_PREVIEWS_DIR,
            preview.id,
            payload,
            expected_sha256,
            "HP-9 Preview",
        )

    def read_document_entity_reconciliation_preview(self, preview_id: str) -> bytes:
        relative_path = DOCUMENT_ENTITY_RECONCILIATION_PREVIEWS_DIR / (
            f"{_validate_archive_id(preview_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        preview = document_entity_reconciliation_preview_from_bytes(payload)
        if (
            preview.id != preview_id
            or canonical_document_entity_reconciliation_preview_bytes(preview) != payload
        ):
            raise ValueError("Stored HP-9 Preview failed canonical validation.")
        return payload

    def put_reconciled_document_proposal_plan(
        self,
        plan: ReconciledDocumentProposalPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> ArchivePutOutcome:
        parsed = reconciled_document_proposal_plan_from_bytes(payload)
        if parsed != plan or canonical_reconciled_document_proposal_plan_bytes(parsed) != payload:
            raise ValueError("HP-9 Document Plan payload is not its canonical DTO encoding.")
        return self._put_hybrid_evidence(
            RECONCILED_DOCUMENT_PROPOSAL_PLANS_DIR,
            plan.id,
            payload,
            expected_sha256,
            "HP-9 Document Plan",
        )

    def read_reconciled_document_proposal_plan(self, plan_id: str) -> bytes:
        relative_path = RECONCILED_DOCUMENT_PROPOSAL_PLANS_DIR / (
            f"{_validate_archive_id(plan_id)}.json"
        )
        payload = self._absolute_path(relative_path).read_bytes()
        plan = reconciled_document_proposal_plan_from_bytes(payload)
        if plan.id != plan_id or canonical_reconciled_document_proposal_plan_bytes(plan) != payload:
            raise ValueError("Stored HP-9 Document Plan failed canonical validation.")
        return payload

    def find_hybrid_document_coverage_report_by_sha256(self, expected_sha256: str) -> str | None:
        if re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is None:
            raise ValueError("Hybrid coverage lookup requires a SHA-256 digest.")
        directory = self._absolute_path(HYBRID_DOCUMENT_COVERAGE_DIR)
        if not directory.exists():
            return None
        matches: list[str] = []
        for path in sorted(directory.glob("*.json")):
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != expected_sha256:
                continue
            report = hybrid_document_coverage_report_from_bytes(payload)
            if path.stem != report.id:
                raise ValueError("Stored Hybrid coverage report path has the wrong identity.")
            if canonical_hybrid_document_coverage_report_bytes(report) != payload:
                raise ValueError("Stored Hybrid coverage report failed canonical validation.")
            matches.append(report.id)
        if len(matches) > 1:
            raise ValueError("Hybrid coverage digest matches multiple Archive records.")
        return matches[0] if matches else None

    def ingestion_evidence_path(self, record_type: str, record_id: str) -> str:
        directories = {
            "ModelRunOutput": MODEL_RUNS_DIR,
            "HybridDocumentCoverageReport": HYBRID_DOCUMENT_COVERAGE_DIR,
            "HybridPipelinePolicyManifest": HYBRID_DOCUMENT_POLICIES_DIR,
            "HybridParagraphReceipt": HYBRID_PARAGRAPH_RECEIPTS_DIR,
            "DocumentEntityReconciliationPreview": (DOCUMENT_ENTITY_RECONCILIATION_PREVIEWS_DIR),
            "ReconciledDocumentProposalPlan": RECONCILED_DOCUMENT_PROPOSAL_PLANS_DIR,
            HybridStageId.HP1_MENTIONS.value: HYBRID_EXTRACTION_PREVIEWS_DIR,
            HybridStageId.HP2_REFERENCES.value: HYBRID_REFERENCE_PREVIEWS_DIR,
            HybridStageId.HP3_GROUNDING.value: HYBRID_ENTITY_GROUNDING_PREVIEWS_DIR,
            HybridStageId.HP4_EVENT_FRAMES.value: HYBRID_EVENT_FRAME_PREVIEWS_DIR,
            HybridStageId.HP5_ATOMIC_CLAIMS.value: HYBRID_ATOMIC_CLAIM_PREVIEWS_DIR,
            HybridStageId.HP6_EVENT_SEMANTICS.value: HYBRID_EVENT_SEMANTICS_PREVIEWS_DIR,
            HybridStageId.HP7_PROPOSAL_PLAN.value: HYBRID_PROPOSAL_PLANS_DIR,
        }
        try:
            directory = directories[record_type]
        except KeyError as error:
            raise ValueError(f"Unsupported ingestion evidence type: {record_type}") from error
        return (directory / f"{_validate_archive_id(record_id)}.json").as_posix()

    def read_briefing_markdown(self, briefing_id: str) -> str:
        relative_path = BRIEFING_DAILY_DIR / f"{_validate_archive_id(briefing_id)}.md"
        return self._absolute_path(relative_path).read_text(encoding="utf-8")

    def read_briefing_citations_json(self, briefing_id: str) -> str:
        relative_path = BRIEFING_DAILY_DIR / f"{_validate_archive_id(briefing_id)}.citations.json"
        return self._absolute_path(relative_path).read_text(encoding="utf-8")

    def stage_briefing_markdown(
        self,
        briefing_id: str,
        markdown: str,
    ) -> StagedArchiveObject:
        final_relative_path = BRIEFING_DAILY_DIR / f"{_validate_archive_id(briefing_id)}.md"
        staged_relative_path = _staged_relative_path(final_relative_path)
        content = markdown.encode("utf-8")
        self._write_bytes(staged_relative_path, self._absolute_path(staged_relative_path), content)
        return StagedArchiveObject(
            staged_relative_path=staged_relative_path.as_posix(),
            final_object=ArchiveObject(
                relative_path=final_relative_path.as_posix(),
                size_bytes=len(content),
            ),
        )

    def stage_briefing_citations_json(
        self,
        briefing_id: str,
        citations_json: str,
    ) -> StagedArchiveObject:
        final_relative_path = (
            BRIEFING_DAILY_DIR / f"{_validate_archive_id(briefing_id)}.citations.json"
        )
        staged_relative_path = _staged_relative_path(final_relative_path)
        content = citations_json.encode("utf-8")
        self._write_bytes(staged_relative_path, self._absolute_path(staged_relative_path), content)
        return StagedArchiveObject(
            staged_relative_path=staged_relative_path.as_posix(),
            final_object=ArchiveObject(
                relative_path=final_relative_path.as_posix(),
                size_bytes=len(content),
            ),
        )

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        staged_path = self._absolute_path(Path(staged_object.staged_relative_path))
        final_path = self._absolute_path(Path(staged_object.final_object.relative_path))
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            raise FileExistsError(
                f"Archive object already exists: {staged_object.final_object.relative_path}"
            )
        staged_path.rename(final_path)
        return staged_object.final_object

    def discard_staged_object(self, staged_object: StagedArchiveObject) -> None:
        staged_relative_path = Path(staged_object.staged_relative_path)
        if not staged_relative_path.is_relative_to(STAGING_DIR):
            raise ValueError("Only an ArchiveStore staging object may be discarded.")
        absolute_path = self._absolute_path(staged_relative_path)
        if absolute_path.exists():
            absolute_path.unlink()

    def _write_bytes(
        self,
        relative_path: Path,
        absolute_path: Path,
        content: bytes,
    ) -> ArchiveObject:
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with absolute_path.open("xb") as archive_file:
                archive_file.write(content)
        except FileExistsError as exc:
            message = f"Archive object already exists: {relative_path.as_posix()}"
            raise FileExistsError(message) from exc
        return ArchiveObject(
            relative_path=relative_path.as_posix(),
            size_bytes=len(content),
        )

    def _put_hybrid_evidence(
        self,
        relative_dir: Path,
        record_id: str,
        payload: bytes,
        expected_sha256: str,
        label: str,
    ) -> ArchivePutOutcome:
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError(f"{label} payload does not match expected digest.")
        relative_path = relative_dir / f"{_validate_archive_id(record_id)}.json"
        absolute_path = self._absolute_path(relative_path)
        if absolute_path.exists():
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(f"{label} conflicts with its immutable identity.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(relative_path.as_posix(), len(existing)),
            )
        staged_relative = _staged_relative_path(relative_path)
        staged_path = self._absolute_path(staged_relative)
        self._write_bytes(staged_relative, staged_path, payload)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        disposition = ArchivePutDisposition.CREATED
        try:
            os.link(staged_path, absolute_path)
        except FileExistsError:
            existing = absolute_path.read_bytes()
            if existing != payload:
                raise ValueError(f"{label} conflicts with its immutable identity.") from None
            disposition = ArchivePutDisposition.REUSED
        finally:
            staged_path.unlink(missing_ok=True)
        return ArchivePutOutcome(
            disposition,
            ArchiveObject(relative_path.as_posix(), len(payload)),
        )

    def _absolute_path(self, relative_path: Path) -> Path:
        absolute_root = self.archive_root.resolve()
        absolute_path = (absolute_root / relative_path).resolve()
        if not absolute_path.is_relative_to(absolute_root):
            raise ValueError(f"Archive path escapes Archive root: {relative_path.as_posix()}")
        return absolute_path


def _validate_archive_id(record_id: str) -> str:
    if not ARCHIVE_ID_PATTERN.fullmatch(record_id):
        raise ValueError(f"Archive id contains unsupported path characters: {record_id}")
    return record_id


def _staged_relative_path(final_relative_path: Path) -> Path:
    return (
        STAGING_DIR / final_relative_path.parent / f"{final_relative_path.name}.{uuid.uuid4()}.tmp"
    )


def _validate_wiki_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Candidate Wiki path is unsafe: {value}")
    if path.suffix not in {".md", ".json"}:
        raise ValueError(f"Candidate Wiki file type is unsupported: {value}")


def _validated_candidate_wiki_payload(
    rendered_wiki: RenderedCandidateWiki,
) -> tuple[WikiBuildManifest, dict[str, bytes]]:
    files = {item.relative_path: item.payload for item in rendered_wiki.files}
    if len(files) != len(rendered_wiki.files):
        raise ValueError("Candidate Wiki contains duplicate file paths.")
    manifest_payload = files.get("manifest.json")
    if manifest_payload is None:
        raise ValueError("Candidate Wiki is missing manifest.json.")
    manifest = wiki_build_manifest_from_bytes(manifest_payload)
    if (
        manifest != rendered_wiki.manifest
        or canonical_wiki_manifest_bytes(manifest) != manifest_payload
    ):
        raise ValueError("Candidate Wiki manifest is not its canonical encoding.")
    expected_paths = {item.relative_path for item in manifest.files} | {"manifest.json"}
    if set(files) != expected_paths:
        raise ValueError("Candidate Wiki files do not match its manifest.")
    _validate_candidate_wiki_citations(files, manifest)
    entries = {item.relative_path: item for item in manifest.files}
    for relative_path, payload in files.items():
        _validate_wiki_relative_path(relative_path)
        if relative_path != "manifest.json" and (
            hashlib.sha256(payload).hexdigest() != entries[relative_path].content_sha256
        ):
            raise ValueError(f"Candidate Wiki file digest is invalid: {relative_path}")
    return manifest, files


def _validate_candidate_wiki_citations(
    files: dict[str, bytes], manifest: WikiBuildManifest
) -> None:
    citations_payload = files.get("citations.json")
    if citations_payload is None:
        raise ValueError("Candidate Wiki is missing citations.json.")
    citations = wiki_citation_registry_from_bytes(citations_payload)
    if (
        citations.candidate_snapshot_digest != manifest.candidate_snapshot_digest
        or canonical_wiki_citations_bytes(citations) != citations_payload
    ):
        raise ValueError("Candidate Wiki citations are not canonical for its manifest.")


def _write_wiki_build(build_path: Path, files: dict[str, bytes]) -> None:
    for relative_path, payload in sorted(files.items()):
        target = build_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def _validate_existing_wiki_build(build_path: Path, expected_files: dict[str, bytes]) -> None:
    if not build_path.is_dir() or build_path.is_symlink():
        raise ValueError("Candidate Wiki build path is not an immutable directory.")
    descendants = tuple(build_path.rglob("*"))
    if any(path.is_symlink() for path in descendants):
        raise ValueError("Candidate Wiki immutable build must not contain symlinks.")
    actual_paths = {
        path.relative_to(build_path).as_posix() for path in descendants if path.is_file()
    }
    if actual_paths != set(expected_files):
        raise ValueError("Candidate Wiki build contains absent or extra files.")
    for relative_path, expected in expected_files.items():
        path = build_path / relative_path
        if path.is_symlink() or path.read_bytes() != expected:
            raise ValueError(f"Candidate Wiki immutable build conflicts: {relative_path}")
