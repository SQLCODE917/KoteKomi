import hashlib
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application.candidate_wiki import (
    RenderedCandidateWiki,
    RenderedWikiFile,
    WikiBuildFileEntry,
    WikiBuildManifest,
    WikiCitationRegistry,
    candidate_wiki_build_id,
    canonical_wiki_citations_bytes,
    canonical_wiki_manifest_bytes,
)


def test_archive_publishes_immutable_build_and_atomically_updates_active_link(
    tmp_path: Path,
) -> None:
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    first = _rendered("first")
    second = _rendered("second")

    created = archive.publish_candidate_wiki(first)
    reused = archive.publish_candidate_wiki(first)
    replaced = archive.publish_candidate_wiki(second)

    active = tmp_path / "archive" / "review" / "wiki"
    assert created.disposition == "created"
    assert reused.disposition == "reused"
    assert replaced.disposition == "created"
    assert active.is_symlink()
    assert active.resolve().name == second.manifest.build_id
    assert (active / "index.md").read_text() == "second\n"
    assert (tmp_path / "archive" / "review" / "wiki-builds" / first.manifest.build_id).is_dir()


def test_archive_rejects_changed_file_before_replacing_active_link(tmp_path: Path) -> None:
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    valid = _rendered("first")
    archive.publish_candidate_wiki(valid)
    active = tmp_path / "archive" / "review" / "wiki"
    previous_target = active.readlink()
    invalid = RenderedCandidateWiki(
        manifest=valid.manifest,
        files=tuple(
            RenderedWikiFile(item.relative_path, b"changed\n")
            if item.relative_path == "index.md"
            else item
            for item in valid.files
        ),
    )

    with pytest.raises(ValueError, match="digest is invalid"):
        archive.publish_candidate_wiki(invalid)

    assert active.readlink() == previous_target
    assert (active / "index.md").read_text() == "first\n"


def _rendered(text: str) -> RenderedCandidateWiki:
    index = f"{text}\n".encode()
    snapshot_digest = hashlib.sha256(text.encode()).hexdigest()
    citations = canonical_wiki_citations_bytes(
        WikiCitationRegistry(candidate_snapshot_digest=snapshot_digest, citations=())
    )
    entries = tuple(
        WikiBuildFileEntry(
            relative_path=path,
            input_fingerprint=hashlib.sha256(payload).hexdigest(),
            content_sha256=hashlib.sha256(payload).hexdigest(),
        )
        for path, payload in (("citations.json", citations), ("index.md", index))
    )
    build_id = candidate_wiki_build_id(
        view_policy_id="candidate_wiki_view_v1",
        renderer_policy_id="deterministic_markdown_wiki_v1",
        ingestion_run_id="igr_example",
        ingestion_change_set_id="ics_example",
        candidate_snapshot_digest=snapshot_digest,
        files=entries,
        counts=(),
    )
    manifest = WikiBuildManifest(
        schema_version="candidate_wiki_manifest_v1",
        build_id=build_id,
        view_policy_id="candidate_wiki_view_v1",
        renderer_policy_id="deterministic_markdown_wiki_v1",
        ingestion_run_id="igr_example",
        ingestion_change_set_id="ics_example",
        candidate_snapshot_digest=snapshot_digest,
        files=entries,
        counts=(),
    )
    return RenderedCandidateWiki(
        manifest,
        (
            RenderedWikiFile("citations.json", citations),
            RenderedWikiFile("index.md", index),
            RenderedWikiFile("manifest.json", canonical_wiki_manifest_bytes(manifest)),
        ),
    )
