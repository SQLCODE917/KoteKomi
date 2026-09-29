"""Focused Pipeline-layer tests for R5 evaluation remediation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    DecontextualizationStatus,
    EventEntityLinguisticToken,
    HeldOutFragmentRequirement,
    HeldOutGoldFragment,
    ParserConstituent,
    parse_constituent_selection_answer,
    parser_constituent_id,
)
from kotekomi_pipelines.evaluation_remediation import (
    HeldOutPropositionGoldCatalog,
    HeldOutPropositionGoldEvent,
    build_held_out_inventories,
    build_held_out_propositions,
    derive_held_out_entities,
    derive_held_out_trigger_head,
    held_out_gold_events,
    render_held_out_selection_tasks,
    verify_held_out_frozen_evidence,
)
from pydantic import ValidationError

SOURCE = "Acme fired Bob."


def _token(
    token_id: str,
    text: str,
    start: int,
    end: int,
    head_token_id: str | None,
    deprel: str = "dep",
    sentence_id: str = "s1",
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


HO_TOKENS = (
    _token("t1", "Acme", 0, 4, "t2", deprel="nsubj"),
    _token("t2", "fired", 5, 10, None, deprel="root"),
    _token("t3", "Bob", 11, 14, "t2", deprel="obj"),
)


def _digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def _fragment(fragment_id: str, start: int, end: int, text: str) -> HeldOutGoldFragment:
    return HeldOutGoldFragment(
        fragment_id=fragment_id,
        start=start,
        end=end,
        text=text,
        requirements=(HeldOutFragmentRequirement.CORE_EVENT,),
    )


def _prop_event(event_id: str, source: str) -> HeldOutPropositionGoldEvent:
    return HeldOutPropositionGoldEvent(
        event_id=event_id,
        phase="held_out",
        source_text_sha256=_digest(source),
        source_text=source,
        authoritative_text_sha256=_digest(source),
        authoritative_text=source,
        event_meaning="fixture",
        fragments=(_fragment(f"PGF-{event_id}-01", 5, 10, "fired"),),
        paragraph_node_id="nod_fixture",
        source_segment_id="src_fixture",
        source_segment_label="s1",
        review_rationale="fixture",
    )


def _catalog(
    events: tuple[HeldOutPropositionGoldEvent, ...],
) -> HeldOutPropositionGoldCatalog:
    return HeldOutPropositionGoldCatalog(
        schema_version="source_grounded_proposition_held_out_gold_v1",
        catalog_id="fixture",
        review_status="approved",
        annotation_status="human_reviewed_held_out_gold",
        development_overlap_count=0,
        event_count=len(events),
        representation_id="rep_e84869f6fcd4ed02c70a550a",
        source_segment_policy_id="paragraph_segment_v3",
        fixture_path="raw/fixture.pdf",
        fixture_sha256="0" * 64,
        packet_path="docs/fixture.md",
        packet_sha256="0" * 64,
        events=events,
    )


def _constituent(
    source: str,
    event_id: str,
    token_ids: tuple[str, ...],
    start: int,
    end: int,
) -> ParserConstituent:
    return ParserConstituent(
        constituent_id=parser_constituent_id(_digest(source), start, end),
        event_id=event_id,
        source_text_sha256=_digest(source),
        constituent_range=AttachmentSourceRange(start=start, end=end, text=source[start:end]),
        token_ids=token_ids,
    )


def test_verify_held_out_frozen_evidence_rejects_drift(tmp_path: Path) -> None:
    paths = {
        "gold": tmp_path / "gold.json",
        "fixture": tmp_path / "fixture.pdf",
        "stanza_lock": tmp_path / "stanza-lock.json",
    }
    for path in paths.values():
        path.write_bytes(b"not the frozen evidence")
    with pytest.raises(ValueError, match="drifted from its pinned digest"):
        verify_held_out_frozen_evidence(
            gold=paths["gold"],
            fixture=paths["fixture"],
            stanza_lock=paths["stanza_lock"],
        )


def test_catalog_rejects_nonzero_development_overlap() -> None:
    payload = _catalog((_prop_event("AHE-001", SOURCE),)).model_dump()
    payload["development_overlap_count"] = 1
    with pytest.raises(ValidationError):
        HeldOutPropositionGoldCatalog.model_validate(payload)


def test_derive_held_out_trigger_head_selects_sentence_root() -> None:
    assert derive_held_out_trigger_head(source_text=SOURCE, tokens=HO_TOKENS) == (5, 10)


TWO_SENTENCE_SOURCE = "Acme fired Bob. Globex sued."


def _two_sentence_tokens() -> tuple[EventEntityLinguisticToken, ...]:
    return (
        _token("t1", "Acme", 0, 4, "t2", deprel="nsubj"),
        _token("t2", "fired", 5, 10, None, deprel="root"),
        _token("t3", "Bob", 11, 14, "t2", deprel="obj"),
        _token("t4", "Globex", 16, 22, "t5", deprel="nsubj", sentence_id="s2"),
        _token("t5", "sued", 23, 27, None, deprel="root", sentence_id="s2"),
    )


def test_derive_held_out_trigger_head_selects_first_sentence_root() -> None:
    assert derive_held_out_trigger_head(
        source_text=TWO_SENTENCE_SOURCE, tokens=_two_sentence_tokens()
    ) == (5, 10)


def test_derive_held_out_entities_selects_first_sentence_root() -> None:
    inventory = ConstituentCandidateInventory(
        event_id="AHE-001",
        source_text_sha256=_digest(TWO_SENTENCE_SOURCE),
        constituents=(
            _constituent(TWO_SENTENCE_SOURCE, "AHE-001", ("t1",), 0, 4),
            _constituent(TWO_SENTENCE_SOURCE, "AHE-001", ("t3",), 11, 14),
            _constituent(TWO_SENTENCE_SOURCE, "AHE-001", ("t4",), 16, 22),
            _constituent(TWO_SENTENCE_SOURCE, "AHE-001", ("t5",), 23, 27),
        ),
    )
    entities = derive_held_out_entities(
        source_text=TWO_SENTENCE_SOURCE,
        source_text_sha256=_digest(TWO_SENTENCE_SOURCE),
        tokens=_two_sentence_tokens(),
        inventory=inventory,
    )
    assert [item.canonical_name for item in entities] == ["Acme", "Bob"]


def test_derive_held_out_entities_returns_source_exact_constituents() -> None:
    inventory = ConstituentCandidateInventory(
        event_id="AHE-001",
        source_text_sha256=_digest(SOURCE),
        constituents=(
            _constituent(SOURCE, "AHE-001", ("t1",), 0, 4),
            _constituent(SOURCE, "AHE-001", ("t1", "t2"), 0, 10),
            _constituent(SOURCE, "AHE-001", ("t2",), 5, 10),
            _constituent(SOURCE, "AHE-001", ("t2", "t3"), 5, 14),
            _constituent(SOURCE, "AHE-001", ("t3",), 11, 14),
        ),
    )
    entities = derive_held_out_entities(
        source_text=SOURCE,
        source_text_sha256=_digest(SOURCE),
        tokens=HO_TOKENS,
        inventory=inventory,
    )
    assert [item.entity_id for item in entities] == ["EGE-101", "EGE-102"]
    assert [item.canonical_name for item in entities] == ["Acme", "Bob"]
    for item in entities:
        assert item.entity_kind == "actor"
        for occurrence in item.accepted_source_occurrences:
            assert SOURCE[occurrence.start : occurrence.end] == occurrence.text


def test_build_held_out_inventories_are_source_exact_and_model_free() -> None:
    catalog = _catalog((_prop_event("AHE-001", SOURCE),))
    inventories = build_held_out_inventories(
        catalog=catalog,
        tokens_by_digest={_digest(SOURCE): HO_TOKENS},
    )
    assert set(inventories) == {"AHE-001"}
    for constituent in inventories["AHE-001"].constituents:
        span = constituent.constituent_range
        assert SOURCE[span.start : span.end] == span.text


def test_render_held_out_selection_tasks_are_boundary_free() -> None:
    catalog = _catalog((_prop_event("AHE-001", SOURCE),))
    inventories = build_held_out_inventories(
        catalog=catalog,
        tokens_by_digest={_digest(SOURCE): HO_TOKENS},
    )
    tasks = render_held_out_selection_tasks(catalog=catalog, inventories=inventories)
    assert [task.event_id for task in tasks] == ["AHE-001"]
    task = tasks[0]
    assert "Event:" not in task.rendered_input
    labels = task.constituent_labels
    assert labels == tuple(f"C{i}" for i in range(1, len(labels) + 1))
    selected = parse_constituent_selection_answer(raw_answer=labels[0], task=task)
    assert selected.status is ConstituentSelectionStatus.SELECTED


def test_build_held_out_propositions_compose_typed_holds() -> None:
    catalog = _catalog((_prop_event("AHE-001", SOURCE),))
    tokens_by_digest = {_digest(SOURCE): HO_TOKENS}
    inventories = build_held_out_inventories(catalog=catalog, tokens_by_digest=tokens_by_digest)
    answer = ConstituentSelectionAnswer(
        event_id="AHE-001",
        status=ConstituentSelectionStatus.NONE,
        selected_label_indexes=(),
    )
    propositions = build_held_out_propositions(
        catalog=catalog,
        inventories=inventories,
        answers={"AHE-001": answer},
        tokens_by_digest=tokens_by_digest,
    )
    assert set(propositions) == {"AHE-001"}
    assert propositions["AHE-001"].status is DecontextualizationStatus.HELD


def test_held_out_gold_events_maps_to_evaluator_input() -> None:
    catalog = _catalog((_prop_event("AHE-001", SOURCE),))
    mapped = held_out_gold_events(catalog)
    assert set(mapped) == {"AHE-001"}
    assert mapped["AHE-001"].source_text_sha256 == _digest(SOURCE)
    assert [item.fragment_id for item in mapped["AHE-001"].fragments] == ["PGF-AHE-001-01"]
