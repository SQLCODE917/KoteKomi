from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application.document_entity_reconciliation import (
    IdentityDecisionStatus,
    IdentityMatchMethod,
    build_document_entity_reconciliation_preview,
    build_reconciled_document_proposal_plan,
    canonical_document_entity_reconciliation_preview_bytes,
    document_entity_reconciliation_preview_from_bytes,
    normalize_entity_name,
    submit_reconciled_document_proposal_plan,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_proposed_changes import (
    HybridProposalLedger,
    HybridProposalPlan,
    PlannedProposedChange,
    ProposalAdmissionDecision,
    ProposalDisposition,
    build_hybrid_proposal_plan_record,
)
from kotekomi_domain import (
    Actor,
    AssertionType,
    AttributionBasis,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EpistemicScope,
    Event,
    Organization,
    ParseQualityReport,
    ProposedAssertion,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    ReviewStatus,
    SourceAuthority,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 9, 4, tzinfo=UTC)
TEXT = "Anthropic signed. Later Anthropic objected."
REPRESENTATION_ID = "rep_reconciliation"


class _Ledger:
    def __init__(self) -> None:
        self.bundle = _bundle()
        self.proposed_changes: dict[str, ProposedChange] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == REPRESENTATION_ID else None

    def get_actor(self, record_id: str) -> None:
        del record_id
        return None

    def get_organization(self, record_id: str) -> None:
        del record_id
        return None

    def get_event(self, record_id: str) -> None:
        del record_id
        return None

    def get_evidence_target(self, record_id: str) -> object | None:
        return object() if record_id == "etg_support" else None

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.provenance_activities.get(record_id)

    def commit_hybrid_proposal_batch(
        self,
        *,
        provenance_activity: ProvenanceActivity,
        proposed_changes: tuple[ProposedChange, ...],
    ) -> None:
        self.provenance_activities[provenance_activity.id] = provenance_activity
        self.proposed_changes.update({item.id: item for item in proposed_changes})


def test_exact_document_mentions_reconcile_and_rewrite_references() -> None:
    first_id = "org_" + "1" * 24
    second_id = "org_" + "2" * 24
    first = _plan(
        ordinal=1,
        changes=(
            _organization_change(first_id, 0, "Anthropic", "organization"),
            _event_change(first_id),
            _assertion_change(first_id),
        ),
    )
    second = _plan(
        ordinal=2,
        changes=(
            _organization_change(second_id, TEXT.rindex("Anthropic"), "Anthropic", "company"),
        ),
    )
    ledger = cast(HybridProposalLedger, _Ledger())

    preview = build_document_entity_reconciliation_preview((first, second), ledger)
    plan = build_reconciled_document_proposal_plan(preview, (first, second), ledger)

    assert len(preview.clusters) == 1
    cluster = preview.clusters[0]
    assert cluster.preferred_name == "Anthropic"
    assert cluster.observed_organization_types == ("company", "organization")
    assert {item.status for item in preview.decisions} == {IdentityDecisionStatus.CLUSTERED}
    assert len(preview.traces) == 2
    entity_changes = [
        item
        for item in plan.proposed_changes
        if item.proposed_json["record_type"] == "Organization"
    ]
    assert len(entity_changes) == 1
    entity = entity_changes[0]
    organization = Organization.model_validate_json(_canonical_json(entity.proposed_json["record"]))
    assert organization.id == cluster.record_id
    assert organization.organization_type is None
    reconciliation = cast(dict[str, JsonValue], entity.proposed_json["identity_reconciliation"])
    evidence = cast(list[JsonValue], reconciliation["mention_evidence"])
    assert len(evidence) == 2
    event_json = next(
        item.proposed_json
        for item in plan.proposed_changes
        if item.proposed_json["record_type"] == "Event"
    )
    event = Event.model_validate_json(_canonical_json(event_json["record"]))
    assert event.participant_organization_ids == (cluster.record_id,)
    assertion_json = next(
        item.proposed_json
        for item in plan.proposed_changes
        if item.proposed_json["record_type"] == "Assertion"
    )
    assertion = ProposedAssertion.model_validate_json(_canonical_json(assertion_json["record"]))
    assert assertion.object_entity_id == cluster.record_id
    assert assertion.id != "ast_" + "1" * 24


def test_reconciliation_is_order_independent_and_conservative() -> None:
    first = _plan(
        ordinal=1,
        changes=(_organization_change("org_" + "1" * 24, 0, "Anthropic", "company"),),
    )
    second = _plan(
        ordinal=2,
        changes=(
            _organization_change(
                "org_" + "2" * 24,
                TEXT.rindex("Anthropic"),
                "Anthropic",
                "company",
            ),
        ),
    )
    ledger = cast(HybridProposalLedger, _Ledger())

    forward = build_document_entity_reconciliation_preview((first, second), ledger)
    reversed_result = build_document_entity_reconciliation_preview((second, first), ledger)

    assert canonical_document_entity_reconciliation_preview_bytes(
        forward
    ) == canonical_document_entity_reconciliation_preview_bytes(reversed_result)
    assert len(forward.clusters) == 1
    assert normalize_entity_name("  ANTHROPIC\t") == "anthropic"
    assert normalize_entity_name("OpenAI") != normalize_entity_name("Open AI")


def test_conflicting_alias_lineage_remains_a_reviewable_singleton() -> None:
    plan = _plan(
        ordinal=1,
        changes=(
            _organization_change(
                "org_" + "1" * 24,
                0,
                "Anthropic",
                "company",
                reference_status="ambiguous",
            ),
        ),
    )

    preview = build_document_entity_reconciliation_preview(
        (plan,), cast(HybridProposalLedger, _Ledger())
    )

    assert len(preview.clusters) == 1
    assert preview.decisions[0].status is IdentityDecisionStatus.SINGLETON
    assert preview.decisions[0].cluster_id == preview.clusters[0].id
    assert preview.justifications[0].evidence[0].hybrid_lineage["reference_decision_ids"] == [
        "rfd_" + "1" * 24
    ]


def test_actor_and_organization_with_same_label_remain_separate() -> None:
    plan = _plan(
        ordinal=1,
        changes=(
            _actor_change("act_" + "1" * 24, 0, "Anthropic"),
            _organization_change("org_" + "1" * 24, 0, "Anthropic", "company"),
        ),
    )

    preview = build_document_entity_reconciliation_preview(
        (plan,), cast(HybridProposalLedger, _Ledger())
    )

    assert {(item.record_type, item.preferred_name) for item in preview.clusters} == {
        ("Actor", "Anthropic"),
        ("Organization", "Anthropic"),
    }


def test_repeated_actor_mentions_create_one_candidate_identity() -> None:
    plan = _plan(
        ordinal=1,
        changes=(
            _actor_change("act_" + "1" * 24, 0, "Dario Amodei"),
            _actor_change("act_" + "2" * 24, TEXT.rindex("Anthropic"), "Dario Amodei"),
        ),
    )

    preview = build_document_entity_reconciliation_preview(
        (plan,), cast(HybridProposalLedger, _Ledger())
    )

    assert len(preview.clusters) == 1
    assert preview.clusters[0].record_type == "Actor"
    assert preview.clusters[0].preferred_name == "Dario Amodei"
    assert len(preview.decisions) == 2


def test_upstream_resolved_names_use_the_exact_document_match_method() -> None:
    first = _plan(
        ordinal=1,
        changes=(_organization_change("org_" + "1" * 24, 0, "Anthropic", "company"),),
    )
    alias = _plan(
        ordinal=2,
        changes=(
            _organization_change(
                "org_" + "2" * 24,
                TEXT.rindex("Anthropic"),
                "Anthropic",
                "company",
                reference_status="resolved",
            ),
        ),
    )

    preview = build_document_entity_reconciliation_preview(
        (first, alias), cast(HybridProposalLedger, _Ledger())
    )

    assert preview.justifications[0].method is IdentityMatchMethod.EXACT_NORMALIZED_NAME


def test_preview_rejects_tampered_canonical_bytes() -> None:
    plan = _plan(
        ordinal=1,
        changes=(_organization_change("org_" + "1" * 24, 0, "Anthropic", "company"),),
    )
    preview = build_document_entity_reconciliation_preview(
        (plan,), cast(HybridProposalLedger, _Ledger())
    )
    payload = canonical_document_entity_reconciliation_preview_bytes(preview)

    assert document_entity_reconciliation_preview_from_bytes(payload) == preview
    with pytest.raises(ValueError, match="canonical encoding"):
        document_entity_reconciliation_preview_from_bytes(b" " + payload)


def test_preview_rejects_cluster_members_that_disagree_with_justification() -> None:
    plan = _plan(
        ordinal=1,
        changes=(_organization_change("org_" + "1" * 24, 0, "Anthropic", "company"),),
    )
    preview = build_document_entity_reconciliation_preview(
        (plan,), cast(HybridProposalLedger, _Ledger())
    )
    payload = preview.model_dump(mode="json")
    payload["clusters"][0]["member_record_ids"] = ["org_" + "f" * 24]
    payload_without_id = {key: value for key, value in payload.items() if key != "id"}
    payload["id"] = _id("erp", _canonical_json(cast(JsonValue, payload_without_id)))

    with pytest.raises(ValueError, match="does not match its justification evidence"):
        type(preview).model_validate_json(_canonical_json(cast(JsonValue, payload)))


def test_submission_reuses_exact_batch_without_resetting_review_status() -> None:
    parent = _plan(
        ordinal=1,
        changes=(_organization_change("org_" + "1" * 24, 0, "Anthropic", "company"),),
    )
    fake = _Ledger()
    ledger = cast(HybridProposalLedger, fake)
    preview = build_document_entity_reconciliation_preview((parent,), ledger)
    plan = build_reconciled_document_proposal_plan(preview, (parent,), ledger)

    created = submit_reconciled_document_proposal_plan(plan, submitted_at=NOW, ledger=ledger)
    proposal_id = plan.proposed_changes[0].id
    fake.proposed_changes[proposal_id] = fake.proposed_changes[proposal_id].model_copy(
        update={"review_status": ReviewStatus.APPROVED}
    )
    reused = submit_reconciled_document_proposal_plan(plan, submitted_at=NOW, ledger=ledger)

    assert created == "created"
    assert reused == "reused"
    assert fake.proposed_changes[proposal_id].review_status is ReviewStatus.APPROVED
    assert len(fake.provenance_activities) == 1


def _organization_change(
    record_id: str,
    start: int,
    name: str,
    organization_type: str,
    *,
    reference_status: str = "unresolved",
) -> PlannedProposedChange:
    record = Organization(
        id=record_id,
        name=name,
        organization_type=organization_type,
    ).model_dump(mode="json", exclude={"created_at", "updated_at"})
    return _change(
        1 if record_id.endswith("1" * 24) else 2,
        {
            "record_type": "Organization",
            "stable_label": record_id,
            "record": cast(JsonValue, record),
            "evidence": _evidence(start, "Anthropic"),
            "hybrid_lineage": {
                "mention_candidate_id": "mnc_" + record_id[-24:],
                "reference_decision_ids": (
                    [] if reference_status == "unresolved" else ["rfd_" + record_id[-24:]]
                ),
            },
        },
    )


def _actor_change(record_id: str, start: int, name: str) -> PlannedProposedChange:
    record = Actor(id=record_id, name=name).model_dump(
        mode="json", exclude={"created_at", "updated_at"}
    )
    return _change(
        1,
        {
            "record_type": "Actor",
            "stable_label": record_id,
            "record": cast(JsonValue, record),
            "evidence": _evidence(start, "Anthropic"),
            "hybrid_lineage": {
                "mention_candidate_id": "mnc_" + record_id[-24:],
                "reference_decision_ids": [],
            },
        },
    )


def _event_change(organization_id: str) -> PlannedProposedChange:
    event = Event(
        id="evt_" + "1" * 24,
        name="signed [agreement]",
        participant_organization_ids=(organization_id,),
    ).model_dump(mode="json", exclude={"created_at", "updated_at"})
    return _change(
        1,
        {
            "record_type": "Event",
            "stable_label": "evt_" + "1" * 24,
            "record": cast(JsonValue, event),
            "evidence": _evidence(0, "Anthropic signed."),
            "hybrid_lineage": {"hp6_preview_id": "hsp_" + "1" * 24},
        },
    )


def _assertion_change(organization_id: str) -> PlannedProposedChange:
    assertion = ProposedAssertion(
        id="ast_" + "1" * 24,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="evt_" + "1" * 24,
        relation_label="has_argument",
        object_entity_id=organization_id,
        source_authority=SourceAuthority.UNKNOWN,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=("src_fixture",),
        evidence_target_ids=("etg_support",),
    ).model_dump(mode="json", exclude_none=True)
    return _change(
        1,
        {
            "record_type": "Assertion",
            "stable_label": "ast_" + "1" * 24,
            "record": cast(JsonValue, assertion),
            "evidence_links": [],
            "hybrid_lineage": {"hp6_preview_id": "hsp_" + "1" * 24},
        },
    )


def _change(ordinal: int, proposed_json: dict[str, JsonValue]) -> PlannedProposedChange:
    provenance_id = "prv_" + str(ordinal) * 24
    return PlannedProposedChange(
        id=_id("pcg", provenance_id, _canonical_json(proposed_json)),
        proposed_json=proposed_json,
        source_id="src_fixture",
        document_id="doc_fixture",
        provenance_activity_id=provenance_id,
    )


def _plan(ordinal: int, changes: tuple[PlannedProposedChange, ...]) -> HybridProposalPlan:
    proposed_ids = tuple(sorted(item.id for item in changes))
    event_semantic_id = "esn_" + str(ordinal) * 24
    decision = ProposalAdmissionDecision(
        id=_id("pad", event_semantic_id, ProposalDisposition.PROPOSED.value, *proposed_ids),
        event_semantic_id=event_semantic_id,
        disposition=ProposalDisposition.PROPOSED,
        proposed_change_ids=proposed_ids,
    )
    trace = build_extraction_stage_trace(
        trace_run_id=f"fixture:{ordinal}",
        ordinal=0,
        stage_id="hybrid_proposal_admission",
        stage_version="hybrid_proposed_change_v1",
        producer_id="test",
        source_segment_id=f"nod_{ordinal}",
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        configuration={},
        input_payload={},
        output_payload={},
        status=ExtractionStageStatus.COMPLETED,
    )
    return build_hybrid_proposal_plan_record(
        parent_preview_id="hsp_" + str(ordinal) * 24,
        parent_preview_sha256=str(ordinal) * 64,
        representation_id=REPRESENTATION_ID,
        paragraph_node_id=f"nod_{ordinal}",
        provenance_activity_id="prv_" + str(ordinal) * 24,
        decisions=(decision,),
        proposed_changes=tuple(sorted(changes, key=lambda item: item.id)),
        traces=(trace,),
    )


def _evidence(start: int, exact: str) -> dict[str, JsonValue]:
    return {
        "selector_type": "pinned_text",
        "source_id": "src_fixture",
        "document_id": "doc_fixture",
        "exact_text": exact,
        "prefix_text": TEXT[max(0, start - 8) : start],
        "suffix_text": TEXT[start + len(exact) : start + len(exact) + 8],
        "location": {
            "representation_id": REPRESENTATION_ID,
            "text_view_id": "tvw_fixture",
            "start_char": start,
            "end_char": start + len(exact),
            "node_ids": ["nod_1" if start < 18 else "nod_2"],
        },
    }


def _bundle() -> DocumentRepresentationBundle:
    digest = hashlib.sha256(TEXT.encode()).hexdigest()
    view = TextView(
        id="tvw_fixture",
        representation_id=REPRESENTATION_ID,
        kind=TextViewKind.LOGICAL,
        content_digest=digest,
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_root",
        representation_id=REPRESENTATION_ID,
        node_type="document",
        order_index=0,
        text_view_id=view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    first = DocumentNode(
        id="nod_1",
        representation_id=REPRESENTATION_ID,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=view.id,
        start_char=0,
        end_char=18,
    )
    second = DocumentNode(
        id="nod_2",
        representation_id=REPRESENTATION_ID,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=2,
        text_view_id=view.id,
        start_char=18,
        end_char=len(TEXT),
    )
    quality = ParseQualityReport(
        id="pqr_fixture",
        representation_id=REPRESENTATION_ID,
        metric_values={},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=REPRESENTATION_ID,
        document_id="doc_fixture",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_fixture",
        input_blob_digest=digest,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(view,),
                nodes=(root, first, second),
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(view,),
        nodes=(root, first, second),
        quality_report=quality,
    )


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
