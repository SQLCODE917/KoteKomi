"""Event-Entity Reference Provider Port (R19).

The composer receives entity references and reviewed subject-value exclusions
only through this Port. A subject resolves to an entity reference on an accepted
Actor or Organization occurrence, or to a ``subject_value`` on a reviewed
``non_entity_value`` exclusion; the absence of either is a ``subject_unavailable``
hold, never a fabricated reference. The coordinating Application Layer use case —
not the composer — calls this Port and passes the validated references into the
composer.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
    DecontextualizationExclusion,
)


class EventEntityReferences(BaseModel):
    """Validated references one source-grounded provider returned for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entities: tuple[DecontextualizationEntityRef, ...]
    subject_value_authorizations: tuple[DecontextualizationExclusion, ...]


class EventEntityReferenceProvider(Protocol):
    """Port that resolves one Event's Actor/Organization references and exclusions.

    Implementations return accepted entity references and reviewed
    ``non_entity_value`` subject-value authorizations only. They never fabricate a
    reference and never resolve a subject to a value without a reviewed exclusion.
    """

    def resolve_references(
        self,
        event_id: str,
        source_text: str,
        source_text_sha256: str,
    ) -> EventEntityReferences: ...
