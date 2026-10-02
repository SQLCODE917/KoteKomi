"""Focused data-in/data-out tests for the R9 Selectable-pool floor."""

from __future__ import annotations

import hashlib
import inspect

import pytest
from kotekomi_application import (
    SELECTABLE_POOL_FLOOR_DEFAULT,
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionStatus,
    EventEntityLinguisticToken,
    EventFrame,
    HeldOutFragmentRequirement,
    HeldOutGoldFragment,
    ParserConstituent,
    PoolFloorRelaxationRecord,
    SelectablePoolDerivation,
    build_calibrated_residual_ownership_report,
    derive_selectable_constituents,
    detect_boundary_gaps,
    parse_constituent_selection_answer,
    parser_constituent_id,
    render_event_frame_selection_task,
)
from pydantic import ValidationError

EVENT = "AHE-001"


def _digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def _token(
    token_id: str,
    text: str,
    start: int,
    end: int,
    head: str | None,
    deprel: str,
    pos: str,
    sentence_id: str = "s1",
) -> EventEntityLinguisticToken:
    return EventEntityLinguisticToken(
        token_id=token_id,
        sentence_id=sentence_id,
        text=text,
        start=start,
        end=end,
        lemma=text.casefold(),
        part_of_speech=pos,
        dependency_relation=deprel,
        head_token_id=head,
    )


def _constituent(
    source: str, token_ids: tuple[str, ...], start: int, end: int
) -> ParserConstituent:
    return ParserConstituent(
        constituent_id=parser_constituent_id(_digest(source), start, end),
        event_id=EVENT,
        source_text_sha256=_digest(source),
        constituent_range=AttachmentSourceRange(start=start, end=end, text=source[start:end]),
        token_ids=token_ids,
    )


def _trigger(source: str, start: int, end: int) -> AttachmentSourceRange:
    return AttachmentSourceRange(start=start, end=end, text=source[start:end])


def _seven_parts() -> tuple[
    str,
    tuple[EventEntityLinguisticToken, ...],
    AttachmentSourceRange,
    tuple[ParserConstituent, ...],
    ConstituentCandidateInventory,
]:
    """Return the 7-attached -> 2-selectable -> floor-relaxed Event scenario parts."""
    source = "Hire Bob the team and 5"
    tokens = (
        _token("t1", "Hire", 0, 4, None, "root", "VERB"),
        _token("t2", "Bob", 5, 8, "t1", "obj", "NOUN"),
        _token("t3", "the", 9, 12, "t4", "det", "DET"),
        _token("t4", "team", 13, 17, "t1", "obl", "NOUN"),
        _token("t5", "and", 18, 21, "t1", "cc", "CCONJ"),
        _token("t6", "5", 22, 23, "t1", "nummod", "NUM"),
    )
    trigger = _trigger(source, 0, 4)
    attached = (
        _constituent(source, ("t1",), 0, 4),
        _constituent(source, ("t1", "t2", "t3", "t4", "t5", "t6"), 0, 23),
        _constituent(source, ("t2",), 5, 8),
        _constituent(source, ("t3", "t4"), 9, 17),
        _constituent(source, ("t4",), 13, 17),
        _constituent(source, ("t5",), 18, 21),
        _constituent(source, ("t6",), 22, 23),
    )
    inventory = ConstituentCandidateInventory(
        event_id=EVENT,
        source_text_sha256=_digest(source),
        constituents=attached,
    )
    return source, tokens, trigger, attached, inventory


# --- Floor and relaxation ---------------------------------------------------


def test_default_floor_equals_three() -> None:
    assert SELECTABLE_POOL_FLOOR_DEFAULT == 3
    default = inspect.signature(derive_selectable_constituents).parameters["floor"].default
    assert default == SELECTABLE_POOL_FLOOR_DEFAULT


def test_derivation_reads_no_gold_and_invokes_no_model() -> None:
    parameters = set(inspect.signature(derive_selectable_constituents).parameters)
    assert not any("gold" in name for name in parameters)
    assert not any("model" in name for name in parameters)
    assert "inventory" not in parameters


def test_seven_to_two_narrows_then_relaxes_to_the_lowest_level_meeting_the_floor() -> None:
    source, tokens, trigger, attached, _ = _seven_parts()
    derivation = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert isinstance(derivation, SelectablePoolDerivation)
    assert derivation.relaxation_level == 1
    assert derivation.selectable_count_before == 2
    assert derivation.selectable_count_after == 3
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in derivation.selectable
    }
    assert spans == {(5, 8), (9, 17), (13, 17)}

    # Reverse skip order: at level 1 the nested filter is skipped (the contained
    # "team" returns) while the function-word and artifact filters still apply.
    by_surface = {item.constituent_range.text for item in derivation.selectable}
    assert "team" in by_surface
    assert "the team" in by_surface
    assert "Bob" in by_surface
    assert "and" not in by_surface
    assert "5" not in by_surface


def test_hard_filters_stay_applied_at_relaxation_level_four() -> None:
    source = "Hire the"
    tokens = (
        _token("t1", "Hire", 0, 4, None, "root", "VERB"),
        _token("t2", "the", 5, 8, "t1", "det", "DET"),
    )
    trigger = _trigger(source, 0, 4)
    attached = (
        _constituent(source, ("t1",), 0, 4),
        _constituent(source, ("t1", "t2"), 0, 8),
        _constituent(source, ("t2",), 5, 8),
    )
    derivation = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert derivation.relaxation_level == 4
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in derivation.selectable
    }
    assert (0, 4) not in spans
    assert (0, 8) not in spans
    assert (5, 8) in spans


def test_attached_below_floor_signals_no_selectable() -> None:
    source = "Go Bob"
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", "Bob", 3, 6, "t1", "obj", "NOUN"),
    )
    trigger = _trigger(source, 0, 2)
    attached = (
        _constituent(source, ("t1",), 0, 2),
        _constituent(source, ("t2",), 3, 6),
    )
    assert len(attached) < SELECTABLE_POOL_FLOOR_DEFAULT
    derivation = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    # The runner routes any Event whose survivor count sits below the floor to
    # residual review with reason ``no_selectable`` and renders no task.
    assert derivation.relaxation_level == 4
    assert derivation.selectable_count_after < SELECTABLE_POOL_FLOOR_DEFAULT


def test_relaxed_derivation_does_not_change_the_boundary_detector_inventory() -> None:
    source, tokens, trigger, attached, inventory = _seven_parts()
    gold = {
        EVENT: (
            HeldOutGoldFragment(
                fragment_id="PGF-AHE-001-01",
                start=0,
                end=23,
                text=source,
                requirements=(HeldOutFragmentRequirement.CORE_EVENT,),
            ),
        ),
    }
    before = detect_boundary_gaps(gold_fragments=gold, inventories={EVENT: inventory})
    assert before == ()
    derivation = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert derivation.relaxation_level > 0
    after = detect_boundary_gaps(gold_fragments=gold, inventories={EVENT: inventory})
    assert after == ()


# --- Rendering and report ---------------------------------------------------


def test_parser_and_scorer_share_the_relaxed_label_set() -> None:
    source, tokens, trigger, attached, inventory = _seven_parts()
    frame = EventFrame(
        event_id=EVENT,
        trigger=trigger,
        core_constituents=(),
    )
    derivation = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert derivation.relaxation_level == 1
    task = render_event_frame_selection_task(
        event_id=EVENT,
        source_text=source,
        inventory=inventory,
        selectable=derivation.selectable,
        frame=frame,
    )
    assert task.constituent_labels == ("C1", "C2", "C3")
    selected = parse_constituent_selection_answer(raw_answer="C1,C3", task=task)
    assert selected.status is ConstituentSelectionStatus.SELECTED
    assert selected.selected_label_indexes == (1, 3)
    rejected = parse_constituent_selection_answer(raw_answer="C4", task=task)
    assert rejected.status is ConstituentSelectionStatus.REJECTED


def test_report_records_one_relaxation_record_per_relaxed_event() -> None:
    first = PoolFloorRelaxationRecord(
        event_id="AHE-001",
        relaxation_level=1,
        selectable_count_before=2,
        selectable_count_after=3,
    )
    second = PoolFloorRelaxationRecord(
        event_id="AHE-002",
        relaxation_level=3,
        selectable_count_before=1,
        selectable_count_after=3,
    )
    report = build_calibrated_residual_ownership_report(
        boundary_gaps=(),
        selection_routing=(),
        residual_review_event_ids=(),
        pool_floor_relaxation=(first, second),
        model_execution_count=0,
    )
    assert report.pool_floor_relaxation == (first, second)


def test_relaxation_record_rejects_negative_counts_or_out_of_range_level() -> None:
    with pytest.raises(ValidationError):
        PoolFloorRelaxationRecord(
            event_id="AHE-001",
            relaxation_level=5,
            selectable_count_before=0,
            selectable_count_after=0,
        )
    with pytest.raises(ValidationError):
        PoolFloorRelaxationRecord(
            event_id="AHE-001",
            relaxation_level=0,
            selectable_count_before=-1,
            selectable_count_after=0,
        )