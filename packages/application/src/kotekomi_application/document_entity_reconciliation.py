"""HP-9 document-local reconciliation of mention-derived entity proposals."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, cast

from kotekomi_domain import (
    Actor,
    DocumentRepresentationBundle,
    Event,
    Organization,
    ProposedAssertion,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_proposed_changes import (
    HYBRID_PROPOSAL_AGENT,
    HybridProposalArchive,
    HybridProposalLedger,
    HybridProposalPlan,
    PlannedProposedChange,
    canonical_hybrid_proposal_plan_bytes,
    load_hybrid_proposal_plan,
    submit_planned_proposal_batch,
    validate_planned_proposed_changes,
)

DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID = "document_entity_reconciliation_v1"
DOCUMENT_PROPOSAL_PLAN_POLICY_ID = "reconciled_document_proposal_plan_v1"
DOCUMENT_PROPOSAL_ACTIVITY_TYPE = "reconciled_document_proposal_batch_submitted"
_SHA256 = r"^[a-f0-9]{64}$"

type ReconciledRecordType = Literal["Actor", "Organization"]


class IdentityDecisionStatus(StrEnum):
    CLUSTERED = "clustered"
    SINGLETON = "singleton"


class IdentityMatchMethod(StrEnum):
    EXACT_NORMALIZED_NAME = "exact_normalized_name"
    SINGLETON = "singleton"


class ProposalEvidenceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    representation_id: Annotated[str, Field(min_length=1)]
    text_view_id: Annotated[str, Field(min_length=1)]
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(gt=0)]
    node_ids: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_char <= self.start_char or not self.node_ids:
            raise ValueError("Proposal evidence requires a non-empty structural range.")
        _distinct("evidence node IDs", self.node_ids)
        return self


class ProposalEvidenceSelector(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    selector_type: Literal["pinned_text"] = "pinned_text"
    source_id: Annotated[str, Field(min_length=1)]
    document_id: Annotated[str, Field(min_length=1)]
    exact_text: Annotated[str, Field(min_length=1)]
    prefix_text: str
    suffix_text: str
    location: ProposalEvidenceLocation


class ParentProposalPlanReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plan_id: Annotated[str, Field(pattern=r"^hpp_[a-f0-9]{24}$")]
    sha256: Annotated[str, Field(pattern=_SHA256)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]


class EntityMentionEvidence(BaseModel):
    """One mention-derived proposal and all evidence HP-9 received for it."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    proposed_change_id: Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")]
    original_record_id: Annotated[str, Field(pattern=r"^(act|org)_[a-f0-9]{24}$")]
    record_type: ReconciledRecordType
    observed_name: Annotated[str, Field(min_length=1)]
    name_key: Annotated[str, Field(min_length=1)]
    evidence: ProposalEvidenceSelector
    hybrid_lineage: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.name_key != normalize_entity_name(self.observed_name):
            raise ValueError("Entity mention name key does not match its observed name.")
        expected_prefix = "act_" if self.record_type == "Actor" else "org_"
        if not self.original_record_id.startswith(expected_prefix):
            raise ValueError("Entity mention record type does not match its record identity.")
        return self


class IdentityMatchJustification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^imj_[a-f0-9]{24}$")]
    policy_id: Literal["document_entity_reconciliation_v1"] = (
        DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID
    )
    method: IdentityMatchMethod
    name_key: Annotated[str, Field(min_length=1)]
    proposed_change_ids: tuple[Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")], ...]
    evidence: tuple[EntityMentionEvidence, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.evidence:
            raise ValueError("Identity justification requires source evidence.")
        _ordered_distinct("justification ProposedChange IDs", self.proposed_change_ids)
        if self.proposed_change_ids != tuple(item.proposed_change_id for item in self.evidence):
            raise ValueError("Identity justification inputs do not match its evidence.")
        if any(item.name_key != self.name_key for item in self.evidence):
            raise ValueError("Identity justification evidence has conflicting name keys.")
        if len({item.record_type for item in self.evidence}) != 1:
            raise ValueError("Identity justification evidence mixes record types.")
        expected_method = (
            IdentityMatchMethod.EXACT_NORMALIZED_NAME
            if len(self.evidence) > 1
            else IdentityMatchMethod.SINGLETON
        )
        if self.method is not expected_method:
            raise ValueError("Identity justification method does not match its evidence.")
        expected = _id(
            "imj",
            self.policy_id,
            self.method.value,
            self.name_key,
            *self.proposed_change_ids,
        )
        if self.id != expected:
            raise ValueError("Identity match justification ID does not match its contents.")
        return self


class EntityIdentityCluster(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^eic_[a-f0-9]{24}$")]
    representation_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["document_entity_reconciliation_v1"] = (
        DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID
    )
    record_type: ReconciledRecordType
    record_id: Annotated[str, Field(pattern=r"^(act|org)_[a-f0-9]{24}$")]
    name_key: Annotated[str, Field(min_length=1)]
    preferred_name: Annotated[str, Field(min_length=1)]
    observed_names: tuple[Annotated[str, Field(min_length=1)], ...]
    observed_organization_types: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    member_proposed_change_ids: tuple[Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")], ...]
    member_record_ids: tuple[Annotated[str, Field(pattern=r"^(act|org)_[a-f0-9]{24}$")], ...]
    justification_id: Annotated[str, Field(pattern=r"^imj_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("observed names", self.observed_names),
            ("observed Organization types", self.observed_organization_types),
            ("member ProposedChange IDs", self.member_proposed_change_ids),
            ("member record IDs", self.member_record_ids),
        ):
            _ordered_distinct(label, values)
        if self.preferred_name not in self.observed_names:
            raise ValueError("Entity cluster preferred name must be observed in source evidence.")
        if not self.member_proposed_change_ids or not self.member_record_ids:
            raise ValueError("Entity cluster requires at least one member.")
        if self.record_type == "Actor" and self.observed_organization_types:
            raise ValueError("Actor clusters cannot contain Organization type observations.")
        prefix = "act" if self.record_type == "Actor" else "org"
        expected_record_id = _id(
            prefix,
            self.representation_id,
            self.record_type,
            self.policy_id,
            self.name_key,
        )
        if self.record_id != expected_record_id:
            raise ValueError("Entity cluster record ID does not match its deterministic key.")
        expected_id = _id(
            "eic",
            self.representation_id,
            self.record_type,
            self.policy_id,
            self.name_key,
        )
        if self.id != expected_id:
            raise ValueError("Entity identity cluster ID does not match its deterministic key.")
        return self


class EntityIdentityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^eid_[a-f0-9]{24}$")]
    proposed_change_id: Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")]
    original_record_id: Annotated[str, Field(pattern=r"^(act|org)_[a-f0-9]{24}$")]
    cluster_id: Annotated[str, Field(pattern=r"^eic_[a-f0-9]{24}$")]
    reconciled_record_id: Annotated[str, Field(pattern=r"^(act|org)_[a-f0-9]{24}$")]
    justification_id: Annotated[str, Field(pattern=r"^imj_[a-f0-9]{24}$")]
    status: IdentityDecisionStatus

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        expected = _id(
            "eid",
            self.proposed_change_id,
            self.original_record_id,
            self.cluster_id,
            self.reconciled_record_id,
            self.justification_id,
            self.status.value,
        )
        if self.id != expected:
            raise ValueError("Entity identity decision ID does not match its contents.")
        return self


class DocumentEntityReconciliationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["document_entity_reconciliation_preview_v1"] = (
        "document_entity_reconciliation_preview_v1"
    )
    id: Annotated[str, Field(pattern=r"^erp_[a-f0-9]{24}$")]
    representation_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["document_entity_reconciliation_v1"] = (
        DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID
    )
    parent_plans: tuple[ParentProposalPlanReference, ...]
    clusters: tuple[EntityIdentityCluster, ...]
    decisions: tuple[EntityIdentityDecision, ...]
    justifications: tuple[IdentityMatchJustification, ...]
    traces: tuple[ExtractionStageTrace, ...]
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("parent Plan IDs", tuple(item.plan_id for item in self.parent_plans))
        _ordered_distinct("cluster IDs", tuple(item.id for item in self.clusters))
        _ordered_distinct("decision IDs", tuple(item.id for item in self.decisions))
        _ordered_distinct("justification IDs", tuple(item.id for item in self.justifications))
        _ordered_distinct("trace IDs", tuple(item.id for item in self.traces))
        _ordered_distinct("diagnostics", self.diagnostics)
        cluster_ids = {item.id for item in self.clusters}
        justification_ids = {item.id for item in self.justifications}
        _ordered_distinct(
            "decision ProposedChange IDs",
            tuple(sorted(item.proposed_change_id for item in self.decisions)),
        )
        if any(item.cluster_id not in cluster_ids for item in self.decisions):
            raise ValueError("Entity decision references a missing cluster.")
        if any(item.justification_id not in justification_ids for item in self.decisions):
            raise ValueError("Entity decision references a missing justification.")
        if len(self.decisions) != len(self.traces):
            raise ValueError("Every Entity Identity Decision requires one stage trace.")
        traced_decision_ids = {
            decision_id
            for trace in self.traces
            if isinstance((raw := trace.output.get("decision")), dict)
            and isinstance((decision_id := raw.get("id")), str)
        }
        if traced_decision_ids != {item.id for item in self.decisions}:
            raise ValueError("HP-9 stage traces do not cover every identity decision.")
        clustered_proposal_ids = {
            item for cluster in self.clusters for item in cluster.member_proposed_change_ids
        }
        if clustered_proposal_ids != {item.proposed_change_id for item in self.decisions}:
            raise ValueError("HP-9 clusters and identity decisions cover different inputs.")
        decisions_by_cluster: dict[str, list[EntityIdentityDecision]] = defaultdict(list)
        for decision in self.decisions:
            decisions_by_cluster[decision.cluster_id].append(decision)
        justification_by_id = {item.id: item for item in self.justifications}
        trace_by_decision_id: dict[str, ExtractionStageTrace] = {}
        for trace in self.traces:
            raw_decision = trace.output.get("decision")
            if not isinstance(raw_decision, dict):
                raise ValueError("HP-9 stage trace is missing its identity decision.")
            parsed_decision = EntityIdentityDecision.model_validate_json(
                _canonical_json(raw_decision)
            )
            trace_by_decision_id[parsed_decision.id] = trace
        for cluster in self.clusters:
            justification = justification_by_id.get(cluster.justification_id)
            if justification is None:
                raise ValueError("Entity cluster references a missing justification.")
            decisions = tuple(
                sorted(
                    decisions_by_cluster.get(cluster.id, ()),
                    key=lambda item: item.proposed_change_id,
                )
            )
            evidence = justification.evidence
            if (
                justification.name_key != cluster.name_key
                or justification.proposed_change_ids != cluster.member_proposed_change_ids
                or tuple(sorted({item.observed_name for item in evidence}))
                != cluster.observed_names
                or tuple(sorted({item.original_record_id for item in evidence}))
                != cluster.member_record_ids
                or any(item.record_type != cluster.record_type for item in evidence)
            ):
                raise ValueError("Entity cluster does not match its justification evidence.")
            if (
                tuple(item.proposed_change_id for item in decisions)
                != cluster.member_proposed_change_ids
            ):
                raise ValueError("Entity cluster does not have one decision per member.")
            for decision in decisions:
                if (
                    decision.original_record_id
                    != next(
                        item.original_record_id
                        for item in evidence
                        if item.proposed_change_id == decision.proposed_change_id
                    )
                    or decision.reconciled_record_id != cluster.record_id
                    or decision.justification_id != justification.id
                ):
                    raise ValueError("Entity identity decision conflicts with its cluster.")
                trace = trace_by_decision_id[decision.id]
                raw_decision = trace.output.get("decision")
                raw_justification = trace.output.get("justification")
                if (
                    not isinstance(raw_decision, dict)
                    or EntityIdentityDecision.model_validate_json(_canonical_json(raw_decision))
                    != decision
                    or not isinstance(raw_justification, dict)
                    or IdentityMatchJustification.model_validate_json(
                        _canonical_json(raw_justification)
                    )
                    != justification
                ):
                    raise ValueError("HP-9 stage trace does not replay its decision evidence.")
        for trace in self.traces:
            validate_extraction_stage_trace_chain((trace,))
        expected = _content_id("erp", self.model_dump(mode="json", exclude={"id"}))
        if self.id != expected:
            raise ValueError("Document reconciliation Preview ID does not match its contents.")
        return self


class ReconciledDocumentProposalPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["reconciled_document_proposal_plan_v1"] = (
        "reconciled_document_proposal_plan_v1"
    )
    id: Annotated[str, Field(pattern=r"^rdp_[a-f0-9]{24}$")]
    representation_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["reconciled_document_proposal_plan_v1"] = DOCUMENT_PROPOSAL_PLAN_POLICY_ID
    parent_preview_id: Annotated[str, Field(pattern=r"^erp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    parent_plans: tuple[ParentProposalPlanReference, ...]
    provenance_activity_id: Annotated[str, Field(pattern=r"^prv_[a-f0-9]{24}$")]
    proposed_changes: tuple[PlannedProposedChange, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("parent Plan IDs", tuple(item.plan_id for item in self.parent_plans))
        _ordered_distinct(
            "planned ProposedChange IDs", tuple(item.id for item in self.proposed_changes)
        )
        if any(
            item.provenance_activity_id != self.provenance_activity_id
            for item in self.proposed_changes
        ):
            raise ValueError("Document Plan changes must share one provenance activity.")
        expected = _content_id("rdp", self.model_dump(mode="json", exclude={"id"}))
        if self.id != expected:
            raise ValueError("Reconciled Document Proposal Plan ID does not match its contents.")
        return self


class DocumentEntityReconciliationArchive(HybridProposalArchive, Protocol):
    def put_document_entity_reconciliation_preview(
        self,
        preview: DocumentEntityReconciliationPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_document_entity_reconciliation_preview(self, preview_id: str) -> bytes: ...

    def put_reconciled_document_proposal_plan(
        self,
        plan: ReconciledDocumentProposalPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_reconciled_document_proposal_plan(self, plan_id: str) -> bytes: ...


def normalize_entity_name(value: str) -> str:
    """Return the deliberately conservative HP-9 exact-name key."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def build_document_entity_reconciliation_preview(
    plans: tuple[HybridProposalPlan, ...],
    ledger: HybridProposalLedger,
    *,
    representation_id: str | None = None,
) -> DocumentEntityReconciliationPreview:
    """Reconcile document-local Actor and Organization proposals without Ledger writes."""
    parent_plans = _parent_plan_references(plans)
    representation_id = _representation_id(plans, expected=representation_id)
    bundle = ledger.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError("HP-9 authoritative DocumentRepresentationBundle is missing.")
    raw_changes = tuple(_unique_raw_changes(plans).values())
    if any(item.document_id != bundle.representation.document_id for item in raw_changes):
        raise ValueError("HP-9 parent Plan contains a foreign Document proposal.")
    if len({item.source_id for item in raw_changes}) > 1:
        raise ValueError("HP-9 parent Plans contain proposals from multiple Sources.")
    occurrences = _entity_occurrences(plans, bundle)
    grouped: dict[tuple[ReconciledRecordType, str], list[EntityMentionEvidence]] = defaultdict(list)
    for occurrence in occurrences:
        grouped[(occurrence.record_type, occurrence.name_key)].append(occurrence)
    clusters: list[EntityIdentityCluster] = []
    decisions: list[EntityIdentityDecision] = []
    justifications: list[IdentityMatchJustification] = []
    traces: list[ExtractionStageTrace] = []
    for (record_type, name_key), members_list in sorted(grouped.items()):
        members = tuple(sorted(members_list, key=_mention_sort_key))
        method = _match_method(members)
        proposed_change_ids = tuple(sorted(item.proposed_change_id for item in members))
        justification = IdentityMatchJustification(
            id=_id(
                "imj",
                DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID,
                method.value,
                name_key,
                *proposed_change_ids,
            ),
            method=method,
            name_key=name_key,
            proposed_change_ids=proposed_change_ids,
            evidence=tuple(sorted(members, key=lambda item: item.proposed_change_id)),
        )
        prefix = "act" if record_type == "Actor" else "org"
        record_id = _id(
            prefix,
            representation_id,
            record_type,
            DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID,
            name_key,
        )
        cluster_id = _id(
            "eic",
            representation_id,
            record_type,
            DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID,
            name_key,
        )
        observed_types = _observed_organization_types(plans, proposed_change_ids)
        cluster = EntityIdentityCluster(
            id=cluster_id,
            representation_id=representation_id,
            record_type=record_type,
            record_id=record_id,
            name_key=name_key,
            preferred_name=members[0].observed_name,
            observed_names=tuple(sorted({item.observed_name for item in members})),
            observed_organization_types=observed_types,
            member_proposed_change_ids=proposed_change_ids,
            member_record_ids=tuple(sorted({item.original_record_id for item in members})),
            justification_id=justification.id,
        )
        clusters.append(cluster)
        justifications.append(justification)
        for member in sorted(members, key=lambda item: item.proposed_change_id):
            status = _decision_status(member, len(members))
            decision = EntityIdentityDecision(
                id=_id(
                    "eid",
                    member.proposed_change_id,
                    member.original_record_id,
                    cluster.id,
                    cluster.record_id,
                    justification.id,
                    status.value,
                ),
                proposed_change_id=member.proposed_change_id,
                original_record_id=member.original_record_id,
                cluster_id=cluster.id,
                reconciled_record_id=cluster.record_id,
                justification_id=justification.id,
                status=status,
            )
            decisions.append(decision)
            traces.append(_decision_trace(decision, member, cluster, justification))
    payload: dict[str, JsonValue] = {
        "schema_version": "document_entity_reconciliation_preview_v1",
        "representation_id": representation_id,
        "policy_id": DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID,
        "parent_plans": [cast(JsonValue, item.model_dump(mode="json")) for item in parent_plans],
        "clusters": [
            cast(JsonValue, item.model_dump(mode="json"))
            for item in sorted(clusters, key=lambda x: x.id)
        ],
        "decisions": [
            cast(JsonValue, item.model_dump(mode="json"))
            for item in sorted(decisions, key=lambda x: x.id)
        ],
        "justifications": [
            cast(JsonValue, item.model_dump(mode="json"))
            for item in sorted(justifications, key=lambda x: x.id)
        ],
        "traces": [
            cast(JsonValue, item.model_dump(mode="json"))
            for item in sorted(traces, key=lambda x: x.id)
        ],
        "diagnostics": [],
    }
    return DocumentEntityReconciliationPreview.model_validate(
        {
            **payload,
            "id": _content_id("erp", payload),
            "parent_plans": parent_plans,
            "clusters": tuple(sorted(clusters, key=lambda item: item.id)),
            "decisions": tuple(sorted(decisions, key=lambda item: item.id)),
            "justifications": tuple(sorted(justifications, key=lambda item: item.id)),
            "traces": tuple(sorted(traces, key=lambda item: item.id)),
            "diagnostics": (),
        }
    )


def build_reconciled_document_proposal_plan(
    preview: DocumentEntityReconciliationPreview,
    plans: tuple[HybridProposalPlan, ...],
    ledger: HybridProposalLedger,
) -> ReconciledDocumentProposalPlan:
    """Rewrite paragraph Plans into one globally referentially valid review batch."""
    if preview != build_document_entity_reconciliation_preview(
        plans, ledger, representation_id=preview.representation_id
    ):
        raise ValueError("HP-9 Preview does not match its parent Plans.")
    raw_changes = _unique_raw_changes(plans)
    cluster_by_member = {
        proposed_change_id: cluster
        for cluster in preview.clusters
        for proposed_change_id in cluster.member_proposed_change_ids
    }
    record_mapping: dict[str, str] = {}
    for decision in preview.decisions:
        prior = record_mapping.setdefault(
            decision.original_record_id, decision.reconciled_record_id
        )
        if prior != decision.reconciled_record_id:
            raise ValueError("HP-9 assigned one original record to conflicting clusters.")
    provenance_id = _id("prv", DOCUMENT_PROPOSAL_ACTIVITY_TYPE, preview.id)
    final_changes: list[PlannedProposedChange] = []
    for cluster in preview.clusters:
        members = tuple(raw_changes[item] for item in cluster.member_proposed_change_ids)
        proposed_json = _cluster_proposed_json(cluster, members, preview, record_mapping)
        final_changes.append(_planned_change(provenance_id, members[0], proposed_json))
    for change in raw_changes.values():
        record_type = change.proposed_json.get("record_type")
        if record_type in {"Actor", "Organization"}:
            if change.id not in cluster_by_member:
                raise ValueError("HP-9 lost one named-entity proposal during reconciliation.")
            continue
        proposed_json = _rewrite_non_entity_proposal(change, record_mapping, preview.id)
        final_changes.append(_planned_change(provenance_id, change, proposed_json))
    planned = tuple(sorted(final_changes, key=lambda item: item.id))
    validate_planned_proposed_changes(planned, ledger, error_label="HP-9 Document Plan")
    preview_bytes = canonical_document_entity_reconciliation_preview_bytes(preview)
    payload: dict[str, JsonValue] = {
        "schema_version": "reconciled_document_proposal_plan_v1",
        "representation_id": preview.representation_id,
        "policy_id": DOCUMENT_PROPOSAL_PLAN_POLICY_ID,
        "parent_preview_id": preview.id,
        "parent_preview_sha256": hashlib.sha256(preview_bytes).hexdigest(),
        "parent_plans": [
            cast(JsonValue, item.model_dump(mode="json")) for item in preview.parent_plans
        ],
        "provenance_activity_id": provenance_id,
        "proposed_changes": [cast(JsonValue, item.model_dump(mode="json")) for item in planned],
    }
    return ReconciledDocumentProposalPlan.model_validate(
        {
            **payload,
            "id": _content_id("rdp", payload),
            "parent_plans": preview.parent_plans,
            "proposed_changes": planned,
        }
    )


def publish_document_entity_reconciliation_preview(
    preview: DocumentEntityReconciliationPreview,
    archive: DocumentEntityReconciliationArchive,
) -> tuple[str, str]:
    payload = canonical_document_entity_reconciliation_preview_bytes(preview)
    digest = hashlib.sha256(payload).hexdigest()
    archive.put_document_entity_reconciliation_preview(preview, payload, digest)
    return digest, f"extraction/entity-reconciliation-previews/{preview.id}.json"


def publish_reconciled_document_proposal_plan(
    plan: ReconciledDocumentProposalPlan,
    archive: DocumentEntityReconciliationArchive,
) -> tuple[str, str]:
    payload = canonical_reconciled_document_proposal_plan_bytes(plan)
    digest = hashlib.sha256(payload).hexdigest()
    archive.put_reconciled_document_proposal_plan(plan, payload, digest)
    return digest, f"extraction/document-proposal-plans/{plan.id}.json"


def submit_reconciled_document_proposal_plan(
    plan: ReconciledDocumentProposalPlan,
    *,
    submitted_at: datetime,
    ledger: HybridProposalLedger,
) -> str:
    return submit_planned_proposal_batch(
        proposed_changes=plan.proposed_changes,
        provenance_activity_id=plan.provenance_activity_id,
        activity_type=DOCUMENT_PROPOSAL_ACTIVITY_TYPE,
        input_ids=(plan.parent_preview_id,),
        submitted_at=submitted_at,
        ledger=ledger,
        error_label="HP-9",
    )


def load_document_entity_reconciliation_preview(
    preview_id: str,
    *,
    ledger: HybridProposalLedger,
    archive: DocumentEntityReconciliationArchive,
) -> DocumentEntityReconciliationPreview:
    payload = archive.read_document_entity_reconciliation_preview(preview_id)
    preview = document_entity_reconciliation_preview_from_bytes(payload)
    plans = tuple(
        load_hybrid_proposal_plan(item.plan_id, ledger, archive) for item in preview.parent_plans
    )
    if preview != build_document_entity_reconciliation_preview(
        plans, ledger, representation_id=preview.representation_id
    ):
        raise ValueError("Stored HP-9 Preview no longer matches its parent evidence.")
    return preview


def load_reconciled_document_proposal_plan(
    plan_id: str,
    *,
    ledger: HybridProposalLedger,
    archive: DocumentEntityReconciliationArchive,
) -> ReconciledDocumentProposalPlan:
    payload = archive.read_reconciled_document_proposal_plan(plan_id)
    plan = reconciled_document_proposal_plan_from_bytes(payload)
    preview = load_document_entity_reconciliation_preview(
        plan.parent_preview_id, ledger=ledger, archive=archive
    )
    plans = tuple(
        load_hybrid_proposal_plan(item.plan_id, ledger, archive) for item in plan.parent_plans
    )
    if plan != build_reconciled_document_proposal_plan(preview, plans, ledger):
        raise ValueError("Stored HP-9 Document Plan no longer matches its parent evidence.")
    return plan


def canonical_document_entity_reconciliation_preview_bytes(
    preview: DocumentEntityReconciliationPreview,
) -> bytes:
    return (_canonical_json(preview.model_dump(mode="json")) + "\n").encode()


def document_entity_reconciliation_preview_from_bytes(
    payload: bytes,
) -> DocumentEntityReconciliationPreview:
    return _parse_canonical(payload, DocumentEntityReconciliationPreview, "HP-9 Preview")


def canonical_reconciled_document_proposal_plan_bytes(
    plan: ReconciledDocumentProposalPlan,
) -> bytes:
    return (_canonical_json(plan.model_dump(mode="json")) + "\n").encode()


def reconciled_document_proposal_plan_from_bytes(
    payload: bytes,
) -> ReconciledDocumentProposalPlan:
    return _parse_canonical(payload, ReconciledDocumentProposalPlan, "HP-9 Document Plan")


def _parent_plan_references(
    plans: tuple[HybridProposalPlan, ...],
) -> tuple[ParentProposalPlanReference, ...]:
    references = tuple(
        sorted(
            (
                ParentProposalPlanReference(
                    plan_id=plan.id,
                    sha256=hashlib.sha256(canonical_hybrid_proposal_plan_bytes(plan)).hexdigest(),
                    paragraph_node_id=plan.paragraph_node_id,
                )
                for plan in plans
            ),
            key=lambda item: item.plan_id,
        )
    )
    if len({item.plan_id for item in references}) != len(references):
        raise ValueError("HP-9 parent Plans must be distinct.")
    if len({item.paragraph_node_id for item in references}) != len(references):
        raise ValueError("HP-9 parent Plans must cover distinct paragraphs.")
    return references


def _representation_id(plans: tuple[HybridProposalPlan, ...], *, expected: str | None) -> str:
    values = {item.representation_id for item in plans}
    if not values and expected is not None:
        return expected
    if len(values) != 1:
        raise ValueError("HP-9 requires parent Plans for exactly one representation.")
    actual = next(iter(values))
    if expected is not None and actual != expected:
        raise ValueError("HP-9 parent Plans do not match the expected representation.")
    return actual


def _unique_raw_changes(
    plans: tuple[HybridProposalPlan, ...],
) -> dict[str, PlannedProposedChange]:
    changes: dict[str, PlannedProposedChange] = {}
    for plan in plans:
        for change in plan.proposed_changes:
            prior = changes.get(change.id)
            if prior is not None and prior != change:
                raise ValueError("HP-9 parent Plans conflict for one ProposedChange ID.")
            changes[change.id] = change
    return dict(sorted(changes.items()))


def _entity_occurrences(
    plans: tuple[HybridProposalPlan, ...],
    bundle: DocumentRepresentationBundle,
) -> tuple[EntityMentionEvidence, ...]:
    occurrences: list[EntityMentionEvidence] = []
    for change in _unique_raw_changes(plans).values():
        record_type = change.proposed_json.get("record_type")
        if record_type not in {"Actor", "Organization"}:
            continue
        record_payload = change.proposed_json.get("record")
        if not isinstance(record_payload, dict):
            raise ValueError("HP-9 named-entity proposal is missing its record body.")
        record = (
            Actor.model_validate_json(_canonical_json(record_payload))
            if record_type == "Actor"
            else Organization.model_validate_json(_canonical_json(record_payload))
        )
        evidence = ProposalEvidenceSelector.model_validate_json(
            _canonical_json(change.proposed_json.get("evidence"))
        )
        _validate_selector(evidence, bundle)
        if evidence.source_id != change.source_id or evidence.document_id != change.document_id:
            raise ValueError("HP-9 evidence does not belong to its ProposedChange.")
        if evidence.document_id != bundle.representation.document_id:
            raise ValueError("HP-9 evidence belongs to a foreign Document.")
        lineage = change.proposed_json.get("hybrid_lineage")
        if not isinstance(lineage, dict):
            raise ValueError("HP-9 named-entity proposal is missing Hybrid lineage.")
        mention_id = lineage.get("mention_candidate_id")
        if not isinstance(mention_id, str) or not mention_id:
            raise ValueError("HP-9 Hybrid lineage is missing its MentionCandidate.")
        occurrences.append(
            EntityMentionEvidence(
                proposed_change_id=change.id,
                original_record_id=record.id,
                record_type=cast(ReconciledRecordType, record_type),
                observed_name=record.name,
                name_key=normalize_entity_name(record.name),
                evidence=evidence,
                hybrid_lineage=lineage,
            )
        )
    return tuple(sorted(occurrences, key=lambda item: item.proposed_change_id))


def _mention_sort_key(item: EntityMentionEvidence) -> tuple[str, int, int, str]:
    location = item.evidence.location
    return (location.text_view_id, location.start_char, location.end_char, item.proposed_change_id)


def _match_method(members: tuple[EntityMentionEvidence, ...]) -> IdentityMatchMethod:
    if len(members) > 1:
        return IdentityMatchMethod.EXACT_NORMALIZED_NAME
    return IdentityMatchMethod.SINGLETON


def _decision_status(member: EntityMentionEvidence, member_count: int) -> IdentityDecisionStatus:
    del member
    if member_count > 1:
        return IdentityDecisionStatus.CLUSTERED
    return IdentityDecisionStatus.SINGLETON


def _observed_organization_types(
    plans: tuple[HybridProposalPlan, ...], proposal_ids: tuple[str, ...]
) -> tuple[str, ...]:
    changes = _unique_raw_changes(plans)
    values: set[str] = set()
    for proposal_id in proposal_ids:
        change = changes[proposal_id]
        if change.proposed_json.get("record_type") != "Organization":
            continue
        record = Organization.model_validate_json(
            _canonical_json(change.proposed_json.get("record"))
        )
        if record.organization_type is not None:
            values.add(record.organization_type)
    return tuple(sorted(values))


def _decision_trace(
    decision: EntityIdentityDecision,
    member: EntityMentionEvidence,
    cluster: EntityIdentityCluster,
    justification: IdentityMatchJustification,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=f"hp9:{cluster.representation_id}",
        ordinal=0,
        stage_id="document_entity_reconciliation",
        stage_version=DOCUMENT_ENTITY_RECONCILIATION_POLICY_ID,
        producer_id=HYBRID_PROPOSAL_AGENT,
        source_segment_id=member.evidence.location.node_ids[0],
        source_text_sha256=hashlib.sha256(member.evidence.exact_text.encode()).hexdigest(),
        configuration=cast(
            dict[str, JsonValue],
            {
                "name_normalization": ["unicode_nfc", "casefold", "whitespace_collapse"],
                "preserve_punctuation": True,
                "scope": "document_local",
            },
        ),
        input_payload={
            "mention": cast(JsonValue, member.model_dump(mode="json")),
            "cluster_member_proposed_change_ids": list(cluster.member_proposed_change_ids),
        },
        output_payload={
            "decision": cast(JsonValue, decision.model_dump(mode="json")),
            "justification": cast(JsonValue, justification.model_dump(mode="json")),
        },
        status=ExtractionStageStatus.COMPLETED,
        input_record_ids=tuple(sorted((member.proposed_change_id, member.original_record_id))),
    )


def _cluster_proposed_json(
    cluster: EntityIdentityCluster,
    members: tuple[PlannedProposedChange, ...],
    preview: DocumentEntityReconciliationPreview,
    record_mapping: dict[str, str],
) -> dict[str, JsonValue]:
    evidence_by_proposal = {
        item.proposed_change_id: item.evidence
        for justification in preview.justifications
        for item in justification.evidence
    }
    member_evidence = tuple(
        sorted(
            (evidence_by_proposal[item.id] for item in members),
            key=lambda item: (
                item.location.text_view_id,
                item.location.start_char,
                item.location.end_char,
            ),
        )
    )
    if cluster.record_type == "Actor":
        records = tuple(
            Actor.model_validate_json(_canonical_json(item.proposed_json["record"]))
            for item in members
        )
        record = Actor(
            id=cluster.record_id,
            name=cluster.preferred_name,
            role_names=tuple(sorted({role for item in records for role in item.role_names})),
            organization_ids=tuple(
                sorted(
                    {
                        organization_id
                        for item in records
                        for organization_id in item.organization_ids
                    }
                )
            ),
        )
        record = record.model_copy(
            update={
                "organization_ids": tuple(
                    sorted({record_mapping.get(item, item) for item in record.organization_ids})
                )
            }
        )
    else:
        organization_type = (
            cluster.observed_organization_types[0]
            if len(cluster.observed_organization_types) == 1
            else None
        )
        record = Organization(
            id=cluster.record_id,
            name=cluster.preferred_name,
            organization_type=organization_type,
        )
    record_json = cast(
        dict[str, JsonValue], record.model_dump(mode="json", exclude={"created_at", "updated_at"})
    )
    decisions = tuple(item for item in preview.decisions if item.cluster_id == cluster.id)
    lineages = tuple(
        {
            "proposed_change_id": item.id,
            "hybrid_lineage": cast(dict[str, JsonValue], item.proposed_json["hybrid_lineage"]),
        }
        for item in members
    )
    return cast(
        dict[str, JsonValue],
        {
            "record_type": cluster.record_type,
            "stable_label": cluster.record_id,
            "record": record_json,
            "evidence": cast(JsonValue, member_evidence[0].model_dump(mode="json")),
            "identity_reconciliation": {
                "preview_id": preview.id,
                "cluster_id": cluster.id,
                "justification_id": cluster.justification_id,
                "decision_ids": sorted(item.id for item in decisions),
                "member_proposed_change_ids": list(cluster.member_proposed_change_ids),
                "member_record_ids": list(cluster.member_record_ids),
                "mention_evidence": [
                    cast(JsonValue, item.model_dump(mode="json")) for item in member_evidence
                ],
                "member_hybrid_lineage": list(lineages),
                "observed_names": list(cluster.observed_names),
                "observed_organization_types": list(cluster.observed_organization_types),
            },
        },
    )


def _rewrite_non_entity_proposal(
    change: PlannedProposedChange,
    record_mapping: dict[str, str],
    preview_id: str,
) -> dict[str, JsonValue]:
    proposed = cast(dict[str, JsonValue], json.loads(_canonical_json(change.proposed_json)))
    record_type = proposed.get("record_type")
    record = proposed.get("record")
    if not isinstance(record, dict):
        raise ValueError("HP-9 non-entity proposal is missing its record body.")
    applied_mapping: dict[str, str] = {}
    if record_type == "Event":
        event = Event.model_validate_json(_canonical_json(record))
        referenced_ids = (*event.participant_actor_ids, *event.participant_organization_ids)
        applied_mapping = {
            item: record_mapping[item]
            for item in referenced_ids
            if item in record_mapping and record_mapping[item] != item
        }
        event = event.model_copy(
            update={
                "participant_actor_ids": tuple(
                    sorted({record_mapping.get(item, item) for item in event.participant_actor_ids})
                ),
                "participant_organization_ids": tuple(
                    sorted(
                        {
                            record_mapping.get(item, item)
                            for item in event.participant_organization_ids
                        }
                    )
                ),
            }
        )
        proposed["record"] = cast(
            JsonValue, event.model_dump(mode="json", exclude={"created_at", "updated_at"})
        )
    elif record_type == "Assertion":
        assertion = ProposedAssertion.model_validate_json(_canonical_json(record))
        referenced_ids = (
            assertion.subject_entity_id,
            *((assertion.object_entity_id,) if assertion.object_entity_id is not None else ()),
        )
        applied_mapping = {
            item: record_mapping[item]
            for item in referenced_ids
            if item in record_mapping and record_mapping[item] != item
        }
        update: dict[str, object] = {
            "subject_entity_id": record_mapping.get(
                assertion.subject_entity_id, assertion.subject_entity_id
            ),
            "object_entity_id": (
                record_mapping.get(assertion.object_entity_id, assertion.object_entity_id)
                if assertion.object_entity_id is not None
                else None
            ),
        }
        rewritten = assertion.model_copy(update=update)
        if applied_mapping:
            assertion_id = _id(
                "ast",
                rewritten.subject_entity_id,
                rewritten.relation_label,
                rewritten.object_entity_id or _canonical_json(rewritten.object_value),
                _canonical_json(rewritten.qualifiers),
                *rewritten.evidence_target_ids,
            )
            rewritten = rewritten.model_copy(update={"id": assertion_id})
        proposed["record"] = cast(JsonValue, rewritten.model_dump(mode="json", exclude_none=True))
        proposed["stable_label"] = rewritten.id
    else:
        raise ValueError(f"HP-9 does not support proposal record type: {record_type}")
    proposed["identity_reconciliation"] = {
        "preview_id": preview_id,
        "parent_proposed_change_id": change.id,
        "rewritten_record_ids": dict(sorted(applied_mapping.items())),
    }
    return proposed


def _planned_change(
    provenance_activity_id: str,
    parent: PlannedProposedChange,
    proposed_json: dict[str, JsonValue],
) -> PlannedProposedChange:
    return PlannedProposedChange(
        id=_id("pcg", provenance_activity_id, _canonical_json(proposed_json)),
        proposed_json=proposed_json,
        source_id=parent.source_id,
        document_id=parent.document_id,
        provenance_activity_id=provenance_activity_id,
    )


def _validate_selector(
    evidence: ProposalEvidenceSelector,
    bundle: DocumentRepresentationBundle,
) -> None:
    location = evidence.location
    if location.representation_id != bundle.representation.id:
        raise ValueError("HP-9 proposal evidence references a foreign representation.")
    view = next((item for item in bundle.text_views if item.id == location.text_view_id), None)
    if view is None or location.end_char > len(view.text):
        raise ValueError("HP-9 proposal evidence text selector is invalid.")
    if view.text[location.start_char : location.end_char] != evidence.exact_text:
        raise ValueError("HP-9 proposal evidence exact text does not replay.")
    if (
        view.text[max(0, location.start_char - len(evidence.prefix_text)) : location.start_char]
        != evidence.prefix_text
    ):
        raise ValueError("HP-9 proposal evidence prefix does not replay.")
    if (
        view.text[location.end_char : location.end_char + len(evidence.suffix_text)]
        != evidence.suffix_text
    ):
        raise ValueError("HP-9 proposal evidence suffix does not replay.")
    nodes = {item.id: item for item in bundle.nodes}
    for node_id in location.node_ids:
        node = nodes.get(node_id)
        if (
            node is None
            or node.text_view_id != location.text_view_id
            or node.start_char > location.start_char
            or node.end_char < location.end_char
        ):
            raise ValueError("HP-9 proposal evidence node selector is invalid.")


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_id(prefix: str, payload: JsonValue) -> str:
    return _id(prefix, _canonical_json(payload))


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"HP-9 {label} must be ordered and distinct.")


def _distinct(label: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"HP-9 {label} must be distinct.")


def _parse_canonical[ModelT: BaseModel](payload: bytes, model: type[ModelT], label: str) -> ModelT:
    try:
        parsed = model.model_validate_json(payload)
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid JSON.") from error
    if (_canonical_json(parsed.model_dump(mode="json")) + "\n").encode() != payload:
        raise ValueError(f"{label} does not use canonical encoding.")
    return parsed
