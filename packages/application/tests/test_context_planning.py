# pyright: reportPrivateUsage=false

import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    AnalysisUnit,
    AnalysisUnitPlanningInput,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    RetrievalSelectionAnalysisUnitInput,
    build_context_manifest,
    create_analysis_unit_from_retrieval_selection,
    plan_analysis_units,
    render_context,
    verify_context_manifest,
)
from kotekomi_application.context_planning import _definition_nodes_for_focus
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
TEXT = (
    "Community Health\n"
    "Improvement Plan\n"
    "Community Health Improvement Plan (CHIP) defines the county strategy.\n"
    "The CHIP identifies health priorities.\n"
    "Furniture header"
)
LOGICAL_TEXT = TEXT.removesuffix("\nFurniture header")


class ExactWhitespaceTokenizer:
    tokenizer_id = "fixture_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


class FakeContextPlanningLedger:
    def __init__(self) -> None:
        self.bundle = _bundle()
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.manifests.get(record_id)

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.analysis_units.update({record.id: record for record in child_analysis_units})
        self.manifests[manifest.id] = manifest


def _bundle() -> DocumentRepresentationBundle:
    representation_id = "rep_context_fixture"
    text_view = TextView(
        id="tvw_context_fixture",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(LOGICAL_TEXT.encode()).hexdigest(),
        text=LOGICAL_TEXT,
        normalization_policy="fixture_v1",
    )
    display_view = TextView(
        id="tvw_context_fixture_display",
        representation_id=representation_id,
        kind=TextViewKind.DISPLAY,
        content_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        text=TEXT,
        normalization_policy="fixture_display_v1",
    )
    outer_heading_end = TEXT.index("\n")
    heading_start = outer_heading_end + 1
    heading_end = TEXT.index("\n", heading_start)
    definition_start = heading_end + 1
    definition_end = definition_start + len(
        "Community Health Improvement Plan (CHIP) defines the county strategy."
    )
    focus_start = definition_end + 1
    focus_end = focus_start + len("The CHIP identifies health priorities.")
    furniture_start = focus_end + 1
    root = DocumentNode(
        id="nod_context_document",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(LOGICAL_TEXT),
    )
    outer_heading = DocumentNode(
        id="nod_context_outer_heading",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=outer_heading_end,
    )
    heading = DocumentNode(
        id="nod_context_heading",
        representation_id=representation_id,
        parent_node_id=outer_heading.id,
        node_type="heading",
        order_index=2,
        text_view_id=text_view.id,
        start_char=heading_start,
        end_char=heading_end,
    )
    definition = DocumentNode(
        id="nod_context_definition",
        representation_id=representation_id,
        parent_node_id=heading.id,
        node_type="paragraph",
        order_index=3,
        text_view_id=text_view.id,
        start_char=definition_start,
        end_char=definition_end,
    )
    focus = DocumentNode(
        id="nod_context_focus",
        representation_id=representation_id,
        parent_node_id=heading.id,
        node_type="paragraph",
        order_index=4,
        text_view_id=text_view.id,
        start_char=focus_start,
        end_char=focus_end,
    )
    furniture = DocumentNode(
        id="nod_context_furniture",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="furniture",
        order_index=5,
        text_view_id=display_view.id,
        start_char=furniture_start,
        end_char=len(TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_context_fixture",
        representation_id=representation_id,
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_context_fixture",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_context_fixture",
        input_blob_digest="b" * 64,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view, display_view),
                nodes=(root, outer_heading, heading, definition, focus, furniture),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view, display_view),
        nodes=(root, outer_heading, heading, definition, focus, furniture),
        quality_report=quality_report,
    )


def _manifest_input(unit: AnalysisUnit, *, limit: int) -> ContextManifestInput:
    return ContextManifestInput(
        analysis_unit=unit,
        model_profile=ContextModelProfile("fixture-model", limit, 4, 2),
        prompt_id="fixture-prompt",
        prompt_bytes=b"Extract a source-backed claim.",
        schema_id="fixture-schema",
        schema_bytes=b'{"type":"object"}',
        renderer_version="fixture-renderer-v1",
    )


def _nonheading_parent_bundle() -> DocumentRepresentationBundle:
    bundle = _bundle()
    logical = next(view for view in bundle.text_views if view.kind is TextViewKind.LOGICAL)
    text = logical.text.replace(
        "The CHIP identifies health priorities.", "The plan identifies health priorities."
    )
    assert len(text) == len(logical.text)
    updated_logical = logical.model_copy(
        update={"text": text, "content_digest": hashlib.sha256(text.encode()).hexdigest()}
    )
    nodes = tuple(
        node.model_copy(update={"parent_node_id": "nod_context_definition"})
        if node.id == "nod_context_focus"
        else node
        for node in bundle.nodes
    )
    template = bundle.representation.model_copy(update={"canonical_output_digest": "0" * 64})
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(
                    updated_logical,
                    *tuple(view for view in bundle.text_views if view.id != logical.id),
                ),
                nodes=nodes,
                edges=bundle.edges,
                source_regions=bundle.source_regions,
                quality_report=bundle.quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(
            updated_logical,
            *tuple(view for view in bundle.text_views if view.id != logical.id),
        ),
        nodes=nodes,
        quality_report=bundle.quality_report,
    )


def test_context_planner_includes_required_definition_and_excludes_furniture() -> None:
    ledger = FakeContextPlanningLedger()
    plan = plan_analysis_units(
        AnalysisUnitPlanningInput(ledger.bundle.representation.id, "fixture-policy", "extract"),
        ledger,
    )
    focus_unit = next(unit for unit in plan.units if unit.focus_node_ids == ("nod_context_focus",))
    tokenizer = ExactWhitespaceTokenizer()

    first = build_context_manifest(_manifest_input(focus_unit, limit=256), ledger, tokenizer)
    second = build_context_manifest(_manifest_input(focus_unit, limit=256), ledger, tokenizer)

    assert first == second
    assert first.manifest.status is ContextManifestStatus.READY
    assert tuple(candidate.node_id for candidate in first.manifest.selected_candidates) == (
        "nod_context_focus",
        "nod_context_outer_heading",
        "nod_context_heading",
        "nod_context_definition",
    )
    assert first.manifest.excluded_candidates[0].candidate.node_id == "nod_context_furniture"
    assert first.manifest.excluded_candidates[0].reason_code == "furniture_excluded"
    assert b"Community Health Improvement Plan (CHIP)" in first.manifest.rendered_input
    assert b"Community Health" in first.manifest.rendered_input
    assert b"Improvement Plan" in first.manifest.rendered_input
    assert b"Furniture header" not in first.manifest.rendered_input
    assert first.manifest.input_token_count <= 250
    assert (
        render_context(
            first.manifest.id,
            ledger,
            tokenizer,
            b"Extract a source-backed claim.",
            b'{"type":"object"}',
        )
        == first.manifest.rendered_input
    )


def test_retrieval_context_includes_heading_ancestors_without_parent_body() -> None:
    ledger = FakeContextPlanningLedger()
    ledger.bundle = _nonheading_parent_bundle()
    unit = create_analysis_unit_from_retrieval_selection(
        RetrievalSelectionAnalysisUnitInput(
            representation_id=ledger.bundle.representation.id,
            focus_node_ids=("nod_context_focus",),
            policy_id="retrieval_selection_v1",
        ),
        ledger,
    )

    outcome = build_context_manifest(
        _manifest_input(unit, limit=256), ledger, ExactWhitespaceTokenizer()
    )

    assert outcome.manifest.status is ContextManifestStatus.READY
    assert tuple(candidate.node_id for candidate in outcome.manifest.selected_candidates) == (
        "nod_context_focus",
        "nod_context_outer_heading",
        "nod_context_heading",
    )
    assert b"Community Health" in outcome.manifest.rendered_input
    assert b"Improvement Plan" in outcome.manifest.rendered_input
    assert b"Community Health Improvement Plan (CHIP)" not in outcome.manifest.rendered_input


def test_context_planner_splits_multiple_focus_nodes_and_blocks_one_oversized_unit() -> None:
    ledger = FakeContextPlanningLedger()
    tokenizer = ExactWhitespaceTokenizer()
    split_unit = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "fixture-paragraph-group-v1",
            "extract",
            max_focus_nodes_per_unit=2,
        ),
        ledger,
    ).units[0]
    split = build_context_manifest(_manifest_input(split_unit, limit=8), ledger, tokenizer)
    blocked_unit = next(
        unit
        for unit in plan_analysis_units(
            AnalysisUnitPlanningInput(ledger.bundle.representation.id, "fixture-policy", "extract"),
            ledger,
        ).units
        if unit.focus_node_ids == ("nod_context_focus",)
    )
    blocked = build_context_manifest(_manifest_input(blocked_unit, limit=8), ledger, tokenizer)

    assert split.manifest.status is ContextManifestStatus.SPLIT
    assert tuple(unit.focus_node_ids for unit in split.split_units) == (
        ("nod_context_definition",),
        ("nod_context_focus",),
    )
    assert blocked.manifest.status is ContextManifestStatus.CONTEXT_BUDGET_BLOCKED
    assert blocked.blocked_reason == "required_context_exceeds_budget"
    assert tuple(
        excluded.candidate.node_id for excluded in blocked.manifest.excluded_candidates
    ) == (
        "nod_context_focus",
        "nod_context_outer_heading",
        "nod_context_heading",
        "nod_context_definition",
        "nod_context_furniture",
    )
    assert all(
        excluded.reason_code == "required_context_exceeds_budget"
        for excluded in blocked.manifest.excluded_candidates
    )


def test_definition_resolution_excludes_structural_document_root() -> None:
    bundle = _bundle()
    nodes = tuple(
        node.model_copy(update={"node_type": "furniture"})
        if node.id == "nod_context_definition"
        else node
        for node in bundle.nodes
    )
    focus = next(node for node in nodes if node.id == "nod_context_focus")

    assert _definition_nodes_for_focus(focus, bundle.model_copy(update={"nodes": nodes})) == ()


def test_context_manifest_rejects_tampered_candidates_segments_and_token_count() -> None:
    ledger = FakeContextPlanningLedger()
    tokenizer = ExactWhitespaceTokenizer()
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(ledger.bundle.representation.id, "fixture-policy", "extract"),
        ledger,
    ).units[0]
    manifest = build_context_manifest(_manifest_input(unit, limit=256), ledger, tokenizer).manifest
    artifact = ledger.manifests[manifest.id]
    payload = deepcopy(artifact.payload)
    integrity = payload["integrity"]
    assert isinstance(integrity, dict)
    selected = integrity["selected"]
    assert isinstance(selected, list)
    assert isinstance(selected[0], dict)
    selected[0] = {**selected[0], "node_id": "nod_context_furniture"}
    ledger.manifests[manifest.id] = artifact.model_copy(update={"payload": payload})

    with pytest.raises(ValueError, match="digest|persisted artifact"):
        verify_context_manifest(
            manifest.id,
            ledger,
            tokenizer,
            b"Extract a source-backed claim.",
            b'{"type":"object"}',
        )

    ledger.manifests[manifest.id] = artifact
    payload = deepcopy(artifact.payload)
    integrity = payload["integrity"]
    assert isinstance(integrity, dict)
    integrity["input_token_count"] = manifest.input_token_count + 1
    ledger.manifests[manifest.id] = artifact.model_copy(update={"payload": payload})
    with pytest.raises(ValueError, match="digest|token count"):
        verify_context_manifest(
            manifest.id,
            ledger,
            tokenizer,
            b"Extract a source-backed claim.",
            b'{"type":"object"}',
        )

    ledger.manifests[manifest.id] = artifact
    payload = deepcopy(artifact.payload)
    integrity = payload["integrity"]
    assert isinstance(integrity, dict)
    segments = integrity["segments"]
    assert isinstance(segments, list)
    assert isinstance(segments[0], dict)
    segments[0] = {**segments[0], "start_byte": 0}
    ledger.manifests[manifest.id] = artifact.model_copy(update={"payload": payload})
    with pytest.raises(ValueError, match="digest|segment"):
        verify_context_manifest(
            manifest.id,
            ledger,
            tokenizer,
            b"Extract a source-backed claim.",
            b'{"type":"object"}',
        )


def test_context_planning_rejects_caller_invented_analysis_unit_identity() -> None:
    ledger = FakeContextPlanningLedger()
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(ledger.bundle.representation.id, "fixture-policy", "extract"),
        ledger,
    ).units[0]
    invented = replace(unit, id="anu_invented")

    with pytest.raises(ValueError, match="AnalysisUnit ID"):
        build_context_manifest(
            _manifest_input(invented, limit=256), ledger, ExactWhitespaceTokenizer()
        )
