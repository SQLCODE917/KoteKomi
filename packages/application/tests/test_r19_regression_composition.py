"""R19 per-Event composition regressions for AHE-901 through AHE-909 (TDD §5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    DecontextualizationAttributionKind,
    DecontextualizationEntityRef,
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DeterministicResidualCompositionOutcome,
    EventEntityReferences,
    EventModality,
    EventPolarity,
    ReferencePolicyRecord,
    complete_deterministic_residual_composition,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data/r17-semantic-selection-contract"


class _Provider:
    def __init__(self, references: EventEntityReferences) -> None:
        self._references = references

    def resolve_references(
        self, event_id: str, source_text: str, source_text_sha256: str
    ) -> EventEntityReferences:
        del event_id, source_text, source_text_sha256
        return self._references


def _span(text: str, value: str, start: int = 0) -> tuple[int, int, str]:
    index = text.index(value, start)
    return (index, index + len(value), value)


def _ref(entity_id: str, name: str, *spans: tuple[int, int, str]) -> DecontextualizationEntityRef:
    return DecontextualizationEntityRef(
        entity_id=entity_id,
        entity_kind="actor",
        canonical_name=name,
        accepted_source_occurrences=tuple(
            AttachmentSourceRange(start=start, end=end, text=value) for start, end, value in spans
        ),
    )


def _references(*refs: DecontextualizationEntityRef) -> EventEntityReferences:
    return EventEntityReferences(entities=tuple(refs), subject_value_authorizations=())


@pytest.fixture(scope="module")
def records() -> dict[str, ReferencePolicyRecord]:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    return {
        item.event_id: item
        for item in load_reference_policy_records(contract=contract, directory=DATA_DIR)
    }


def _run(
    record: ReferencePolicyRecord, references: EventEntityReferences
) -> DeterministicResidualCompositionOutcome:
    return complete_deterministic_residual_composition(
        event_id=record.event_id,
        source_text=record.source_text,
        source_text_sha256=record.input_binding.source_sha256,
        inventory=record.inventory,
        trigger_head_start=record.frame.trigger.start,
        trigger_head_end=record.frame.trigger.end,
        tokens=record.composition_tokens,
        provider=_Provider(references),
    )


def _selected(outcome: DeterministicResidualCompositionOutcome) -> tuple[str, ...]:
    answer = outcome.selection.answer
    if answer is None:
        return ()
    return tuple(f"C{index}" for index in answer.selected_label_indexes)


def test_ahe_901_composes_subject_and_object(
    records: dict[str, ReferencePolicyRecord],
) -> None:
    record = records["AHE-901"]
    text = record.source_text
    refs = _references(
        _ref("EGE-101", "Mira", _span(text, "Mira")),
        _ref("EGE-102", "Tomas", _span(text, "Tomas")),
    )
    outcome = _run(record, refs)

    assert _selected(outcome) == ("C1", "C2")
    proposition = outcome.proposition
    assert proposition is not None
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None and proposition.subject.entity_ref == "EGE-101"
    assert proposition.object is not None and proposition.object.entity_ref == "EGE-102"
    assert proposition.polarity is EventPolarity.AFFIRMED
    assert proposition.modality is EventModality.ACTUAL
    assert proposition.attribution is not None
    assert proposition.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_ahe_902_holds_unsupported_time_place(records: dict[str, ReferencePolicyRecord]) -> None:
    outcome = _run(records["AHE-902"], _references())

    assert _selected(outcome) == ("C1",)
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.UNSUPPORTED_TIME_PLACE


def test_ahe_903_composes_negated_hypothetical(records: dict[str, ReferencePolicyRecord]) -> None:
    record = records["AHE-903"]
    refs = _references(_ref("EGE-103", "Mira", _span(record.source_text, "Mira")))
    outcome = _run(record, refs)

    assert _selected(outcome) == ("C1", "C4")
    proposition = outcome.proposition
    assert proposition is not None
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None and proposition.subject.entity_ref == "EGE-103"
    assert proposition.object is not None and proposition.object.object_value == "the agreement"
    assert proposition.polarity is EventPolarity.NEGATED
    assert proposition.modality is EventModality.HYPOTHETICAL
    assert proposition.attribution is not None
    assert proposition.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_ahe_904_holds_unsupported_coordination(
    records: dict[str, ReferencePolicyRecord],
) -> None:
    outcome = _run(records["AHE-904"], _references())

    assert _selected(outcome) == ("C1", "C2", "C3")
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.UNSUPPORTED_COORDINATION


def test_ahe_905_composes_targeted_attribution(
    records: dict[str, ReferencePolicyRecord],
) -> None:
    record = records["AHE-905"]
    text = record.source_text
    refs = _references(
        _ref("EGE-105", "Mira", _span(text, "Mira")),
        _ref("EGE-106", "Tomas", _span(text, "Tomas")),
    )
    outcome = _run(record, refs)

    assert _selected(outcome) == ("C3", "C4")
    proposition = outcome.proposition
    assert proposition is not None
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None and proposition.subject.entity_ref == "EGE-106"
    assert proposition.object is not None and proposition.object.object_value == "the agreement"
    assert proposition.attribution is not None
    assert proposition.attribution.kind is DecontextualizationAttributionKind.TARGETED
    assert proposition.attribution.reporter_ref == "EGE-105"


def test_ahe_906_composes_compound_subject(
    records: dict[str, ReferencePolicyRecord],
) -> None:
    record = records["AHE-906"]
    refs = _references(_ref("EGE-107", "Mira Chen", _span(record.source_text, "Mira Chen")))
    outcome = _run(record, refs)

    assert _selected(outcome) == ("C4", "C6")
    proposition = outcome.proposition
    assert proposition is not None
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None
    assert proposition.subject.entity_ref == "EGE-107"
    assert proposition.subject.exact_fragment.text == "Mira Chen"
    assert proposition.object is not None and proposition.object.object_value == "the agreement"


def test_ahe_907_composes_repeated_name(records: dict[str, ReferencePolicyRecord]) -> None:
    record = records["AHE-907"]
    text = record.source_text
    first = _span(text, "Mira")
    second = _span(text, "Mira", first[1])
    refs = _references(_ref("EGE-108", "Mira", first, second))
    outcome = _run(record, refs)

    assert _selected(outcome) == ("C1", "C2")
    proposition = outcome.proposition
    assert proposition is not None
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None and proposition.subject.entity_ref == "EGE-108"
    assert proposition.object is not None and proposition.object.entity_ref == "EGE-108"


def test_ahe_908_holds_selection_empty(records: dict[str, ReferencePolicyRecord]) -> None:
    outcome = _run(records["AHE-908"], _references())

    assert _selected(outcome) == ()
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.SELECTION_EMPTY


def test_ahe_909_holds_subject_unavailable(records: dict[str, ReferencePolicyRecord]) -> None:
    outcome = _run(records["AHE-909"], _references())

    assert _selected(outcome) == ("C1", "C2")
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE
