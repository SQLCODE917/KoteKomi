import hashlib
from datetime import UTC, datetime

from kotekomi_application import (
    BuildDocumentRetrievalProjectionCommand,
    BuildDocumentSemanticProjectionCommand,
    ChannelCandidate,
    EmbeddingBatch,
    EmbeddingProfile,
    QueryDocumentRetrievalCommand,
    QueryDocumentSemanticRetrievalCommand,
    RetrievalFailureCode,
    build_document_retrieval_projection,
    build_document_semantic_projection,
    query_document_retrieval,
    query_document_semantic_retrieval,
)
from kotekomi_application.document_retrieval import (
    ProjectionBuildInput,
    SemanticProjectionBuildInput,
    embedding_profile_configuration_digest,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EmbeddingModelIdentity,
    ParseQualityReport,
    RepresentationAnalyzability,
    RetrievalChannel,
    RetrievalIndexManifest,
    RetrievalQueryRecord,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 8, 21, tzinfo=UTC)
TEXT = "Fixture title\nFixture section\nNeedle phrase"


class FakeLedger:
    def __init__(self) -> None:
        self.bundle = _bundle()
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.manifests: dict[str, ContextManifestArtifact] = {}

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.manifests.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.analysis_units.update({record.id: record for record in child_analysis_units})
        self.manifests[manifest.id] = manifest


class FakeProjection:
    def __init__(self) -> None:
        self.manifest: RetrievalIndexManifest | None = None
        self.build: ProjectionBuildInput | None = None
        self.query_records: list[RetrievalQueryRecord] = []

    def publish(self, build: ProjectionBuildInput) -> tuple[RetrievalIndexManifest, bool]:
        reused = self.manifest == build.manifest
        self.manifest = build.manifest
        self.build = build
        return build.manifest, reused

    def get_complete_manifest(self, representation_id: str) -> RetrievalIndexManifest | None:
        if self.manifest is not None and self.manifest.representation_id == representation_id:
            return self.manifest
        return None

    def exact_candidates(
        self, manifest: RetrievalIndexManifest, normalized_query: str
    ) -> tuple[ChannelCandidate, ...]:
        assert self.build is not None
        if normalized_query.casefold() != "needle":
            return ()
        return (
            ChannelCandidate(
                retrieval_unit_id=self.build.units[-1].retrieval_unit_id,
                channel=RetrievalChannel.EXACT,
                channel_rank=1,
                matched_field="body_nfc",
            ),
        )

    def lexical_candidates(
        self, manifest: RetrievalIndexManifest, query_text: str
    ) -> tuple[ChannelCandidate, ...]:
        return ()

    def save_query_record(self, record: RetrievalQueryRecord) -> None:
        self.query_records.append(record)


class Tokenizer:
    tokenizer_id = "fixture_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


class FakeSemanticProjection:
    def __init__(self) -> None:
        self.manifest: RetrievalIndexManifest | None = None
        self.build: SemanticProjectionBuildInput | None = None
        self.query_records: list[RetrievalQueryRecord] = []

    def publish_semantic(
        self, build: SemanticProjectionBuildInput
    ) -> tuple[RetrievalIndexManifest, bool]:
        reused = self.manifest == build.manifest
        self.manifest = build.manifest
        self.build = build
        return build.manifest, reused

    def get_complete_semantic_manifest(
        self, representation_id: str, profile_id: str
    ) -> RetrievalIndexManifest | None:
        if (
            self.manifest is not None
            and self.manifest.representation_id == representation_id
            and self.manifest.embedding_profile_id == profile_id
        ):
            return self.manifest
        return None

    def semantic_candidates(
        self, manifest: RetrievalIndexManifest, query_vector: bytes
    ) -> tuple[ChannelCandidate, ...]:
        del manifest, query_vector
        assert self.build is not None
        return (
            ChannelCandidate(
                retrieval_unit_id=self.build.units[-1].retrieval_unit_id,
                channel=RetrievalChannel.SEMANTIC,
                channel_rank=1,
                raw_score=1.0,
            ),
        )

    def delete_semantic_projection(self, representation_id: str, profile_id: str) -> None:
        del representation_id, profile_id
        self.manifest = None
        self.build = None

    def save_query_record(self, record: RetrievalQueryRecord) -> None:
        self.query_records.append(record)


class FakeEmbedding:
    def __init__(self, profile: EmbeddingProfile) -> None:
        self.profile = profile
        self.inputs: list[tuple[str, ...]] = []

    def embed(self, profile: EmbeddingProfile, inputs: tuple[str, ...]) -> EmbeddingBatch:
        assert profile == self.profile
        self.inputs.append(inputs)
        return EmbeddingBatch(
            model_identity=EmbeddingModelIdentity(
                adapter_id=profile.adapter_id,
                model_id=profile.model_id,
                model_digest=profile.model_digest,
                vector_dimension=profile.expected_vector_dimension,
                configuration_digest=embedding_profile_configuration_digest(profile),
            ),
            vectors=tuple((1.0, 0.0, 0.0) for _ in inputs),
        )


def _embedding_profile(*, maximum_rendered_characters: int = 1000) -> EmbeddingProfile:
    return EmbeddingProfile(
        profile_id="semantic-fixture-v1",
        adapter_id="fixture",
        endpoint="http://fixture.invalid/v1",
        model_id="fixture-embedding",
        model_path="/fixture/embedding.bin",
        model_digest="d" * 64,
        expected_vector_dimension=3,
        maximum_rendered_characters=maximum_rendered_characters,
    )


def _bundle() -> DocumentRepresentationBundle:
    representation_id = "rep_document_retrieval_fixture"
    text_view = TextView(
        id="tvw_document_retrieval_fixture",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        text=TEXT,
        normalization_policy="fixture-v1",
    )
    title_end = TEXT.index("\n")
    section_start = title_end + 1
    section_end = TEXT.index("\n", section_start)
    root = DocumentNode(
        id="nod_document_retrieval_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    title = DocumentNode(
        id="nod_document_retrieval_title",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        structural_path=("document", "heading:0001"),
        section_path=("Fixture title",),
        text_view_id=text_view.id,
        start_char=0,
        end_char=title_end,
    )
    section = DocumentNode(
        id="nod_document_retrieval_section",
        representation_id=representation_id,
        parent_node_id=title.id,
        node_type="heading",
        order_index=2,
        structural_path=("document", "heading:0001", "heading:0002"),
        section_path=("Fixture title", "Fixture section"),
        text_view_id=text_view.id,
        start_char=section_start,
        end_char=section_end,
    )
    needle = DocumentNode(
        id="nod_document_retrieval_needle",
        representation_id=representation_id,
        parent_node_id=section.id,
        node_type="paragraph",
        order_index=3,
        structural_path=("document", "heading:0001", "heading:0002", "paragraph:0003"),
        section_path=("Fixture title", "Fixture section"),
        text_view_id=text_view.id,
        start_char=section_end + 1,
        end_char=len(TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_document_retrieval_fixture",
        representation_id=representation_id,
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_document_retrieval_fixture",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_document_retrieval_fixture",
        input_blob_digest="b" * 64,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, title, section, needle),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, title, section, needle),
        quality_report=quality_report,
    )


def test_document_retrieval_uses_fake_port_hits_and_authoritative_context() -> None:
    ledger = FakeLedger()
    projection = FakeProjection()
    build = build_document_retrieval_projection(
        BuildDocumentRetrievalProjectionCommand(ledger.bundle.representation.id),
        ledger_repository=ledger,
        projection=projection,
    )

    result = query_document_retrieval(
        QueryDocumentRetrievalCommand(
            representation_id=ledger.bundle.representation.id,
            query_text="Needle",
            maximum_hits=1,
            context_profile_id="retrieval-validation-v1",
        ),
        ledger_repository=ledger,
        projection=projection,
        tokenizer=Tokenizer(),
    )

    assert build.status == "complete"
    assert result.status == "complete"
    assert result.hits[0].selection_reason == "exact_before_lexical"
    assert result.selected_node_ids == ("nod_document_retrieval_needle",)
    assert result.context_manifest_rendered_input is not None
    assert b"Fixture title" in result.context_manifest_rendered_input
    assert b"Fixture section" in result.context_manifest_rendered_input
    assert b"Needle phrase" in result.context_manifest_rendered_input
    assert len(projection.query_records) == 1


def test_document_retrieval_rejects_a_stale_manifest() -> None:
    ledger = FakeLedger()
    projection = FakeProjection()
    build_document_retrieval_projection(
        BuildDocumentRetrievalProjectionCommand(ledger.bundle.representation.id),
        ledger_repository=ledger,
        projection=projection,
    )
    assert projection.manifest is not None
    projection.manifest = projection.manifest.model_copy(update={"representation_digest": "c" * 64})

    result = query_document_retrieval(
        QueryDocumentRetrievalCommand(
            representation_id=ledger.bundle.representation.id,
            query_text="Needle",
            maximum_hits=1,
            context_profile_id="retrieval-validation-v1",
        ),
        ledger_repository=ledger,
        projection=projection,
        tokenizer=Tokenizer(),
    )

    assert result.status == "failed"
    assert result.failure is RetrievalFailureCode.INDEX_STALE


def test_semantic_retrieval_uses_fake_embedding_and_authoritative_context() -> None:
    ledger = FakeLedger()
    profile = _embedding_profile()
    projection = FakeSemanticProjection()
    embedding = FakeEmbedding(profile)

    build = build_document_semantic_projection(
        BuildDocumentSemanticProjectionCommand(ledger.bundle.representation.id, profile),
        ledger_repository=ledger,
        projection=projection,
        embedding=embedding,
    )
    result = query_document_semantic_retrieval(
        QueryDocumentSemanticRetrievalCommand(
            representation_id=ledger.bundle.representation.id,
            query_text="Where is the needle?",
            maximum_hits=1,
            context_profile_id="retrieval-validation-v1",
            embedding_profile=profile,
        ),
        ledger_repository=ledger,
        projection=projection,
        embedding=embedding,
        tokenizer=Tokenizer(),
    )

    assert build.status == "complete"
    assert build.embedding_profile_id == profile.profile_id
    assert build.embedding_model_identity is not None
    assert result.status == "complete"
    assert result.selected_node_ids == ("nod_document_retrieval_needle",)
    assert embedding.inputs[0][0].startswith("search_document: Source title: Fixture title\n")
    assert embedding.inputs[-1] == ("search_query: Where is the needle?",)
    assert result.context_manifest_rendered_input is not None
    assert b"Needle phrase" in result.context_manifest_rendered_input
    assert b"search_document:" not in result.context_manifest_rendered_input
    assert projection.query_records[0].embedding_profile_id == profile.profile_id
    assert result.embedding_model_identity == projection.query_records[0].embedding_model_identity


def test_semantic_retrieval_rejects_oversized_rendered_input() -> None:
    ledger = FakeLedger()
    profile = _embedding_profile(maximum_rendered_characters=10)
    embedding = FakeEmbedding(profile)

    result = build_document_semantic_projection(
        BuildDocumentSemanticProjectionCommand(ledger.bundle.representation.id, profile),
        ledger_repository=ledger,
        projection=FakeSemanticProjection(),
        embedding=embedding,
    )

    assert result.status == "failed"
    assert result.failure is RetrievalFailureCode.SEMANTIC_INPUT_TOO_LARGE
    assert embedding.inputs == []
