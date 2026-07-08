"""Local filesystem implementation of the ArchiveStore Port."""

from __future__ import annotations

import re
from pathlib import Path

from kotekomi_application import ArchiveObject

ARCHIVE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
RAW_SOURCE_DIR = Path("sources/raw")
EXTRACTED_DOCUMENT_DIR = Path("documents/extracted")
ATTACHMENTS_DIR = Path("attachments")


class LocalArchiveStore:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = archive_root

    def initialize(self) -> None:
        for relative_dir in (RAW_SOURCE_DIR, EXTRACTED_DOCUMENT_DIR, ATTACHMENTS_DIR):
            self._absolute_path(relative_dir).mkdir(parents=True, exist_ok=True)

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        relative_path = RAW_SOURCE_DIR / f"{_validate_archive_id(source_id)}.bin"
        absolute_path = self._absolute_path(relative_path)
        return self._write_bytes(relative_path, absolute_path, content)

    def read_raw_source(self, source_id: str) -> bytes:
        relative_path = RAW_SOURCE_DIR / f"{_validate_archive_id(source_id)}.bin"
        return self._absolute_path(relative_path).read_bytes()

    def write_document_text(self, document_id: str, text: str) -> ArchiveObject:
        relative_path = EXTRACTED_DOCUMENT_DIR / f"{_validate_archive_id(document_id)}.txt"
        absolute_path = self._absolute_path(relative_path)
        content = text.encode("utf-8")
        return self._write_bytes(relative_path, absolute_path, content)

    def read_document_text(self, document_id: str) -> str:
        relative_path = EXTRACTED_DOCUMENT_DIR / f"{_validate_archive_id(document_id)}.txt"
        return self._absolute_path(relative_path).read_text(encoding="utf-8")

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
