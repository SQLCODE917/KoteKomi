from __future__ import annotations

import hashlib

from kotekomi_application import (
    StandingFactDraft,
    StandingFactHoldReason,
    derive_source_copy_view,
    resolve_standing_fact_relation,
    standing_fact_source_hold_reasons,
)
from kotekomi_application.hybrid_event_trigger_preview import source_occurrences
from kotekomi_application.hybrid_standing_fact_model_output import StandingFactObjectKind


def test_event_bearing_source_does_not_preempt_an_independent_standing_fact() -> None:
    source = "Dario Amodei is Anthropic's chief executive and criticized Stargate."
    draft = _draft(
        relation="is",
        object_literal="Anthropic's chief executive",
    )

    reasons = standing_fact_source_hold_reasons(draft, source)

    assert reasons == ()
    assert StandingFactHoldReason.EVENT_ROUTE_REQUIRED not in reasons


def test_parallel_route_still_rejects_a_literal_absent_from_authoritative_source() -> None:
    draft = _draft(relation="is", object_literal="Anthropic's founder")

    reasons = standing_fact_source_hold_reasons(
        draft,
        "Dario Amodei is Anthropic's chief executive and criticized Stargate.",
    )

    assert reasons == (StandingFactHoldReason.LITERAL_NOT_IN_SOURCE,)


def test_event_route_owns_a_standing_relation_that_overlaps_its_trigger() -> None:
    source = 'Dario Amodei described Trump as a "feudal warlord".'
    draft = _draft(relation="described", object_literal='"feudal warlord"')

    reasons = standing_fact_source_hold_reasons(
        draft,
        source,
        event_trigger_ranges=((13, 22, "etd_characterization"),),
    )

    assert reasons == (StandingFactHoldReason.EVENT_ROUTE_REQUIRED,)


def test_standing_relation_selector_reconstructs_exact_authoritative_characters() -> None:
    source = "Dario Amodei serves  as Anthropic's chief executive."
    occurrences = source_occurrences(derive_source_copy_view(source))

    relation = resolve_standing_fact_relation(source, occurrences, "o3-o4")

    assert relation.text == "serves  as"
    assert source[relation.start : relation.end] == relation.text


def test_standing_relation_selector_rejects_unknown_or_reversed_occurrences() -> None:
    source = "Dario Amodei serves as Anthropic's chief executive."
    occurrences = source_occurrences(derive_source_copy_view(source))

    for selector in ("o999", "o4-o3"):
        try:
            resolve_standing_fact_relation(source, occurrences, selector)
        except ValueError:
            continue
        raise AssertionError(f"Expected {selector} to be rejected.")


def _draft(*, relation: str, object_literal: str) -> StandingFactDraft:
    parts = (
        "seg_fixture",
        "c1",
        "candidate_amodei",
        relation,
        "13",
        str(13 + len(relation)),
        StandingFactObjectKind.LITERAL.value,
        object_literal,
        "",
        "ext_fixture",
        "mrn_fixture",
    )
    return StandingFactDraft(
        id="sfd_" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24],
        source_segment_id=parts[0],
        subject_label=parts[1],
        subject_candidate_id=parts[2],
        relation_label=relation,
        relation_start=13,
        relation_end=13 + len(relation),
        object_kind=StandingFactObjectKind.LITERAL,
        object_label_or_literal=object_literal,
        extraction_task_id=parts[9],
        model_run_id=parts[10],
    )
