"""Focused data-in/data-out tests for R3 parser-constituent contracts."""

from __future__ import annotations

import inspect
import re

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    BoundaryFidelityPartitionCensus,
    ConstituentSelectionStatus,
    CorrectedAttachmentGold,
    CorrectedCandidateLabel,
    EventEntityLinguisticToken,
    GoldFragmentRef,
    build_boundary_fidelity_census,
    build_constituent_candidate_inventory,
    build_constituent_selection_census,
    build_constituent_selection_report,
    constituent_selection_report_fingerprint,
    corrected_gold_attachment_spans,
    parse_constituent_selection_answer,
    render_constituent_selection_task,
    selected_constituent_spans,
)

SINGLE_SOURCE = "Anthropic cut ties with the firms that rival OpenAI."
SINGLE_EVENT_START = 10
SINGLE_EVENT_END = 18


def _token(
    token_id: str,
    sentence_id: str,
    text: str,
    start: int,
    end: int,
    head_token_id: str | None,
    deprel: str = "dep",
) -> EventEntityLinguisticToken:
    return EventEntityLinguisticToken(
        token_id=token_id,
        sentence_id=sentence_id,
        text=text,
        start=start,
        end=end,
        lemma=text.casefold(),
        part_of_speech="NOUN",
        dependency_relation=deprel,
        head_token_id=head_token_id,
    )


SINGLE_TOKENS = (
    _token("t1", "s1", "Anthropic", 0, 9, "t2", deprel="nsubj"),
    _token("t2", "s1", "cut", 10, 13, None, deprel="root"),
    _token("t3", "s1", "ties", 14, 18, "t2", deprel="obj"),
    _token("t4", "s1", "with", 19, 23, "t6", deprel="case"),
    _token("t5", "s1", "the", 24, 27, "t6", deprel="det"),
    _token("t6", "s1", "firms", 28, 33, "t2", deprel="obl"),
    _token("t7", "s1", "that", 34, 38, "t8", deprel="mark"),
    _token("t8", "s1", "rival", 39, 44, "t6", deprel="acl:relcl"),
    _token("t9", "s1", "OpenAI", 45, 51, "t8", deprel="obj"),
)

TWO_SOURCE = "Anthropic cut ties. OpenAI sued."
TWO_EVENT_START = 10
TWO_EVENT_END = 18

TWO_TOKENS = (
    _token("t1", "s1", "Anthropic", 0, 9, "t2", deprel="nsubj"),
    _token("t2", "s1", "cut", 10, 13, None, deprel="root"),
    _token("t3", "s1", "ties", 14, 18, "t2", deprel="obj"),
    _token("t4", "s2", "OpenAI", 20, 26, "t5", deprel="nsubj"),
    _token("t5", "s2", "sued", 27, 31, None, deprel="root"),
)


def _inventory(source: str, tokens: tuple[EventEntityLinguisticToken, ...], start: int, end: int):
    return build_constituent_candidate_inventory(
        source_text=source,
        event_id="TGE-001",
        tokens=tokens,
        event_expression_start=start,
        event_expression_end=end,
    )


def test_inventory_includes_exact_event_expression() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    assert (SINGLE_EVENT_START, SINGLE_EVENT_END) in spans


def test_inventory_spans_are_exact_and_deterministic() -> None:
    first = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    second = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    assert first.model_dump() == second.model_dump()
    spans = [
        (item.constituent_range.start, item.constituent_range.end) for item in first.constituents
    ]
    assert spans == [
        (0, 9),
        (0, 33),
        (10, 13),
        (10, 18),
        (14, 18),
        (19, 23),
        (19, 33),
        (24, 27),
        (28, 33),
        (34, 38),
        (34, 51),
        (39, 44),
        (45, 51),
    ]


def test_every_constituent_is_source_exact() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    for item in inventory.constituents:
        assert SINGLE_SOURCE[item.constituent_range.start : item.constituent_range.end] == (
            item.constituent_range.text
        )
        assert item.constituent_range.text.strip()


def test_constituents_are_clause_local() -> None:
    inventory = _inventory(TWO_SOURCE, TWO_TOKENS, TWO_EVENT_START, TWO_EVENT_END)
    token_by_id = {item.token_id: item for item in TWO_TOKENS}
    for item in inventory.constituents:
        tokens = [token_by_id[token_id] for token_id in item.token_ids]
        assert {token.sentence_id for token in tokens} == {tokens[0].sentence_id}
        for left, right in zip(tokens, tokens[1:], strict=False):
            assert left.end <= right.start


def test_builder_reads_no_gold() -> None:
    parameters = inspect.signature(build_constituent_candidate_inventory).parameters
    assert not any(name.casefold().count("gold") for name in parameters)


def test_builder_rejects_unsupported_characters() -> None:
    bad = (_token("t1", "s1", "Anthropic", 0, 9, None, deprel="root"),)
    with pytest.raises(ValueError, match="exact source characters"):
        _inventory("AnthropiX", bad, 0, 9)


def test_builder_rejects_whitespace_event_expression() -> None:
    with pytest.raises(ValueError, match="whitespace-only"):
        _inventory(SINGLE_SOURCE, SINGLE_TOKENS, 13, 14)


def test_token_sub_spans_exist_per_dependency_token() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    for token in SINGLE_TOKENS:
        assert (token.start, token.end) in spans


def test_head_phrase_projection_exists_per_governing_head() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    # Each governing head projects one contiguous phrase: t2 (cut) -> (0, 33),
    # t6 (firms) -> (19, 33), and t8 (rival) -> (34, 51).
    assert (0, 33) in spans
    assert (19, 33) in spans
    assert (34, 51) in spans


def test_head_phrase_projection_never_crosses_detached_clause() -> None:
    source = "John , who quit , arrived ."
    tokens = (
        _token("t1", "s1", "John", 0, 4, "t4", deprel="nsubj"),
        _token("t2", "s1", "who", 7, 10, "t3", deprel="nsubj"),
        _token("t3", "s1", "quit", 11, 15, "t1", deprel="acl:relcl"),
        _token("t4", "s1", "arrived", 18, 25, None, deprel="root"),
    )
    inventory = _inventory(source, tokens, 18, 25)
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    assert (0, 4) in spans
    assert (7, 15) in spans
    assert (18, 25) in spans
    assert (0, 25) not in spans


def test_enrichment_keeps_r3_clause_level_and_trigger() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    assert (0, 33) in spans
    assert (34, 51) in spans
    assert (10, 18) in spans


def test_enriched_inventory_is_ordered_and_distinct() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    spans = [
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    ]
    assert spans == sorted(spans)
    assert len(spans) == len(set(spans))


def test_sub_span_growth_stays_within_two_per_token() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    token_sub_spans = {(token.start, token.end) for token in SINGLE_TOKENS}
    single_token_constituents = [
        item
        for item in inventory.constituents
        if (item.constituent_range.start, item.constituent_range.end) in token_sub_spans
    ]
    # One Token sub-span per dependency token, plus at most one Head phrase
    # projection per governing head (<= token count), keeps Sub-span growth
    # within two candidates per token on top of the R3 clause-level groups.
    assert len(single_token_constituents) == len(SINGLE_TOKENS)
    assert len(inventory.constituents) <= 2 * len(SINGLE_TOKENS) + 2


def _census(gold_fragments: dict[str, tuple[GoldFragmentRef, ...]]):
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    return build_boundary_fidelity_census(
        partition_role="development",
        inventories={"TGE-001": inventory},
        gold_fragments=gold_fragments,
    )


def test_fidelity_covers_exact_span_only() -> None:
    census = _census(
        {
            "TGE-001": (
                GoldFragmentRef(fragment_id="PGF-TGE-001-01", start=0, end=33),
                GoldFragmentRef(fragment_id="PGF-TGE-001-02", start=10, end=18),
                GoldFragmentRef(fragment_id="PGF-TGE-001-03", start=34, end=51),
                GoldFragmentRef(fragment_id="PGF-TGE-001-04", start=10, end=20),
            )
        }
    )
    assert census.covered_fragment_ids == tuple(
        ["PGF-TGE-001-01", "PGF-TGE-001-02", "PGF-TGE-001-03"]
    )
    assert [item.fragment_id for item in census.missed_fragments] == ["PGF-TGE-001-04"]


def test_fidelity_pool_ceiling_recomputes() -> None:
    census = _census(
        {
            "TGE-001": (
                GoldFragmentRef(fragment_id="PGF-TGE-001-01", start=0, end=33),
                GoldFragmentRef(fragment_id="PGF-TGE-001-02", start=10, end=20),
            )
        }
    )
    assert census.pool_ceiling == 0.5
    with pytest.raises(ValueError, match="drifted"):
        BoundaryFidelityPartitionCensus(
            partition_role="development",
            covered_fragment_ids=("PGF-TGE-001-01",),
            missed_fragments=(),
            pool_ceiling=0.0,
        )


def test_fidelity_requires_one_inventory_per_gold_event() -> None:
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    with pytest.raises(ValueError, match="one inventory per Gold Event"):
        build_boundary_fidelity_census(
            partition_role="development",
            inventories={"TGE-002": inventory},
            gold_fragments={
                "TGE-001": (GoldFragmentRef(fragment_id="PGF-TGE-001-01", start=0, end=38),)
            },
        )


def _render(event_literal: str = "cut ties"):
    inventory = _inventory(SINGLE_SOURCE, SINGLE_TOKENS, SINGLE_EVENT_START, SINGLE_EVENT_END)
    return inventory, render_constituent_selection_task(
        inventory=inventory, source_text=SINGLE_SOURCE, event_literal=event_literal
    )


def test_selection_labels_are_stable() -> None:
    _, first = _render()
    _, second = _render()
    assert (
        first.constituent_labels
        == second.constituent_labels
        == (
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "C6",
            "C7",
            "C8",
            "C9",
            "C10",
            "C11",
            "C12",
            "C13",
        )
    )
    assert first.rendered_input == second.rendered_input


def test_render_excludes_boundary_bytes() -> None:
    inventory, task = _render()
    lines = task.rendered_input.splitlines()
    assert lines[-3:] == [
        "C11: that rival OpenAI",
        "C12: rival",
        "C13: OpenAI",
    ]
    for item in inventory.constituents:
        start = str(item.constituent_range.start)
        end = str(item.constituent_range.end)
        assert re.search(rf"\b{start}\b", task.rendered_input) is None
        assert re.search(rf"\b{end}\b", task.rendered_input) is None


def test_renderer_rejects_repeated_event_literal() -> None:
    source = "Anthropic Anthropic cut ties."
    tokens = (
        _token("t1", "s1", "Anthropic", 0, 9, "t3", deprel="nsubj"),
        _token("t2", "s1", "Anthropic", 10, 19, "t3", deprel="conj"),
        _token("t3", "s1", "cut", 20, 23, None, deprel="root"),
        _token("t4", "s1", "ties", 24, 28, "t3", deprel="obj"),
    )
    inventory = _inventory(source, tokens, 20, 28)
    with pytest.raises(ValueError, match="unique Event literal"):
        render_constituent_selection_task(
            inventory=inventory,
            source_text=source,
            event_literal="Anthropic",
        )


def _parse(raw: str):
    return parse_constituent_selection_answer(raw_answer=raw, task=_render()[1])


def test_parse_accepts_subset() -> None:
    answer = _parse("C1, C3")
    assert answer.status is ConstituentSelectionStatus.SELECTED
    assert answer.selected_label_indexes == (1, 3)


def test_parse_accepts_none() -> None:
    answer = _parse("NONE")
    assert answer.status is ConstituentSelectionStatus.NONE
    assert answer.selected_label_indexes == ()


def test_parse_rejects_out_of_inventory_label() -> None:
    assert _parse("C1, C14").status is ConstituentSelectionStatus.REJECTED


def test_parse_rejects_garbage_answer() -> None:
    assert _parse("yes").status is ConstituentSelectionStatus.REJECTED


def test_selected_constituent_spans_map_to_inventory() -> None:
    inventory, task = _render()
    answer = parse_constituent_selection_answer(raw_answer="C4", task=task)
    spans = selected_constituent_spans(answer=answer, inventory=inventory)
    assert [(item.start, item.end) for item in spans] == [(10, 18)]


def _corrected_label(
    candidate_id: str, start: int, end: int, text: str, event_ids: tuple[str, ...]
) -> CorrectedCandidateLabel:
    return CorrectedCandidateLabel.model_construct(
        candidate_id=candidate_id,
        phase="development",
        source_range=AttachmentSourceRange(start=start, end=end, text=text),
        gold_event_ids=event_ids,
    )


def _corrected_gold(
    labels: tuple[CorrectedCandidateLabel, ...],
) -> CorrectedAttachmentGold:
    return CorrectedAttachmentGold.model_construct(
        schema_version="corrected_attachment_gold_v1",
        catalog_id="fixture",
        source_catalog_sha256="a" * 64,
        corrected_labels=labels,
        resizes=(),
    )


def test_corrected_gold_attachment_spans_group_by_event() -> None:
    corrected = _corrected_gold(
        (
            _corrected_label("cac_" + "a" * 24, 10, 18, "cut ties", ("TGE-001",)),
            _corrected_label(
                "cac_" + "b" * 24,
                0,
                33,
                "Anthropic cut ties with the firms",
                ("TGE-001", "TGE-002"),
            ),
        )
    )
    spans = corrected_gold_attachment_spans(corrected)
    assert spans == {"TGE-001": ((0, 33), (10, 18)), "TGE-002": ((0, 33),)}


def test_selection_census_scores_exact_and_missed_spans() -> None:
    inventory, task = _render()
    answer = parse_constituent_selection_answer(raw_answer="C4", task=task)
    census = build_constituent_selection_census(
        partition_role="development",
        answers={"TGE-001": answer},
        inventories={"TGE-001": inventory},
        gold_attachment_spans={"TGE-001": ((10, 18), (34, 51))},
    )
    assert census.partition_role == "development"
    assert census.event_count == 1
    assert census.selected_event_count == 1
    assert census.none_event_count == 0
    assert census.rejected_event_count == 0
    assert census.exact_attachment_count == 1
    assert census.gold_attachment_span_count == 2
    assert census.false_positive_span_count == 0
    assert census.false_negative_span_count == 1


def test_selection_census_counts_none_as_missed() -> None:
    inventory, task = _render()
    answer = parse_constituent_selection_answer(raw_answer="NONE", task=task)
    census = build_constituent_selection_census(
        partition_role="development",
        answers={"TGE-001": answer},
        inventories={"TGE-001": inventory},
        gold_attachment_spans={"TGE-001": ((10, 18),)},
    )
    assert census.none_event_count == 1
    assert census.exact_attachment_count == 0
    assert census.false_negative_span_count == 1


def _validation_inventory():
    source = "OpenAI sued."
    tokens = (
        _token("t1", "s1", "OpenAI", 0, 6, "t2", deprel="nsubj"),
        _token("t2", "s1", "sued", 7, 11, None, deprel="root"),
    )
    return build_constituent_candidate_inventory(
        source_text=source,
        event_id="TGE-002",
        tokens=tokens,
        event_expression_start=7,
        event_expression_end=11,
    )


def test_selection_report_is_fingerprinted_and_write_free() -> None:
    dev_inventory, dev_task = _render()
    val_inventory = _validation_inventory()
    dev_fidelity = build_boundary_fidelity_census(
        partition_role="development",
        inventories={"TGE-001": dev_inventory},
        gold_fragments={
            "TGE-001": (GoldFragmentRef(fragment_id="PGF-TGE-001-01", start=10, end=18),)
        },
    )
    val_fidelity = build_boundary_fidelity_census(
        partition_role="validation",
        inventories={"TGE-002": val_inventory},
        gold_fragments={
            "TGE-002": (GoldFragmentRef(fragment_id="PGF-TGE-002-01", start=7, end=11),)
        },
    )
    dev_answer = parse_constituent_selection_answer(raw_answer="C2", task=dev_task)
    dev_selection = build_constituent_selection_census(
        partition_role="development",
        answers={"TGE-001": dev_answer},
        inventories={"TGE-001": dev_inventory},
        gold_attachment_spans={"TGE-001": ((10, 18),)},
    )
    val_task = render_constituent_selection_task(
        inventory=val_inventory,
        source_text="OpenAI sued.",
        event_literal="sued",
    )
    val_selection = build_constituent_selection_census(
        partition_role="validation",
        answers={"TGE-002": parse_constituent_selection_answer(raw_answer="NONE", task=val_task)},
        inventories={"TGE-002": val_inventory},
        gold_attachment_spans={"TGE-002": ((7, 11),)},
    )
    report = build_constituent_selection_report(
        development_fidelity=dev_fidelity,
        validation_fidelity=val_fidelity,
        development_selection=dev_selection,
        validation_selection=val_selection,
        corrected_gold_sha256="b" * 64,
        model_execution_count=2,
    )
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 2
    assert report.result_fingerprint == constituent_selection_report_fingerprint(report)
    first = constituent_selection_report_fingerprint(report)
    second = constituent_selection_report_fingerprint(report)
    assert first == second
