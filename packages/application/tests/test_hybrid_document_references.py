from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V2,
    ContextualKind,
    CoreferenceExecution,
    CoreferenceInput,
    CoreferenceSpanProposal,
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
    SemanticReferenceCandidateLabelBinding,
    SemanticReferenceCandidateValidationExecution,
    SemanticReferenceCandidateValidationInput,
    SemanticReferenceChallengeExecution,
    SemanticReferenceChallengeInput,
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
from kotekomi_application.semantic_reference_challenge_model_output import (
    SemanticReferenceChallengeSelection,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    SemanticReferenceCandidateValidation,
    SemanticReferenceCandidateVerdict,
)
from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ModelRunStatus,
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


class _Tokenizer:
    tokenizer_id = "fixture-coref-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


class _CoreferenceProposer:
    def __init__(self, clusters: tuple[tuple[tuple[int, int], ...], ...]) -> None:
        self._clusters = clusters

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        del request
        return CoreferenceExecution(
            model_id="fixture-coref",
            model_revision="1",
            resource_identity="fixture-coref-resource",
            clusters=tuple(
                tuple(CoreferenceSpanProposal(*span) for span in cluster)
                for cluster in self._clusters
            ),
            elapsed_milliseconds=1,
            raw_output=json.dumps({"clusters": self._clusters}).encode(),
        )


class _RecordingCoreferenceProposer:
    def __init__(self) -> None:
        self.request: CoreferenceInput | None = None

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        self.request = request
        antecedent = request.source_text.index("Anthropic")
        return CoreferenceExecution(
            model_id="fixture-coref",
            model_revision="1",
            resource_identity="fixture-coref-resource",
            clusters=(
                (
                    CoreferenceSpanProposal(antecedent, antecedent + len("Anthropic")),
                    CoreferenceSpanProposal(request.target_start, request.target_end),
                ),
            ),
            elapsed_milliseconds=1,
            raw_output=b'{"clusters":[[[0,9],[30,32]]]}',
        )


class _WindowRecordingProposer:
    def __init__(self) -> None:
        self.request: CoreferenceInput | None = None

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        self.request = request
        return CoreferenceExecution(
            model_id="fixture-coref",
            model_revision="1",
            resource_identity="fixture-coref-resource",
            clusters=(),
            elapsed_milliseconds=1,
            raw_output=b'{"clusters":[]}',
        )


class _Challenger:
    def __init__(
        self,
        antecedent_text: str | None = None,
        validation_verdict: SemanticReferenceCandidateVerdict | None = None,
    ) -> None:
        self._antecedent_text = antecedent_text
        self._validation_verdict = validation_verdict

    def validate(
        self, request: SemanticReferenceCandidateValidationInput
    ) -> SemanticReferenceCandidateValidationExecution:
        verdict = self._validation_verdict
        if verdict is None:
            verdict = (
                SemanticReferenceCandidateVerdict.SUPPORTED
                if self._antecedent_text
                in {
                    None,
                    request.antecedent_candidate.span.text,
                }
                else SemanticReferenceCandidateVerdict.UNSUPPORTED
            )
        return SemanticReferenceCandidateValidationExecution(
            validation=SemanticReferenceCandidateValidation(
                verdict,
                "The source context supports this bounded verdict.",
            ),
            candidate_id=request.antecedent_candidate.id,
            extraction_task_id="ext_reference_validation",
            model_run_id="mrn_reference_validation",
            model_status=ModelRunStatus.SUCCEEDED,
            producer_id="qwen2.5-fixture",
            model_visible_task=b"exact bounded validation task",
            raw_output_sha256="b" * 64,
        )

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution:
        bindings = tuple(
            SemanticReferenceCandidateLabelBinding(f"a{ordinal}", candidate.id)
            for ordinal, candidate in enumerate(request.antecedent_candidates, start=1)
        )
        selected = (
            request.antecedent_candidates[0]
            if self._antecedent_text is None
            else next(
                item
                for item in request.antecedent_candidates
                if item.span.text == self._antecedent_text
            )
        )
        selected_label = next(item.label for item in bindings if item.candidate_id == selected.id)
        selection = SemanticReferenceChallengeSelection(
            selected_label,
            False,
            "The source context identifies this antecedent.",
        )
        return SemanticReferenceChallengeExecution(
            selection=selection,
            candidate_label_bindings=bindings,
            extraction_task_id="ext_reference_challenge",
            model_run_id="mrn_reference_challenge",
            model_status=ModelRunStatus.SUCCEEDED,
            producer_id="qwen2.5-fixture",
            model_visible_task=b"exact bounded reference task",
            raw_output_sha256="a" * 64,
            mode=request.mode,
        )


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


def test_validated_semantic_reference_becomes_a_source_bound_hp2_decision() -> None:
    text = "Trump spoke before Amodei criticized him."
    bundle = _bundle((text,))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Trump", "him"))
    trump = text.index("Trump")
    him = text.index("him")

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
        coreference_proposer=_CoreferenceProposer(
            (((trump, trump + len("Trump")), (him, him + len("him"))),)
        ),
        coreference_tokenizer=_Tokenizer(),
        semantic_reference_challenger=_Challenger(),
    )

    decision = next(
        item for item in preview.reference_decisions if item.reference_span.text == "him"
    )
    assert decision.status is ReferenceStatus.RESOLVED
    assert decision.reason is ReferenceReason.UNIQUE_SEMANTIC_ANTECEDENT
    assert decision.semantic_reference_decision_id == preview.semantic_reference_decisions[0].id
    assert [item.text for item in preview.semantic_antecedent_spans] == ["Trump"]
    assert preview.coreference_observations[0].clusters[0][0].text == "Trump"


def test_contrastively_confirmed_specialist_becomes_a_resolved_hp2_decision() -> None:
    text = "Defense conflicted with Anthropic over the use of its products."
    bundle = _bundle((text,))
    parent = _parent_preview(
        bundle,
        paragraph_index=0,
        candidate_texts=("Defense", "Anthropic", "its"),
    )
    anthropic = text.index("Anthropic")
    target = text.index("its")

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
        coreference_proposer=_CoreferenceProposer(
            (((anthropic, anthropic + len("Anthropic")), (target, target + len("its"))),)
        ),
        coreference_tokenizer=_Tokenizer(),
        semantic_reference_challenger=_Challenger(
            "Anthropic",
            validation_verdict=SemanticReferenceCandidateVerdict.UNSUPPORTED,
        ),
    )

    decision = next(
        item for item in preview.reference_decisions if item.reference_span.text == "its"
    )
    assert decision.status is ReferenceStatus.RESOLVED
    assert decision.reason is ReferenceReason.UNIQUE_SEMANTIC_ANTECEDENT
    assert [item.text for item in preview.semantic_antecedent_spans] == ["Anthropic"]
    assert preview.semantic_reference_decisions[0].reason.value == (
        "specialist_contrastive_confirmation"
    )


def test_semantic_disagreement_uses_canonical_reference_id_order() -> None:
    text = "Sacks viewed Amodei's decision and his hiring as evidence."
    bundle = _bundle((text,))
    parent = _parent_preview(
        bundle,
        paragraph_index=0,
        candidate_texts=("Sacks", "Amodei", "his"),
    )
    sacks = text.index("Sacks")
    his = text.index("his")

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
        coreference_proposer=_CoreferenceProposer(
            (((sacks, sacks + len("Sacks")), (his, his + len("his"))),)
        ),
        coreference_tokenizer=_Tokenizer(),
        semantic_reference_challenger=_Challenger("Amodei"),
    )

    decision = next(
        item for item in preview.reference_decisions if item.reference_span.text == "his"
    )
    assert decision.status is ReferenceStatus.AMBIGUOUS
    assert decision.reason is ReferenceReason.MULTIPLE_SEMANTIC_ANTECEDENTS
    assert decision.antecedent_span_ids == tuple(sorted(decision.antecedent_span_ids))
    spans = {item.id: item.text for item in preview.semantic_antecedent_spans}
    assert {spans[item] for item in decision.antecedent_span_ids} == {"Sacks", "Amodei"}


def test_semantic_reference_uses_bounded_preceding_same_paragraph_sentences() -> None:
    text = "Anthropic announced a policy. It revised the policy."
    bundle = _bundle((text,))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Anthropic", "It"))
    proposer = _RecordingCoreferenceProposer()

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
        coreference_proposer=proposer,
        coreference_tokenizer=_Tokenizer(),
        semantic_reference_challenger=_Challenger(),
    )

    assert proposer.request is not None
    assert proposer.request.source_text == text
    assert proposer.request.target_text == "It"
    assert preview.reference_decisions[0].status is ReferenceStatus.RESOLVED
    assert preview.semantic_antecedent_spans[0].text == "Anthropic"


def test_deterministic_reference_marker_routes_without_model_interpretation() -> None:
    text = "Anthropic changed the  company's policy."
    bundle = _bundle((text,))
    paragraph = _paragraphs(bundle)[0]
    segment = paragraph_source_segments(text, PARAGRAPH_SEGMENT_V2)[0]
    segment_id = hybrid_source_segment_id(bundle.representation.id, paragraph.id, segment)
    marker_text = "the  company's"
    marker_start = segment.exact_text.index(marker_text)
    marker_trace = build_extraction_stage_trace(
        trace_run_id="hpr_direct_marker",
        ordinal=0,
        stage_id="semantic_reference_discovery",
        stage_version="exact_reference_markers_v1",
        producer_id="kotekomi_application",
        source_segment_id=segment_id,
        source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
        configuration={"policy_id": "exact_reference_markers_v1"},
        input_payload={"source_text": segment.exact_text},
        output_payload={"marker_text": marker_text},
        status=ExtractionStageStatus.COMPLETED,
    )
    observation = observation_from_proposal(
        proposal=MentionProposal(
            segment.label,
            marker_text,
            marker_start,
            marker_start + len(marker_text),
            ("organization",),
        ),
        source_segment_id=segment_id,
        producer_id="kotekomi_reference_marker_v1",
        execution_record_id=marker_trace.id,
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: segment.exact_text},
        observations=(observation,),
    )
    decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: segment.exact_text},
        observations=(observation,),
        candidates=candidates,
    )
    parent = build_hybrid_extraction_preview(
        representation_id=bundle.representation.id,
        paragraph_node_id=paragraph.id,
        context_manifest_id="ctx_direct_marker",
        ontology_card_sha256="a" * 64,
        observations=(observation,),
        candidates=candidates,
        boundary_decisions=decisions,
        traces=(marker_trace,),
        terminal_status=HybridPreviewStatus.COMPLETE,
    )

    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )

    assert selected == candidates
    assert parent.interpretations == ()
    assert len(preview.reference_decisions) == 1
    assert preview.reference_decisions[0].reference_kind is ReferenceKind.ANAPHORIC
    assert preview.reference_decisions[0].reason is ReferenceReason.SEMANTIC_RESOLUTION_DEFERRED


def test_semantic_reference_excludes_a_preceding_sentence_beyond_the_token_limit() -> None:
    text = ("word " * 1025).strip() + ". It acted."
    bundle = _bundle((text,))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("It",))
    proposer = _WindowRecordingProposer()

    build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
        coreference_proposer=proposer,
        coreference_tokenizer=_Tokenizer(),
        semantic_reference_challenger=_Challenger(),
    )

    assert proposer.request is not None
    assert proposer.request.source_text == "It acted."
    assert proposer.request.target_text == "It"


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
    located = tuple(
        (
            text,
            next(item for item in segments if text in item.exact_text),
        )
        for text in candidate_texts
    )
    source_segments = {
        hybrid_source_segment_id(bundle.representation.id, node.id, segment): segment.exact_text
        for _, segment in located
    }
    observations = tuple(
        observation_from_proposal(
            proposal=MentionProposal(
                segment.label,
                text,
                segment.exact_text.index(text),
                segment.exact_text.index(text) + len(text),
                ("organization",),
            ),
            source_segment_id=hybrid_source_segment_id(bundle.representation.id, node.id, segment),
            producer_id=f"fixture_{index}",
            execution_record_id=f"mrn_proposal_{index}",
        )
        for index, (text, segment) in enumerate(located, start=1)
    )
    candidates = fuse_mention_observations(
        source_segments=source_segments, observations=observations
    )
    boundary_decisions, selected = reconcile_mention_boundaries(
        source_segments=source_segments,
        observations=observations,
        candidates=candidates,
    )
    traces: list[ExtractionStageTrace] = []
    model_run_ids: list[str] = []
    ordinals: dict[str, int] = {}
    for observation in observations:
        source_text = source_segments[observation.source_segment_id]
        ordinal = ordinals.get(observation.source_segment_id, 0)
        ordinals[observation.source_segment_id] = ordinal + 1
        model_run_ids.append(observation.execution_record_id)
        traces.append(
            build_extraction_stage_trace(
                trace_run_id="hpr_fixture_reference",
                ordinal=ordinal,
                stage_id="mention_proposal",
                stage_version="fixture_v1",
                producer_id=observation.producer_id,
                source_segment_id=observation.source_segment_id,
                source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
                execution_record_ids=(observation.execution_record_id,),
                configuration={},
                input_payload={"text": source_text},
                output_payload={"observation_id": observation.id},
                status=ExtractionStageStatus.COMPLETED,
            )
        )
    for segment_id, source_text in sorted(source_segments.items()):
        ordinal = ordinals.get(segment_id, 0)
        ordinals[segment_id] = ordinal + 1
        traces.append(
            build_extraction_stage_trace(
                trace_run_id="hpr_fixture_reference",
                ordinal=ordinal,
                stage_id="mention_boundary_reconciliation",
                stage_version="fixture_v1",
                producer_id="fixture",
                source_segment_id=segment_id,
                source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
                configuration={},
                input_payload={
                    "candidate_ids": [
                        item.id for item in candidates if item.source_segment_id == segment_id
                    ]
                },
                output_payload={
                    "decision_ids": [
                        item.id
                        for item in boundary_decisions
                        if item.source_segment_id == segment_id
                    ]
                },
                status=ExtractionStageStatus.COMPLETED,
            )
        )
    interpretations: list[MentionInterpretation] = []
    for candidate in selected:
        source_text = source_segments[candidate.source_segment_id]
        ordinal = ordinals.get(candidate.source_segment_id, 0)
        ordinals[candidate.source_segment_id] = ordinal + 1
        model_run_id = f"mrn_interpret_{candidate.id}"
        model_run_ids.append(model_run_id)
        trace = build_extraction_stage_trace(
            trace_run_id="hpr_fixture_reference",
            ordinal=ordinal,
            stage_id="mention_interpretation",
            stage_version="fixture_v1",
            producer_id="fixture",
            source_segment_id=candidate.source_segment_id,
            source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
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
                        if candidate.text.casefold() in {"him", "his", "it", "its", "the institute"}
                        else Referentiality.SPECIFIC_ENTITY
                    ),
                    contextual_kind=ContextualKind.ORGANIZATION,
                    discourse_role=DiscourseRole.ACTOR,
                    support_segment_label="s1",
                ),
                candidate_labels={"c1": candidate},
                source_segment_ids={"s1": candidate.source_segment_id},
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
        traces=tuple(
            sorted(traces, key=lambda item: (item.source_segment_id, item.ordinal, item.id))
        ),
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
