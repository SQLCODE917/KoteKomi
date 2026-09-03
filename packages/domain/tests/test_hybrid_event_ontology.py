import hashlib

import pytest
from kotekomi_domain import (
    HYBRID_EVENT_CORE_V1,
    HYBRID_EVENT_SEMANTICS_V1,
    HybridEventOntologySlice,
    HybridEventStructuralPredicate,
    UpperRole,
    canonical_hybrid_event_ontology_slice_bytes,
    canonical_hybrid_event_semantics_profile_bytes,
    hybrid_event_ontology_slice_sha256,
    hybrid_event_semantics_profile_sha256,
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


def test_hybrid_event_semantics_profile_is_bounded_canonical_and_source_agnostic() -> None:
    payload = canonical_hybrid_event_semantics_profile_bytes()

    assert HYBRID_EVENT_SEMANTICS_V1.upper_roles == tuple(
        sorted(UpperRole, key=lambda item: item.value)
    )
    assert tuple(item.id for item in HYBRID_EVENT_SEMANTICS_V1.frames) == (
        "authorization",
        "causation",
        "change_in_intensity",
        "characterization",
        "classification",
        "investment_abandonment",
        "recommendation",
    )
    assert hybrid_event_semantics_profile_sha256() == hashlib.sha256(payload).hexdigest()
    assert b"initiative_increase" not in payload
    assert b"Anthropic" not in payload
    assert b"Department of Defense" not in payload
    frames = {item.id: item for item in HYBRID_EVENT_SEMANTICS_V1.frames}
    assert frames["characterization"].attribution_role_id == "characterization.evaluator"
    assert frames["recommendation"].attribution_role_id == "recommendation.recommender"
    assert frames["authorization"].attribution_role_id is None


def test_hybrid_event_semantics_roles_are_frame_scoped_and_not_metadata() -> None:
    roles = {role.id: role for frame in HYBRID_EVENT_SEMANTICS_V1.frames for role in frame.roles}

    assert roles["change_in_intensity.affected_process"].upper_role is UpperRole.THEME
    assert roles["authorization.authorizer"].upper_role is UpperRole.AGENT
    assert roles["causation.effect"].upper_role is UpperRole.RESULT
    assert all(role.id.startswith(f"{role.frame_id}.") for role in roles.values())
    assert not {"time", "place", "attribution", "organization"}.intersection(roles)
