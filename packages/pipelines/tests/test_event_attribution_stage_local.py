"""Deterministic model-free Event attribution submission stage tests (D5/D6).

Covers the D5 manifest/loader/composition contract and the D6 pinned-resolver and
fixture-backed submission contract: strict manifest validation, wiring-input
reconstruction, fast-fail resolution, and a pending reviewed ``ProposedChange`` plus its
``ProvenanceActivity`` with idempotent resubmission.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import BuildIdentity, processing_task_fingerprint
from kotekomi_domain import (
    Actor,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ParseQualityReport,
    RawBlob,
    RepresentationAnalyzability,
    ReviewStatus,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.event_attribution_stage_local import (
    compose_event_attribution_wiring_input,
    load_event_attribution_manifest,
    submit_event_attribution,
)
from pydantic import ValidationError

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "event_attribution_submission_v1.json"

_SUPPORT = "etg_" + "e" * 24
_SOURCE_ID = "src_article_a"
_DOCUMENT_ID = "doc_article_a"
_ATTRIBUTED_TO_ID = "act_sacks"
_ASSERTION_ID = "ast_wiring_01"
_TEXT = "Alpha. Alpha."
_NOW = datetime(2026, 9, 23, 0, 0, tzinfo=UTC)


def test_manifest_fixture_loads_strictly_and_composes_wiring_input() -> None:
    manifest = load_event_attribution_manifest(FIXTURE_PATH)

    assert manifest.schema_version == "event_attribution_submission_v1"
    assert manifest.attributed_to_id == _ATTRIBUTED_TO_ID
    assert manifest.support_validation_attempt_id == "eva_support_01"
    assert manifest.proposer == "analyst"
    assert manifest.document_id == _DOCUMENT_ID
    assert manifest.model_name == "fixture-model"
    assert manifest.prompt_id == "prompt_fixture_01"

    wiring_input = compose_event_attribution_wiring_input(manifest)
    assert wiring_input.source_text == manifest.source_text
    assert wiring_input.event == manifest.event
    assert wiring_input.trigger == manifest.trigger
    assert wiring_input.semantic_draft == manifest.semantic_draft
    assert wiring_input.attribution_target == manifest.attribution_target
    assert wiring_input.source_id == _SOURCE_ID
    assert wiring_input.support_evidence_target_id == _SUPPORT
    assert wiring_input.assertion_id == _ASSERTION_ID
    assert wiring_input.evidence_assertion_id == "ast_evidence_01"
    assert wiring_input.rationale is not None
    assert wiring_input.confidence is not None
    assert wiring_input.support_decision_id is not None
    assert wiring_input.support_judgment_id is not None
    assert wiring_input.nli_observation_id is not None
    assert wiring_input.occurred_at is not None


def test_manifest_rejects_unknown_field(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["unexpected_field"] = "intruder"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_event_attribution_manifest(path)


def test_manifest_rejects_both_object_entity_and_object_value(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["object_entity_id"] = "act_object"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_event_attribution_manifest(path)


def test_pinned_resolver_fails_fast_when_actor_missing(tmp_path: Path) -> None:
    ledger_path = _seed_ledger(tmp_path, include_actor=False)
    manifest = load_event_attribution_manifest(FIXTURE_PATH)

    with sqlite_ledger_transaction(ledger_path) as ledger:
        with pytest.raises(ValueError, match="missing from the Ledger"):
            submit_event_attribution(manifest=manifest, ledger=ledger)


def test_submit_writes_pending_change_and_provenance_and_is_idempotent(
    tmp_path: Path,
) -> None:
    ledger_path = _seed_ledger(tmp_path, include_actor=True)
    manifest = load_event_attribution_manifest(FIXTURE_PATH)

    with sqlite_ledger_transaction(ledger_path) as ledger:
        result = submit_event_attribution(manifest=manifest, ledger=ledger)

        assert result.status == "pending"
        assert result.wiring_status.value == "constructed"
        assert result.assertion_id == _ASSERTION_ID
        assert result.proposed_change_id is not None
        assert result.provenance_activity_id is not None

        change = ledger.get_proposed_change(result.proposed_change_id)
        assert change is not None
        assert change.review_status is ReviewStatus.PENDING
        assert change.proposed_json["record_type"] == "Assertion"
        assert change.proposed_json["stable_label"] == _ASSERTION_ID
        assert change.source_id == _SOURCE_ID
        assert change.document_id == _DOCUMENT_ID

        activity = ledger.get_provenance_activity(result.provenance_activity_id)
        assert activity is not None
        assert activity.activity_type == "attributed_statement_proposed"
        assert activity.agent == "analyst"
        assert activity.output_ids == (result.proposed_change_id,)

    with sqlite_ledger_transaction(ledger_path) as ledger:
        repeated = submit_event_attribution(manifest=manifest, ledger=ledger)

        assert repeated.status == "pending"
        assert repeated.proposed_change_id == result.proposed_change_id
        assert repeated.provenance_activity_id == result.provenance_activity_id


def test_cli_submit_attribution_writes_pending_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger_path = _seed_ledger(tmp_path, include_actor=True)

    exit_code = main(
        [
            "submit-attribution",
            "--manifest",
            str(FIXTURE_PATH),
            "--ledger-path",
            str(ledger_path),
            "--format",
            "json",
        ]
    )
    captured = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["status"] == "pending"
    assert captured["wiring_status"] == "constructed"
    assert captured["proposed_change_id"] is not None
    assert captured["provenance_activity_id"] is not None
    assert captured["failure"] is None


def test_cli_submit_attribution_reports_missing_actor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger_path = _seed_ledger(tmp_path, include_actor=False)

    exit_code = main(
        [
            "submit-attribution",
            "--manifest",
            str(FIXTURE_PATH),
            "--ledger-path",
            str(ledger_path),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "missing from the Ledger" in captured.err


def _seed_ledger(tmp_path: Path, *, include_actor: bool) -> Path:
    ledger_path = tmp_path / "ledger.sqlite"
    SQLiteLedgerInitializer(ledger_path).initialize()

    bundle, evidence_target, validation_attempt = _evidence_records()

    with sqlite_ledger_transaction(ledger_path) as ledger:
        if include_actor:
            ledger.save_actor(Actor(id=_ATTRIBUTED_TO_ID, name="Sacks"))
        ledger.save_source(
            Source(
                id=_SOURCE_ID,
                source_type=SourceType.ARTICLE,
                identity_policy_id="pol_article",
                canonical_identity_key="key_article",
            )
        )
        ledger.save_document(
            Document(id=_DOCUMENT_ID, source_id=_SOURCE_ID, content_sha256="a" * 64)
        )
        ledger.save_raw_blob(
            RawBlob(
                id="blb_article_fixture",
                hash_algorithm="sha256",
                digest="b" * 64,
                byte_length=1,
                media_type="text/plain",
                storage_locator="sources/raw/blb_article_fixture.txt",
            )
        )
        ledger.ensure_processing_task_fingerprint(
            processing_task_fingerprint(
                task_kind="fixture_representation",
                document_id=_DOCUMENT_ID,
                blob_id="blb_article_fixture",
                input_digest=bundle.representation.input_blob_digest,
                processor_name=bundle.representation.parser_name,
                processor_version=bundle.representation.parser_version,
                processor_config_digest=bundle.representation.parser_config_digest,
                build_identity=BuildIdentity("fixture", "fixture", "c" * 64, "1"),
                policy_id="fixture_policy",
                output_contract_version="1",
            ).model_copy(update={"id": bundle.representation.processing_task_fingerprint_id})
        )
        ledger.save_document_representation(bundle.representation)
        for text_view in bundle.text_views:
            ledger.save_text_view(text_view)
        for node in bundle.nodes:
            ledger.save_document_node(node)
        ledger.save_parse_quality_report(bundle.quality_report)
        ledger.save_evidence_target(evidence_target)
        ledger.save_evidence_validation_attempt(validation_attempt)
    return ledger_path


def _evidence_records() -> tuple[
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
]:
    text_digest = hashlib.sha256(_TEXT.encode()).hexdigest()
    text_view = TextView(
        id="tvw_article",
        representation_id="rep_article",
        kind=TextViewKind.LOGICAL,
        content_digest=text_digest,
        text=_TEXT,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id="nod_article",
        representation_id="rep_article",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(_TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_article",
        representation_id="rep_article",
        metric_values={"text_char_count": len(_TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_article",
        document_id=_DOCUMENT_ID,
        parser_name="test",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_fixture",
        input_blob_digest="b" * 64,
        canonical_output_digest="0" * 64,
        created_at=_NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(node,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    bundle = DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(node,),
        quality_report=quality_report,
    )
    evidence_target = EvidenceTarget(
        id=_SUPPORT,
        source_id=_SOURCE_ID,
        document_id=_DOCUMENT_ID,
        exact_text="Alpha",
        prefix_text="",
        suffix_text=". Alpha.",
        representation_id="rep_article",
        text_view_id="tvw_article",
        text_view_digest=text_digest,
        start_char=0,
        end_char=5,
        node_ids=("nod_article",),
        normalization_policy="utf8_identity_v1",
        created_at=_NOW,
    )
    validation_attempt = EvidenceValidationAttempt(
        id="eva_support_01",
        evidence_target_id=evidence_target.id,
        target_digest=canonical_evidence_target_digest(evidence_target),
        validator_version="1",
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=_NOW,
    )
    return bundle, evidence_target, validation_attempt
