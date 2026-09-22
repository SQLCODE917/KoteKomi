"""Prepare and evaluate the CEA-1.23 Nested Event ownership transfer."""

from __future__ import annotations

import hashlib
import json
from base64 import b64decode
from collections.abc import Mapping, Sequence
from typing import cast

from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentNestedTransferCase,
    AttachmentNestedTransferCatalog,
    AttachmentNestedTransferEvaluation,
    AttachmentNestedTransferObservation,
    AttachmentNestedTransferReport,
    AttachmentNestedTransferSelector,
    AttachmentNestedTransferSelectorCatalog,
    AttachmentNestedTransferSubmission,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_nested_transfer_case_id,
    attachment_nested_transfer_fingerprint,
    attachment_nested_transfer_group_metrics,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    classify_attachment_nested_transfer_outcome,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)


def build_attachment_nested_transfer_catalog(
    *,
    selector_catalog: AttachmentNestedTransferSelectorCatalog,
    source_catalog: Mapping[str, object],
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
) -> AttachmentNestedTransferCatalog:
    """Resolve the frozen answer-free selectors against exact reviewed SourceSegments."""
    segments = _source_segments(source_catalog)
    cases = tuple(
        _build_case(selector, _source_segment(segments, selector.source_segment_id))
        for selector in selector_catalog.selectors
    )
    draft = AttachmentNestedTransferCatalog.model_construct(
        inputs=inputs,
        prompt=prompt,
        cases=cases,
        case_count=20,
        document_count=2,
        result_fingerprint="0" * 64,
    )
    return AttachmentNestedTransferCatalog(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_nested_transfer_fingerprint(draft),
    )


def validate_attachment_nested_transfer_submission(
    catalog: AttachmentNestedTransferCatalog,
    submission: AttachmentNestedTransferSubmission,
) -> AttachmentNestedTransferSubmission:
    """Validate one complete blind response without repair or coercion."""
    expected = {item.id for item in catalog.cases}
    observed = {item.case_id for item in submission.decisions}
    if observed != expected or len(submission.decisions) != len(catalog.cases):
        raise ValueError("Transfer review response does not cover the exact catalog.")
    return submission


def build_attachment_nested_transfer_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    catalog: AttachmentNestedTransferCatalog,
    submission: AttachmentNestedTransferSubmission,
    observations: tuple[AttachmentNestedTransferObservation, ...],
) -> AttachmentNestedTransferReport:
    """Evaluate one Qwen observation for every sealed Transfer Case."""
    validate_attachment_nested_transfer_submission(catalog, submission)
    decisions = {item.case_id: item for item in submission.decisions}
    observed = {item.case_id: item for item in observations}
    if len(observed) != len(observations) or set(observed) != {item.id for item in catalog.cases}:
        raise ValueError("Transfer observations do not cover the exact catalog.")
    evaluations = tuple(
        AttachmentNestedTransferEvaluation(
            case=case,
            expected=decisions[case.id],
            observation=observed[case.id],
            complete=(observed[case.id].decision.status.value == "complete"),
            correct=_answer_matches(
                observed[case.id],
                decisions[case.id].answer,
            ),
        )
        for case in catalog.cases
    )
    yes = tuple(item for item in evaluations if item.expected.answer == "Y")
    no = tuple(item for item in evaluations if item.expected.answer == "N")
    unclear = tuple(item for item in evaluations if item.expected.answer == "U")
    identities = tuple(
        sorted(
            {
                item.model_identity_digest
                for item in observations
                if item.model_identity_digest is not None
            }
        )
    )
    draft = AttachmentNestedTransferReport.model_construct(
        inputs=inputs,
        reviewer=submission.reviewer,
        evaluations=evaluations,
        outcome=classify_attachment_nested_transfer_outcome(evaluations=evaluations),
        case_count=20,
        expected_yes_count=len(yes),
        expected_no_count=len(no),
        expected_unclear_count=len(unclear),
        complete_count=sum(item.complete for item in evaluations),
        correct_count=sum(item.correct for item in evaluations),
        actual_yes_count=sum(
            item.observation.decision.answer is not None
            and item.observation.decision.answer.value == "Y"
            for item in evaluations
        ),
        actual_no_count=sum(
            item.observation.decision.answer is not None
            and item.observation.decision.answer.value == "N"
            for item in evaluations
        ),
        actual_unclear_count=sum(
            item.observation.decision.status.value == "unclear" for item in evaluations
        ),
        invalid_output_count=sum(
            item.observation.decision.status.value == "invalid_output" for item in evaluations
        ),
        input_blocked_count=sum(
            item.observation.decision.status.value == "input_blocked" for item in evaluations
        ),
        model_failed_count=sum(
            item.observation.decision.status.value == "model_failed" for item in evaluations
        ),
        accuracy=_ratio(sum(item.correct for item in evaluations), len(evaluations)),
        yes_recall=_ratio(sum(item.correct for item in yes), len(yes)),
        no_recall=_ratio(sum(item.correct for item in no), len(no)),
        unresolved_count=sum(not item.complete for item in evaluations),
        group_metrics=attachment_nested_transfer_group_metrics(evaluations),
        model_identity_digests=identities,
        model_execution_count=sum(item.runtime_invoked for item in observations),
        model_elapsed_milliseconds=sum(item.elapsed_milliseconds for item in observations),
        result_fingerprint="0" * 64,
    )
    return AttachmentNestedTransferReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_nested_transfer_fingerprint(draft),
    )


def render_attachment_nested_transfer_blind_request(
    catalog: AttachmentNestedTransferCatalog,
) -> str:
    """Render a label-free semantic review request."""
    lines = [
        "# CEA-1.23 Blind Nested Event Ownership Review",
        "",
        "Review each case from the exact source text.",
        "",
        "The Passage is the complete source text.",
        "",
        "The Candidate is the exact quoted text.",
        "",
        "The Target Event is the exact event expression being tested.",
        "",
        "Contained Events are other event expressions inside the Candidate.",
        "",
        "Answer `Y` when every substantive Candidate part belongs to what the Passage says "
        "about the Target Event.",
        "",
        "Answer `N` when any substantive Candidate part belongs to a separate sibling event "
        "or proposition.",
        "",
        "Answer `U` only when the Passage does not decide ownership.",
        "",
        "Return one JSON object with this exact shape:",
        "",
        "~~~~json",
        '{"schema_version":"attachment_nested_transfer_submission_v1",'
        '"reviewer":"<name>","decisions":['
        '{"case_id":"ntc_...","answer":"Y|N|U","rationale":"..."}]}',
        "~~~~",
        "",
        "Return JSON only.",
        "",
    ]
    for case in catalog.cases:
        task = case.task
        target = next(item for item in task.event_options if item.label == task.target_event_label)
        contained = tuple(
            item
            for item in task.event_options
            if item.source_grounded_event_id in case.contained_event_ids
        )
        lines.extend(
            [
                f"## {case.id}",
                "",
                "Passage:",
                "",
                "> " + task.source_text.replace("\n", "\n> "),
                "",
                f"Candidate: {json.dumps(task.candidate.text, ensure_ascii=False)}",
                "",
                f"Target Event: {json.dumps(target.text, ensure_ascii=False)}",
                "",
                "Contained Events:",
                "",
                *[f"- {json.dumps(item.text, ensure_ascii=False)}" for item in contained],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_nested_transfer_catalog(
    catalog: AttachmentNestedTransferCatalog,
) -> str:
    """Render the exact answer-free transfer inventory."""
    lines = [
        "# CEA-1.23 Nested Event Ownership Transfer Catalog",
        "",
        f"Cases: `{catalog.case_count}`",
        "",
        f"Documents: `{catalog.document_count}`",
        "",
        f"Frozen prompt SHA-256: `{catalog.prompt.sha256}`",
        "",
    ]
    for case in catalog.cases:
        target = next(
            item for item in case.task.event_options if item.label == case.task.target_event_label
        )
        lines.extend(
            [
                f"## {case.selector_id} — {case.id}",
                "",
                f"Fixture: `{case.fixture_path}`",
                "",
                f"SourceSegment: `{case.source_segment_id}`",
                "",
                f"Candidate: {json.dumps(case.task.candidate.text, ensure_ascii=False)}",
                "",
                f"Target Event: {json.dumps(target.text, ensure_ascii=False)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_nested_transfer_review(
    report: AttachmentNestedTransferReport,
    *,
    prompt_text: str,
) -> str:
    """Render compact exact data-in and data-out evidence."""
    lines = [
        "# CEA-1.23 Nested Event Ownership Transfer Result",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Reviewer: `{report.reviewer}`",
        "",
        f"Correct: `{report.correct_count}` / `{report.case_count}`",
        "",
        f"Accuracy: `{report.accuracy:.6f}`",
        "",
        f"Y recall: `{report.yes_recall:.6f}`",
        "",
        f"N recall: `{report.no_recall:.6f}`",
        "",
        f"Unresolved: `{report.unresolved_count}`",
        "",
        f"Actual Y / N / U: `{report.actual_yes_count}` / `{report.actual_no_count}` / "
        f"`{report.actual_unclear_count}`",
        "",
        f"Invalid / blocked / failed: `{report.invalid_output_count}` / "
        f"`{report.input_blocked_count}` / `{report.model_failed_count}`",
        "",
        f"Model executions: `{report.model_execution_count}`",
        "",
        f"Model elapsed milliseconds: `{report.model_elapsed_milliseconds}`",
        "",
        "## Frozen prompt",
        "",
        "~~~~text",
        prompt_text.rstrip(),
        "~~~~",
        "",
        "## Group metrics",
        "",
        *[
            f"- `{item.group_kind.value}:{item.group_value}`: "
            f"{item.correct_count}/{item.case_count} correct; "
            f"{item.unresolved_count} unresolved; accuracy `{item.accuracy:.6f}`"
            for item in report.group_metrics
        ],
        "",
    ]
    for evaluation in report.evaluations:
        raw = (
            b64decode(evaluation.observation.raw_output_base64).decode(errors="replace")
            if evaluation.observation.raw_output_base64 is not None
            else None
        )
        actual = (
            evaluation.observation.decision.answer.value
            if evaluation.observation.decision.answer is not None
            else evaluation.observation.decision.status.value
        )
        lines.extend(
            [
                f"## {evaluation.case.selector_id} — {evaluation.case.id}",
                "",
                f"Expected: `{evaluation.expected.answer}`",
                "",
                f"Expected rationale: {evaluation.expected.rationale}",
                "",
                f"Actual: `{actual}`",
                "",
                f"Correct: `{evaluation.correct}`",
                "",
                "Exact complete model input:",
                "",
                "~~~~text",
                evaluation.observation.exact_model_input.rstrip(),
                "~~~~",
                "",
                f"Raw output: `{json.dumps(raw, ensure_ascii=False)}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_nested_transfer_handoff(
    report: AttachmentNestedTransferReport,
    *,
    prompt_text: str,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render the self-contained CEA-1.23 second-opinion request."""
    return "\n".join(
        [
            "# CEA-1.23 Nested Event Ownership Transfer Handoff",
            "",
            "Verify the blind labels against each exact SourceSegment.",
            "",
            "Verify each Qwen answer and every reported metric.",
            "",
            "Assess whether the Frozen Prompt transfers beyond its design Document.",
            "",
            "The blind labels answer semantic ownership rather than Original Gold "
            "character containment.",
            "",
            "The label reviewer and a later Claude review use the same model family.",
            "",
            render_attachment_nested_transfer_review(
                report,
                prompt_text=prompt_text,
            ).rstrip(),
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


def _build_case(
    selector: AttachmentNestedTransferSelector,
    source: Mapping[str, object],
) -> AttachmentNestedTransferCase:
    text = _required_str(source, "source_text")
    source_digest = _required_str(source, "source_text_sha256")
    if hashlib.sha256(text.encode()).hexdigest() != source_digest:
        raise ValueError("Transfer SourceSegment digest drifted.")
    source_segment_id = _required_str(source, "source_segment_id")
    fixture_path = _required_str(source, "fixture_path")
    candidate_start = _unique_start(text, selector.candidate_text, "Candidate")
    candidate_end = candidate_start + len(selector.candidate_text)
    event_texts = (selector.target_event_text, *selector.contained_event_texts)
    event_ranges = tuple(
        (_unique_start(text, event_text, "Event"), event_text) for event_text in event_texts
    )
    if any(
        start < candidate_start or start + len(event_text) > candidate_end
        for start, event_text in event_ranges
    ):
        raise ValueError("Every Transfer Event must occur inside the Candidate.")
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=candidate_start,
        end=candidate_end,
        text=selector.candidate_text,
        reasons=(PropositionFragmentReason.CLAUSE_LOCAL_CONSTITUENT,),
        parent_candidate_ids=(_local_id("pfc", selector.case_id, selector.candidate_text),),
        linguistic_token_ids=(),
        source_record_ids=(selector.case_id,),
    )
    candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=candidate_start,
        end=candidate_end,
        text=selector.candidate_text,
        reasons=(PropositionFragmentReason.CLAUSE_LOCAL_CONSTITUENT,),
        parent_candidate_ids=(_local_id("pfc", selector.case_id, selector.candidate_text),),
        linguistic_token_ids=(),
        source_record_ids=(selector.case_id,),
    )
    unsorted_options = tuple(
        _event_option(
            selector=selector,
            source_segment_id=source_segment_id,
            source_digest=source_digest,
            start=start,
            text=event_text,
        )
        for start, event_text in event_ranges
    )
    sorted_options = tuple(
        sorted(unsorted_options, key=lambda item: (item.start, item.end, item.id))
    )
    options = tuple(
        item.model_copy(update={"label": f"E{index}"})
        for index, item in enumerate(sorted_options, start=1)
    )
    target = next(item for item in options if item.text == selector.target_event_text)
    edge_values = {
        "phase": "validation",
        "source_segment_id": source_segment_id,
        "source_text_sha256": source_digest,
        "candidate_id": candidate.id,
        "source_grounded_event_id": target.source_grounded_event_id,
        "candidate_start": candidate.start,
        "candidate_end": candidate.end,
        "event_start": target.start,
        "event_end": target.end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**edge_values),
        phase="validation",
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        candidate_id=candidate.id,
        source_grounded_event_id=target.source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate.start,
            end=candidate.end,
            text=candidate.text,
        ),
        event_range=AttachmentSourceRange(
            start=target.start,
            end=target.end,
            text=target.text,
        ),
        origins=(AttachmentProposalOrigin.CURATED_TRANSFER,),
        syntax_arms=(),
    )
    task = build_attachment_edge_filter_task(
        source_text=text,
        edge=edge,
        candidate=candidate,
        event_options=options,
    )
    contained = tuple(
        item.source_grounded_event_id
        for item in options
        if item.source_grounded_event_id != target.source_grounded_event_id
    )
    return AttachmentNestedTransferCase(
        id=attachment_nested_transfer_case_id(
            selector_id=selector.case_id,
            task_id=task.task_id,
        ),
        selector_id=selector.case_id,
        fixture_path=fixture_path,
        source_segment_id=source_segment_id,
        task=task,
        contained_event_ids=contained,
    )


def _event_option(
    *,
    selector: AttachmentNestedTransferSelector,
    source_segment_id: str,
    source_digest: str,
    start: int,
    text: str,
) -> CompetitiveAttachmentEventOption:
    event_id = _local_id("sge", selector.case_id, start, text)
    trigger_id = _local_id("etd", selector.case_id, start, text)
    end = start + len(text)
    return CompetitiveAttachmentEventOption(
        id=competitive_attachment_event_option_id(
            source_grounded_event_id=event_id,
            event_trigger_id=trigger_id,
            source_segment_id=source_segment_id,
            source_text_sha256=source_digest,
            start=start,
            end=end,
            text=text,
        ),
        label="E1",
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=start,
        end=end,
        text=text,
    )


def _source_segments(source_catalog: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    if source_catalog.get("schema_version") != "organization_mention_held_out_gold_v1":
        raise ValueError("CEA-1.23 requires the reviewed held-out SourceSegment catalog.")
    if source_catalog.get("annotation_status") != "human_reviewed_held_out_gold":
        raise ValueError("CEA-1.23 requires human-reviewed SourceSegments.")
    raw = source_catalog.get("segments")
    if not isinstance(raw, list):
        raise ValueError("The held-out catalog lacks SourceSegments.")
    values = cast(list[object], raw)
    segments: dict[str, Mapping[str, object]] = {}
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("The held-out catalog contains an invalid SourceSegment.")
        typed = cast(Mapping[str, object], value)
        source_segment_id = _required_str(typed, "source_segment_id")
        if source_segment_id in segments:
            raise ValueError("The held-out catalog repeats a SourceSegment ID.")
        segments[source_segment_id] = typed
    return segments


def _source_segment(
    segments: Mapping[str, Mapping[str, object]],
    source_segment_id: str,
) -> Mapping[str, object]:
    try:
        return segments[source_segment_id]
    except KeyError as error:
        raise ValueError("One Transfer selector names an unknown SourceSegment.") from error


def _unique_start(source_text: str, value: str, label: str) -> int:
    if source_text.count(value) != 1:
        raise ValueError(f"Transfer {label} must occur exactly once in its SourceSegment.")
    return source_text.index(value)


def _required_str(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"Transfer source evidence requires string {key}.")
    return result


def _local_id(prefix: str, *values: object) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"{prefix}_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _answer_matches(
    observation: AttachmentNestedTransferObservation,
    expected: str,
) -> bool:
    answer = observation.decision.answer
    return answer is not None and answer.value == expected
