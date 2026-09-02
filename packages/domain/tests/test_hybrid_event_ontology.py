import hashlib

import pytest
from kotekomi_domain import (
    HYBRID_EVENT_CORE_V1,
    HybridEventOntologySlice,
    HybridEventStructuralPredicate,
    canonical_hybrid_event_ontology_slice_bytes,
    hybrid_event_ontology_slice_sha256,
)


def test_hybrid_event_core_slice_is_canonical_and_source_agnostic() -> None:
    payload = canonical_hybrid_event_ontology_slice_bytes()

    assert HYBRID_EVENT_CORE_V1.core_event_labels == ("event",)
    assert HYBRID_EVENT_CORE_V1.core_role_labels == (
        "actor",
        "object",
        "participant",
        "place",
        "time",
    )
    assert "Event" not in HYBRID_EVENT_CORE_V1.core_event_labels
    assert "Actor" not in HYBRID_EVENT_CORE_V1.core_role_labels
    assert b"Anthropic" not in payload
    assert hybrid_event_ontology_slice_sha256() == hashlib.sha256(payload).hexdigest()


def test_hybrid_event_slice_rejects_missing_structural_predicate() -> None:
    with pytest.raises(ValueError, match="every structural predicate"):
        HybridEventOntologySlice(
            structural_predicates=tuple(HybridEventStructuralPredicate)[:-1],
            core_event_labels=("event",),
            core_role_labels=("actor", "object", "participant", "place", "time"),
        )
