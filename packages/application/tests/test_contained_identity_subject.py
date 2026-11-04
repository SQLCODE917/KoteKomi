"""An accepted occurrence contained in the selected subject resolves that subject.

The selected boundary may carry a determiner while the reviewed occurrence does not:
selected `the US` with an accepted `US` occurrence still yields the entity role.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from kotekomi_application import (
    AssertionConstructionInputs,
    DecontextualizationEntityRef,
    EventEntityLinguisticToken,
    EventEntityReferences,
    ReferenceResolution,
    SourceRange,
    build_constituent_candidate_inventory,
    compose_event_from_resolution,
)
from kotekomi_domain import AssertionType, AttributionBasis, SourceAuthority

TEXT = "the US started the war"
EVENT = "sge_contained_identity"


def _token(token_id, text, start, end, pos, relation, head):
    return EventEntityLinguisticToken(
        token_id=token_id,
        sentence_id="s1",
        text=text,
        start=start,
        end=end,
        lemma=text.casefold(),
        part_of_speech=pos,
        dependency_relation=relation,
        head_token_id=head,
    )


def test_contained_identity_resolves_a_determiner_prefixed_subject() -> None:
    tokens = (
        _token("t1", "the", 0, 3, "DET", "det", "t2"),
        _token("t2", "US", 4, 6, "PROPN", "nsubj", "t3"),
        _token("t3", "started", 7, 14, "VERB", "root", None),
        _token("t4", "the", 15, 18, "DET", "det", "t5"),
        _token("t5", "war", 19, 22, "NOUN", "obj", "t3"),
    )
    inventory = build_constituent_candidate_inventory(
        source_text=TEXT,
        event_id=EVENT,
        tokens=tokens,
        event_expression_start=7,
        event_expression_end=14,
    )
    resolution = ReferenceResolution(
        references=EventEntityReferences(
            entities=(
                DecontextualizationEntityRef(
                    entity_id="org_us_probe",
                    entity_kind="organization",
                    canonical_name="United States",
                    accepted_source_occurrences=(SourceRange(start=4, end=6, text="US"),),
                ),
            ),
            subject_value_authorizations=(),
        ),
        diagnostics=(),
    )
    inputs = AssertionConstructionInputs(
        predicate_by_label={"started": "started"},
        identity_by_entity={"org_us_probe": "org_us_probe"},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_contained",
        evidence_target_id="etg_contained",
        constructed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    record = compose_event_from_resolution(
        event_id=EVENT,
        source_text=TEXT,
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        inventory=inventory,
        trigger_head_start=7,
        trigger_head_end=14,
        tokens=tokens,
        resolution=resolution,
        assertion_inputs=inputs,
    )

    assert record.status.value == "composed"
    assert record.hold_reason is None
    assert record.assertion is not None
    assert record.assertion.subject_entity_id == "org_us_probe"
    assert record.assertion.object_value == "the war"
