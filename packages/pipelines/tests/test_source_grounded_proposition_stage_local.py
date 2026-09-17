from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest
from kotekomi_application import (
    EventEntityKind,
    PropositionFragmentCandidate,
    PropositionFragmentReason,
    PropositionScopeStatus,
    SourceGroundedPropositionFragment,
    SourceGroundedPropositionScope,
    proposition_fragment_candidate_id,
    source_grounded_proposition_fragment_id,
    source_grounded_proposition_scope_id,
)
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldEntity,
    ConnectionGoldSourceOccurrence,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragment,
    PropositionGoldFragmentRequirement,
    PropositionGoldReviewStatus,
    evaluate_proposition_candidate_preflight,
    evaluate_proposition_scope_case,
    load_proposition_gold_catalog,
    render_proposition_gold_review,
)


def test_catalog_loads_only_with_exact_parent_bindings(tmp_path: Path) -> None:
    connection_path = tmp_path / "connection.json"
    trigger_path = tmp_path / "trigger.json"
    events = _forty_events()
    connection_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": item.event_id,
                        "phase": item.phase,
                        "source_text_sha256": item.source_text_sha256,
                        "event_meaning": item.event_meaning,
                    }
                    for item in events
                ]
            }
        )
    )
    trigger_path.write_text("{}")
    catalog = PropositionGoldCatalog(
        catalog_id="source-grounded-proposition-gold-v1",
        review_status=PropositionGoldReviewStatus.APPROVED,
        connection_gold_path=connection_path.name,
        connection_gold_sha256=_sha256(connection_path.read_bytes()),
        trigger_gold_path=trigger_path.name,
        trigger_gold_sha256=_sha256(trigger_path.read_bytes()),
        events=events,
    )
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(catalog.model_dump_json())

    loaded = load_proposition_gold_catalog(catalog_path, repository_root=tmp_path)

    assert loaded == catalog
    connection_path.write_text('{"events": []}')
    with pytest.raises(ValueError, match="digest drifted"):
        load_proposition_gold_catalog(catalog_path, repository_root=tmp_path)


def test_preflight_reports_the_exact_uncovered_gold_fragment() -> None:
    gold = _gold_event(
        "TGE-001",
        "development",
        "Sacks stated that Anthropic was running a strategy.",
        fragments=(
            (0, 12, (PropositionGoldFragmentRequirement.ATTRIBUTION,)),
            (18, 50, (PropositionGoldFragmentRequirement.CORE_EVENT,)),
        ),
    )
    candidate = _candidate(gold, 18, 50, PropositionFragmentReason.EVENT_EXPRESSION)

    preflight = evaluate_proposition_candidate_preflight(gold, (candidate,))

    assert preflight.passed is False
    assert preflight.covered_fragment_ids == ("PGF-TGE-001-02",)
    assert preflight.missing_fragment_ids == ("PGF-TGE-001-01",)


def test_case_evaluation_preserves_attribution_and_expected_entity_occurrence() -> None:
    source = "Sacks stated that Anthropic was running a strategy."
    gold = _gold_event(
        "TGE-001",
        "development",
        source,
        fragments=(
            (0, 12, (PropositionGoldFragmentRequirement.ATTRIBUTION,)),
            (18, 50, (PropositionGoldFragmentRequirement.CORE_EVENT,)),
        ),
    )
    scope = _scope(gold, ((0, 12), (18, 50)))
    entity = ConnectionGoldEntity(
        entity_id="EGE-001",
        entity_kind=EventEntityKind.ORGANIZATION,
        canonical_name="Anthropic",
        accepted_entity_names=("Anthropic",),
        accepted_source_occurrences=(
            ConnectionGoldSourceOccurrence(start=18, end=27, source_text="Anthropic"),
        ),
        rationale="Anthropic is the attributed organization.",
    )

    evaluation = evaluate_proposition_scope_case(
        gold=gold,
        scope=scope,
        expected_entities=(entity,),
    )

    assert evaluation.passed is True
    assert evaluation.retained_qualification_fragment_count == 1
    assert evaluation.retained_entity_count == 1
    assert evaluation.false_positive_character_count == 0
    assert evaluation.false_negative_character_count == 0


def test_review_renders_exact_source_and_fragment_text() -> None:
    catalog = PropositionGoldCatalog(
        catalog_id="source-grounded-proposition-gold-v1",
        review_status=PropositionGoldReviewStatus.PROPOSED,
        connection_gold_path="docs/connection.json",
        connection_gold_sha256="1" * 64,
        trigger_gold_path="docs/trigger.json",
        trigger_gold_sha256="2" * 64,
        events=_forty_events(),
    )

    rendered = render_proposition_gold_review(catalog)

    assert "Review status: `proposed`" in rendered
    assert "## TGE-001 — development" in rendered
    assert "`stated` — core_event — `PGF-TGE-001-01`" in rendered


def _forty_events() -> tuple[PropositionGoldEvent, ...]:
    return tuple(
        _gold_event(
            f"TGE-{ordinal:03d}",
            "development" if ordinal <= 20 else "validation",
            f"Actor stated claim {ordinal}.",
            fragments=(
                (
                    len("Actor "),
                    len("Actor stated"),
                    (PropositionGoldFragmentRequirement.CORE_EVENT,),
                ),
            ),
        )
        for ordinal in range(1, 41)
    )


def _gold_event(
    event_id: str,
    phase: Literal["development", "validation"],
    source: str,
    *,
    fragments: tuple[tuple[int, int, tuple[PropositionGoldFragmentRequirement, ...]], ...],
) -> PropositionGoldEvent:
    return PropositionGoldEvent(
        event_id=event_id,
        phase=phase,
        source_text_sha256=_sha256(source.encode()),
        source_text=source,
        event_meaning=f"Reviewed meaning for {event_id}.",
        fragments=tuple(
            PropositionGoldFragment(
                fragment_id=f"PGF-{event_id}-{ordinal:02d}",
                start=start,
                end=end,
                text=source[start:end],
                requirements=tuple(sorted(requirements, key=lambda item: item.value)),
            )
            for ordinal, (start, end, requirements) in enumerate(fragments, start=1)
        ),
        review_rationale="Reviewed exact source meaning.",
    )


def _candidate(
    gold: PropositionGoldEvent,
    start: int,
    end: int,
    reason: PropositionFragmentReason,
) -> PropositionFragmentCandidate:
    reasons = (reason,)
    token_ids = ("t1",)
    record_ids = ("record_fixture",)
    candidate_id = proposition_fragment_candidate_id(
        source_grounded_event_id="sge_" + "1" * 24,
        event_trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=gold.source_text_sha256,
        start=start,
        end=end,
        text=gold.source_text[start:end],
        reasons=reasons,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    return PropositionFragmentCandidate(
        id=candidate_id,
        source_grounded_event_id="sge_" + "1" * 24,
        event_trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=gold.source_text_sha256,
        start=start,
        end=end,
        text=gold.source_text[start:end],
        reasons=reasons,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )


def _scope(
    gold: PropositionGoldEvent,
    ranges: tuple[tuple[int, int], ...],
) -> SourceGroundedPropositionScope:
    candidate_ids = tuple(f"pfc_{ordinal:024x}" for ordinal in range(1, len(ranges) + 1))
    decision_ids = tuple(f"pfd_{ordinal:024x}" for ordinal in range(1, len(ranges) + 1))
    fragments = tuple(
        SourceGroundedPropositionFragment(
            id=source_grounded_proposition_fragment_id(
                source_segment_id="seg_fixture",
                source_text_sha256=gold.source_text_sha256,
                start=start,
                end=end,
                text=gold.source_text[start:end],
                contributing_candidate_ids=(candidate_ids[index],),
            ),
            source_segment_id="seg_fixture",
            source_text_sha256=gold.source_text_sha256,
            start=start,
            end=end,
            text=gold.source_text[start:end],
            contributing_candidate_ids=(candidate_ids[index],),
        )
        for index, (start, end) in enumerate(ranges)
    )
    scope_id = source_grounded_proposition_scope_id(
        source_grounded_event_id="sge_" + "1" * 24,
        event_trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=gold.source_text_sha256,
        candidate_ids=candidate_ids,
        decision_ids=decision_ids,
        fragment_ids=tuple(item.id for item in fragments),
        unresolved_candidate_ids=(),
        status=PropositionScopeStatus.COMPLETE,
    )
    return SourceGroundedPropositionScope(
        id=scope_id,
        source_grounded_event_id="sge_" + "1" * 24,
        event_trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=gold.source_text_sha256,
        candidate_ids=candidate_ids,
        decision_ids=decision_ids,
        fragments=fragments,
        unresolved_candidate_ids=(),
        status=PropositionScopeStatus.COMPLETE,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
