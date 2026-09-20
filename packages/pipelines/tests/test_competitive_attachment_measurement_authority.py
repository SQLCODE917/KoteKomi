from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentCalibrationDiagnosticOutcome,
    AttachmentComparisonRange,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentMeasurementOutcome,
    AttachmentMeasurementRuleAnswer,
    AttachmentNormalizationChange,
    AttachmentNormalizationOperation,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    CompetitiveAttachmentGoldDecision,
    PropositionFragmentReason,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)
from kotekomi_pipelines.competitive_attachment_measurement_authority import (
    audit_r1_strict_phase,
    authoritative_attachment_gold_sets,
    build_attachment_measurement_audit,
    build_attachment_measurement_controls,
    render_attachment_measurement_handoff,
)


def test_authoritative_gold_applies_only_the_reviewed_occurrence_change() -> None:
    candidate_id = "cac_" + "1" * 24
    event_id = "sge_" + "2" * 24
    source = ", alpha"
    digest = hashlib.sha256(source.encode()).hexdigest()
    comparison = AttachmentComparisonRange(
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id=candidate_id,
        authoritative_range=AttachmentSourceRange(start=0, end=7, text=source),
        comparison_start=2,
        comparison_end=7,
        comparison_text="alpha",
        operations=(AttachmentNormalizationOperation.LEADING_DELIMITER,),
        gap_code=None,
    )
    change = AttachmentNormalizationChange(
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        source_text=source,
        candidate_id=candidate_id,
        comparison=comparison,
        original_gold_event_ids=(),
        normalized_gold_event_ids=(event_id,),
    )

    result = authoritative_attachment_gold_sets(
        phase="development",
        original_decisions=(
            CompetitiveAttachmentGoldDecision(
                candidate_id=candidate_id,
                source_grounded_event_ids=(),
            ),
        ),
        normalization_changes=(change,),
        expected_candidate_count=1,
    )

    assert result == {candidate_id: (event_id,)}


def test_authoritative_gold_rejects_changed_original_decision() -> None:
    candidate_id = "cac_" + "1" * 24
    event_id = "sge_" + "2" * 24
    source = ", alpha"
    digest = hashlib.sha256(source.encode()).hexdigest()
    change = AttachmentNormalizationChange(
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        source_text=source,
        candidate_id=candidate_id,
        comparison=AttachmentComparisonRange(
            phase="development",
            source_segment_id="seg_fixture",
            source_text_sha256=digest,
            candidate_id=candidate_id,
            authoritative_range=AttachmentSourceRange(start=0, end=7, text=source),
            comparison_start=2,
            comparison_end=7,
            comparison_text="alpha",
            operations=(AttachmentNormalizationOperation.LEADING_DELIMITER,),
            gap_code=None,
        ),
        original_gold_event_ids=(),
        normalized_gold_event_ids=(event_id,),
    )

    with pytest.raises(ValueError, match="original decision drifted"):
        authoritative_attachment_gold_sets(
            phase="development",
            original_decisions=(
                CompetitiveAttachmentGoldDecision(
                    candidate_id=candidate_id,
                    source_grounded_event_ids=(event_id,),
                ),
            ),
            normalization_changes=(change,),
            expected_candidate_count=1,
        )


def test_r1_strict_audit_exposes_a_gold_positive_loss() -> None:
    source, edge, task = _contained_task()

    report = audit_r1_strict_phase(
        phase="development",
        edges=(edge,),
        tasks=(task,),
        gold_sets={edge.candidate_id: (edge.source_grounded_event_id,)},
    )

    assert report.pool_edge_count == 1
    assert report.rule_firing_count == 1
    assert report.gold_negative_removal_count == 0
    assert report.gold_positive_loss_count == 1
    assert report.decisions[0].source_text == source
    assert report.decisions[0].rule_answer is AttachmentMeasurementRuleAnswer.REJECT


def test_frozen_r1_counts_and_handoff_preserve_all_twelve_positive_losses() -> None:
    development_edges, development_tasks, development_gold = _frozen_phase(
        phase="development",
        edge_count=490,
        firing_count=22,
        positive_firing_count=7,
    )
    validation_edges, validation_tasks, validation_gold = _frozen_phase(
        phase="validation",
        edge_count=257,
        firing_count=9,
        positive_firing_count=5,
    )
    development = audit_r1_strict_phase(
        phase="development",
        edges=development_edges,
        tasks=development_tasks,
        gold_sets=development_gold,
    )
    validation = audit_r1_strict_phase(
        phase="validation",
        edges=validation_edges,
        tasks=validation_tasks,
        gold_sets=validation_gold,
    )
    report = build_attachment_measurement_audit(
        inputs=_audit_inputs(),
        v8_outcome=AttachmentCalibrationDiagnosticOutcome.NOT_SEPARABLE,
        v9_outcome=AttachmentCalibrationDiagnosticOutcome.NOT_SEPARABLE,
        development=development,
        validation=validation,
    )
    controls = build_attachment_measurement_controls(
        predecessor_catalog=AttachmentEvidenceReference(
            label="predecessor_catalog",
            path="diagnostic-catalog.json",
            sha256="a" * 64,
        ),
        development=development,
    )
    handoff = render_attachment_measurement_handoff(report, controls)

    assert report.outcome is AttachmentMeasurementOutcome.UNSAFE
    assert (
        report.combined_rule_firing_count,
        report.combined_gold_negative_removal_count,
        report.combined_gold_positive_loss_count,
    ) == (31, 19, 12)
    assert handoff.count("Attachment Gold: `Y`") == 12
    assert "Authoritative Gold: `proposition_gold.json`" in handoff
    assert any(
        "Palantir and Amazon Web Services" in item.decision.edge.candidate_range.text
        for item in controls.controls
    )


def _contained_task():  # type: ignore[no-untyped-def]
    source = "Acme announced acquisition."
    digest = hashlib.sha256(source.encode()).hexdigest()
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=5,
        end=26,
        text="announced acquisition",
        reasons=(PropositionFragmentReason.PREDICATE_DEPENDENT,),
        parent_candidate_ids=("pfc_" + "1" * 24,),
        linguistic_token_ids=("t1", "t2"),
        source_record_ids=("record_fixture",),
    )
    candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=5,
        end=26,
        text="announced acquisition",
        reasons=(PropositionFragmentReason.PREDICATE_DEPENDENT,),
        parent_candidate_ids=("pfc_" + "1" * 24,),
        linguistic_token_ids=("t1", "t2"),
        source_record_ids=("record_fixture",),
    )
    event_id = "sge_" + "2" * 24
    event_option_id = competitive_attachment_event_option_id(
        source_grounded_event_id=event_id,
        event_trigger_id="etd_" + "3" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=15,
        end=26,
        text="acquisition",
    )
    option = CompetitiveAttachmentEventOption(
        id=event_option_id,
        label="E1",
        source_grounded_event_id=event_id,
        event_trigger_id="etd_" + "3" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=15,
        end=26,
        text="acquisition",
    )
    identity = {
        "phase": "development",
        "source_segment_id": "seg_fixture",
        "source_text_sha256": digest,
        "candidate_id": candidate_id,
        "source_grounded_event_id": event_id,
        "candidate_start": 5,
        "candidate_end": 26,
        "event_start": 15,
        "event_end": 26,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**identity),
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id=candidate_id,
        source_grounded_event_id=event_id,
        candidate_range=AttachmentSourceRange(
            start=5,
            end=26,
            text="announced acquisition",
        ),
        event_range=AttachmentSourceRange(start=15, end=26, text="acquisition"),
        origins=(AttachmentProposalOrigin.QWEN,),
        syntax_arms=(),
    )
    return (
        source,
        edge,
        build_attachment_edge_filter_task(
            source_text=source,
            edge=edge,
            candidate=candidate,
            event_options=(option,),
        ),
    )


def _frozen_phase(
    *,
    phase: Literal["development", "validation"],
    edge_count: int,
    firing_count: int,
    positive_firing_count: int,
) -> tuple[
    tuple[AttachmentPoolEdge, ...],
    tuple[AttachmentEdgeFilterTask, ...],
    dict[str, tuple[str, ...]],
]:
    edges: list[AttachmentPoolEdge] = []
    tasks: list[AttachmentEdgeFilterTask] = []
    gold: dict[str, tuple[str, ...]] = {}
    for ordinal in range(edge_count):
        source = (
            "Palantir and Amazon Web Services offered services"
            if phase == "development" and ordinal == positive_firing_count
            else f"Candidate {phase} {ordinal} event"
        )
        digest = hashlib.sha256(source.encode()).hexdigest()
        event_start = source.rindex("offered") if "offered" in source else source.rindex("event")
        event_text = "offered" if "offered" in source else "event"
        contains = ordinal < firing_count
        candidate_start = 0
        candidate_end = len(source) if contains else len("Candidate")
        candidate_text = source[candidate_start:candidate_end]
        suffix = hashlib.sha256(f"{phase}:{ordinal}".encode()).hexdigest()[:24]
        candidate_id = competitive_attachment_candidate_id(
            source_segment_id=f"seg_{suffix}",
            source_text_sha256=digest,
            start=candidate_start,
            end=candidate_end,
            text=candidate_text,
            reasons=(PropositionFragmentReason.PREDICATE_DEPENDENT,),
            parent_candidate_ids=(f"pfc_{suffix}",),
            linguistic_token_ids=(f"t{ordinal + 1}",),
            source_record_ids=(f"record-{ordinal}",),
        )
        candidate = CompetitiveAttachmentCandidate(
            id=candidate_id,
            source_segment_id=f"seg_{suffix}",
            source_text_sha256=digest,
            start=candidate_start,
            end=candidate_end,
            text=candidate_text,
            reasons=(PropositionFragmentReason.PREDICATE_DEPENDENT,),
            parent_candidate_ids=(f"pfc_{suffix}",),
            linguistic_token_ids=(f"t{ordinal + 1}",),
            source_record_ids=(f"record-{ordinal}",),
        )
        event_id = f"sge_{suffix}"
        trigger_id = f"etd_{suffix}"
        option_id = competitive_attachment_event_option_id(
            source_grounded_event_id=event_id,
            event_trigger_id=trigger_id,
            source_segment_id=f"seg_{suffix}",
            source_text_sha256=digest,
            start=event_start,
            end=event_start + len(event_text),
            text=event_text,
        )
        option = CompetitiveAttachmentEventOption(
            id=option_id,
            label="E1",
            source_grounded_event_id=event_id,
            event_trigger_id=trigger_id,
            source_segment_id=f"seg_{suffix}",
            source_text_sha256=digest,
            start=event_start,
            end=event_start + len(event_text),
            text=event_text,
        )
        edge = AttachmentPoolEdge(
            id=attachment_pool_edge_id(
                phase=phase,
                source_segment_id=f"seg_{suffix}",
                source_text_sha256=digest,
                candidate_id=candidate_id,
                source_grounded_event_id=event_id,
                candidate_start=candidate_start,
                candidate_end=candidate_end,
                event_start=event_start,
                event_end=event_start + len(event_text),
            ),
            phase=phase,
            source_segment_id=f"seg_{suffix}",
            source_text_sha256=digest,
            candidate_id=candidate_id,
            source_grounded_event_id=event_id,
            candidate_range=AttachmentSourceRange(
                start=candidate_start,
                end=candidate_end,
                text=candidate_text,
            ),
            event_range=AttachmentSourceRange(
                start=event_start,
                end=event_start + len(event_text),
                text=event_text,
            ),
            origins=(AttachmentProposalOrigin.QWEN,),
            syntax_arms=(),
        )
        edges.append(edge)
        tasks.append(
            build_attachment_edge_filter_task(
                source_text=source,
                edge=edge,
                candidate=candidate,
                event_options=(option,),
            )
        )
        expected_positive = ordinal < positive_firing_count or ordinal >= firing_count
        gold[candidate_id] = (event_id,) if expected_positive else ()
    return tuple(edges), tuple(tasks), gold


def _audit_inputs() -> tuple[AttachmentEvidenceReference, ...]:
    labels = (
        "calibration_diagnostic_catalog",
        "calibration_run",
        "calibration_v8_report",
        "calibration_v9_report",
        "development_oracle",
        "development_pool",
        "development_tasks",
        "proposition_gold",
        "selection_report",
        "validation_oracle",
        "validation_pool",
        "validation_tasks",
    )
    return tuple(
        AttachmentEvidenceReference(
            label=label,
            path=f"{label}.json",
            sha256="a" * 64,
        )
        for label in labels
    )
