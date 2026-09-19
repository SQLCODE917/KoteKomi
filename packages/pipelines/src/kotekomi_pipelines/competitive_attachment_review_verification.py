"""Model-free verification of claims about competitive Event attachment."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from typing import Literal

from kotekomi_application import (
    AttachmentCandidateEvaluation,
    AttachmentCatalogConcentration,
    AttachmentEvidenceReference,
    AttachmentMetricSnapshot,
    AttachmentNestedCandidateFlip,
    AttachmentPromptCardinalityObservation,
    AttachmentRangeObservation,
    AttachmentRepeatedOccurrenceResult,
    AttachmentReviewClaimId,
    AttachmentReviewClaimResult,
    AttachmentReviewVerificationReport,
    AttachmentSegmentCount,
    AttachmentSourceRange,
    AttachmentSyntaxObservation,
    AttachmentSyntaxPhaseResult,
    AttachmentTriggerContainmentObservation,
    AttachmentTriggerContainmentSummary,
    AttachmentUnorderedCounterfactual,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    CompetitiveAttachmentFailureAudit,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
    CompetitiveDiscriminationCatalog,
    CompetitiveDiscriminationCategory,
    ReviewClaimVerdict,
    attachment_review_verification_fingerprint,
    build_attachment_syntax_observation,
    classify_attachment_range_relation,
    parse_unordered_attachment_labels,
)

from kotekomi_pipelines.event_entity_connection_stage_local import EventEntityExperimentInput
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragmentRequirement,
)

type _Oracle = dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]
type _Bindings = dict[str, str]
type _ConditionMatrices = tuple[tuple[str, tuple[CompetitiveAttachmentMatrix, ...]], ...]


def build_attachment_review_verification_report(
    *,
    input_references: tuple[AttachmentEvidenceReference, ...],
    development_report: CompetitiveAttachmentPhaseReport,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    development_oracle: _Oracle,
    development_inputs: tuple[EventEntityExperimentInput, ...],
    development_bindings: _Bindings,
    validation_report: CompetitiveAttachmentPhaseReport,
    validation_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    validation_oracle: _Oracle,
    validation_inputs: tuple[EventEntityExperimentInput, ...],
    validation_bindings: _Bindings,
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    gold_catalog: PropositionGoldCatalog,
    failure_audit: CompetitiveAttachmentFailureAudit,
    discrimination_catalog: CompetitiveDiscriminationCatalog,
    condition_matrices: _ConditionMatrices,
    prompt_bytes_by_arm: dict[str, bytes],
) -> AttachmentReviewVerificationReport:
    """Build one complete CEA-1.2 report without executing a model."""
    _validate_inventory(
        development_report=development_report,
        development_matrices=development_matrices,
        development_inputs=development_inputs,
        validation_report=validation_report,
        validation_matrices=validation_matrices,
        validation_inputs=validation_inputs,
        failure_audit=failure_audit,
        discrimination_catalog=discrimination_catalog,
    )
    gold_by_sge = _gold_by_source_grounded_event(
        catalog=gold_catalog,
        development_bindings=development_bindings,
        validation_bindings=validation_bindings,
    )
    development_gold = _gold_sets(development_oracle)
    validation_gold = _gold_sets(validation_oracle)
    source_text_by_digest = {
        item.event.source_text_sha256: item.source_text
        for item in (*development_inputs, *validation_inputs)
    }
    range_observations = _range_observations(
        phase="development",
        matrices=development_matrices,
        gold_by_sge=gold_by_sge,
        source_text_by_digest=source_text_by_digest,
    ) + _range_observations(
        phase="validation",
        matrices=validation_matrices,
        gold_by_sge=gold_by_sge,
        source_text_by_digest=source_text_by_digest,
    )
    flips, nested_pair_count = _segmentation_flips(
        phases=(
            ("development", development_matrices, development_gold),
            ("validation", validation_matrices, validation_gold),
        ),
        source_text_by_digest=source_text_by_digest,
    )
    development = _syntax_phase_result(
        phase="development",
        report=development_report,
        matrices=development_matrices,
        oracle=development_gold,
        inputs=development_inputs,
        gold_by_sge=gold_by_sge,
        source_text_by_digest=source_text_by_digest,
        entity_occurrences_by_event=entity_occurrences_by_event,
    )
    validation = _syntax_phase_result(
        phase="validation",
        report=validation_report,
        matrices=validation_matrices,
        oracle=validation_gold,
        inputs=validation_inputs,
        gold_by_sge=gold_by_sge,
        source_text_by_digest=source_text_by_digest,
        entity_occurrences_by_event=entity_occurrences_by_event,
    )
    challenge_ids_by_category = _catalog_candidate_ids(discrimination_catalog)
    trigger_containment = _trigger_containment_summary(
        phases=(
            ("development", development_matrices, development_gold),
            ("validation", validation_matrices, validation_gold),
        ),
        validation_report=validation_report,
        challenge_none_ids=challenge_ids_by_category[
            CompetitiveDiscriminationCategory.NONE_FALSE_POSITIVE
        ],
        source_text_by_digest=source_text_by_digest,
    )
    syntax_by_candidate = {
        item.candidate_id: item for item in (*development.candidates, *validation.candidates)
    }
    candidate_by_id = {
        candidate.id: candidate
        for matrix in (*development_matrices, *validation_matrices)
        for candidate in matrix.candidates
    }
    repeated_occurrences = tuple(
        AttachmentRepeatedOccurrenceResult(
            candidate_id=candidate_id,
            source_segment_id=candidate_by_id[candidate_id].source_segment_id,
            candidate_range=_candidate_range(candidate_by_id[candidate_id]),
            linguistic_token_ids=tuple(
                sorted(
                    candidate_by_id[candidate_id].linguistic_token_ids,
                    key=_token_ordinal,
                )
            ),
            gold_event_ids=syntax_by_candidate[candidate_id].gold_event_ids,
            syntax_event_ids=syntax_by_candidate[candidate_id].syntax_event_ids,
            exact=syntax_by_candidate[candidate_id].exact,
        )
        for candidate_id in sorted(
            challenge_ids_by_category[CompetitiveDiscriminationCategory.REPEATED_TEXT]
        )
    )
    unordered = _unordered_counterfactuals(
        condition_matrices=condition_matrices,
        gold_by_candidate=development_gold,
    )
    cardinalities = _prompt_cardinalities(prompt_bytes_by_arm)
    concentration = _catalog_concentration(
        catalog=discrimination_catalog,
        development_matrices=development_matrices,
    )
    claims = _claim_results(
        segmentation_flips=flips,
        nested_pair_count=nested_pair_count,
        trigger_containment=trigger_containment,
        development=development,
        validation=validation,
        repeated_occurrences=repeated_occurrences,
        unordered=unordered,
        cardinalities=cardinalities,
        concentration=concentration,
        governing_candidate_ids=challenge_ids_by_category[
            CompetitiveDiscriminationCategory.GOVERNING_CONTEXT
        ],
    )
    ordered_inputs = tuple(sorted(input_references, key=lambda item: item.label))
    ordered_ranges = tuple(
        sorted(
            range_observations,
            key=lambda item: (
                item.phase,
                item.source_text_sha256,
                item.candidate_range.start,
                item.source_grounded_event_id,
            ),
        )
    )
    draft = AttachmentReviewVerificationReport.model_construct(
        inputs=ordered_inputs,
        range_observations=ordered_ranges,
        segmentation_flips=flips,
        trigger_containment=trigger_containment,
        development=development,
        validation=validation,
        repeated_occurrences=repeated_occurrences,
        unordered_counterfactuals=unordered,
        prompt_cardinalities=cardinalities,
        catalog_concentration=concentration,
        claims=claims,
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint="0" * 64,
    )
    return AttachmentReviewVerificationReport(
        inputs=ordered_inputs,
        range_observations=ordered_ranges,
        segmentation_flips=flips,
        trigger_containment=trigger_containment,
        development=development,
        validation=validation,
        repeated_occurrences=repeated_occurrences,
        unordered_counterfactuals=unordered,
        prompt_cardinalities=cardinalities,
        catalog_concentration=concentration,
        claims=claims,
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint=attachment_review_verification_fingerprint(draft),
    )


def attachment_review_verification_summary(
    report: AttachmentReviewVerificationReport,
) -> dict[str, object]:
    """Return the bounded machine-readable summary for one CEA-1.2 report."""
    return {
        "schema_version": "attachment_review_verification_summary_v1",
        "status": "complete",
        "result_fingerprint": report.result_fingerprint,
        "model_execution_count": report.model_execution_count,
        "proposed_change_count": report.proposed_change_count,
        "accepted_ledger_change_count": report.accepted_ledger_change_count,
        "segmentation_flip_count": len(report.segmentation_flips),
        "trigger_containment": report.trigger_containment.model_dump(
            mode="json", exclude={"observations"}
        ),
        "development_syntax_metrics": report.development.syntax_metrics.model_dump(mode="json"),
        "validation_syntax_metrics": report.validation.syntax_metrics.model_dump(mode="json"),
        "validation_qwen_metrics": report.validation.archived_qwen_metrics.model_dump(mode="json"),
        "claims": [item.model_dump(mode="json") for item in report.claims],
    }


def render_attachment_review_verification(
    report: AttachmentReviewVerificationReport,
    *,
    source_text_by_digest: dict[str, str],
) -> str:
    """Render complete inspectable data-in and data-out for repository review."""
    lines = [
        "# CEA-1.2 Review-Claim Verification",
        "",
        f"Result fingerprint: `{report.result_fingerprint}`",
        "",
        "## Claim verdicts",
        "",
    ]
    for claim in report.claims:
        lines.extend(
            (
                f"### {claim.claim_id.value}",
                "",
                f"Statement: {claim.statement}",
                "",
                f"Verdict: `{claim.verdict.value}`",
                "",
                f"Observed: `{claim.observed_count}/{claim.population_count}`",
                "",
                claim.rationale,
                "",
            )
        )
    lines.extend(("## Syntax metrics", ""))
    for phase in (report.development, report.validation):
        lines.extend(
            (
                f"### {phase.phase}",
                "",
                _metric_lines("Syntax", phase.syntax_metrics),
                "",
                _metric_lines("Archived Qwen", phase.archived_qwen_metrics),
                "",
            )
        )
    lines.extend(("## Segmentation Flips", ""))
    for item in report.segmentation_flips:
        lines.extend(
            (
                f"### {item.inner_candidate_id} inside {item.outer_candidate_id}",
                "",
                f"> {item.source_text}",
                "",
                f"Inner: `{item.inner_range.text}` "
                f"`[{item.inner_range.start}, {item.inner_range.end})`",
                "",
                f"Inner Gold: `{', '.join(item.inner_gold_event_ids) or 'NONE'}`",
                "",
                f"Outer: `{item.outer_range.text}` "
                f"`[{item.outer_range.start}, {item.outer_range.end})`",
                "",
                f"Outer Gold: `{', '.join(item.outer_gold_event_ids) or 'NONE'}`",
                "",
            )
        )
    lines.extend(("## Trigger containment", ""))
    trigger = report.trigger_containment
    lines.extend(
        (
            "All Candidates: "
            f"`{trigger.trigger_containing_candidate_count}/{trigger.all_candidate_count}`",
            "",
            "Gold-NONE Candidates: "
            f"`{trigger.trigger_containing_gold_none_count}/{trigger.gold_none_candidate_count}`",
            "",
            f"Validation false-NONE: `{trigger.trigger_containing_validation_false_none_count}/13`",
            "",
            f"CEA-1.1 challenge NONE: `{trigger.trigger_containing_challenge_none_count}/4`",
            "",
        )
    )
    for item in trigger.observations:
        lines.extend(
            (
                f"### {item.candidate_id}",
                "",
                f"> {item.source_text}",
                "",
                f"Candidate: `{item.candidate_range.text}`",
                "",
                f"Contained Events: `{', '.join(item.contained_event_ids)}`",
                "",
                f"Source-exact split: `{' | '.join(part.text for part in item.split_ranges)}`",
                "",
            )
        )
    lines.extend(("## Governing-context paths", ""))
    governing_ids = {
        evidence_id
        for claim in report.claims
        if claim.claim_id is AttachmentReviewClaimId.SYNTAX_RECOVERS_GOVERNING_CASES
        for evidence_id in claim.evidence_ids
    }
    for item in report.development.observations:
        if item.candidate_id not in governing_ids or not item.structurally_supported:
            continue
        source = source_text_by_digest[item.source_text_sha256]
        path = " -> ".join(
            f"{token.token_id}:{token.text}/{token.dependency_relation}"
            for token in item.path_tokens
        )
        lines.extend(
            (
                f"### {item.candidate_id} -> {item.source_grounded_event_id}",
                "",
                f"> {source}",
                "",
                f"Candidate: `{item.candidate_range.text}`",
                "",
                f"Event: `{item.event_range.text}`",
                "",
                f"Hypothesis: `{item.hypothesis.value}`",
                "",
                f"Path: `{path or 'none'}`",
                "",
            )
        )
    lines.extend(("## Repeated occurrences", ""))
    for item in report.repeated_occurrences:
        lines.extend(
            (
                f"### {item.candidate_id}",
                "",
                f"Candidate: `{item.candidate_range.text}` "
                f"`[{item.candidate_range.start}, {item.candidate_range.end})`",
                "",
                f"Tokens: `{', '.join(item.linguistic_token_ids)}`",
                "",
                f"Gold: `{', '.join(item.gold_event_ids) or 'NONE'}`",
                "",
                f"Syntax: `{', '.join(item.syntax_event_ids) or 'NONE'}`",
                "",
            )
        )
    lines.extend(("## Unordered counterfactual", ""))
    for item in report.unordered_counterfactuals:
        raw = base64.b64decode(item.raw_output_base64).decode("utf-8")
        lines.extend(
            (
                f"### {item.condition} / {item.candidate_id}",
                "",
                f"Raw output: `{raw}`",
                "",
                f"Emitted labels: `{', '.join(item.emitted_labels)}`",
                "",
                f"Canonical labels: `{', '.join(item.canonical_labels)}`",
                "",
                f"Gold: `{', '.join(item.gold_event_ids) or 'NONE'}`",
                "",
                f"Counterfactual result: `{', '.join(item.predicted_event_ids) or 'NONE'}`",
                "",
                f"Semantically exact: `{str(item.semantically_exact).lower()}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_second_opinion_summary(
    report: AttachmentReviewVerificationReport,
) -> str:
    """Render a compact self-contained handoff for a future second opinion."""
    lines = [
        "# CEA-1.2 Second-Opinion Handoff",
        "",
        "## Purpose",
        "",
        "This model-free diagnostic tests selected claims from `2nd-opinion-3.md`.",
        "It uses frozen CEA-1 and CEA-1.1 occurrence evidence.",
        "It does not execute Qwen, change Gold, or activate production behavior.",
        "",
        "## Bound inputs",
        "",
    ]
    lines.extend(f"- `{item.label}` `{item.sha256}` — `{item.path}`" for item in report.inputs)
    lines.extend(("", "## Verdicts", ""))
    lines.extend(
        f"- `{item.claim_id.value}`: `{item.verdict.value}` "
        f"(`{item.observed_count}/{item.population_count}`) — {item.rationale}"
        for item in report.claims
    )
    lines.extend(
        (
            "",
            "## Syntax comparison",
            "",
            _metric_lines("Development syntax", report.development.syntax_metrics),
            "",
            _metric_lines("Development archived Qwen", report.development.archived_qwen_metrics),
            "",
            _metric_lines("Validation syntax", report.validation.syntax_metrics),
            "",
            _metric_lines("Validation archived Qwen", report.validation.archived_qwen_metrics),
            "",
            "## Mechanical findings",
            "",
            f"- Segmentation Flips: `{len(report.segmentation_flips)}`.",
            "- Trigger containment among validation false-NONE cases: "
            f"`{report.trigger_containment.trigger_containing_validation_false_none_count}/13`.",
            "- Trigger containment among challenge NONE cases: "
            f"`{report.trigger_containment.trigger_containing_challenge_none_count}/4`.",
            "- Exact repeated-occurrence syntax routes: "
            f"`{sum(item.exact for item in report.repeated_occurrences)}/3`.",
            "- Semantically exact unordered re-parses: "
            f"`{sum(item.semantically_exact for item in report.unordered_counterfactuals)}/3`.",
            "- CEA-1.1 SourceSegment concentration: "
            f"`{report.catalog_concentration.maximum_segment_candidate_count}/24` in one segment.",
            "",
            "## Limits and next decision",
            "",
            "The frozen evidence cannot estimate statistical significance or independent transfer.",
            "It cannot establish a lower true model-error count without new semantic adjudication.",
            "Syntax remains a diagnostic candidate route unless its full validation "
            "metrics match Qwen.",
            "A successor TDD can use the verified mechanism evidence to choose one "
            "bounded correction.",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
            "Complete evidence files: `report.json`, `review.md`, `summary.json`, "
            "and `manifest.json`.",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _validate_inventory(
    *,
    development_report: CompetitiveAttachmentPhaseReport,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    development_inputs: tuple[EventEntityExperimentInput, ...],
    validation_report: CompetitiveAttachmentPhaseReport,
    validation_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    validation_inputs: tuple[EventEntityExperimentInput, ...],
    failure_audit: CompetitiveAttachmentFailureAudit,
    discrimination_catalog: CompetitiveDiscriminationCatalog,
) -> None:
    observed = (
        development_report.phase,
        development_report.metrics.candidate_count,
        len(development_inputs),
        validation_report.phase,
        validation_report.metrics.candidate_count,
        len(validation_inputs),
        failure_audit.error_count,
        len(discrimination_catalog.cases),
    )
    expected = ("development", 162, 20, "validation", 179, 20, 65, 24)
    if observed != expected:
        raise ValueError(f"CEA-1.2 frozen inventory drifted: {observed!r}.")
    if sum(len(item.candidates) for item in development_matrices) != 162:
        raise ValueError("CEA-1.2 development matrix inventory drifted.")
    if sum(len(item.candidates) for item in validation_matrices) != 179:
        raise ValueError("CEA-1.2 validation matrix inventory drifted.")


def _gold_by_source_grounded_event(
    *,
    catalog: PropositionGoldCatalog,
    development_bindings: _Bindings,
    validation_bindings: _Bindings,
) -> dict[str, PropositionGoldEvent]:
    bindings = {**development_bindings, **validation_bindings}
    if set(bindings) != {item.event_id for item in catalog.events}:
        raise ValueError("CEA-1.2 Gold bindings do not cover forty Events.")
    return {bindings[item.event_id]: item for item in catalog.events}


def _gold_sets(oracle: _Oracle) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for decisions in oracle.values():
        for value in decisions:
            result[value.candidate_id] = tuple(sorted(value.source_grounded_event_ids))
    return result


def _range_observations(
    *,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_by_sge: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
) -> tuple[AttachmentRangeObservation, ...]:
    result: list[AttachmentRangeObservation] = []
    for matrix in matrices:
        source = source_text_by_digest[matrix.source_text_sha256]
        for candidate in matrix.candidates:
            for event in matrix.event_options:
                gold = gold_by_sge[event.source_grounded_event_id]
                ranges = tuple((item.start, item.end) for item in gold.fragments)
                result.append(
                    AttachmentRangeObservation(
                        phase=phase,
                        source_segment_id=matrix.source_segment_id,
                        source_text_sha256=matrix.source_text_sha256,
                        candidate_id=candidate.id,
                        source_grounded_event_id=event.source_grounded_event_id,
                        candidate_range=_candidate_range(candidate),
                        gold_ranges=tuple(
                            AttachmentSourceRange(
                                start=item.start,
                                end=item.end,
                                text=item.text,
                            )
                            for item in gold.fragments
                        ),
                        relation=classify_attachment_range_relation(
                            source_text=source,
                            candidate_start=candidate.start,
                            candidate_end=candidate.end,
                            gold_ranges=ranges,
                        ),
                    )
                )
    return tuple(result)


def _segmentation_flips(
    *,
    phases: tuple[
        tuple[
            Literal["development", "validation"],
            tuple[CompetitiveAttachmentMatrix, ...],
            dict[str, tuple[str, ...]],
        ],
        ...,
    ],
    source_text_by_digest: dict[str, str],
) -> tuple[tuple[AttachmentNestedCandidateFlip, ...], int]:
    flips: list[AttachmentNestedCandidateFlip] = []
    nested_pair_count = 0
    for phase, matrices, gold in phases:
        for matrix in matrices:
            source = source_text_by_digest[matrix.source_text_sha256]
            for left, right in combinations(matrix.candidates, 2):
                inner, outer = _nested_pair(left, right)
                if inner is None or outer is None:
                    continue
                nested_pair_count += 1
                if gold[inner.id] == gold[outer.id]:
                    continue
                flips.append(
                    AttachmentNestedCandidateFlip(
                        phase=phase,
                        source_segment_id=matrix.source_segment_id,
                        source_text_sha256=matrix.source_text_sha256,
                        source_text=source,
                        inner_candidate_id=inner.id,
                        inner_range=_candidate_range(inner),
                        inner_gold_event_ids=gold[inner.id],
                        outer_candidate_id=outer.id,
                        outer_range=_candidate_range(outer),
                        outer_gold_event_ids=gold[outer.id],
                    )
                )
    return (
        tuple(
            sorted(
                flips,
                key=lambda item: (
                    item.phase,
                    item.source_text_sha256,
                    item.outer_range.start,
                    item.inner_range.start,
                    item.inner_candidate_id,
                ),
            )
        ),
        nested_pair_count,
    )


def _syntax_phase_result(
    *,
    phase: Literal["development", "validation"],
    report: CompetitiveAttachmentPhaseReport,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[str, ...]],
    inputs: tuple[EventEntityExperimentInput, ...],
    gold_by_sge: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
) -> AttachmentSyntaxPhaseResult:
    input_by_event = {item.event.id: item for item in inputs}
    observations: list[AttachmentSyntaxObservation] = []
    predictions: dict[str, set[str]] = defaultdict(set)
    for matrix in matrices:
        source = source_text_by_digest[matrix.source_text_sha256]
        for candidate in matrix.candidates:
            for option in matrix.event_options:
                prepared = input_by_event[option.source_grounded_event_id]
                observation = build_attachment_syntax_observation(
                    phase=phase,
                    source_text=source,
                    candidate=candidate,
                    event=option,
                    event_head_start=prepared.trigger.head_start,
                    event_head_end=prepared.trigger.head_end,
                    event_head_text=prepared.trigger.head_text,
                    linguistic_evidence=prepared.linguistic_evidence,
                )
                observations.append(observation)
                if observation.structurally_supported:
                    predictions[candidate.id].add(option.source_grounded_event_id)
    syntax_sets = {key: tuple(sorted(value)) for key, value in predictions.items()}
    for candidate_id in oracle:
        syntax_sets.setdefault(candidate_id, ())
    candidate_by_id = {
        candidate.id: candidate for matrix in matrices for candidate in matrix.candidates
    }
    evaluations = tuple(
        sorted(
            (
                AttachmentCandidateEvaluation(
                    phase=phase,
                    source_segment_id=candidate_by_id[candidate_id].source_segment_id,
                    candidate_id=candidate_id,
                    candidate_range=_candidate_range(candidate_by_id[candidate_id]),
                    gold_event_ids=gold,
                    syntax_event_ids=syntax_sets[candidate_id],
                    exact=gold == syntax_sets[candidate_id],
                )
                for candidate_id, gold in oracle.items()
            ),
            key=lambda item: item.candidate_id,
        )
    )
    syntax_metrics = _metric_snapshot(
        matrices=matrices,
        gold_sets=oracle,
        predicted_sets=syntax_sets,
        gold_by_sge=gold_by_sge,
        source_text_by_digest=source_text_by_digest,
        entity_occurrences_by_event=entity_occurrences_by_event,
        anchor_gap_count=sum(item.hypothesis.value == "diagnostic_gap" for item in observations),
    )
    qwen_sets = {item.candidate_id: item.competitive_event_ids for item in report.cases}
    qwen_metrics = _metric_snapshot(
        matrices=matrices,
        gold_sets=oracle,
        predicted_sets=qwen_sets,
        gold_by_sge=gold_by_sge,
        source_text_by_digest=source_text_by_digest,
        entity_occurrences_by_event=entity_occurrences_by_event,
        anchor_gap_count=0,
    )
    _validate_archived_metric_replay(report, qwen_metrics)
    return AttachmentSyntaxPhaseResult(
        phase=phase,
        observations=tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.source_text_sha256,
                    item.candidate_range.start,
                    item.candidate_id,
                    item.event_range.start,
                    item.source_grounded_event_id,
                ),
            )
        ),
        candidates=evaluations,
        syntax_metrics=syntax_metrics,
        archived_qwen_metrics=qwen_metrics,
    )


def _metric_snapshot(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_sets: dict[str, tuple[str, ...]],
    predicted_sets: dict[str, tuple[str, ...]],
    gold_by_sge: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    anchor_gap_count: int,
) -> AttachmentMetricSnapshot:
    candidate_by_id = {
        candidate.id: candidate for matrix in matrices for candidate in matrix.candidates
    }
    tp = fp = fn = leakage = 0
    shared_total = shared_matched = 0
    none_total = none_correct = 0
    entity_total = entity_matched = 0
    qualification_total = qualification_matched = 0
    exact = 0
    for candidate_id, gold_ids in gold_sets.items():
        predicted_ids = predicted_sets[candidate_id]
        gold = set(gold_ids)
        predicted = set(predicted_ids)
        exact += gold == predicted
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        if gold:
            leakage += len(predicted - gold)
        else:
            none_total += 1
            none_correct += not predicted
        if len(gold) > 1:
            shared_total += len(gold)
            shared_matched += len(gold & predicted)
    character_counts = [0, 0, 0]
    exact_events = 0
    phase_event_ids = tuple(
        sorted(
            {
                option.source_grounded_event_id
                for matrix in matrices
                for option in matrix.event_options
            }
        )
    )
    for event_id in phase_event_ids:
        gold_event = gold_by_sge[event_id]
        source = source_text_by_digest[gold_event.source_text_sha256]
        required = _positions(
            source,
            tuple((item.start, item.end) for item in gold_event.fragments),
        )
        selected = _positions(
            source,
            tuple(
                (candidate.start, candidate.end)
                for candidate_id, candidate in candidate_by_id.items()
                if event_id in predicted_sets[candidate_id]
                and candidate.source_text_sha256 == gold_event.source_text_sha256
            ),
        )
        character_counts[0] += len(required & selected)
        character_counts[1] += len(selected - required)
        character_counts[2] += len(required - selected)
        exact_events += selected == required
        qualifications = tuple(
            item
            for item in gold_event.fragments
            if any(
                requirement is not PropositionGoldFragmentRequirement.CORE_EVENT
                for requirement in item.requirements
            )
        )
        qualification_total += len(qualifications)
        qualification_matched += sum(
            _positions(source, ((item.start, item.end),)) <= selected for item in qualifications
        )
        entity_occurrences = entity_occurrences_by_event.get(event_id, ())
        entity_total += len(entity_occurrences)
        entity_matched += sum(
            _positions(source, (occurrence,)) <= selected for occurrence in entity_occurrences
        )
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    char_precision = _ratio(character_counts[0], character_counts[0] + character_counts[1])
    char_recall = _ratio(character_counts[0], character_counts[0] + character_counts[2])
    return AttachmentMetricSnapshot(
        candidate_count=len(gold_sets),
        event_count=len(phase_event_ids),
        exact_set_count=exact,
        exact_set_accuracy=_ratio(exact, len(gold_sets)),
        true_positive_edge_count=tp,
        false_positive_edge_count=fp,
        false_negative_edge_count=fn,
        edge_precision=precision,
        edge_recall=recall,
        edge_f1=_f1(precision, recall),
        sibling_event_leakage_count=leakage,
        shared_gold_edge_count=shared_total,
        shared_matched_edge_count=shared_matched,
        shared_fragment_recall=_ratio(shared_matched, shared_total),
        none_case_count=none_total,
        none_correct_count=none_correct,
        none_accuracy=_ratio(none_correct, none_total),
        exact_event_count=exact_events,
        character_precision=char_precision,
        character_recall=char_recall,
        character_f1=_f1(char_precision, char_recall),
        entity_gold_edge_count=entity_total,
        entity_matched_edge_count=entity_matched,
        entity_recall=_ratio(entity_matched, entity_total),
        qualification_gold_edge_count=qualification_total,
        qualification_matched_edge_count=qualification_matched,
        qualification_recall=_ratio(qualification_matched, qualification_total),
        anchor_gap_count=anchor_gap_count,
    )


def _validate_archived_metric_replay(
    report: CompetitiveAttachmentPhaseReport,
    observed: AttachmentMetricSnapshot,
) -> None:
    expected = report.metrics
    pairs = (
        (observed.exact_set_accuracy, expected.competitive_exact_set_accuracy),
        (observed.edge_precision, expected.edge_precision),
        (observed.edge_recall, expected.edge_recall),
        (observed.edge_f1, expected.edge_f1),
        (observed.none_accuracy, expected.none_accuracy),
        (observed.shared_fragment_recall, expected.shared_fragment_recall),
        (observed.character_precision, expected.competitive_character_precision),
        (observed.character_recall, expected.competitive_character_recall),
        (observed.character_f1, expected.competitive_character_f1),
        (observed.entity_recall, expected.competitive_entity_recall),
        (observed.qualification_recall, expected.competitive_qualification_recall),
    )
    if any(abs(left - right) > 1e-12 for left, right in pairs):
        raise ValueError("CEA-1.2 archived metric replay drifted from the CEA-1 report.")
    if (
        observed.sibling_event_leakage_count != expected.competitive_sibling_event_leakage_count
        or observed.exact_event_count != expected.competitive_exact_event_count
    ):
        raise ValueError("CEA-1.2 archived count replay drifted from the CEA-1 report.")


def _trigger_containment_summary(
    *,
    phases: tuple[
        tuple[
            Literal["development", "validation"],
            tuple[CompetitiveAttachmentMatrix, ...],
            dict[str, tuple[str, ...]],
        ],
        ...,
    ],
    validation_report: CompetitiveAttachmentPhaseReport,
    challenge_none_ids: set[str],
    source_text_by_digest: dict[str, str],
) -> AttachmentTriggerContainmentSummary:
    validation_false_none = {
        item.candidate_id
        for item in validation_report.cases
        if not item.gold_event_ids and item.competitive_event_ids
    }
    if len(validation_false_none) != 13:
        raise ValueError("CEA-1.2 expected thirteen validation false-NONE cases.")
    if len(challenge_none_ids) != 4:
        raise ValueError("CEA-1.2 expected four challenge NONE cases.")
    all_candidates = 0
    gold_none = 0
    observations: list[AttachmentTriggerContainmentObservation] = []
    containing_ids: set[str] = set()
    for phase, matrices, gold_sets in phases:
        for matrix in matrices:
            source = source_text_by_digest[matrix.source_text_sha256]
            all_candidates += len(matrix.candidates)
            for candidate in matrix.candidates:
                if not gold_sets[candidate.id]:
                    gold_none += 1
                contained = tuple(
                    sorted(
                        (
                            option
                            for option in matrix.event_options
                            if candidate.start <= option.start
                            and option.end <= candidate.end
                            and (candidate.start, candidate.end) != (option.start, option.end)
                        ),
                        key=lambda item: (item.start, item.end, item.id),
                    )
                )
                if not contained:
                    continue
                containing_ids.add(candidate.id)
                event_ranges = tuple(
                    AttachmentSourceRange(start=item.start, end=item.end, text=item.text)
                    for item in contained
                )
                observations.append(
                    AttachmentTriggerContainmentObservation(
                        phase=phase,
                        source_segment_id=matrix.source_segment_id,
                        source_text_sha256=matrix.source_text_sha256,
                        source_text=source,
                        candidate_id=candidate.id,
                        candidate_range=_candidate_range(candidate),
                        contained_event_ids=tuple(
                            item.source_grounded_event_id for item in contained
                        ),
                        contained_event_ranges=event_ranges,
                        split_ranges=_split_candidate(source, candidate, contained),
                        gold_event_ids=gold_sets[candidate.id],
                        validation_false_none=candidate.id in validation_false_none,
                        challenge_none=candidate.id in challenge_none_ids,
                    )
                )
    gold_none_ids = {
        candidate_id
        for _, _, gold_sets in phases
        for candidate_id, event_ids in gold_sets.items()
        if not event_ids
    }
    return AttachmentTriggerContainmentSummary(
        all_candidate_count=all_candidates,
        trigger_containing_candidate_count=len(containing_ids),
        gold_none_candidate_count=gold_none,
        trigger_containing_gold_none_count=len(containing_ids & gold_none_ids),
        validation_false_none_count=13,
        trigger_containing_validation_false_none_count=len(containing_ids & validation_false_none),
        challenge_none_count=4,
        trigger_containing_challenge_none_count=len(containing_ids & challenge_none_ids),
        observations=tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.phase,
                    item.source_text_sha256,
                    item.candidate_range.start,
                    item.candidate_id,
                ),
            )
        ),
    )


def _unordered_counterfactuals(
    *,
    condition_matrices: _ConditionMatrices,
    gold_by_candidate: dict[str, tuple[str, ...]],
) -> tuple[AttachmentUnorderedCounterfactual, ...]:
    results: list[AttachmentUnorderedCounterfactual] = []
    for condition, matrices in condition_matrices:
        for matrix in matrices:
            option_by_label = {item.label: item for item in matrix.event_options}
            allowed = tuple(item.label for item in matrix.event_options)
            for decision in matrix.decisions:
                if decision.status.value != "invalid_output":
                    continue
                if decision.raw_output_base64 is None or decision.raw_output_sha256 is None:
                    raise ValueError("CEA-1.2 invalid output lacks archived bytes.")
                raw = base64.b64decode(decision.raw_output_base64, validate=True)
                emitted, canonical = parse_unordered_attachment_labels(
                    raw,
                    allowed_event_labels=allowed,
                )
                predicted = tuple(
                    sorted(option_by_label[label].source_grounded_event_id for label in canonical)
                )
                gold = gold_by_candidate[decision.candidate_id]
                results.append(
                    AttachmentUnorderedCounterfactual(
                        condition=condition,
                        candidate_id=decision.candidate_id,
                        raw_output_base64=decision.raw_output_base64,
                        raw_output_sha256=decision.raw_output_sha256,
                        emitted_labels=emitted,
                        canonical_labels=canonical,
                        predicted_event_ids=predicted,
                        gold_event_ids=gold,
                        semantically_exact=predicted == gold,
                    )
                )
    if len(results) != 3:
        raise ValueError(f"CEA-1.2 expected three invalid outputs, observed {len(results)}.")
    return tuple(sorted(results, key=lambda item: (item.condition, item.candidate_id)))


def _prompt_cardinalities(
    prompt_bytes_by_arm: dict[str, bytes],
) -> tuple[AttachmentPromptCardinalityObservation, ...]:
    results: list[AttachmentPromptCardinalityObservation] = []
    for arm, payload in sorted(prompt_bytes_by_arm.items()):
        text = payload.decode("utf-8")
        answers = tuple(re.findall(r"^Answer: `([^`]+)`$", text, flags=re.MULTILINE))
        cardinalities = tuple(
            0 if answer in {"NONE", "UNCLEAR"} else len(answer.split(",")) for answer in answers
        )
        results.append(
            AttachmentPromptCardinalityObservation(
                prompt_arm=arm,
                prompt_sha256=hashlib.sha256(payload).hexdigest(),
                answer_cardinalities=cardinalities,
                maximum_answer_cardinality=max(cardinalities),
            )
        )
    return tuple(results)


def _catalog_candidate_ids(
    catalog: CompetitiveDiscriminationCatalog,
) -> dict[CompetitiveDiscriminationCategory, set[str]]:
    return {
        category: {item.candidate_id for item in catalog.cases if category in item.categories}
        for category in CompetitiveDiscriminationCategory
    }


def _catalog_concentration(
    *,
    catalog: CompetitiveDiscriminationCatalog,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
) -> AttachmentCatalogConcentration:
    matrix_by_id = {item.id: item for item in development_matrices}
    counts = Counter(matrix_by_id[item.matrix_id].source_segment_id for item in catalog.cases)
    segments = tuple(
        AttachmentSegmentCount(source_segment_id=key, candidate_count=value)
        for key, value in sorted(counts.items())
    )
    return AttachmentCatalogConcentration(
        candidate_count=24,
        source_segment_count=len(segments),
        maximum_segment_candidate_count=max(counts.values()),
        segments=segments,
    )


def _claim_results(
    *,
    segmentation_flips: tuple[AttachmentNestedCandidateFlip, ...],
    nested_pair_count: int,
    trigger_containment: AttachmentTriggerContainmentSummary,
    development: AttachmentSyntaxPhaseResult,
    validation: AttachmentSyntaxPhaseResult,
    repeated_occurrences: tuple[AttachmentRepeatedOccurrenceResult, ...],
    unordered: tuple[AttachmentUnorderedCounterfactual, ...],
    cardinalities: tuple[AttachmentPromptCardinalityObservation, ...],
    concentration: AttachmentCatalogConcentration,
    governing_candidate_ids: set[str],
) -> tuple[AttachmentReviewClaimResult, ...]:
    syntax_by_candidate = {item.candidate_id: item for item in development.candidates}
    governing_exact = sum(syntax_by_candidate[item].exact for item in governing_candidate_ids)
    trigger_count = trigger_containment.trigger_containing_validation_false_none_count
    repeated_exact = sum(item.exact for item in repeated_occurrences)
    unordered_exact = sum(item.semantically_exact for item in unordered)
    cardinality_by_arm = {item.prompt_arm: item for item in cardinalities}
    control_max = cardinality_by_arm["control"].maximum_answer_cardinality
    revised_max = cardinality_by_arm["examples"].maximum_answer_cardinality
    syntax_gates = _syntax_replacement_gates(
        syntax=validation.syntax_metrics,
        qwen=validation.archived_qwen_metrics,
    )
    syntax_gate_count = sum(syntax_gates.values())
    claims = (
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.SEGMENTATION_DEPENDENT_GOLD,
            statement=(
                "The containment oracle can change labels when only Candidate boundaries change."
            ),
            verdict=(
                ReviewClaimVerdict.CONFIRMED if segmentation_flips else ReviewClaimVerdict.FALSIFIED
            ),
            observed_count=len(segmentation_flips),
            population_count=nested_pair_count,
            evidence_ids=tuple(
                sorted(
                    {item.inner_candidate_id for item in segmentation_flips}
                    | {item.outer_candidate_id for item in segmentation_flips}
                )
            ),
            rationale=(
                "At least one strict nested Candidate pair changes its Gold Attachment Set."
                if segmentation_flips
                else "No strict nested Candidate pair changes its Gold Attachment Set."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.TRIGGER_CONTAINMENT_CATCHES_MOST,
            statement="Trigger containment detects most validation Gold-NONE false attachments.",
            verdict=_bounded_majority_verdict(trigger_count, 13),
            observed_count=trigger_count,
            population_count=13,
            evidence_ids=tuple(
                sorted(
                    item.candidate_id
                    for item in trigger_containment.observations
                    if item.validation_false_none
                )
            ),
            rationale=("The verdict uses all thirteen CEA-1 validation false-NONE occurrences."),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.SYNTAX_RECOVERS_GOVERNING_CASES,
            statement="The frozen syntax policy exactly recovers the four governing-context cases.",
            verdict=_bounded_exact_verdict(governing_exact, 4),
            observed_count=governing_exact,
            population_count=4,
            evidence_ids=tuple(sorted(governing_candidate_ids)),
            rationale="Each case is scored by exact occurrence-level Attachment Set.",
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.SYNTAX_CAN_REPLACE_QWEN,
            statement="The frozen syntax policy can replace archived Qwen attachment.",
            verdict=(
                ReviewClaimVerdict.CONFIRMED
                if syntax_gate_count == len(syntax_gates)
                else ReviewClaimVerdict.FALSIFIED
            ),
            observed_count=syntax_gate_count,
            population_count=len(syntax_gates),
            evidence_ids=tuple(sorted(name for name, passed in syntax_gates.items() if passed)),
            rationale=(
                "Syntax must meet or exceed Qwen on every declared validation metric; "
                "passed gates: "
                f"{', '.join(name for name, passed in syntax_gates.items() if passed) or 'none'}."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.REPEATED_OCCURRENCES_ROUTE_DETERMINISTICALLY,
            statement=(
                "Exact token occurrences deterministically route all three repeated-text cases."
            ),
            verdict=_bounded_exact_verdict(repeated_exact, 3),
            observed_count=repeated_exact,
            population_count=3,
            evidence_ids=tuple(sorted(item.candidate_id for item in repeated_occurrences)),
            rationale="The comparison keeps equal strings distinct by range and token ID.",
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.UNORDERED_FAILURES_ARE_FORMAT_ONLY,
            statement="All three archived reversed-label failures are format-only.",
            verdict=_bounded_exact_verdict(unordered_exact, 3),
            observed_count=unordered_exact,
            population_count=3,
            evidence_ids=tuple(
                sorted(f"{item.condition}:{item.candidate_id}" for item in unordered)
            ),
            rationale=(
                "The counterfactual changes parsing only and preserves archived output bytes."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.EXAMPLE_CARDINALITY_CONFOUND,
            statement=(
                "The examples change also lowered the maximum demonstrated answer cardinality."
            ),
            verdict=(
                ReviewClaimVerdict.CONFIRMED
                if revised_max < control_max
                else ReviewClaimVerdict.FALSIFIED
            ),
            observed_count=control_max - revised_max if revised_max < control_max else 0,
            population_count=control_max,
            evidence_ids=("control", "examples"),
            rationale=(
                f"The control maximum is {control_max}; the examples-arm maximum is {revised_max}. "
                "This confirms a confound but does not establish a causal effect."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.STATISTICAL_SIGNIFICANCE,
            statement="The 24-case arm comparison establishes statistical significance.",
            verdict=ReviewClaimVerdict.NOT_TESTABLE,
            observed_count=24,
            population_count=24,
            evidence_ids=tuple(item.source_segment_id for item in concentration.segments),
            rationale=(
                "The deliberately hard catalog has clustered SourceSegments and no registered "
                "inferential test."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.GENERALIZATION,
            statement="The 24-case arm comparison establishes transfer to independent sources.",
            verdict=ReviewClaimVerdict.NOT_TESTABLE,
            observed_count=concentration.source_segment_count,
            population_count=24,
            evidence_ids=tuple(item.source_segment_id for item in concentration.segments),
            rationale=(
                "All cases come from prior development material; the largest segment contributes "
                f"{concentration.maximum_segment_candidate_count} candidates."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.TRUE_MODEL_ERROR_IS_LOWER,
            statement="The true semantic model-error count is below 65 of 179.",
            verdict=ReviewClaimVerdict.NOT_TESTABLE,
            observed_count=65,
            population_count=179,
            evidence_ids=(),
            rationale=(
                "The frozen catalog lacks independent semantic adjudication for all 65 errors."
            ),
        ),
        AttachmentReviewClaimResult(
            claim_id=AttachmentReviewClaimId.SYNTAX_THRESHOLD_IS_VALIDATED,
            statement="An 85 percent syntax-edge threshold is empirically validated.",
            verdict=ReviewClaimVerdict.NOT_TESTABLE,
            observed_count=0,
            population_count=100,
            evidence_ids=(),
            rationale=(
                "The threshold was a proposed decision rule rather than an accepted benchmark."
            ),
        ),
    )
    return tuple(sorted(claims, key=lambda item: item.claim_id.value))


def _syntax_replacement_gates(
    *,
    syntax: AttachmentMetricSnapshot,
    qwen: AttachmentMetricSnapshot,
) -> dict[str, bool]:
    return {
        "character_precision": syntax.character_precision >= qwen.character_precision,
        "character_recall": syntax.character_recall >= qwen.character_recall,
        "edge_precision": syntax.edge_precision >= qwen.edge_precision,
        "edge_recall": syntax.edge_recall >= qwen.edge_recall,
        "entity_recall": syntax.entity_recall >= qwen.entity_recall,
        "exact_event_count": syntax.exact_event_count >= qwen.exact_event_count,
        "exact_set_accuracy": syntax.exact_set_accuracy >= qwen.exact_set_accuracy,
        "none_accuracy": syntax.none_accuracy >= qwen.none_accuracy,
        "qualification_recall": syntax.qualification_recall >= qwen.qualification_recall,
        "shared_fragment_recall": (syntax.shared_fragment_recall >= qwen.shared_fragment_recall),
        "sibling_event_leakage": (
            syntax.sibling_event_leakage_count <= qwen.sibling_event_leakage_count
        ),
    }


def _bounded_majority_verdict(observed: int, population: int) -> ReviewClaimVerdict:
    if observed > population / 2:
        return ReviewClaimVerdict.CONFIRMED
    if observed > 0:
        return ReviewClaimVerdict.PARTLY_CONFIRMED
    return ReviewClaimVerdict.FALSIFIED


def _bounded_exact_verdict(observed: int, population: int) -> ReviewClaimVerdict:
    if observed == population:
        return ReviewClaimVerdict.CONFIRMED
    if observed > 0:
        return ReviewClaimVerdict.PARTLY_CONFIRMED
    return ReviewClaimVerdict.FALSIFIED


def _nested_pair(
    left: CompetitiveAttachmentCandidate,
    right: CompetitiveAttachmentCandidate,
) -> tuple[CompetitiveAttachmentCandidate | None, CompetitiveAttachmentCandidate | None]:
    left_start = left.start
    left_end = left.end
    right_start = right.start
    right_end = right.end
    if (
        left_start <= right_start
        and right_end <= left_end
        and (left_start < right_start or right_end < left_end)
    ):
        return right, left
    if (
        right_start <= left_start
        and left_end <= right_end
        and (right_start < left_start or left_end < right_end)
    ):
        return left, right
    return None, None


def _split_candidate(
    source: str,
    candidate: CompetitiveAttachmentCandidate,
    contained: tuple[CompetitiveAttachmentEventOption, ...],
) -> tuple[AttachmentSourceRange, ...]:
    start = candidate.start
    end = candidate.end
    boundaries = {start, end}
    for event in contained:
        boundaries.add(event.start)
        boundaries.add(event.end)
    ordered = sorted(boundaries)
    return tuple(
        AttachmentSourceRange(start=left, end=right, text=source[left:right])
        for left, right in zip(ordered, ordered[1:], strict=False)
        if left < right and source[left:right].strip()
    )


def _candidate_range(candidate: CompetitiveAttachmentCandidate) -> AttachmentSourceRange:
    return AttachmentSourceRange(
        start=candidate.start,
        end=candidate.end,
        text=candidate.text,
    )


def _token_ordinal(value: str) -> int:
    return int(value[1:])


def _positions(source: str, ranges: tuple[tuple[int, int], ...]) -> set[int]:
    return {
        position
        for start, end in ranges
        for position in range(start, end)
        if not source[position].isspace()
    }


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _metric_lines(label: str, metrics: AttachmentMetricSnapshot) -> str:
    return (
        f"{label}: exact-set `{metrics.exact_set_accuracy:.6f}`, "
        f"edge precision `{metrics.edge_precision:.6f}`, "
        f"edge recall `{metrics.edge_recall:.6f}`, "
        f"NONE `{metrics.none_accuracy:.6f}`, "
        f"leakage `{metrics.sibling_event_leakage_count}`, "
        f"exact Events `{metrics.exact_event_count}/{metrics.event_count}`."
    )


def canonical_attachment_review_json(value: object) -> bytes:
    """Serialize one CEA-1.2 boundary value canonically."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
