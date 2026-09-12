"""Event-trigger discovery over immutable HP-3 source evidence."""

from __future__ import annotations

import hashlib
import json
import re
from base64 import b64encode
from dataclasses import dataclass
from functools import partial
from typing import Protocol, cast

from kotekomi_domain import DocumentRepresentationBundle, ModelRunStatus
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisUnit,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextPlanningLedger,
    ContextTokenizer,
    SourceCopyView,
    SourceSegmentAnalysisUnitInput,
    build_context_manifest,
    create_analysis_unit_from_source_segment,
    derive_source_copy_view,
    load_context_manifest,
    paragraph_source_segments,
    verify_context_manifest,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_entity_grounding import (
    HybridEntityGroundingPreview,
    canonical_hybrid_entity_grounding_preview_bytes,
    hybrid_entity_grounding_preview_from_bytes,
)
from kotekomi_application.hybrid_event_trigger_model_output import (
    BinarySemanticAnswerValue,
    EventHeadAnswerValue,
    EventVerbRoleAnswerValue,
    binary_semantic_answer_schema_bytes,
    event_head_answer_schema_bytes,
    event_verb_role_answer_schema_bytes,
    parse_binary_semantic_answer,
    parse_event_head_answer,
    parse_event_verb_role_answer,
)
from kotekomi_application.hybrid_event_triggers import (
    EVENT_HEAD_CANDIDATE_POLICY_ID,
    HYBRID_EVENT_TRIGGER_POLICY_ID,
    EventHeadCandidate,
    EventHeadCandidateSelection,
    EventRoutingAnswerValue,
    EventRoutingJudgment,
    EventSemanticRoute,
    EventTriggerDecision,
    EventTriggerDraft,
    HybridEventTriggerPreview,
    HybridEventTriggerStatus,
    TriggerDecisionDisposition,
    TriggerDecisionDispositionValue,
    build_hybrid_event_trigger_preview,
    canonical_hybrid_event_trigger_preview_bytes,
    event_trigger_id,
    hybrid_event_trigger_preview_from_bytes,
    hybrid_event_trigger_preview_sha256,
    select_event_head_candidates,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)
from kotekomi_application.linguistic_analysis import (
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticAnalyzer,
    LinguisticToken,
    UniversalPartOfSpeech,
)
from kotekomi_application.nominalization_analysis import (
    NominalizationAnalysis,
    NominalizationAnalysisInput,
    NominalizationAnalyzer,
    NominalizationCandidate,
)
from kotekomi_application.source_occurrences import SourceOccurrence
from kotekomi_application.source_occurrences import source_occurrences as _source_occurrences
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    BoundedExtractionOutcome,
    ExecutionSetting,
    ModelExecutionSpec,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    run_bounded_extraction,
)

EVENT_HEAD_JUDGMENT_SCHEMA_ID = "event_head_judgment_text_v2"
EVENT_VERB_ROLE_SCHEMA_ID = "event_verb_role_text_v1"
EVENT_BINARY_SEMANTIC_SCHEMA_ID = "event_binary_semantic_text_v1"
BOUNDED_ANSWER_MAX_OUTPUT_TOKENS = 2
TRIGGER_RECONCILIATION_POLICY_ID = "routed_event_judgment_v2"
_EVENT_TYPE_LABEL = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$"
_SUPPORT_VERBS = frozenset(
    {"conduct", "do", "express", "give", "hold", "make", "perform", "reach", "take"}
)
_TEMPORAL_CASE_MARKERS = frozenset({"amid", "during"})


class HybridEventTriggerLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class HybridEventTriggerArchive(Protocol):
    def read_hybrid_event_trigger_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_entity_grounding_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes: ...

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object: ...

    def put_hybrid_event_trigger_preview(
        self,
        preview: HybridEventTriggerPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...


@dataclass(frozen=True)
class HybridEventTriggerCommand:
    parent_preview_id: str
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]


@dataclass(frozen=True)
class HybridEventTriggerPrompts:
    verb_role: bytes
    verb_similarity: bytes
    noun_inventory: bytes
    noun_dependent_kind: bytes
    noun_media_artifact: bytes
    noun_governor_distinct: bytes
    noun_reaction: bytes
    noun_standing: bytes

    def for_route(self, route: EventSemanticRoute) -> bytes:
        return {
            EventSemanticRoute.VERB_ROLE: self.verb_role,
            EventSemanticRoute.VERB_SIMILARITY: self.verb_similarity,
            EventSemanticRoute.NOUN_INVENTORY: self.noun_inventory,
            EventSemanticRoute.NOUN_DEPENDENT_KIND: self.noun_dependent_kind,
            EventSemanticRoute.NOUN_MEDIA_ARTIFACT: self.noun_media_artifact,
            EventSemanticRoute.NOUN_GOVERNOR_DISTINCT: self.noun_governor_distinct,
            EventSemanticRoute.NOUN_REACTION: self.noun_reaction,
            EventSemanticRoute.NOUN_STANDING: self.noun_standing,
        }[route]


@dataclass(frozen=True)
class HybridEventTriggerResult:
    preview: HybridEventTriggerPreview
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class _SourceContext:
    bundle: DocumentRepresentationBundle
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    grounding: HybridEntityGroundingPreview
    paragraph_text: str


@dataclass(frozen=True)
class EventTriggerDecisionReconciliation:
    """Complete deterministic result over every selected candidate."""

    event_decisions: tuple[EventTriggerDecision, ...]
    non_event_decisions: tuple[EventTriggerDecision, ...]
    dispositions: tuple[TriggerDecisionDisposition, ...]
    unclassified_occurrence_ids: tuple[str, ...]
    routing_judgments: tuple[EventRoutingJudgment, ...]


@dataclass(frozen=True)
class _RouteExecution:
    judgment: EventRoutingJudgment | None
    outcome: BoundedExtractionOutcome
    trace: ExtractionStageTrace


class _EventHeadSchemaRegistry:
    schema_id = EVENT_HEAD_JUDGMENT_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Event head judgment schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id,
            event_head_answer_schema_bytes(),
            schema_id,
            parse_event_head_answer,
        )


class _EventVerbRoleSchemaRegistry:
    schema_id = EVENT_VERB_ROLE_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Event verb-role schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id,
            event_verb_role_answer_schema_bytes(),
            schema_id,
            parse_event_verb_role_answer,
        )


class _BinarySemanticSchemaRegistry:
    schema_id = EVENT_BINARY_SEMANTIC_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Event binary semantic schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id,
            binary_semantic_answer_schema_bytes(),
            schema_id,
            parse_binary_semantic_answer,
        )


def load_hybrid_event_trigger_preview(
    preview_id: str,
    archive: HybridEventTriggerArchive,
) -> HybridEventTriggerPreview:
    """Reload one canonical trigger Preview and verify its complete parent chain."""
    payload = archive.read_hybrid_event_trigger_preview(preview_id)
    preview = hybrid_event_trigger_preview_from_bytes(payload)
    if preview.id != preview_id or canonical_hybrid_event_trigger_preview_bytes(preview) != payload:
        raise ValueError("Event-trigger Preview identity or canonical encoding is invalid.")
    grounding_payload = archive.read_hybrid_entity_grounding_preview(preview.parent_preview_id)
    grounding = hybrid_entity_grounding_preview_from_bytes(grounding_payload)
    if (
        grounding.id != preview.parent_preview_id
        or canonical_hybrid_entity_grounding_preview_bytes(grounding) != grounding_payload
        or hashlib.sha256(grounding_payload).hexdigest() != preview.parent_preview_sha256
    ):
        raise ValueError("Event-trigger HP-3 parent evidence does not match its digest.")
    reference_payload = archive.read_hybrid_reference_preview(preview.reference_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if (
        references.id != preview.reference_preview_id
        or references.id != grounding.parent_preview_id
        or canonical_hybrid_reference_preview_bytes(references) != reference_payload
        or hashlib.sha256(reference_payload).hexdigest() != preview.reference_preview_sha256
        or grounding.parent_preview_sha256 != preview.reference_preview_sha256
    ):
        raise ValueError("Event-trigger HP-2 parent evidence does not match its lineage.")
    mention_payload = archive.read_hybrid_extraction_preview(preview.mention_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    if (
        mentions.id != preview.mention_preview_id
        or mentions.id != references.parent_preview_id
        or mentions.id != grounding.mention_preview_id
        or canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload
        or hashlib.sha256(mention_payload).hexdigest() != preview.mention_preview_sha256
        or grounding.mention_preview_sha256 != preview.mention_preview_sha256
    ):
        raise ValueError("Event-trigger HP-1 parent evidence does not match its lineage.")
    if (
        len(
            {
                preview.representation_id,
                grounding.representation_id,
                references.representation_id,
                mentions.representation_id,
            }
        )
        != 1
    ):
        raise ValueError("Event-trigger representation lineage is inconsistent.")
    return preview


def run_hybrid_event_trigger_preview(
    *,
    command: HybridEventTriggerCommand,
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    prompts: HybridEventTriggerPrompts,
    linguistic_analyzer: LinguisticAnalyzer,
    nominalization_analyzer: NominalizationAnalyzer,
) -> HybridEventTriggerResult:
    """Route specialist candidates through bounded judgments and publish exact triggers."""
    context, digests = _load_source_context(command.parent_preview_id, ledger, archive)
    segments = paragraph_source_segments(context.paragraph_text, PARAGRAPH_SEGMENT_V3)
    document = ledger.get_document(context.bundle.representation.document_id)
    if document is None:
        raise ValueError("Event-trigger representation references a missing Document.")
    source = ledger.get_source(document.source_id)
    if source is None:
        raise ValueError("Event-trigger Document references a missing Source.")

    task_ids: list[str] = []
    run_ids: list[str] = []
    manifest_ids: list[str] = []
    traces: list[ExtractionStageTrace] = []
    diagnostics: list[str] = []
    triggers: list[EventTriggerDraft] = []
    for segment in segments:
        segment_id = hybrid_source_segment_id(
            context.mentions.representation_id,
            context.mentions.paragraph_node_id,
            segment,
        )
        unit = create_analysis_unit_from_source_segment(
            SourceSegmentAnalysisUnitInput(
                representation_id=context.mentions.representation_id,
                paragraph_node_id=context.mentions.paragraph_node_id,
                source_segment_label=segment.label,
                policy_id=HYBRID_EVENT_TRIGGER_POLICY_ID,
                task_type="hybrid_event_trigger_preview",
            ),
            ledger,
        )
        source_copy = derive_source_copy_view(segment.exact_text)
        occurrences = source_occurrences(source_copy)
        trace_run_id = f"event_trigger:{context.grounding.id}:{segment_id}"
        try:
            linguistic = linguistic_analyzer.analyze(LinguisticAnalysisInput(source_copy.text))
            nominalization = nominalization_analyzer.analyze(
                NominalizationAnalysisInput(source_copy.text, linguistic)
            )
            selection = select_event_head_candidates(
                source_copy.text,
                occurrences,
                linguistic,
                nominalization,
            )
        except (OSError, RuntimeError, ValueError) as error:
            traces.append(
                _failed_specialist_trace(
                    trace_run_id=trace_run_id,
                    source_segment_id=segment_id,
                    source_text=segment.exact_text,
                    source_copy=source_copy,
                    occurrences=occurrences,
                    error=error,
                    input_record_id=context.grounding.id,
                )
            )
            diagnostics.append(f"event_candidate_analysis_failed:{segment_id}")
            continue

        linguistic_trace = _linguistic_analysis_trace(
            trace_run_id=trace_run_id,
            source_segment_id=segment_id,
            source_text=segment.exact_text,
            source_copy=source_copy,
            analysis=linguistic,
            input_record_id=context.grounding.id,
        )
        nominalization_trace = _nominalization_analysis_trace(
            trace_run_id=trace_run_id,
            source_segment_id=segment_id,
            source_text=segment.exact_text,
            analysis=nominalization,
            parent_trace_id=linguistic_trace.id,
        )
        candidate_trace = _event_head_candidate_trace(
            trace_run_id=trace_run_id,
            source_segment_id=segment_id,
            source_text=segment.exact_text,
            occurrences=occurrences,
            selection=selection,
            parent_trace_ids=tuple(sorted((linguistic_trace.id, nominalization_trace.id))),
        )
        segment_traces = [linguistic_trace, nominalization_trace, candidate_trace]
        manifests: dict[EventSemanticRoute, ContextManifest] = {}
        judgments: list[EventRoutingJudgment] = []
        decisions: list[EventTriggerDecision] = []
        unclassified: list[str] = []
        candidate_by_id = {item.occurrence_id: item for item in selection.candidates}
        token_by_id = {item.token_id: item for item in linguistic.tokens}

        judge = partial(
            _run_and_record_route,
            source_text=source_copy.text,
            source_id=source.id,
            document_id=document.id,
            representation_id=context.mentions.representation_id,
            unit=unit,
            command=command,
            prompts=prompts,
            manifests=manifests,
            ledger=ledger,
            archive=archive,
            model_runtime=model_runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=tokenizer,
            trace_run_id=trace_run_id,
            source_segment_id=segment_id,
            source_segment_text=segment.exact_text,
            parent_trace_id=candidate_trace.id,
            input_record_id=context.grounding.id,
            task_ids=task_ids,
            run_ids=run_ids,
            segment_traces=segment_traces,
            manifest_ids=manifest_ids,
            diagnostics=diagnostics,
            judgments=judgments,
        )

        noun_candidates = tuple(
            item
            for item in selection.candidates
            if item.part_of_speech is UniversalPartOfSpeech.NOUN
        )
        for candidate in noun_candidates:
            decision = _route_noun_candidate(
                candidate,
                source_copy.text,
                token_by_id,
                judge,
            )
            if decision is None:
                unclassified.append(candidate.occurrence_id)
            else:
                decisions.append(decision)

        selected_noun_ids = {
            item.occurrence_id for item in decisions if item.answer is EventHeadAnswerValue.EVENT
        }
        verb_candidates = tuple(
            item
            for item in selection.candidates
            if item.part_of_speech is UniversalPartOfSpeech.VERB
        )
        for candidate in verb_candidates:
            decision = _route_verb_candidate(
                candidate,
                candidate_by_id,
                token_by_id,
                selected_noun_ids,
                judge,
            )
            if decision is None:
                unclassified.append(candidate.occurrence_id)
            else:
                decisions.append(decision)

        reconciliation = reconcile_event_trigger_decisions(
            tuple(decisions),
            candidates=candidate_by_id,
            routing_judgments=tuple(judgments),
            unclassified_occurrence_ids=tuple(unclassified),
        )
        parent_trace_ids = tuple(item.id for item in segment_traces[2:])
        reconciliation_trace = _trigger_reconciliation_trace(
            trace_run_id=trace_run_id,
            source_segment_id=segment_id,
            source_text=segment.exact_text,
            candidates=selection.candidates,
            reconciliation=reconciliation,
            parent_trace_ids=parent_trace_ids or (candidate_trace.id,),
            ordinal=len(segment_traces),
        )
        segment_traces.append(reconciliation_trace)
        triggers.extend(
            _resolve_trigger(
                decision,
                candidate=candidate_by_id[decision.occurrence_id],
                segment_id=segment_id,
                source_text=segment.exact_text,
                source_copy=source_copy,
                trace_id=reconciliation_trace.id,
            )
            for decision in reconciliation.event_decisions
        )
        traces.extend(segment_traces)

    status = HybridEventTriggerStatus.COMPLETE
    if diagnostics:
        status = HybridEventTriggerStatus.PARTIAL
    preview = build_hybrid_event_trigger_preview(
        parent_preview_id=context.grounding.id,
        parent_preview_sha256=digests["grounding"],
        reference_preview_id=context.references.id,
        reference_preview_sha256=digests["references"],
        mention_preview_id=context.mentions.id,
        mention_preview_sha256=digests["mentions"],
        representation_id=context.mentions.representation_id,
        paragraph_node_id=context.mentions.paragraph_node_id,
        context_manifest_ids=tuple(sorted(set(manifest_ids))),
        triggers=tuple(sorted(triggers, key=lambda item: (item.start, item.end, item.id))),
        extraction_task_ids=tuple(sorted(set(task_ids))),
        model_run_ids=tuple(sorted(set(run_ids))),
        traces=tuple(sorted(traces, key=lambda item: (item.trace_run_id, item.ordinal, item.id))),
        terminal_status=status,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    payload = canonical_hybrid_event_trigger_preview_bytes(preview)
    digest = hybrid_event_trigger_preview_sha256(preview)
    archive.put_hybrid_event_trigger_preview(preview, payload, digest)
    return HybridEventTriggerResult(
        preview,
        digest,
        f"extraction/event-trigger-previews/{preview.id}.json",
    )


def _run_and_record_route(
    candidate: EventHeadCandidate,
    route: EventSemanticRoute,
    *,
    other: LinguisticToken | None = None,
    source_text: str,
    source_id: str,
    document_id: str,
    representation_id: str,
    unit: AnalysisUnit,
    command: HybridEventTriggerCommand,
    prompts: HybridEventTriggerPrompts,
    manifests: dict[EventSemanticRoute, ContextManifest],
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    trace_run_id: str,
    source_segment_id: str,
    source_segment_text: str,
    parent_trace_id: str,
    input_record_id: str,
    task_ids: list[str],
    run_ids: list[str],
    segment_traces: list[ExtractionStageTrace],
    manifest_ids: list[str],
    diagnostics: list[str],
    judgments: list[EventRoutingJudgment],
) -> EventRoutingJudgment | None:
    execution = _run_route(
        route=route,
        candidate=candidate,
        other=other,
        source_text=source_text,
        source_id=source_id,
        document_id=document_id,
        representation_id=representation_id,
        unit=unit,
        command=command,
        prompts=prompts,
        manifests=manifests,
        ledger=ledger,
        archive=archive,
        model_runtime=model_runtime,
        model_run_id_factory=model_run_id_factory,
        tokenizer=tokenizer,
        trace_run_id=trace_run_id,
        trace_ordinal=len(segment_traces),
        source_segment_id=source_segment_id,
        source_segment_text=source_segment_text,
        parent_trace_id=parent_trace_id,
        input_record_id=input_record_id,
    )
    task_ids.append(execution.outcome.extraction_task.id)
    run_ids.append(execution.outcome.model_run.id)
    segment_traces.append(execution.trace)
    manifest_ids.append(execution.outcome.extraction_task.context_manifest_id)
    if execution.judgment is None:
        diagnostics.append(
            f"event_route_failed:{source_segment_id}:{candidate.occurrence_id}:{route.value}"
        )
        return None
    judgments.append(execution.judgment)
    return execution.judgment


def _route_noun_candidate(
    candidate: EventHeadCandidate,
    source_text: str,
    token_by_id: dict[str, LinguisticToken],
    judge: object,
) -> EventTriggerDecision | None:
    run = cast(_Judge, judge)
    inventory = run(candidate, EventSemanticRoute.NOUN_INVENTORY)
    governor = (
        token_by_id.get(candidate.dependency_head_token_id)
        if candidate.dependency_head_token_id is not None
        else None
    )
    children = tuple(
        item for item in token_by_id.values() if item.head_token_id == candidate.linguistic_token_id
    )

    if candidate.dependency_relation == "compound":
        accepted = candidate.text.casefold().endswith("ing")
        reason = "gerundive_compound_occurrence" if accepted else "non_gerundive_compound_modifier"
        return _final_decision(candidate, accepted, reason, inventory)
    if (
        governor is not None
        and governor.part_of_speech is UniversalPartOfSpeech.VERB
        and governor.lemma.casefold() in _SUPPORT_VERBS
        and candidate.dependency_relation in {"obj", "iobj"}
    ):
        return _final_decision(candidate, True, "support_verb_nominal_head", inventory)
    if inventory is None:
        return None
    if inventory.answer is EventRoutingAnswerValue.NO:
        if (
            governor is None
            or governor.part_of_speech is not UniversalPartOfSpeech.VERB
            or candidate.dependency_relation != "obj"
        ):
            return _final_decision(candidate, False, "model_not_event", inventory)
        if not _has_bounded_nominal_reference(children):
            return _final_decision(
                candidate,
                False,
                "inventory_non_event_without_bounded_reference",
                inventory,
            )
        dependent_kind = run(
            candidate,
            EventSemanticRoute.NOUN_DEPENDENT_KIND,
            other=governor,
        )
        if dependent_kind is None:
            return None
        if dependent_kind.answer is EventRoutingAnswerValue.YES:
            return _final_decision(
                candidate,
                False,
                "dependent_artifact_content_or_plan",
                dependent_kind,
            )
        distinct = run(candidate, EventSemanticRoute.NOUN_GOVERNOR_DISTINCT, other=governor)
        reaction = run(candidate, EventSemanticRoute.NOUN_REACTION, other=governor)
        if distinct is None or reaction is None:
            return None
        accepted = (
            distinct.answer is EventRoutingAnswerValue.YES
            and reaction.answer is EventRoutingAnswerValue.YES
        )
        return _final_decision(
            candidate,
            accepted,
            "distinct_reaction_object_occurrence" if accepted else "model_not_event",
            reaction,
        )

    if governor is not None and governor.part_of_speech is UniversalPartOfSpeech.VERB:
        dependent_kind = run(
            candidate,
            EventSemanticRoute.NOUN_DEPENDENT_KIND,
            other=governor,
        )
        if dependent_kind is None:
            return None
        if dependent_kind.answer is EventRoutingAnswerValue.YES:
            return _final_decision(
                candidate,
                False,
                "dependent_artifact_content_or_plan",
                dependent_kind,
            )
    if candidate.dependency_relation == "obl":
        media = run(candidate, EventSemanticRoute.NOUN_MEDIA_ARTIFACT)
        if media is None:
            return None
        if media.answer is EventRoutingAnswerValue.YES:
            return _final_decision(
                candidate,
                False,
                "communication_or_media_artifact",
                media,
            )
    if re.search(
        rf"(?i)prior\s+to\s+the\s+{re.escape(candidate.text)}\s*$",
        source_text[: candidate.end],
    ):
        return _final_decision(candidate, False, "anaphoric_prior_occurrence", inventory)
    finite_acl = any(
        child.part_of_speech is UniversalPartOfSpeech.VERB
        and child.dependency_relation.startswith("acl")
        and not any(
            marker.head_token_id == child.token_id and marker.lemma.casefold() == "to"
            for marker in token_by_id.values()
        )
        for child in children
    )
    if finite_acl:
        return _final_decision(
            candidate,
            False,
            "artifact_with_explicit_verbal_occurrence",
            inventory,
        )
    standing = run(candidate, EventSemanticRoute.NOUN_STANDING)
    if standing is None:
        return None
    if standing.answer is EventRoutingAnswerValue.YES:
        temporal = any(
            child.dependency_relation == "case" and child.lemma.casefold() in _TEMPORAL_CASE_MARKERS
            for child in children
        )
        return _final_decision(
            candidate,
            temporal,
            "temporally_introduced_occurrence" if temporal else "standing_state_or_relationship",
            standing,
        )
    return _final_decision(candidate, True, "model_event_inventory", inventory)


def _has_bounded_nominal_reference(children: tuple[LinguisticToken, ...]) -> bool:
    """Require grammatical evidence before rescuing an inventory-rejected noun."""
    return any(
        child.dependency_relation in {"det", "nummod"}
        or child.dependency_relation.startswith("nmod")
        for child in children
    )


def _route_verb_candidate(
    candidate: EventHeadCandidate,
    candidates: dict[str, EventHeadCandidate],
    token_by_id: dict[str, LinguisticToken],
    selected_noun_ids: set[str],
    judge: object,
) -> EventTriggerDecision | None:
    run = cast(_Judge, judge)
    role = run(candidate, EventSemanticRoute.VERB_ROLE)
    if role is None:
        return None
    linked_noun = any(
        noun_id in selected_noun_ids
        and (
            candidates[noun_id].dependency_head_token_id == candidate.linguistic_token_id
            or candidate.dependency_head_token_id == candidates[noun_id].linguistic_token_id
        )
        and token_by_id[candidates[noun_id].linguistic_token_id].sentence_id
        == candidate.sentence_id
        for noun_id in selected_noun_ids
    )
    has_content_complement = any(
        token.head_token_id == candidate.linguistic_token_id
        and token.dependency_relation in {"ccomp", "iobj", "obj", "obl", "xcomp"}
        for token in token_by_id.values()
    )
    if candidate.lemma.casefold() == "have" and not has_content_complement:
        return _final_decision(candidate, False, "bare_have_proform_or_state", role)
    if role.answer is EventRoutingAnswerValue.STANDING:
        return _final_decision(candidate, False, "model_non_event_role", role)
    if role.answer is EventRoutingAnswerValue.HELPER:
        return _final_decision(
            candidate,
            not linked_noun,
            ("model_helper_for_selected_nominal" if linked_noun else "uncorroborated_model_helper"),
            role,
        )
    similarity = run(candidate, EventSemanticRoute.VERB_SIMILARITY)
    if similarity is None:
        return None
    if similarity.answer is EventRoutingAnswerValue.YES:
        return _final_decision(candidate, False, "standing_similarity", similarity)
    if candidate.lemma.casefold() in _SUPPORT_VERBS and linked_noun:
        return _final_decision(
            candidate,
            False,
            "support_verb_for_selected_nominal",
            role,
        )
    return _final_decision(candidate, True, "model_event_role", role)


class _Judge(Protocol):
    def __call__(
        self,
        candidate: EventHeadCandidate,
        route: EventSemanticRoute,
        *,
        other: LinguisticToken | None = None,
    ) -> EventRoutingJudgment | None: ...


def _final_decision(
    candidate: EventHeadCandidate,
    accepted: bool,
    reason_code: str,
    lineage: EventRoutingJudgment | None,
) -> EventTriggerDecision | None:
    if lineage is None:
        return None
    return EventTriggerDecision(
        occurrence_id=candidate.occurrence_id,
        answer=(EventHeadAnswerValue.EVENT if accepted else EventHeadAnswerValue.NOT_EVENT),
        reason_code=reason_code,
        extraction_task_id=lineage.extraction_task_id,
        model_run_id=lineage.model_run_id,
    )


def reconcile_event_trigger_decisions(
    decisions: tuple[EventTriggerDecision, ...],
    *,
    candidates: dict[str, EventHeadCandidate],
    routing_judgments: tuple[EventRoutingJudgment, ...] = (),
    unclassified_occurrence_ids: tuple[str, ...] = (),
) -> EventTriggerDecisionReconciliation:
    """Validate complete coverage and expose every deterministic disposition."""
    decision_by_id = {item.occurrence_id: item for item in decisions}
    if len(decision_by_id) != len(decisions) or not set(decision_by_id) <= set(candidates):
        raise ValueError("Event decisions must bind distinct known candidates.")
    unclassified = set(unclassified_occurrence_ids)
    if len(unclassified) != len(unclassified_occurrence_ids) or not unclassified <= set(candidates):
        raise ValueError("Unclassified Event candidates must be distinct and known.")
    if set(decision_by_id) & unclassified:
        raise ValueError("An Event candidate cannot be both decided and unclassified.")
    if set(candidates) != set(decision_by_id) | unclassified:
        raise ValueError("Every Event candidate requires a decision or failed attempt.")
    judgments_by_key = {(item.occurrence_id, item.route) for item in routing_judgments}
    if len(judgments_by_key) != len(routing_judgments):
        raise ValueError("Event routing judgments must be unique by candidate and route.")
    dispositions = tuple(
        TriggerDecisionDisposition(
            occurrence_id=item.occurrence_id,
            answer=item.answer,
            disposition=(
                TriggerDecisionDispositionValue.ACCEPTED
                if item.answer is EventHeadAnswerValue.EVENT
                else TriggerDecisionDispositionValue.REJECTED
            ),
            reason_code=item.reason_code,
        )
        for item in sorted(decisions, key=lambda value: candidates[value.occurrence_id].start)
    )
    return EventTriggerDecisionReconciliation(
        event_decisions=tuple(
            item
            for item in sorted(decisions, key=lambda value: candidates[value.occurrence_id].start)
            if item.answer is EventHeadAnswerValue.EVENT
        ),
        non_event_decisions=tuple(
            item
            for item in sorted(decisions, key=lambda value: candidates[value.occurrence_id].start)
            if item.answer is EventHeadAnswerValue.NOT_EVENT
        ),
        dispositions=dispositions,
        unclassified_occurrence_ids=tuple(
            sorted(unclassified, key=lambda value: candidates[value].start)
        ),
        routing_judgments=routing_judgments,
    )


def source_occurrences(source_copy: SourceCopyView) -> tuple[SourceOccurrence, ...]:
    return _source_occurrences(source_copy.text)


def _run_route(
    *,
    route: EventSemanticRoute,
    candidate: EventHeadCandidate,
    other: LinguisticToken | None,
    source_text: str,
    source_id: str,
    document_id: str,
    representation_id: str,
    unit: AnalysisUnit,
    command: HybridEventTriggerCommand,
    prompts: HybridEventTriggerPrompts,
    manifests: dict[EventSemanticRoute, ContextManifest],
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    trace_run_id: str,
    trace_ordinal: int,
    source_segment_id: str,
    source_segment_text: str,
    parent_trace_id: str,
    input_record_id: str,
) -> _RouteExecution:
    registry, schema = _schema_for_route(route)
    prompt_bytes = prompts.for_route(route)
    manifest = manifests.get(route)
    if manifest is None:
        manifest = _build_manifest(
            unit=unit,
            profile=command.model_profile,
            prompt_id=f"event_{route.value}_v1",
            renderer_version=f"event_{route.value}_context_v1",
            prompt_bytes=prompt_bytes,
            schema=schema,
            ledger=ledger,
            tokenizer=tokenizer,
        )
        manifests[route] = manifest
    task_input = _route_task_input(source_text, candidate, route, other)
    outcome = _run_model_judgment(
        source_id=source_id,
        document_id=document_id,
        representation_id=representation_id,
        manifest=manifest,
        prompt_bytes=prompt_bytes,
        schema=schema,
        task_input=task_input,
        task_type=f"event_{route.value}",
        validator_version=f"event_{route.value}_validator_v1",
        generation_parameters=_bounded_answer_generation_parameters(command.generation_parameters),
        ledger=ledger,
        archive=archive,
        model_runtime=model_runtime,
        model_run_id_factory=model_run_id_factory,
        tokenizer=tokenizer,
        registry=registry,
    )
    answer = _routing_answer(route, outcome)
    succeeded = outcome.model_run.status is ModelRunStatus.SUCCEEDED and answer is not None
    judgment = (
        EventRoutingJudgment(
            occurrence_id=candidate.occurrence_id,
            route=route,
            answer=answer,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
        )
        if succeeded and answer is not None
        else None
    )
    trace = _model_judgment_trace(
        trace_run_id=trace_run_id,
        ordinal=trace_ordinal,
        route=route,
        source_segment_id=source_segment_id,
        source_text=source_segment_text,
        parent_trace_id=parent_trace_id,
        input_record_id=input_record_id,
        manifest=manifest,
        prompt_bytes=prompt_bytes,
        schema=schema,
        task_input=task_input,
        candidate_binding=_event_head_candidate_payload(candidate),
        other_binding=_linguistic_token_payload(other) if other is not None else None,
        outcome=outcome,
        parsed_answer=answer.value if answer is not None else None,
    )
    return _RouteExecution(judgment, outcome, trace)


def _schema_for_route(
    route: EventSemanticRoute,
) -> tuple[TaskSchemaRegistry, PinnedTaskSchema]:
    if route is EventSemanticRoute.VERB_ROLE:
        registry: TaskSchemaRegistry = _EventVerbRoleSchemaRegistry()
        return registry, registry.resolve(EVENT_VERB_ROLE_SCHEMA_ID)
    if route is EventSemanticRoute.NOUN_INVENTORY:
        registry = _EventHeadSchemaRegistry()
        return registry, registry.resolve(EVENT_HEAD_JUDGMENT_SCHEMA_ID)
    registry = _BinarySemanticSchemaRegistry()
    return registry, registry.resolve(EVENT_BINARY_SEMANTIC_SCHEMA_ID)


def _routing_answer(
    route: EventSemanticRoute,
    outcome: BoundedExtractionOutcome,
) -> EventRoutingAnswerValue | None:
    if route is EventSemanticRoute.VERB_ROLE:
        answer = outcome.event_verb_role_answer
        if answer is None:
            return None
        return {
            EventVerbRoleAnswerValue.EVENT: EventRoutingAnswerValue.EVENT,
            EventVerbRoleAnswerValue.STANDING: EventRoutingAnswerValue.STANDING,
            EventVerbRoleAnswerValue.HELPER: EventRoutingAnswerValue.HELPER,
        }[answer.value]
    if route is EventSemanticRoute.NOUN_INVENTORY:
        answer = outcome.event_head_answer
        if answer is None:
            return None
        return (
            EventRoutingAnswerValue.EVENT
            if answer.value is EventHeadAnswerValue.EVENT
            else EventRoutingAnswerValue.NO
        )
    answer = outcome.binary_semantic_answer
    if answer is None:
        return None
    return (
        EventRoutingAnswerValue.YES
        if answer.value is BinarySemanticAnswerValue.YES
        else EventRoutingAnswerValue.NO
    )


def _route_task_input(
    source_text: str,
    candidate: EventHeadCandidate,
    route: EventSemanticRoute,
    other: LinguisticToken | None,
) -> bytes:
    target_kind = "verb" if candidate.part_of_speech is UniversalPartOfSpeech.VERB else "noun"
    if route in {
        EventSemanticRoute.NOUN_DEPENDENT_KIND,
        EventSemanticRoute.NOUN_GOVERNOR_DISTINCT,
        EventSemanticRoute.NOUN_REACTION,
    }:
        if other is None or other.part_of_speech is not UniversalPartOfSpeech.VERB:
            raise ValueError(f"{route.value} requires one governing verb.")
        lines = [
            "Sentence as a JSON string:",
            json.dumps(source_text, ensure_ascii=False),
            "Marked verb as a JSON string:",
            json.dumps(other.text, ensure_ascii=False),
            "Marked noun as a JSON string:",
            json.dumps(candidate.text, ensure_ascii=False),
        ]
    else:
        lines = [
            "Sentence as a JSON string:",
            json.dumps(source_text, ensure_ascii=False),
            f"Marked {target_kind} as a JSON string:",
            json.dumps(candidate.text, ensure_ascii=False),
            f"Text before the marked {target_kind} as a JSON string:",
            json.dumps(source_text[: candidate.start], ensure_ascii=False),
            f"Text after the marked {target_kind} as a JSON string:",
            json.dumps(source_text[candidate.end :], ensure_ascii=False),
        ]
    return ("\n".join(lines) + "\n").encode()


def _load_source_context(
    parent_id: str,
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
) -> tuple[_SourceContext, dict[str, str]]:
    grounding_payload = archive.read_hybrid_entity_grounding_preview(parent_id)
    grounding = hybrid_entity_grounding_preview_from_bytes(grounding_payload)
    if (
        grounding.id != parent_id
        or canonical_hybrid_entity_grounding_preview_bytes(grounding) != grounding_payload
    ):
        raise ValueError("Event-trigger parent HP-3 Preview identity or encoding is invalid.")
    reference_payload = archive.read_hybrid_reference_preview(grounding.parent_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    reference_digest = hashlib.sha256(reference_payload).hexdigest()
    if (
        references.id != grounding.parent_preview_id
        or reference_digest != grounding.parent_preview_sha256
    ):
        raise ValueError("Event-trigger HP-2 parent digest does not match HP-3 lineage.")
    mention_payload = archive.read_hybrid_extraction_preview(references.parent_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    mention_digest = hashlib.sha256(mention_payload).hexdigest()
    if (
        mentions.id != references.parent_preview_id
        or mentions.id != grounding.mention_preview_id
        or mention_digest != references.parent_preview_sha256
        or mention_digest != grounding.mention_preview_sha256
    ):
        raise ValueError("Event-trigger HP-1 parent digest does not match parent lineage.")
    if (
        len({grounding.representation_id, references.representation_id, mentions.representation_id})
        != 1
    ):
        raise ValueError("Event-trigger parent representation lineage is inconsistent.")
    if mentions.terminal_status is HybridPreviewStatus.BLOCKED:
        raise ValueError("Event-trigger discovery cannot consume a blocked HP-1 Preview.")
    bundle = ledger.get_document_representation_bundle(mentions.representation_id)
    if bundle is None:
        raise ValueError("Event-trigger parent references a missing representation.")
    manifest = load_context_manifest(mentions.context_manifest_id, ledger, verified_bundle=bundle)
    if manifest.representation_id != mentions.representation_id:
        raise ValueError("Event-trigger HP-1 ContextManifest lineage drifted.")
    node = next((item for item in bundle.nodes if item.id == mentions.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("Event-trigger parent paragraph is missing or invalid.")
    text_view = next((item for item in bundle.text_views if item.id == node.text_view_id), None)
    if text_view is None:
        raise ValueError("Event-trigger paragraph TextView is missing.")
    return (
        _SourceContext(
            bundle,
            mentions,
            references,
            grounding,
            text_view.text[node.start_char : node.end_char],
        ),
        {
            "grounding": hashlib.sha256(grounding_payload).hexdigest(),
            "references": reference_digest,
            "mentions": mention_digest,
        },
    )


def _build_manifest(
    *,
    unit: AnalysisUnit,
    profile: ContextModelProfile,
    prompt_id: str,
    renderer_version: str,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    ledger: HybridEventTriggerLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id=prompt_id,
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version=renderer_version,
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Event-trigger ContextManifest is not ready: "
            f"{planning.manifest.blocked_reason or planning.manifest.status.value}"
        )
    verify_context_manifest(
        planning.manifest.id,
        ledger,
        tokenizer,
        prompt_bytes,
        schema.canonical_schema_bytes,
    )
    return planning.manifest


def _execution_spec(
    manifest: ContextManifest,
    runtime: ModelTaskRuntime,
    generation: tuple[ExecutionSetting, ...],
    schema: PinnedTaskSchema,
    task_input: bytes,
) -> ModelExecutionSpec:
    rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=schema.schema_id,
        schema_digest=schema.digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
        output_contract_version=schema.output_contract_version,
    )


def _bounded_answer_generation_parameters(
    generation: tuple[ExecutionSetting, ...],
) -> tuple[ExecutionSetting, ...]:
    if sum(item.key == "max_output_tokens" for item in generation) != 1:
        raise ValueError("A bounded Event answer requires one max_output_tokens setting.")
    return tuple(
        ExecutionSetting(
            item.key,
            BOUNDED_ANSWER_MAX_OUTPUT_TOKENS if item.key == "max_output_tokens" else item.value,
        )
        for item in generation
    )


def _run_model_judgment(
    *,
    source_id: str,
    document_id: str,
    representation_id: str,
    manifest: ContextManifest,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_input: bytes,
    task_type: str,
    validator_version: str,
    generation_parameters: tuple[ExecutionSetting, ...],
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    registry: TaskSchemaRegistry,
) -> BoundedExtractionOutcome:
    return run_bounded_extraction(
        BoundedExtractionInput(
            source_id=source_id,
            document_id=document_id,
            representation_id=representation_id,
            context_manifest_id=manifest.id,
            prompt_bytes=prompt_bytes,
            execution_spec=_execution_spec(
                manifest,
                model_runtime,
                generation_parameters,
                schema,
                task_input,
            ),
            validator_version=validator_version,
            task_type=task_type,
            task_local_input=task_input,
        ),
        ledger,
        archive,
        model_runtime,
        model_run_id_factory,
        tokenizer,
        registry,
    )


def _resolve_trigger(
    decision: EventTriggerDecision,
    *,
    candidate: EventHeadCandidate,
    segment_id: str,
    source_text: str,
    source_copy: SourceCopyView,
    trace_id: str,
) -> EventTriggerDraft:
    if decision.answer is not EventHeadAnswerValue.EVENT:
        raise ValueError("Only an Event decision can resolve to an EventTriggerDraft.")
    event_type_label = _event_type_label(candidate.lemma)
    start, end = source_copy.authoritative_range(candidate.start, candidate.end)
    head_start, head_end = start, end
    text = source_text[start:end]
    head_text = source_text[head_start:head_end]
    if head_text != candidate.text or not start <= head_start < head_end <= end:
        raise ValueError("source_occurrence_mapping_drift")
    digest = hashlib.sha256(source_text.encode()).hexdigest()
    return EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id=segment_id,
            source_text_sha256=digest,
            start=start,
            end=end,
            text=text,
            head_start=head_start,
            head_end=head_end,
            head_text=head_text,
            event_type_label=event_type_label,
            extraction_task_id=decision.extraction_task_id,
            model_run_id=decision.model_run_id,
            trace_id=trace_id,
        ),
        source_segment_id=segment_id,
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        head_start=head_start,
        head_end=head_end,
        head_text=head_text,
        event_type_label=event_type_label,
        extraction_task_id=decision.extraction_task_id,
        model_run_id=decision.model_run_id,
        trace_id=trace_id,
    )


def _event_type_label(lemma: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", lemma.casefold()).strip("_")
    if not normalized or re.fullmatch(_EVENT_TYPE_LABEL, normalized) is None:
        return "event"
    return normalized


def _model_judgment_trace(
    *,
    trace_run_id: str,
    ordinal: int,
    route: EventSemanticRoute,
    source_segment_id: str,
    source_text: str,
    parent_trace_id: str,
    input_record_id: str,
    manifest: ContextManifest,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_input: bytes,
    candidate_binding: dict[str, JsonValue],
    other_binding: dict[str, JsonValue] | None,
    outcome: BoundedExtractionOutcome,
    parsed_answer: str | None,
) -> ExtractionStageTrace:
    succeeded = outcome.model_run.status is ModelRunStatus.SUCCEEDED and parsed_answer is not None
    rendered_input = manifest.rendered_input + b"\n\n[task]\n" + task_input
    raw_output = outcome.raw_model_output
    raw_output_text: str | None = None
    if raw_output is not None:
        try:
            raw_output_text = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            raw_output_text = None
    binding: dict[str, JsonValue] = {"candidate": candidate_binding}
    if other_binding is not None:
        binding["governing_verb"] = other_binding
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=ordinal,
        stage_id=f"event_{route.value}",
        stage_version=f"event_{route.value}_v1",
        producer_id="qwen2.5",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        input_record_ids=(input_record_id,),
        execution_record_ids=tuple(sorted((outcome.extraction_task.id, outcome.model_run.id))),
        configuration={
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "source_binding": binding,
            "model_visible_task": task_input.decode("utf-8"),
            "exact_model_input": rendered_input.decode("utf-8"),
            "exact_model_input_sha256": hashlib.sha256(rendered_input).hexdigest(),
        },
        output_payload={
            "model_run_id": outcome.model_run.id,
            "model_run_status": outcome.model_run.status.value,
            "raw_output_base64": (
                b64encode(raw_output).decode("ascii") if raw_output is not None else None
            ),
            "raw_output_text": raw_output_text,
            "raw_output_sha256": outcome.model_run.output_digest,
            "parsed_answer": parsed_answer,
        },
        status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
        diagnostics=() if succeeded else (f"event_{route.value}_failed",),
    )


def _linguistic_analysis_trace(
    *,
    trace_run_id: str,
    source_segment_id: str,
    source_text: str,
    source_copy: SourceCopyView,
    analysis: LinguisticAnalysis,
    input_record_id: str,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=0,
        stage_id="linguistic_analysis",
        stage_version=f"{analysis.model_id}:{analysis.model_version}",
        producer_id=analysis.producer_id,
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        input_record_ids=(input_record_id,),
        configuration={
            "model_id": analysis.model_id,
            "model_version": analysis.model_version,
            "resource_identity": analysis.resource_identity,
        },
        input_payload={"source_copy_text": source_copy.text},
        output_payload={
            "source_text_sha256": analysis.source_text_sha256,
            "tokens": [_linguistic_token_payload(item) for item in analysis.tokens],
        },
        status=ExtractionStageStatus.COMPLETED,
    )


def _nominalization_analysis_trace(
    *,
    trace_run_id: str,
    source_segment_id: str,
    source_text: str,
    analysis: NominalizationAnalysis,
    parent_trace_id: str,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=1,
        stage_id="nominalization_analysis",
        stage_version=analysis.model_revision,
        producer_id=analysis.producer_id,
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        configuration={
            "model_id": analysis.model_id,
            "model_revision": analysis.model_revision,
            "resource_identity": analysis.resource_identity,
            "threshold": analysis.threshold,
        },
        input_payload={"source_text": source_text},
        output_payload={
            "candidates": [_nominalization_candidate_payload(item) for item in analysis.candidates]
        },
        status=ExtractionStageStatus.COMPLETED,
    )


def _failed_specialist_trace(
    *,
    trace_run_id: str,
    source_segment_id: str,
    source_text: str,
    source_copy: SourceCopyView,
    occurrences: tuple[SourceOccurrence, ...],
    error: Exception,
    input_record_id: str,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=0,
        stage_id="event_candidate_analysis",
        stage_version=EVENT_HEAD_CANDIDATE_POLICY_ID,
        producer_id="kotekomi_application",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        input_record_ids=(input_record_id,),
        configuration={"policy_id": EVENT_HEAD_CANDIDATE_POLICY_ID},
        input_payload={
            "source_copy_text": source_copy.text,
            "source_occurrences": [_occurrence_payload(item) for item in occurrences],
        },
        output_payload={"error_type": type(error).__name__, "error": str(error)},
        status=ExtractionStageStatus.FAILED,
        diagnostics=("event_candidate_analysis_failed",),
    )


def _event_head_candidate_trace(
    *,
    trace_run_id: str,
    source_segment_id: str,
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
    selection: EventHeadCandidateSelection,
    parent_trace_ids: tuple[str, ...],
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=2,
        stage_id="event_head_candidate_selection",
        stage_version=selection.policy_id,
        producer_id="kotekomi_application",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        parent_trace_ids=tuple(sorted(parent_trace_ids)),
        configuration={"policy_id": selection.policy_id},
        input_payload={"source_occurrences": [_occurrence_payload(item) for item in occurrences]},
        output_payload={
            "candidates": [_event_head_candidate_payload(item) for item in selection.candidates],
            "dispositions": [
                cast(dict[str, JsonValue], item.model_dump(mode="json"))
                for item in selection.dispositions
            ],
        },
        status=ExtractionStageStatus.COMPLETED,
    )


def _trigger_reconciliation_trace(
    *,
    trace_run_id: str,
    source_segment_id: str,
    source_text: str,
    candidates: tuple[EventHeadCandidate, ...],
    reconciliation: EventTriggerDecisionReconciliation,
    parent_trace_ids: tuple[str, ...],
    ordinal: int,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=ordinal,
        stage_id="event_trigger_reconciliation",
        stage_version=TRIGGER_RECONCILIATION_POLICY_ID,
        producer_id="kotekomi_application",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        parent_trace_ids=tuple(sorted(parent_trace_ids)),
        configuration={"policy_id": TRIGGER_RECONCILIATION_POLICY_ID},
        input_payload={
            "event_head_candidates": [_event_head_candidate_payload(item) for item in candidates],
            "routing_judgments": [
                cast(dict[str, JsonValue], item.model_dump(mode="json"))
                for item in reconciliation.routing_judgments
            ],
        },
        output_payload={
            "event_decisions": [
                cast(dict[str, JsonValue], item.model_dump(mode="json"))
                for item in (*reconciliation.event_decisions, *reconciliation.non_event_decisions)
            ],
            "unclassified_occurrence_ids": list(reconciliation.unclassified_occurrence_ids),
            "dispositions": [
                cast(dict[str, JsonValue], item.model_dump(mode="json"))
                for item in reconciliation.dispositions
            ],
        },
        status=ExtractionStageStatus.COMPLETED,
    )


def _occurrence_payload(item: SourceOccurrence) -> dict[str, JsonValue]:
    return {
        "occurrence_id": item.occurrence_id,
        "text": item.text,
        "start": item.start,
        "end": item.end,
    }


def _linguistic_token_payload(token: LinguisticToken | None) -> dict[str, JsonValue]:
    if token is None:
        raise ValueError("A linguistic token payload requires one token.")
    return {
        "token_id": token.token_id,
        "sentence_id": token.sentence_id,
        "text": token.text,
        "start": token.start,
        "end": token.end,
        "lemma": token.lemma,
        "part_of_speech": token.part_of_speech.value,
        "dependency_relation": token.dependency_relation,
        "head_token_id": token.head_token_id,
    }


def _nominalization_candidate_payload(item: NominalizationCandidate) -> dict[str, JsonValue]:
    return {
        "linguistic_token_id": item.linguistic_token_id,
        "text": item.text,
        "start": item.start,
        "end": item.end,
        "lexical_candidate": item.lexical_candidate,
        "positive_logit": item.positive_logit,
        "negative_logit": item.negative_logit,
        "nominalization_probability": item.nominalization_probability,
    }


def _event_head_candidate_payload(item: EventHeadCandidate) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], item.model_dump(mode="json"))
