from kotekomi_application import (
    ArchiveObject,
    ArchivePutDisposition,
    ArchivePutOutcome,
    ArchiveStore,
    StagedArchiveObject,
)


class FakeArchiveStore:
    def __init__(self) -> None:
        self.raw_sources: dict[str, bytes] = {}
        self.staged: dict[str, bytes] = {}

    def initialize(self) -> None:
        return None

    def put_if_absent_or_identical(
        self, object_id: str, payload: bytes, expected_digest: str
    ) -> ArchivePutOutcome:
        existing = self.raw_sources.get(object_id)
        if existing is not None and existing != payload:
            raise ValueError("archive object conflict")
        self.raw_sources[object_id] = payload
        return ArchivePutOutcome(
            ArchivePutDisposition.REUSED if existing is not None else ArchivePutDisposition.CREATED,
            ArchiveObject(f"sources/raw/{object_id}.bin", len(payload)),
        )

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        self.raw_sources[source_id] = content
        return ArchiveObject(
            relative_path=f"sources/raw/{source_id}.bin",
            size_bytes=len(content),
        )

    def read_raw_source(self, source_id: str) -> bytes:
        return self.raw_sources[source_id]

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
        else:
            self.staged[staged_object.final_object.relative_path] = content
        return staged_object.final_object

    def discard_staged_object(self, staged_object: StagedArchiveObject) -> None:
        self.staged.pop(staged_object.staged_relative_path, None)


def test_fake_archive_store_satisfies_port_shape() -> None:
    store: ArchiveStore = FakeArchiveStore()

    store.initialize()
    raw = store.write_raw_source("src_article_a", b"raw bytes")

    assert raw == ArchiveObject("sources/raw/src_article_a.bin", 9)
    assert store.read_raw_source("src_article_a") == b"raw bytes"

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
