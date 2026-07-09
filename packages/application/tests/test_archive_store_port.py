from kotekomi_application import ArchiveObject, ArchiveStore, StagedArchiveObject


class FakeArchiveStore:
    def __init__(self) -> None:
        self.raw_sources: dict[str, bytes] = {}
        self.document_texts: dict[str, str] = {}
        self.staged: dict[str, bytes] = {}

    def initialize(self) -> None:
        return None

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        self.raw_sources[source_id] = content
        return ArchiveObject(
            relative_path=f"sources/raw/{source_id}.bin",
            size_bytes=len(content),
        )

    def read_raw_source(self, source_id: str) -> bytes:
        return self.raw_sources[source_id]

    def write_document_text(self, document_id: str, text: str) -> ArchiveObject:
        self.document_texts[document_id] = text
        return ArchiveObject(
            relative_path=f"documents/extracted/{document_id}.txt",
            size_bytes=len(text.encode("utf-8")),
        )

    def read_document_text(self, document_id: str) -> str:
        return self.document_texts[document_id]

    def read_briefing_markdown(self, briefing_id: str) -> str:
        return self.staged[f"briefings/daily/{briefing_id}.md"].decode("utf-8")

    def read_briefing_citations_json(self, briefing_id: str) -> str:
        return self.staged[f"briefings/daily/{briefing_id}.citations.json"].decode("utf-8")

    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject:
        staged_path = f".staging/sources/raw/{source_id}.bin.tmp"
        self.staged[staged_path] = content
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(f"sources/raw/{source_id}.bin", len(content)),
        )

    def stage_document_text(self, document_id: str, text: str) -> StagedArchiveObject:
        content = text.encode("utf-8")
        staged_path = f".staging/documents/extracted/{document_id}.txt.tmp"
        self.staged[staged_path] = content
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(f"documents/extracted/{document_id}.txt", len(content)),
        )

    def stage_briefing_markdown(self, briefing_id: str, markdown: str) -> StagedArchiveObject:
        content = markdown.encode("utf-8")
        staged_path = f".staging/briefings/daily/{briefing_id}.md.tmp"
        self.staged[staged_path] = content
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(f"briefings/daily/{briefing_id}.md", len(content)),
        )

    def stage_briefing_citations_json(
        self,
        briefing_id: str,
        citations_json: str,
    ) -> StagedArchiveObject:
        content = citations_json.encode("utf-8")
        staged_path = f".staging/briefings/daily/{briefing_id}.citations.json.tmp"
        self.staged[staged_path] = content
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(
                f"briefings/daily/{briefing_id}.citations.json",
                len(content),
            ),
        )

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        content = self.staged.pop(staged_object.staged_relative_path)
        if staged_object.final_object.relative_path.startswith("sources/raw/"):
            source_id = staged_object.final_object.relative_path.removeprefix(
                "sources/raw/"
            ).removesuffix(".bin")
            self.raw_sources[source_id] = content
        elif staged_object.final_object.relative_path.startswith("documents/extracted/"):
            document_id = staged_object.final_object.relative_path.removeprefix(
                "documents/extracted/"
            ).removesuffix(".txt")
            self.document_texts[document_id] = content.decode("utf-8")
        else:
            self.staged[staged_object.final_object.relative_path] = content
        return staged_object.final_object

    def delete_object(self, relative_path: str) -> None:
        self.staged.pop(relative_path, None)


def test_fake_archive_store_satisfies_port_shape() -> None:
    store: ArchiveStore = FakeArchiveStore()

    store.initialize()
    raw = store.write_raw_source("src_article_a", b"raw bytes")
    text = store.write_document_text("doc_article_a", "extracted text")

    assert raw == ArchiveObject("sources/raw/src_article_a.bin", 9)
    assert text == ArchiveObject("documents/extracted/doc_article_a.txt", 14)
    assert store.read_raw_source("src_article_a") == b"raw bytes"
    assert store.read_document_text("doc_article_a") == "extracted text"

    staged = store.stage_raw_source("src_article_b", b"staged")
    assert store.promote_staged_object(staged) == ArchiveObject("sources/raw/src_article_b.bin", 6)
    assert store.read_raw_source("src_article_b") == b"staged"

    staged_briefing = store.stage_briefing_markdown("brf_daily", "# Daily\n")
    assert store.promote_staged_object(staged_briefing) == ArchiveObject(
        "briefings/daily/brf_daily.md", 8
    )
    assert store.read_briefing_markdown("brf_daily") == "# Daily\n"
    citations_json = '{"briefing_id":"brf_daily","citations":[]}\n'
    staged_citations = store.stage_briefing_citations_json("brf_daily", citations_json)
    assert store.promote_staged_object(staged_citations) == ArchiveObject(
        "briefings/daily/brf_daily.citations.json",
        len(citations_json.encode("utf-8")),
    )
    assert store.read_briefing_citations_json("brf_daily") == citations_json
