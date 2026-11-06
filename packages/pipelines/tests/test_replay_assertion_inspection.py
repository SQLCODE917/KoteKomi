"""Composed intelligence participates in interactive annotation inspection."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Collection
from dataclasses import replace
from pathlib import Path

import pytest
from kotekomi_adapters.extraction_view.render import annotated_rows, profile_annotations
from kotekomi_adapters.extraction_view.tui import MessageStream, ReplayApp
from kotekomi_application.composition_inspection import (
    COMPOSITION_LAYER,
    INSPECTION_LAYERS,
    enrich_composition_annotation,
)
from kotekomi_application.ingestion_debug_summary import (
    DebugSummary,
    SnapshotOperation,
    build_debug_summary,
)
from kotekomi_application.ingestion_inspection import (
    EventAnnotation,
    ParagraphAnnotationProfile,
    ParagraphSnapshot,
    Span,
)
from kotekomi_application.source_grounded_reference_composition import (
    EventCompositionRecord,
    EventCompositionStatus,
    composition_annotation,
)
from kotekomi_application.source_ranges import SourceRange
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    Organization,
    ProposedAssertion,
    ProposedChange,
    ReviewStatus,
    SourceAuthority,
)
from rich.text import Text
from textual.widgets import Static

TEXT = "The US started the 2026 Iran war."
EVENT = "sge_inspection"


def composed_profile() -> ParagraphAnnotationProfile:
    assertion = Assertion(
        id="ast_inspection",
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_us",
        predicate="started",
        object_value="the 2026 Iran war",
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_ids=("src_inspection",),
        evidence_target_ids=("etg_inspection",),
        qualifiers={"polarity": "affirmed", "modality": "actual"},
    )
    outcome = EventCompositionRecord(
        event_id=EVENT,
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        status=EventCompositionStatus.COMPOSED,
        relation_label="start",
        subject_text="The US",
        object_text="the 2026 Iran war",
        assertion=assertion,
        supporting_subject_span=SourceRange(start=0, end=6, text="The US"),
        supporting_object_span=SourceRange(start=15, end=32, text="the 2026 Iran war"),
    )
    return ParagraphAnnotationProfile(
        text=TEXT,
        representation_id="rep_inspection",
        paragraph_node_id="nod_inspection",
        node_start_char=0,
        text_view_id="tvw_inspection",
        segments=(),
        mentions=(),
        references=(),
        groundings=(),
        triggers=(),
        events=(EventAnnotation(EVENT, Span(7, 14, "started"), "start", "started", "started"),),
        standing_facts=(),
        present_stages=frozenset({"hp6_event_semantics"}),
        composition=(composition_annotation(outcome),),
    )


def test_composition_is_an_interactive_annotation() -> None:
    annotations = profile_annotations(composed_profile())
    composed = [item for item in annotations if item.stage == "composition"]
    assert len(composed) == 1
    assert "started" in composed[0].label
    assert {span.text for span in (composed[0].span, *composed[0].related_spans)} == {
        "The US",
        "started",
        "the 2026 Iran war",
    }


def reviewed_profile(status: ReviewStatus = ReviewStatus.PENDING) -> ParagraphAnnotationProfile:
    profile = composed_profile()
    annotation = profile.composition[0]
    assertion = annotation.assertion
    assert assertion is not None
    proposed = ProposedAssertion(
        id=assertion.id,
        assertion_type=assertion.assertion_type,
        epistemic_scope=assertion.epistemic_scope,
        subject_entity_id=assertion.subject_entity_id,
        relation_label=assertion.predicate,
        object_value=assertion.object_value,
        source_authority=assertion.source_authority,
        attribution_basis=assertion.attribution_basis,
        qualifiers=assertion.qualifiers,
        source_ids=assertion.source_ids,
        evidence_target_ids=assertion.evidence_target_ids,
    )
    proposal = ProposedChange(
        id="pcg_inspection",
        review_status=status,
        proposed_json={
            "record_type": "Assertion",
            "stable_label": assertion.id,
            "record": proposed.model_dump(mode="json"),
        },
    )
    annotation = enrich_composition_annotation(
        annotation, subject=Organization(id="org_us", name="United States"), proposals=(proposal,)
    )
    return replace(
        profile,
        composition=(
            replace(
                annotation,
                outcome_path=f"composition-outcomes/{EVENT}.json",
                outcome_sha256="a" * 64,
            ),
        ),
    )


def capture(
    profile: ParagraphAnnotationProfile,
    *,
    visible: Collection[str] = INSPECTION_LAYERS,
    selected: str | None = f"composition:{EVENT}",
) -> DebugSummary:
    return build_debug_summary(
        profile,
        ordinal=13,
        paragraph_status="complete",
        operation=SnapshotOperation(mode="replay", status="complete", exit_code=0),
        visible_stages=visible,
        selected_key=selected,
        context=None,
    )


@pytest.mark.parametrize(
    "status", [ReviewStatus.PENDING, ReviewStatus.APPROVED, ReviewStatus.REJECTED]
)
def test_copy_contains_compact_assertion_review_evidence_and_file_handles(
    status: ReviewStatus,
) -> None:
    copied = capture(reviewed_profile(status))
    raw = copied.clipboard_json()
    assert DebugSummary.model_validate_json(raw) == copied
    assert copied.selected_record_id == "ast_inspection"
    record = copied.records[COMPOSITION_LAYER][0]
    assert record.data["predicate"] == "started"
    assert record.data["subject"] == "United States"
    assert record.data["assertion_status"] == "proposed"
    assert record.data["proposals"] == [{"id": "pcg_inspection", "review_status": status.value}]
    assert record.data["outcome_path"] == f"composition-outcomes/{EVENT}.json"
    assert "etg_inspection" in record.related_ids
    assert {copied.spans[index] for index in record.spans} == {(0, 6), (7, 14), (15, 32)}
    assert len(raw.encode()) < 2300
    assert "viewport" not in raw
    assert "created_at" not in raw


def test_copy_omits_hidden_composition() -> None:
    copied = capture(reviewed_profile(), visible=("hp6_event_semantics",), selected=None)
    assert COMPOSITION_LAYER not in copied.records
    assert not copied.composition_enabled


@pytest.mark.parametrize(
    "field,value", [("outcome_path", "../outside.json"), ("outcome_sha256", "invalid")]
)
def test_copied_composition_rejects_invalid_file_handles(field: str, value: str) -> None:
    raw = json.loads(capture(reviewed_profile()).model_dump_json())
    raw["records"][COMPOSITION_LAYER][0]["data"][field] = value
    with pytest.raises(ValueError):
        DebugSummary.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("subject", [None, Organization(id="org_other", name="Other")])
def test_missing_or_mismatched_accepted_subject_fails(subject: Organization | None) -> None:
    with pytest.raises(ValueError, match="missing accepted subject identity"):
        enrich_composition_annotation(
            composed_profile().composition[0], subject=subject, proposals=()
        )


def test_selected_assertion_highlights_all_linked_spans_across_wrapping() -> None:
    rows = annotated_rows(reviewed_profile(), INSPECTION_LAYERS, 18, f"composition:{EVENT}")
    highlighted = "".join(
        row.text.plain[span.start : span.end]
        for row in rows
        for span in row.text.spans
        if span.style == "bold reverse"
    )
    assert "The US" in highlighted
    assert "started" in highlighted
    assert "the 2026 Iran war" in highlighted


@pytest.mark.parametrize("corruption", ["digest", "span", "event", "artifact"])
def test_invalid_composition_bindings_fail(corruption: str) -> None:
    profile = reviewed_profile()
    item = profile.composition[0]
    if corruption == "digest":
        item = replace(item, source_text_sha256="b" * 64)
    elif corruption == "span":
        item = replace(item, object_span=Span(15, 32, "x" * 17))
    elif corruption == "event":
        item = replace(item, event_id="sge_other")
    else:
        item = replace(item, outcome_path="../outside.json")
    with pytest.raises(ValueError):
        capture(replace(profile, composition=(item,)))


def test_held_event_is_selectable_and_copied_without_assertion() -> None:
    profile = composed_profile()
    outcome = EventCompositionRecord(
        event_id=EVENT,
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        status=EventCompositionStatus.HELD,
        hold_reason="awaiting_acceptance",
        unavailable_reference="US",
    )
    profile = replace(profile, composition=(composition_annotation(outcome),))
    row = profile_annotations(profile)[0]
    assert "Composition held" in row.label
    copied = capture(profile)
    record = copied.records[COMPOSITION_LAYER][0]
    assert record.record_type == "EventCompositionHold"
    assert record.data["hold_reason"] == "awaiting_acceptance"
    assert "assertion_status" not in record.data


def test_store_handles_bind_the_actual_bytes_and_reject_wrong_event(tmp_path: Path) -> None:
    from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore

    store = CompositionOutcomeStore(tmp_path / "composition-outcomes")
    outcome = EventCompositionRecord(
        event_id="AHE-001",
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        status=EventCompositionStatus.HELD,
        hold_reason="awaiting_acceptance",
    )
    store.save(outcome)
    annotation = store.annotations(("AHE-001",))[0]
    assert (
        annotation.outcome_sha256
        == hashlib.sha256((store.root / "AHE-001.json").read_bytes()).hexdigest()
    )
    (store.root / "AHE-002.json").write_bytes((store.root / "AHE-001.json").read_bytes())
    with pytest.raises(ValueError, match="filename and Event ID"):
        store.annotations(("AHE-002",))


def test_textual_assertion_shortcut_cycle_click_hide_and_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kotekomi_adapters.extraction_view import clipboard

    monkeypatch.setattr(clipboard, "platform", "linux")
    profile = reviewed_profile()

    def content(app: ReplayApp, selector: str) -> str:
        text = app.query_one(selector, Static).content
        assert isinstance(text, Text)
        return text.plain

    def operation(
        publish: Callable[[ParagraphSnapshot], None], _out: MessageStream, _err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, profile, "complete"))
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test(size=(130, 36)) as pilot:
            await pilot.pause()
            assert "United States → started → the 2026 Iran war" in content(app, "#inspector")
            assert "Review: pending" in content(app, "#inspector")
            assert "etg_inspection" in content(app, "#inspector")
            assert "pcg_inspection" in content(app, "#inspector")
            await pilot.press("n")
            assert app.selected_keys[0] == "hp6_event_semantics:0"
            await pilot.press("p")
            assert app.selected_keys[0] == f"composition:{EVENT}"
            await pilot.press("n")
            await pilot.click("#source", offset=(12, 1))
            assert app.selected_keys[0] == f"composition:{EVENT}"
            await pilot.press("8")
            assert "Assertion ·" not in content(app, "#source")
            await pilot.press("c")
            assert COMPOSITION_LAYER not in DebugSummary.model_validate_json(app.clipboard).records
            await pilot.press("a", "c")
            assert app.selected_keys[0] == f"composition:{EVENT}"
            copied = DebugSummary.model_validate_json(app.clipboard)
            assert copied.selected_record_id == "ast_inspection"
            assert copied.records[COMPOSITION_LAYER][0].data["predicate"] == "started"
            assert "proposed" in content(app, "#source")
            await pilot.press("q")

    asyncio.run(scenario())
