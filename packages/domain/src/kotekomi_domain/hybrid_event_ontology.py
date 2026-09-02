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
