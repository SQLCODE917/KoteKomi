"""Deterministic residual composition completion use case (R19).

This coordinating use case composes three model-free operations for one residual
Event:

1. the deterministic source-grounded selector, which derives one
   ``ConstituentSelectionAnswer`` from the trigger-head dependents only;
2. the ``EventEntityReferenceProvider`` Port, which resolves accepted Actor and
   Organization references and reviewed subject-value exclusions; and
3. the deterministic composer, which assembles one ``DecontextualizedProposition``.

The use case — not the composer — calls the Port and passes validated references
into the composer. A boundary-gap selection halts with a typed partial outcome
instead of a composed proposition. R19 executes no model, writes no canonical
state, and records no proposed change.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    SourceAuthority,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.decontextualization_composition import (
    DecontextualizationAttributionKind,
    DecontextualizationStatus,
    DecontextualizedProposition,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.event_entity_reference_provider import (
    EventEntityReferenceProvider,
    EventEntityReferences,
)
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
)
from kotekomi_application.source_grounded_selection import (
    SourceGroundedSelectionResult,
    SourceGroundedSelectionStatus,
    select_source_grounded_constituents,
)

_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]


class DeterministicResidualCompositionStatus(StrEnum):
    """Terminal state of one deterministic residual composition completion."""

    COMPOSED = "composed"
    COMPOSITION_HELD = "composition_held"
    SELECTION_GAP = "selection_gap"


class DeterministicResidualCompositionOutcome(BaseModel):
    """One residual Event's production selection and composed proposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    status: DeterministicResidualCompositionStatus
    selection: SourceGroundedSelectionResult
    references: EventEntityReferences
    proposition: DecontextualizedProposition | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is DeterministicResidualCompositionStatus.COMPOSED:
            if (
                self.proposition is None
                or self.proposition.status is not DecontextualizationStatus.PROPOSITION
            ):
                raise ValueError("A composed outcome requires a proposition, not a held result.")
        elif self.status is DeterministicResidualCompositionStatus.COMPOSITION_HELD:
            if (
                self.proposition is None
                or self.proposition.status is not DecontextualizationStatus.HELD
            ):
                raise ValueError(
                    "A composition-held outcome requires a held proposition with a hold reason."
                )
        elif self.proposition is not None:
            raise ValueError("A selection-gap outcome cannot carry a proposition.")
        return self


def complete_deterministic_residual_composition(
    *,
    event_id: str,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    provider: EventEntityReferenceProvider,
) -> DeterministicResidualCompositionOutcome:
    """Complete one residual Event's selection and composition through the Port.

    The selection runs first; the provider runs second so a selection gap never
    hides a missing reference, and the composer runs last with validated
    references it never looks up itself.
    """
    selection = select_source_grounded_constituents(
        event_id=event_id,
        source_text=source_text,
        inventory=inventory,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
    )
    references = provider.resolve_references(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
    )
    if selection.status is SourceGroundedSelectionStatus.BOUNDARY_GAP:
        return DeterministicResidualCompositionOutcome(
            event_id=event_id,
            status=DeterministicResidualCompositionStatus.SELECTION_GAP,
            selection=selection,
            references=references,
            proposition=None,
        )
    answer = selection.answer
    if answer is None:
        raise ValueError("A non-gap source-grounded selection requires an answer.")
    proposition = build_decontextualized_proposition(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        answer=answer,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
        entities=references.entities,
        subject_value_authorizations=references.subject_value_authorizations,
    )
    if proposition.status is DecontextualizationStatus.PROPOSITION:
        status = DeterministicResidualCompositionStatus.COMPOSED
    else:
        status = DeterministicResidualCompositionStatus.COMPOSITION_HELD
    return DeterministicResidualCompositionOutcome(
        event_id=event_id,
        status=status,
        selection=selection,
        references=references,
        proposition=proposition,
    )


class AssertionBlockReason(StrEnum):
    """Typed reason one inspectable Assertion cannot be constructed."""

    PROPOSITION_REQUIRED = "proposition_required"
    UNMAPPED_PREDICATE = "unmapped_predicate"
    UNRESOLVED_SUBJECT_IDENTITY = "unresolved_subject_identity"
    UNRESOLVED_REPORTER = "unresolved_reporter"
    MISSING_OBJECT = "missing_object"


class AssertionConstructionStatus(StrEnum):
    """Terminal state of one inspectable Assertion construction."""

    CONSTRUCTED = "constructed"
    BLOCKED = "blocked"


class AssertionConstructionOutcome(BaseModel):
    """One Event's constructed Assertion or one typed construction block."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    status: AssertionConstructionStatus
    assertion: Assertion | None = None
    block_reason: AssertionBlockReason | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is AssertionConstructionStatus.CONSTRUCTED:
            if self.assertion is None or self.block_reason is not None:
                raise ValueError("A constructed outcome requires one Assertion and no block.")
            if self.assertion.status is not AssertionStatus.PROPOSED:
                raise ValueError("The inspectable Assertion must stay proposed.")
        elif self.assertion is not None or self.block_reason is None:
            raise ValueError("A blocked outcome requires a block reason and no Assertion.")
        return self


@dataclass(frozen=True)
class AssertionConstructionInputs:
    """Resolved inputs one inspectable Assertion construction consumes."""

    predicate_by_label: Mapping[str, str]
    identity_by_entity: Mapping[str, str]
    assertion_type: AssertionType
    source_authority: SourceAuthority
    attribution_basis: AttributionBasis
    source_id: str
    evidence_target_id: str


def construct_inspectable_assertion(
    proposition: DecontextualizedProposition,
    inputs: AssertionConstructionInputs,
) -> AssertionConstructionOutcome:
    """Build one proposed source-report Assertion or one typed block.

    The construction is deterministic and fail-closed. It requires a composed
    proposition, a reviewed predicate for its relation label, and an identity
    mapping for every entity reference the Assertion actually emits. An object
    entity with no reviewed identity mapping stays an object value.
    """
    if proposition.status is not DecontextualizationStatus.PROPOSITION:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.PROPOSITION_REQUIRED,
        )

    relation_label = proposition.relation_label
    if relation_label is None:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.PROPOSITION_REQUIRED,
        )
    predicate = inputs.predicate_by_label.get(relation_label)
    if predicate is None:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.UNMAPPED_PREDICATE,
        )

    subject = proposition.subject
    if subject is None:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.PROPOSITION_REQUIRED,
        )
    subject_entity_id: str | None
    subject_value: str | None
    if subject.entity_ref is not None:
        resolved_subject = inputs.identity_by_entity.get(subject.entity_ref)
        if resolved_subject is None:
            return AssertionConstructionOutcome(
                event_id=proposition.event_id,
                status=AssertionConstructionStatus.BLOCKED,
                block_reason=AssertionBlockReason.UNRESOLVED_SUBJECT_IDENTITY,
            )
        subject_entity_id = resolved_subject
        subject_value = None
    elif subject.subject_value is not None:
        subject_entity_id = None
        subject_value = subject.subject_value
    else:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.UNRESOLVED_SUBJECT_IDENTITY,
        )

    obj = proposition.object
    if obj is None:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.MISSING_OBJECT,
        )
    object_entity_id: str | None = None
    object_value: str | None = None
    if obj.entity_ref is not None:
        object_entity_id = inputs.identity_by_entity.get(obj.entity_ref)
        if object_entity_id is None:
            object_value = obj.exact_fragment.text
    elif obj.object_value is not None:
        object_value = obj.object_value
    else:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.MISSING_OBJECT,
        )

    attributed_to_id: str | None = None
    attribution = proposition.attribution
    if attribution is None:
        return AssertionConstructionOutcome(
            event_id=proposition.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.PROPOSITION_REQUIRED,
        )
    if attribution.kind is DecontextualizationAttributionKind.TARGETED:
        reporter = attribution.reporter_ref
        if reporter is None:
            return AssertionConstructionOutcome(
                event_id=proposition.event_id,
                status=AssertionConstructionStatus.BLOCKED,
                block_reason=AssertionBlockReason.UNRESOLVED_REPORTER,
            )
        attributed_to_id = inputs.identity_by_entity.get(reporter)

    qualifiers: dict[str, JsonValue] = {}
    if proposition.polarity is not None:
        qualifiers["polarity"] = proposition.polarity.value
    if proposition.modality is not None:
        qualifiers["modality"] = proposition.modality.value

    assertion = Assertion(
        id=_deterministic_assertion_id(proposition, inputs.source_id),
        assertion_type=inputs.assertion_type,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id=subject_entity_id,
        subject_value=subject_value,
        predicate=predicate,
        object_entity_id=object_entity_id,
        object_value=object_value,
        status=AssertionStatus.PROPOSED,
        source_authority=inputs.source_authority,
        attribution_basis=inputs.attribution_basis,
        attributed_to_id=attributed_to_id,
        qualifiers=qualifiers,
        source_ids=(inputs.source_id,),
        evidence_target_ids=(inputs.evidence_target_id,),
    )
    return AssertionConstructionOutcome(
        event_id=proposition.event_id,
        status=AssertionConstructionStatus.CONSTRUCTED,
        assertion=assertion,
    )


def _deterministic_assertion_id(
    proposition: DecontextualizedProposition,
    source_id: str,
) -> str:
    payload = json.dumps(
        {
            "event_id": proposition.event_id,
            "source_text_sha256": proposition.source_text_sha256,
            "relation_label": proposition.relation_label,
            "subject": proposition.subject.exact_fragment.text if proposition.subject else None,
            "object": proposition.object.exact_fragment.text if proposition.object else None,
            "polarity": proposition.polarity.value if proposition.polarity else None,
            "modality": proposition.modality.value if proposition.modality else None,
            "source_id": source_id,
        },
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "ast_" + hashlib.sha256(payload.encode()).hexdigest()[:32]
