from __future__ import annotations

from kotekomi_application import (
    AttachmentEdgeFilterArmResult,
    AttachmentMetricSnapshot,
    AttachmentPoolArm,
    AttachmentProposalOrigin,
)
from kotekomi_pipelines.competitive_attachment_edge_filter import (
    build_attachment_pool_edges,
    normalized_attachment_gold_sets,
    select_attachment_pool_arm,
)

from packages.pipelines.tests.test_competitive_event_attachment_stage_local import (
    attachment_matrix_fixture,
    phase_report_fixture,
)


def test_pool_construction_uses_qwen_evidence_without_gold() -> None:
    matrix = attachment_matrix_fixture()
    report = phase_report_fixture()
    expected_edges = sum(len(item.competitive_event_ids) for item in report.cases)

    edges = build_attachment_pool_edges(
        phase="development",
        matrices=(matrix,),
        qwen_report=report,
        syntax_observations=(),
        expected_candidate_count=len(matrix.candidates),
        expected_maximum_pool_size=expected_edges,
    )

    assert len(edges) == expected_edges
    assert all(item.origins == (AttachmentProposalOrigin.QWEN,) for item in edges)
    assert all(item.syntax_arms == () for item in edges)


def test_normalized_gold_changes_only_declared_candidate() -> None:
    event_one = "sge_" + "1" * 24
    event_two = "sge_" + "2" * 24

    result = normalized_attachment_gold_sets(
        original_gold={"c1": (event_one,), "c2": (event_two,)},
        normalization_changes={"c1": ()},
    )

    assert result == {"c1": (), "c2": (event_two,)}


def test_arm_selection_uses_exact_f1_leakage_then_narrower_pool() -> None:
    arms = (
        _arm(AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT, exact=0.7, f1=0.8, leakage=5, edges=20),
        _arm(AttachmentPoolArm.PATH_3_PLUS_COMPLEMENT, exact=0.7, f1=0.9, leakage=7, edges=30),
        _arm(
            AttachmentPoolArm.PATH_UNBOUNDED_PLUS_COMPLEMENT,
            exact=0.7,
            f1=0.9,
            leakage=7,
            edges=40,
        ),
    )

    assert select_attachment_pool_arm(arms) is AttachmentPoolArm.PATH_3_PLUS_COMPLEMENT


def _arm(
    arm: AttachmentPoolArm,
    *,
    exact: float,
    f1: float,
    leakage: int,
    edges: int,
) -> AttachmentEdgeFilterArmResult:
    metrics = _metrics(exact=exact, f1=f1, leakage=leakage)
    return AttachmentEdgeFilterArmResult(
        phase="development",
        arm=arm,
        raw_pool_metrics=metrics,
        filtered_metrics=metrics,
        edge_count=edges,
        retained_edge_count=edges,
        rejected_edge_count=0,
        unresolved_edge_count=0,
        pool_gap_count=0,
    )


def _metrics(*, exact: float, f1: float, leakage: int) -> AttachmentMetricSnapshot:
    return AttachmentMetricSnapshot(
        candidate_count=10,
        event_count=2,
        exact_set_count=int(exact * 10),
        exact_set_accuracy=exact,
        true_positive_edge_count=8,
        false_positive_edge_count=2,
        false_negative_edge_count=2,
        edge_precision=0.8,
        edge_recall=0.8,
        edge_f1=f1,
        sibling_event_leakage_count=leakage,
        shared_gold_edge_count=2,
        shared_matched_edge_count=2,
        shared_fragment_recall=1.0,
        none_case_count=1,
        none_correct_count=1,
        none_accuracy=1.0,
        exact_event_count=1,
        character_precision=0.8,
        character_recall=0.8,
        character_f1=0.8,
        entity_gold_edge_count=2,
        entity_matched_edge_count=2,
        entity_recall=1.0,
        qualification_gold_edge_count=2,
        qualification_matched_edge_count=2,
        qualification_recall=1.0,
        anchor_gap_count=0,
    )
