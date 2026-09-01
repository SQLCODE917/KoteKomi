from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V2,
    ContextualKind,
    DiscourseRole,
    ExtractionStageTrace,
    HybridExtractionPreview,
    HybridPreviewStatus,
    MentionInterpretation,
    MentionProposal,
    ReferenceKind,
    ReferenceReason,
    ReferenceStatus,
    Referentiality,
    build_extraction_stage_trace,
    build_hybrid_extraction_preview,
    build_hybrid_reference_preview,
    canonical_hybrid_reference_preview_bytes,
    find_alias_declarations,
    hybrid_extraction_preview_sha256,
    hybrid_reference_preview_from_bytes,
    hybrid_source_segment_id,
    paragraph_source_segments,
    reconcile_mention_boundaries,
)
from kotekomi_application.extraction_stage_trace import ExtractionStageStatus
from kotekomi_application.hybrid_mention_interpretation import (
    MentionInterpretationDraft,
    fuse_mention_observations,
    observation_from_proposal,
    resolve_mention_interpretation,
)
from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from pydantic import BaseModel, ConfigDict

NOW = datetime(2026, 9, 1, tzinfo=UTC)
GOLD_PATH = Path(__file__).resolve().parents[3] / "docs" / "hp2-document-reference-gold-v1.json"


class ReferenceGoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str
    paragraphs: tuple[str, ...]
    focus_paragraph_index: int
    candidate_text: str
    expected_status: ReferenceStatus | None
    expected_reason: ReferenceReason | None
    expected_expanded_literals: tuple[str, ...]


class ReferenceGoldCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str
    policy_id: str
    review_basis: str
    cases: tuple[ReferenceGoldCase, ...]


def test_find_alias_declarations_preserves_exact_document_ranges() -> None:
    bundle = _bundle(
        (
            "National Institute of Standards and Technology (NIST) issued guidance.",
            "The U.S. AISI Consortium (AISIC) accepted members.",
            "National Institute of Standards and Technology (NISX) is malformed.",
            "NIST later revised its guidance.",
        )
    )

    declarations, traces = find_alias_declarations(bundle)

    assert [(item.expanded_span.text, item.alias_span.text) for item in declarations] == [
        ("National Institute of Standards and Technology", "NIST"),
        ("U.S. AISI Consortium", "AISIC"),
    ]
    logical_text = bundle.text_views[0].text
    assert all(
        logical_text[item.expanded_span.start_char : item.expanded_span.end_char]
        == item.expanded_span.text
        and logical_text[item.alias_span.start_char : item.alias_span.end_char]
        == item.alias_span.text
        for item in declarations
    )
    assert {item.trace_id for item in declarations} == {item.id for item in traces}


def test_unique_document_alias_resolves_and_anaphor_remains_unresolved() -> None:
    bundle = _bundle(
        (
            "National Institute of Standards and Technology (NIST) issued guidance.",
            "NIST revised it.",
        )
    )
    parent = _parent_preview(bundle, paragraph_index=1, candidate_texts=("NIST", "it"))

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )

    assert [
        (item.reference_span.text, item.status, item.reason) for item in preview.reference_decisions
    ] == [
        ("NIST", ReferenceStatus.RESOLVED, ReferenceReason.UNIQUE_EXPLICIT_ALIAS),
        ("it", ReferenceStatus.UNRESOLVED, ReferenceReason.SEMANTIC_RESOLUTION_DEFERRED),
    ]
    resolved, unresolved = preview.reference_decisions
    assert resolved.reference_kind is ReferenceKind.EXPLICIT_ALIAS
    assert len(resolved.declaration_ids) == len(resolved.antecedent_span_ids) == 1
    assert unresolved.reference_kind is ReferenceKind.ANAPHORIC
    assert unresolved.declaration_ids == unresolved.antecedent_span_ids == ()
    assert preview.parent_preview_id == parent.id


def test_repeated_equal_declarations_remain_one_unique_alias() -> None:
    bundle = _bundle(
        (
            "National Institute of Standards and Technology (NIST) issued guidance.",
            "National Institute of Standards and Technology (NIST) revised it.",
            "NIST published the result.",
        )
    )
    parent = _parent_preview(bundle, paragraph_index=2, candidate_texts=("NIST",))

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )

    decision = preview.reference_decisions[0]
    assert decision.status is ReferenceStatus.RESOLVED
    assert len(decision.declaration_ids) == len(decision.antecedent_span_ids) == 2


def test_conflicting_alias_declarations_remain_ambiguous_regardless_of_order() -> None:
    forward = _bundle(("Agency One (AO) acted.", "Agency Other (AO) replied.", "AO changed."))
    reversed_bundle = _bundle(
        ("Agency Other (AO) replied.", "Agency One (AO) acted.", "AO changed."),
        representation_id="rep_reference_reversed",
    )

    outcomes: list[tuple[ReferenceStatus, ReferenceReason, int]] = []
    for bundle in (forward, reversed_bundle):
        parent = _parent_preview(bundle, paragraph_index=2, candidate_texts=("AO",))
        decision = build_hybrid_reference_preview(
            parent_preview=parent,
            parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
            bundle=bundle,
        ).reference_decisions[0]
        outcomes.append((decision.status, decision.reason, len(decision.declaration_ids)))

    assert outcomes == [
        (ReferenceStatus.AMBIGUOUS, ReferenceReason.CONFLICTING_EXPLICIT_ALIAS, 2),
        (ReferenceStatus.AMBIGUOUS, ReferenceReason.CONFLICTING_EXPLICIT_ALIAS, 2),
    ]


def test_unmatched_alias_is_unresolved_and_pluralized_alias_is_not_eligible() -> None:
    bundle = _bundle(("AISIs coordinate research while NIST publishes guidance.",))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("AISIs", "NIST"))

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )

    assert [(item.reference_span.text, item.reason) for item in preview.reference_decisions] == [
        ("NIST", ReferenceReason.EXPLICIT_ALIAS_MISSING)
    ]


def test_ordinary_full_name_candidate_receives_no_reference_decision() -> None:
    bundle = _bundle(("Anthropic published guidance.",))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Anthropic",))

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )

    assert preview.reference_decisions == ()


def test_deterministic_replay_is_byte_identical_and_tampering_fails() -> None:
    bundle = _bundle(
        ("National Institute of Standards and Technology (NIST) acted.", "NIST replied.")
    )
    parent = _parent_preview(bundle, paragraph_index=1, candidate_texts=("NIST",))
    first = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )
    second = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )
    payload = canonical_hybrid_reference_preview_bytes(first)

    assert first == second
    assert canonical_hybrid_reference_preview_bytes(second) == payload
    assert hybrid_reference_preview_from_bytes(payload) == first
    tampered = payload.replace(b'"status":"resolved"', b'"status":"unresolved"')
    with pytest.raises(ValueError):
        hybrid_reference_preview_from_bytes(tampered)


def test_blocked_parent_and_representation_drift_fail_before_preview() -> None:
    bundle = _bundle(("NIST acted.",))
    blocked = build_hybrid_extraction_preview(
        representation_id=bundle.representation.id,
        paragraph_node_id=_paragraphs(bundle)[0].id,
        context_manifest_id="ctx_blocked",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.BLOCKED,
        diagnostics=("proposer_blocked",),
    )

    with pytest.raises(ValueError, match="blocked"):
        build_hybrid_reference_preview(
            parent_preview=blocked,
            parent_preview_sha256=hybrid_extraction_preview_sha256(blocked),
            bundle=bundle,
        )

    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("NIST",))
    other = _bundle(("NIST acted.",), representation_id="rep_other")
    with pytest.raises(ValueError, match="representation"):
        build_hybrid_reference_preview(
            parent_preview=parent,
            parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
            bundle=other,
        )


def test_hp2_deterministic_gold_catalog() -> None:
    catalog = ReferenceGoldCatalog.model_validate_json(GOLD_PATH.read_bytes())

    for case in catalog.cases:
        bundle = _bundle(case.paragraphs, representation_id=f"rep_{case.id.casefold()}")
        parent = _parent_preview(
            bundle,
            paragraph_index=case.focus_paragraph_index,
            candidate_texts=(case.candidate_text,),
        )
        preview = build_hybrid_reference_preview(
            parent_preview=parent,
            parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
            bundle=bundle,
        )
        if case.expected_status is None:
            assert preview.reference_decisions == (), case.id
            continue
        assert len(preview.reference_decisions) == 1, case.id
        decision = preview.reference_decisions[0]
        declaration_by_id = {item.id: item for item in preview.alias_declarations}
        assert decision.status is case.expected_status, case.id
        assert decision.reason is case.expected_reason, case.id
        assert tuple(
            sorted(
                {declaration_by_id[item].expanded_span.text for item in decision.declaration_ids}
            )
        ) == tuple(sorted(case.expected_expanded_literals)), case.id


def _parent_preview(
    bundle: DocumentRepresentationBundle,
    *,
    paragraph_index: int,
    candidate_texts: tuple[str, ...],
) -> HybridExtractionPreview:
    node = _paragraphs(bundle)[paragraph_index]
    view = bundle.text_views[0]
    paragraph = view.text[node.start_char : node.end_char]
    segments = paragraph_source_segments(paragraph, PARAGRAPH_SEGMENT_V2)
    segment = next(
        item for item in segments if all(text in item.exact_text for text in candidate_texts)
    )
    segment_id = hybrid_source_segment_id(bundle.representation.id, node.id, segment)
    observations = tuple(
        observation_from_proposal(
            proposal=MentionProposal(
                segment.label,
                text,
                segment.exact_text.index(text),
                segment.exact_text.index(text) + len(text),
                ("organization",),
            ),
            source_segment_id=segment_id,
            producer_id=f"fixture_{index}",
            execution_record_id=f"mrn_proposal_{index}",
        )
        for index, text in enumerate(candidate_texts, start=1)
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: segment.exact_text}, observations=observations
    )
    boundary_decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: segment.exact_text},
        observations=observations,
        candidates=candidates,
    )
    traces: list[ExtractionStageTrace] = []
    model_run_ids: list[str] = []
    for ordinal, observation in enumerate(observations):
        model_run_ids.append(observation.execution_record_id)
        traces.append(
            build_extraction_stage_trace(
                trace_run_id="hpr_fixture_reference",
                ordinal=ordinal,
                stage_id="mention_proposal",
                stage_version="fixture_v1",
                producer_id=observation.producer_id,
                source_segment_id=segment_id,
                source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
                execution_record_ids=(observation.execution_record_id,),
                configuration={},
                input_payload={"text": segment.exact_text},
                output_payload={"observation_id": observation.id},
                status=ExtractionStageStatus.COMPLETED,
            )
        )
    traces.append(
        build_extraction_stage_trace(
            trace_run_id="hpr_fixture_reference",
            ordinal=len(traces),
            stage_id="mention_boundary_reconciliation",
            stage_version="fixture_v1",
            producer_id="fixture",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            configuration={},
            input_payload={"candidate_ids": [item.id for item in candidates]},
            output_payload={"decision_ids": [item.id for item in boundary_decisions]},
            status=ExtractionStageStatus.COMPLETED,
        )
    )
    interpretations: list[MentionInterpretation] = []
    for candidate in selected:
        model_run_id = f"mrn_interpret_{candidate.id}"
        model_run_ids.append(model_run_id)
        trace = build_extraction_stage_trace(
            trace_run_id="hpr_fixture_reference",
            ordinal=len(traces),
            stage_id="mention_interpretation",
            stage_version="fixture_v1",
            producer_id="fixture",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            execution_record_ids=(model_run_id,),
            configuration={},
            input_payload={"candidate_id": candidate.id},
            output_payload={},
            status=ExtractionStageStatus.COMPLETED,
        )
        traces.append(trace)
        interpretations.append(
            resolve_mention_interpretation(
                draft=MentionInterpretationDraft(
                    candidate_label="c1",
                    referentiality=(
                        Referentiality.ANAPHORIC
                        if candidate.text.casefold() in {"it", "the institute"}
                        else Referentiality.SPECIFIC_ENTITY
                    ),
                    contextual_kind=ContextualKind.ORGANIZATION,
                    discourse_role=DiscourseRole.ACTOR,
                    support_segment_label="s1",
                ),
                candidate_labels={"c1": candidate},
                source_segment_ids={"s1": segment_id},
                model_run_id=model_run_id,
                trace_id=trace.id,
            )
        )
    return build_hybrid_extraction_preview(
        representation_id=bundle.representation.id,
        paragraph_node_id=node.id,
        context_manifest_id="ctx_reference_fixture",
        ontology_card_sha256="a" * 64,
        observations=observations,
        candidates=candidates,
        boundary_decisions=boundary_decisions,
        interpretations=tuple(interpretations),
        model_run_ids=tuple(sorted(model_run_ids)),
        traces=tuple(traces),
        terminal_status=HybridPreviewStatus.COMPLETE,
    )


def _bundle(
    paragraphs: tuple[str, ...],
    *,
    representation_id: str = "rep_reference_fixture",
) -> DocumentRepresentationBundle:
    heading = "Reference Fixture"
    text = heading + "\n" + "\n".join(paragraphs)
    view = TextView(
        id=f"tvw_{representation_id}",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id=f"nod_{representation_id}_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=view.id,
        start_char=0,
        end_char=len(text),
    )
    heading_node = DocumentNode(
        id=f"nod_{representation_id}_heading",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        text_view_id=view.id,
        start_char=0,
        end_char=len(heading),
    )
    nodes = [root, heading_node]
    cursor = len(heading) + 1
    for index, paragraph in enumerate(paragraphs, start=1):
        nodes.append(
            DocumentNode(
                id=f"nod_{representation_id}_paragraph_{index}",
                representation_id=representation_id,
                parent_node_id=heading_node.id,
                node_type="paragraph",
                order_index=index + 1,
                text_view_id=view.id,
                start_char=cursor,
                end_char=cursor + len(paragraph),
            )
        )
        cursor += len(paragraph) + 1
    quality = ParseQualityReport(
        id=f"pqr_{representation_id}",
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_reference_fixture",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_reference_fixture",
        input_blob_digest=hashlib.sha256(text.encode()).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(view,),
                nodes=tuple(nodes),
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(view,),
        nodes=tuple(nodes),
        quality_report=quality,
    )


def _paragraphs(bundle: DocumentRepresentationBundle) -> tuple[DocumentNode, ...]:
    return tuple(item for item in bundle.nodes if item.node_type == "paragraph")
