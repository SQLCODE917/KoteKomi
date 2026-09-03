"""Versioned structural ontology for derived hybrid event claims."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class HybridEventStructuralPredicate(StrEnum):
    """Source-agnostic predicates supported by the first hybrid event slice."""

    HAS_EVENT_TYPE = "has_event_type"
    HAS_ARGUMENT = "has_argument"
    HAS_TIME = "has_time"
    HAS_PLACE = "has_place"
    HAS_POLARITY = "has_polarity"
    HAS_MODALITY = "has_modality"
    ACCORDING_TO = "according_to"


class HybridEventOntologySlice(BaseModel):
    """One immutable, canonically serializable structural ontology slice."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_event_ontology_slice_v1"] = "hybrid_event_ontology_slice_v1"
    id: Literal["hybrid_event_core_v1"] = "hybrid_event_core_v1"
    structural_predicates: tuple[HybridEventStructuralPredicate, ...]
    core_event_labels: tuple[str, ...]
    core_role_labels: tuple[str, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.structural_predicates != tuple(HybridEventStructuralPredicate):
            raise ValueError("The hybrid event ontology must expose every structural predicate.")
        if self.core_event_labels != tuple(sorted(set(self.core_event_labels))):
            raise ValueError("Core event labels must be ordered and distinct.")
        if self.core_role_labels != tuple(sorted(set(self.core_role_labels))):
            raise ValueError("Core role labels must be ordered and distinct.")
        return self


HYBRID_EVENT_CORE_V1 = HybridEventOntologySlice(
    structural_predicates=tuple(HybridEventStructuralPredicate),
    core_event_labels=("event",),
    core_role_labels=("actor", "object", "participant", "place", "time"),
)


class UpperRole(StrEnum):
    """Stable role meanings shared by governed event frames."""

    AGENT = "agent"
    CAUSE = "cause"
    CONTENT = "content"
    PARTICIPANT = "participant"
    RESULT = "result"
    THEME = "theme"


class SemanticArgumentTargetKind(StrEnum):
    """Source-backed target forms admitted by the first semantic profile."""

    EVENT_SUBJECT = "event_subject"
    MENTION_CANDIDATE = "mention_candidate"
    SOURCE_SPAN = "source_span"


class FrameRoleDefinition(BaseModel):
    """One governed role whose meaning is scoped to one event frame."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str
    frame_id: str
    label: str
    definition: str
    upper_role: UpperRole
    required: bool
    allowed_target_kinds: tuple[SemanticArgumentTargetKind, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.id != f"{self.frame_id}.{self.label}":
            raise ValueError("Frame role ID must bind its frame and label.")
        if not self.definition.strip():
            raise ValueError("Frame role definition requires text.")
        if self.allowed_target_kinds != tuple(
            sorted(set(self.allowed_target_kinds), key=lambda item: item.value)
        ):
            raise ValueError("Frame role target kinds must be ordered and distinct.")
        return self


class EventFrameDefinition(BaseModel):
    """One governed event frame with its complete role inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str
    label: str
    definition: str
    roles: tuple[FrameRoleDefinition, ...]
    attribution_role_id: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.id != self.label:
            raise ValueError("Event frame ID and label must match in the first profile.")
        if not self.definition.strip():
            raise ValueError("Event frame definition requires text.")
        if self.roles != tuple(sorted(self.roles, key=lambda item: item.id)):
            raise ValueError("Frame roles must use canonical order.")
        if len({item.id for item in self.roles}) != len(self.roles):
            raise ValueError("Event frame repeats one role.")
        if any(item.frame_id != self.id for item in self.roles):
            raise ValueError("Frame role belongs to a different event frame.")
        if not any(item.required for item in self.roles):
            raise ValueError("Event frame requires at least one required role.")
        if self.attribution_role_id is not None:
            attribution_role = next(
                (item for item in self.roles if item.id == self.attribution_role_id), None
            )
            if attribution_role is None:
                raise ValueError("Event attribution role must belong to its frame.")
            if not attribution_role.required or attribution_role.upper_role is not UpperRole.AGENT:
                raise ValueError("Event attribution role must be a required agent role.")
        return self


class HybridEventSemanticsProfile(BaseModel):
    """One immutable governed profile for qualified event semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_event_semantics_profile_v1"] = (
        "hybrid_event_semantics_profile_v1"
    )
    id: Literal["hybrid_event_semantics_v1"] = "hybrid_event_semantics_v1"
    upper_roles: tuple[UpperRole, ...]
    frames: tuple[EventFrameDefinition, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.upper_roles != tuple(sorted(set(self.upper_roles), key=lambda item: item.value)):
            raise ValueError("Upper roles must be ordered and distinct.")
        if self.frames != tuple(sorted(self.frames, key=lambda item: item.id)):
            raise ValueError("Event frames must use canonical order.")
        if len({item.id for item in self.frames}) != len(self.frames):
            raise ValueError("Semantic profile repeats one event frame.")
        if any(
            role.upper_role not in self.upper_roles for frame in self.frames for role in frame.roles
        ):
            raise ValueError("Frame role references an unknown UpperRole.")
        return self


_MENTION_OR_SPAN = (
    SemanticArgumentTargetKind.MENTION_CANDIDATE,
    SemanticArgumentTargetKind.SOURCE_SPAN,
)
_EVENT_OR_SPAN = (
    SemanticArgumentTargetKind.EVENT_SUBJECT,
    SemanticArgumentTargetKind.SOURCE_SPAN,
)
_ANY_TARGET = tuple(SemanticArgumentTargetKind)


def _role(
    frame_id: str,
    label: str,
    definition: str,
    upper_role: UpperRole,
    *,
    required: bool,
    allowed: tuple[SemanticArgumentTargetKind, ...],
) -> FrameRoleDefinition:
    return FrameRoleDefinition(
        id=f"{frame_id}.{label}",
        frame_id=frame_id,
        label=label,
        definition=definition,
        upper_role=upper_role,
        required=required,
        allowed_target_kinds=tuple(sorted(allowed, key=lambda item: item.value)),
    )


HYBRID_EVENT_SEMANTICS_V1 = HybridEventSemanticsProfile(
    upper_roles=tuple(sorted(UpperRole, key=lambda item: item.value)),
    frames=tuple(
        sorted(
            (
                EventFrameDefinition(
                    id="authorization",
                    label="authorization",
                    definition=(
                        "One party permits another party to perform an action or use a resource."
                    ),
                    roles=tuple(
                        sorted(
                            (
                                _role(
                                    "authorization",
                                    "authorized_party",
                                    "The party that receives permission.",
                                    UpperRole.PARTICIPANT,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "authorization",
                                    "authorized_resource",
                                    "A resource whose use the authorization permits.",
                                    UpperRole.THEME,
                                    required=False,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "authorization",
                                    "authorizer",
                                    "The party that grants permission.",
                                    UpperRole.AGENT,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "authorization",
                                    "permitted_action",
                                    "The action that the authorization permits.",
                                    UpperRole.CONTENT,
                                    required=True,
                                    allowed=_EVENT_OR_SPAN,
                                ),
                            ),
                            key=lambda item: item.id,
                        )
                    ),
                ),
                EventFrameDefinition(
                    id="causation",
                    label="causation",
                    definition=(
                        "One event, condition, or situation produces another event or result."
                    ),
                    roles=tuple(
                        sorted(
                            (
                                _role(
                                    "causation",
                                    "cause",
                                    "The event, condition, or situation that produces the effect.",
                                    UpperRole.CAUSE,
                                    required=True,
                                    allowed=_EVENT_OR_SPAN,
                                ),
                                _role(
                                    "causation",
                                    "effect",
                                    "The event or result produced by the cause.",
                                    UpperRole.RESULT,
                                    required=True,
                                    allowed=_EVENT_OR_SPAN,
                                ),
                            ),
                            key=lambda item: item.id,
                        )
                    ),
                ),
                EventFrameDefinition(
                    id="change_in_intensity",
                    label="change_in_intensity",
                    definition="An activity, process, or condition changes in strength or extent.",
                    roles=(
                        _role(
                            "change_in_intensity",
                            "affected_process",
                            "The activity, process, or condition whose intensity changes.",
                            UpperRole.THEME,
                            required=True,
                            allowed=_ANY_TARGET,
                        ),
                    ),
                ),
                EventFrameDefinition(
                    id="characterization",
                    label="characterization",
                    definition="One party assigns a description or assessment to a subject.",
                    attribution_role_id="characterization.evaluator",
                    roles=tuple(
                        sorted(
                            (
                                _role(
                                    "characterization",
                                    "characterization",
                                    "The description or assessment assigned to the subject.",
                                    UpperRole.CONTENT,
                                    required=True,
                                    allowed=(SemanticArgumentTargetKind.SOURCE_SPAN,),
                                ),
                                _role(
                                    "characterization",
                                    "evaluated_subject",
                                    "The subject that receives the description or assessment.",
                                    UpperRole.THEME,
                                    required=True,
                                    allowed=_ANY_TARGET,
                                ),
                                _role(
                                    "characterization",
                                    "evaluator",
                                    "The party that supplies the description or assessment.",
                                    UpperRole.AGENT,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                            ),
                            key=lambda item: item.id,
                        )
                    ),
                ),
                EventFrameDefinition(
                    id="classification",
                    label="classification",
                    definition="One party assigns a governed category or status to a subject.",
                    roles=tuple(
                        sorted(
                            (
                                _role(
                                    "classification",
                                    "assigned_classification",
                                    "The category or status assigned to the subject.",
                                    UpperRole.RESULT,
                                    required=True,
                                    allowed=(SemanticArgumentTargetKind.SOURCE_SPAN,),
                                ),
                                _role(
                                    "classification",
                                    "classified_entity",
                                    "The subject that receives the category or status.",
                                    UpperRole.THEME,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "classification",
                                    "classifier",
                                    "The party that assigns the category or status.",
                                    UpperRole.AGENT,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "classification",
                                    "stated_reason",
                                    "The source-stated reason for the classification.",
                                    UpperRole.CAUSE,
                                    required=False,
                                    allowed=(SemanticArgumentTargetKind.SOURCE_SPAN,),
                                ),
                            ),
                            key=lambda item: item.id,
                        )
                    ),
                ),
                EventFrameDefinition(
                    id="investment_abandonment",
                    label="investment_abandonment",
                    definition="An investor abandons an existing or planned investment.",
                    roles=tuple(
                        sorted(
                            (
                                _role(
                                    "investment_abandonment",
                                    "abandoned_asset",
                                    "The investment that the investor abandons.",
                                    UpperRole.THEME,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "investment_abandonment",
                                    "disinvestor",
                                    "The party that abandons the investment.",
                                    UpperRole.AGENT,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                                _role(
                                    "investment_abandonment",
                                    "investee",
                                    "The party in which the abandoned investment was placed.",
                                    UpperRole.PARTICIPANT,
                                    required=False,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                            ),
                            key=lambda item: item.id,
                        )
                    ),
                ),
                EventFrameDefinition(
                    id="recommendation",
                    label="recommendation",
                    definition="One party recommends an action concerning a subject.",
                    attribution_role_id="recommendation.recommender",
                    roles=tuple(
                        sorted(
                            (
                                _role(
                                    "recommendation",
                                    "recommendation_subject",
                                    "The subject that the recommended action concerns.",
                                    UpperRole.THEME,
                                    required=False,
                                    allowed=_ANY_TARGET,
                                ),
                                _role(
                                    "recommendation",
                                    "recommended_action",
                                    "The action that the party recommends.",
                                    UpperRole.CONTENT,
                                    required=True,
                                    allowed=_EVENT_OR_SPAN,
                                ),
                                _role(
                                    "recommendation",
                                    "recommender",
                                    "The party that recommends the action.",
                                    UpperRole.AGENT,
                                    required=True,
                                    allowed=_MENTION_OR_SPAN,
                                ),
                            ),
                            key=lambda item: item.id,
                        )
                    ),
                ),
            ),
            key=lambda item: item.id,
        )
    ),
)


def canonical_hybrid_event_ontology_slice_bytes(
    ontology_slice: HybridEventOntologySlice = HYBRID_EVENT_CORE_V1,
) -> bytes:
    """Return canonical JSON bytes for ontology identity and replay."""
    return (
        json.dumps(
            ontology_slice.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def hybrid_event_ontology_slice_sha256(
    ontology_slice: HybridEventOntologySlice = HYBRID_EVENT_CORE_V1,
) -> str:
    """Return the canonical ontology slice digest."""
    return hashlib.sha256(canonical_hybrid_event_ontology_slice_bytes(ontology_slice)).hexdigest()


def canonical_hybrid_event_semantics_profile_bytes(
    profile: HybridEventSemanticsProfile = HYBRID_EVENT_SEMANTICS_V1,
) -> bytes:
    """Return canonical JSON bytes for the governed semantic profile."""
    return (
        json.dumps(
            profile.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def hybrid_event_semantics_profile_sha256(
    profile: HybridEventSemanticsProfile = HYBRID_EVENT_SEMANTICS_V1,
) -> str:
    """Return the canonical governed semantic-profile digest."""
    return hashlib.sha256(canonical_hybrid_event_semantics_profile_bytes(profile)).hexdigest()
