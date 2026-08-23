from datetime import UTC, datetime
from typing import Any, cast

from kotekomi_application.evidence_graph_projection import (
    EVIDENCE_GRAPH_PROJECTION_POLICY_ID,
    EvidenceGraphError,
    EvidenceGraphFailureCode,
    EvidenceGraphLedger,
    EvidenceGraphProjectionPort,
    EvidenceGraphStateLedger,
    ExplainEvidenceGraphRelationshipCommand,
    build_evidence_graph_lineage_clusters,
    build_evidence_graph_state,
    explain_evidence_graph_relationship,
)
from kotekomi_application.ports import AcceptedCanonicalRecord
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionEvidenceLink,
    AssertionEvidenceRole,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Document,
    EpistemicScope,
    EvidenceGraphProjectionManifest,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    Organization,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    ReviewStatus,
    SourceAuthority,
    SourceLineageRelation,
    SourceLineageRelationType,
)
from pytest import raises

NOW = datetime(2026, 8, 23, tzinfo=UTC)


class FakeLedger:
    def __init__(self, *, validation_status: EvidenceValidationAttemptStatus) -> None:
        self.anthropic = Organization(id="org_anthropic", name="Anthropic")
        self.department = Organization(id="org_department", name="Department of Defense")
        self.document = Document(
            id="doc_policy",
            source_id="src_policy",
            content_sha256="c" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
        self.direct = _direct_assertion("ast_direct")
        self.inference = _inference_assertion("ast_inference", self.direct.id)
        self.relationship = Relationship(
            id="rel_policy",
            subject_id=self.anthropic.id,
            predicate="is_subject_to_policy",
            object_id=self.department.id,
            assertion_ids=(self.inference.id,),
            created_at=NOW,
            updated_at=NOW,
        )
        self.target = EvidenceTarget(
            id="etg_policy",
            source_id="src_policy",
            document_id="doc_policy",
            representation_id="rep_policy",
            text_view_id="tvw_policy",
            text_view_digest="a" * 64,
            start_char=0,
            end_char=10,
            exact_text="Directive 3000.09",
            normalization_policy="exact-v1",
            node_ids=("nod_policy",),
            created_at=NOW,
        )
        self.attempt = EvidenceValidationAttempt(
            id="eva_policy",
            evidence_target_id=self.target.id,
            target_digest="b" * 64,
            validator_version="test-v1",
            status=validation_status,
            error_message="mismatch"
            if validation_status is EvidenceValidationAttemptStatus.FAILED
            else None,
            attempted_at=NOW,
        )
        self.link = AssertionEvidenceLink(
            id="ael_policy",
            assertion_id=self.direct.id,
            evidence_target_id=self.target.id,
            validation_attempt_id=self.attempt.id,
            role=AssertionEvidenceRole.DIRECT_SUPPORT,
            polarity=EvidencePolarity.SUPPORTS,
            necessity=EvidenceNecessity.REQUIRED,
            provenance_id="prv_policy",
            created_at=NOW,
        )
        self.argument_edges: tuple[ArgumentEdge, ...] = ()

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        return (
            self.anthropic,
            self.department,
            self.document,
            self.direct,
            self.inference,
            self.relationship,
            *self.argument_edges,
        )

    def list_assertion_evidence_links(self) -> tuple[AssertionEvidenceLink, ...]:
        return (self.link,)

    def list_evidence_validation_attempts(self) -> tuple[EvidenceValidationAttempt, ...]:
        return (self.attempt,)

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.target if record_id == self.target.id else None


class TemporalLedger(FakeLedger):
    initial_reviewed_at = datetime(2026, 8, 20, tzinfo=UTC)
    correction_reviewed_at = datetime(2026, 8, 21, tzinfo=UTC)

    def __init__(self) -> None:
        super().__init__(validation_status=EvidenceValidationAttemptStatus.SUCCEEDED)
        self.target = self.target.model_copy(update={"id": "etg_initial"})
        initial = self.direct.model_copy(
            update={
                "id": "ast_initial",
                "status": AssertionStatus.SUPERSEDED,
                "evidence_target_ids": (self.target.id,),
                "created_at": self.initial_reviewed_at,
                "updated_at": self.correction_reviewed_at,
            }
        )
        corrected = self.direct.model_copy(
            update={
                "id": "ast_corrected",
                "supersedes_assertion_id": initial.id,
                "evidence_target_ids": (self.target.id,),
                "provenance_activity_ids": ("prv_corrected",),
                "created_at": self.correction_reviewed_at,
                "updated_at": self.correction_reviewed_at,
            }
        )
        self.initial = initial
        self.corrected = corrected
        self.initial_relationship = self.relationship.model_copy(
            update={
                "id": "rel_initial",
                "assertion_ids": (initial.id,),
                "created_at": self.initial_reviewed_at,
                "updated_at": self.initial_reviewed_at,
            }
        )
        self.current_relationship = self.relationship.model_copy(
            update={
                "id": "rel_corrected",
                "assertion_ids": (corrected.id,),
                "created_at": self.correction_reviewed_at,
                "updated_at": self.correction_reviewed_at,
            }
        )
        self.link = self.link.model_copy(
            update={
                "id": "ael_initial",
                "assertion_id": initial.id,
                "evidence_target_id": self.target.id,
                "provenance_id": "prv_initial",
                "created_at": self.initial_reviewed_at,
            }
        )
        self.attempt = self.attempt.model_copy(
            update={"evidence_target_id": self.target.id, "attempted_at": self.initial_reviewed_at}
        )
        self.corrected_link = self.link.model_copy(
            update={
                "id": "ael_corrected",
                "assertion_id": corrected.id,
                "provenance_id": "prv_corrected",
                "created_at": self.correction_reviewed_at,
            }
        )
        self.activities = (
            _approval("pcg_target", self.target.id, self.initial_reviewed_at, "prv_target"),
            _approval("pcg_initial", initial.id, self.initial_reviewed_at, "prv_initial"),
            _approval(
                "pcg_rel_initial",
                self.initial_relationship.id,
                self.initial_reviewed_at,
                "prv_rel_initial",
            ),
            _approval("pcg_corrected", corrected.id, self.correction_reviewed_at, "prv_corrected"),
            _approval(
                "pcg_rel_corrected",
                self.current_relationship.id,
                self.correction_reviewed_at,
                "prv_rel_corrected",
            ),
        )
        self.changes: tuple[ProposedChange, ...] = (
            _change("pcg_target", self.target),
            _change("pcg_initial", initial.model_copy(update={"status": AssertionStatus.REPORTED})),
            _change("pcg_rel_initial", self.initial_relationship),
            _change("pcg_corrected", corrected),
            _change("pcg_rel_corrected", self.current_relationship),
        )

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        return (
            self.anthropic,
            self.department,
            self.document,
            self.initial,
            self.corrected,
            self.initial_relationship,
            self.current_relationship,
        )

    def list_assertion_evidence_links(self) -> tuple[AssertionEvidenceLink, ...]:
        return self.link, self.corrected_link

    def list_provenance_activities(self) -> tuple[ProvenanceActivity, ...]:
        return self.activities

    def list_proposed_changes(self) -> tuple[ProposedChange, ...]:
        return self.changes


def _approval(
    change_id: str, record_id: str, occurred_at: datetime, activity_id: str
) -> ProvenanceActivity:
    return ProvenanceActivity(
        id=activity_id,
        activity_type="proposed_change_approved",
        agent="reviewer",
        input_ids=(change_id,),
        output_ids=(record_id,),
        occurred_at=occurred_at,
    )


def _change(change_id: str, record: Assertion | EvidenceTarget | Relationship) -> ProposedChange:
    return ProposedChange(
        id=change_id,
        review_status=ReviewStatus.APPROVED,
        proposed_json={
            "record_type": type(record).__name__,
            "record": record.model_dump(mode="json"),
        },
        accepted_json=record.model_dump(mode="json"),
        provenance_activity_id="prv_seed",
        created_at=NOW,
        updated_at=NOW,
    )


def _direct_assertion(assertion_id: str) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="is_subject_to_policy",
        object_value="Directive 3000.09",
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=("src_policy",),
        evidence_target_ids=("etg_policy",),
        provenance_activity_ids=("prv_policy",),
        created_at=NOW,
        updated_at=NOW,
    )


def _inference_assertion(assertion_id: str, support_id: str) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
        subject_entity_id="org_anthropic",
        predicate="is_subject_to_policy",
        object_value="Directive 3000.09",
        status=AssertionStatus.CONFIRMED,
        source_authority=SourceAuthority.NOT_APPLICABLE,
        attribution_basis=AttributionBasis.NOT_APPLICABLE,
        supporting_assertion_ids=(support_id,),
        provenance_activity_ids=("prv_inference",),
        created_at=NOW,
        updated_at=NOW,
    )


def test_evidence_graph_resolves_inference_to_validated_direct_evidence() -> None:
    edges, contributions, clusters, dimensions, scores, snapshot = build_evidence_graph_state(
        cast(
            EvidenceGraphStateLedger,
            FakeLedger(validation_status=EvidenceValidationAttemptStatus.SUCCEEDED),
        )
    )

    assert snapshot
    assert edges[0].relationship_id == "rel_policy"
    assert contributions[0].supporting_assertion_id == "ast_inference"
    assert contributions[0].terminal_assertion_ids == ("ast_direct",)
    assert contributions[0].assertion_evidence_link_ids == ("ael_policy",)
    assert contributions[0].validation_attempt_ids == ("eva_policy",)
    assert contributions[0].evidence_target_ids == ("etg_policy",)
    assert contributions[0].source_document_ids == ("doc_policy",)
    assert clusters[0].cross_source_relation_state.value == "no_cross_source_relation_recorded"
    assert {item.value.value for item in dimensions} == {"present", "absent", "unknown"}
    assert scores[0].value.value == "supported"


def test_evidence_graph_rejects_failed_evidence_validation() -> None:
    with raises(EvidenceGraphError) as raised:
        build_evidence_graph_state(
            cast(
                EvidenceGraphStateLedger,
                FakeLedger(validation_status=EvidenceValidationAttemptStatus.FAILED),
            )
        )

    assert raised.value.code is EvidenceGraphFailureCode.EVIDENCE_INVALID


def test_evidence_graph_marks_a_relationship_contested_from_an_accepted_argument_edge() -> None:
    ledger = FakeLedger(validation_status=EvidenceValidationAttemptStatus.SUCCEEDED)
    ledger.argument_edges = (
        ArgumentEdge(
            id="arg_contradicts_policy",
            from_assertion_id=ledger.direct.id,
            to_assertion_id=ledger.inference.id,
            relation=ArgumentEdgeRelation.CONTRADICTS,
            rationale="The source-backed Assertion conflicts with the inference.",
            confidence=0.9,
            created_at=NOW,
        ),
    )

    _, _, _, dimensions, scores, _ = build_evidence_graph_state(
        cast(EvidenceGraphStateLedger, ledger)
    )

    contradiction = next(item for item in dimensions if item.name.value == "contradiction")
    assert contradiction.value.value == "present"
    assert contradiction.input_ids == ("arg_contradicts_policy",)
    assert scores[0].value.value == "contested"


def test_evidence_graph_reconstructs_current_and_as_of_correction_views() -> None:
    ledger = TemporalLedger()

    historical = build_evidence_graph_state(
        cast(EvidenceGraphStateLedger, ledger), as_of=datetime(2026, 8, 20, 12, tzinfo=UTC)
    )
    current = build_evidence_graph_state(cast(EvidenceGraphStateLedger, ledger))

    assert historical[0][0].relationship_id == ledger.initial_relationship.id
    assert historical[1][0].terminal_assertion_ids == (ledger.initial.id,)
    assert current[0][0].relationship_id == ledger.current_relationship.id
    assert current[1][0].terminal_assertion_ids == (ledger.corrected.id,)
    assert historical[3] != current[3]


def test_evidence_graph_historical_view_rejects_missing_acceptance_provenance() -> None:
    ledger = TemporalLedger()
    ledger.changes = tuple(item for item in ledger.changes if item.id != "pcg_initial")

    with raises(EvidenceGraphError) as raised:
        build_evidence_graph_state(
            cast(EvidenceGraphStateLedger, ledger), as_of=datetime(2026, 8, 20, 12, tzinfo=UTC)
        )

    assert raised.value.code is EvidenceGraphFailureCode.TEMPORAL_PROVENANCE_INVALID


def test_reviewed_relation_groups_two_contributing_documents() -> None:
    first = Document(
        id="doc_first",
        source_id="src_first",
        content_sha256="a" * 64,
        created_at=NOW,
        updated_at=NOW,
    )
    second = Document(
        id="doc_second",
        source_id="src_second",
        content_sha256="a" * 64,
        created_at=NOW,
        updated_at=NOW,
    )
    relation = SourceLineageRelation(
        id="slr_contract",
        document_ids=(first.id, second.id),
        relation_type=SourceLineageRelationType.VERBATIM_REPUBLICATION,
        shared_content_sha256="a" * 64,
        rationale="The archived bytes are identical.",
        review_provenance_activity_id="prv_contract",
        reviewed_at=NOW,
    )

    clusters, memberships = build_evidence_graph_lineage_clusters(
        snapshot="b" * 64,
        documents=(first, second),
        lineage_relations=(relation,),
        contributing_document_ids=(first.id, second.id),
    )

    assert clusters[0].document_ids == (first.id, second.id)
    assert clusters[0].source_lineage_relation_ids == (relation.id,)
    assert memberships[first.id].lineage_cluster_id == memberships[second.id].lineage_cluster_id


class StaleProjection:
    def __init__(self) -> None:
        self.manifest = EvidenceGraphProjectionManifest(
            projection_manifest_id="egm_stale",
            source_snapshot_digest="f" * 64,
            projection_policy_id=EVIDENCE_GRAPH_PROJECTION_POLICY_ID,
            builder_version="dr6_1_evidence_graph_projection_v1",
            adapter_identity="test",
            adapter_configuration_digest="a" * 64,
            edge_count=0,
            contribution_count=0,
            lineage_cluster_count=0,
            content_fingerprint="b" * 64,
            publication_status="complete",
            published_at=NOW,
        )
        self.published = 0
        self.records: list[object] = []

    def get_complete_evidence_graph_manifest(
        self, *args: object
    ) -> EvidenceGraphProjectionManifest:
        del args
        return self.manifest

    def publish_evidence_graph(self, build: Any) -> tuple[EvidenceGraphProjectionManifest, bool]:
        self.manifest = cast(EvidenceGraphProjectionManifest, build.manifest)
        self.published += 1
        return self.manifest, False

    def load_evidence_graph_edge(self, *args: object) -> None:
        del args
        return None

    def save_evidence_graph_explanation(self, record: object) -> None:
        self.records.append(record)


class NoopTokenizer:
    tokenizer_id = "test"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input)


class MissingRelationshipProjection:
    def __init__(self, snapshot: str) -> None:
        self.manifest = EvidenceGraphProjectionManifest(
            projection_manifest_id="egm_current",
            source_snapshot_digest=snapshot,
            projection_policy_id=EVIDENCE_GRAPH_PROJECTION_POLICY_ID,
            builder_version="dr6_1_evidence_graph_projection_v1",
            adapter_identity="test",
            adapter_configuration_digest="a" * 64,
            edge_count=0,
            contribution_count=0,
            lineage_cluster_count=0,
            content_fingerprint="b" * 64,
            publication_status="complete",
            published_at=NOW,
        )
        self.records: list[object] = []

    def get_complete_evidence_graph_manifest(
        self, *args: object
    ) -> EvidenceGraphProjectionManifest:
        del args
        return self.manifest

    def load_evidence_graph_edge(
        self, manifest: EvidenceGraphProjectionManifest, relationship_id: str
    ) -> None:
        del manifest, relationship_id
        return None

    def save_evidence_graph_explanation(self, record: object) -> None:
        self.records.append(record)


def test_stale_evidence_graph_manifest_rebuilds_before_explanation() -> None:
    ledger = FakeLedger(validation_status=EvidenceValidationAttemptStatus.SUCCEEDED)
    projection = StaleProjection()

    result = explain_evidence_graph_relationship(
        ExplainEvidenceGraphRelationshipCommand(relationship_id="rel_policy"),
        ledger_repository=cast(EvidenceGraphLedger, ledger),
        projection=cast(EvidenceGraphProjectionPort, projection),
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "failed"
    assert result.failure is EvidenceGraphFailureCode.RELATIONSHIP_NOT_FOUND
    assert projection.published == 1


def test_missing_relationship_records_a_typed_failed_explanation() -> None:
    ledger = FakeLedger(validation_status=EvidenceValidationAttemptStatus.SUCCEEDED)
    _, _, _, _, _, snapshot = build_evidence_graph_state(cast(EvidenceGraphStateLedger, ledger))
    projection = MissingRelationshipProjection(snapshot)

    result = explain_evidence_graph_relationship(
        ExplainEvidenceGraphRelationshipCommand(relationship_id="rel_missing"),
        ledger_repository=cast(EvidenceGraphLedger, ledger),
        projection=cast(EvidenceGraphProjectionPort, projection),
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "failed"
    assert result.failure is EvidenceGraphFailureCode.RELATIONSHIP_NOT_FOUND
    assert result.explanation_id is not None
    assert len(projection.records) == 1
