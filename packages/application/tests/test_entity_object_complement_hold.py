"""An accepted object identity cannot bypass a required object complement.

The parse is coherent and source-exact: Mira praised Acme denying fraud.
The object `Acme` is an accepted organization and governs an `acl` complement,
so composition must hold instead of emitting a proposition that drops it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from kotekomi_application import (
    AssertionConstructionInputs,
    DecontextualizationEntityRef,
    EventCompositionRecord,
    EventEntityLinguisticToken,
    EventEntityReferences,
    ObjectContentCompletion,
    ReferenceResolution,
    SourceRange,
    build_constituent_candidate_inventory,
    compose_event_from_resolution,
)
from kotekomi_domain import AssertionType, AttributionBasis, SourceAuthority

TEXT = "Mira praised Acme denying fraud"
EVENT = "sge_entity_complement"


def _token(
    token_id: str,
    text: str,
    start: int,
    end: int,
    pos: str,
    relation: str,
    head: str | None,
) -> EventEntityLinguisticToken:
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


def _tokens() -> tuple[EventEntityLinguisticToken, ...]:
    return (
        _token("t1", "Mira", 0, 4, "PROPN", "nsubj", "t2"),
        _token("t2", "praised", 5, 12, "VERB", "root", None),
        _token("t3", "Acme", 13, 17, "PROPN", "obj", "t2"),
        _token("t4", "denying", 18, 25, "VERB", "acl", "t3"),
        _token("t5", "fraud", 26, 31, "NOUN", "obj", "t4"),
    )


def _compose(
    object_completion: ObjectContentCompletion | None = None,
) -> EventCompositionRecord:
    tokens = _tokens()
    inventory = build_constituent_candidate_inventory(
        source_text=TEXT,
        event_id=EVENT,
        tokens=tokens,
        event_expression_start=5,
        event_expression_end=12,
    )
    resolution = ReferenceResolution(
        references=EventEntityReferences(
            entities=(
                DecontextualizationEntityRef(
                    entity_id="org_mira",
                    entity_kind="organization",
                    canonical_name="Mira",
                    accepted_source_occurrences=(SourceRange(start=0, end=4, text="Mira"),),
                ),
                DecontextualizationEntityRef(
                    entity_id="org_acme",
                    entity_kind="organization",
                    canonical_name="Acme",
                    accepted_source_occurrences=(SourceRange(start=13, end=17, text="Acme"),),
                ),
            ),
            subject_value_authorizations=(),
        ),
        diagnostics=(),
    )
    inputs = AssertionConstructionInputs(
        predicate_by_label={"praised": "praised"},
        identity_by_entity={"org_mira": "org_mira", "org_acme": "org_acme"},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_entity_complement",
        evidence_target_id="etg_entity_complement",
        constructed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return compose_event_from_resolution(
        event_id=EVENT,
        source_text=TEXT,
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        inventory=inventory,
        trigger_head_start=5,
        trigger_head_end=12,
        tokens=tokens,
        resolution=resolution,
        assertion_inputs=inputs,
        object_completion=object_completion,
    )


def test_entity_backed_object_holds_instead_of_dropping_its_complement() -> None:
    """The accepted object identity must not produce a truncated proposition."""
    record = _compose(None)

    assert record.status.value == "held"
    assert record.hold_reason == "object_complement_required"
    assert record.assertion is None
