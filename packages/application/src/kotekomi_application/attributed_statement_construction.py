"""Deterministic model-free attributed-statement construction.

D1 of the Event Attribution Production Wiring package. The constructor converts one
governed ``EventSemanticDraft`` plus its resolved attribution target into a single
``attributed_statement`` ``ProposedAssertion``, using the governed event's own content
triple and a separate ``attributed_to_id`` speaker link.

The constructor dispatches on ``EventSemanticDraft.attribution_kind``:

- ``source_narrator``: no attributed-statement Assertion is produced.
- ``unresolved``: a typed failure is produced instead of a record.
- ``mention_candidate`` / ``source_span``: the attribution target resolves to an Actor
  or Organization and one proposed Assertion is constructed.

The module never invokes a model and never creates accepted state. It produces reviewable
``ProposedAssertion`` records only.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, Self

from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    ProposedAssertion,
    SourceAuthority,
)
from kotekomi_domain.models import (
    ActorId,
    AssertionId,
    EntityId,
    EventId,
    EvidenceTargetId,
    JsonValue,
    OrganizationId,
    PlaceId,
    SourceId,
)
from pydantic import BaseModel, ConfigDict, model_validator

from kotekomi_application.hybrid_event_semantics import (
    EventArgumentTargetDraft,
    EventAttributionKind,
    EventSemanticDraft,
)

_ContentEntityId = EntityId | ActorId | OrganizationId | EventId | PlaceId
_TARGETED_KINDS = frozenset(
    {EventAttributionKind.MENTION_CANDIDATE, EventAttributionKind.SOURCE_SPAN}
)


class AttributedStatementStatus(StrEnum):
    """Terminal state of one deterministic attributed-statement construction."""

    CONSTRUCTED = "constructed"
    NO_ASSERTION = "no_assertion"
    FAILED = "failed"


class AttributedStatementFailureReason(StrEnum):
    """Typed reason that one attributed statement could not be constructed."""

    ATTRIBUTION_UNRESOLVED = "attribution_unresolved"
    ATTRIBUTION_TARGET_MISSING = "attribution_target_missing"
    ATTRIBUTION_TARGET_NOT_ACTOR_OR_ORGANIZATION = "attribution_target_not_actor_or_organization"


class AttributionTargetResolver(Protocol):
    """Resolve one attribution target to an Actor or Organization, or reject it."""

    def resolve_attribution_target(
        self, target: EventArgumentTargetDraft
    ) -> ActorId | OrganizationId | None: ...


class AttributedStatementOutcome(BaseModel):
    """One bounded result of attributed-statement construction."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: AttributedStatementStatus
    failure_reason: AttributedStatementFailureReason | None = None
    proposed_assertion: ProposedAssertion | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is AttributedStatementStatus.CONSTRUCTED:
            if self.proposed_assertion is None or self.failure_reason is not None:
                raise ValueError("A constructed outcome requires a proposed assertion.")
        elif self.status is AttributedStatementStatus.NO_ASSERTION:
            if self.proposed_assertion is not None or self.failure_reason is not None:
                raise ValueError("A no-assertion outcome cannot carry an assertion or failure.")
        elif self.proposed_assertion is not None or self.failure_reason is None:
            raise ValueError("A failed outcome requires one failure reason.")
        return self


def construct_attributed_statement(
    *,
    draft: EventSemanticDraft,
    attribution_target: EventArgumentTargetDraft | None,
    resolver: AttributionTargetResolver,
    subject_entity_id: _ContentEntityId,
    object_entity_id: _ContentEntityId | None,
    object_value: JsonValue,
    source_id: SourceId,
    support_evidence_target_id: EvidenceTargetId,
    assertion_id: AssertionId,
) -> AttributedStatementOutcome:
    """Construct one ``attributed_statement`` ProposedAssertion or a typed non-record.

    One of ``object_entity_id`` or ``object_value`` must be supplied; the other must be
    ``None``. ``relation_label`` is taken from ``draft.proposed_event_label``, so the
    governed event content triple stays ``subject_entity_id`` / ``relation_label`` /
    ``object_entity_id | object_value`` with the speaker carried on ``attributed_to_id``.
    """
    if draft.attribution_kind is EventAttributionKind.SOURCE_NARRATOR:
        return AttributedStatementOutcome(status=AttributedStatementStatus.NO_ASSERTION)

    if draft.attribution_kind is EventAttributionKind.UNRESOLVED:
        return AttributedStatementOutcome(
            status=AttributedStatementStatus.FAILED,
            failure_reason=AttributedStatementFailureReason.ATTRIBUTION_UNRESOLVED,
        )

    if draft.attribution_kind not in _TARGETED_KINDS:
        raise ValueError("Unsupported EventAttributionKind for attributed-statement construction.")

    if attribution_target is None:
        return AttributedStatementOutcome(
            status=AttributedStatementStatus.FAILED,
            failure_reason=AttributedStatementFailureReason.ATTRIBUTION_TARGET_MISSING,
        )

    attributed_to_id = resolver.resolve_attribution_target(attribution_target)
    if attributed_to_id is None or not (
        attributed_to_id.startswith("act_") or attributed_to_id.startswith("org_")
    ):
        return AttributedStatementOutcome(
            status=AttributedStatementStatus.FAILED,
            failure_reason=(
                AttributedStatementFailureReason.ATTRIBUTION_TARGET_NOT_ACTOR_OR_ORGANIZATION
            ),
        )

    proposed = ProposedAssertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.ATTRIBUTED_STATEMENT,
        subject_entity_id=subject_entity_id,
        relation_label=draft.proposed_event_label,
        object_entity_id=object_entity_id,
        object_value=object_value,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        attributed_to_id=attributed_to_id,
        source_ids=(source_id,),
        evidence_target_ids=(support_evidence_target_id,),
    )
    return AttributedStatementOutcome(
        status=AttributedStatementStatus.CONSTRUCTED,
        proposed_assertion=proposed,
    )
