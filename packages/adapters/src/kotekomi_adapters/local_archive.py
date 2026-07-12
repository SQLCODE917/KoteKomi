"""Local filesystem implementation of the ArchiveStore Port."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from kotekomi_application import (
    ArchiveObject,
    ArchivePutDisposition,
    ArchivePutOutcome,
    StagedArchiveObject,
)

ARCHIVE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
RAW_SOURCE_DIR = Path("sources/raw")
ATTACHMENTS_DIR = Path("attachments")
BRIEFING_DAILY_DIR = Path("briefings/daily")
STAGING_DIR = Path(".staging")


class LocalArchiveStore:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = archive_root

    def initialize(self) -> None:
        for relative_dir in (
            RAW_SOURCE_DIR,
            ATTACHMENTS_DIR,
            BRIEFING_DAILY_DIR,
        ):
            self._absolute_path(relative_dir).mkdir(parents=True, exist_ok=True)

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        relative_path = RAW_SOURCE_DIR / f"{_validate_archive_id(source_id)}.bin"
        absolute_path = self._absolute_path(relative_path)
        return self._write_bytes(relative_path, absolute_path, content)

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

    def read_briefing_markdown(self, briefing_id: str) -> str:
        relative_path = BRIEFING_DAILY_DIR / f"{_validate_archive_id(briefing_id)}.md"
        return self._absolute_path(relative_path).read_text(encoding="utf-8")

    def read_briefing_citations_json(self, briefing_id: str) -> str:
        relative_path = BRIEFING_DAILY_DIR / f"{_validate_archive_id(briefing_id)}.citations.json"
        return self._absolute_path(relative_path).read_text(encoding="utf-8")

    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject:
        final_relative_path = RAW_SOURCE_DIR / f"{_validate_archive_id(source_id)}.bin"
        staged_relative_path = _staged_relative_path(final_relative_path)
        self._write_bytes(staged_relative_path, self._absolute_path(staged_relative_path), content)
        return StagedArchiveObject(
            staged_relative_path=staged_relative_path.as_posix(),
            final_object=ArchiveObject(
                relative_path=final_relative_path.as_posix(),
                size_bytes=len(content),
            ),
        )

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
