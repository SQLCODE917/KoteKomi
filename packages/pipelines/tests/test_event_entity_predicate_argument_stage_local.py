from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    EventEntityCandidateSelection,
    EventEntityDenotationDecision,
    EventEntityDenotationRule,
    EventEntityKind,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    EventTriggerDraft,
    build_source_grounded_event_draft,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id
from kotekomi_pipelines.evaluation_contracts import EvaluationPhase
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldCatalog,
    ConnectionGoldEntity,
    ConnectionGoldEvent,
    ConnectionGoldSourceOccurrence,
    EventEntityExperimentInput,
)
from kotekomi_pipelines.event_entity_predicate_argument_stage_local import (
    PredicateArgumentComparison,
    build_predicate_argument_diagnostic_report,
    evaluate_predicate_argument_event,
    predicate_argument_summary,
    render_predicate_argument_review,
)


def test_event_evaluation_separates_structural_match_from_structural_extra() -> None:
    prepared = _prepared(include_stargate=True)
    gold = _gold_event("TGE-900", "EGE-900", phase="development")

    result = evaluate_predicate_argument_event(gold, prepared)

    assert result.structurally_matched_entity_ids == ("EGE-900",)
    assert result.semantic_remainder_entity_ids == ()
    assert result.missing_candidate_entity_ids == ()
    assert [item.comparison for item in result.candidates] == [
        PredicateArgumentComparison.STRUCTURAL_MATCH,
        PredicateArgumentComparison.STRUCTURAL_EXTRA,
    ]
    assert all(item.observation.path_tokens for item in result.candidates)


def test_complete_40_case_report_is_model_free_stable_and_reviewable() -> None:
    base = _prepared(include_stargate=False)
    events: list[ConnectionGoldEvent] = []
    inputs: list[EventEntityExperimentInput] = []
    for index in range(40):
        event_id = f"TGE-{100 + index:03d}"
        entity_id = f"EGE-{100 + index:03d}"
        phase = "development" if index < 20 else "validation"
        events.append(_gold_event(event_id, entity_id, phase=phase))
        inputs.append(base.model_copy(update={"gold_event_id": event_id, "phase": phase}))
    catalog = ConnectionGoldCatalog(
        catalog_id="predicate-argument-fixture-v1",
        review_status="approved",
        trigger_gold_path="docs/trigger.json",
        trigger_gold_sha256="1" * 64,
        source_grounded_gold_path="docs/source-grounded.json",
        source_grounded_gold_sha256="2" * 64,
        events=tuple(events),
    )

    first = build_predicate_argument_diagnostic_report(
        catalog=catalog,
        catalog_sha256="3" * 64,
        inputs=tuple(inputs),
    )
    second = build_predicate_argument_diagnostic_report(
        catalog=catalog,
        catalog_sha256="3" * 64,
        inputs=tuple(reversed(inputs)),
    )

    assert first.passed is True
    assert first.routing_hypothesis_supported is True
    assert first.model_execution_count == 0
    assert first.accepted_ledger_change_count == 0
    assert first.development.event_count == 20
    assert first.validation.event_count == 20
    assert first.development.structural_match_count == 20
    assert first.validation.structural_match_count == 20
    development_metrics = {
        item.hypothesis.value: item for item in first.development.hypothesis_metrics
    }
    validation_metrics = {
        item.hypothesis.value: item for item in first.validation.hypothesis_metrics
    }
    assert development_metrics["direct_argument"].candidate_count == 20
    assert development_metrics["direct_argument"].precision == 1.0
    assert validation_metrics["direct_argument"].candidate_count == 20
    assert validation_metrics["direct_argument"].precision == 1.0
    assert first.result_fingerprint == second.result_fingerprint
    assert first.model_dump(mode="json") == second.model_dump(mode="json")

    review = render_predicate_argument_review(first)
    summary = predicate_argument_summary(first)
    assert "Exact SourceSegment" in review
    assert "Exact Event head" in review
    assert "Actual hypothesis: `direct_argument`" in review
    assert summary["model_execution_count"] == 0
    assert summary["accepted_ledger_change_count"] == 0


def test_diagnostic_requires_approved_complete_gold() -> None:
    prepared = _prepared(include_stargate=False)
    events = tuple(
        _gold_event(
            f"TGE-{100 + index:03d}",
            f"EGE-{100 + index:03d}",
            phase="development" if index < 20 else "validation",
        )
        for index in range(40)
    )
    catalog = ConnectionGoldCatalog(
        catalog_id="predicate-argument-fixture-v1",
        review_status="proposed",
        trigger_gold_path="docs/trigger.json",
        trigger_gold_sha256="1" * 64,
        source_grounded_gold_path="docs/source-grounded.json",
        source_grounded_gold_sha256="2" * 64,
        events=events,
    )

    with pytest.raises(ValueError, match="approved Gold"):
        build_predicate_argument_diagnostic_report(
            catalog=catalog,
            catalog_sha256="3" * 64,
            inputs=tuple(
                prepared.model_copy(update={"gold_event_id": item.event_id, "phase": item.phase})
                for item in events
            ),
        )


def _prepared(*, include_stargate: bool) -> EventEntityExperimentInput:
    source = "Anthropic criticized Stargate."
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    trigger_start = source.index("criticized")
    trigger_end = trigger_start + len("criticized")
    trigger_trace_id = "xst_" + "1" * 24
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id="seg_predicate_pipeline_fixture",
            source_text_sha256=source_digest,
            start=trigger_start,
            end=trigger_end,
            text="criticized",
            head_start=trigger_start,
            head_end=trigger_end,
            head_text="criticized",
            event_type_label="source_grounded",
            extraction_task_id="ext_predicate_pipeline_fixture",
            model_run_id="mrn_predicate_pipeline_fixture",
            trace_id=trigger_trace_id,
        ),
        source_segment_id="seg_predicate_pipeline_fixture",
        source_text_sha256=source_digest,
        start=trigger_start,
        end=trigger_end,
        text="criticized",
        head_start=trigger_start,
        head_end=trigger_end,
        head_text="criticized",
        event_type_label="source_grounded",
        extraction_task_id="ext_predicate_pipeline_fixture",
        model_run_id="mrn_predicate_pipeline_fixture",
        trace_id=trigger_trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "2" * 24,
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        expression_text=trigger.text,
        head_text=trigger.head_text,
        head_evidence_target_id="etg_" + "3" * 24,
        expression_evidence_target_id="etg_" + "4" * 24,
        support_evidence_target_id="etg_" + "5" * 24,
    )
    mention_texts = ("Anthropic", "Stargate") if include_stargate else ("Anthropic",)
    mentions: list[EventEntityMentionInput] = []
    denotations: list[EventEntityDenotationDecision] = []
    for ordinal, text in enumerate(mention_texts, start=1):
        start = source.index(text)
        mention_id = "mnc_" + str(ordinal) * 24
        span_values = (
            event.source_segment_id,
            source_digest,
            str(start),
            str(start + len(text)),
            text,
            mention_id,
            "",
        )
        span = EventEntitySourceSpan(
            id="ees_" + hashlib.sha256(chr(31).join(span_values).encode()).hexdigest()[:24],
            source_segment_id=event.source_segment_id,
            source_text_sha256=source_digest,
            start=start,
            end=start + len(text),
            text=text,
            mention_candidate_id=mention_id,
        )
        evidence_id = "mob_" + str(ordinal + 2) * 24
        interpretation_id = "mit_" + str(ordinal + 4) * 24
        denotation_values = (
            mention_id,
            EventEntityKind.ORGANIZATION.value,
            text,
            EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND.value,
            interpretation_id,
            evidence_id,
        )
        denotation = EventEntityDenotationDecision(
            id="edd_" + hashlib.sha256(chr(31).join(denotation_values).encode()).hexdigest()[:24],
            mention_candidate_id=mention_id,
            entity_kind=EventEntityKind.ORGANIZATION,
            entity_name=text,
            rule_id=EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND,
            source_evidence_ids=(evidence_id,),
            mention_interpretation_id=interpretation_id,
        )
        denotations.append(denotation)
        mentions.append(
            EventEntityMentionInput(
                entity_identity="organization:" + text.casefold(),
                entity_kind=EventEntityKind.ORGANIZATION,
                entity_name=text,
                denotation_decision_id=denotation.id,
                source_span=span,
            )
        )
    evidence = EventEntityLinguisticEvidence(
        trace_id="xst_" + "8" * 24,
        source_segment_id=event.source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="9" * 64,
        tokens=(
            EventEntityLinguisticToken(
                token_id="t1",
                sentence_id="s1",
                text="Anthropic",
                start=0,
                end=9,
                lemma="anthropic",
                part_of_speech="PROPN",
                dependency_relation="nsubj",
                head_token_id="t2",
            ),
            EventEntityLinguisticToken(
                token_id="t2",
                sentence_id="s1",
                text="criticized",
                start=10,
                end=20,
                lemma="criticize",
                part_of_speech="VERB",
                dependency_relation="root",
            ),
            EventEntityLinguisticToken(
                token_id="t3",
                sentence_id="s1",
                text="Stargate",
                start=21,
                end=29,
                lemma="stargate",
                part_of_speech="PROPN",
                dependency_relation="obj",
                head_token_id="t2",
            ),
            EventEntityLinguisticToken(
                token_id="t4",
                sentence_id="s1",
                text=".",
                start=29,
                end=30,
                lemma=".",
                part_of_speech="PUNCT",
                dependency_relation="punct",
                head_token_id="t2",
            ),
        ),
    )
    return EventEntityExperimentInput(
        phase="development",
        gold_event_id="TGE-900",
        source_id="src_predicate_fixture",
        document_id="doc_predicate_fixture",
        representation_id="rep_predicate_fixture",
        paragraph_node_id="nod_predicate_fixture",
        source_segment_label="segment-1",
        source_text=source,
        event_semantics_preview_id="hsp_" + "6" * 24,
        event_semantics_preview_sha256="7" * 64,
        trigger=trigger,
        event=event,
        candidate_selection=EventEntityCandidateSelection(
            mentions=tuple(mentions),
            denotation_decisions=tuple(denotations),
            gaps=(),
            gap_dependencies=(),
        ),
        linguistic_evidence=evidence,
    )


def _gold_event(
    event_id: str,
    entity_id: str,
    *,
    phase: EvaluationPhase,
) -> ConnectionGoldEvent:
    source = "Anthropic criticized Stargate."
    return ConnectionGoldEvent(
        event_id=event_id,
        phase=phase,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        event_meaning="Anthropic criticized Stargate.",
        expected_entities=(
            ConnectionGoldEntity(
                entity_id=entity_id,
                entity_kind=EventEntityKind.ORGANIZATION,
                canonical_name="Anthropic",
                accepted_entity_names=("Anthropic",),
                accepted_source_occurrences=(
                    ConnectionGoldSourceOccurrence(
                        start=0,
                        end=9,
                        source_text="Anthropic",
                    ),
                ),
                rationale="Anthropic performs the criticism.",
            ),
        ),
        review_rationale="Synthetic predicate-argument fixture.",
    )
