import hashlib
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ArchivePutDisposition,
    HybridAtomicClaimStatus,
    HybridEntityGroundingStatus,
    HybridEventFrameStatus,
    HybridPreviewStatus,
    StagedArchiveObject,
    build_hybrid_atomic_claim_preview,
    build_hybrid_entity_grounding_preview_record,
    build_hybrid_event_frame_preview,
    build_hybrid_extraction_preview,
    build_hybrid_reference_preview_record,
    canonical_hybrid_atomic_claim_preview_bytes,
    canonical_hybrid_entity_grounding_preview_bytes,
    canonical_hybrid_event_frame_preview_bytes,
    canonical_hybrid_extraction_preview_bytes,
    canonical_hybrid_reference_preview_bytes,
    hybrid_atomic_claim_preview_sha256,
    hybrid_entity_grounding_preview_sha256,
    hybrid_event_frame_preview_sha256,
    hybrid_extraction_preview_sha256,
    hybrid_reference_preview_sha256,
)


def test_initialize_creates_archive_directories(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)

    store.initialize()

    assert (tmp_path / "sources" / "raw").is_dir()
    assert not (tmp_path / "documents" / "extracted").exists()
    assert (tmp_path / "attachments").is_dir()
    assert (tmp_path / "briefings" / "daily").is_dir()
    assert (tmp_path / "extraction" / "previews").is_dir()
    assert (tmp_path / "extraction" / "reference-previews").is_dir()
    assert (tmp_path / "extraction" / "entity-grounding-previews").is_dir()
    assert (tmp_path / "extraction" / "event-frame-previews").is_dir()
    assert (tmp_path / "extraction" / "atomic-claim-previews").is_dir()
    assert (tmp_path / "transformations").is_dir()


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
    content = b"outcome: abstain\nreason: ambiguous\n"

    outcome = store.put_model_run_output(
        "mrn_fixture_output",
        content,
        hashlib.sha256(content).hexdigest(),
    )

    assert outcome.object.relative_path == "model-runs/mrn_fixture_output.json"
    assert store.read_model_run_output("mrn_fixture_output") == content


def test_put_reuse_and_restart_hybrid_extraction_preview(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    preview = build_hybrid_extraction_preview(
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_id="ctx_fixture",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    payload = canonical_hybrid_extraction_preview_bytes(preview)
    digest = hybrid_extraction_preview_sha256(preview)

    created = store.put_hybrid_extraction_preview(preview, payload, digest)
    reused = store.put_hybrid_extraction_preview(preview, payload, digest)
    reopened = LocalArchiveStore(tmp_path)

    assert created.disposition is ArchivePutDisposition.CREATED
    assert reused.disposition is ArchivePutDisposition.REUSED
    assert reopened.read_hybrid_extraction_preview(preview.id) == payload


def test_hybrid_extraction_preview_rejects_immutable_identity_conflict(
    tmp_path: Path,
) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    preview = build_hybrid_extraction_preview(
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_id="ctx_fixture",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    payload = canonical_hybrid_extraction_preview_bytes(preview)
    digest = hybrid_extraction_preview_sha256(preview)
    store.put_hybrid_extraction_preview(preview, payload, digest)
    stored_path = tmp_path / "extraction" / "previews" / f"{preview.id}.json"
    stored_path.write_bytes(b"different bytes")

    with pytest.raises(ValueError, match="immutable identity"):
        store.put_hybrid_extraction_preview(preview, payload, digest)


def test_put_reuse_and_restart_hybrid_reference_preview(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    parent = build_hybrid_extraction_preview(
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_id="ctx_fixture",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    preview = build_hybrid_reference_preview_record(
        parent_preview_id=parent.id,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        representation_id="rep_fixture",
        alias_declarations=(),
        reference_decisions=(),
        traces=(),
    )
    payload = canonical_hybrid_reference_preview_bytes(preview)
    digest = hybrid_reference_preview_sha256(preview)

    created = store.put_hybrid_reference_preview(preview, payload, digest)
    reused = store.put_hybrid_reference_preview(preview, payload, digest)
    reopened = LocalArchiveStore(tmp_path)

    assert created.disposition is ArchivePutDisposition.CREATED
    assert reused.disposition is ArchivePutDisposition.REUSED
    assert reopened.read_hybrid_reference_preview(preview.id) == payload


def test_hybrid_reference_preview_rejects_tampered_stored_bytes(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    parent = build_hybrid_extraction_preview(
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_id="ctx_fixture",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    preview = build_hybrid_reference_preview_record(
        parent_preview_id=parent.id,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        representation_id="rep_fixture",
        alias_declarations=(),
        reference_decisions=(),
        traces=(),
    )
    payload = canonical_hybrid_reference_preview_bytes(preview)
    store.put_hybrid_reference_preview(
        preview,
        payload,
        hybrid_reference_preview_sha256(preview),
    )
    stored = tmp_path / "extraction" / "reference-previews" / f"{preview.id}.json"
    stored.write_bytes(b"different bytes")

    with pytest.raises(ValueError):
        store.read_hybrid_reference_preview(preview.id)


def test_put_reuse_and_restart_hybrid_entity_grounding_preview(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    preview = build_hybrid_entity_grounding_preview_record(
        parent_preview_id="hrp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        mention_preview_id="hxp_" + "2" * 24,
        mention_preview_sha256="b" * 64,
        representation_id="rep_fixture",
        eligibility=(),
        link_evidence=(),
        extraction_task_ids=(),
        model_run_ids=(),
        traces=(),
        terminal_status=HybridEntityGroundingStatus.COMPLETE,
        diagnostics=(),
    )
    payload = canonical_hybrid_entity_grounding_preview_bytes(preview)
    digest = hybrid_entity_grounding_preview_sha256(preview)

    created = store.put_hybrid_entity_grounding_preview(preview, payload, digest)
    reused = store.put_hybrid_entity_grounding_preview(preview, payload, digest)
    reopened = LocalArchiveStore(tmp_path)

    assert created.disposition is ArchivePutDisposition.CREATED
    assert reused.disposition is ArchivePutDisposition.REUSED
    assert reopened.read_hybrid_entity_grounding_preview(preview.id) == payload


def test_put_reuse_and_restart_hybrid_event_frame_preview(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    preview = build_hybrid_event_frame_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        trigger_context_manifest_id="ctx_trigger",
        frame_context_manifest_id="ctx_frame",
        terminal_status=HybridEventFrameStatus.COMPLETE,
    )
    payload = canonical_hybrid_event_frame_preview_bytes(preview)
    digest = hybrid_event_frame_preview_sha256(preview)

    created = store.put_hybrid_event_frame_preview(preview, payload, digest)
    reused = store.put_hybrid_event_frame_preview(preview, payload, digest)
    reopened = LocalArchiveStore(tmp_path)

    assert created.disposition is ArchivePutDisposition.CREATED
    assert reused.disposition is ArchivePutDisposition.REUSED
    assert reopened.read_hybrid_event_frame_preview(preview.id) == payload


def test_hybrid_event_frame_preview_rejects_tampered_stored_bytes(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    preview = build_hybrid_event_frame_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        trigger_context_manifest_id="ctx_trigger",
        frame_context_manifest_id="ctx_frame",
        terminal_status=HybridEventFrameStatus.COMPLETE,
    )
    payload = canonical_hybrid_event_frame_preview_bytes(preview)
    store.put_hybrid_event_frame_preview(
        preview,
        payload,
        hybrid_event_frame_preview_sha256(preview),
    )
    stored = tmp_path / "extraction" / "event-frame-previews" / f"{preview.id}.json"
    stored.write_bytes(b"different bytes")

    with pytest.raises(ValueError, match="conflicts with its immutable identity"):
        store.put_hybrid_event_frame_preview(
            preview,
            payload,
            hybrid_event_frame_preview_sha256(preview),
        )
    with pytest.raises(ValueError):
        store.read_hybrid_event_frame_preview(preview.id)


def test_put_reuse_and_restart_hybrid_atomic_claim_preview(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    preview = build_hybrid_atomic_claim_preview(
        parent_preview_id="hep_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        grounding_preview_id="hgp_" + "2" * 24,
        grounding_preview_sha256="b" * 64,
        reference_preview_id="hrp_" + "3" * 24,
        reference_preview_sha256="c" * 64,
        mention_preview_id="hxp_" + "4" * 24,
        mention_preview_sha256="d" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        ontology_slice_id="hybrid_event_core_v1",
        ontology_slice_sha256="e" * 64,
        terminal_status=HybridAtomicClaimStatus.COMPLETE,
    )
    payload = canonical_hybrid_atomic_claim_preview_bytes(preview)
    digest = hybrid_atomic_claim_preview_sha256(preview)

    created = store.put_hybrid_atomic_claim_preview(preview, payload, digest)
    reused = store.put_hybrid_atomic_claim_preview(preview, payload, digest)
    reopened = LocalArchiveStore(tmp_path)

    assert created.disposition is ArchivePutDisposition.CREATED
    assert reused.disposition is ArchivePutDisposition.REUSED
    assert reopened.read_hybrid_atomic_claim_preview(preview.id) == payload

    stored = tmp_path / "extraction" / "atomic-claim-previews" / f"{preview.id}.json"
    stored.write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="conflicts with its immutable identity"):
        store.put_hybrid_atomic_claim_preview(preview, payload, digest)
    with pytest.raises(ValueError):
        reopened.read_hybrid_atomic_claim_preview(preview.id)


def test_put_and_reuse_pdf_transformation_blob(tmp_path: Path) -> None:
    store = LocalArchiveStore(tmp_path)
    store.initialize()
    content = b'{"page":2,"text":"OCR output"}'
    digest = hashlib.sha256(content).hexdigest()

    created = store.put_pdf_transformation_blob(f"blb_{digest}", content, digest)
    reused = store.put_pdf_transformation_blob(f"blb_{digest}", content, digest)

    assert created.object.relative_path == f"transformations/blb_{digest}.bin"
    assert reused.object == created.object
    assert store.read_pdf_transformation_blob(f"blb_{digest}") == content


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
