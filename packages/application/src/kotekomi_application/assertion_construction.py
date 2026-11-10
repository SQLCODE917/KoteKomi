"""Production ownership of source ranges and inspectable Assertion construction.

Production composition and experiment runners both consume these contracts. The
caller supplies the construction timestamp: a live workflow passes the current
inspection-clock time, and a historical runner passes its documented logical epoch.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
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
)

_EventId = Annotated[
    str, Field(pattern=r"^(?:(?:TGE|AHE)-[0-9]{3}|sge_[A-Za-z0-9][A-Za-z0-9_-]*)$")
]


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
    constructed_at: datetime


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
        resolved_reporter = (
            inputs.identity_by_entity.get(reporter) if reporter is not None else None
        )
        if reporter is None or resolved_reporter is None:
            return AssertionConstructionOutcome(
                event_id=proposition.event_id,
                status=AssertionConstructionStatus.BLOCKED,
                block_reason=AssertionBlockReason.UNRESOLVED_REPORTER,
            )
        attributed_to_id = resolved_reporter

    qualifiers: dict[str, JsonValue] = {}
    if proposition.polarity is not None:
        qualifiers["polarity"] = proposition.polarity.value
    if proposition.modality is not None:
        qualifiers["modality"] = proposition.modality.value
    if proposition.adjunct_qualifier is not None:
        qualifiers["time"] = proposition.adjunct_qualifier.exact_range.text

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
        created_at=inputs.constructed_at,
        updated_at=inputs.constructed_at,
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
            **(
                {"time": proposition.adjunct_qualifier.exact_range.text}
                if proposition.adjunct_qualifier
                else {}
            ),
            "source_id": source_id,
        },
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "ast_" + hashlib.sha256(payload.encode()).hexdigest()[:32]
