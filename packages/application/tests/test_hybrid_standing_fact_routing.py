from __future__ import annotations

import hashlib

from kotekomi_application import (
    StandingFactDraft,
    StandingFactHoldReason,
    StandingFactObjectMapping,
    build_standing_fact_draft,
    build_standing_fact_proposition,
    derive_source_copy_view,
    resolve_standing_fact_relation,
    standing_fact_candidate_occurrence_selector,
    standing_fact_source_hold_reasons,
)
from kotekomi_application.hybrid_event_trigger_preview import source_occurrences
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    MentionCandidate,
)
from kotekomi_application.hybrid_standing_fact_model_output import (
    StandingFactObjectKind,
    StandingFactProposal,
)


def test_event_bearing_source_does_not_preempt_an_independent_standing_fact() -> None:
    source = "Dario Amodei is Anthropic's chief executive and criticized Stargate."
    draft = _draft(
        relation="is",
        object_literal="Anthropic's chief executive",
    )

    reasons = standing_fact_source_hold_reasons(draft, source)

    assert reasons == ()
    assert StandingFactHoldReason.EVENT_ROUTE_REQUIRED not in reasons


def test_amodei_07_keeps_an_independent_standing_fact_beside_three_events() -> None:
    source = (
        "Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook "
        "post ahead of the 2024 presidential election, Amodei urged his associates to "
        'vote for vice president Kamala Harris over Trump, describing him as a "feudal '
        'warlord". '
    )
    draft = _draft(
        source=source,
        subject_text="Anthropic",
        subject_start=0,
        relation="strategy has mirrored",
        relation_start=12,
        object_literal="Amodei's views toward Trump",
        object_start=34,
    )

    reasons = standing_fact_source_hold_reasons(
        draft,
        source,
        event_trigger_ranges=(
            (130, 135, "etd_urged"),
            (154, 158, "etd_vote"),
            (204, 214, "etd_describing"),
        ),
        mention_ranges=((34, 41, "mnc_amodei"), (56, 61, "mnc_trump")),
    )
    proposition = build_standing_fact_proposition(draft, source, "etg_" + "a" * 24)

    assert reasons == ()
    assert proposition.text == ("Anthropic's strategy has mirrored Amodei's views toward Trump.")


def test_relation_that_consumes_object_mentions_is_held_before_qualification() -> None:
    source = "Anthropic's strategy has mirrored Amodei's views toward Trump."
    draft = _draft(
        source=source,
        subject_text="Anthropic",
        subject_start=0,
        relation="mirrored Amodei's views toward Trump",
        relation_start=25,
        object_literal="Trump",
        object_start=56,
    )

    reasons = standing_fact_source_hold_reasons(
        draft,
        source,
        mention_ranges=((34, 41, "mnc_amodei"), (56, 61, "mnc_trump")),
    )

    assert StandingFactHoldReason.RELATION_OVERLAPS_MENTION in reasons
    assert StandingFactHoldReason.PROPOSITION_NOT_SOURCE_ORDERED in reasons


def test_candidate_occurrence_locator_disambiguates_repeated_names() -> None:
    source = "Trump criticized a policy before officials briefed Trump."
    occurrences = source_occurrences(derive_source_copy_view(source))
    first = _candidate(source, start=0, end=5)
    second_start = source.rindex("Trump")
    second = _candidate(source, start=second_start, end=second_start + 5)

    assert standing_fact_candidate_occurrence_selector(first, source, occurrences) == "o1"
    assert standing_fact_candidate_occurrence_selector(second, source, occurrences) == "o8"


def test_candidate_occurrence_locator_maps_collapsed_copy_positions_back_to_source() -> None:
    source = "Officials  briefed  Dario  Amodei."
    occurrences = source_occurrences(derive_source_copy_view(source))
    start = source.index("Dario")
    candidate = _candidate(source, start=start, end=start + len("Dario  Amodei"))

    assert standing_fact_candidate_occurrence_selector(candidate, source, occurrences) == "o3-o4"


def test_amodei_07_model_choices_map_to_exact_source_components() -> None:
    source = "Anthropic's strategy has mirrored Amodei's views toward Trump."
    occurrences = source_occurrences(derive_source_copy_view(source))
    subject = _candidate(source, start=0, end=9)

    draft = build_standing_fact_draft(
        source_segment_id="seg_fixture",
        source_text=source,
        occurrences=occurrences,
        candidates_by_label={"c1": subject},
        proposal=StandingFactProposal(
            "c1",
            "o2-o4",
            StandingFactObjectKind.LITERAL,
            "o5-o8",
        ),
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
    )

    assert draft.subject_text == "Anthropic"
    assert draft.relation_label == "strategy has mirrored"
    assert draft.object_text == "Amodei's views toward Trump"
    assert (draft.object_start, draft.object_end) == (34, 61)
    assert draft.object_mapping is StandingFactObjectMapping.EXACT_SELECTOR


def test_literal_object_anchor_is_completed_from_the_relation_boundary() -> None:
    source = "Anthropic's strategy has mirrored Amodei's views toward Trump."
    occurrences = source_occurrences(derive_source_copy_view(source))
    subject = _candidate(source, start=0, end=9)

    draft = build_standing_fact_draft(
        source_segment_id="seg_fixture",
        source_text=source,
        occurrences=occurrences,
        candidates_by_label={"c1": subject},
        proposal=StandingFactProposal(
            "c1",
            "o2-o4",
            StandingFactObjectKind.LITERAL,
            "o8",
        ),
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
    )

    assert draft.object_text == "Amodei's views toward Trump"
    assert (draft.object_start, draft.object_end) == (34, 61)
    assert draft.object_mapping is StandingFactObjectMapping.COMPLETED_POST_RELATION
    assert (
        build_standing_fact_proposition(
            draft,
            source,
            "etg_" + "a" * 24,
        ).text
        == source
    )


def test_parallel_route_still_rejects_a_literal_absent_from_authoritative_source() -> None:
    draft = _draft(relation="is", object_literal="Anthropic's founder")

    reasons = standing_fact_source_hold_reasons(
        draft,
        "Dario Amodei is Anthropic's chief executive and criticized Stargate.",
    )

    assert reasons == (StandingFactHoldReason.LITERAL_NOT_IN_SOURCE,)


def test_event_route_owns_a_standing_relation_that_overlaps_its_trigger() -> None:
    source = 'Dario Amodei described Trump as a "feudal warlord".'
    draft = _draft(
        source=source,
        relation="described",
        object_literal='"feudal warlord"',
    )

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


def _draft(
    *,
    relation: str,
    object_literal: str,
    source: str | None = None,
    subject_text: str = "Dario Amodei",
    subject_start: int = 0,
    relation_start: int = 13,
    object_start: int | None = None,
) -> StandingFactDraft:
    source = source or f"{subject_text} {relation} {object_literal}."
    resolved_object_start = (
        source.index(object_literal, relation_start + len(relation))
        if object_start is None
        else object_start
    )
    extraction_task_id = "ext_fixture"
    model_run_id = "mrn_fixture"
    parts = (
        "seg_fixture",
        "c1",
        "candidate_amodei",
        subject_text,
        str(subject_start),
        str(subject_start + len(subject_text)),
        relation,
        str(relation_start),
        str(relation_start + len(relation)),
        StandingFactObjectKind.LITERAL.value,
        "o1",
        StandingFactObjectMapping.EXACT_SELECTOR.value,
        object_literal,
        str(resolved_object_start),
        str(resolved_object_start + len(object_literal)),
        "",
        extraction_task_id,
        model_run_id,
    )
    return StandingFactDraft(
        id="sfd_" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24],
        source_segment_id=parts[0],
        subject_label=parts[1],
        subject_candidate_id=parts[2],
        subject_text=subject_text,
        subject_start=subject_start,
        subject_end=subject_start + len(subject_text),
        relation_label=relation,
        relation_start=relation_start,
        relation_end=relation_start + len(relation),
        object_kind=StandingFactObjectKind.LITERAL,
        object_selector="o1",
        object_mapping=StandingFactObjectMapping.EXACT_SELECTOR,
        object_text=object_literal,
        object_start=resolved_object_start,
        object_end=resolved_object_start + len(object_literal),
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
    )


def _candidate(source: str, *, start: int, end: int) -> MentionCandidate:
    text = source[start:end]
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    identifier = (
        "mnc_"
        + hashlib.sha256(
            "\x1f".join(("seg_fixture", source_digest, str(start), str(end), text)).encode()
        ).hexdigest()[:24]
    )
    return MentionCandidate(
        id=identifier,
        source_segment_id="seg_fixture",
        source_text_sha256=source_digest,
        start=start,
        end=end,
        text=text,
        observation_ids=("mob_" + "a" * 24,),
        type_hints=(ContextualKind.PERSON,),
    )
