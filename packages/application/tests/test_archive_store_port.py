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

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        content = self.staged.pop(staged_object.staged_relative_path)
        if staged_object.final_object.relative_path.startswith("sources/raw/"):
            source_id = staged_object.final_object.relative_path.removeprefix(
                "sources/raw/"
            ).removesuffix(".bin")
            self.raw_sources[source_id] = content
        else:
            document_id = staged_object.final_object.relative_path.removeprefix(
                "documents/extracted/"
            ).removesuffix(".txt")
            self.document_texts[document_id] = content.decode("utf-8")
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
