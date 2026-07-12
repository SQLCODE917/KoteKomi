import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import pytest
from kotekomi_adapters import (
    ImmutableRecordConflict,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_adapters.sqlite_ledger import SQLiteLedgerRepository
from kotekomi_application import (
    BuildIdentity,
    ReviewProposedChangeInput,
    approve_proposed_change,
    canonical_record_json,
    deterministic_assertion_evidence_link_id,
    deterministic_review_provenance_activity_id,
    processing_task_fingerprint,
    verify_evidence_target,
)
from kotekomi_application.proposed_change_review import ProposedChangeReviewLedger
from kotekomi_domain import (
    AssertionEvidenceLink,
    AssertionEvidenceRole,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    Organization,
    ParseQualityReport,
    ProposedChange,
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
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 7, 11, tzinfo=UTC)
TEXT = "Alpha supports the reviewed assertion."
TEXT_DIGEST = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()


def _bundle() -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_atomic_logical",
        representation_id="rep_atomic",
        kind=TextViewKind.LOGICAL,
        content_digest=TEXT_DIGEST,
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )

    node = DocumentNode(
        id="nod_atomic_document",
        representation_id="rep_atomic",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_atomic",
        representation_id="rep_atomic",
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_atomic",
        document_id="doc_atomic",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_fixture",
        input_blob_digest="b" * 64,
        canonical_output_digest="0" * 64,
        created_at=NOW,
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
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(node,),
        quality_report=quality_report,
    )


def _representation_task():
    return processing_task_fingerprint(
        task_kind="atomic_acceptance_fixture",
        document_id="doc_atomic",
        blob_id="blb_atomic",
        input_digest="b" * 64,
        processor_name="fixture",
        processor_version="1",
        processor_config_digest="a" * 64,
        build_identity=BuildIdentity("fixture", "fixture", "c" * 64, "1"),
        policy_id="fixture_policy",
        output_contract_version="1",
    ).model_copy(update={"id": "ptf_fixture"})


def _evidence_target(
    record_id: str,
    *,
    text_view_digest: str = TEXT_DIGEST,
    exact_text: str = TEXT,
    representation_id: str = "rep_atomic",
) -> EvidenceTarget:
    evidence = EvidenceTarget(
        id=record_id,
        source_id="src_atomic",
        document_id="doc_atomic",
        exact_text=exact_text,
        representation_id=representation_id,
        text_view_id="tvw_atomic_logical",
        text_view_digest=text_view_digest,
        start_char=0,
        end_char=len(TEXT),
        node_ids=("nod_atomic_document",),
        normalization_policy="utf8_identity_v1",
    )
    return evidence


def _assertion_record(*, evidence_target_ids: list[str] | None = None) -> dict[str, JsonValue]:
    return {
        "id": "ast_atomic",
        "assertion_type": "source_claim",
        "epistemic_scope": "source_report",
        "subject_entity_id": "org_atomic",
        "predicate": "reported_alpha",
        "object_value": "Alpha",
        "status": "proposed",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_ids": ["src_atomic"],
        "evidence_target_ids": cast(list[JsonValue], evidence_target_ids or ["etg_atomic"]),
        "provenance_activity_ids": [],
    }


def _link_spec(
    evidence_target_id: str,
    *,
    role: str = "direct_support",
    polarity: str = "supports",
) -> dict[str, JsonValue]:
    return {
        "evidence_target_id": evidence_target_id,
        "validation_attempt_id": _validation_attempt_id(evidence_target_id),
        "role": role,
        "polarity": polarity,
        "necessity": "required",
    }


def _proposed_change(
    *,
    evidence_links: list[dict[str, JsonValue]],
    evidence_target_ids: list[str] | None = None,
) -> ProposedChange:
    proposed_json: dict[str, JsonValue] = {
        "record_type": "Assertion",
        "stable_label": "atomic_assertion",
        "record": _assertion_record(evidence_target_ids=evidence_target_ids),
        "evidence": {
            "selector_type": "exact_text",
            "exact_text": TEXT,
            "source_id": "src_atomic",
            "document_id": "doc_atomic",
        },
        "evidence_links": cast(JsonValue, evidence_links),
    }
    return ProposedChange(
        id="pcg_atomic",
        review_status=ReviewStatus.PENDING,
        proposed_json=proposed_json,
        source_id="src_atomic",
        document_id="doc_atomic",
        model_name="fixture",
        prompt_id="fixture",
        provenance_activity_id="prv_model",
        created_at=NOW,
        updated_at=NOW,
    )


def _seed(
    ledger_path: Path,
    *,
    evidence: tuple[EvidenceTarget, ...],
    proposed_change: ProposedChange,
    validated_evidence_ids: tuple[str, ...] | None = None,
) -> None:
    SQLiteLedgerInitializer(ledger_path).initialize()
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_source(
            Source(
                id="src_atomic",
                source_type=SourceType.ARTICLE,
                identity_policy_id="fixture_v1",
                canonical_identity_key="atomic",
            )
        )
        repository.save_document(
            Document(
                id="doc_atomic",
                source_id="src_atomic",
                content_sha256="b" * 64,
            )
        )
        repository.save_raw_blob(
            RawBlob(
                id="blb_atomic",
                hash_algorithm="sha256",
                digest="b" * 64,
                byte_length=1,
                media_type="application/octet-stream",
                storage_locator="sources/raw/blb_atomic.bin",
            )
        )
        repository.ensure_processing_task_fingerprint(_representation_task())
        repository.save_organization(Organization(id="org_atomic", name="Atomic Org"))
        repository.commit_document_representation_bundle(_bundle())
        for span in evidence:
            repository.save_evidence_target(span)
        for evidence_target_id in (
            tuple(span.id for span in evidence)
            if validated_evidence_ids is None
            else validated_evidence_ids
        ):
            span = next(item for item in evidence if item.id == evidence_target_id)
            repository.save_evidence_validation_attempt(
                EvidenceValidationAttempt(
                    id=_validation_attempt_id(span.id),
                    evidence_target_id=span.id,
                    target_digest=canonical_evidence_target_digest(span),
                    validator_version="fixture_v1",
                    status=EvidenceValidationAttemptStatus.SUCCEEDED,
                    attempted_at=NOW,
                )
            )
        repository.save_proposed_change(proposed_change)


def _validation_attempt_id(evidence_target_id: str) -> str:
    return f"eva_{evidence_target_id.removeprefix('evt_')}"


def _review_input() -> ReviewProposedChangeInput:
    return ReviewProposedChangeInput("pcg_atomic", "reviewer", NOW)


def _assert_no_acceptance_writes(ledger_path: Path) -> None:
    provenance_id = deterministic_review_provenance_activity_id(
        proposed_change_id="pcg_atomic",
        activity_type="proposed_change_approved",
        reviewer="reviewer",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_assertion("ast_atomic") is None
        assert repository.get_provenance_activity(provenance_id) is None
        proposed_change = repository.get_proposed_change("pcg_atomic")
        assert proposed_change is not None
        assert proposed_change.review_status is ReviewStatus.PENDING


def test_acceptance_commits_assertion_links_and_review_provenance_after_restart(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    first = _evidence_target("etg_atomic")
    second = _evidence_target("etg_atomic_context")
    change = _proposed_change(
        evidence_links=[
            _link_spec(first.id),
            _link_spec(
                second.id,
                role="definition",
                polarity="contextualizes",
            ),
        ],
        evidence_target_ids=[first.id, second.id],
    )
    _seed(ledger_path, evidence=(first, second), proposed_change=change)

    with sqlite_ledger_transaction(ledger_path) as repository:
        result = approve_proposed_change(_review_input(), repository)

    with sqlite_ledger_transaction(ledger_path) as repository:
        assertion = repository.get_assertion("ast_atomic")
        assert assertion is not None
        assert result.assertion_evidence_link_ids == tuple(
            link.id for link in repository.list_assertion_evidence_links()
        )
        assert len(result.assertion_evidence_link_ids) == 2
        assert repository.get_provenance_activity(result.provenance_activity_id) is not None
        proposed_change = repository.get_proposed_change("pcg_atomic")
        assert proposed_change is not None
        assert proposed_change.review_status is ReviewStatus.APPROVED
        stored_evidence = repository.get_evidence_target(first.id)
        validation_attempt = repository.get_evidence_validation_attempt(
            _validation_attempt_id(first.id)
        )
        assert stored_evidence is not None
        assert validation_attempt is not None
        assert verify_evidence_target(stored_evidence, validation_attempt, repository).valid


@pytest.mark.parametrize(
    ("failure", "expected_message"),
    [
        ("no_links", "requires validated direct_support evidence"),
        ("definition_only", "requires validated direct_support evidence"),
        ("unvalidated", "missing EvidenceValidationAttempt"),
        ("stale_text_view", "successful EvidenceValidationAttempt"),
        ("selector_disagreement", "successful EvidenceValidationAttempt"),
        ("missing_representation", "successful EvidenceValidationAttempt"),
        ("source_absent", "must belong to the accepted Assertion"),
        ("evidence_absent", "must belong to the accepted Assertion"),
    ],
)
def test_evidence_gate_failures_leave_no_partial_acceptance_writes(
    tmp_path: Path,
    failure: Literal[
        "no_links",
        "definition_only",
        "unvalidated",
        "stale_text_view",
        "selector_disagreement",
        "missing_representation",
        "source_absent",
        "evidence_absent",
    ],
    expected_message: str,
) -> None:
    evidence = _evidence_target("etg_atomic")
    links = [_link_spec(evidence.id)]
    evidence_ids: list[str] | None = None
    if failure == "no_links":
        links = []
    elif failure == "definition_only":
        links = [_link_spec(evidence.id, role="definition", polarity="contextualizes")]
    elif failure == "stale_text_view":
        evidence = _evidence_target(evidence.id, text_view_digest="0" * 64)
    elif failure == "selector_disagreement":
        evidence = _evidence_target(evidence.id, exact_text="Wrong evidence")
    elif failure == "missing_representation":
        evidence = _evidence_target(evidence.id, representation_id="rep_missing")
    elif failure == "source_absent":
        change = _proposed_change(evidence_links=links)
        record = dict(cast(dict[str, JsonValue], change.proposed_json["record"]))
        record["source_ids"] = ["src_other"]
        proposed_json = {**change.proposed_json, "record": record}
        change = change.model_copy(update={"proposed_json": proposed_json})
        ledger_path = tmp_path / "ledger.db"
        _seed(ledger_path, evidence=(evidence,), proposed_change=change)
        with pytest.raises(ValueError, match=expected_message):
            with sqlite_ledger_transaction(ledger_path) as repository:
                approve_proposed_change(_review_input(), repository)
        _assert_no_acceptance_writes(ledger_path)
        return
    elif failure == "evidence_absent":
        evidence_ids = ["etg_other"]

    ledger_path = tmp_path / "ledger.db"
    _seed(
        ledger_path,
        evidence=(evidence,),
        proposed_change=_proposed_change(evidence_links=links, evidence_target_ids=evidence_ids),
        validated_evidence_ids=() if failure == "unvalidated" else None,
    )
    with pytest.raises(ValueError, match=expected_message):
        with sqlite_ledger_transaction(ledger_path) as repository:
            approve_proposed_change(_review_input(), repository)
    _assert_no_acceptance_writes(ledger_path)


def test_second_link_conflict_rolls_back_the_entire_acceptance_bundle(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    first = _evidence_target("etg_atomic")
    second = _evidence_target("etg_atomic_context")
    change = _proposed_change(
        evidence_links=[_link_spec(first.id), _link_spec(second.id)],
        evidence_target_ids=[first.id, second.id],
    )
    _seed(ledger_path, evidence=(first, second), proposed_change=change)
    conflicting_id = deterministic_assertion_evidence_link_id(
        assertion_id="ast_atomic",
        evidence_target_id=second.id,
        validation_attempt_id=_validation_attempt_id(second.id),
        role=AssertionEvidenceRole.DIRECT_SUPPORT,
        polarity=EvidencePolarity.SUPPORTS,
        necessity=EvidenceNecessity.REQUIRED,
    )
    conflicting_link = AssertionEvidenceLink(
        id=conflicting_id,
        assertion_id="ast_atomic",
        evidence_target_id=second.id,
        validation_attempt_id=_validation_attempt_id(second.id),
        role=AssertionEvidenceRole.DIRECT_SUPPORT,
        polarity=EvidencePolarity.SUPPORTS,
        necessity=EvidenceNecessity.REQUIRED,
        provenance_id="prv_preexisting",
        created_at=NOW,
    )
    with sqlite3.connect(ledger_path) as connection:
        connection.execute(
            """
            INSERT INTO assertion_evidence_links (id, created_at, payload_json)
            VALUES (?, ?, ?)
            """,
            (
                conflicting_link.id,
                conflicting_link.created_at.isoformat(),
                canonical_record_json(conflicting_link),
            ),
        )

    with pytest.raises(ImmutableRecordConflict):
        with sqlite_ledger_transaction(ledger_path) as repository:
            approve_proposed_change(_review_input(), repository)

    _assert_no_acceptance_writes(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert tuple(link.id for link in repository.list_assertion_evidence_links()) == (
            conflicting_id,
        )


def test_repository_does_not_expose_a_generic_assertion_evidence_link_write(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    SQLiteLedgerInitializer(ledger_path).initialize()

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert not hasattr(repository, "save_assertion_evidence_link")


class _CorruptBundleRepository:
    def __init__(self, repository: SQLiteLedgerRepository) -> None:
        self._repository = repository

    def __getattr__(self, name: str) -> object:
        return getattr(self._repository, name)

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        bundle = self._repository.get_document_representation_bundle(record_id)
        if bundle is None:
            return None
        representation = bundle.representation.model_copy(
            update={"canonical_output_digest": "0" * 64}
        )
        return bundle.model_copy(update={"representation": representation})


def test_corrupt_representation_digest_rejects_acceptance_without_partial_writes(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    evidence = _evidence_target("etg_atomic")
    _seed(
        ledger_path,
        evidence=(evidence,),
        proposed_change=_proposed_change(evidence_links=[_link_spec(evidence.id)]),
    )

    with pytest.raises(ValueError, match="replayable successful EvidenceValidationAttempt"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            approve_proposed_change(
                _review_input(),
                cast(ProposedChangeReviewLedger, _CorruptBundleRepository(repository)),
            )

    _assert_no_acceptance_writes(ledger_path)
