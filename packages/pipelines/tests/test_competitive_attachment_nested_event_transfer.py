from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from copy import deepcopy
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentNestedTransferCatalog,
    AttachmentNestedTransferDecision,
    AttachmentNestedTransferObservation,
    AttachmentNestedTransferOutcome,
    AttachmentNestedTransferSelectorCatalog,
    AttachmentNestedTransferSubmission,
)
from kotekomi_pipelines.competitive_attachment_nested_event_transfer import (
    build_attachment_nested_transfer_catalog,
    build_attachment_nested_transfer_report,
    render_attachment_nested_transfer_blind_request,
    validate_attachment_nested_transfer_submission,
)

ROOT = Path(__file__).resolve().parents[3]
SELECTORS = ROOT / "docs/cea123-nested-event-transfer-catalog-v1.json"
SOURCE_CATALOG = ROOT / "docs/organization-mention-held-out-gold-v1.json"
PROMPT = ROOT / "prompts/competitive_attachment_nested_event_ownership_v1.md"


def test_transfer_catalog_resolves_twenty_exact_cross_document_cases() -> None:
    catalog = _catalog()

    assert catalog.case_count == 20
    assert catalog.document_count == 2
    assert len({item.source_segment_id for item in catalog.cases}) == 20
    for case in catalog.cases:
        task = case.task
        assert task.source_text[task.candidate.start : task.candidate.end] == task.candidate.text
        assert len(case.contained_event_ids) >= 1


def test_transfer_blind_request_contains_no_expected_answer() -> None:
    request = render_attachment_nested_transfer_blind_request(_catalog())

    assert "Expected:" not in request
    assert "Original Gold" not in request
    assert "Qwen" not in request
    assert request.count("## ntc_") == 20


def test_transfer_catalog_rejects_non_unique_source_expression() -> None:
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    source = json.loads(SOURCE_CATALOG.read_text(encoding="utf-8"))
    changed = deepcopy(source)
    target_id = selectors.selectors[0].source_segment_id
    segment = next(item for item in changed["segments"] if item["source_segment_id"] == target_id)
    segment["source_text"] += " " + selectors.selectors[0].candidate_text
    segment["source_text_sha256"] = hashlib.sha256(segment["source_text"].encode()).hexdigest()

    with pytest.raises(ValueError, match="Candidate must occur exactly once"):
        build_attachment_nested_transfer_catalog(
            selector_catalog=selectors,
            source_catalog=changed,
            inputs=(_reference("selectors", SELECTORS),),
            prompt=_reference("prompt", PROMPT),
        )


def test_transfer_catalog_rejects_absent_candidate_expression() -> None:
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    first = selectors.selectors[0].model_copy(update={"candidate_text": "absent candidate"})
    changed = selectors.model_copy(update={"selectors": (first, *selectors.selectors[1:])})

    with pytest.raises(ValueError, match="Candidate must occur exactly once"):
        build_attachment_nested_transfer_catalog(
            selector_catalog=changed,
            source_catalog=json.loads(SOURCE_CATALOG.read_text(encoding="utf-8")),
            inputs=(_reference("selectors", SELECTORS),),
            prompt=_reference("prompt", PROMPT),
        )


def test_transfer_catalog_rejects_non_unique_event_expression() -> None:
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    source = json.loads(SOURCE_CATALOG.read_text(encoding="utf-8"))
    changed = deepcopy(source)
    target_id = selectors.selectors[0].source_segment_id
    segment = next(item for item in changed["segments"] if item["source_segment_id"] == target_id)
    segment["source_text"] += " " + selectors.selectors[0].target_event_text
    segment["source_text_sha256"] = hashlib.sha256(segment["source_text"].encode()).hexdigest()

    with pytest.raises(ValueError, match="Event must occur exactly once"):
        build_attachment_nested_transfer_catalog(
            selector_catalog=selectors,
            source_catalog=changed,
            inputs=(_reference("selectors", SELECTORS),),
            prompt=_reference("prompt", PROMPT),
        )


def test_transfer_catalog_rejects_absent_event_expression() -> None:
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    first = selectors.selectors[0].model_copy(update={"target_event_text": "absent event"})
    changed = selectors.model_copy(update={"selectors": (first, *selectors.selectors[1:])})

    with pytest.raises(ValueError, match="Event must occur exactly once"):
        build_attachment_nested_transfer_catalog(
            selector_catalog=changed,
            source_catalog=json.loads(SOURCE_CATALOG.read_text(encoding="utf-8")),
            inputs=(_reference("selectors", SELECTORS),),
            prompt=_reference("prompt", PROMPT),
        )


def test_transfer_submission_requires_exact_case_coverage() -> None:
    catalog = _catalog()
    submission = _submission(catalog)
    incomplete = submission.model_copy(update={"decisions": submission.decisions[:-1]})

    with pytest.raises(ValueError, match="exact catalog"):
        validate_attachment_nested_transfer_submission(catalog, incomplete)


def test_transfer_report_scores_exact_occurrence_answers(tmp_path: Path) -> None:
    catalog = _catalog()
    submission = _submission(catalog)
    expected = {item.case_id: item.answer for item in submission.decisions}
    evidence = tmp_path / "execution.json"
    evidence.write_text("{}\n", encoding="utf-8")
    observations = tuple(
        _observation(
            case_id=case.id,
            task_id=case.task.task_id,
            edge_id=case.task.edge.id,
            answer=expected[case.id],
            evidence=evidence,
        )
        for case in catalog.cases
    )

    report = build_attachment_nested_transfer_report(
        inputs=(_reference("catalog", SELECTORS),),
        catalog=catalog,
        submission=submission,
        observations=observations,
    )

    assert report.outcome is AttachmentNestedTransferOutcome.SUPPORTED
    assert report.correct_count == 20
    assert report.accuracy == 1.0
    assert report.yes_recall == 1.0
    assert report.no_recall == 1.0
    assert report.actual_yes_count == 12
    assert report.actual_no_count == 8
    assert report.actual_unclear_count == 0
    assert report.invalid_output_count == 0
    assert report.input_blocked_count == 0
    assert report.model_failed_count == 0
    assert {item.group_kind.value for item in report.group_metrics} == {
        "document",
        "expected_label",
    }
    assert all(item.accuracy == 1.0 for item in report.group_metrics)
    assert report.accepted_ledger_change_count == 0


def _catalog() -> AttachmentNestedTransferCatalog:
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    source = json.loads(SOURCE_CATALOG.read_text(encoding="utf-8"))
    return build_attachment_nested_transfer_catalog(
        selector_catalog=selectors,
        source_catalog=source,
        inputs=(
            _reference("selectors", SELECTORS),
            _reference("source_catalog", SOURCE_CATALOG),
        ),
        prompt=_reference("prompt", PROMPT),
    )


def _submission(
    catalog: AttachmentNestedTransferCatalog,
) -> AttachmentNestedTransferSubmission:
    return AttachmentNestedTransferSubmission(
        reviewer="blind reviewer",
        decisions=tuple(
            AttachmentNestedTransferDecision(
                case_id=case.id,
                answer="Y" if index <= 12 else "N",
                rationale="The exact source decides this ownership.",
            )
            for index, case in enumerate(catalog.cases, start=1)
        ),
    )


def _observation(
    *,
    case_id: str,
    task_id: str,
    edge_id: str,
    answer: str,
    evidence: Path,
) -> AttachmentNestedTransferObservation:
    raw = answer.encode()
    typed_answer = AttachmentEdgeFilterAnswerValue(answer)
    decision = AttachmentEdgeFilterDecision(
        task_id=task_id,
        edge_id=edge_id,
        status=AttachmentEdgeFilterDecisionStatus.COMPLETE,
        answer=typed_answer,
        retained=typed_answer is AttachmentEdgeFilterAnswerValue.YES,
        unresolved=False,
        extraction_task_id="ext_fixture",
        model_run_id="mrun_fixture",
        trace_id="xtr_fixture",
        raw_output_sha256=hashlib.sha256(raw).hexdigest(),
        diagnostic_code=None,
    )
    return AttachmentNestedTransferObservation(
        case_id=case_id,
        decision=decision,
        execution_record=_reference(f"execution_{case_id}", evidence),
        exact_model_input="complete model input",
        raw_output_base64=b64encode(raw).decode(),
        model_identity_digest="a" * 64,
        elapsed_milliseconds=1,
        runtime_invoked=True,
    )


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    return AttachmentEvidenceReference(
        label=label,
        path=str(path.resolve()),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
