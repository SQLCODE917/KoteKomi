"""Replay display of the R20 Event composition outcome (held and composed)."""

from __future__ import annotations

from pathlib import Path

from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_adapters.extraction_view.render import render_annotated_paragraph
from kotekomi_application import (
    EventCompositionRecord,
    EventCompositionStatus,
    SourceRange,
)
from kotekomi_application.ingestion_inspection import (
    CompositionAnnotation,
    ParagraphAnnotationProfile,
)
from kotekomi_application.source_grounded_reference_composition import (
    composition_annotation,
)
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    SourceAuthority,
)

_SHA = "a" * 64


def _profile(composition: tuple[CompositionAnnotation, ...]) -> ParagraphAnnotationProfile:
    return ParagraphAnnotationProfile(
        text="Alpha supports the reviewed assertion.",
        representation_id="rep_r20",
        paragraph_node_id="nod_r20",
        node_start_char=0,
        text_view_id="tvw_r20",
        segments=(),
        mentions=(),
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        standing_facts=(),
        present_stages=frozenset(),
        composition=composition,
    )


def test_held_composition_renders_in_replay() -> None:
    record = EventCompositionRecord(
        event_id="AHE-001",
        source_text_sha256=_SHA,
        status=EventCompositionStatus.HELD,
        hold_reason="awaiting_acceptance",
        unavailable_reference="act_alpha",
    )
    annotation = composition_annotation(record)

    rendered = render_annotated_paragraph(_profile((annotation,)), frozenset())

    assert "composition" in rendered
    assert "AHE-001 · held · held: awaiting_acceptance (missing act_alpha)" in rendered


def test_composed_composition_renders_assertion_with_span() -> None:
    assertion = Assertion(
        id="ast_r20",
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="act_alpha",
        predicate="supports",
        object_value="the reviewed assertion",
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_ids=("src_r20",),
        evidence_target_ids=("etg_r20",),
    )
    record = EventCompositionRecord(
        event_id="AHE-001",
        source_text_sha256=_SHA,
        status=EventCompositionStatus.COMPOSED,
        relation_label="support",
        subject_text="Alpha",
        object_text="the reviewed assertion",
        assertion=assertion,
        supporting_subject_span=SourceRange(start=0, end=5, text="Alpha"),
        supporting_object_span=SourceRange(start=15, end=37, text="the reviewed assertion"),
    )
    annotation = composition_annotation(record)

    rendered = render_annotated_paragraph(_profile((annotation,)), frozenset())

    assert "AHE-001 · composed · composed: support Alpha -> the reviewed assertion" in rendered


def test_composition_store_loads_persisted_outcome(tmp_path: Path) -> None:
    record = EventCompositionRecord(
        event_id="AHE-001",
        source_text_sha256=_SHA,
        status=EventCompositionStatus.HELD,
        hold_reason="awaiting_acceptance",
        unavailable_reference="act_alpha",
    )
    store = CompositionOutcomeStore(tmp_path / "composition-outcomes")
    store.save(record)

    annotations = store.annotations(("AHE-001", "AHE-999"))

    assert [item.event_id for item in annotations] == ["AHE-001"]
    assert annotations[0].status == "held"
    assert "awaiting_acceptance" in annotations[0].summary
