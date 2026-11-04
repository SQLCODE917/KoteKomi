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


def test_saved_r20_outcomes_remain_readable(tmp_path: Path) -> None:
    """ISC-03-D: an already-persisted record keeps its binding, Assertion, and spans."""
    saved = Path(__file__).resolve().parents[3] / "data"
    candidates = sorted(saved.glob("*/composition-outcomes/*.json"))
    if not candidates:
        pytest.skip("no persisted composition outcome is present in this checkout")
    store = CompositionOutcomeStore(candidates[0].parent)
    record = store.load(candidates[0].stem)

    assert record.event_id == candidates[0].stem
    assert record.source_text_sha256
    if record.status is EventCompositionStatus.COMPOSED:
        assert record.assertion is not None
        assert record.supporting_subject_span is not None
    else:
        assert record.hold_reason
