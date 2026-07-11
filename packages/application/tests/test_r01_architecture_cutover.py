from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]


def test_r01_removed_superseded_authority_bypasses_do_not_reappear() -> None:
    source_files = tuple(
        path
        for package in ("application", "adapters", "pipelines")
        for path in (SOURCE_ROOT / package / "src").rglob("*.py")
    )
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)

    for forbidden in (
        "propose_assertions_for_document",
        "def propose_assertions(",
        "ModelProposal",
        "document_text=document_text",
        '"propose-assertions"',
        "cleanup_created_source_archive_objects",
        "def link_assertion_evidence(",
        'processing_task_fingerprint_id="ptf_fixture"',
        'code_revision: str = "unknown"',
        "DEFAULT_PROMPT_PATH",
        "propose_assertions.md",
        "model_prompt_path",
    ):
        assert forbidden not in source_text


def test_authoritative_capture_uses_targeted_repository_queries() -> None:
    capture_modules = (
        SOURCE_ROOT / "application" / "src" / "kotekomi_application" / "source_capture.py",
        SOURCE_ROOT / "application" / "src" / "kotekomi_application" / "source_file_ingest.py",
    )
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in capture_modules)

    for forbidden in (".list_documents()", ".list_document_revision_relations()"):
        assert forbidden not in source_text
