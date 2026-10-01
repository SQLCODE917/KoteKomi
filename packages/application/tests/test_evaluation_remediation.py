"""Focused data-in/data-out tests for R5 evaluation remediation (Application layer)."""

from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    DecontextualizationEntityRef,
    DecontextualizationStatus,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    HeldOutFragmentRequirement,
    HeldOutGoldEvent,
    HeldOutGoldFragment,
    ModelExecutionReceipt,
    ModelOutputTokenProbability,
    ModelTokenAlternative,
    ParserConstituent,
    SelectionProbabilityReceipt,
    SelectionTokenAlternative,
    SelectionTokenProbability,
    build_decontextualized_proposition,
    build_held_out_error_census,
    build_held_out_exact_set_score,
    build_held_out_transfer_report,
    build_representative_selection_score,
    build_selection_probability_receipt,
    build_selection_scores,
    held_out_transfer_report_fingerprint,
    parse_constituent_selection_answer_labels,
    parser_constituent_id,
    reconstruct_selection_label_sequence_log_probabilities,
)

OK_SOURCE = "Acme fired Bob."


def _words(
    source: str, specs: list[tuple[str, str | None, str, str]]
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
    for word, head, deprel, lemma in specs:
        start, end = positions[word]
        tokens.append(
            EventEntityLinguisticToken(
                token_id=by_word[word],
                sentence_id="s1",
                text=word,
                start=start,
                end=end,
                lemma=lemma,
                part_of_speech="NOUN",
                dependency_relation=deprel,
                head_token_id=by_word[head] if head else None,
            )
        )
    return tuple(tokens)


def _span(source: str, start_word: str, end_word: str) -> AttachmentSourceRange:
    start = source.index(start_word)
    end = source.index(end_word) + len(end_word)
    return AttachmentSourceRange(start=start, end=end, text=source[start:end])


def _constituent(
    source: str,
    event_id: str,
    token_ids: tuple[str, ...],
    start_word: str,
    end_word: str,
) -> ParserConstituent:
    span = _span(source, start_word, end_word)
    digest = hashlib.sha256(source.encode()).hexdigest()
    return ParserConstituent(
        constituent_id=parser_constituent_id(digest, span.start, span.end),
        event_id=event_id,
        source_text_sha256=digest,
        constituent_range=span,
        token_ids=token_ids,
    )


def _entity(
    entity_id: str,
    name: str,
    source: str,
    start_word: str,
    end_word: str,
) -> DecontextualizationEntityRef:
    return DecontextualizationEntityRef(
        entity_id=entity_id,
        entity_kind="actor",
        canonical_name=name,
        accepted_source_occurrences=(_span(source, start_word, end_word),),
    )


def _answer(
    event_id: str, status: ConstituentSelectionStatus, indexes: tuple[int, ...]
) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=status,
        selected_label_indexes=indexes,
    )


def _gold_fragment(
    fragment_id: str,
    start: int,
    end: int,
    text: str,
    requirements: tuple[HeldOutFragmentRequirement, ...],
) -> HeldOutGoldFragment:
    return HeldOutGoldFragment(
        fragment_id=fragment_id,
        start=start,
        end=end,
        text=text,
        requirements=requirements,
    )


def _held_out_event(
    event_id: str,
    source: str,
    fragments: tuple[HeldOutGoldFragment, ...],
) -> HeldOutGoldEvent:
    return HeldOutGoldEvent(
        event_id=event_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        event_meaning="fixture",
        fragments=fragments,
    )


def _ok_inventory() -> tuple[
    str, tuple[EventEntityLinguisticToken, ...], ConstituentCandidateInventory
]:
    tokens = _words(
        OK_SOURCE,
        [
            ("Acme", "fired", "nsubj", "acme"),
            ("fired", None, "root", "fire"),
            ("Bob", "fired", "obj", "bob"),
        ],
    )
    digest = hashlib.sha256(OK_SOURCE.encode()).hexdigest()
    inventory = ConstituentCandidateInventory(
        event_id="AHE-001",
        source_text_sha256=digest,
        constituents=(
            _constituent(OK_SOURCE, "AHE-001", ("t1",), "Acme", "Acme"),
            _constituent(OK_SOURCE, "AHE-001", ("t2",), "fired", "fired"),
            _constituent(OK_SOURCE, "AHE-001", ("t3",), "Bob", "Bob"),
        ),
    )
    return digest, tokens, inventory


def _ok_proposition(
    digest: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    inventory: ConstituentCandidateInventory,
) -> DecontextualizedProposition:
    entities = (
        _entity("EGE-001", "Acme", OK_SOURCE, "Acme", "Acme"),
        _entity("EGE-002", "Bob", OK_SOURCE, "Bob", "Bob"),
    )
    head = next(token for token in tokens if token.lemma == "fire")
    return build_decontextualized_proposition(
        event_id="AHE-001",
        source_text=OK_SOURCE,
        source_text_sha256=digest,
        inventory=inventory,
        answer=_answer("AHE-001", ConstituentSelectionStatus.SELECTED, (1, 2, 3)),
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=entities,
    )


def _model_receipt() -> ModelExecutionReceipt:
    c_token = ModelOutputTokenProbability(
        position=0,
        token="C",
        log_probability=-0.1,
        token_bytes=tuple(b"C"),
        alternatives=(
            ModelTokenAlternative("C", -0.1, tuple(b"C")),
            ModelTokenAlternative("1", -2.0, tuple(b"1")),
            ModelTokenAlternative("2", -3.0, tuple(b"2")),
        ),
    )
    two_token = ModelOutputTokenProbability(
        position=1,
        token="2",
        log_probability=-0.4,
        token_bytes=tuple(b"2"),
        alternatives=(
            ModelTokenAlternative("2", -0.4, tuple(b"2")),
            ModelTokenAlternative("1", -1.0, tuple(b"1")),
            ModelTokenAlternative("3", -2.0, tuple(b"3")),
        ),
    )
    return ModelExecutionReceipt(
        model_identity_digest="a" * 64,
        generation_parameters_digest="b" * 64,
        rendered_input_digest="c" * 64,
        input_token_count=12,
        output_token_count=2,
        output_token_probabilities=(c_token, two_token),
    )


def _token_probability(
    position: int, token: str, log_probability: float
) -> SelectionTokenProbability:
    return SelectionTokenProbability(
        position=position,
        token=token,
        log_probability=log_probability,
        token_bytes=tuple(token.encode("utf-8")),
        alternatives=(
            SelectionTokenAlternative(
                token=token,
                log_probability=log_probability,
                token_bytes=tuple(token.encode("utf-8")),
            ),
        ),
    )


def _receipt(*tokens: SelectionTokenProbability) -> SelectionProbabilityReceipt:
    return SelectionProbabilityReceipt(
        event_id="AHE-001",
        model_execution_id="mrn-1",
        output_token_probabilities=tokens,
    )


def _ok_gold_fragments() -> tuple[HeldOutGoldFragment, ...]:
    return (
        _gold_fragment("PGF-AHE-001-01", 0, 4, "Acme", (HeldOutFragmentRequirement.CORE_EVENT,)),
        _gold_fragment("PGF-AHE-001-02", 5, 10, "fired", (HeldOutFragmentRequirement.CORE_EVENT,)),
        _gold_fragment("PGF-AHE-001-03", 11, 14, "Bob", (HeldOutFragmentRequirement.CORE_EVENT,)),
    )


def _held_proposition(
    digest: str,
    inventory: ConstituentCandidateInventory,
) -> DecontextualizedProposition:
    return build_decontextualized_proposition(
        event_id="AHE-001",
        source_text=OK_SOURCE,
        source_text_sha256=digest,
        inventory=inventory,
        answer=_answer("AHE-001", ConstituentSelectionStatus.NONE, ()),
        trigger_head_start=5,
        trigger_head_end=10,
        tokens=(),
        entities=(),
    )


def test_selection_probability_receipt_preserves_per_token_evidence() -> None:
    receipt = build_selection_probability_receipt(
        event_id="AHE-001",
        model_execution_id="mrn-1",
        receipt=_model_receipt(),
    )
    assert receipt.event_id == "AHE-001"
    assert receipt.model_execution_id == "mrn-1"
    assert [item.position for item in receipt.output_token_probabilities] == [0, 1]
    assert [item.token for item in receipt.output_token_probabilities] == ["C", "2"]
    first_alternatives = receipt.output_token_probabilities[0].alternatives
    assert [item.token for item in first_alternatives] == ["C", "1", "2"]
    assert [item.log_probability for item in first_alternatives] == [-0.1, -2.0, -3.0]


def test_selection_probability_receipt_rejects_missing_token_probabilities() -> None:
    empty = ModelExecutionReceipt(
        model_identity_digest="a" * 64,
        generation_parameters_digest="b" * 64,
        rendered_input_digest="c" * 64,
        input_token_count=0,
        output_token_count=None,
    )
    with pytest.raises(ValueError, match="output token probabilities"):
        build_selection_probability_receipt(
            event_id="AHE-001",
            model_execution_id="mrn-1",
            receipt=empty,
        )


def test_selection_scores_reconstruct_full_sequence_and_censor_missing() -> None:
    receipt = build_selection_probability_receipt(
        event_id="AHE-001",
        model_execution_id="mrn-1",
        receipt=_model_receipt(),
    )
    scores = build_selection_scores(
        event_id="AHE-001",
        allowed_labels=("C1", "C2", "C3"),
        receipt=receipt,
    )
    assert [item.label for item in scores] == ["C1", "C2", "C3"]
    assert scores[1].label == "C2"
    assert scores[1].censored is False
    assert scores[1].log_probability == -0.5  # logp("C") + logp("2")
    for index in (0, 2):
        assert scores[index].censored is True
        assert scores[index].log_probability is None


def test_reconstruction_prefers_the_longer_numeric_label() -> None:
    receipt = _receipt(
        _token_probability(0, "C", -0.5),
        _token_probability(1, "1", -0.25),
        _token_probability(2, "0", -0.25),
    )
    scores = build_selection_scores(
        event_id="AHE-001",
        allowed_labels=("C1", "C10"),
        receipt=receipt,
    )
    by_label = {item.label: item for item in scores}
    assert by_label["C10"].censored is False
    assert by_label["C10"].log_probability == -1.0
    assert by_label["C1"].censored is True
    assert by_label["C1"].log_probability is None


def test_reconstruction_strips_the_first_tokens_leading_whitespace() -> None:
    receipt = _receipt(
        _token_probability(0, " C", -0.5),
        _token_probability(1, "3", -0.5),
    )
    scores = reconstruct_selection_label_sequence_log_probabilities(
        receipt=receipt, allowed_labels=("C3",)
    )
    assert scores["C3"] == -1.0


def test_reconstruction_strips_one_leading_comma() -> None:
    receipt = _receipt(
        _token_probability(0, ",C", -0.4),
        _token_probability(1, "6", -0.6),
    )
    scores = reconstruct_selection_label_sequence_log_probabilities(
        receipt=receipt, allowed_labels=("C6",)
    )
    assert scores["C6"] == -1.0


def test_reconstruction_recovers_the_none_sequence() -> None:
    receipt = _receipt(_token_probability(0, "NONE", -1.0))
    scores = reconstruct_selection_label_sequence_log_probabilities(
        receipt=receipt, allowed_labels=("NONE",)
    )
    assert scores["NONE"] == -1.0


def test_reconstruction_censors_a_label_with_no_run() -> None:
    receipt = _receipt(
        _token_probability(0, "C", -0.2),
        _token_probability(1, "9", -0.2),
    )
    scores = build_selection_scores(
        event_id="AHE-001",
        allowed_labels=("C4",),
        receipt=receipt,
    )
    assert scores[0].label == "C4"
    assert scores[0].censored is True
    assert scores[0].log_probability is None


def test_representative_score_censors_a_rejected_prose_answer() -> None:
    answer = ConstituentSelectionAnswer(
        event_id="AHE-001",
        status=ConstituentSelectionStatus.REJECTED,
        selected_label_indexes=(),
    )
    receipt = _receipt(
        _token_probability(0, "C", -0.1),
        _token_probability(1, "6", -0.1),
    )
    score = build_representative_selection_score(
        event_id="AHE-001",
        answer=answer,
        allowed_labels=("C6",),
        receipt=receipt,
    )
    assert score.label == "NONE"
    assert score.censored is True
    assert score.log_probability is None


def test_scorer_labels_match_the_parser_accepted_subset() -> None:
    answer = parse_constituent_selection_answer_labels(
        event_id="AHE-001",
        raw_answer="C1, C3",
        constituent_labels=("C1", "C2", "C3"),
    )
    assert answer.status is ConstituentSelectionStatus.SELECTED
    accepted = {f"C{index}" for index in answer.selected_label_indexes}
    receipt = _receipt(
        _token_probability(0, "C", -0.1),
        _token_probability(1, "1", -0.1),
        _token_probability(2, ",", -0.1),
        _token_probability(3, "C", -0.2),
        _token_probability(4, "3", -0.2),
    )
    scores = build_selection_scores(
        event_id="AHE-001",
        allowed_labels=("C1", "C2", "C3"),
        receipt=receipt,
    )
    reconstructed = {item.label for item in scores if not item.censored}
    assert reconstructed == accepted


def test_error_census_lists_every_boundary_miss_fragment_id() -> None:
    digest, _, inventory = _ok_inventory()
    events = {
        "AHE-001": _held_out_event(
            "AHE-001",
            OK_SOURCE,
            (
                _gold_fragment("PGF-AHE-001-01", 1, 3, "cm", (HeldOutFragmentRequirement.PURPOSE,)),
                _gold_fragment(
                    "PGF-AHE-001-02", 6, 9, "ire", (HeldOutFragmentRequirement.PURPOSE,)
                ),
            ),
        )
    }
    census = build_held_out_error_census(
        events=events,
        inventories={"AHE-001": inventory},
        answers={"AHE-001": _answer("AHE-001", ConstituentSelectionStatus.NONE, ())},
        propositions={"AHE-001": _held_proposition(digest, inventory)},
    )
    assert census.boundary_miss_count == 1
    assert census.boundary_miss_event_ids == ("AHE-001",)
    assert census.boundary_miss_fragment_ids == ("PGF-AHE-001-01", "PGF-AHE-001-02")


def test_error_census_counts_a_selection_error() -> None:
    digest, _, inventory = _ok_inventory()
    events = {
        "AHE-001": _held_out_event(
            "AHE-001",
            OK_SOURCE,
            (
                _gold_fragment(
                    "PGF-AHE-001-01", 0, 4, "Acme", (HeldOutFragmentRequirement.PURPOSE,)
                ),
            ),
        )
    }
    census = build_held_out_error_census(
        events=events,
        inventories={"AHE-001": inventory},
        answers={"AHE-001": _answer("AHE-001", ConstituentSelectionStatus.NONE, ())},
        propositions={"AHE-001": _held_proposition(digest, inventory)},
    )
    assert census.selection_error_count == 1
    assert census.selection_error_event_ids == ("AHE-001",)


def test_error_census_marks_an_error_free_event_ok() -> None:
    digest, tokens, inventory = _ok_inventory()
    events = {
        "AHE-001": _held_out_event("AHE-001", OK_SOURCE, _ok_gold_fragments()),
    }
    proposition = _ok_proposition(digest, tokens, inventory)
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    selected_answer = _answer("AHE-001", ConstituentSelectionStatus.SELECTED, (1, 2, 3))
    census = build_held_out_error_census(
        events=events,
        inventories={"AHE-001": inventory},
        answers={"AHE-001": selected_answer},
        propositions={"AHE-001": proposition},
    )
    assert census.ok_count == 1
    assert census.ok_event_ids == ("AHE-001",)
    assert census.boundary_miss_count == 0
    assert census.selection_error_count == 0


def test_exact_set_score_reports_but_does_not_gate() -> None:
    digest, tokens, inventory = _ok_inventory()
    selected_answer = _answer("AHE-001", ConstituentSelectionStatus.SELECTED, (1, 2, 3))
    events = {
        "AHE-001": _held_out_event("AHE-001", OK_SOURCE, _ok_gold_fragments()),
    }
    exact = build_held_out_exact_set_score(
        events=events,
        inventories={"AHE-001": inventory},
        answers={"AHE-001": selected_answer},
    )
    assert exact == 1.0
    census = build_held_out_error_census(
        events=events,
        inventories={"AHE-001": inventory},
        answers={"AHE-001": selected_answer},
        propositions={"AHE-001": _ok_proposition(digest, tokens, inventory)},
    )
    report = build_held_out_transfer_report(
        census=census,
        exact_set_score=exact,
        selection_scores=(),
        model_execution_count=1,
    )
    assert report.exact_set_score == 1.0
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.result_fingerprint == held_out_transfer_report_fingerprint(report)


def test_transfer_report_seals_a_zero_exact_set_score_without_failure() -> None:
    census = build_held_out_error_census(
        events={},
        inventories={},
        answers={},
        propositions={},
    )
    report = build_held_out_transfer_report(
        census=census,
        exact_set_score=0.0,
        selection_scores=(),
        model_execution_count=0,
    )
    assert report.exact_set_score == 0.0
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == held_out_transfer_report_fingerprint(report)
