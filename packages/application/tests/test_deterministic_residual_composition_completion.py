"""Focused tests for the R19 residual composition completion use case."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    AssertionBlockReason,
    AssertionConstructionInputs,
    AssertionConstructionStatus,
    DecontextualizationAttributionKind,
    DecontextualizationEntityRef,
    DecontextualizationExclusion,
    DecontextualizationHoldReason,
    DecontextualizationRoleKind,
    DecontextualizationStatus,
    DecontextualizedAttribution,
    DecontextualizedProposition,
    DecontextualizedRole,
    EventEntityReferences,
    EventModality,
    EventPolarity,
    ReferencePolicyRecord,
    SourceRange,
    construct_inspectable_assertion,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
)
from kotekomi_application.deterministic_residual_composition_completion import (
    DeterministicResidualCompositionOutcome,
    DeterministicResidualCompositionStatus,
    complete_deterministic_residual_composition,
)
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    SourceAuthority,
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
            accepted_source_occurrences=(SourceRange(start=0, end=5, text="Sacks"),),
        ),
        DecontextualizationEntityRef(
            entity_id="EGE-020",
            entity_kind="actor",
            canonical_name="Amodei",
            accepted_source_occurrences=(SourceRange(start=13, end=19, text="Amodei"),),
        ),
    )


def _april_order_authorization() -> DecontextualizationExclusion:
    return DecontextualizationExclusion(
        exclusion_id="EGX-900",
        contextual_kind="non_entity_value",
        source_range=SourceRange(start=5, end=20, text="The April order"),
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


def test_ahe_022_holds_when_its_object_complement_is_unsupported(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    """AHE-022 keeps its hold: its object governs an acl clause."""
    record = next(item for item in policy_records if item.event_id == "AHE-022")
    provider = _FakeReferenceProvider(
        {
            "AHE-022": EventEntityReferences(
                entities=_sacks_entities(), subject_value_authorizations=()
            )
        }
    )
    outcome = _compose(record, provider)

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSITION_HELD
    assert outcome.references.entities == _sacks_entities()
    assert outcome.proposition is not None
    proposition = outcome.proposition
    assert proposition.status is DecontextualizationStatus.HELD
    assert proposition.hold_reason is DecontextualizationHoldReason.OBJECT_COMPLEMENT_UNSUPPORTED
    assert proposition.subject is None
    assert proposition.object is None


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

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSITION_HELD
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

    assert outcome.status is DeterministicResidualCompositionStatus.COMPOSITION_HELD
    assert outcome.proposition is not None
    assert outcome.proposition.status is DecontextualizationStatus.HELD
    assert outcome.proposition.hold_reason is DecontextualizationHoldReason.SELECTION_EMPTY


def _assertion_inputs(
    predicate_by_label: dict[str, str], identity_by_entity: dict[str, str]
) -> AssertionConstructionInputs:
    return AssertionConstructionInputs(
        predicate_by_label=predicate_by_label,
        identity_by_entity=identity_by_entity,
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_d97195ee5c8ced32c0cd41b0",
        evidence_target_id="etg_ahe_022",
        constructed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_assertion_construction_completes_for_ahe_051(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    """The supported AHE-051 proposition constructs one inspectable Assertion."""
    record = next(item for item in policy_records if item.event_id == "AHE-051")
    provider = _FakeReferenceProvider(
        {
            "AHE-051": EventEntityReferences(
                entities=(), subject_value_authorizations=(_april_order_authorization(),)
            )
        }
    )
    outcome = _compose(record, provider)
    assert outcome.proposition is not None

    result = construct_inspectable_assertion(
        outcome.proposition,
        _assertion_inputs(predicate_by_label={"is": "is"}, identity_by_entity={}),
    )

    assert result.status is AssertionConstructionStatus.CONSTRUCTED
    assert result.assertion is not None
    assert result.assertion.predicate == "is"


def test_assertion_construction_blocks_on_unresolved_subject_identity(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    """A valid proposition with an unmapped entity subject is blocked."""
    from kotekomi_application import DecontextualizedRole, SourceRange

    record = next(item for item in policy_records if item.event_id == "AHE-051")
    provider = _FakeReferenceProvider(
        {
            "AHE-051": EventEntityReferences(
                entities=(), subject_value_authorizations=(_april_order_authorization(),)
            )
        }
    )
    outcome = _compose(record, provider)
    proposition = outcome.proposition
    assert proposition is not None
    assert proposition.subject is not None
    proposition = proposition.model_copy(
        update={
            "subject": DecontextualizedRole(
                role=proposition.subject.role,
                exact_fragment=SourceRange(start=0, end=5, text="Alpha"),
                entity_ref="EGE-019",
            )
        }
    )

    result = construct_inspectable_assertion(
        proposition,
        _assertion_inputs(predicate_by_label={"is": "is"}, identity_by_entity={}),
    )

    assert result.status is AssertionConstructionStatus.BLOCKED
    assert result.assertion is None


def test_assertion_construction_blocks_on_unmapped_predicate(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    """A supported proposition without a reviewed predicate is blocked."""
    record = next(item for item in policy_records if item.event_id == "AHE-051")
    provider = _FakeReferenceProvider(
        {
            "AHE-051": EventEntityReferences(
                entities=(), subject_value_authorizations=(_april_order_authorization(),)
            )
        }
    )
    outcome = _compose(record, provider)
    assert outcome.proposition is not None

    result = construct_inspectable_assertion(
        outcome.proposition,
        _assertion_inputs(predicate_by_label={}, identity_by_entity={}),
    )

    assert result.status is AssertionConstructionStatus.BLOCKED
    assert result.assertion is None
    assert result.block_reason is AssertionBlockReason.UNMAPPED_PREDICATE


def test_assertion_construction_blocks_on_unmapped_reporter() -> None:
    proposition = DecontextualizedProposition(
        event_id="AHE-905",
        source_text_sha256="a" * 64,
        relation_label="urged",
        subject=DecontextualizedRole(
            role=DecontextualizationRoleKind.SUBJECT,
            exact_fragment=SourceRange(start=0, end=5, text="Tomas"),
            entity_ref="EGE-901",
        ),
        object=DecontextualizedRole(
            role=DecontextualizationRoleKind.OBJECT,
            exact_fragment=SourceRange(start=6, end=19, text="the agreement"),
            object_value="the agreement",
        ),
        polarity=EventPolarity.AFFIRMED,
        modality=EventModality.ACTUAL,
        attribution=DecontextualizedAttribution(
            kind=DecontextualizationAttributionKind.TARGETED,
            exact_carrier=SourceRange(start=20, end=24, text="Mira"),
            reporter_ref="EGE-902",
        ),
        status=DecontextualizationStatus.PROPOSITION,
    )

    result = construct_inspectable_assertion(
        proposition,
        _assertion_inputs(
            predicate_by_label={"urged": "urged"},
            identity_by_entity={"EGE-901": "act_tomas_fixture"},
        ),
    )

    assert result.status is AssertionConstructionStatus.BLOCKED
    assert result.assertion is None
    assert result.block_reason is AssertionBlockReason.UNRESOLVED_REPORTER
