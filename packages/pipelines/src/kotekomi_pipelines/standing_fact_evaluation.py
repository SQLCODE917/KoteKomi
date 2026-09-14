"""Source-exact Gold evaluation for the Standing Fact route."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiAssertionPresentation,
)
from kotekomi_application.hybrid_standing_facts import StandingFactPlan
from kotekomi_domain import ProposedChange
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.evaluation_contracts import EvaluationPhase

_SHA256 = r"^[a-f0-9]{64}$"


class StandingFactGoldItem(BaseModel):
    """One reviewed source-grounded relationship expectation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    phase: EvaluationPhase
    paragraph_ordinal: Annotated[int, Field(ge=0)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    expected_summary: Annotated[str, Field(min_length=1)]
    subject_text: Annotated[str, Field(min_length=1)]
    accepted_relation_texts: tuple[Annotated[str, Field(min_length=1)], ...]
    object_text: Annotated[str, Field(min_length=1)]
    expected_disposition: Literal["proposed"]

    @model_validator(mode="after")
    def validate_source_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Standing Fact Gold source digest does not match its exact text.")
        values = (
            self.subject_text,
            *self.accepted_relation_texts,
            self.object_text,
        )
        if any(value not in self.source_text for value in values):
            raise ValueError("Standing Fact Gold expression is absent from its exact source.")
        if not self.accepted_relation_texts or len(set(self.accepted_relation_texts)) != len(
            self.accepted_relation_texts
        ):
            raise ValueError(
                "Standing Fact Gold relation alternatives must be nonempty and distinct."
            )
        return self


class StandingFactGoldCatalog(BaseModel):
    """The reviewed Standing Fact acceptance corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_standing_fact_gold_v1"] = "hsq_standing_fact_gold_v1"
    catalog_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["approved"]
    fixture_path: Annotated[str, Field(min_length=1)]
    fixture_sha256: Annotated[str, Field(pattern=_SHA256)]
    items: tuple[StandingFactGoldItem, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        item_ids = tuple(item.item_id for item in self.items)
        if item_ids != ("AMO-02", "AMO-07", "ANT-11"):
            raise ValueError("Standing Fact Gold must contain AMO-02, AMO-07, and ANT-11.")
        return self


class StandingFactRuntimeDraft(BaseModel):
    """Trusted StandingFactDraft fields needed for exact evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    subject_text: str | None
    subject_start: int | None
    subject_end: int | None
    relation_label: Annotated[str, Field(min_length=1)]
    relation_start: Annotated[int, Field(ge=0)]
    relation_end: Annotated[int, Field(gt=0)]
    object_text: Annotated[str, Field(min_length=1)]
    object_start: int | None
    object_end: int | None


class StandingFactRuntimeDecision(BaseModel):
    """Trusted StandingFactDecision fields needed for proposal evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(min_length=1)]
    draft_id: Annotated[str, Field(min_length=1)]
    disposition: Literal["proposed", "held"]
    proposed_change_ids: tuple[Annotated[str, Field(min_length=1)], ...]


class StandingFactRuntimeRecord(BaseModel):
    """One deterministic proposal-to-record identity mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    proposed_change_id: Annotated[str, Field(min_length=1)]
    record_id: Annotated[str, Field(min_length=1)]


class StandingFactRuntimeEvidence(BaseModel):
    """Current Standing Fact plan fields projected through a named boundary mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    paragraph_ordinal: Annotated[int, Field(ge=0)]
    drafts: tuple[StandingFactRuntimeDraft, ...]
    decisions: tuple[StandingFactRuntimeDecision, ...]
    proposed_records: tuple[StandingFactRuntimeRecord, ...]


class StandingFactReconciledRecord(BaseModel):
    """Stable HP-10 proposal lineage after document entity reconciliation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_proposed_change_id: Annotated[str, Field(min_length=1)]
    reconciled_proposed_change_id: Annotated[str, Field(min_length=1)]
    reconciled_record_id: Annotated[str, Field(min_length=1)]


class _ReconciledRecordIdentity(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, strict=True)

    id: Annotated[str, Field(min_length=1)]


class _IdentityReconciliationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    preview_id: Annotated[str, Field(min_length=1)]
    parent_proposed_change_id: Annotated[str, Field(min_length=1)]
    rewritten_record_ids: dict[str, str]


class _ReconciledAssertionProposal(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, strict=True)

    record_type: Literal["Assertion"]
    record: _ReconciledRecordIdentity
    identity_reconciliation: _IdentityReconciliationEvidence


class StandingFactItemEvaluation(BaseModel):
    """One exact Gold-to-runtime Standing Fact comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: str
    phase: EvaluationPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    expected_summary: str
    expected_subject_text: str
    expected_relation_texts: tuple[str, ...]
    expected_object_text: str
    actual_drafts: tuple[StandingFactRuntimeDraft, ...]
    matched_draft: StandingFactRuntimeDraft | None
    decision: StandingFactRuntimeDecision | None
    proposed_change_ids: tuple[str, ...]
    proposed_record_ids: tuple[str, ...]
    reconciled_records: tuple[StandingFactReconciledRecord, ...]
    wiki_page_paths: tuple[str, ...]
    status: Literal[
        "exact",
        "missing",
        "incorrect",
        "not_proposed",
        "lineage_incomplete",
        "not_visible",
    ]
    passed: bool

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.passed != (self.status == "exact"):
            raise ValueError("Standing Fact evaluation outcome does not match its status.")
        return self


class StandingFactEvaluationReport(BaseModel):
    """Current Standing Fact acceptance result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_standing_fact_evaluation_v1"] = "hsq_standing_fact_evaluation_v1"
    catalog_id: str
    item_count: Annotated[int, Field(ge=0)]
    exact_count: Annotated[int, Field(ge=0)]
    missing_count: Annotated[int, Field(ge=0)]
    incorrect_count: Annotated[int, Field(ge=0)]
    not_proposed_count: Annotated[int, Field(ge=0)]
    lineage_incomplete_count: Annotated[int, Field(ge=0)]
    not_visible_count: Annotated[int, Field(ge=0)]
    passed: bool
    items: tuple[StandingFactItemEvaluation, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        counts = {
            "exact_count": sum(item.status == "exact" for item in self.items),
            "missing_count": sum(item.status == "missing" for item in self.items),
            "incorrect_count": sum(item.status == "incorrect" for item in self.items),
            "not_proposed_count": sum(item.status == "not_proposed" for item in self.items),
            "lineage_incomplete_count": sum(
                item.status == "lineage_incomplete" for item in self.items
            ),
            "not_visible_count": sum(item.status == "not_visible" for item in self.items),
        }
        if self.item_count != len(self.items):
            raise ValueError("Standing Fact evaluation item count drifted.")
        if any(getattr(self, name) != value for name, value in counts.items()):
            raise ValueError("Standing Fact evaluation status counts drifted.")
        if self.passed != all(item.passed for item in self.items):
            raise ValueError("Standing Fact evaluation pass state drifted.")
        return self


def load_standing_fact_gold(path: Path) -> StandingFactGoldCatalog:
    """Load the strict reviewed Standing Fact corpus."""
    return StandingFactGoldCatalog.model_validate_json(path.read_bytes())


def standing_fact_evidence_from_plan(
    paragraph_ordinal: int,
    plan: StandingFactPlan,
) -> StandingFactRuntimeEvidence:
    """Map one validated Application record to the evaluator's narrow trusted fields."""
    digest_by_segment: dict[str, str] = {}
    for trace in plan.traces:
        existing = digest_by_segment.get(trace.source_segment_id)
        if existing is not None and existing != trace.source_text_sha256:
            raise ValueError("Standing Fact plan has conflicting SourceSegment digests.")
        digest_by_segment[trace.source_segment_id] = trace.source_text_sha256
    drafts: list[StandingFactRuntimeDraft] = []
    for item in plan.drafts:
        source_text_sha256 = digest_by_segment.get(item.source_segment_id)
        if source_text_sha256 is None:
            raise ValueError("Standing Fact draft has no traced SourceSegment digest.")
        drafts.append(
            StandingFactRuntimeDraft(
                id=item.id,
                source_text_sha256=source_text_sha256,
                subject_text=item.subject_text,
                subject_start=item.subject_start,
                subject_end=item.subject_end,
                relation_label=item.relation_label,
                relation_start=item.relation_start,
                relation_end=item.relation_end,
                object_text=item.object_text,
                object_start=item.object_start,
                object_end=item.object_end,
            )
        )
    decisions = tuple(
        StandingFactRuntimeDecision(
            id=item.id,
            draft_id=item.draft_id,
            disposition=item.disposition.value,
            proposed_change_ids=item.proposed_change_ids,
        )
        for item in plan.decisions
    )
    proposed_records: list[StandingFactRuntimeRecord] = []
    for item in plan.proposed_changes:
        record = item.proposed_json.get("record")
        if not isinstance(record, dict):
            raise ValueError("Standing Fact ProposedChange has no typed record.")
        record_id = cast(dict[str, object], record).get("id")
        if not isinstance(record_id, str):
            raise ValueError("Standing Fact ProposedChange has no record identity.")
        proposed_records.append(
            StandingFactRuntimeRecord(proposed_change_id=item.id, record_id=record_id)
        )
    return StandingFactRuntimeEvidence(
        paragraph_ordinal=paragraph_ordinal,
        drafts=tuple(drafts),
        decisions=decisions,
        proposed_records=tuple(proposed_records),
    )


def standing_fact_reconciliation_from_proposed_changes(
    proposed_changes: tuple[ProposedChange, ...],
) -> tuple[StandingFactReconciledRecord, ...]:
    """Map current reconciled Assertion proposals to their exact parent proposals."""
    records: list[StandingFactReconciledRecord] = []
    for change in proposed_changes:
        record_type = change.proposed_json.get("record_type")
        if record_type in {"Actor", "Organization", "Event"}:
            continue
        if record_type != "Assertion":
            raise ValueError(
                f"Standing Fact reconciliation encountered unsupported record type: {record_type}"
            )
        parsed = _ReconciledAssertionProposal.model_validate(change.proposed_json)
        records.append(
            StandingFactReconciledRecord(
                source_proposed_change_id=(
                    parsed.identity_reconciliation.parent_proposed_change_id
                ),
                reconciled_proposed_change_id=change.id,
                reconciled_record_id=parsed.record.id,
            )
        )
    ordered = tuple(sorted(records, key=lambda item: item.source_proposed_change_id))
    parent_ids = tuple(item.source_proposed_change_id for item in ordered)
    if len(parent_ids) != len(set(parent_ids)):
        raise ValueError("Standing Fact reconciliation has duplicate parent proposal IDs.")
    return ordered


def evaluate_standing_fact_gold(
    catalog: StandingFactGoldCatalog,
    evidence_by_ordinal: dict[int, StandingFactRuntimeEvidence],
    *,
    reconciled_records: tuple[StandingFactReconciledRecord, ...],
    wiki_plan: CandidateWikiPlan | None,
) -> StandingFactEvaluationReport:
    """Compare every Gold item with source-valid plans, proposals, and Wiki output."""
    evaluations = tuple(
        _evaluate_item(
            item,
            evidence_by_ordinal.get(item.paragraph_ordinal),
            reconciled_records,
            wiki_plan,
        )
        for item in catalog.items
    )
    return StandingFactEvaluationReport(
        catalog_id=catalog.catalog_id,
        item_count=len(evaluations),
        exact_count=sum(item.status == "exact" for item in evaluations),
        missing_count=sum(item.status == "missing" for item in evaluations),
        incorrect_count=sum(item.status == "incorrect" for item in evaluations),
        not_proposed_count=sum(item.status == "not_proposed" for item in evaluations),
        lineage_incomplete_count=sum(item.status == "lineage_incomplete" for item in evaluations),
        not_visible_count=sum(item.status == "not_visible" for item in evaluations),
        passed=all(item.passed for item in evaluations),
        items=evaluations,
    )


def _evaluate_item(
    expected: StandingFactGoldItem,
    evidence: StandingFactRuntimeEvidence | None,
    reconciled_records: tuple[StandingFactReconciledRecord, ...],
    wiki_plan: CandidateWikiPlan | None,
) -> StandingFactItemEvaluation:
    actual_drafts = _source_drafts(evidence, expected.source_text_sha256)
    source_valid = tuple(
        item for item in actual_drafts if _draft_is_source_valid(item, expected.source_text)
    )
    matching = tuple(
        item
        for item in source_valid
        if item.subject_text == expected.subject_text
        and item.relation_label in expected.accepted_relation_texts
        and item.object_text == expected.object_text
    )
    draft = matching[0] if len(matching) == 1 else None
    decision = (
        next(
            (
                item
                for item in evidence.decisions
                if draft is not None and item.draft_id == draft.id
            ),
            None,
        )
        if evidence is not None
        else None
    )
    proposal_ids = decision.proposed_change_ids if decision is not None else ()
    record_ids = _proposed_record_ids(evidence, proposal_ids)
    reconciliation_by_parent = {item.source_proposed_change_id: item for item in reconciled_records}
    current_records = tuple(
        reconciliation_by_parent[item] for item in proposal_ids if item in reconciliation_by_parent
    )
    current_record_ids = tuple(item.reconciled_record_id for item in current_records)
    wiki_paths = _wiki_paths(wiki_plan, current_record_ids, expected.source_text_sha256)
    if not actual_drafts:
        status = "missing"
    elif draft is None:
        status = "incorrect"
    elif (
        decision is None
        or decision.disposition != expected.expected_disposition
        or not proposal_ids
        or not record_ids
    ):
        status = "not_proposed"
    elif len(current_records) != len(proposal_ids):
        status = "lineage_incomplete"
    elif wiki_plan is not None and not wiki_paths:
        status = "not_visible"
    else:
        status = "exact"
    return StandingFactItemEvaluation(
        item_id=expected.item_id,
        phase=expected.phase,
        source_text_sha256=expected.source_text_sha256,
        expected_summary=expected.expected_summary,
        expected_subject_text=expected.subject_text,
        expected_relation_texts=expected.accepted_relation_texts,
        expected_object_text=expected.object_text,
        actual_drafts=actual_drafts,
        matched_draft=draft,
        decision=decision,
        proposed_change_ids=proposal_ids,
        proposed_record_ids=record_ids,
        reconciled_records=current_records,
        wiki_page_paths=wiki_paths,
        status=status,
        passed=status == "exact",
    )


def _source_drafts(
    evidence: StandingFactRuntimeEvidence | None,
    source_text_sha256: str,
) -> tuple[StandingFactRuntimeDraft, ...]:
    if evidence is None:
        return ()
    return tuple(item for item in evidence.drafts if item.source_text_sha256 == source_text_sha256)


def _draft_is_source_valid(draft: StandingFactRuntimeDraft, source_text: str) -> bool:
    spans = (
        (draft.subject_start, draft.subject_end, draft.subject_text),
        (draft.relation_start, draft.relation_end, draft.relation_label),
        (draft.object_start, draft.object_end, draft.object_text),
    )
    return all(
        start is not None
        and end is not None
        and text is not None
        and source_text[start:end] == text
        for start, end, text in spans
    )


def _proposed_record_ids(
    evidence: StandingFactRuntimeEvidence | None,
    proposal_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if evidence is None:
        return ()
    wanted = set(proposal_ids)
    return tuple(
        sorted(
            item.record_id
            for item in evidence.proposed_records
            if item.proposed_change_id in wanted
        )
    )


def _wiki_paths(
    plan: CandidateWikiPlan | None,
    record_ids: tuple[str, ...],
    source_text_sha256: str,
) -> tuple[str, ...]:
    if plan is None or not record_ids:
        return ()
    wanted = set(record_ids)
    citations = {item.citation_number: item for item in plan.citation_registry.citations}
    paths: set[str] = set()
    for page in plan.pages:
        for presentation in page.presentations:
            if isinstance(presentation, WikiAssertionPresentation):
                presented_ids = {presentation.edge.assertion_id}
            else:
                presented_ids = {item.assertion_id for item in presentation.edges}
            if not presented_ids & wanted:
                continue
            if any(
                number in citations
                and hashlib.sha256(citations[number].exact_text.encode()).hexdigest()
                == source_text_sha256
                for number in presentation.citation_numbers
            ):
                paths.add(page.relative_path)
    return tuple(sorted(paths))
