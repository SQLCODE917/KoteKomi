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
    build_decontextualized_proposition,
    build_held_out_error_census,
    build_held_out_exact_set_score,
    build_held_out_transfer_report,
    build_selection_probability_receipt,
    build_selection_scores,
    held_out_transfer_report_fingerprint,
    parser_constituent_id,
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
    first = ModelOutputTokenProbability(
        position=0,
        token="C2",
        log_probability=-0.5,
        token_bytes=tuple(b"C2"),
        alternatives=(
            ModelTokenAlternative("C2", -0.5, tuple(b"C2")),
            ModelTokenAlternative("NONE", -1.0, tuple(b"NONE")),
            ModelTokenAlternative("C1", -2.0, tuple(b"C1")),
        ),
    )
    return ModelExecutionReceipt(
        model_identity_digest="a" * 64,
        generation_parameters_digest="b" * 64,
        rendered_input_digest="c" * 64,
        input_token_count=12,
        output_token_count=1,
        output_token_probabilities=(first,),
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


def test_selection_probability_receipt_preserves_unmodified_alternatives() -> None:
    receipt = build_selection_probability_receipt(
        event_id="AHE-001",
        model_execution_id="mrn-1",
        receipt=_model_receipt(),
    )
    assert receipt.event_id == "AHE-001"
    assert receipt.model_execution_id == "mrn-1"
    assert [item.token for item in receipt.alternatives] == ["C2", "NONE", "C1"]
    assert [item.log_probability for item in receipt.alternatives] == [-0.5, -1.0, -2.0]


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


def test_selection_scores_censor_a_missing_label() -> None:
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
    assert scores[1].log_probability == -0.5
    censored = scores[2]
    assert censored.label == "C3"
    assert censored.censored is True
    assert censored.log_probability is None


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
