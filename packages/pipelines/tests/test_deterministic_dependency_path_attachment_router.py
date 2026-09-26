from __future__ import annotations

import hashlib
from typing import Literal

from kotekomi_application import (
    AttachmentOracleCeilingKind,
    AttachmentRouteKind,
    AttachmentSourceRange,
    AttachmentSyntaxObservation,
    CompetitiveAttachmentGoldDecision,
    PredicateArgumentGapCode,
    PredicateArgumentHypothesis,
    PredicateArgumentPathDirection,
    PredicateArgumentPathStep,
    PredicateArgumentToken,
    build_attachment_route_report,
)
from kotekomi_pipelines.deterministic_dependency_path_attachment_router import (
    attachment_gold_sets,
    build_attachment_route_ceilings,
    build_attachment_route_phase,
    render_dependency_path_attachment_route_review,
)

EVENT_A = "sge_" + "a" * 24
EVENT_B = "sge_" + "b" * 24
CANDIDATE_1 = "cac_" + "c" * 24
CANDIDATE_2 = "cac_" + "d" * 24
CANDIDATE_3 = "cac_" + "e" * 24


def _token(
    token_id: str,
    text: str,
    start: int,
    end: int,
    relation: str,
    head: str | None,
) -> PredicateArgumentToken:
    return PredicateArgumentToken(
        token_id=token_id,
        sentence_id="s1",
        text=text,
        start=start,
        end=end,
        lemma=text,
        part_of_speech="VERB" if relation == "root" else "NOUN",
        dependency_relation=relation,
        head_token_id=head,
    )


def _range(start: int, end: int, text: str) -> AttachmentSourceRange:
    return AttachmentSourceRange(start=start, end=end, text=text)


def _observation(
    *,
    candidate_id: str,
    event_id: str,
    hypothesis: PredicateArgumentHypothesis,
    structurally_supported: bool,
    steps: tuple[tuple[PredicateArgumentPathDirection, str], ...] = (),
    phase: Literal["development", "validation"] = "development",
) -> AttachmentSyntaxObservation:
    digest = hashlib.sha256(b"Anthropic criticized Stargate.").hexdigest()
    candidate_range = _range(11, 19, "Stargate")
    event_range = _range(0, 10, "criticized")
    if hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP:
        return AttachmentSyntaxObservation(
            phase=phase,
            source_segment_id="seg_fixture",
            source_text_sha256=digest,
            linguistic_trace_id="xst_" + "1" * 24,
            linguistic_resource_identity="2" * 64,
            candidate_id=candidate_id,
            source_grounded_event_id=event_id,
            candidate_range=candidate_range,
            event_range=event_range,
            event_head_range=event_range,
            event_anchor=None,
            candidate_anchor=None,
            path_tokens=(),
            path_steps=(),
            hypothesis=hypothesis,
            gap_code=PredicateArgumentGapCode.PREDICATE_ANCHOR_MISSING,
            own_event_expression=False,
            structurally_supported=False,
        )
    event = _token("t1", "criticized", 0, 10, "root", None)
    tokens = [event]
    path_steps: list[PredicateArgumentPathStep] = []
    previous_id = "t1"
    for index, (direction, relation) in enumerate(steps, start=2):
        token_id = f"t{index}"
        tokens.append(_token(token_id, "target", index * 5, index * 5 + 6, relation, previous_id))
        path_steps.append(
            PredicateArgumentPathStep(
                from_token_id=previous_id,
                to_token_id=token_id,
                dependency_relation=relation,
                direction=direction,
            )
        )
        previous_id = token_id
    return AttachmentSyntaxObservation(
        phase=phase,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        linguistic_trace_id="xst_" + "1" * 24,
        linguistic_resource_identity="2" * 64,
        candidate_id=candidate_id,
        source_grounded_event_id=event_id,
        candidate_range=candidate_range,
        event_range=event_range,
        event_head_range=event_range,
        event_anchor=event,
        candidate_anchor=tokens[-1],
        path_tokens=tuple(tokens),
        path_steps=tuple(path_steps),
        hypothesis=hypothesis,
        gap_code=None,
        own_event_expression=False,
        structurally_supported=structurally_supported,
    )


def _gap(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
        structurally_supported=False,
    )


def _distance_one(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.DIRECT_ARGUMENT,
        structurally_supported=True,
        steps=((PredicateArgumentPathDirection.TOWARD_DEPENDENT, "obj"),),
    )


def _validation_distance_one(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.DIRECT_ARGUMENT,
        structurally_supported=True,
        steps=((PredicateArgumentPathDirection.TOWARD_DEPENDENT, "obj"),),
        phase="validation",
    )


def _far(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.INHERITED_ARGUMENT,
        structurally_supported=True,
        steps=(
            (PredicateArgumentPathDirection.TOWARD_DEPENDENT, "nmod"),
            (PredicateArgumentPathDirection.TOWARD_DEPENDENT, "acl"),
        ),
    )


def test_attachment_gold_sets_flattens_and_sorts() -> None:
    oracle = {
        "cam_1": (
            CompetitiveAttachmentGoldDecision(
                candidate_id=CANDIDATE_1,
                source_grounded_event_ids=(EVENT_A, EVENT_B),
            ),
        ),
    }

    assert attachment_gold_sets(oracle) == {CANDIDATE_1: (EVENT_A, EVENT_B)}


def test_attachment_gold_sets_rejects_duplicate_candidate() -> None:
    oracle = {
        "cam_1": (
            CompetitiveAttachmentGoldDecision(
                candidate_id=CANDIDATE_1,
                source_grounded_event_ids=(EVENT_A,),
            ),
        ),
        "cam_2": (
            CompetitiveAttachmentGoldDecision(
                candidate_id=CANDIDATE_1,
                source_grounded_event_ids=(EVENT_B,),
            ),
        ),
    }

    try:
        attachment_gold_sets(oracle)
    except ValueError as error:
        assert "repeats a candidate" in str(error)
    else:
        raise AssertionError("attachment_gold_sets must reject duplicate candidates.")


def test_build_attachment_route_ceilings_counts() -> None:
    observations = (
        _distance_one(CANDIDATE_1, EVENT_A),
        _distance_one(CANDIDATE_2, EVENT_A),
        _far(CANDIDATE_2, EVENT_B),
        _gap(CANDIDATE_3, EVENT_A),
    )
    gold_attachment = {
        CANDIDATE_1: (EVENT_A,),
        CANDIDATE_2: (EVENT_A, EVENT_B),
        CANDIDATE_3: (),
    }

    ceilings = build_attachment_route_ceilings(
        partition_role="development",
        observations=observations,
        gold_attachment=gold_attachment,
    )

    by_key = {(item.kind, item.policy_id): item for item in ceilings}
    candidate_path_3 = by_key[
        (AttachmentOracleCeilingKind.CANDIDATE_SOURCE, "path_3")
    ]
    assert candidate_path_3.reachable_count == 2
    assert candidate_path_3.gold_count == 2
    assert candidate_path_3.ceiling == 1.0
    per_edge_path_1 = by_key[(AttachmentOracleCeilingKind.PER_EDGE, "path_1")]
    assert per_edge_path_1.reachable_count == 2
    assert per_edge_path_1.gold_count == 3
    per_edge_path_2 = by_key[(AttachmentOracleCeilingKind.PER_EDGE, "path_2")]
    assert per_edge_path_2.reachable_count == 3
    assert per_edge_path_2.gold_count == 3
    assert per_edge_path_2.ceiling == 1.0


def test_build_attachment_route_phase_routes_and_accounts() -> None:
    observations = (
        _distance_one(CANDIDATE_1, EVENT_A),
        _gap(CANDIDATE_3, EVENT_A),
    )
    report = build_attachment_route_phase(
        phase="development",
        observations=observations,
        gold_attachment={
            CANDIDATE_1: (EVENT_A,),
            CANDIDATE_3: (),
        },
        gold_mixed={},
        gold_temporal={},
    )

    decisions = {item.candidate_id: item for item in report.decisions}
    assert decisions[CANDIDATE_1].route_kind is AttachmentRouteKind.ATTACHED
    assert decisions[CANDIDATE_3].route_kind is AttachmentRouteKind.NOT_ATTACHED
    assert report.none_confusion_matrix.syntax_empty_gold_none == 1
    assert report.error_census.none_count == 1


def test_render_review_lists_route_decisions_and_ceilings() -> None:
    development = build_attachment_route_phase(
        phase="development",
        observations=(_distance_one(CANDIDATE_1, EVENT_A),),
        gold_attachment={CANDIDATE_1: (EVENT_A,)},
        gold_mixed={},
        gold_temporal={},
    )
    validation = build_attachment_route_phase(
        phase="validation",
        observations=(_validation_distance_one(CANDIDATE_2, EVENT_B),),
        gold_attachment={CANDIDATE_2: (EVENT_B,)},
        gold_mixed={},
        gold_temporal={},
    )
    ceilings = (
        build_attachment_route_ceilings(
            partition_role="development",
            observations=(_distance_one(CANDIDATE_1, EVENT_A),),
            gold_attachment={CANDIDATE_1: (EVENT_A,)},
        )
        + build_attachment_route_ceilings(
            partition_role="validation",
            observations=(_validation_distance_one(CANDIDATE_2, EVENT_B),),
            gold_attachment={CANDIDATE_2: (EVENT_B,)},
        )
    )
    report = build_attachment_route_report(
        development=development,
        validation=validation,
        ceilings=ceilings,
    )
    rendered = render_dependency_path_attachment_route_review(report)

    assert "R1 Deterministic Dependency-Path Attachment Router Review" in rendered
    assert CANDIDATE_1 in rendered
    assert "## Ceilings" in rendered
    assert report.result_fingerprint in rendered
