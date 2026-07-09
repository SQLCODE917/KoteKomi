from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore


def test_initialize_creates_archive_directories(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    store.initialize()

    assert (tmp_path / "sources" / "raw").is_dir()
    assert (tmp_path / "documents" / "extracted").is_dir()
    assert (tmp_path / "attachments").is_dir()
    assert (tmp_path / "briefings" / "daily").is_dir()


def test_write_and_read_raw_source(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    archive_object = store.write_raw_source("src_article_a", b"raw source bytes")

    assert archive_object.relative_path == "sources/raw/src_article_a.bin"
    assert archive_object.size_bytes == len(b"raw source bytes")
    assert not Path(archive_object.relative_path).is_absolute()
    assert ".." not in Path(archive_object.relative_path).parts
    assert store.read_raw_source("src_article_a") == b"raw source bytes"


def test_write_and_read_document_text(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    text = "extracted text with unicode: cafe"

    archive_object = store.write_document_text("doc_article_a", text)

    assert archive_object.relative_path == "documents/extracted/doc_article_a.txt"
    assert archive_object.size_bytes == len(text.encode("utf-8"))
    assert not Path(archive_object.relative_path).is_absolute()
    assert ".." not in Path(archive_object.relative_path).parts
    assert store.read_document_text("doc_article_a") == text


def test_stage_and_promote_raw_source(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    staged = store.stage_raw_source("src_article_a", b"raw source bytes")

    assert staged.final_object.relative_path == "sources/raw/src_article_a.bin"
    assert staged.final_object.size_bytes == len(b"raw source bytes")
    assert staged.staged_relative_path.startswith(".staging/sources/raw/")
    assert (tmp_path / staged.staged_relative_path).is_file()
    assert not (tmp_path / staged.final_object.relative_path).exists()

    archive_object = store.promote_staged_object(staged)

    assert archive_object == staged.final_object
    assert not (tmp_path / staged.staged_relative_path).exists()
    assert store.read_raw_source("src_article_a") == b"raw source bytes"


def test_stage_and_promote_document_text(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    staged = store.stage_document_text("doc_article_a", "extracted text")

    assert staged.final_object.relative_path == "documents/extracted/doc_article_a.txt"
    assert (tmp_path / staged.staged_relative_path).is_file()
    assert not (tmp_path / staged.final_object.relative_path).exists()

    archive_object = store.promote_staged_object(staged)

    assert archive_object == staged.final_object
    assert not (tmp_path / staged.staged_relative_path).exists()
    assert store.read_document_text("doc_article_a") == "extracted text"


def test_stage_and_promote_briefing_markdown(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    staged = store.stage_briefing_markdown("brf_daily", "# Daily Briefing\n")

    assert staged.final_object.relative_path == "briefings/daily/brf_daily.md"
    assert staged.final_object.size_bytes == len(b"# Daily Briefing\n")
    assert (tmp_path / staged.staged_relative_path).is_file()
    assert not (tmp_path / staged.final_object.relative_path).exists()

    archive_object = store.promote_staged_object(staged)

    assert archive_object == staged.final_object
    assert not (tmp_path / staged.staged_relative_path).exists()
    assert store.read_briefing_markdown("brf_daily") == "# Daily Briefing\n"


def test_promote_staged_object_rejects_existing_final_object(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    staged = store.stage_raw_source("src_article_a", b"raw source bytes")
    store.write_raw_source("src_article_a", b"existing")

    with pytest.raises(FileExistsError, match="sources/raw/src_article_a.bin"):
        store.promote_staged_object(staged)

    assert (tmp_path / staged.staged_relative_path).is_file()
    assert store.read_raw_source("src_article_a") == b"existing"


def test_delete_object_removes_archive_object_and_ignores_missing(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    archive_object = store.write_raw_source("src_article_a", b"raw source bytes")

    store.delete_object(archive_object.relative_path)
    store.delete_object(archive_object.relative_path)

    with pytest.raises(FileNotFoundError):
        store.read_raw_source("src_article_a")


def test_duplicate_raw_source_write_raises(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.write_raw_source("src_article_a", b"raw source bytes")

    with pytest.raises(FileExistsError, match="sources/raw/src_article_a.bin"):
        store.write_raw_source("src_article_a", b"replacement")


def test_duplicate_document_text_write_raises(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.write_document_text("doc_article_a", "extracted text")

    with pytest.raises(FileExistsError, match="documents/extracted/doc_article_a.txt"):
        store.write_document_text("doc_article_a", "replacement")


def test_missing_reads_raise(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    with pytest.raises(FileNotFoundError):
        store.read_raw_source("src_missing")
    with pytest.raises(FileNotFoundError):
        store.read_document_text("doc_missing")
    with pytest.raises(FileNotFoundError):
        store.read_briefing_markdown("brf_missing")


def test_archive_ids_reject_path_characters(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    with pytest.raises(ValueError, match="unsupported path characters"):
        store.write_raw_source("../src_escape", b"escape")
    with pytest.raises(ValueError, match="unsupported path characters"):
        store.write_document_text("doc/escape", "escape")
    with pytest.raises(ValueError, match="unsupported path characters"):
        store.stage_raw_source("../src_escape", b"escape")
    with pytest.raises(ValueError, match="unsupported path characters"):
        store.stage_document_text("doc/escape", "escape")
    with pytest.raises(ValueError, match="unsupported path characters"):
        store.stage_briefing_markdown("brf/escape", "escape")
