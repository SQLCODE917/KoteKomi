"""Focused data-in/data-out tests for R7 parser-constituent Candidate filters."""

from __future__ import annotations

import hashlib
import inspect

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionStatus,
    EventEntityLinguisticToken,
    HeldOutFragmentRequirement,
    HeldOutGoldFragment,
    ParserConstituent,
    attached_constituents,
    build_event_frame,
    derive_selectable_constituents,
    detect_boundary_gaps,
    parse_constituent_selection_answer,
    parser_constituent_id,
    render_event_frame_selection_task,
    selectable_display_surface,
)

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


# --- Trigger filter ---------------------------------------------------------


def test_trigger_filter_removes_the_event_trigger_candidate() -> None:
    source = "Acme hired Bob"
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN"),
        _token("t2", "hired", 5, 10, None, "root", "VERB"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN"),
    )
    trigger = _trigger(source, 5, 10)
    attached = (
        _constituent(source, ("t1",), 0, 4),
        _constituent(source, ("t2",), 5, 10),
        _constituent(source, ("t3",), 11, 14),
    )
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    spans = {(item.constituent_range.start, item.constituent_range.end) for item in result}
    assert spans == {(0, 4), (11, 14)}
    assert (5, 10) not in spans


# --- Core filter ------------------------------------------------------------


def test_core_filter_removes_the_segment_core_span_candidate() -> None:
    source = "Acme hired Bob"
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN"),
        _token("t2", "hired", 5, 10, None, "root", "VERB"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN"),
    )
    trigger = _trigger(source, 5, 10)
    attached = (
        _constituent(source, ("t1", "t2", "t3"), 0, 14),
        _constituent(source, ("t1",), 0, 4),
        _constituent(source, ("t3",), 11, 14),
    )
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    spans = {(item.constituent_range.start, item.constituent_range.end) for item in result}
    assert (0, 14) not in spans
    assert (0, 4) in spans
    assert (11, 14) in spans


# --- Function-word filter ---------------------------------------------------


@pytest.mark.parametrize(
    ("surface", "pos"),
    [
        ("of", "ADP"),
        ("is", "AUX"),
        ("and", "CCONJ"),
        ("the", "DET"),
        ("to", "PART"),
        ("that", "SCONJ"),
    ],
)
def test_function_word_filter_removes_function_word_only_candidate(surface: str, pos: str) -> None:
    source = f"Go {surface}"
    start = 3
    end = start + len(surface)
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", surface, start, end, "t1", "dep", pos),
    )
    trigger = _trigger(source, 0, 2)
    attached = (_constituent(source, ("t2",), start, end),)
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert result == ()


def test_function_word_filter_keeps_candidate_with_content_token() -> None:
    source = "Go to school"
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", "to", 3, 5, "t3", "case", "ADP"),
        _token("t3", "school", 6, 12, "t1", "obl", "NOUN"),
    )
    trigger = _trigger(source, 0, 2)
    attached = (_constituent(source, ("t2", "t3"), 3, 12),)
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert result == attached


# --- Artifact filter --------------------------------------------------------


@pytest.mark.parametrize(
    ("surface", "pos"),
    [("5", "NUM"), (")", "PUNCT"), ("$", "SYM")],
)
def test_artifact_filter_removes_artifact_only_candidate(surface: str, pos: str) -> None:
    source = f"Go {surface}"
    start = 3
    end = start + len(surface)
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", surface, start, end, "t1", "dep", pos),
    )
    trigger = _trigger(source, 0, 2)
    attached = (_constituent(source, ("t2",), start, end),)
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert result == ()


def test_artifact_filter_keeps_mixed_candidate_with_content_token() -> None:
    source = "Go 5 dollars"
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", "5", 3, 4, "t3", "nummod", "NUM"),
        _token("t3", "dollars", 5, 12, "t1", "obj", "NOUN"),
    )
    trigger = _trigger(source, 0, 2)
    attached = (_constituent(source, ("t2", "t3"), 3, 12),)
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert result == attached


# --- Dedup filter -----------------------------------------------------------


def test_dedup_surface_strips_leading_trailing_whitespace_and_trailing_punctuation() -> None:
    assert selectable_display_surface("  fired Bob.!  ") == "fired Bob"
    assert selectable_display_surface("Bob,;:!?..") == "Bob"
    assert selectable_display_surface("plain") == "plain"


def test_dedup_surface_of_punctuation_or_whitespace_only_is_empty() -> None:
    assert selectable_display_surface("  .? !  ") == ""


def test_dedup_filter_drops_candidate_with_empty_surface() -> None:
    source = "Go of"
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", "of", 3, 5, "t1", "case", "ADP"),
    )
    trigger = _trigger(source, 0, 2)
    attached = (_constituent(source, ("t2",), 3, 5),)
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert result == ()


def test_dedup_filter_keeps_the_earliest_candidate_by_source_offset() -> None:
    source = "Bob fired Bob."
    tokens = (
        _token("t1", "Bob", 0, 3, "t2", "nsubj", "NOUN"),
        _token("t2", "fired", 4, 9, None, "root", "VERB"),
        _token("t3", "Bob", 10, 13, "t2", "obj", "NOUN"),
        _token("t4", ".", 13, 14, "t2", "punct", "PUNCT"),
    )
    trigger = _trigger(source, 4, 9)
    attached = (
        _constituent(source, ("t1",), 0, 3),
        _constituent(source, ("t3", "t4"), 10, 14),
    )
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    spans = [(item.constituent_range.start, item.constituent_range.end) for item in result]
    assert spans == [(0, 3)]


# --- Nested filter ----------------------------------------------------------


def test_nested_filter_removes_contained_candidate_when_superset_adds_only_function_words() -> None:
    source = "Hire the team"
    tokens = (
        _token("t1", "Hire", 0, 4, None, "root", "VERB"),
        _token("t2", "the", 5, 8, "t3", "det", "DET"),
        _token("t3", "team", 9, 13, "t1", "obj", "NOUN"),
    )
    trigger = _trigger(source, 0, 4)
    attached = (
        _constituent(source, ("t2", "t3"), 5, 13),
        _constituent(source, ("t3",), 9, 13),
    )
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    spans = [(item.constituent_range.start, item.constituent_range.end) for item in result]
    assert spans == [(5, 13)]


def test_nested_filter_keeps_contained_candidate_when_superset_adds_content_token() -> None:
    source = "Hire the blue team"
    tokens = (
        _token("t1", "Hire", 0, 4, None, "root", "VERB"),
        _token("t2", "the", 5, 8, "t4", "det", "DET"),
        _token("t3", "blue", 9, 13, "t4", "amod", "ADJ"),
        _token("t4", "team", 14, 18, "t1", "obj", "NOUN"),
    )
    trigger = _trigger(source, 0, 4)
    attached = (
        _constituent(source, ("t2", "t3", "t4"), 5, 18),
        _constituent(source, ("t4",), 14, 18),
    )
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    spans = {(item.constituent_range.start, item.constituent_range.end) for item in result}
    assert spans == {(5, 18), (14, 18)}


# --- Selectable derivation --------------------------------------------------


def test_selectable_list_is_a_source_ordered_subsequence_of_attached() -> None:
    source = "Acme hired Bob"
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN"),
        _token("t2", "hired", 5, 10, None, "root", "VERB"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN"),
    )
    trigger = _trigger(source, 5, 10)
    attached = (
        _constituent(source, ("t1",), 0, 4),
        _constituent(source, ("t2",), 5, 10),
        _constituent(source, ("t3",), 11, 14),
    )
    result = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert result == (attached[0], attached[2])


def test_selectable_derivation_reads_no_gold_and_invokes_no_model() -> None:
    parameters = set(inspect.signature(derive_selectable_constituents).parameters)
    assert not any("gold" in name for name in parameters)
    assert not any("model" in name for name in parameters)


# --- Rendering and non-regression -------------------------------------------


def test_renderer_names_one_label_per_selectable_and_none_for_removed() -> None:
    source = "Acme hired Bob"
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN"),
        _token("t2", "hired", 5, 10, None, "root", "VERB"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN"),
    )
    inventory = ConstituentCandidateInventory(
        event_id=EVENT,
        source_text_sha256=_digest(source),
        constituents=(
            _constituent(source, ("t1",), 0, 4),
            _constituent(source, ("t2",), 5, 10),
            _constituent(source, ("t3",), 11, 14),
        ),
    )
    frame = build_event_frame(
        event_id=EVENT,
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
        inventory=inventory,
    )
    attached = attached_constituents(
        inventory=inventory,
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
    )
    selectable = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=frame.trigger
    )
    task = render_event_frame_selection_task(
        event_id=EVENT,
        source_text=source,
        inventory=inventory,
        selectable=selectable,
        frame=frame,
    )
    assert task.constituent_labels == ("C1", "C2")
    candidates = task.rendered_input.split("Candidates:")[1]
    assert "Acme" in candidates
    assert "Bob" in candidates
    assert "hired" not in candidates


def test_parser_and_scorer_share_the_filtered_label_set() -> None:
    source = "Acme hired Bob"
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN"),
        _token("t2", "hired", 5, 10, None, "root", "VERB"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN"),
    )
    inventory = ConstituentCandidateInventory(
        event_id=EVENT,
        source_text_sha256=_digest(source),
        constituents=(
            _constituent(source, ("t1",), 0, 4),
            _constituent(source, ("t2",), 5, 10),
            _constituent(source, ("t3",), 11, 14),
        ),
    )
    frame = build_event_frame(
        event_id=EVENT,
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
        inventory=inventory,
    )
    attached = attached_constituents(
        inventory=inventory,
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
    )
    selectable = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=frame.trigger
    )
    task = render_event_frame_selection_task(
        event_id=EVENT,
        source_text=source,
        inventory=inventory,
        selectable=selectable,
        frame=frame,
    )
    selected = parse_constituent_selection_answer(raw_answer="C1,C2", task=task)
    assert selected.status is ConstituentSelectionStatus.SELECTED
    assert selected.selected_label_indexes == (1, 2)
    rejected = parse_constituent_selection_answer(raw_answer="C3", task=task)
    assert rejected.status is ConstituentSelectionStatus.REJECTED


def test_filters_never_change_the_inventory_the_boundary_gap_detector_reads() -> None:
    source = "Acme hired Bob"
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN"),
        _token("t2", "hired", 5, 10, None, "root", "VERB"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN"),
    )
    inventory = ConstituentCandidateInventory(
        event_id=EVENT,
        source_text_sha256=_digest(source),
        constituents=(
            _constituent(source, ("t1",), 0, 4),
            _constituent(source, ("t1", "t2", "t3"), 0, 14),
            _constituent(source, ("t2",), 5, 10),
            _constituent(source, ("t3",), 11, 14),
        ),
    )
    gold = {
        EVENT: (
            HeldOutGoldFragment(
                fragment_id="PGF-AHE-001-01",
                start=0,
                end=14,
                text="Acme hired Bob",
                requirements=(HeldOutFragmentRequirement.CORE_EVENT,),
            ),
            HeldOutGoldFragment(
                fragment_id="PGF-AHE-001-02",
                start=5,
                end=10,
                text="hired",
                requirements=(HeldOutFragmentRequirement.CORE_EVENT,),
            ),
        ),
    }
    before = detect_boundary_gaps(gold_fragments=gold, inventories={EVENT: inventory})
    assert before == ()
    trigger = _trigger(source, 5, 10)
    selectable = derive_selectable_constituents(
        attached=tuple(inventory.constituents),
        source_text=source,
        tokens=tokens,
        trigger=trigger,
    )
    spans = {(item.constituent_range.start, item.constituent_range.end) for item in selectable}
    assert (0, 14) not in spans
    assert (5, 10) not in spans
    after = detect_boundary_gaps(gold_fragments=gold, inventories={EVENT: inventory})
    assert after == ()


def test_an_event_with_only_function_word_candidates_has_an_empty_selectable_list() -> None:
    source = "Go of"
    tokens = (
        _token("t1", "Go", 0, 2, None, "root", "VERB"),
        _token("t2", "of", 3, 5, "t1", "case", "ADP"),
    )
    trigger = _trigger(source, 0, 2)
    attached = (_constituent(source, ("t2",), 3, 5),)
    selectable = derive_selectable_constituents(
        attached=attached, source_text=source, tokens=tokens, trigger=trigger
    )
    assert selectable == ()
