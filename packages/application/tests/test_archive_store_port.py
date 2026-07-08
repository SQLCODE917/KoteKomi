from kotekomi_application import ArchiveObject, ArchiveStore


class FakeArchiveStore:
    def __init__(self) -> None:
        self.raw_sources: dict[str, bytes] = {}
        self.document_texts: dict[str, str] = {}

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


def test_fake_archive_store_satisfies_port_shape() -> None:
    store: ArchiveStore = FakeArchiveStore()

    store.initialize()
    raw = store.write_raw_source("src_article_a", b"raw bytes")
    text = store.write_document_text("doc_article_a", "extracted text")

    assert raw == ArchiveObject("sources/raw/src_article_a.bin", 9)
    assert text == ArchiveObject("documents/extracted/doc_article_a.txt", 14)
    assert store.read_raw_source("src_article_a") == b"raw bytes"
    assert store.read_document_text("doc_article_a") == "extracted text"
