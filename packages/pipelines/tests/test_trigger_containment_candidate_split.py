"""Focused tests for the R2 trigger-containment Pipeline layer.

These tests cover candidate-ID derivation, the candidate universe, trigger
materialization, the corrected Gold, and the Markdown review.  Small synthetic
Catalogs exercise the split logic, and one integration test pins the frozen
187-candidate universe.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentPartitionRole,
    AttachmentRouteDecision,
    AttachmentRouteKind,
    build_correction_partition_report,
    build_trigger_containment_correction_report,
)
from kotekomi_pipelines.event_trigger_stage_local import TriggerGoldCatalog
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragment,
    PropositionGoldFragmentRequirement,
    PropositionGoldReviewStatus,
    load_proposition_gold_catalog,
)
from kotekomi_pipelines.trigger_containment_candidate_split import (
    CORRECTED_CATALOG_ID,
    build_candidate_universe,
    correct_attachment_gold,
    corrected_gold_file_bytes,
    materialize_event_triggers,
    render_trigger_containment_correction_review,
    source_by_digest,
    trigger_containment_candidate_id,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_PROPOSITION_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
_TRIGGER_GOLD = REPOSITORY_ROOT / "docs/hsq-event-trigger-gold-v1.json"

_FAKE_SHA = "a" * 64


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
        event_meaning="fixture meaning",
        fragments=fragments,
        review_rationale="fixture rationale",
    )


def _catalog(events: tuple[PropositionGoldEvent, ...]) -> PropositionGoldCatalog:
    return PropositionGoldCatalog.model_construct(
        schema_version="source_grounded_proposition_gold_v1",
        catalog_id="fixture",
        review_status=PropositionGoldReviewStatus.APPROVED,
        connection_gold_path="connection.json",
        connection_gold_sha256=_FAKE_SHA,
        trigger_gold_path="trigger.json",
        trigger_gold_sha256=_FAKE_SHA,
        events=events,
    )


def _PROPOSITION_GOLD_SHA() -> str:
    return hashlib.sha256(_PROPOSITION_GOLD.read_bytes()).hexdigest()


def test_trigger_containment_candidate_id_is_deterministic() -> None:
    first = trigger_containment_candidate_id(_FAKE_SHA, 0, 5)
    second = trigger_containment_candidate_id(_FAKE_SHA, 0, 5)
    other = trigger_containment_candidate_id(_FAKE_SHA, 0, 6)
    assert first == second
    assert first != other
    assert first.startswith("cac_")
    assert len(first) == 28


def test_source_by_digest_maps_and_rejects_collision() -> None:
    source = "foo bar baz"
    sha = hashlib.sha256(source.encode()).hexdigest()
    catalog = _catalog(
        (
            _event("TGE-001", "development", source, (_fragment("PGF-TGE-001-01", 0, 3, "foo"),)),
            _event("TGE-002", "development", source, (_fragment("PGF-TGE-002-01", 4, 7, "bar"),)),
        )
    )
    assert source_by_digest(catalog) == {sha: source}

    catalog_with_conflict = _catalog(
        (
            PropositionGoldEvent.model_construct(
                event_id="TGE-001",
                phase="development",
                source_text_sha256=sha,
                source_text="foo bar baz",
                event_meaning="fixture meaning",
                fragments=(),
                review_rationale="fixture rationale",
            ),
            PropositionGoldEvent.model_construct(
                event_id="TGE-002",
                phase="development",
                source_text_sha256=sha,
                source_text="different text",
                event_meaning="fixture meaning",
                fragments=(),
                review_rationale="fixture rationale",
            ),
        )
    )
    with pytest.raises(ValueError):
        source_by_digest(catalog_with_conflict)


def test_build_candidate_universe_groups_shared_fragments() -> None:
    source = "foo bar"
    sha = hashlib.sha256(source.encode()).hexdigest()
    catalog = _catalog(
        (
            _event(
                "TGE-001",
                "development",
                source,
                (
                    _fragment("PGF-TGE-001-01", 0, 3, "foo"),
                    _fragment("PGF-TGE-001-02", 4, 7, "bar"),
                ),
            ),
            _event(
                "TGE-002",
                "development",
                source,
                (_fragment("PGF-TGE-002-01", 0, 3, "foo"),),
            ),
        )
    )
    universe = build_candidate_universe(catalog)
    assert len(universe) == 2
    by_range = {(item.source_range.start, item.source_range.end): item for item in universe}
    shared = by_range[(0, 3)]
    assert shared.gold_event_ids == ("TGE-001", "TGE-002")
    assert shared.candidate_id == trigger_containment_candidate_id(sha, 0, 3)
    assert by_range[(4, 7)].gold_event_ids == ("TGE-001",)
    assert tuple(item.candidate_id for item in universe) == tuple(
        sorted(item.candidate_id for item in universe)
    )


def _decision(
    candidate_id: str,
    *,
    partition_role: AttachmentPartitionRole,
    route_kind: AttachmentRouteKind,
) -> AttachmentRouteDecision:
    informing = (
        "development" if partition_role is AttachmentPartitionRole.DEVELOPMENT else "validation"
    )
    allowed = ("sge_" + "b" * 24,) if route_kind is AttachmentRouteKind.ATTACHED else ()
    return AttachmentRouteDecision(
        candidate_id=candidate_id,
        partition_role=partition_role,
        informing_partition=informing,
        route_kind=route_kind,
        allowed_event_ids=allowed,
        selected_policy="path_1" if route_kind is AttachmentRouteKind.ATTACHED else None,
        path_1_supported=route_kind is AttachmentRouteKind.ATTACHED,
        trigger_containment=False,
    )


def _cid(suffix: str) -> str:
    return "cac_" + (suffix * 24)[:24]


def _eid(ordinal: int) -> str:
    return f"TGE-{ordinal:03d}"


def test_render_trigger_containment_correction_review_shows_before_after() -> None:
    development = build_correction_partition_report(
        partition_role="development",
        decisions=(
            _decision(
                _cid("a"),
                partition_role=AttachmentPartitionRole.DEVELOPMENT,
                route_kind=AttachmentRouteKind.MODEL_REVIEW,
            ),
        ),
        before_attachment={_cid("a"): ()},
        before_mixed={_cid("a"): False},
        before_temporal={_cid("a"): False},
        after_attachment={_cid("a"): (_eid(1), _eid(2))},
        after_mixed={_cid("a"): True},
        after_temporal={_cid("a"): False},
    )
    validation = build_correction_partition_report(
        partition_role="validation",
        decisions=(
            _decision(
                _cid("c"),
                partition_role=AttachmentPartitionRole.VALIDATION,
                route_kind=AttachmentRouteKind.MODEL_REVIEW,
            ),
        ),
        before_attachment={_cid("c"): ()},
        before_mixed={_cid("c"): False},
        before_temporal={_cid("c"): False},
        after_attachment={_cid("c"): ()},
        after_mixed={_cid("c"): False},
        after_temporal={_cid("c"): False},
    )
    report = build_trigger_containment_correction_report(
        development=development,
        validation=validation,
        corrected_gold_sha256=_FAKE_SHA,
    )
    corrected = correct_attachment_gold(
        catalog=load_proposition_gold_catalog(_PROPOSITION_GOLD, repository_root=REPOSITORY_ROOT),
        trigger_gold=TriggerGoldCatalog.model_validate_json(_TRIGGER_GOLD.read_bytes()),
        source_catalog_sha256=_PROPOSITION_GOLD_SHA(),
    )
    review = render_trigger_containment_correction_review(corrected=corrected, report=report)
    assert "## Error-class re-score" in review
    assert "### development" in review
    assert "### validation" in review
    assert "`none`" in review and "-> `0`" in review
    assert "## Changed candidates" in review
    assert "Changed candidates: `1`" in review
    assert "## Resized candidates" in review
    assert "Model executions: `0`" in review


def test_correct_attachment_gold_pins_frozen_universe() -> None:
    catalog = load_proposition_gold_catalog(_PROPOSITION_GOLD, repository_root=REPOSITORY_ROOT)
    trigger_gold = TriggerGoldCatalog.model_validate_json(_TRIGGER_GOLD.read_bytes())
    corrected = correct_attachment_gold(
        catalog=catalog,
        trigger_gold=trigger_gold,
        source_catalog_sha256=_PROPOSITION_GOLD_SHA(),
    )
    assert len(corrected.corrected_labels) == 187
    assert len(corrected.resizes) == 18
    assert corrected.catalog_id == CORRECTED_CATALOG_ID
    # Every resize excludes its foreign trigger text from the resized range.
    for resize in corrected.resizes:
        for foreign in resize.foreign_trigger_ranges:
            assert not (resize.resized_range.start <= foreign.start < resize.resized_range.end)
            assert not (resize.resized_range.start < foreign.end <= resize.resized_range.end)


def test_materialize_event_triggers_is_source_exact() -> None:
    trigger_gold = TriggerGoldCatalog.model_validate_json(_TRIGGER_GOLD.read_bytes())
    triggers = materialize_event_triggers(trigger_gold)
    assert len(triggers) > 0
    for trigger in triggers:
        assert trigger.source_range.text == trigger.source_range.text
        assert trigger.event_id.startswith("TGE-")


def test_corrected_gold_file_bytes_preserves_events_and_roundtrips() -> None:
    catalog = load_proposition_gold_catalog(_PROPOSITION_GOLD, repository_root=REPOSITORY_ROOT)
    trigger_gold = TriggerGoldCatalog.model_validate_json(_TRIGGER_GOLD.read_bytes())
    corrected = correct_attachment_gold(
        catalog=catalog,
        trigger_gold=trigger_gold,
        source_catalog_sha256=_PROPOSITION_GOLD_SHA(),
    )
    data = corrected_gold_file_bytes(catalog=catalog, corrected=corrected)
    payload = json.loads(data)
    assert payload["schema_version"] == "corrected_attachment_gold_v1"
    assert len(payload["events"]) == 40
    assert len(payload["corrected_labels"]) == 187
    assert len(payload["resizes"]) == 18
    assert data.endswith(b"\n")


def test_render_review_lists_off_universe_census() -> None:
    development = build_correction_partition_report(
        partition_role="development",
        decisions=(
            _decision(
                _cid("a"),
                partition_role=AttachmentPartitionRole.DEVELOPMENT,
                route_kind=AttachmentRouteKind.MODEL_REVIEW,
            ),
        ),
        before_attachment={_cid("a"): ()},
        before_mixed={_cid("a"): False},
        before_temporal={_cid("a"): False},
        after_attachment={_cid("a"): ()},
        after_mixed={_cid("a"): False},
        after_temporal={_cid("a"): False},
        off_universe_candidate_ids=(_cid("b"),),
    )
    validation = build_correction_partition_report(
        partition_role="validation",
        decisions=(
            _decision(
                _cid("c"),
                partition_role=AttachmentPartitionRole.VALIDATION,
                route_kind=AttachmentRouteKind.MODEL_REVIEW,
            ),
        ),
        before_attachment={_cid("c"): ()},
        before_mixed={_cid("c"): False},
        before_temporal={_cid("c"): False},
        after_attachment={_cid("c"): ()},
        after_mixed={_cid("c"): False},
        after_temporal={_cid("c"): False},
        off_universe_candidate_ids=(_cid("d"), _cid("e")),
    )
    report = build_trigger_containment_correction_report(
        development=development,
        validation=validation,
        corrected_gold_sha256=_FAKE_SHA,
    )
    corrected = correct_attachment_gold(
        catalog=load_proposition_gold_catalog(_PROPOSITION_GOLD, repository_root=REPOSITORY_ROOT),
        trigger_gold=TriggerGoldCatalog.model_validate_json(_TRIGGER_GOLD.read_bytes()),
        source_catalog_sha256=_PROPOSITION_GOLD_SHA(),
    )
    review = render_trigger_containment_correction_review(corrected=corrected, report=report)
    assert "## Off-universe candidates (carried, not re-scored)" in review
    assert "- development: `1`" in review
    assert "- validation: `2`" in review
