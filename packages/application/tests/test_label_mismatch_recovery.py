"""Focused data-in/data-out tests for R12 label-mismatch recovery."""

from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
    DecontextualizationAttributionKind,
    DecontextualizationEntityRef,
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    EventModality,
    EventPolarity,
    LabelMismatchRecoveryHalt,
    ParserConstituent,
    SelectionFailureSlot,
    build_label_mismatch_recovery,
    build_label_mismatch_recovery_report,
    label_mismatch_recovery_report_fingerprint,
    parser_constituent_id,
    recover_label_mismatch,
    remeasure_recovered_selection,
)

AHE004_RAW = (
    "C1,E2\n\nWhere E2 is presumed to be a mislabeling in the instruction and should refer to "
    'C2, as the candidates provided do not include an "E2" label. Thus, the relevant parts of the '
    'passage are "Efforts" and "under the term of Secretary Ash Carter", which correspond to C1 '
    "and C2 respectively."
)
AHE022_RAW = (
    "Sacks, Amodei's decision, to attend the World Economic Forum over Trump's second "
    "inauguration; his hiring of Biden officials; and Anthropic's association with the "
    "philanthropic initiative Open Philanthropy as evidence, Trump's, second inauguration, his "
    "hiring of Biden officials, Anthropic's association with the philanthropic initiative Open "
    "Philanthropy as evidence, that Anthropic would not support Trump's agenda"
)
AHE051_RAW = "NONE"

AHE004_SOURCE = "Efforts intensified."


def _task(event_id: str, labels: tuple[str, ...]) -> ConstituentSelectionTask:
    source_text = "candidate source text"
    rendered = "Event: test\nCandidates:\n" + "\n".join(f"{label}: sample" for label in labels)
    return ConstituentSelectionTask(
        event_id=event_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        source_text=source_text,
        constituent_labels=labels,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
    )


def _token(
    token_id: str,
    text: str,
    start: int,
    end: int,
    lemma: str,
    dependency_relation: str,
    head_token_id: str | None,
) -> EventEntityLinguisticToken:
    return EventEntityLinguisticToken(
        token_id=token_id,
        sentence_id="s1",
        text=text,
        start=start,
        end=end,
        lemma=lemma,
        part_of_speech="NOUN",
        dependency_relation=dependency_relation,
        head_token_id=head_token_id,
    )


def _remeasure_fixture() -> tuple[
    ConstituentSelectionTask, tuple[EventEntityLinguisticToken, ...], ConstituentCandidateInventory
]:
    tokens = (
        _token("t1", "Efforts", 0, 7, "effort", "nsubj", "t2"),
        _token("t2", "intensified", 8, 19, "intensify", "root", None),
    )
    digest = hashlib.sha256(AHE004_SOURCE.encode()).hexdigest()
    constituent = ParserConstituent(
        constituent_id=parser_constituent_id(digest, 0, 7),
        event_id="AHE-004",
        source_text_sha256=digest,
        constituent_range=AttachmentSourceRange(start=0, end=7, text="Efforts"),
        token_ids=("t1",),
    )
    inventory = ConstituentCandidateInventory(
        event_id="AHE-004",
        source_text_sha256=digest,
        constituents=(constituent,),
    )
    return _task("AHE-004", ("C1",)), tokens, inventory


def _remeasure(
    *, entities: tuple[DecontextualizationEntityRef, ...] = ()
) -> DecontextualizedProposition:
    task, tokens, inventory = _remeasure_fixture()
    recovered = recover_label_mismatch(raw_answer="C1, E2", task=task)
    return remeasure_recovered_selection(
        recovered=recovered,
        source_text=AHE004_SOURCE,
        source_text_sha256=inventory.source_text_sha256,
        inventory=inventory,
        trigger_head_start=8,
        trigger_head_end=19,
        tokens=tokens,
        entities=entities,
    )


def test_frozen_ahe004_answer_recovers_to_index_one() -> None:
    recovered = recover_label_mismatch(
        raw_answer=AHE004_RAW, task=_task("AHE-004", ("C1", "C2", "C3"))
    )
    assert recovered.event_id == "AHE-004"
    assert recovered.status is ConstituentSelectionStatus.SELECTED
    assert recovered.selected_label_indexes == (1,)


def test_recovery_keeps_valid_labels_and_drops_foreign_tokens() -> None:
    recovered = recover_label_mismatch(
        raw_answer="C1, E2, C3", task=_task("AHE-004", ("C1", "C2", "C3"))
    )
    assert recovered.selected_label_indexes == (1, 3)


def test_recovery_orders_kept_labels_by_task_order_and_distinct() -> None:
    recovered = recover_label_mismatch(
        raw_answer="C3, C1, C1, E2", task=_task("AHE-004", ("C1", "C2", "C3"))
    )
    assert recovered.selected_label_indexes == (1, 3)


def test_recovery_halt_for_rejection_no_valid_label() -> None:
    with pytest.raises(LabelMismatchRecoveryHalt) as exc:
        recover_label_mismatch(raw_answer=AHE022_RAW, task=_task("AHE-004", ("C1", "C2", "C3")))
    assert exc.value.slot is SelectionFailureSlot.REJECTION_NO_VALID_LABEL


def test_recovery_halt_for_abstained() -> None:
    with pytest.raises(LabelMismatchRecoveryHalt) as exc:
        recover_label_mismatch(raw_answer=AHE051_RAW, task=_task("AHE-004", ("C1", "C2", "C3")))
    assert exc.value.slot is SelectionFailureSlot.ABSTAINED


def test_recovery_halt_for_rejection_empty() -> None:
    with pytest.raises(LabelMismatchRecoveryHalt) as exc:
        recover_label_mismatch(raw_answer="", task=_task("AHE-004", ("C1", "C2", "C3")))
    assert exc.value.slot is SelectionFailureSlot.REJECTION_EMPTY


def test_recovery_halt_for_selected() -> None:
    with pytest.raises(LabelMismatchRecoveryHalt) as exc:
        recover_label_mismatch(raw_answer="C1, C3", task=_task("AHE-004", ("C1", "C2", "C3")))
    assert exc.value.slot is SelectionFailureSlot.SELECTED


def test_nonrecoverable_events_never_produce_completed_selection() -> None:
    for raw_answer in (AHE022_RAW, AHE051_RAW):
        with pytest.raises(LabelMismatchRecoveryHalt):
            recover_label_mismatch(raw_answer=raw_answer, task=_task("AHE-004", ("C1", "C2", "C3")))


def test_recovered_selection_remeasures_to_one_decontextualized_proposition() -> None:
    result = _remeasure()
    assert isinstance(result, DecontextualizedProposition)
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE


def test_recovery_hold_carries_typed_reason_and_zero_content() -> None:
    result = _remeasure()
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE
    assert result.relation_label is None
    assert result.subject is None
    assert result.object is None
    assert result.polarity is None
    assert result.modality is None
    assert result.attribution is None


def test_recovered_selection_remeasures_to_proposition_with_resolved_entity() -> None:
    entities = (
        DecontextualizationEntityRef(
            entity_id="EGE-001",
            entity_kind="actor",
            canonical_name="Efforts",
            accepted_source_occurrences=(AttachmentSourceRange(start=0, end=7, text="Efforts"),),
        ),
    )
    result = _remeasure(entities=entities)
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.relation_label == "intensify"
    assert result.polarity is EventPolarity.AFFIRMED
    assert result.modality is EventModality.ACTUAL
    assert result.attribution is not None
    assert result.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_report_records_zero_writes_and_seals_fingerprint() -> None:
    recovery = build_label_mismatch_recovery(
        recovered=recover_label_mismatch(raw_answer="C1, E2", task=_task("AHE-004", ("C1",))),
        raw_answer="C1, E2",
        remeasured=_remeasure(),
    )
    report = build_label_mismatch_recovery_report(recoveries=(recovery,))
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == label_mismatch_recovery_report_fingerprint(report)


def test_report_fingerprint_changes_when_recovery_changes() -> None:
    held = _remeasure()
    entities = (
        DecontextualizationEntityRef(
            entity_id="EGE-001",
            entity_kind="actor",
            canonical_name="Efforts",
            accepted_source_occurrences=(AttachmentSourceRange(start=0, end=7, text="Efforts"),),
        ),
    )
    proposition = _remeasure(entities=entities)
    recovered = recover_label_mismatch(raw_answer="C1, E2", task=_task("AHE-004", ("C1",)))
    report_a = build_label_mismatch_recovery_report(
        recoveries=(
            build_label_mismatch_recovery(
                recovered=recovered, raw_answer="C1, E2", remeasured=held
            ),
        )
    )
    report_b = build_label_mismatch_recovery_report(
        recoveries=(
            build_label_mismatch_recovery(
                recovered=recovered, raw_answer="C1, E2", remeasured=proposition
            ),
        )
    )
    assert report_a.result_fingerprint != report_b.result_fingerprint
