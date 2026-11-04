"""ISC-03: one Adapter persists Event composition outcomes.

These checks exercise the real filesystem Adapter that ingestion, recomposition,
and replay share. They use a disposable directory, never the operator's Ledger.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import EventCompositionRecord, EventCompositionStatus, SourceRange
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    SourceAuthority,
)

_SHA = "a" * 64


def _held(event_id: str = "AHE-001") -> EventCompositionRecord:
    return EventCompositionRecord(
        event_id=event_id,
        source_text_sha256=_SHA,
        status=EventCompositionStatus.HELD,
        hold_reason="assertion_inputs_unavailable",
    )


def _composed(event_id: str = "AHE-001") -> EventCompositionRecord:
    assertion = Assertion(
        id="ast_isc03",
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="act_alpha",
        predicate="supports",
        object_value="the reviewed assertion",
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_ids=("src_isc03",),
        evidence_target_ids=("etg_isc03",),
    )
    return EventCompositionRecord(
        event_id=event_id,
        source_text_sha256=_SHA,
        status=EventCompositionStatus.COMPOSED,
        relation_label="support",
        subject_text="Alpha",
        object_text="the reviewed assertion",
        assertion=assertion,
        supporting_subject_span=SourceRange(start=0, end=5, text="Alpha"),
    )


def test_ingestion_recomposition_and_replay_share_one_store(tmp_path: Path) -> None:
    """ISC-03-A: saving and reading through the Adapter round-trips one record."""
    store = CompositionOutcomeStore(tmp_path / "composition-outcomes")
    store.save(_held("AHE-001"))
    store.save(_composed("AHE-002"))

    held = store.load("AHE-001")
    assert (held.event_id, held.status, held.hold_reason) == (
        "AHE-001",
        EventCompositionStatus.HELD,
        "assertion_inputs_unavailable",
    )
    composed = store.load("AHE-002")
    assert (composed.event_id, composed.status, composed.relation_label) == (
        "AHE-002",
        EventCompositionStatus.COMPOSED,
        "support",
    )
    assert composed.assertion is not None
    assert composed.assertion.predicate == "supports"
    assert composed.supporting_subject_span == SourceRange(start=0, end=5, text="Alpha")
    annotations = store.annotations(("AHE-002", "AHE-999"))
    assert [item.event_id for item in annotations] == ["AHE-002"]
    assert annotations[0].status == "composed"
    assert annotations[0].span is not None
    assert annotations[0].span.text == "Alpha"


def test_interrupted_replacement_preserves_the_previous_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ISC-03-B: a reader observes the previous complete record after a failure."""
    store = CompositionOutcomeStore(tmp_path / "composition-outcomes")
    store.save(_held("AHE-001"))

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr("kotekomi_adapters.composition_outcome_store.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.save(_composed("AHE-001"))

    assert store.load("AHE-001") == _held("AHE-001")
    leftovers = sorted(path.name for path in store.root.iterdir())
    assert leftovers == ["AHE-001.json"]


def test_corrupt_record_raises_a_validation_error(tmp_path: Path) -> None:
    """ISC-03-C: a corrupt record is a validation error, not an empty result."""
    store = CompositionOutcomeStore(tmp_path / "composition-outcomes")
    store.save(_held("AHE-001"))
    (store.root / "AHE-001.json").write_text(
        json.dumps({"event_id": "AHE-001", "status": "composed"}), encoding="utf-8"
    )

    with pytest.raises(ValueError):
        store.load("AHE-001")
    with pytest.raises(ValueError):
        store.annotations(("AHE-001",))


def test_saved_outcomes_keep_assertions_and_spans() -> None:
    """ISC-03-D: committed pre-cleanup outcomes stay readable with their values."""
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "composition_outcomes"
    store = CompositionOutcomeStore(fixture_root)

    held = store.load("TGE-018")
    assert held.status is EventCompositionStatus.HELD
    assert held.hold_reason == "awaiting_acceptance"
    assert held.unavailable_reference == "act_david_sacks"
    assert held.source_text_sha256 == (
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    )

    composed = store.load("AHE-022")
    assert composed.status is EventCompositionStatus.COMPOSED
    assert composed.relation_label == "viewed"
    assert composed.subject_text == "Sacks"
    assert composed.object_text == "Amodei's decision"
    assert composed.assertion is not None
    assert composed.assertion.id == "ast_5f0d9a2f4c8e4f8f9d1b7c3a2e6d4b8a"
    assert composed.assertion.predicate == "viewed"
    assert composed.assertion.subject_entity_id == "act_david_sacks"
    assert composed.assertion.object_value == "Amodei's decision"
    assert composed.assertion.qualifiers == {"polarity": "affirmed", "modality": "actual"}
    assert composed.assertion.source_ids == ("src_d97195ee5c8ced32c0cd41b0",)
    assert composed.assertion.evidence_target_ids == ("etg_ahe_022",)
    assert composed.supporting_subject_span == SourceRange(start=0, end=5, text="Sacks")

    annotations = store.annotations(("TGE-018", "AHE-022"))
    assert [item.status for item in annotations] == ["held", "composed"]
    assert annotations[1].span is not None
    assert annotations[1].span.text == "Sacks"
