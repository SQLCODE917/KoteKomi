"""Blind semantic review of Head-Aligned unequal-range Attachment Edges."""

from __future__ import annotations

import json
from collections.abc import Sequence

from kotekomi_application import (
    AttachmentBlindReviewCase,
    AttachmentBlindReviewCatalog,
    AttachmentBlindReviewDecision,
    AttachmentBlindReviewEvaluation,
    AttachmentBlindReviewReport,
    AttachmentBlindReviewSubmission,
    AttachmentEvidenceReference,
    AttachmentSourceRange,
    AttachmentStructuralSafetyReport,
    attachment_blind_review_case_id,
    attachment_blind_review_fingerprint,
    classify_attachment_blind_review_outcome,
    classify_attachment_unequal_range_relation,
)


def build_attachment_blind_review_catalog(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    structural_safety: AttachmentStructuralSafetyReport,
) -> AttachmentBlindReviewCatalog:
    """Build the sealed Head-Aligned unequal-range review inventory."""
    cases: list[AttachmentBlindReviewCase] = []
    for phase_report in (structural_safety.development, structural_safety.validation):
        for source_case in phase_report.cases:
            candidate_range = AttachmentSourceRange(
                start=source_case.candidate.start,
                end=source_case.candidate.end,
                text=source_case.candidate.text,
            )
            event_range = AttachmentSourceRange(
                start=source_case.event.start,
                end=source_case.event.end,
                text=source_case.event.text,
            )
            if (candidate_range.start, candidate_range.end) == (
                event_range.start,
                event_range.end,
            ):
                continue
            cases.append(
                AttachmentBlindReviewCase(
                    id=attachment_blind_review_case_id(
                        phase=source_case.phase,
                        matrix_id=source_case.matrix_id,
                        candidate_id=source_case.candidate.id,
                        event_id=source_case.event.source_grounded_event_id,
                    ),
                    phase=source_case.phase,
                    matrix_id=source_case.matrix_id,
                    source_text=source_case.source_text,
                    source_text_sha256=source_case.candidate.source_text_sha256,
                    candidate_id=source_case.candidate.id,
                    event_id=source_case.event.source_grounded_event_id,
                    candidate_range=candidate_range,
                    event_range=event_range,
                    relation=classify_attachment_unequal_range_relation(
                        candidate_range,
                        event_range,
                    ),
                    foreign_event_ids=source_case.foreign_event_ids,
                    structural_selected=source_case.structural_answer == "Y",
                    original_gold=source_case.original_gold,
                    reviewed_gold=source_case.reviewed_gold,
                    effective_gold=source_case.effective_gold,
                    gold_authority=source_case.gold_authority,
                )
            )
    ordered = tuple(
        sorted(
            cases,
            key=lambda item: (
                item.phase,
                item.matrix_id,
                item.candidate_range.start,
                item.candidate_range.end,
                item.event_range.start,
                item.event_range.end,
                item.event_id,
            ),
        )
    )
    draft = AttachmentBlindReviewCatalog.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        cases=ordered,
        case_count=len(ordered),
        selected_count=sum(item.structural_selected for item in ordered),
        excluded_count=sum(not item.structural_selected for item in ordered),
        candidate_contains_event_count=sum(
            item.relation.value == "candidate_contains_event" for item in ordered
        ),
        event_contains_candidate_count=sum(
            item.relation.value == "event_contains_candidate" for item in ordered
        ),
        partial_overlap_count=sum(item.relation.value == "partial_overlap" for item in ordered),
        disjoint_count=sum(item.relation.value == "disjoint" for item in ordered),
        catalog_fingerprint="0" * 64,
    )
    return AttachmentBlindReviewCatalog(
        **draft.model_dump(exclude={"catalog_fingerprint"}),
        catalog_fingerprint=attachment_blind_review_fingerprint(draft),
    )


def render_attachment_blind_review_request(catalog: AttachmentBlindReviewCatalog) -> str:
    """Render only the semantic task and source evidence visible to the reviewer."""
    lines = [
        "# Blind Candidate-to-Event Review",
        "",
        "Judge each case using only the passage shown in that case.",
        "",
        "The Event is the exact text shown after `Event`.",
        "",
        "The Candidate is the exact text shown after `Candidate`.",
        "",
        "Answer `Y` when the complete Candidate belongs to what the passage says about the Event.",
        "",
        "This includes participants, objects, time, place, negation, uncertainty, purpose, "
        "comparison, attribution, and other details of that same Event.",
        "",
        "Answer `N` when any substantive part of the Candidate belongs only to another event, "
        "claim, or incidental context.",
        "",
        "The Candidate containing the Event words does not by itself make the answer `Y`.",
        "",
        "Answer `U` only when the passage does not decide whether the complete Candidate belongs.",
        "",
        "Return only one JSON object with this shape:",
        "",
        "```json",
        '{"schema_version":"attachment_blind_review_submission_v1",'
        '"reviewer":"Claude Opus 5 high",'
        '"decisions":[{"case_id":"ubr_...","answer":"Y|N|U",'
        '"rationale":"one concise sentence"}]}',
        "```",
        "",
        "Return one decision for every case ID exactly once.",
        "",
    ]
    for index, case in enumerate(catalog.cases, start=1):
        lines.extend(
            [
                f"## Case {index}: {case.id}",
                "",
                "Passage:",
                "",
                "```text",
                case.source_text,
                "```",
                "",
                f"Event: `{json.dumps(case.event_range.text, ensure_ascii=False)}`",
                "",
                f"Candidate: `{json.dumps(case.candidate_range.text, ensure_ascii=False)}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_attachment_blind_review_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    catalog: AttachmentBlindReviewCatalog,
    submission: AttachmentBlindReviewSubmission,
    response_sha256: str,
) -> AttachmentBlindReviewReport:
    """Reveal and evaluate Structural Selection after complete response validation."""
    decision_by_id = {item.case_id: item for item in submission.decisions}
    expected_ids = {item.id for item in catalog.cases}
    if set(decision_by_id) != expected_ids:
        missing = tuple(sorted(expected_ids - set(decision_by_id)))
        foreign = tuple(sorted(set(decision_by_id) - expected_ids))
        raise ValueError(
            f"Blind review response inventory drifted; missing={missing}, foreign={foreign}."
        )
    evaluations = tuple(_evaluate_case(case, decision_by_id[case.id]) for case in catalog.cases)
    selected = tuple(item for item in evaluations if item.case.structural_selected)
    excluded = tuple(item for item in evaluations if not item.case.structural_selected)
    selected_no_count = sum(item.decision.answer == "N" for item in selected)
    selected_unclear_count = sum(item.decision.answer == "U" for item in selected)
    excluded_yes_count = sum(item.decision.answer == "Y" for item in excluded)
    excluded_unclear_count = sum(item.decision.answer == "U" for item in excluded)
    draft = AttachmentBlindReviewReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        catalog_fingerprint=catalog.catalog_fingerprint,
        response_sha256=response_sha256,
        reviewer=submission.reviewer,
        evaluations=evaluations,
        outcome=classify_attachment_blind_review_outcome(
            selected_no_count=selected_no_count,
            selected_unclear_count=selected_unclear_count,
            excluded_yes_count=excluded_yes_count,
            excluded_unclear_count=excluded_unclear_count,
        ),
        case_count=len(evaluations),
        selected_yes_count=sum(item.decision.answer == "Y" for item in selected),
        selected_no_count=selected_no_count,
        selected_unclear_count=selected_unclear_count,
        excluded_yes_count=excluded_yes_count,
        excluded_no_count=sum(item.decision.answer == "N" for item in excluded),
        excluded_unclear_count=excluded_unclear_count,
        result_fingerprint="0" * 64,
    )
    return AttachmentBlindReviewReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_blind_review_fingerprint(draft),
    )


def render_attachment_blind_review_comparison(report: AttachmentBlindReviewReport) -> str:
    """Render exact reviewer input, output, and revealed policy result."""
    lines = [
        "# CEA-1.21 Unequal-Range Blind Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Reviewer: `{report.reviewer}`",
        "",
        f"Cases: `{report.case_count}`",
        "",
        f"Selected Y/N/U: `{report.selected_yes_count}` / `{report.selected_no_count}` / "
        f"`{report.selected_unclear_count}`",
        "",
        f"Excluded Y/N/U: `{report.excluded_yes_count}` / `{report.excluded_no_count}` / "
        f"`{report.excluded_unclear_count}`",
        "",
    ]
    for evaluation in report.evaluations:
        case = evaluation.case
        lines.extend(
            [
                f"## {case.id}",
                "",
                "> " + case.source_text,
                "",
                f"Event: `{json.dumps(case.event_range.text, ensure_ascii=False)}`",
                "",
                f"Candidate: `{json.dumps(case.candidate_range.text, ensure_ascii=False)}`",
                "",
                f"Blind answer: `{evaluation.decision.answer}`",
                "",
                f"Blind rationale: {evaluation.decision.rationale}",
                "",
                f"Range relation: `{case.relation.value}`",
                "",
                f"Structural Selection: `{case.structural_selected}`",
                "",
                f"Structural expected answer: `{evaluation.structural_expected_answer}`",
                "",
                "Structural evaluation: "
                f"`{'correct' if evaluation.structural_correct else 'wrong'}`",
                "",
                f"Original Gold: `{case.original_gold}`",
                "",
                f"Reviewed Gold: `{case.reviewed_gold}`",
                "",
                f"Effective Gold: `{case.effective_gold}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_blind_review_handoff(
    report: AttachmentBlindReviewReport,
    *,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained second-opinion handoff."""
    return "\n".join(
        [
            "# CEA-1.21 Unequal-Range Blind Review Handoff",
            "",
            "Verify that the blind request omitted all evaluation authority.",
            "",
            "Verify every blind judgment against the exact source text.",
            "",
            "Verify the revealed Structural Selection comparison and outcome.",
            "",
            "This one-document, one-reviewer result cannot establish transfer.",
            "",
            render_attachment_blind_review_comparison(report).rstrip(),
            "",
            "## Package files",
            "",
            *[
                f"- `{item.label}`: `{item.path}` (`sha256:{item.sha256}`)"
                for item in sorted(package_files, key=lambda item: item.label)
            ],
            "",
            f"Source repository: {source_repository_url}",
            "",
            f"Source revision: `{source_revision}`",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
        ]
    )


def _evaluate_case(
    case: AttachmentBlindReviewCase,
    decision: AttachmentBlindReviewDecision,
) -> AttachmentBlindReviewEvaluation:
    expected = "Y" if case.structural_selected else "N"
    answer = decision.answer
    return AttachmentBlindReviewEvaluation(
        case=case,
        decision=decision,
        structural_expected_answer=expected,
        structural_correct=answer == expected,
        original_gold_agrees=None if answer == "U" else answer == case.original_gold,
        reviewed_gold_agrees=(
            None if answer == "U" or case.reviewed_gold is None else answer == case.reviewed_gold
        ),
        effective_gold_agrees=None if answer == "U" else answer == case.effective_gold,
    )
