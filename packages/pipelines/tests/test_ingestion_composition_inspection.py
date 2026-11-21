"""Current saved Composition outcomes for one retained IngestionRun.

The portable IPI capture supplies a real retained run with 24 realized Events.
The fixture adds one explicit gap paragraph by reusing its captured HP-1 preview
and marking the later stages not run. The composed outcome comes from the
supported review and recomposition path; the held and missing outcomes are
disposable test state. No workstation database, fresh ingestion, or model call is
used, so the acceptance case runs in a clean checkout.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionRecord,
    EventCompositionStatus,
    EventConstructionDecisionInput,
)
from kotekomi_application.hybrid_document_orchestration import (
    HYBRID_STAGE_ORDER,
    HybridDocumentCoverageRecord,
    HybridDocumentCoverageReport,
    HybridParagraphReceipt,
    HybridParagraphStageRecord,
    HybridParagraphStatus,
    HybridStageDisposition,
    canonical_hybrid_document_coverage_report_bytes,
    canonical_hybrid_paragraph_receipt_bytes,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
)
from kotekomi_application.ingestion_inspection import build_profile
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    IdentityOccurrenceKind,
    IngestionChangeSet,
    IngestionRun,
    IngestionRunStatus,
    SourceAuthority,
)
from kotekomi_pipelines import cli
from kotekomi_pipelines.event_review_workflow import record_review_decision
from kotekomi_pipelines.ingestion_composition_inspection import (
    InspectCompositionOutcomesInput,
    InspectCompositionOutcomesResult,
    _resolve_outcome,
    inspect_composition_outcomes,
    realized_event_evidence,
)
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

from packages.pipelines.tests.test_ipi_production_promotion import RUN, _seed_capture
from packages.pipelines.tests.test_operator_journey import NOW, Journey

PORTABLE_RUN = "igr_portable_composition_inspection"
GAP_NODE = "nod_f1e64380625a2f2c533fc277_0015"
GAP_ORDINAL = 2
COMPOSED_EVENT = "sge_c0ff4b58ad8962717514c9f3"
HELD_EVENT = "sge_e8d444a0222b3344ab28d1d8"
MISSING_EVENT = "sge_513e3aa24329a73b89ee4f94"
EXPECTED_EVENTS = 24
EXPECTED_HELD = 22
ANNOUNCEMENT_FIXTURE = Path(__file__).parent / "fixtures" / "announcement"
ANNOUNCEMENT_RECEIPT = (
    ANNOUNCEMENT_FIXTURE
    / "archive"
    / "extraction"
    / "paragraph-receipts"
    / "hpr_0d67ab86a42ca5eff27856d3.json"
)
ANNOUNCEMENT_HP1 = (
    ANNOUNCEMENT_FIXTURE
    / "archive"
    / "extraction"
    / "previews"
    / "hxp_05c8252319a8ac6a02acce11.json"
)


@dataclass(frozen=True)
class _Event:
    event_id: str
    paragraph_ordinal: int
    source_text_sha256: str


class _JsonRow(TypedDict):
    event_id: str
    status: str
    paragraphs: list[int]
    hold_reason: str | None
    diagnostic: str | None


class _JsonPayload(TypedDict):
    ingestion_run_id: str
    total_events: int
    counts: dict[str, int]
    events: list[_JsonRow]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _row_locations(paragraphs: tuple[int, ...]) -> str:
    return (
        f"paragraph {paragraphs[0]}"
        if len(paragraphs) == 1
        else "paragraphs " + ",".join(str(item) for item in paragraphs)
    )


def _text_rows(text: str) -> list[tuple[str, str, str]]:
    lines = text.splitlines()
    start = lines.index("Events:") + 1
    rows: list[tuple[str, str, str]] = []
    for line in lines[start:]:
        status, locations, event_id = line.split("\t")[:3]
        rows.append((status, locations, event_id))
    return rows


def _json_rows(payload: _JsonPayload) -> list[tuple[str, str, str]]:
    return [
        (event["status"], _row_locations(tuple(event["paragraphs"])), event["event_id"])
        for event in payload["events"]
    ]


def _run_cli(config: Path, run_id: str, output_format: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(
            [
                "--config",
                str(config),
                "ingestions",
                "composition",
                run_id,
                "--format",
                output_format,
            ]
        )
    return code, out.getvalue(), err.getvalue()


def _portable_journey(tmp_path: Path) -> Journey:
    journey = Journey(tmp_path)
    journey.prepare()
    _seed_capture(journey)
    _add_gap_paragraph(journey, LocalArchiveStore(journey.archive))
    journey.run_id = PORTABLE_RUN
    return journey


def _add_gap_paragraph(journey: Journey, archive: LocalArchiveStore) -> None:
    """Add one explicit gap paragraph with captured HP-1 evidence and later stages off."""
    with sqlite_ledger_transaction(journey.ledger) as ledger:
        run = ledger.get_ingestion_run(RUN)
        assert run is not None and run.ingestion_change_set_id is not None
        change_set = ledger.get_ingestion_change_set(run.ingestion_change_set_id)
        assert change_set is not None
        report_id = archive.find_hybrid_document_coverage_report_by_sha256(
            change_set.coverage_report_digest
        )
        assert report_id is not None
        report = hybrid_document_coverage_report_from_bytes(
            archive.read_hybrid_document_coverage_report(report_id)
        )
        manifest_raw = archive.read_hybrid_pipeline_policy_manifest(report.policy_manifest_id)
    manifest = hybrid_pipeline_policy_manifest_from_bytes(manifest_raw)
    work = next(item for item in manifest.work_items if item.paragraph_node_id == GAP_NODE)
    announcement = hybrid_paragraph_receipt_from_bytes(ANNOUNCEMENT_RECEIPT.read_bytes())
    hp1 = announcement.stages[0]
    shutil.copyfile(
        ANNOUNCEMENT_HP1,
        journey.archive / "extraction" / "previews" / ANNOUNCEMENT_HP1.name,
    )
    reason = "portable_fixture:no_event_paragraph"
    receipt = HybridParagraphReceipt(
        id=f"hpr_{work.input_fingerprint[:24]}",
        policy_manifest_id=manifest.id,
        policy_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        analysis_unit_id=work.analysis_unit_id,
        input_fingerprint=work.input_fingerprint,
        context_manifest_id=announcement.context_manifest_id,
        status=HybridParagraphStatus.GAP,
        stages=(
            hp1,
            *(
                HybridParagraphStageRecord(
                    stage_id=stage,
                    disposition=HybridStageDisposition.NOT_RUN,
                    diagnostics=("portable_fixture:stage_not_run",),
                )
                for stage in HYBRID_STAGE_ORDER[1:]
            ),
        ),
        gap_reasons=(reason,),
    )
    receipt_bytes = canonical_hybrid_paragraph_receipt_bytes(receipt)
    receipt_digest = hashlib.sha256(receipt_bytes).hexdigest()
    archive.put_hybrid_paragraph_receipt(receipt, receipt_bytes, receipt_digest)
    records = (
        *report.records,
        HybridDocumentCoverageRecord(
            ordinal=len(report.records),
            paragraph_node_id=work.paragraph_node_id,
            input_fingerprint=work.input_fingerprint,
            receipt_id=receipt.id,
            receipt_sha256=receipt_digest,
            status=HybridParagraphStatus.GAP,
            gap_reasons=(reason,),
        ),
    )
    report_data: dict[str, object] = report.model_dump(mode="json")
    report_data["records"] = [item.model_dump(mode="json") for item in records]
    report_data["required_paragraph_count"] = len(records)
    report_data["complete_paragraph_count"] = 0
    report_data["gap_paragraph_count"] = len(records)
    report_data["status"] = "complete_with_gaps"
    report_data.pop("id")
    report_data["id"] = "hdc_" + hashlib.sha256(_canonical(report_data).encode()).hexdigest()[:24]
    gap_report = HybridDocumentCoverageReport.model_validate_json(json.dumps(report_data))
    report_bytes = canonical_hybrid_document_coverage_report_bytes(gap_report)
    report_digest = hashlib.sha256(report_bytes).hexdigest()
    archive.put_hybrid_document_coverage_report(gap_report, report_bytes, report_digest)
    _create_portable_run(
        journey,
        run=run,
        change_set=change_set,
        report_digest=report_digest,
    )


def _create_portable_run(
    journey: Journey,
    *,
    run: IngestionRun,
    change_set: IngestionChangeSet,
    report_digest: str,
) -> None:
    """Create one captured run over the two real paragraphs plus the gap paragraph."""
    with sqlite_ledger_transaction(journey.ledger) as ledger:
        payload = {
            "ingestion_run_id": PORTABLE_RUN,
            "analysis_run_id": change_set.analysis_run_id,
            "representation_id": change_set.representation_id,
            "coverage_report_digest": report_digest,
            "proposed_change_ids": list(change_set.proposed_change_ids),
            "analysis_origin": change_set.analysis_origin.value,
        }
        digest = hashlib.sha256(_canonical(payload).encode()).hexdigest()
        new_change_set = IngestionChangeSet(
            id=f"ics_{digest[:24]}",
            ingestion_run_id=PORTABLE_RUN,
            analysis_run_id=change_set.analysis_run_id,
            representation_id=change_set.representation_id,
            coverage_report_digest=report_digest,
            proposed_change_ids=change_set.proposed_change_ids,
            analysis_origin=change_set.analysis_origin,
            closed_at=change_set.closed_at,
            change_set_digest=digest,
        )
        ledger.create_ingestion_run(
            IngestionRun(
                id=PORTABLE_RUN,
                requested_path=run.requested_path,
                display_filename=run.display_filename,
                requested_source_url=run.requested_source_url,
                status=IngestionRunStatus.RUNNING,
                started_at=run.started_at,
            )
        )
        ledger.save_ingestion_change_set(new_change_set)
        terminal = IngestionRun(
            id=PORTABLE_RUN,
            requested_path=run.requested_path,
            display_filename=run.display_filename,
            requested_source_url=run.requested_source_url,
            normalized_source_url=run.normalized_source_url,
            status=IngestionRunStatus.CAPTURED,
            started_at=run.started_at,
            completed_at=run.completed_at,
            source_id=run.source_id,
            document_id=run.document_id,
            representation_id=run.representation_id,
            provenance_activity_id=run.provenance_activity_id,
            analysis_run_id=run.analysis_run_id,
            ingestion_change_set_id=new_change_set.id,
        )
        assert ledger.complete_ingestion_run_if_running(terminal)


def _event_evidence(journey: Journey) -> tuple[list[int], list[_Event]]:
    paragraphs = load_paragraph_inputs(
        journey.ledger, journey.archive, ingestion_run_id=journey.run_id
    )
    counts: list[int] = []
    events: list[_Event] = []
    for paragraph in paragraphs:
        profile = build_profile(
            text=paragraph.text,
            representation_id=paragraph.representation_id,
            paragraph_node_id=paragraph.paragraph_node_id,
            node_start_char=paragraph.node_start_char,
            stage_outputs=paragraph.stage_outputs,
            bundle=paragraph.bundle,
        )
        counts.append(len(profile.events))
        digest = hashlib.sha256(paragraph.text.encode()).hexdigest()
        events.extend(_Event(event.event_id, paragraph.ordinal, digest) for event in profile.events)
    return counts, events


def _compose_established(journey: Journey) -> None:
    """Create one valid composed outcome through the supported review path."""
    journey.event_id = COMPOSED_EVENT
    packet = journey.packet()
    candidate = next(
        item for item in packet.candidates if item.exact_text == "Department  of  Defense"
    )
    record_review_decision(
        ledger_path=journey.ledger,
        archive_path=journey.archive,
        ingestion_run_id=journey.run_id,
        event_id=COMPOSED_EVENT,
        now=NOW,
        decision=EventConstructionDecisionInput(
            candidate_start=candidate.start,
            candidate_end=candidate.end,
            exact_text=candidate.exact_text,
            identity_kind=IdentityOccurrenceKind.ORGANIZATION,
            identity_decision="new_identity",
            existing_identity_id=None,
            identity_name=candidate.identity_name,
            predicate="established",
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
            reviewer="portable-composition-inspection",
        ),
    )
    assert journey.recompose().status is EventCompositionStatus.COMPOSED


def _save_held(store: CompositionOutcomeStore, event: _Event) -> None:
    store.save(
        EventCompositionRecord(
            event_id=event.event_id,
            source_text_sha256=event.source_text_sha256,
            status=EventCompositionStatus.HELD,
            hold_reason="assertion_inputs_unavailable",
        )
    )


def test_portable_mixed_outcomes_are_reported(tmp_path: Path) -> None:
    """A clean-checkout retained run shows composed, held, missing, and no-Event evidence."""
    journey = _portable_journey(tmp_path)
    counts, events = _event_evidence(journey)
    assert counts == [8, 16, 0]
    assert len(events) == EXPECTED_EVENTS
    assert all(event.paragraph_ordinal != GAP_ORDINAL for event in events)

    _compose_established(journey)
    store = CompositionOutcomeStore(journey.state / "composition-outcomes")
    for event in events:
        if event.event_id not in {COMPOSED_EVENT, MISSING_EVENT}:
            _save_held(store, event)

    code, text, err = _run_cli(journey.config, journey.run_id, "text")
    assert (code, err) == (0, "")
    assert "Composed: 1" in text
    assert f"Held: {EXPECTED_HELD}" in text
    assert "Missing: 1" in text
    assert "Invalid: 0" in text
    assert f"composed\tparagraph 1\t{COMPOSED_EVENT}" in text
    assert f"held\tparagraph 2\t{HELD_EVENT}\thold: assertion_inputs_unavailable" in text
    assert f"missing\tparagraph 2\t{MISSING_EVENT}" in text
    assert "paragraph 3" not in text
    assert "United States Department" not in text

    code, payload_text, err = _run_cli(journey.config, journey.run_id, "json")
    assert (code, err) == (0, "")
    payload = cast(_JsonPayload, json.loads(payload_text))
    assert payload["ingestion_run_id"] == PORTABLE_RUN
    assert payload["total_events"] == EXPECTED_EVENTS
    assert payload["counts"] == {
        "composed": 1,
        "held": EXPECTED_HELD,
        "missing": 1,
        "invalid": 0,
    }
    assert _text_rows(text) == _json_rows(payload)
    by_id = {row["event_id"]: row for row in payload["events"]}
    assert (by_id[COMPOSED_EVENT]["status"], by_id[COMPOSED_EVENT]["paragraphs"]) == (
        "composed",
        [1],
    )
    assert (by_id[HELD_EVENT]["status"], by_id[HELD_EVENT]["paragraphs"]) == ("held", [2])
    assert by_id[HELD_EVENT]["hold_reason"] == "assertion_inputs_unavailable"
    assert (by_id[MISSING_EVENT]["status"], by_id[MISSING_EVENT]["paragraphs"]) == (
        "missing",
        [2],
    )
    assert all(3 not in row["paragraphs"] for row in payload["events"])


def test_portable_invalid_evidence_is_actionable_and_not_repaired(tmp_path: Path) -> None:
    """Malformed and mismatched portable evidence is invalid; unrelated files are ignored."""
    journey = _portable_journey(tmp_path)
    _, events = _event_evidence(journey)
    malformed_event, mismatched_event = events[0], events[1]
    outcomes = journey.state / "composition-outcomes"
    outcomes.mkdir(parents=True)
    malformed = outcomes / f"{malformed_event.event_id}.json"
    malformed.write_text("{not a composition record", encoding="utf-8")
    mismatched = outcomes / f"{mismatched_event.event_id}.json"
    CompositionOutcomeStore(outcomes).save(
        EventCompositionRecord(
            event_id=mismatched_event.event_id,
            source_text_sha256="0" * 64,
            status=EventCompositionStatus.HELD,
            hold_reason="assertion_inputs_unavailable",
        )
    )
    unrelated = outcomes / "unrelated.json"
    unrelated.write_text("{not a composition record", encoding="utf-8")
    malformed_before = malformed.read_bytes()
    mismatched_before = mismatched.read_bytes()
    unrelated_before = unrelated.read_bytes()

    code, text, err = _run_cli(journey.config, journey.run_id, "text")
    assert (code, err) == (1, "")
    assert "Composed: 0" in text
    assert "Held: 0" in text
    assert "Missing: 22" in text
    assert "Invalid: 2" in text
    assert (
        f"invalid\tparagraph 1\t{malformed_event.event_id}\tdiagnostic: outcome is malformed"
    ) in text
    assert (
        f"invalid\tparagraph 1\t{mismatched_event.event_id}\t"
        "diagnostic: source text digest differs from the paragraph"
    ) in text
    assert "unrelated" not in text

    code, payload_text, err = _run_cli(journey.config, journey.run_id, "json")
    assert (code, err) == (1, "")
    payload = cast(_JsonPayload, json.loads(payload_text))
    assert payload["counts"] == {
        "composed": 0,
        "held": 0,
        "missing": 22,
        "invalid": 2,
    }
    assert _text_rows(text) == _json_rows(payload)
    assert malformed.read_bytes() == malformed_before
    assert mismatched.read_bytes() == mismatched_before
    assert unrelated.read_bytes() == unrelated_before
    assert not (outcomes / f"{MISSING_EVENT}.json").exists()


def test_portable_newer_saved_outcome_is_reported_as_current(tmp_path: Path) -> None:
    """A later saved outcome replaces the earlier result without historical claims."""
    journey = _portable_journey(tmp_path)
    _compose_established(journey)
    store = CompositionOutcomeStore(journey.state / "composition-outcomes")
    current = store.load(COMPOSED_EVENT)
    store.save(
        EventCompositionRecord(
            event_id=current.event_id,
            source_text_sha256=current.source_text_sha256,
            status=EventCompositionStatus.HELD,
            hold_reason="selection_gap",
        )
    )

    result = inspect_composition_outcomes(
        InspectCompositionOutcomesInput(
            ledger_path=journey.ledger,
            archive_path=journey.archive,
            ingestion_run_id=journey.run_id,
        )
    )
    row = {item.event_id: item for item in result.rows}[COMPOSED_EVENT]
    assert row.status == "held"
    assert row.hold_reason == "selection_gap"
    assert result.counts == {"composed": 0, "held": 1, "missing": 23, "invalid": 0}


def test_realized_events_count_once_per_paragraph_evidence() -> None:
    """Repeated occurrences do not inflate the denominator or merge conflicts."""
    evidence = realized_event_evidence(
        (
            (1, "a" * 64, ("sge_repeat",)),
            (1, "a" * 64, ("sge_repeat",)),
            (2, "b" * 64, ("sge_repeat",)),
        )
    )

    assert evidence == {"sge_repeat": ((1, "a" * 64), (2, "b" * 64))}


def test_unreadable_outcome_is_invalid() -> None:
    """An unreadable matching file is invalid, not a saved or missing outcome."""

    def load(_event_id: str) -> EventCompositionRecord:
        raise OSError("fixture read failure")

    row = _resolve_outcome(
        event_id="sge_unreadable",
        evidence=((1, "a" * 64),),
        load=load,
    )

    assert row.status == "invalid"
    assert row.diagnostic == "outcome is unreadable"


def test_conflicting_paragraph_evidence_is_invalid_not_deduplicated() -> None:
    """A conflicting Event location is actionable and never silently chosen."""

    def load(_event_id: str) -> EventCompositionRecord:
        raise AssertionError("conflicting evidence must not read one saved outcome")

    row = _resolve_outcome(
        event_id="sge_conflict",
        evidence=((1, "a" * 64), (2, "b" * 64)),
        load=load,
    )

    assert row.status == "invalid"
    assert row.paragraphs == (1, 2)
    assert row.diagnostic == "conflicting paragraph evidence"


def test_zero_events_does_not_claim_completed_composition() -> None:
    """Zero realized Events is reported as zero, not as completion."""
    result = InspectCompositionOutcomesResult(
        ingestion_run_id="igr_empty",
        total_events=0,
        counts={"composed": 0, "held": 0, "missing": 0, "invalid": 0},
        rows=(),
    )

    text = cli._composition_inspection_text(result)

    assert "Realized Events: 0" in text
    assert "Events: none" in text
    assert "complete" not in text.lower()
