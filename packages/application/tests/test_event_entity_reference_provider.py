"""Focused tests for the Event-Entity Reference Provider Port (R19)."""

from __future__ import annotations

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    DecontextualizationEntityRef,
    DecontextualizationExclusion,
    EventEntityReferenceProvider,
    EventEntityReferences,
)
from pydantic import ValidationError


def _entity(*, entity_id: str = "EGE-001") -> DecontextualizationEntityRef:
    return DecontextualizationEntityRef(
        entity_id=entity_id,
        entity_kind="actor",
        canonical_name="Sacks",
        accepted_source_occurrences=(AttachmentSourceRange(start=0, end=5, text="Sacks"),),
    )


def _exclusion() -> DecontextualizationExclusion:
    return DecontextualizationExclusion(
        exclusion_id="EGX-900",
        contextual_kind="non_entity_value",
        source_range=AttachmentSourceRange(start=5, end=20, text="The April order"),
        rationale="A date-scoped nominal order, not an Actor or Organization.",
    )


def test_references_are_typed_and_immutable() -> None:
    refs = EventEntityReferences(
        entities=(_entity(),),
        subject_value_authorizations=(_exclusion(),),
    )
    assert [item.entity_id for item in refs.entities] == ["EGE-001"]
    assert [item.exclusion_id for item in refs.subject_value_authorizations] == ["EGX-900"]
    with pytest.raises(ValidationError):
        EventEntityReferences(entities=(_entity(),), subject_value_authorizations=("x",))  # type: ignore[arg-type]


def test_provider_protocol_accepts_a_conforming_adapter() -> None:
    class Adapter:
        def resolve_references(
            self, event_id: str, source_text: str, source_text_sha256: str
        ) -> EventEntityReferences:
            del event_id, source_text, source_text_sha256
            return EventEntityReferences(entities=(), subject_value_authorizations=())

    provider: EventEntityReferenceProvider = Adapter()
    result = provider.resolve_references("AHE-051", "[45] The April order is not final.", "0" * 64)
    assert result.entities == ()
    assert result.subject_value_authorizations == ()
