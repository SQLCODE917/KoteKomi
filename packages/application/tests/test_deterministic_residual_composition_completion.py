"""Focused tests for the R19 residual composition completion use case."""

from __future__ import annotations

from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    DecontextualizationAttributionKind,
    DecontextualizationEntityRef,
    DecontextualizationExclusion,
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DeterministicResidualCompositionOutcome,
    DeterministicResidualCompositionStatus,
    EventEntityReferences,
    EventModality,
    EventPolarity,
    ReferencePolicyRecord,
    complete_deterministic_residual_composition,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data/r17-semantic-selection-contract"


class _FakeReferenceProvider:
    """An in-memory provider that returns one Event's reviewed references."""

    def __init__(self, references_by_event: dict[str, EventEntityReferences]) -> None:
        self._references = references_by_event

    def resolve_references(
        self, event_id: str, source_text: str, source_text_sha256: str
    ) -> EventEntityReferences:
        del source_text, source_text_sha256
        return self._references[event_id]


def _sacks_entities() -> tuple[DecontextualizationEntityRef, ...]:
    return (
        DecontextualizationEntityRef(
            entity_id="EGE-019",
            entity_kind="actor",
            canonical_name="Sacks",
            accepted_source_occurrences=(AttachmentSourceRange(start=0, end=5, text="Sacks"),),
        ),
        DecontextualizationEntityRef(
            entity_id="EGE-020",
            entity_kind="actor",
            canonical_name="Amodei",
            accepted_source_occurrences=(AttachmentSourceRange(start=13, end=19, text="Amodei"),),
        ),
    )


def _april_order_authorization() -> DecontextualizationExclusion:
    return DecontextualizationExclusion(
        exclusion_id="EGX-900",
        contextual_kind="non_entity_value",
        source_range=AttachmentSourceRange(start=5, end=20, text="The April order"),
        rationale="A date-scoped nominal order, not an Actor or Organization.",
    )


@pytest.fixture(scope="module")
def policy_records() -> tuple[ReferencePolicyRecord, ...]:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    return load_reference_policy_records(contract=contract, directory=DATA_DIR)


def _compose(
    record: ReferencePolicyRecord, provider: _FakeReferenceProvider
) -> DeterministicResidualCompositionOutcome:
    return complete_deterministic_residual_composition(
        event_id=record.event_id,
        source_text=record.source_text,
        source_text_sha256=record.input_binding.source_sha256,
        inventory=record.inventory,
        trigger_head_start=record.frame.trigger.start,
        trigger_head_end=record.frame.trigger.end,
        tokens=record.composition_tokens,
        provider=provider,
    )


def test_ahe_022_composes_subject_entity_and_object(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    record = next(item for item in policy_records if item.event_id == "AHE-022")
    provider = _FakeReferenceProvider(
        {
            "AHE-022": EventEntityReferences(
                entities=_sacks_entities(), subject_value_authorizations=()
            )
        }
    )
    outcome = _compose(record, provider)

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSED
    assert outcome.references.entities == _sacks_entities()
    assert outcome.proposition is not None
    proposition = outcome.proposition
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None
    assert proposition.subject.exact_fragment.text == "Sacks"
    assert proposition.subject.entity_ref == "EGE-019"
    assert proposition.object is not None
    assert proposition.object.exact_fragment.text == "Amodei's decision"
    assert proposition.polarity is EventPolarity.AFFIRMED
    assert proposition.modality is EventModality.ACTUAL
    assert proposition.attribution is not None
    assert proposition.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_ahe_051_composes_subject_value_and_copular_object(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    record = next(item for item in policy_records if item.event_id == "AHE-051")
    provider = _FakeReferenceProvider(
        {
            "AHE-051": EventEntityReferences(
                entities=(), subject_value_authorizations=(_april_order_authorization(),)
            )
        }
    )
    outcome = _compose(record, provider)

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSED
    assert outcome.proposition is not None
    proposition = outcome.proposition
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    assert proposition.subject is not None
    assert proposition.subject.subject_value == "The April order"
    assert proposition.relation_label == "is"
    assert proposition.object is not None
    assert proposition.object.object_value == "final"
    assert proposition.polarity is EventPolarity.NEGATED
    assert proposition.modality is EventModality.ACTUAL
    assert proposition.attribution is not None
    assert proposition.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_unresolved_subject_holds_without_a_fabricated_reference(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    """An Actor subject with no accepted reference must not become a value."""
    record = next(item for item in policy_records if item.event_id == "AHE-022")
    provider = _FakeReferenceProvider(
        {"AHE-022": EventEntityReferences(entities=(), subject_value_authorizations=())}
    )
    outcome = _compose(record, provider)

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSED
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE


def test_none_selection_holds_with_selection_empty(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    record = next(item for item in policy_records if item.event_id == "AHE-908")
    provider = _FakeReferenceProvider(
        {"AHE-908": EventEntityReferences(entities=(), subject_value_authorizations=())}
    )
    outcome = _compose(record, provider)

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSED
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.SELECTION_EMPTY
