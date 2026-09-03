"""Local filesystem implementation of the ArchiveStore Port."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

from kotekomi_application import (
    ArchiveObject,
    ArchivePutDisposition,
    ArchivePutOutcome,
    StagedArchiveObject,
)
from kotekomi_application.hybrid_atomic_claims import (
    HybridAtomicClaimPreview,
    canonical_hybrid_atomic_claim_preview_bytes,
    hybrid_atomic_claim_preview_from_bytes,
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
PDF_TRANSFORMATIONS_DIR = Path("transformations")
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
            PDF_TRANSFORMATIONS_DIR,
        ):
            self._absolute_path(relative_dir).mkdir(parents=True, exist_ok=True)

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
