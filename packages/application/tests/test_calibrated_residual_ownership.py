"""Focused data-in/data-out tests for R6 calibrated residual ownership (Application layer)."""

from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    BoundaryGap,
    CalibratedResidualOwnershipReport,
    CandidateAttachmentMark,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    EventEntityLinguisticToken,
    HeldOutFragmentRequirement,
    HeldOutGoldFragment,
    ParserConstituent,
    ResidualReviewReason,
    SelectionRoutingDecision,
    SelectionScore,
    attached_constituents,
    augment_candidate_inventory_with_segment_core,
    build_calibrated_residual_ownership_report,
    build_event_frame,
    build_residual_review_set,
    calibrated_residual_ownership_report_fingerprint,
    derive_selectable_constituents,
    detect_boundary_gaps,
    mark_candidate_attachment,
    parser_constituent_id,
    render_event_frame_selection_task,
    route_selection_scores,
)

OK_SOURCE = "Acme fired Bob."
BRACKET_SOURCE = "[1] Acme fired Bob."


def _tokens(
    source: str, specs: list[tuple[str, str | None, str, str, str]]
) -> tuple[EventEntityLinguisticToken, ...]:
    positions: dict[str, tuple[int, int]] = {}
    offset = 0
    for word, *_ in specs:
        start = source.index(word, offset)
        end = start + len(word)
        positions[word] = (start, end)
        offset = end
    by_word = {word: f"t{i}" for i, word in enumerate(positions, start=1)}
    tokens: list[EventEntityLinguisticToken] = []
    for word, head, deprel, lemma, pos in specs:
        start, end = positions[word]
        tokens.append(
            EventEntityLinguisticToken(
                token_id=by_word[word],
                sentence_id="s1",
                text=word,
                start=start,
                end=end,
                lemma=lemma,
                part_of_speech=pos,
                dependency_relation=deprel,
                head_token_id=by_word[head] if head else None,
            )
        )
    return tuple(tokens)


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
        lemma=text.lower(),
        part_of_speech=pos,
        dependency_relation=deprel,
        head_token_id=head,
    )


def _digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def _constituent(
    source: str, event_id: str, token_ids: tuple[str, ...], start: int, end: int
) -> ParserConstituent:
    return ParserConstituent(
        constituent_id=parser_constituent_id(_digest(source), start, end),
        event_id=event_id,
        source_text_sha256=_digest(source),
        constituent_range=AttachmentSourceRange(start=start, end=end, text=source[start:end]),
        token_ids=token_ids,
    )


def _inventory(
    event_id: str, source: str, constituents: tuple[ParserConstituent, ...]
) -> ConstituentCandidateInventory:
    return ConstituentCandidateInventory(
        event_id=event_id,
        source_text_sha256=_digest(source),
        constituents=constituents,
    )


def _gold(
    source: str,
    fragment_id: str,
    start: int,
    end: int,
    requirements: tuple[HeldOutFragmentRequirement, ...],
) -> HeldOutGoldFragment:
    return HeldOutGoldFragment(
        fragment_id=fragment_id,
        start=start,
        end=end,
        text=source[start:end],
        requirements=requirements,
    )


def _ok_tokens() -> tuple[EventEntityLinguisticToken, ...]:
    return _tokens(
        OK_SOURCE,
        [
            ("Acme", "fired", "nsubj", "acme", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
        ],
    )


def _token_inventory() -> ConstituentCandidateInventory:
    source = OK_SOURCE
    return _inventory(
        "AHE-001",
        source,
        (
            _constituent(source, "AHE-001", ("t1",), 0, 4),
            _constituent(source, "AHE-001", ("t2",), 5, 10),
            _constituent(source, "AHE-001", ("t3",), 11, 14),
        ),
    )


def _score(
    event_id: str,
    label: str,
    log_probability: float | None,
    censored: bool,
) -> SelectionScore:
    return SelectionScore(
        event_id=event_id,
        label=label,
        log_probability=log_probability,
        censored=censored,
    )


def _rejected_answer(event_id: str) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=ConstituentSelectionStatus.REJECTED,
        selected_label_indexes=(),
    )


# --- Boundary coverage ---------------------------------------------------------


def test_segment_core_augmentation_covers_the_full_segment_fragment() -> None:
    tokens = _ok_tokens()
    base = _token_inventory()
    augmented = augment_candidate_inventory_with_segment_core(
        inventory=base,
        source_text=OK_SOURCE,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
    )
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in augmented.constituents
    }
    assert (0, 15) in spans
    gold = (_gold(OK_SOURCE, "PGF-AHE-001-01", 0, 15, (HeldOutFragmentRequirement.CORE_EVENT,)),)
    assert (
        detect_boundary_gaps(gold_fragments={"AHE-001": gold}, inventories={"AHE-001": augmented})
        == ()
    )


def test_uncovered_fragment_raises_a_typed_boundary_gap() -> None:
    base = _token_inventory()
    gold = (_gold(OK_SOURCE, "PGF-AHE-001-01", 0, 15, (HeldOutFragmentRequirement.CORE_EVENT,)),)
    gaps = detect_boundary_gaps(gold_fragments={"AHE-001": gold}, inventories={"AHE-001": base})
    assert len(gaps) == 1
    gap = gaps[0]
    assert isinstance(gap, BoundaryGap)
    assert gap.fragment_id == "PGF-AHE-001-01"
    assert (gap.start, gap.end) == (0, 15)


def test_leading_citation_marker_is_stripped_from_the_segment_core() -> None:
    source = BRACKET_SOURCE
    tokens = _tokens(
        source,
        [
            ("[", None, "punct", "[", "PUNCT"),
            ("1", None, "nummod", "1", "NUM"),
            ("]", None, "punct", "]", "PUNCT"),
            ("Acme", "fired", "nsubj", "acme", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
        ],
    )
    base = _inventory(
        "AHE-001",
        source,
        (
            _constituent(source, "AHE-001", ("t4",), 4, 8),
            _constituent(source, "AHE-001", ("t5",), 9, 14),
            _constituent(source, "AHE-001", ("t6",), 15, 18),
        ),
    )
    augmented = augment_candidate_inventory_with_segment_core(
        inventory=base,
        source_text=source,
        tokens=tokens,
        trigger_head_start=9,
        trigger_head_end=14,
    )
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in augmented.constituents
    }
    assert (4, 19) in spans
    gold = (_gold(source, "PGF-AHE-001-01", 4, 19, (HeldOutFragmentRequirement.CORE_EVENT,)),)
    assert (
        detect_boundary_gaps(gold_fragments={"AHE-001": gold}, inventories={"AHE-001": augmented})
        == ()
    )


def test_segment_core_spans_whole_segment_across_multiple_sentences() -> None:
    source = "Acme fired Bob. Contractors left their posts."
    tokens = (
        _token("t1", "Acme", 0, 4, "t2", "nsubj", "NOUN", "s1"),
        _token("t2", "fired", 5, 10, None, "root", "VERB", "s1"),
        _token("t3", "Bob", 11, 14, "t2", "obj", "NOUN", "s1"),
        _token("t4", ".", 14, 15, None, "punct", "PUNCT", "s1"),
        _token("t5", "Contractors", 16, 27, "t6", "nsubj", "NOUN", "s2"),
        _token("t6", "left", 28, 32, None, "root", "VERB", "s2"),
        _token("t7", "their", 33, 38, "t8", "det", "DET", "s2"),
        _token("t8", "posts", 39, 44, "t6", "obj", "NOUN", "s2"),
        _token("t9", ".", 44, 45, None, "punct", "PUNCT", "s2"),
    )
    base = _inventory(
        "AHE-001",
        source,
        (_constituent(source, "AHE-001", ("t2",), 5, 10),),
    )
    augmented = augment_candidate_inventory_with_segment_core(
        inventory=base,
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
    )
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in augmented.constituents
    }
    assert (0, len(source)) in spans


def test_leading_citation_run_is_stripped_from_the_segment_core() -> None:
    source = "[1][2] Acme fired Bob."
    tokens = (
        _token("t1", "[", 0, 1, None, "punct", "PUNCT"),
        _token("t2", "1", 1, 2, None, "nummod", "NUM"),
        _token("t3", "]", 2, 3, None, "punct", "PUNCT"),
        _token("t4", "[", 3, 4, None, "punct", "PUNCT"),
        _token("t5", "2", 4, 5, None, "nummod", "NUM"),
        _token("t6", "]", 5, 6, None, "punct", "PUNCT"),
        _token("t7", "Acme", 7, 11, "t8", "nsubj", "NOUN"),
        _token("t8", "fired", 12, 17, None, "root", "VERB"),
        _token("t9", "Bob", 18, 21, "t8", "obj", "NOUN"),
    )
    base = _inventory(
        "AHE-001",
        source,
        (_constituent(source, "AHE-001", ("t8",), 12, 17),),
    )
    augmented = augment_candidate_inventory_with_segment_core(
        inventory=base,
        source_text=source,
        tokens=tokens,
        trigger_head_start=12,
        trigger_head_end=17,
    )
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in augmented.constituents
    }
    assert (7, len(source)) in spans


def test_trailing_citation_run_is_stripped_from_the_segment_core() -> None:
    source = "Acme fired Bob. [3]"
    tokens = _tokens(
        source,
        [
            ("Acme", "fired", "nsubj", "acme", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
            ("[", None, "punct", "[", "PUNCT"),
            ("3", None, "nummod", "3", "NUM"),
            ("]", None, "punct", "]", "PUNCT"),
        ],
    )
    base = _inventory(
        "AHE-001",
        source,
        (_constituent(source, "AHE-001", ("t2",), 5, 10),),
    )
    augmented = augment_candidate_inventory_with_segment_core(
        inventory=base,
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
    )
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in augmented.constituents
    }
    assert (0, 15) in spans


# --- Attachment ladder ---------------------------------------------------------


def test_attachment_marks_the_trigger_head_as_attached() -> None:
    tokens = _ok_tokens()
    candidate = _constituent(OK_SOURCE, "AHE-001", ("t2",), 5, 10)
    assert (
        mark_candidate_attachment(
            candidate=candidate,
            source_text=OK_SOURCE,
            tokens=tokens,
            trigger_head_start=5,
            trigger_head_end=10,
        )
        is CandidateAttachmentMark.ATTACHED
    )


def test_attachment_marks_a_direct_subject_as_attached() -> None:
    tokens = _ok_tokens()
    candidate = _constituent(OK_SOURCE, "AHE-001", ("t1",), 0, 4)
    assert (
        mark_candidate_attachment(
            candidate=candidate,
            source_text=OK_SOURCE,
            tokens=tokens,
            trigger_head_start=5,
            trigger_head_end=10,
        )
        is CandidateAttachmentMark.ATTACHED
    )


def test_attachment_marks_a_distant_non_complement_candidate_for_model_review() -> None:
    source = "Acme's CEO fired Bob."
    tokens = _tokens(
        source,
        [
            ("Acme's", "CEO", "nmod:poss", "acme", "NOUN"),
            ("CEO", "fired", "nsubj", "ceo", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
        ],
    )
    candidate = _constituent(source, "AHE-001", ("t1",), 0, 6)
    assert (
        mark_candidate_attachment(
            candidate=candidate,
            source_text=source,
            tokens=tokens,
            trigger_head_start=11,
            trigger_head_end=16,
        )
        is CandidateAttachmentMark.MODEL_REVIEW
    )


def test_attachment_marks_a_cross_sentence_candidate_as_not_attached() -> None:
    source = "Acme fired Bob. Sam left."
    tokens = (
        EventEntityLinguisticToken(
            token_id="t1",
            sentence_id="s1",
            text="Acme",
            start=0,
            end=4,
            lemma="acme",
            part_of_speech="NOUN",
            dependency_relation="nsubj",
            head_token_id="t2",
        ),
        EventEntityLinguisticToken(
            token_id="t2",
            sentence_id="s1",
            text="fired",
            start=5,
            end=10,
            lemma="fire",
            part_of_speech="VERB",
            dependency_relation="root",
            head_token_id=None,
        ),
        EventEntityLinguisticToken(
            token_id="t3",
            sentence_id="s1",
            text="Bob",
            start=11,
            end=14,
            lemma="bob",
            part_of_speech="NOUN",
            dependency_relation="obj",
            head_token_id="t2",
        ),
        EventEntityLinguisticToken(
            token_id="t4",
            sentence_id="s2",
            text="Sam",
            start=15,
            end=18,
            lemma="sam",
            part_of_speech="NOUN",
            dependency_relation="nsubj",
            head_token_id="t5",
        ),
        EventEntityLinguisticToken(
            token_id="t5",
            sentence_id="s2",
            text="left",
            start=19,
            end=23,
            lemma="leave",
            part_of_speech="VERB",
            dependency_relation="root",
            head_token_id=None,
        ),
    )
    candidate = _constituent(source, "AHE-001", ("t4",), 15, 18)
    assert (
        mark_candidate_attachment(
            candidate=candidate,
            source_text=source,
            tokens=tokens,
            trigger_head_start=5,
            trigger_head_end=10,
        )
        is CandidateAttachmentMark.NOT_ATTACHED
    )


# --- Event frame ---------------------------------------------------------------


def test_event_frame_renders_trigger_and_core_constituents_only() -> None:
    tokens = _ok_tokens()
    inventory = _token_inventory()
    frame = build_event_frame(
        event_id="AHE-001",
        source_text=OK_SOURCE,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
        inventory=inventory,
    )
    assert frame.trigger.start == 5 and frame.trigger.end == 10
    assert [(item.start, item.end) for item in frame.core_constituents] == [(0, 4), (11, 14)]
    assert (5, 10) not in [(item.start, item.end) for item in frame.core_constituents]


def test_event_frame_excludes_a_non_core_modifier() -> None:
    source = "Acme fired Bob yesterday."
    tokens = _tokens(
        source,
        [
            ("Acme", "fired", "nsubj", "acme", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
            ("yesterday", "fired", "advmod", "yesterday", "NOUN"),
        ],
    )
    inventory = _inventory(
        "AHE-001",
        source,
        (
            _constituent(source, "AHE-001", ("t1",), 0, 4),
            _constituent(source, "AHE-001", ("t2",), 5, 10),
            _constituent(source, "AHE-001", ("t3",), 11, 14),
            _constituent(source, "AHE-001", ("t4",), 15, 24),
        ),
    )
    frame = build_event_frame(
        event_id="AHE-001",
        source_text=source,
        tokens=tokens,
        trigger_head_start=5,
        trigger_head_end=10,
        inventory=inventory,
    )
    assert [(item.start, item.end) for item in frame.core_constituents] == [(0, 4), (11, 14)]


def test_event_frame_selection_task_renders_only_selectable_candidates() -> None:
    source = "Acme's CEO fired Bob."
    tokens = _tokens(
        source,
        [
            ("Acme's", "CEO", "nmod:poss", "acme", "NOUN"),
            ("CEO", "fired", "nsubj", "ceo", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
        ],
    )
    inventory = _inventory(
        "AHE-001",
        source,
        (
            _constituent(source, "AHE-001", ("t1",), 0, 6),
            _constituent(source, "AHE-001", ("t2",), 7, 10),
            _constituent(source, "AHE-001", ("t3",), 11, 16),
            _constituent(source, "AHE-001", ("t4",), 17, 20),
        ),
    )
    frame = build_event_frame(
        event_id="AHE-001",
        source_text=source,
        tokens=tokens,
        trigger_head_start=11,
        trigger_head_end=16,
        inventory=inventory,
    )
    attached = attached_constituents(
        inventory=inventory,
        source_text=source,
        tokens=tokens,
        trigger_head_start=11,
        trigger_head_end=16,
    )
    selectable = derive_selectable_constituents(
        attached=attached,
        source_text=source,
        tokens=tokens,
        trigger=frame.trigger,
    ).selectable
    task = render_event_frame_selection_task(
        event_id="AHE-001",
        source_text=source,
        inventory=inventory,
        selectable=selectable,
        frame=frame,
    )
    assert task.event_id == "AHE-001"
    assert "Event: fired" in task.rendered_input
    assert task.constituent_labels == ("C1", "C2")
    candidates = task.rendered_input.split("Candidates:")[1]
    assert "CEO" in candidates
    assert "Bob" in candidates
    assert "fired" not in candidates
    assert "Acme's" not in candidates


def test_attached_constituents_excludes_model_review_candidates() -> None:
    source = "Acme's CEO fired Bob."
    tokens = _tokens(
        source,
        [
            ("Acme's", "CEO", "nmod:poss", "acme", "NOUN"),
            ("CEO", "fired", "nsubj", "ceo", "NOUN"),
            ("fired", None, "root", "fire", "VERB"),
            ("Bob", "fired", "obj", "bob", "NOUN"),
        ],
    )
    inventory = _inventory(
        "AHE-001",
        source,
        (
            _constituent(source, "AHE-001", ("t1",), 0, 6),
            _constituent(source, "AHE-001", ("t2",), 7, 10),
            _constituent(source, "AHE-001", ("t3",), 11, 16),
            _constituent(source, "AHE-001", ("t4",), 17, 20),
        ),
    )
    attached = attached_constituents(
        inventory=inventory,
        source_text=source,
        tokens=tokens,
        trigger_head_start=11,
        trigger_head_end=16,
    )
    attached_spans = {
        (item.constituent_range.start, item.constituent_range.end) for item in attached
    }
    assert attached_spans == {(7, 10), (11, 16), (17, 20)}


# --- Calibration routing -------------------------------------------------------


def test_below_threshold_score_routes_to_residual_review() -> None:
    scores = {"AHE-001": _score("AHE-001", "C2", -2.0, False)}
    routing = route_selection_scores(scores=scores, threshold=-1.0)
    assert routing[0].decision is SelectionRoutingDecision.RESIDUAL_REVIEW
    assert routing[0].reason is ResidualReviewReason.BELOW_THRESHOLD


def test_above_threshold_score_reaches_accepted_selection() -> None:
    scores = {"AHE-001": _score("AHE-001", "C2", -0.5, False)}
    routing = route_selection_scores(scores=scores, threshold=-1.0)
    assert routing[0].decision is SelectionRoutingDecision.ACCEPTED_SELECTION
    assert routing[0].reason is None


def test_censored_score_lists_its_event_in_the_residual_review_set() -> None:
    scores = {
        "AHE-001": _score("AHE-001", "C1", -0.3, False),
        "AHE-002": _score("AHE-002", "C2", None, True),
    }
    residual = build_residual_review_set(scores=scores, threshold=-2.0)
    assert residual.event_ids == ("AHE-002",)
    routing = route_selection_scores(scores=scores, threshold=-2.0)
    censored = next(item for item in routing if item.event_id == "AHE-002")
    assert censored.reason is ResidualReviewReason.CENSORED


def test_none_selection_routes_to_residual_review() -> None:
    scores = {"AHE-001": _score("AHE-001", "NONE", -0.2, False)}
    routing = route_selection_scores(scores=scores, threshold=-10.0)
    assert routing[0].decision is SelectionRoutingDecision.RESIDUAL_REVIEW
    assert routing[0].reason is ResidualReviewReason.COMPOSITION_HOLD


def test_rejected_selection_routes_to_residual_review() -> None:
    scores = {"AHE-001": _score("AHE-001", "NONE", None, True)}
    answers = {"AHE-001": _rejected_answer("AHE-001")}
    routing = route_selection_scores(scores=scores, answers=answers, threshold=-100.0)
    assert routing[0].decision is SelectionRoutingDecision.RESIDUAL_REVIEW
    assert routing[0].reason is ResidualReviewReason.REJECTED


def test_rejected_selection_bypasses_an_above_threshold_score() -> None:
    scores = {"AHE-001": _score("AHE-001", "C2", -0.1, False)}
    answers = {"AHE-001": _rejected_answer("AHE-001")}
    routing = route_selection_scores(scores=scores, answers=answers, threshold=-100.0)
    assert routing[0].decision is SelectionRoutingDecision.RESIDUAL_REVIEW
    assert routing[0].reason is ResidualReviewReason.REJECTED


def test_rejected_selection_lists_its_event_in_the_residual_review_set() -> None:
    scores = {"AHE-001": _score("AHE-001", "NONE", None, True)}
    answers = {"AHE-001": _rejected_answer("AHE-001")}
    residual = build_residual_review_set(scores=scores, answers=answers, threshold=-100.0)
    assert residual.event_ids == ("AHE-001",)


# --- Report safety -------------------------------------------------------------


def test_report_seals_zero_canonical_writes_and_proposed_changes() -> None:
    routing = route_selection_scores(
        scores={"AHE-001": _score("AHE-001", "C2", -0.5, False)}, threshold=-1.0
    )
    report = build_calibrated_residual_ownership_report(
        boundary_gaps=(),
        selection_routing=routing,
        residual_review_event_ids=(),
        pool_floor_relaxation=(),
        model_execution_count=1,
    )
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.result_fingerprint == calibrated_residual_ownership_report_fingerprint(report)


def test_report_rejects_a_non_zero_canonical_write_count() -> None:
    with pytest.raises(ValueError):
        CalibratedResidualOwnershipReport(
            boundary_gaps=(),
            selection_routing=(),
            residual_review_event_ids=(),
            pool_floor_relaxation=(),
            model_execution_count=0,
            canonical_write_count=1,
            proposed_change_count=0,
            result_fingerprint="0" * 64,
        )
