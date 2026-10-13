"""Application inspection operates with fake Ports and canonical model fixtures."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import cast

import pytest
from kotekomi_application.hybrid_document_orchestration import (
    HYBRID_STAGE_ORDER,
    HybridDocumentArchive,
    HybridDocumentLedger,
    HybridParagraphStageRecord,
    HybridStageDisposition,
    HybridStageId,
    build_hybrid_document_coverage_report,
    build_hybrid_paragraph_receipt,
    canonical_hybrid_document_coverage_report_bytes,
    canonical_hybrid_paragraph_receipt_bytes,
)
from kotekomi_application.ingestion_debug_summary import SnapshotOperation, build_debug_summary
from kotekomi_application.ingestion_inspection import (
    ArtifactHandle,
    HybridParagraphStageProgress,
    InspectionContext,
    ParagraphInput,
    ParagraphSnapshot,
    build_profile,
)
from kotekomi_application.ingestion_inspection_reader import (
    InspectionLedger,
    InspectParagraphInput,
    inspect_ingestion_paragraph,
)
from kotekomi_application.ingestion_observability import IngestionObservabilityArchive
from kotekomi_application.inspection_session import InspectionSession
from kotekomi_domain import (
    AnalysisRun,
    DocumentRepresentationBundle,
    IngestionChangeSet,
    IngestionRun,
)
from kotekomi_domain.models import JsonValue

from packages.application.tests.test_hybrid_document_orchestration import (
    _plan,  # pyright: ignore[reportPrivateUsage]
    _PlanningArchive,  # pyright: ignore[reportPrivateUsage]
    _PlanningLedger,  # pyright: ignore[reportPrivateUsage]
    _policy_input,  # pyright: ignore[reportPrivateUsage]
)
from packages.application.tests.test_hybrid_mention_preview import (
    FixtureArchive,
    FixtureLedger,
    FixtureModelRuntime,
    FixtureProposer,
    _run,  # pyright: ignore[reportPrivateUsage]
)
from packages.application.tests.test_ingestion_observability import (
    _complete_ledger,  # pyright: ignore[reportPrivateUsage]
)


def test_projection_and_session_use_effective_adjudication_and_cache_source() -> None:
    ledger = FixtureLedger(paragraph_text="Services had FedRAMP authorization.")
    archive = FixtureArchive()
    preview = _run(
        ledger,
        archive,
        FixtureProposer(proposal_spans=("FedRAMP authorization",)),
        FixtureModelRuntime(proposal_abstains=True, boundary_output=b"c1 | incomplete\n"),
    ).preview
    bundle = ledger.bundle
    node = next(n for n in bundle.nodes if n.id == preview.paragraph_node_id)
    text = next(v for v in bundle.text_views if v.id == node.text_view_id).text[
        node.start_char : node.end_char
    ]
    reads: list[str] = []

    class Source:
        def get_document_representation_bundle(
            self, record_id: str
        ) -> DocumentRepresentationBundle | None:
            reads.append(record_id)
            return ledger.get_document_representation_bundle(record_id)

    class Artifacts:
        def describe_stage(self, stage: HybridStageId, output_id: str) -> ArtifactHandle:
            raw = archive.read_hybrid_extraction_preview(output_id)
            return ArtifactHandle(
                stage.value,
                output_id,
                f"archive/previews/{output_id}.json",
                hashlib.sha256(raw).hexdigest(),
            )

    snapshots: list[ParagraphSnapshot] = []
    session = InspectionSession(
        Source(),
        artifacts_port=Artifacts(),
        on_snapshot=snapshots.append,
        context=InspectionContext("igr_fixture", "/local/state"),
    )
    session.on_stage_progress(
        HybridParagraphStageProgress(0, 1, bundle.representation.id, node.id, None, None, False)
    )
    assert snapshots[-1].profile.present_stages == frozenset()
    session.on_stage_progress(
        HybridParagraphStageProgress(
            0, 1, bundle.representation.id, node.id, HybridStageId.HP1_MENTIONS, preview, False
        )
    )
    profile = snapshots[-1].profile
    assert {m.span.text: m.selected for m in profile.mentions} == {
        "FedRAMP": True,
        "FedRAMP authorization": False,
    }
    assert profile.records[1].data["boundary_status"] == "incomplete"
    assert reads == [bundle.representation.id]
    direct = build_profile(
        text=text,
        representation_id=bundle.representation.id,
        paragraph_node_id=node.id,
        node_start_char=node.start_char,
        stage_outputs={"hp1_mentions": preview},
        bundle=bundle,
    )
    assert replace(profile, artifacts=()) == direct
    replayed: list[ParagraphSnapshot] = []
    replay = InspectionSession(Source(), on_snapshot=replayed.append)
    replay.replay_stored(
        (
            ParagraphInput(
                0,
                text,
                bundle.representation.id,
                node.id,
                node.start_char,
                "complete",
                (),
                {"hp1_mentions": preview},
                bundle,
            ),
        ),
        None,
    )
    assert replayed[-1].profile.records == direct.records
    captured = build_debug_summary(
        profile,
        ordinal=0,
        paragraph_status="processing",
        operation=SnapshotOperation(mode="ingestion", status="running"),
        visible_stages=profile.present_stages,
        selected_key="hp1_mentions:1",
        context=snapshots[-1].context,
    )
    assert captured.records["hp1_mentions"][1].related_ids
    assert captured.records["hp1_mentions"][1].trace_ids


class ScopedArchive(_PlanningArchive):
    def __init__(self) -> None:
        super().__init__()
        self.receipt_reads: list[str] = []
        self.previews: dict[str, bytes] = {}

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes:
        return self.previews[preview_id]

    def read_hybrid_paragraph_receipt(self, receipt_id: str) -> bytes:
        self.receipt_reads.append(receipt_id)
        return super().read_hybrid_paragraph_receipt(receipt_id)

    def find_hybrid_document_coverage_report_by_sha256(self, expected_sha256: str) -> str | None:
        return next(
            (
                k
                for k, v in self.reports.items()
                if hashlib.sha256(v).hexdigest() == expected_sha256
            ),
            None,
        )

    def ingestion_evidence_path(self, record_type: str, record_id: str) -> str:
        return f"extraction/{record_type}/{record_id}.json"

    def read_model_run_output(self, model_run_id: str) -> bytes:
        raise AssertionError("Scoped inspection must not read whole-run model payloads.")


class ScopedLedger(_PlanningLedger):
    run: IngestionRun
    analysis: AnalysisRun
    change_set: IngestionChangeSet

    def get_ingestion_run(self, record_id: str) -> IngestionRun | None:
        return self.run if record_id == self.run.id else None

    def get_analysis_run(self, record_id: str) -> AnalysisRun | None:
        return self.analysis if record_id == self.analysis.id else None

    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None:
        return self.change_set if record_id == self.change_set.id else None


def closed_fixture() -> tuple[ScopedLedger, ScopedArchive]:
    import json

    ledger, archive = ScopedLedger(), ScopedArchive()
    plan = _plan(_policy_input(), ledger, archive)
    from kotekomi_application.hybrid_mention_interpretation import (
        canonical_hybrid_extraction_preview_bytes,
    )

    from packages.application.tests.test_hybrid_document_references import (
        _parent_preview,  # pyright: ignore[reportPrivateUsage]
    )

    for work in plan.manifest.work_items:
        preview = _parent_preview(
            ledger.bundle,
            paragraph_index=next(
                i
                for i, n in enumerate(n for n in ledger.bundle.nodes if n.node_type == "paragraph")
                if n.id == work.paragraph_node_id
            ),
            candidate_texts=(),
        )
        raw = canonical_hybrid_extraction_preview_bytes(preview)
        archive.previews[preview.id] = raw
        receipt = build_hybrid_paragraph_receipt(
            manifest=plan.manifest,
            work=work,
            context_manifest_id=preview.context_manifest_id,
            stages=(
                HybridParagraphStageRecord(
                    stage_id=HybridStageId.HP1_MENTIONS,
                    disposition=HybridStageDisposition.CREATED,
                    output_id=preview.id,
                    output_sha256=hashlib.sha256(raw).hexdigest(),
                    terminal_status="complete",
                ),
            )
            + tuple(
                HybridParagraphStageRecord(
                    stage_id=s,
                    disposition=HybridStageDisposition.NOT_RUN,
                    diagnostics=("fixture_blocked",),
                )
                for s in HYBRID_STAGE_ORDER[1:]
            ),
        )
        archive.receipts[receipt.id] = canonical_hybrid_paragraph_receipt_bytes(receipt)
    report = build_hybrid_document_coverage_report(
        manifest=plan.manifest,
        ledger=cast(HybridDocumentLedger, ledger),
        archive=cast(HybridDocumentArchive, archive),
    )
    base = _complete_ledger("a" * 64)
    assert base.analysis and base.change_set
    ledger.analysis = AnalysisRun.model_validate_json(
        base.analysis.model_copy(
            update={
                "document_id": ledger.bundle.representation.document_id,
                "representation_id": ledger.bundle.representation.id,
            }
        ).model_dump_json()
    )
    data: dict[str, JsonValue] = {
        "ingestion_run_id": base.runs[0].id,
        "analysis_run_id": ledger.analysis.id,
        "representation_id": ledger.bundle.representation.id,
        "coverage_report_digest": hashlib.sha256(
            canonical_hybrid_document_coverage_report_bytes(report)
        ).hexdigest(),
        "proposed_change_ids": [],
        "analysis_origin": "executed",
    }
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    ledger.change_set = IngestionChangeSet.model_validate_json(
        json.dumps(
            {
                **base.change_set.model_dump(mode="json"),
                **data,
                "id": f"ics_{digest[:24]}",
                "change_set_digest": digest,
            }
        )
    )
    ledger.run = IngestionRun.model_validate_json(
        base.runs[0]
        .model_copy(
            update={
                "document_id": ledger.analysis.document_id,
                "representation_id": ledger.analysis.representation_id,
                "ingestion_change_set_id": ledger.change_set.id,
            }
        )
        .model_dump_json()
    )
    archive.receipt_reads.clear()
    return ledger, archive


def test_paragraph_lookup_reads_only_selected_receipt_and_preserves_not_run() -> None:
    ledger, archive = closed_fixture()
    result = inspect_ingestion_paragraph(
        InspectParagraphInput(
            ingestion_run_id=ledger.run.id, paragraph_node_id="nod_first", state_root="/local/state"
        ),
        cast(InspectionLedger, ledger),
        cast(IngestionObservabilityArchive, archive),
    )
    assert result.summary is not None
    assert result.summary.phases[0].status == "complete"
    assert all(p.status == "not run" and p.diagnostic_count == 1 for p in result.summary.phases[1:])
    assert len(set(archive.receipt_reads)) == 1
    assert result.summary.context and result.summary.context.receipt_id == archive.receipt_reads[0]


@pytest.mark.parametrize("failure", ["run", "node", "digest", "receipt"])
def test_narrow_lookup_rejects_missing_and_tampered_evidence(failure: str) -> None:
    ledger, archive = closed_fixture()
    run_id, node_id = ledger.run.id, "nod_first"
    if failure == "run":
        run_id = "missing"
    elif failure == "node":
        node_id = "missing"
    elif failure == "digest":
        ledger.change_set = ledger.change_set.model_copy(update={"change_set_digest": "b" * 64})
    else:
        key = next(iter(archive.receipts))
        archive.receipts[key] += b" "
    with pytest.raises(ValueError):
        inspect_ingestion_paragraph(
            InspectParagraphInput(
                ingestion_run_id=run_id, paragraph_node_id=node_id, state_root="/local/state"
            ),
            cast(InspectionLedger, ledger),
            cast(IngestionObservabilityArchive, archive),
        )


def test_trump_jr_handoff_preserves_debugging_content_under_six_kib() -> None:
    from pathlib import Path

    from kotekomi_application.ingestion_debug_summary import DebugSummary
    from kotekomi_application.ingestion_inspection import (
        STAGE_ORDER,
        InspectionRecord,
        ParagraphAnnotationProfile,
        Span,
    )

    sample = DebugSummary.model_validate_json(
        (
            Path(__file__).parent / "fixtures/ingestion_inspection/trump_jr_summary_v2.json"
        ).read_text()
    )
    records = tuple(
        InspectionRecord(
            f"{stage}:{index}",
            stage,
            row.record_id,
            row.record_type,
            tuple(
                Span(*sample.spans[s], sample.source.text[sample.spans[s][0] : sample.spans[s][1]])
                for s in row.spans
            ),
            row.data,
            row.related_ids,
            row.trace_ids,
        )
        for stage, rows in sample.records.items()
        for index, row in enumerate(rows)
    )
    profile = ParagraphAnnotationProfile(
        text=sample.source.text,
        representation_id=sample.source.representation_id,
        paragraph_node_id=sample.source.paragraph_node_id,
        node_start_char=sample.source.node_start_char,
        text_view_id=sample.source.text_view_id,
        segments=(),
        mentions=(),
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        standing_facts=(),
        present_stages=frozenset(STAGE_ORDER),
        records=records,
        artifacts=sample.artifacts,
        stage_statuses=tuple((p.stage, p.status) for p in sample.phases),
    )
    selected = next(r.key for r in records if r.record_id == sample.selected_record_id)
    captured = build_debug_summary(
        profile,
        ordinal=sample.paragraph_ordinal,
        paragraph_status=sample.paragraph_status,
        operation=sample.operation,
        visible_stages=STAGE_ORDER,
        selected_key=selected,
        context=sample.context,
    )
    payload = captured.clipboard_json()
    assert len(sample.clipboard_json().encode()) < 6 * 1024
    assert len(payload.encode()) < 6 * 1024
    assert payload.count(sample.source.text) == 1
    assert len(captured.records["hp1_mentions"]) == 6
    by_text = {
        sample.source.text[captured.spans[r.spans[0]][0] : captured.spans[r.spans[0]][1]]: r.data
        for r in captured.records["hp1_mentions"]
    }
    assert by_text["Donald Trump"]["effective_selected"] is True
    assert by_text["Donald Trump Jr."]["effective_selected"] is True
    assert by_text["Trump Jr"]["boundary_status"] == "incomplete"
    assert by_text["Trump Jr"]["effective_selected"] is False
    facts = captured.records["hp10_standing_facts"]
    assert all(r.data["disposition"] == "held" and r.data["reason_codes"] for r in facts)
    assert facts[1].related_ids and facts[1].trace_ids
    assert len(captured.artifacts) == 7


@pytest.mark.parametrize("failure", ["none", "digest", "record", "trace", "node"])
def test_explicit_artifact_lookup_before_run_closure(failure: str) -> None:
    from packages.application.tests.test_ingestion_observability import (
        _running,  # pyright: ignore[reportPrivateUsage]
    )

    ledger = FixtureLedger()
    archive = FixtureArchive()
    preview = _run(ledger, archive, FixtureProposer(), FixtureModelRuntime()).preview
    run = _running("igr_fixture")

    class Ledger:
        def get_ingestion_run(self, record_id: str) -> IngestionRun | None:
            return run if record_id == run.id else None

        def get_document_representation_bundle(self, record_id: str):
            return ledger.get_document_representation_bundle(record_id)

    raw = archive.previews[preview.id]
    record_id = preview.candidates[0].id
    arguments = InspectParagraphInput(
        ingestion_run_id=run.id,
        paragraph_node_id=preview.paragraph_node_id,
        state_root="/local/state",
        phase=HybridStageId.HP1_MENTIONS,
        artifact_id=preview.id,
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        record_id=record_id,
    )
    if failure == "none":
        result = inspect_ingestion_paragraph(
            arguments,
            cast(InspectionLedger, Ledger()),
            cast(IngestionObservabilityArchive, archive),
        )
        assert (
            result.binding == "explicit_artifact"
            and result.evidence
            and result.evidence["id"] == record_id
        )
        return
    if failure == "digest":
        arguments = arguments.model_copy(update={"artifact_sha256": "a" * 64})
    elif failure == "node":
        arguments = arguments.model_copy(update={"paragraph_node_id": "missing"})
    elif failure == "record":
        arguments = arguments.model_copy(update={"record_id": "missing"})
    else:
        arguments = arguments.model_copy(update={"record_id": None, "trace_id": "missing"})
    with pytest.raises(ValueError):
        inspect_ingestion_paragraph(
            arguments,
            cast(InspectionLedger, Ledger()),
            cast(IngestionObservabilityArchive, archive),
        )


def test_not_run_phase_lookup_returns_receipt_diagnostics_and_matches_replay() -> None:
    ledger, archive = closed_fixture()
    input = InspectParagraphInput(
        ingestion_run_id=ledger.run.id, paragraph_node_id="nod_first", state_root="/local/state"
    )
    result = inspect_ingestion_paragraph(
        input.model_copy(update={"phase": HybridStageId.HP2_REFERENCES}),
        cast(InspectionLedger, ledger),
        cast(IngestionObservabilityArchive, archive),
    )
    assert result.evidence and result.evidence["disposition"] == "not_run"
    assert result.evidence["diagnostics"] == ["fixture_blocked"]
    from kotekomi_application.ingestion_inspection_reader import load_inspection_paragraph

    paragraph = load_inspection_paragraph(
        input, cast(InspectionLedger, ledger), cast(IngestionObservabilityArchive, archive)
    )
    snapshots: list[ParagraphSnapshot] = []
    session = InspectionSession(ledger, on_snapshot=snapshots.append)
    session.replay_stored((paragraph,), None)
    snapshot = snapshots[-1]
    assert dict(snapshot.profile.phase_diagnostics)["hp2_references"] == ("fixture_blocked",)
