import hashlib
import json
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application.candidate_wiki import (
    AuditCandidateWikiRecordCommand,
    CandidateWikiAuditBundle,
    WikiAssertionPresentation,
    WikiBuildManifest,
    WikiEventPresentation,
    audit_candidate_wiki_record,
    build_candidate_knowledge_view,
    candidate_wiki_build_id,
    plan_candidate_wiki,
    select_candidate_ingestions,
)
from kotekomi_domain import (
    Actor,
    Assertion,
    AssertionEvidenceLink,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    Entity,
    Event,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    IngestionChangeSet,
    IngestionChangeSetOrigin,
    IngestionRun,
    IngestionRunStatus,
    Organization,
    ParseQualityReport,
    Place,
    ProposedChange,
    RepresentationAnalyzability,
    ReviewStatus,
    Source,
    SourceCoordinateSystem,
    SourceRegion,
    SourceType,
    TextView,
    TextViewKind,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 9, 4, tzinfo=UTC)
TEXT = "Acme hired Alice."
CHARACTERIZATION_TEXT = 'Amodei characterized Donald Trump as a "feudal warlord".'
type JsonObject = dict[str, JsonValue]


class FakeCandidateWikiLedger:
    def __init__(self) -> None:
        self.source = Source(
            id="src_example",
            source_type=SourceType.PDF,
            identity_policy_id="test",
            canonical_identity_key="https://example.test/report",
            created_at=NOW,
            updated_at=NOW,
        )
        self.document = Document(
            id="doc_example",
            source_id=self.source.id,
            content_sha256="a" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        self.bundle = _bundle()
        self.target = _target()
        self.attempt = EvidenceValidationAttempt(
            id="eva_example",
            evidence_target_id=self.target.id,
            target_digest=canonical_evidence_target_digest(self.target),
            validator_version="test",
            status=EvidenceValidationAttemptStatus.SUCCEEDED,
            attempted_at=NOW,
        )
        self.accepted_organization = Organization(
            id="org_accepted",
            name="Accepted Corp",
            organization_type="company",
            created_at=NOW,
            updated_at=NOW,
        )
        self.proposals = _proposals(self.accepted_organization)
        self.change_set = _change_set(tuple(sorted(self.proposals)))
        self.run = IngestionRun(
            id="igr_example",
            requested_path="/input/report.pdf",
            display_filename="report.pdf",
            requested_source_url="https://example.test/report",
            normalized_source_url="https://example.test/report",
            status=IngestionRunStatus.CAPTURED,
            started_at=NOW,
            completed_at=NOW,
            source_id=self.source.id,
            document_id=self.document.id,
            representation_id=self.bundle.representation.id,
            provenance_activity_id="prv_example",
            analysis_run_id="arn_example",
            ingestion_change_set_id=self.change_set.id,
        )

    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]:
        return (self.run,)

    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None:
        return self.change_set if record_id == self.change_set.id else None

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposals.get(record_id)

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def get_entity(self, record_id: str) -> Entity | None:
        return None

    def get_actor(self, record_id: str) -> Actor | None:
        return None

    def get_organization(self, record_id: str) -> Organization | None:
        if record_id == self.accepted_organization.id:
            return self.accepted_organization
        return None

    def get_place(self, record_id: str) -> Place | None:
        return None

    def get_event(self, record_id: str) -> Event | None:
        return None

    def get_assertion(self, record_id: str) -> Assertion | None:
        return None

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.target if record_id == self.target.id else None

    def get_evidence_validation_attempt(self, record_id: str) -> EvidenceValidationAttempt | None:
        return self.attempt if record_id == self.attempt.id else None

    def list_assertion_evidence_links(self) -> tuple[AssertionEvidenceLink, ...]:
        return ()


class FakeCandidateWikiAuditArchive:
    def __init__(self, bundle: CandidateWikiAuditBundle) -> None:
        self.bundle = bundle

    def read_candidate_wiki_audit_bundle(self, build_id: str) -> CandidateWikiAuditBundle:
        assert build_id == self.bundle.manifest.build_id
        return self.bundle


def test_candidate_view_preserves_review_state_closes_references_and_plans_pages() -> None:
    ledger = FakeCandidateWikiLedger()

    first = build_candidate_knowledge_view(ledger.run, ledger)
    second = build_candidate_knowledge_view(ledger.run, ledger)
    plan = plan_candidate_wiki(first)

    assert first.candidate_snapshot_digest == second.candidate_snapshot_digest
    assert first.excluded_proposal_counts == (("Organization", 1),)
    assert len(first.records) == 5
    assert {item.record.id for item in first.records} == {
        "act_alice",
        "ast_hired",
        "evt_hiring",
        "org_accepted",
        "org_acme",
    }
    assert (
        next(item for item in first.records if item.record.id == "org_accepted").is_pending is False
    )
    assert len(first.evidence_references) == 5
    assert {page.page_kind for page in plan.pages} == {
        "home",
        "document",
        "actor",
        "organization",
        "event",
    }
    event_page = next(page for page in plan.pages if page.page_kind == "event")
    organization_page = next(page for page in plan.pages if page.display_label == "Acme")
    event_statement = event_page.presentations[0]
    organization_statement = organization_page.presentations[0]
    assert isinstance(event_statement, WikiAssertionPresentation)
    assert isinstance(organization_statement, WikiAssertionPresentation)
    assert event_statement.edge.predicate == "hired"
    assert organization_statement.edge.subject_label == "Hiring"
    pending_org = next(item for item in first.records if item.record.id == "org_acme")
    assert "created_at" not in pending_org.source_payload_json


def test_candidate_view_fails_when_proposal_evidence_does_not_replay() -> None:
    ledger = FakeCandidateWikiLedger()
    proposal = ledger.proposals["pcg_org"]
    evidence = dict(cast(JsonObject, proposal.proposed_json["evidence"]))
    evidence["exact_text"] = "Wrong"
    ledger.proposals[proposal.id] = proposal.model_copy(
        update={"proposed_json": proposal.proposed_json | {"evidence": evidence}}
    )

    with pytest.raises(ValueError, match="exact text does not replay"):
        build_candidate_knowledge_view(ledger.run, ledger)


def test_reconciled_entity_page_preserves_every_source_selector() -> None:
    ledger = FakeCandidateWikiLedger()
    proposal = ledger.proposals["pcg_org"]
    whole = _embedded_evidence()
    mention = cast(JsonObject, json.loads(json.dumps(whole)))
    mention["exact_text"] = "Acme"
    mention["suffix_text"] = TEXT[len("Acme") :]
    location = cast(JsonObject, mention["location"])
    location["end_char"] = len("Acme")
    ledger.proposals[proposal.id] = proposal.model_copy(
        update={
            "proposed_json": proposal.proposed_json
            | {
                "identity_reconciliation": {
                    "preview_id": "erp_example",
                    "mention_evidence": [mention, whole],
                }
            }
        }
    )

    view = build_candidate_knowledge_view(ledger.run, ledger)
    organization = next(item for item in view.records if item.record.id == "org_acme")
    references = tuple(
        item for item in view.evidence_references if item.proposed_change_id == proposal.id
    )

    assert organization.evidence_reference_keys == (
        "proposal:pcg_org:0",
        "proposal:pcg_org:1",
    )
    assert tuple(item.exact_text for item in references) == ("Acme", TEXT)


def test_rejected_proposal_body_remains_part_of_candidate_snapshot() -> None:
    ledger = FakeCandidateWikiLedger()
    before = build_candidate_knowledge_view(ledger.run, ledger)
    rejected = ledger.proposals["pcg_rejected"]
    record = dict(cast(JsonObject, rejected.proposed_json["record"]))
    record["name"] = "Different rejected proposal"
    ledger.proposals[rejected.id] = rejected.model_copy(
        update={"proposed_json": rejected.proposed_json | {"record": record}}
    )

    after = build_candidate_knowledge_view(ledger.run, ledger)

    assert after.excluded_proposal_counts == before.excluded_proposal_counts
    assert after.candidate_snapshot_digest != before.candidate_snapshot_digest


def test_exact_filename_selector_returns_all_closed_matches_newest_first() -> None:
    ledger = FakeCandidateWikiLedger()
    older = ledger.run.model_copy(
        update={"id": "igr_older", "started_at": datetime(2026, 9, 3, tzinfo=UTC)}
    )
    ledger.list_ingestion_runs = lambda: (ledger.run, older)  # type: ignore[method-assign]

    result = select_candidate_ingestions("report.pdf", ledger)

    assert tuple(item.id for item in result.matches) == ("igr_example", "igr_older")


def test_candidate_wiki_groups_a_complete_characterization_event() -> None:
    ledger = FakeCandidateWikiLedger()
    _use_source_text(ledger, CHARACTERIZATION_TEXT)
    ledger.proposals = _characterization_proposals()
    ledger.change_set = _change_set(tuple(sorted(ledger.proposals)))
    ledger.run = ledger.run.model_copy(update={"ingestion_change_set_id": ledger.change_set.id})

    plan = plan_candidate_wiki(build_candidate_knowledge_view(ledger.run, ledger))

    amodei_page = next(page for page in plan.pages if page.display_label == "Amodei")
    trump_page = next(page for page in plan.pages if page.display_label == "Donald Trump")
    assert len(amodei_page.presentations) == 1
    event = amodei_page.presentations[0]
    assert isinstance(event, WikiEventPresentation)
    assert trump_page.presentations == (event,)
    assert event.frame_id == "characterization"
    assert event.complete is True
    assert event.issues == ()
    assert tuple(edge.predicate for edge in event.edges) == (
        "has_event_type",
        "has_argument",
        "has_argument",
        "has_argument",
        "has_polarity",
        "has_modality",
    )
    role_edges = {
        next(
            qualifier.value for qualifier in edge.qualifiers if qualifier.key == "frame_role_id"
        ): edge
        for edge in event.edges
        if edge.predicate == "has_argument"
    }
    assert role_edges["characterization.evaluator"].object_label == "Amodei"
    assert role_edges["characterization.evaluated_subject"].object_label == "Donald Trump"
    assert role_edges["characterization.characterization"].object_label == '"feudal warlord"'
    assert tuple(
        (qualifier.key, qualifier.value)
        for qualifier in role_edges["characterization.evaluator"].qualifiers
    ) == (
        ("frame_role_id", "characterization.evaluator"),
        ("upper_role", "agent"),
    )


def test_candidate_wiki_audit_resolves_event_graph_and_exact_evidence() -> None:
    ledger = FakeCandidateWikiLedger()
    _use_source_text(ledger, CHARACTERIZATION_TEXT)
    ledger.proposals = _characterization_proposals()
    ledger.change_set = _change_set(tuple(sorted(ledger.proposals)))
    ledger.run = ledger.run.model_copy(update={"ingestion_change_set_id": ledger.change_set.id})
    plan = plan_candidate_wiki(build_candidate_knowledge_view(ledger.run, ledger))
    build_id = candidate_wiki_build_id(
        view_policy_id=plan.view_policy_id,
        renderer_policy_id=plan.renderer_policy_id,
        ingestion_run_id=plan.ingestion_run_id,
        ingestion_change_set_id=plan.ingestion_change_set_id,
        candidate_snapshot_digest=plan.candidate_snapshot_digest,
        counts=plan.counts,
    )
    archive = FakeCandidateWikiAuditArchive(
        CandidateWikiAuditBundle(
            manifest=WikiBuildManifest(
                schema_version="candidate_wiki_manifest_v2",
                build_id=build_id,
                view_policy_id=plan.view_policy_id,
                renderer_policy_id=plan.renderer_policy_id,
                ingestion_run_id=plan.ingestion_run_id,
                ingestion_change_set_id=plan.ingestion_change_set_id,
                candidate_snapshot_digest=plan.candidate_snapshot_digest,
                files=(),
                counts=plan.counts,
            ),
            citation_registry=plan.citation_registry,
            audit_catalog=plan.audit_catalog,
        )
    )

    result = audit_candidate_wiki_record(
        AuditCandidateWikiRecordCommand(build_id, "evt_characterization"), archive
    )

    assert result.record.record_type == "Event"
    assert result.record.state == "pending"
    assert tuple(edge.assertion_id for edge in result.record.ontology_edges) == (
        "ast_00_event_type",
        "ast_01_characterization",
        "ast_02_evaluated_subject",
        "ast_03_evaluator",
        "ast_04_polarity",
        "ast_05_modality",
    )
    assert result.record.provenance_activity_ids == ("prv_example",)
    assert result.evidence
    assert {item.exact_text for item in result.evidence} == {CHARACTERIZATION_TEXT}
    with pytest.raises(ValueError, match="has no record: evt_missing"):
        audit_candidate_wiki_record(
            AuditCandidateWikiRecordCommand(build_id, "evt_missing"), archive
        )


def test_candidate_wiki_exposes_an_incomplete_governed_event() -> None:
    ledger = FakeCandidateWikiLedger()
    _use_source_text(ledger, CHARACTERIZATION_TEXT)
    proposals = _characterization_proposals()
    proposals.pop("pcg_characterization_value")
    ledger.proposals = proposals
    ledger.change_set = _change_set(tuple(sorted(ledger.proposals)))
    ledger.run = ledger.run.model_copy(update={"ingestion_change_set_id": ledger.change_set.id})

    plan = plan_candidate_wiki(build_candidate_knowledge_view(ledger.run, ledger))

    event_page = next(page for page in plan.pages if page.display_label == "Characterization")
    event = event_page.presentations[0]
    assert isinstance(event, WikiEventPresentation)
    assert event.complete is False
    assert event.issues == ("Missing required role: characterization.characterization.",)


def _bundle(text: str = TEXT) -> DocumentRepresentationBundle:
    text_digest = hashlib.sha256(text.encode()).hexdigest()
    text_view = TextView(
        id="tvw_example",
        representation_id="rep_example",
        kind=TextViewKind.LOGICAL,
        content_digest=text_digest,
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_root",
        representation_id="rep_example",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    node = DocumentNode(
        id="nod_example",
        representation_id="rep_example",
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
        source_region_ids=("srg_example",),
        source_page_numbers=(1,),
        source_text_digest=text_digest,
    )
    region = SourceRegion(
        id="srg_example",
        representation_id="rep_example",
        coordinate_system=SourceCoordinateSystem.PDF_POINTS_TOP_LEFT_V1,
        page_number=1,
        page_width=100.0,
        page_height=100.0,
        left=1.0,
        top=1.0,
        right=99.0,
        bottom=20.0,
        rotation_applied=0,
    )
    quality = ParseQualityReport(
        id="pqr_example",
        representation_id="rep_example",
        metric_values={},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_example",
        document_id="doc_example",
        parser_name="test",
        parser_version="1",
        parser_config_digest="b" * 64,
        processing_task_fingerprint_id="ptf_example",
        input_blob_digest="a" * 64,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, node),
                edges=(),
                source_regions=(region,),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, node),
        source_regions=(region,),
        quality_report=quality,
    )


def _target(text: str = TEXT) -> EvidenceTarget:
    text_digest = hashlib.sha256(text.encode()).hexdigest()
    return EvidenceTarget(
        id="etg_example",
        source_id="src_example",
        document_id="doc_example",
        representation_id="rep_example",
        text_view_id="tvw_example",
        text_view_digest=text_digest,
        start_char=0,
        end_char=len(text),
        exact_text=text,
        normalization_policy="utf8_identity_v1",
        node_ids=("nod_example",),
        created_at=NOW,
    )


def _proposals(accepted: Organization) -> dict[str, ProposedChange]:
    records: tuple[tuple[str, str, JsonObject], ...] = (
        (
            "pcg_actor",
            "Actor",
            {"id": "act_alice", "name": "Alice", "role_names": [], "organization_ids": []},
        ),
        (
            "pcg_event",
            "Event",
            {
                "id": "evt_hiring",
                "name": "Hiring",
                "start_at": None,
                "end_at": None,
                "place_id": None,
                "participant_actor_ids": ["act_alice"],
                "participant_organization_ids": ["org_acme"],
            },
        ),
        (
            "pcg_org",
            "Organization",
            {"id": "org_acme", "name": "Acme", "organization_type": "company"},
        ),
    )
    proposals = {
        change_id: _proposal(change_id, record_type, record)
        for change_id, record_type, record in records
    }
    proposals["pcg_assertion"] = ProposedChange(
        id="pcg_assertion",
        proposed_json={
            "record_type": "Assertion",
            "stable_label": "ast_hired",
            "record": {
                "id": "ast_hired",
                "assertion_type": "source_claim",
                "epistemic_scope": "source_report",
                "subject_entity_id": "evt_hiring",
                "relation_label": "hired",
                "object_entity_id": "org_acme",
                "object_value": None,
                "source_authority": "secondary",
                "attribution_basis": "reported_by_source",
                "source_ids": ["src_example"],
                "evidence_target_ids": ["etg_example"],
                "supporting_assertion_ids": [],
                "authority_source_ids": [],
                "authority_evidence_target_ids": [],
            },
            "evidence_links": [
                {
                    "evidence_target_id": "etg_example",
                    "validation_attempt_id": "eva_example",
                    "role": "direct_support",
                    "polarity": "supports",
                    "necessity": "required",
                }
            ],
        },
        source_id="src_example",
        document_id="doc_example",
        provenance_activity_id="prv_example",
        created_at=NOW,
        updated_at=NOW,
    )
    proposals["pcg_approved"] = ProposedChange(
        id="pcg_approved",
        review_status=ReviewStatus.APPROVED,
        proposed_json={
            "record_type": "Organization",
            "stable_label": accepted.id,
            "record": {
                "id": accepted.id,
                "name": accepted.name,
                "organization_type": accepted.organization_type,
            },
            "evidence": _embedded_evidence(),
        },
        accepted_json=accepted.model_dump(mode="json"),
        source_id="src_example",
        document_id="doc_example",
        provenance_activity_id="prv_example",
        created_at=NOW,
        updated_at=NOW,
    )
    proposals["pcg_rejected"] = _proposal(
        "pcg_rejected",
        "Organization",
        {"id": "org_rejected", "name": "Rejected", "organization_type": "company"},
    ).model_copy(update={"review_status": ReviewStatus.REJECTED})
    return proposals


def _proposal(
    change_id: str,
    record_type: str,
    record: JsonObject,
    *,
    evidence_text: str = TEXT,
) -> ProposedChange:
    return ProposedChange(
        id=change_id,
        proposed_json={
            "record_type": record_type,
            "stable_label": str(record["id"]),
            "record": record,
            "evidence": _embedded_evidence(evidence_text),
        },
        source_id="src_example",
        document_id="doc_example",
        provenance_activity_id="prv_example",
        created_at=NOW,
        updated_at=NOW,
    )


def _embedded_evidence(text: str = TEXT) -> JsonObject:
    return {
        "selector_type": "pinned_text",
        "source_id": "src_example",
        "document_id": "doc_example",
        "exact_text": text,
        "prefix_text": "",
        "suffix_text": "",
        "location": {
            "representation_id": "rep_example",
            "text_view_id": "tvw_example",
            "start_char": 0,
            "end_char": len(text),
            "node_ids": ["nod_example"],
        },
    }


def _use_source_text(ledger: FakeCandidateWikiLedger, text: str) -> None:
    ledger.bundle = _bundle(text)
    ledger.target = _target(text)
    ledger.attempt = ledger.attempt.model_copy(
        update={"target_digest": canonical_evidence_target_digest(ledger.target)}
    )


def _characterization_proposals() -> dict[str, ProposedChange]:
    records: tuple[tuple[str, str, JsonObject], ...] = (
        (
            "pcg_amodei",
            "Actor",
            {"id": "act_amodei", "name": "Amodei", "role_names": [], "organization_ids": []},
        ),
        (
            "pcg_trump",
            "Actor",
            {
                "id": "act_donald_trump",
                "name": "Donald Trump",
                "role_names": [],
                "organization_ids": [],
            },
        ),
        (
            "pcg_characterization_event",
            "Event",
            {
                "id": "evt_characterization",
                "name": "Characterization",
                "start_at": None,
                "end_at": None,
                "place_id": None,
                "participant_actor_ids": ["act_amodei", "act_donald_trump"],
                "participant_organization_ids": [],
            },
        ),
    )
    proposals = {
        change_id: _proposal(
            change_id,
            record_type,
            record,
            evidence_text=CHARACTERIZATION_TEXT,
        )
        for change_id, record_type, record in records
    }
    proposals.update(
        {
            "pcg_characterization_event_type": _characterization_assertion(
                "pcg_characterization_event_type",
                "ast_00_event_type",
                "has_event_type",
                object_value="characterization",
            ),
            "pcg_characterization_value": _characterization_assertion(
                "pcg_characterization_value",
                "ast_01_characterization",
                "has_argument",
                object_value='"feudal warlord"',
                qualifiers={
                    "frame_role_id": "characterization.characterization",
                    "upper_role": "content",
                },
            ),
            "pcg_characterization_subject": _characterization_assertion(
                "pcg_characterization_subject",
                "ast_02_evaluated_subject",
                "has_argument",
                object_entity_id="act_donald_trump",
                qualifiers={
                    "frame_role_id": "characterization.evaluated_subject",
                    "upper_role": "theme",
                },
            ),
            "pcg_characterization_evaluator": _characterization_assertion(
                "pcg_characterization_evaluator",
                "ast_03_evaluator",
                "has_argument",
                object_entity_id="act_amodei",
                qualifiers={
                    "frame_role_id": "characterization.evaluator",
                    "upper_role": "agent",
                },
            ),
            "pcg_characterization_polarity": _characterization_assertion(
                "pcg_characterization_polarity",
                "ast_04_polarity",
                "has_polarity",
                object_value="affirmed",
            ),
            "pcg_characterization_modality": _characterization_assertion(
                "pcg_characterization_modality",
                "ast_05_modality",
                "has_modality",
                object_value="actual",
            ),
        }
    )
    return proposals


def _characterization_assertion(
    change_id: str,
    assertion_id: str,
    relation_label: str,
    *,
    object_entity_id: str | None = None,
    object_value: JsonValue = None,
    qualifiers: JsonObject | None = None,
) -> ProposedChange:
    return ProposedChange(
        id=change_id,
        proposed_json={
            "record_type": "Assertion",
            "stable_label": assertion_id,
            "record": {
                "id": assertion_id,
                "assertion_type": "source_claim",
                "epistemic_scope": "source_report",
                "subject_entity_id": "evt_characterization",
                "relation_label": relation_label,
                "object_entity_id": object_entity_id,
                "object_value": object_value,
                "source_authority": "secondary",
                "attribution_basis": "reported_by_source",
                "qualifiers": qualifiers or {},
                "source_ids": ["src_example"],
                "evidence_target_ids": ["etg_example"],
                "supporting_assertion_ids": [],
                "authority_source_ids": [],
                "authority_evidence_target_ids": [],
            },
            "evidence_links": [
                {
                    "evidence_target_id": "etg_example",
                    "validation_attempt_id": "eva_example",
                    "role": "direct_support",
                    "polarity": "supports",
                    "necessity": "required",
                }
            ],
        },
        source_id="src_example",
        document_id="doc_example",
        provenance_activity_id="prv_example",
        created_at=NOW,
        updated_at=NOW,
    )


def _change_set(proposal_ids: tuple[str, ...]) -> IngestionChangeSet:
    payload = {
        "ingestion_run_id": "igr_example",
        "analysis_run_id": "arn_example",
        "representation_id": "rep_example",
        "coverage_report_digest": "c" * 64,
        "proposed_change_ids": list(proposal_ids),
        "analysis_origin": "executed",
    }
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return IngestionChangeSet(
        id=f"ics_{digest[:24]}",
        ingestion_run_id="igr_example",
        analysis_run_id="arn_example",
        representation_id="rep_example",
        coverage_report_digest="c" * 64,
        proposed_change_ids=proposal_ids,
        analysis_origin=IngestionChangeSetOrigin.EXECUTED,
        closed_at=NOW,
        change_set_digest=digest,
    )
