"""Focused Pipeline-layer tests for R3 parser-constituent candidate generation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentSelectionStatus,
    CorrectedAttachmentGold,
    CorrectedCandidateLabel,
    EventEntityLinguisticToken,
    parse_constituent_selection_answer,
)
from kotekomi_pipelines.parser_constituent_candidate_generation import (
    build_event_inventories,
    build_partition_fidelity_censuses,
    build_partition_selection_censuses,
    build_r3_constituent_selection_report,
    derive_event_constituent_contracts,
    gold_fragment_refs_by_event,
    inventory_lookup,
    render_constituent_selection_review,
    render_event_selection_tasks,
    verify_frozen_evidence_digests,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragment,
    PropositionGoldFragmentRequirement,
    PropositionGoldReviewStatus,
)

DEV_SOURCE = "Acme fired Bob."
DEV_EVENT = (5, 10)  # "fired"
VAL_SOURCE = "Dell recalled laptops."
VAL_EVENT = (5, 13)  # "recalled"


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


DEV_TOKENS = (
    _token("t1", "s1", "Acme", 0, 4, "t2", deprel="nsubj"),
    _token("t2", "s1", "fired", 5, 10, None, deprel="root"),
    _token("t3", "s1", "Bob", 11, 14, "t2", deprel="obj"),
)

VAL_TOKENS = (
    _token("t1", "s1", "Dell", 0, 4, "t2", deprel="nsubj"),
    _token("t2", "s1", "recalled", 5, 13, None, deprel="root"),
    _token("t3", "s1", "laptops", 14, 21, "t2", deprel="obj"),
)


def _fragment(fragment_id: str, start: int, end: int, text: str) -> PropositionGoldFragment:
    return PropositionGoldFragment.model_construct(
        fragment_id=fragment_id,
        start=start,
        end=end,
        text=text,
        requirements=(PropositionGoldFragmentRequirement.CORE_EVENT,),
    )


def _event(
    event_id: str,
    phase: str,
    source_text: str,
    fragments: tuple[PropositionGoldFragment, ...],
) -> PropositionGoldEvent:
    return PropositionGoldEvent.model_construct(
        event_id=event_id,
        phase=phase,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        source_text=source_text,
        event_meaning="fixture",
        fragments=fragments,
        review_rationale="fixture",
    )


def _catalog(events: tuple[PropositionGoldEvent, ...]) -> PropositionGoldCatalog:
    return PropositionGoldCatalog.model_construct(
        schema_version="source_grounded_proposition_gold_v1",
        catalog_id="fixture",
        review_status=PropositionGoldReviewStatus.APPROVED,
        connection_gold_path="fixture",
        connection_gold_sha256="0" * 64,
        trigger_gold_path="fixture",
        trigger_gold_sha256="0" * 64,
        events=events,
    )


def _pipeline_state():
    dev_event = _event(
        "TGE-001", "development", DEV_SOURCE, (_fragment("PGF-TGE-001-01", 5, 10, "fired"),)
    )
    val_event = _event(
        "TGE-002", "validation", VAL_SOURCE, (_fragment("PGF-TGE-002-01", 5, 13, "recalled"),)
    )
    catalog = _catalog((dev_event, val_event))

    def digest(source: str) -> str:
        return hashlib.sha256(source.encode()).hexdigest()

    contracts = derive_event_constituent_contracts(
        catalog=catalog,
        tokens_by_digest={digest(DEV_SOURCE): DEV_TOKENS, digest(VAL_SOURCE): VAL_TOKENS},
        expressions_by_event={"TGE-001": DEV_EVENT, "TGE-002": VAL_EVENT},
        literals_by_event={"TGE-001": "fired", "TGE-002": "recalled"},
    )
    inventories = build_event_inventories(contracts)
    return catalog, contracts, inventories


def _corrected_gold() -> CorrectedAttachmentGold:
    return CorrectedAttachmentGold.model_construct(
        schema_version="corrected_attachment_gold_v1",
        catalog_id="fixture",
        source_catalog_sha256="0" * 64,
        corrected_labels=(
            CorrectedCandidateLabel.model_construct(
                candidate_id="cac_" + "1" * 24,
                phase="development",
                source_range=AttachmentSourceRange(start=5, end=10, text="fired"),
                gold_event_ids=("TGE-001",),
            ),
            CorrectedCandidateLabel.model_construct(
                candidate_id="cac_" + "2" * 24,
                phase="validation",
                source_range=AttachmentSourceRange(start=5, end=13, text="recalled"),
                gold_event_ids=("TGE-002",),
            ),
        ),
        resizes=(),
    )


def test_verify_frozen_evidence_digests_rejects_drift(tmp_path: Path) -> None:
    files = {
        "proposition_gold": tmp_path / "gold.json",
        "trigger_gold": tmp_path / "trigger.json",
        "connection_gold": tmp_path / "connection.json",
        "stanza_lock": tmp_path / "stanza.json",
    }
    for path in files.values():
        path.write_bytes(b"not the frozen evidence")
    with pytest.raises(ValueError, match="drifted from its pinned digest"):
        verify_frozen_evidence_digests(
            proposition_gold=files["proposition_gold"],
            trigger_gold=files["trigger_gold"],
            connection_gold=files["connection_gold"],
            stanza_lock=files["stanza_lock"],
        )


def test_derive_contracts_preserves_canonical_order_and_phase() -> None:
    _, contracts, _ = _pipeline_state()
    assert [contract.event_id for contract in contracts] == ["TGE-001", "TGE-002"]
    assert [contract.phase for contract in contracts] == ["development", "validation"]
    assert contracts[0].source_text == DEV_SOURCE
    assert contracts[0].event_expression_start == 5
    assert contracts[0].event_expression_end == 10
    assert contracts[0].event_literal == "fired"
    assert contracts[0].tokens == DEV_TOKENS


def test_build_event_inventories_and_lookup() -> None:
    _, _, inventories = _pipeline_state()
    assert [item.event_id for item in inventories] == ["TGE-001", "TGE-002"]
    lookup = inventory_lookup(inventories)
    assert set(lookup) == {"TGE-001", "TGE-002"}
    for event_id, inventory in lookup.items():
        assert inventory.event_id == event_id


def test_gold_fragment_refs_by_event() -> None:
    catalog, _, _ = _pipeline_state()
    refs = gold_fragment_refs_by_event(catalog)
    assert set(refs) == {"TGE-001", "TGE-002"}
    assert refs["TGE-001"][0].fragment_id == "PGF-TGE-001-01"
    assert (refs["TGE-001"][0].start, refs["TGE-001"][0].end) == (5, 10)


def test_fidelity_census_covers_exact_fragment_spans() -> None:
    catalog, _, inventories = _pipeline_state()
    development, validation = build_partition_fidelity_censuses(
        catalog=catalog, inventories=inventory_lookup(inventories)
    )
    assert development.partition_role == "development"
    assert validation.partition_role == "validation"
    assert development.covered_fragment_ids == ("PGF-TGE-001-01",)
    assert development.missed_fragments == ()
    assert development.pool_ceiling == 1.0
    assert validation.covered_fragment_ids == ("PGF-TGE-002-01",)
    assert validation.pool_ceiling == 1.0


def test_fidelity_census_lists_missed_fragments_and_lowers_ceiling() -> None:
    dev_event = _event(
        "TGE-001",
        "development",
        DEV_SOURCE,
        (
            _fragment("PGF-TGE-001-01", 1, 3, "cm"),
            _fragment("PGF-TGE-001-02", 5, 10, "fired"),
        ),
    )
    val_event = _event(
        "TGE-002", "validation", VAL_SOURCE, (_fragment("PGF-TGE-002-01", 5, 13, "recalled"),)
    )
    catalog = _catalog((dev_event, val_event))

    def digest(source: str) -> str:
        return hashlib.sha256(source.encode()).hexdigest()

    contracts = derive_event_constituent_contracts(
        catalog=catalog,
        tokens_by_digest={digest(DEV_SOURCE): DEV_TOKENS, digest(VAL_SOURCE): VAL_TOKENS},
        expressions_by_event={"TGE-001": DEV_EVENT, "TGE-002": VAL_EVENT},
        literals_by_event={"TGE-001": "fired", "TGE-002": "recalled"},
    )
    development, _ = build_partition_fidelity_censuses(
        catalog=catalog, inventories=inventory_lookup(build_event_inventories(contracts))
    )
    assert development.covered_fragment_ids == ("PGF-TGE-001-02",)
    assert [item.fragment_id for item in development.missed_fragments] == ["PGF-TGE-001-01"]
    assert development.pool_ceiling == 0.5


def test_render_tasks_use_stable_labels_and_parse_finite_answers() -> None:
    _, contracts, inventories = _pipeline_state()
    tasks = render_event_selection_tasks(
        contracts=contracts, inventories=inventory_lookup(inventories)
    )
    assert [task.event_id for task in tasks] == ["TGE-001", "TGE-002"]
    assert tasks[0].constituent_labels == ("C1", "C2", "C3", "C4")
    selected = parse_constituent_selection_answer(raw_answer="C2", task=tasks[0])
    assert selected.status is ConstituentSelectionStatus.SELECTED
    assert selected.selected_label_indexes == (2,)
    none = parse_constituent_selection_answer(raw_answer="NONE", task=tasks[1])
    assert none.status is ConstituentSelectionStatus.NONE
    rejected = parse_constituent_selection_answer(raw_answer="C9", task=tasks[0])
    assert rejected.status is ConstituentSelectionStatus.REJECTED


def test_selection_census_scores_against_corrected_gold() -> None:
    catalog, contracts, inventories = _pipeline_state()
    lookup = inventory_lookup(inventories)
    tasks = render_event_selection_tasks(contracts=contracts, inventories=lookup)
    answers = {
        task.event_id: parse_constituent_selection_answer(
            raw_answer="C3" if task.event_id == "TGE-001" else "NONE", task=task
        )
        for task in tasks
    }
    development, validation = build_partition_selection_censuses(
        catalog=catalog, inventories=lookup, answers=answers, corrected=_corrected_gold()
    )
    assert development.selected_event_count == 1
    assert development.none_event_count == 0
    assert development.exact_attachment_count == 1
    assert development.false_positive_span_count == 0
    assert development.false_negative_span_count == 0
    assert validation.selected_event_count == 0
    assert validation.none_event_count == 1
    assert validation.exact_attachment_count == 0
    assert validation.false_negative_span_count == 1


def test_report_assembles_and_review_mentions_zero_writes() -> None:
    catalog, contracts, inventories = _pipeline_state()
    lookup = inventory_lookup(inventories)
    tasks = render_event_selection_tasks(contracts=contracts, inventories=lookup)
    answers = {
        task.event_id: parse_constituent_selection_answer(
            raw_answer="C3" if task.event_id == "TGE-001" else "NONE", task=task
        )
        for task in tasks
    }
    report = build_r3_constituent_selection_report(
        catalog=catalog,
        inventories=lookup,
        answers=answers,
        corrected=_corrected_gold(),
        corrected_gold_sha256="0" * 64,
        model_execution_count=2,
    )
    assert report.model_execution_count == 2
    assert report.development_fidelity.pool_ceiling == 1.0
    assert report.validation_selection.none_event_count == 1
    review = render_constituent_selection_review(report=report)
    assert "Canonical writes: 0" in review
    assert "ProposedChanges: 0" in review
    assert "pool ceiling: `1.000000`" in review
