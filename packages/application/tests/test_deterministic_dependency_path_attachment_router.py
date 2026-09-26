from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentErrorClass,
    AttachmentNoneClassification,
    AttachmentNoneDecision,
    AttachmentOracleCeilingKind,
    AttachmentPartitionRole,
    AttachmentRouteKind,
    AttachmentSourceRange,
    AttachmentSyntaxObservation,
    PredicateArgumentGapCode,
    PredicateArgumentHypothesis,
    PredicateArgumentPathDirection,
    PredicateArgumentPathStep,
    PredicateArgumentToken,
    attachment_candidate_is_syntax_empty,
    attachment_complement_event_ids,
    attachment_distance_one_event_ids,
    attachment_route_report_fingerprint,
    build_attachment_route_decision,
    build_attachment_route_report,
    build_error_census,
    build_none_confusion_matrix,
    build_none_decisions,
    build_route_ceiling,
    build_route_partition_report,
    classify_error_class,
    classify_none_decision,
)


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
    own_event_expression: bool = False,
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
                direction=direction,
                dependency_relation=relation,
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
        own_event_expression=own_event_expression,
        structurally_supported=structurally_supported,
    )


def _gap_observation(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
        structurally_supported=False,
    )


def _distance_one_observation(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.DIRECT_ARGUMENT,
        structurally_supported=True,
        steps=((PredicateArgumentPathDirection.TOWARD_DEPENDENT, "obj"),),
    )


def _complement_observation(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.INHERITED_ARGUMENT,
        structurally_supported=True,
        steps=(
            (PredicateArgumentPathDirection.TOWARD_DEPENDENT, "ccomp"),
            (PredicateArgumentPathDirection.TOWARD_DEPENDENT, "obj"),
        ),
    )


def _far_observation(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
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


def _nmod_acl_observation(candidate_id: str, event_id: str) -> AttachmentSyntaxObservation:
    return _observation(
        candidate_id=candidate_id,
        event_id=event_id,
        hypothesis=PredicateArgumentHypothesis.INHERITED_ARGUMENT,
        structurally_supported=True,
        steps=(
            (PredicateArgumentPathDirection.TOWARD_DEPENDENT, "ccomp"),
            (PredicateArgumentPathDirection.TOWARD_HEAD, "acl"),
        ),
    )


@pytest.mark.parametrize(
    ("route", "expected_kind"),
    (
        (AttachmentRouteKind.ATTACHED, "attached"),
        (AttachmentRouteKind.NOT_ATTACHED, "not_attached"),
        (AttachmentRouteKind.MODEL_REVIEW, "model_review"),
    ),
)
def test_route_kind_values(route: AttachmentRouteKind, expected_kind: str) -> None:
    assert route.value == expected_kind


def test_syntax_empty_candidate_routes_not_attached() -> None:
    candidate_id = "cac_" + "a" * 24
    decision = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_gap_observation(candidate_id, "sge_" + "b" * 24),),
    )
    assert decision.route_kind is AttachmentRouteKind.NOT_ATTACHED
    assert decision.allowed_event_ids == ()
    assert decision.selected_policy is None


def test_distance_one_candidate_routes_attached_under_path_1() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    decision = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_distance_one_observation(candidate_id, event_id),),
    )
    assert decision.route_kind is AttachmentRouteKind.ATTACHED
    assert decision.allowed_event_ids == (event_id,)
    assert decision.selected_policy == "path_1"
    assert decision.path_1_supported is True


def test_governed_complement_routes_attached_under_complement_policy() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    decision = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_complement_observation(candidate_id, event_id),),
    )
    assert decision.route_kind is AttachmentRouteKind.ATTACHED
    assert decision.allowed_event_ids == (event_id,)
    assert decision.selected_policy == "path_unbounded_plus_complement"


def test_remaining_candidate_routes_model_review() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    decision = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_far_observation(candidate_id, event_id),),
    )
    assert decision.route_kind is AttachmentRouteKind.MODEL_REVIEW
    assert decision.allowed_event_ids == ()
    assert decision.selected_policy is None
def test_complement_family_rejects_nmod_mediated_acl() -> None:
    complement = _complement_observation("cac_" + "a" * 24, "sge_" + "b" * 24)
    excluded = _nmod_acl_observation("cac_" + "c" * 24, "sge_" + "d" * 24)
    assert attachment_distance_one_event_ids((complement,)) == ()
    assert attachment_complement_event_ids((complement,)) == ("sge_" + "b" * 24,)
    assert attachment_complement_event_ids((excluded,)) == ()


def test_syntax_empty_detector() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    gap = _gap_observation(candidate_id, event_id)
    direct = _distance_one_observation(candidate_id, event_id)
    assert attachment_candidate_is_syntax_empty((gap,)) is True
    assert attachment_candidate_is_syntax_empty((direct,)) is False


def test_route_decision_rejects_foreign_candidate() -> None:
    with pytest.raises(ValueError):
        build_attachment_route_decision(
            candidate_id="cac_" + "a" * 24,
            partition_role=AttachmentPartitionRole.DEVELOPMENT,
            observations=(_gap_observation("cac_" + "c" * 24, "sge_" + "b" * 24),),
        )


def test_route_decision_rejects_held_out_partition() -> None:
    with pytest.raises(ValueError):
        build_attachment_route_decision(
            candidate_id="cac_" + "a" * 24,
            partition_role=AttachmentPartitionRole.HELD_OUT,
            observations=(_gap_observation("cac_" + "a" * 24, "sge_" + "b" * 24),),
        )


def test_classify_none_decision() -> None:
    assert classify_none_decision(()) is AttachmentNoneClassification.TRUE_NONE
    assert (
        classify_none_decision(("sge_" + "b" * 24,)) is AttachmentNoneClassification.FALSE_NONE
    )


def test_build_none_confusion_matrix() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    none = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_gap_observation(candidate_id, event_id),),
    )
    matrix = build_none_confusion_matrix(
        partition_role="development",
        decisions=(none,),
        gold_attachment={candidate_id: ()},
    )
    assert matrix.syntax_empty_gold_none == 1
    assert matrix.syntax_empty_gold_attached == 0
    assert matrix.false_none_rate == 0.0


def test_build_none_decisions() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    none = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_gap_observation(candidate_id, event_id),),
    )
    none_decisions = build_none_decisions(
        decisions=(none,),
        gold_attachment={candidate_id: ()},
        gold_temporal={},
    )
    assert none_decisions == (
        AttachmentNoneDecision(
            candidate_id=candidate_id,
            none_classification=AttachmentNoneClassification.TRUE_NONE,
            trigger_containment=False,
            gold_temporal=False,
        ),
    )
def test_classify_error_class() -> None:
    assert (
        classify_error_class(gold_is_empty=True, gold_mixed=False, gold_temporal=False)
        is AttachmentErrorClass.NONE
    )
    assert (
        classify_error_class(gold_is_empty=False, gold_mixed=False, gold_temporal=True)
        is AttachmentErrorClass.TEMPORAL
    )
    assert (
        classify_error_class(gold_is_empty=False, gold_mixed=True, gold_temporal=False)
        is AttachmentErrorClass.MIXED
    )
    assert classify_error_class(gold_is_empty=False, gold_mixed=False, gold_temporal=False) is None


def test_build_error_census_flags_mixed_attached_and_false_none_temporal() -> None:
    mixed_id = "cac_" + "a" * 24
    temporal_false_none_id = "cac_" + "b" * 24
    mixed = build_attachment_route_decision(
        candidate_id=mixed_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_distance_one_observation(mixed_id, "sge_" + "c" * 24),),
    )
    false_none = build_attachment_route_decision(
        candidate_id=temporal_false_none_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_gap_observation(temporal_false_none_id, "sge_" + "d" * 24),),
    )
    census = build_error_census(
        partition_role="development",
        decisions=(mixed, false_none),
        gold_attachment={
            mixed_id: ("sge_" + "c" * 24,),
            temporal_false_none_id: ("sge_" + "d" * 24,),
        },
        gold_mixed={mixed_id: True, temporal_false_none_id: False},
        gold_temporal={mixed_id: False, temporal_false_none_id: True},
    )
    assert census.mixed_count == 1
    assert census.temporal_count == 1
    assert census.mixed_attached_candidate_ids == (mixed_id,)
    assert census.false_none_temporal_candidate_ids == (temporal_false_none_id,)


def test_build_route_ceiling_recomputes_value() -> None:
    ceiling = build_route_ceiling(
        partition_role="development",
        kind=AttachmentOracleCeilingKind.CANDIDATE_SOURCE,
        policy_id="path_3",
        reachable_count=6,
        gold_count=8,
    )
    assert ceiling.ceiling == 0.75
    assert ceiling.deployable is False


def test_build_route_partition_report_invariants() -> None:
    candidate_id = "cac_" + "a" * 24
    event_id = "sge_" + "b" * 24
    direct = build_attachment_route_decision(
        candidate_id=candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_distance_one_observation(candidate_id, event_id),),
    )
    report = build_route_partition_report(
        partition_role="development",
        decisions=(direct,),
        gold_attachment={candidate_id: (event_id,)},
        gold_mixed={},
        gold_temporal={},
    )
    assert report.partition_role == "development"
    assert report.decisions == (direct,)
    assert report.exact_set_count == 1
    assert report.exact_set_score == 1.0


def test_build_route_partition_report_orders_decisions() -> None:
    first_id = "cac_" + "a" * 24
    second_id = "cac_" + "b" * 24
    second = build_attachment_route_decision(
        candidate_id=second_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_distance_one_observation(second_id, "sge_" + "c" * 24),),
    )
    first = build_attachment_route_decision(
        candidate_id=first_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        observations=(_distance_one_observation(first_id, "sge_" + "d" * 24),),
    )
    report = build_route_partition_report(
        partition_role="development",
        decisions=(second, first),
        gold_attachment={
            first_id: ("sge_" + "d" * 24,),
            second_id: ("sge_" + "c" * 24,),
        },
        gold_mixed={},
        gold_temporal={},
    )
    assert tuple(item.candidate_id for item in report.decisions) == (first_id, second_id)


def test_build_attachment_route_report_fingerprint() -> None:
    development = build_route_partition_report(
        partition_role="development",
        decisions=(),
        gold_attachment={},
        gold_mixed={},
        gold_temporal={},
    )
    validation = build_route_partition_report(
        partition_role="validation",
        decisions=(),
        gold_attachment={},
        gold_mixed={},
        gold_temporal={},
    )
    report = build_attachment_route_report(
        development=development,
        validation=validation,
        ceilings=(),
    )
    assert report.result_fingerprint == attachment_route_report_fingerprint(report)
    assert report.model_execution_count == 0
    assert report.canonical_write_count == 0
    assert report.partitions[0].partition_role == "development"
    assert report.partitions[1].partition_role == "validation"


def test_attachment_route_report_fingerprint_excludes_result_field() -> None:
    payload: dict[str, object] = {
        "schema_version": "attachment_route_report_v1",
        "result_fingerprint": "0" * 64,
    }
    assert attachment_route_report_fingerprint(payload) == hashlib.sha256(
        b'{"schema_version":"attachment_route_report_v1"}'
    ).hexdigest()