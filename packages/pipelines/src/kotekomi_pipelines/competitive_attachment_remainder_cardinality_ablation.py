"""Evaluation and review rendering for CEA-1.16."""

from __future__ import annotations

import json
from collections.abc import Sequence

from kotekomi_application import (
    ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID,
    AttachmentEvidenceReference,
    AttachmentRemainderCardinalityObservation,
    AttachmentRemainderCardinalityPreflight,
    AttachmentRemainderCardinalityReport,
    AttachmentRemainderEnumerationReport,
    attachment_remainder_cardinality_fingerprint,
    attachment_remainder_cardinality_outcome,
    build_attachment_remainder_cardinality_view,
)


def build_remainder_cardinality_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    predecessor: AttachmentRemainderEnumerationReport,
    configured_max_output_tokens: int,
) -> AttachmentRemainderCardinalityPreflight:
    """Build the one-case split inventory from sealed CEA-1.15 evidence."""
    if predecessor.outcome.value != "supported":
        raise ValueError("CEA-1.16 requires the supported CEA-1.15 outcome.")
    recovered = next(
        (
            item
            for item in predecessor.cases
            if item.view.authoritative_task.id == ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID
        ),
        None,
    )
    if recovered is None or recovered.fresh_answers != ("Y", "Y") or not recovered.passed:
        raise ValueError("CEA-1.15 recovered-case evidence drifted.")
    identities = {item.model_identity_digest for item in recovered.observations}
    if len(identities) != 1:
        raise ValueError("CEA-1.15 recovered case used more than one model identity.")
    view = build_attachment_remainder_cardinality_view(recovered.view)
    draft = AttachmentRemainderCardinalityPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        view=view,
        expected_model_identity_digest=next(iter(identities)),
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentRemainderCardinalityPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_remainder_cardinality_fingerprint(draft),
    )


def build_remainder_cardinality_report(
    *,
    preflight: AttachmentRemainderCardinalityPreflight,
    inputs: tuple[AttachmentEvidenceReference, ...],
    observation: AttachmentRemainderCardinalityObservation,
) -> AttachmentRemainderCardinalityReport:
    """Evaluate one exact split judgment against the sealed one-part control."""
    outcome = attachment_remainder_cardinality_outcome(observation)
    draft = AttachmentRemainderCardinalityReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=preflight.prompt,
        view=preflight.view,
        observation=observation,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentRemainderCardinalityReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_remainder_cardinality_fingerprint(draft),
    )


def render_remainder_cardinality_review(report: AttachmentRemainderCardinalityReport) -> str:
    """Render compact exact data-in/data-out and probability evidence."""
    task = report.view.predecessor_view.authoritative_task
    edge = task.edge_filter_task.edge
    observation = report.observation
    evidence = observation.finite_label_evidence
    split_start = report.view.split_remainder_ranges[0].start
    split_end = report.view.split_remainder_ranges[-1].end
    one_part_text = task.edge_filter_task.source_text[split_start:split_end]
    lines = [
        "# CEA-1.16 Remainder Cardinality Ablation Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        "Exact SourceSegment:",
        "",
        f"> {_json(task.edge_filter_task.source_text)}",
        "",
        f"Authoritative Candidate: `{_json(edge.candidate_range.text)}`",
        "",
        f"Target Event: `{_json(edge.event_range.text)}`",
        "",
        "Sealed one-part control:",
        "",
        f"- `{_json(one_part_text)}`",
        "",
        f"Sealed answers: `{'/'.join(report.sealed_one_part_answers)}`",
        "",
        "Fresh two-part view:",
        "",
        *(f"- `{_json(item.text)}`" for item in report.view.split_remainder_ranges),
        "",
        "Exact model input:",
        "",
        "~~~~text",
        observation.exact_model_input,
        "~~~~",
        "",
        f"Raw output: `{_json(observation.raw_output_text)}`",
        "",
        f"Parsed answer: `{_answer(observation)}`",
        "",
    ]
    if evidence is None:
        lines.extend(["Finite-label evidence: `missing`", ""])
    else:
        lines.extend(
            [
                f"Finite-label argmax: `{evidence.finite_label_argmax.value}`",
                "",
                f"Y log probability: `{evidence.yes_log_probability}`",
                "",
                f"N log probability: `{evidence.no_log_probability}`",
                "",
                f"U log probability: `{evidence.unclear_log_probability}`",
                "",
                f"Attachment score: `{evidence.attachment_score}`",
                "",
            ]
        )
    lines.extend(
        [
            f"Strict finite answer: `{str(observation.strict_finite_answer).lower()}`",
            "",
            "ProposedChanges: `0`",
            "",
            "Accepted Ledger changes: `0`",
            "",
        ]
    )
    return "\n".join(lines)


def render_remainder_cardinality_handoff(
    report: AttachmentRemainderCardinalityReport,
    *,
    prompt_text: str,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained independent-review package."""
    lines = [
        "# CEA-1.16 Remainder Cardinality Ablation Handoff",
        "",
        "## Review question",
        "",
        "Does splitting unchanged Remainder content from one tagged part into two "
        "change the recovered answer from `Y` to `N`?",
        "",
        "## Result summary",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        "Model executions: `1`",
        "",
        "False-positive safety tested: `false`",
        "",
        "Validation executed: `false`",
        "",
        "Production integration: `not_activated`",
        "",
        "## Interpretation",
        "",
        "`supported` means this exact task is cardinality-sensitive.",
        "",
        "`falsified` means one-part cardinality was not necessary for this exact recovery.",
        "",
        "Neither outcome authorizes a general Remainder policy or production integration.",
        "",
        "## Questions for independent review",
        "",
        "1. Do all file digests and the report fingerprint reconcile?",
        "2. Did every model-visible character and marker remain fixed except the added "
        "Remainder boundary?",
        "3. Does the finite-label evidence agree with the observed answer?",
        "4. Does the declared outcome follow from the accepted TDD?",
        "5. What is the smallest production-relevant next experiment?",
        "",
        "## Exact prompt",
        "",
        "~~~~text",
        prompt_text,
        "~~~~",
        "",
        "## Exact experiment evidence",
        "",
        render_remainder_cardinality_review(report).rstrip(),
        "",
        "## Package files",
        "",
    ]
    lines.extend(
        f"- `{item.label}`: `{item.path}` (`sha256:{item.sha256}`)"
        for item in sorted(package_files, key=lambda value: value.label)
    )
    lines.extend(
        [
            "",
            f"Source repository: {source_repository_url}",
            "",
            f"Source revision: `{source_revision}`",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
        ]
    )
    return "\n".join(lines)


def _answer(observation: AttachmentRemainderCardinalityObservation) -> str:
    answer = observation.decision.answer
    return answer.value if answer is not None else "unresolved"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
