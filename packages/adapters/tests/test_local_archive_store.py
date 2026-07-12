import hashlib
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import StagedArchiveObject


def test_initialize_creates_archive_directories(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    store.initialize()

    assert (tmp_path / "sources" / "raw").is_dir()
    assert not (tmp_path / "documents" / "extracted").exists()
    assert (tmp_path / "attachments").is_dir()
    assert (tmp_path / "briefings" / "daily").is_dir()


def test_put_and_read_raw_source(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    content = b"raw source bytes"

    outcome = store.put_if_absent_or_identical(
        "src_article_a", content, hashlib.sha256(content).hexdigest()
    )
    archive_object = outcome.object

    assert archive_object.relative_path == "sources/raw/src_article_a.bin"
    assert archive_object.size_bytes == len(b"raw source bytes")
    assert not Path(archive_object.relative_path).is_absolute()
    assert ".." not in Path(archive_object.relative_path).parts
    assert store.read_raw_source("src_article_a") == b"raw source bytes"


def test_put_and_read_model_run_output(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    content = b'{"kind":"abstain","schema_id":"fixture","reason":"ambiguous"}'

    outcome = store.put_model_run_output(
        "mrn_fixture_output",
        content,
        hashlib.sha256(content).hexdigest(),
    )

    assert outcome.object.relative_path == "model-runs/mrn_fixture_output.json"
    assert store.read_model_run_output("mrn_fixture_output") == content


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


def test_stage_and_promote_briefing_citations_json(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    citations_json = '{"briefing_id":"brf_daily","citations":[]}\n'

    staged = store.stage_briefing_citations_json("brf_daily", citations_json)

    assert staged.final_object.relative_path == "briefings/daily/brf_daily.citations.json"
    assert staged.final_object.size_bytes == len(citations_json.encode("utf-8"))
    assert (tmp_path / staged.staged_relative_path).is_file()
    assert not (tmp_path / staged.final_object.relative_path).exists()

    archive_object = store.promote_staged_object(staged)

    assert archive_object == staged.final_object
    assert not (tmp_path / staged.staged_relative_path).exists()
    assert store.read_briefing_citations_json("brf_daily") == citations_json


def test_promote_staged_object_rejects_existing_final_object(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    existing = store.stage_briefing_markdown("brf_daily", "# Existing\n")
    store.promote_staged_object(existing)
    staged = store.stage_briefing_markdown("brf_daily", "# Replacement\n")

    with pytest.raises(FileExistsError, match="briefings/daily/brf_daily.md"):
        store.promote_staged_object(staged)

    assert (tmp_path / staged.staged_relative_path).is_file()


def test_discard_staged_object_preserves_authoritative_archive_objects(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    assert not hasattr(store, "delete_object")
    content = b"raw source bytes"
    store.put_if_absent_or_identical("src_article_a", content, hashlib.sha256(content).hexdigest())
    staged = store.stage_briefing_markdown("brf_daily", "# Staged\n")

    store.discard_staged_object(staged)
    store.discard_staged_object(staged)

    assert store.read_raw_source("src_article_a") == b"raw source bytes"

    with pytest.raises(ValueError, match="Only an ArchiveStore staging object"):
        store.discard_staged_object(
            StagedArchiveObject(
                staged_relative_path="sources/raw/src_article_a.bin",
                final_object=staged.final_object,
            )
        )


def test_put_rejects_existing_raw_source_with_a_different_digest(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    content = b"raw source bytes"
    store.put_if_absent_or_identical("src_article_a", content, hashlib.sha256(content).hexdigest())

    with pytest.raises(ValueError, match="conflicts with its expected digest"):
        store.put_if_absent_or_identical(
            "src_article_a", b"replacement", hashlib.sha256(b"replacement").hexdigest()
        )


def test_missing_reads_raise(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    with pytest.raises(FileNotFoundError):
        store.read_raw_source("src_missing")
    with pytest.raises(FileNotFoundError):
        store.read_briefing_markdown("brf_missing")
    with pytest.raises(FileNotFoundError):
        store.read_briefing_citations_json("brf_missing")


def test_archive_ids_reject_path_characters(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    with pytest.raises(ValueError, match="unsupported path characters"):
        store.put_if_absent_or_identical(
            "../src_escape", b"escape", hashlib.sha256(b"escape").hexdigest()
        )
    with pytest.raises(ValueError, match="unsupported path characters"):
        store.stage_briefing_markdown("brf/escape", "escape")
    with pytest.raises(ValueError, match="unsupported path characters"):
        store.stage_briefing_citations_json("brf/escape", "escape")
