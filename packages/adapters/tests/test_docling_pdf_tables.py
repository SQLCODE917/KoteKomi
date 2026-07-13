import hashlib
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import (
    DoclingPdfParser,
    DoclingPdfParserConfig,
    LocalArchiveStore,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    BuildIdentity,
    CaptureRequest,
    ContextManifestInput,
    ContextModelProfile,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    PdfIngestInput,
    PdfParseInput,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    TableCellAnalysisPlanningInput,
    Uuid4ProcessingAttemptIdFactory,
    build_context_manifest,
    capture_identity,
    capture_source,
    ingest_pdf,
    load_context_manifest,
    plan_table_cell_analysis_unit,
    submit_grounded_candidate_batch,
    verify_evidence_target,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentRepresentationBundle,
    DocumentVersionKind,
    SourceType,
    TableAnnotationKind,
    TableEvidenceSelector,
    canonical_representation_digest,
)

FIXTURE = Path(__file__).parent / "fixtures" / "pdf" / "tables" / "complex_table_v1.pdf"
RAW_PDF = FIXTURE.read_bytes()
RAW_DIGEST = "0d05a75d046914ffc90eee9ac96dab3b7233fdde58777a96d8d7a06f94cc4c89"
NOW = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)


class FixtureTokenizer:
    tokenizer_id = "fixture_utf8_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


class StrippedHeaderLedger:
    def __init__(self, bundle: DocumentRepresentationBundle) -> None:
        self.bundle = bundle
        self.artifacts: dict[str, AnalysisUnitArtifact] = {}
        self.manifests: dict[str, ContextManifestArtifact] = {}

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.artifacts[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.artifacts.get(record_id)

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
        self.manifests[manifest.id] = manifest
        for unit in child_analysis_units:
            self.artifacts[unit.id] = unit


def _capture_request() -> CaptureRequest:
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="KoteKomi complex table fixture",
            stable_key="kotekomi-complex-table-v1",
            uri="file:///fixtures/complex_table_v1.pdf",
        ),
        payload=RAW_PDF,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{RAW_DIGEST}.bin",
        idempotency_key="kotekomi-complex-table-v1",
        retrieval_method="fixture",
        requested_uri="file:///fixtures/complex_table_v1.pdf",
        canonical_uri="file:///fixtures/complex_table_v1.pdf",
        provider_item_id=None,
        provider_version=None,
        version_kind=DocumentVersionKind.ORIGINAL,
        publication_time=None,
        provider_update_time=None,
        captured_at=NOW,
        transaction_time=NOW,
        rights_profile_id=None,
        embargo_until=None,
        request_metadata={},
        response_metadata={},
    )


def _node_text(bundle: DocumentRepresentationBundle, node_id: str) -> str:
    node = next(item for item in bundle.nodes if item.id == node_id)
    view = next(item for item in bundle.text_views if item.id == node.text_view_id)
    return view.text[node.start_char : node.end_char]


def _cell_node_id(bundle: DocumentRepresentationBundle, cell_id: str) -> str:
    cell = next(item for item in bundle.table_cells if item.id == cell_id)
    assert cell.node_id is not None
    return cell.node_id


def _stripped_header_bundle(
    bundle: DocumentRepresentationBundle,
    value_cell_id: str,
) -> DocumentRepresentationBundle:
    stripped_cells = tuple(
        cell.model_copy(update={"column_header_cell_ids": ()}) if cell.id == value_cell_id else cell
        for cell in bundle.table_cells
    )
    template = bundle.representation.model_copy(update={"canonical_output_digest": "0" * 64})
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=bundle.text_views,
                nodes=bundle.nodes,
                edges=bundle.edges,
                source_regions=bundle.source_regions,
                quality_report=bundle.quality_report,
                tables=bundle.tables,
                table_fragments=bundle.table_fragments,
                table_rows=bundle.table_rows,
                table_cells=stripped_cells,
                table_annotations=bundle.table_annotations,
                references=bundle.references,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        tables=bundle.tables,
        table_fragments=bundle.table_fragments,
        table_rows=bundle.table_rows,
        table_cells=stripped_cells,
        table_annotations=bundle.table_annotations,
        references=bundle.references,
        quality_report=bundle.quality_report,
    )


def test_table_value_reaches_context_and_evidence_only_with_header_ancestry_after_restart(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(RAW_PDF).hexdigest() == RAW_DIGEST
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    identity = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(identity.raw_blob_id, RAW_PDF, RAW_DIGEST)
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)
        ingest = ingest_pdf(
            PdfIngestInput(
                document_id=capture.document.id,
                raw_bytes=RAW_PDF,
                policy_id="canonical_pdf_table_v1",
                ingested_at=NOW,
                raw_blob_id=capture.raw_blob.id,
                build_identity=BuildIdentity("table-proof", "table-proof", "d" * 64, "1"),
            ),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert ingest.representation_id is not None
        bundle = repository.get_document_representation_bundle(ingest.representation_id)
        assert bundle is not None
        value_cell = next(
            cell
            for cell in bundle.table_cells
            if cell.node_id is not None and _node_text(bundle, cell.node_id) == "23(a)"
        )
        assert value_cell.row_span == value_cell.column_span == 1
        assert tuple(
            _node_text(bundle, _cell_node_id(bundle, cell_id))
            for cell_id in value_cell.row_header_cell_ids
        ) == ("Region B",)
        assert tuple(
            _node_text(bundle, _cell_node_id(bundle, cell_id))
            for cell_id in value_cell.column_header_cell_ids
        ) == ("Measurements", "2025", "Q2")
        assert {annotation.kind for annotation in bundle.table_annotations} == {
            TableAnnotationKind.CAPTION,
            TableAnnotationKind.UNIT,
            TableAnnotationKind.NOTE,
        }
        assert {reference.kind.value for reference in bundle.references} == {
            "cross_reference",
            "footnote",
        }

        planning = plan_table_cell_analysis_unit(
            TableCellAnalysisPlanningInput(
                representation_id=bundle.representation.id,
                table_cell_id=value_cell.id,
                policy_id="table_header_closure_v1",
                task_type="table_claim_extraction",
            ),
            repository,
        )
        assert planning.blocked_reason is None
        assert planning.analysis_unit is not None
        manifest = build_context_manifest(
            ContextManifestInput(
                analysis_unit=planning.analysis_unit,
                model_profile=ContextModelProfile("fixture-model", 2048, 32, 16),
                prompt_id="table_claim_prompt_v1",
                prompt_bytes=b"Extract one table claim with its complete headers.",
                schema_id="table_claim_schema_v1",
                schema_bytes=b'{"type":"object"}',
                renderer_version="table_context_renderer_v1",
            ),
            repository,
            FixtureTokenizer(),
        ).manifest
        assert manifest.status.value == "ready"
        selected_text = tuple(
            _node_text(bundle, candidate.node_id) for candidate in manifest.selected_candidates
        )
        assert selected_text == (
            "23(a)",
            "Region B",
            "Measurements",
            "2025",
            "Q2",
            "Table 1. Regional measurements",
            "Units: index points",
            "(a): adjusted value. Note: blank 2025 cells for Region A are intentionally empty.",
        )

        cells_by_id = {cell.id: cell for cell in bundle.table_cells}
        header_cells = tuple(
            cells_by_id[cell_id]
            for cell_id in (
                *value_cell.row_header_cell_ids,
                *value_cell.column_header_cell_ids,
            )
        )
        assert value_cell.node_id is not None
        header_node_ids = tuple(cell.node_id for cell in header_cells)
        assert all(node_id is not None for node_id in header_node_ids)
        evidence_node_ids = (
            value_cell.node_id,
            *(node_id for node_id in header_node_ids if node_id),
        )
        nodes_by_id = {node.id: node for node in bundle.nodes}
        evidence_region_ids = tuple(
            region_id
            for node_id in evidence_node_ids
            for region_id in nodes_by_id[node_id].source_region_ids
        )
        value_node = nodes_by_id[value_cell.node_id]
        logical_view = next(
            view for view in bundle.text_views if view.id == value_node.text_view_id
        )
        batch = submit_grounded_candidate_batch(
            GroundedCandidateBatchInput(
                task_fingerprint=manifest.manifest_digest,
                source_id=capture.source.id,
                document_id=capture.document.id,
                representation_id=bundle.representation.id,
                model_name="deterministic-table-fixture",
                prompt_id=manifest.prompt_id,
                validator_version="table-evidence-validator-v1",
                submitted_at=NOW,
                organizations=(GroundedOrganizationCandidate("org", "Fixture Organization"),),
                evidence=(
                    GroundedEvidenceCandidate(
                        local_id="value",
                        text_view_id=logical_view.id,
                        start_char=value_node.start_char,
                        end_char=value_node.end_char,
                        exact_text="23(a)",
                        node_ids=evidence_node_ids,
                        pdf_region_ids=evidence_region_ids,
                        table_selector=TableEvidenceSelector(
                            table_id=value_cell.table_id,
                            cell_id=value_cell.id,
                            row_header_cell_ids=value_cell.row_header_cell_ids,
                            column_header_cell_ids=value_cell.column_header_cell_ids,
                        ),
                    ),
                ),
                assertions=(
                    GroundedAssertionCandidate(
                        local_id="claim",
                        subject_organization_local_id="org",
                        evidence_local_id="value",
                        predicate="reported_table_value",
                        object_value="23 index points",
                    ),
                ),
            ),
            repository,
        )
        evidence_id = batch.evidence_target_ids_by_local_id["value"]
        attempt_id = batch.validation_attempt_ids_by_evidence_local_id["value"]
        stripped_bundle = _stripped_header_bundle(bundle, value_cell.id)

    with sqlite_ledger_transaction(ledger_path) as repository:
        replayed_bundle = repository.get_document_representation_bundle(ingest.representation_id)
        assert replayed_bundle == bundle
        assert load_context_manifest(manifest.id, repository) == manifest
        evidence = repository.get_evidence_target(evidence_id)
        attempt = repository.get_evidence_validation_attempt(attempt_id)
        assert evidence is not None and attempt is not None
        assert verify_evidence_target(evidence, attempt, repository).valid

    blocked = plan_table_cell_analysis_unit(
        TableCellAnalysisPlanningInput(
            representation_id=stripped_bundle.representation.id,
            table_cell_id=value_cell.id,
            policy_id="table_header_closure_v1",
            task_type="table_claim_extraction",
        ),
        StrippedHeaderLedger(stripped_bundle),
    )
    assert blocked.analysis_unit is None
    assert blocked.blocked_reason == "missing_column_header_ancestry"


def test_nist_table_continuation_is_one_logical_table_with_three_page_fragments() -> None:
    raw_pdf = (
        Path(__file__).parent / "fixtures" / "pdf" / "tables" / "nist-srm-2259-certificate.pdf"
    ).read_bytes()
    result = DoclingPdfParser(DoclingPdfParserConfig()).parse(
        PdfParseInput(
            document=Document(
                id="doc_nist_table_continuation",
                source_id="src_nist_table_continuation",
                content_sha256=hashlib.sha256(raw_pdf).hexdigest(),
            ),
            raw_bytes=raw_pdf,
            policy_id="cross_page_table_v1",
            processing_task_fingerprint_id="ptf_nist_table_continuation",
            parsed_at=NOW,
        )
    )

    assert result.representation_bundle is not None
    bundle = result.representation_bundle
    continuation = next(table for table in bundle.tables if len(table.fragment_ids) == 3)
    fragments_by_id = {fragment.id: fragment for fragment in bundle.table_fragments}
    fragments = tuple(fragments_by_id[fragment_id] for fragment_id in continuation.fragment_ids)
    assert tuple(fragment.page_numbers for fragment in fragments) == ((2,), (3,), (4,))
    assert tuple(fragment.fragment_index for fragment in fragments) == (0, 1, 2)
    assert fragments[0].continued_from_fragment_id is None
    assert fragments[1].continued_from_fragment_id == fragments[0].id
    assert fragments[2].continued_from_fragment_id == fragments[1].id
    assert fragments[1].repeated_header_cell_ids
    assert fragments[2].repeated_header_cell_ids
