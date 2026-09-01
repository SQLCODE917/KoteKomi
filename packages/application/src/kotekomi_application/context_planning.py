"""Deterministic bounded context planning over pinned Document representations."""

from __future__ import annotations

import hashlib
import json
import re
from base64 import b64decode, b64encode
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, cast

import pysbd  # type: ignore[import-untyped]
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentNode,
    DocumentRepresentationBundle,
    RepresentationAnalyzability,
    TextView,
    canonical_representation_digest,
)
from kotekomi_domain.models import JsonValue

HASH_ID_LENGTH = 24
PARAGRAPH_FOCUS_SPLIT_V1 = "paragraph_focus_split_v1"
FOCUS_NODE_EVIDENCE_SELECTION_V1 = "focus_node_evidence_v1"
DIRECT_PROSE_EVIDENCE_SELECTION_V1 = "direct_prose_evidence_v1"
PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1 = "paragraph_hypothesis_evidence_v1"
HYBRID_MENTION_EVIDENCE_SELECTION_V1 = "hybrid_mention_evidence_v1"
PARAGRAPH_SEGMENT_V1 = "paragraph_segment_v1"
PARAGRAPH_SEGMENT_V2 = "paragraph_segment_v2"
PARAGRAPH_SEGMENT_V3 = "paragraph_segment_v3"


class ContextCandidateRole(StrEnum):
    FOCUS = "focus"
    HEADING = "heading"
    DEFINITION = "definition"
    FURNITURE = "furniture"
    TABLE_HEADER = "table_header"
    TABLE_CONTEXT = "table_context"


class ContextManifestStatus(StrEnum):
    READY = "ready"
    SPLIT = "split"
    CONTEXT_BUDGET_BLOCKED = "context_budget_blocked"


class ContextPlanningLedger(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None: ...
    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None: ...
    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None: ...
    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None: ...
    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None: ...


class ContextTokenizer(Protocol):
    @property
    def tokenizer_id(self) -> str: ...

    def count_tokens(self, rendered_input: bytes) -> int: ...


@dataclass(frozen=True)
class AnalysisUnitPlanningInput:
    representation_id: str
    policy_id: str
    task_type: str
    max_focus_nodes_per_unit: int = 1
    focus_node_types: tuple[str, ...] = ("paragraph", "table_caption")


@dataclass(frozen=True)
class TableCellAnalysisPlanningInput:
    representation_id: str
    table_cell_id: str
    policy_id: str
    task_type: str


@dataclass(frozen=True)
class TableCellAnalysisPlanningOutcome:
    analysis_unit: AnalysisUnit | None
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.analysis_unit is None) == (self.blocked_reason is None):
            raise ValueError("Table-cell planning requires exactly one unit or blocked reason.")


@dataclass(frozen=True)
class RetrievalSelectionAnalysisUnitInput:
    """Pinned authoritative focus nodes selected by a retrieval policy."""

    representation_id: str
    focus_node_ids: tuple[str, ...]
    policy_id: str
    task_type: str = "document_retrieval"


@dataclass(frozen=True)
class AnalysisUnit:
    id: str
    representation_id: str
    task_type: str
    focus_node_ids: tuple[str, ...]
    dependency_node_ids: tuple[str, ...]
    planner_policy_id: str
    fingerprint: str
    source_segment_label: str | None = None


@dataclass(frozen=True)
class AnalysisPlan:
    representation_id: str
    policy_id: str
    units: tuple[AnalysisUnit, ...]


@dataclass(frozen=True)
class ContextCandidate:
    node_id: str
    role: ContextCandidateRole
    reason_code: str
    required: bool
    priority: int
    dependency_path: tuple[str, ...]
    source_node_ids: tuple[str, ...]
    estimated_tokens: int


@dataclass(frozen=True)
class EvidenceCandidate:
    """One model-selectable, authoritative evidence span in a ready context."""

    id: str
    node_id: str
    text_view_id: str
    start_char: int
    end_char: int
    source_region_ids: tuple[str, ...]


@dataclass(frozen=True)
class SourceSegment:
    """One task-local, exact source span inside an authoritative Paragraph."""

    label: str
    start_char: int
    end_char: int
    exact_text: str


@dataclass(frozen=True)
class SourceCopyView:
    """One model-facing copy with authoritative boundary provenance."""

    text: str
    authoritative_text_sha256: str
    copy_to_authoritative_boundaries: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.authoritative_text_sha256:
            raise ValueError("Source copy requires an authoritative text digest.")
        if len(self.copy_to_authoritative_boundaries) != len(self.text) + 1:
            raise ValueError("Source copy boundary count does not match its text.")
        if any(
            current > following
            for current, following in zip(
                self.copy_to_authoritative_boundaries,
                self.copy_to_authoritative_boundaries[1:],
                strict=False,
            )
        ):
            raise ValueError("Source copy boundaries must use authoritative order.")

    def authoritative_range(self, copy_start: int, copy_end: int) -> tuple[int, int]:
        """Resolve one half-open Source copy range into authoritative coordinates."""
        if (
            type(copy_start) is not int
            or type(copy_end) is not int
            or copy_start < 0
            or copy_end <= copy_start
            or copy_end > len(self.text)
        ):
            raise ValueError("Source copy range is invalid.")
        return (
            self.copy_to_authoritative_boundaries[copy_start],
            self.copy_to_authoritative_boundaries[copy_end],
        )


def paragraph_source_segments(
    text: str, policy_id: str = PARAGRAPH_SEGMENT_V1
) -> tuple[SourceSegment, ...]:
    """Derive exact source segments for one versioned policy."""
    if not text:
        raise ValueError("Paragraph source text must not be empty.")
    if policy_id == PARAGRAPH_SEGMENT_V1:
        boundaries = [match.end() for match in re.finditer(r"[.?!](?=\s+)", text)]
        starts = (0, *boundaries)
        ends = (*boundaries, len(text))
    elif policy_id in {PARAGRAPH_SEGMENT_V2, PARAGRAPH_SEGMENT_V3}:
        segmenter: Any = pysbd.Segmenter(language="en", clean=False, char_span=True)
        spans = cast(list[Any], segmenter.segment(text))
        starts = tuple(span.start for span in spans)
        ends = tuple(span.end for span in spans)
    else:
        raise ValueError(f"Unsupported source segment policy: {policy_id}")
    return tuple(
        SourceSegment(
            label=f"s{index}",
            start_char=start,
            end_char=end,
            exact_text=text[start:end],
        )
        for index, (start, end) in enumerate(zip(starts, ends, strict=True), start=1)
    )


def derive_source_copy_view(text: str) -> SourceCopyView:
    """Derive model text and a deterministic map to authoritative characters."""
    matches = tuple(re.finditer(r"\S+", text))
    if not matches:
        return SourceCopyView("", hashlib.sha256(text.encode()).hexdigest(), (0,))
    output: list[str] = []
    boundaries: list[int] = [matches[0].start()]
    for index, match in enumerate(matches):
        if index:
            output.append(" ")
            boundaries.append(match.start())
        for offset, character in enumerate(match.group()):
            output.append(character)
            boundaries.append(match.start() + offset + 1)
    return SourceCopyView(
        "".join(output),
        hashlib.sha256(text.encode()).hexdigest(),
        tuple(boundaries),
    )


def source_copy_view(text: str) -> str:
    """Derive the model-facing whitespace-normalized copy of authoritative text."""
    return derive_source_copy_view(text).text


@dataclass(frozen=True)
class ExcludedContextCandidate:
    candidate: ContextCandidate
    reason_code: str


@dataclass(frozen=True)
class RenderedContextSegment:
    node_id: str
    start_byte: int
    end_byte: int


@dataclass(frozen=True)
class ContextModelProfile:
    id: str
    model_context_limit: int
    reserved_output_tokens: int
    safety_margin_tokens: int


@dataclass(frozen=True)
class ContextManifestInput:
    analysis_unit: AnalysisUnit
    model_profile: ContextModelProfile
    prompt_id: str
    prompt_bytes: bytes
    schema_id: str
    schema_bytes: bytes
    renderer_version: str
    evidence_selection_policy_id: str | None = None
    source_segment_policy_id: str | None = None
    source_segment_label: str | None = None


@dataclass(frozen=True)
class ContextManifest:
    id: str
    analysis_unit_id: str
    analysis_unit_payload: dict[str, JsonValue]
    representation_id: str
    prompt_id: str
    prompt_bytes: bytes
    prompt_digest: str
    schema_id: str
    schema_digest: str
    schema_bytes: bytes
    renderer_version: str
    planner_policy_id: str
    tokenizer_id: str
    model_profile_id: str
    model_context_limit: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    selected_candidates: tuple[ContextCandidate, ...]
    excluded_candidates: tuple[ExcludedContextCandidate, ...]
    rendered_segments: tuple[RenderedContextSegment, ...]
    rendered_input: bytes
    rendered_input_digest: str
    input_token_count: int
    manifest_digest: str
    status: ContextManifestStatus
    evidence_selection_policy_id: str | None = None
    source_segment_policy_id: str | None = None
    source_segment_label: str | None = None
    evidence_candidates: tuple[EvidenceCandidate, ...] = ()
    split_strategy_id: str | None = None
    child_analysis_unit_ids: tuple[str, ...] = ()
    blocked_reason: str | None = None


@dataclass(frozen=True)
class ContextPlanningOutcome:
    manifest: ContextManifest
    split_units: tuple[AnalysisUnit, ...] = ()
    blocked_reason: str | None = None


@dataclass(frozen=True)
class VerifiedContextManifest:
    """A persisted manifest whose exact task inputs have been independently checked."""

    manifest: ContextManifest


def plan_analysis_units(
    planning_input: AnalysisUnitPlanningInput,
    ledger_repository: ContextPlanningLedger,
) -> AnalysisPlan:
    """Create deterministic units for the named structural node types."""
    bundle = _load_acceptable_bundle(planning_input.representation_id, ledger_repository)
    if not planning_input.focus_node_types:
        raise ValueError("Analysis unit focus node types cannot be empty.")
    if len(set(planning_input.focus_node_types)) != len(planning_input.focus_node_types):
        raise ValueError("Analysis unit focus node types must be distinct.")
    focus_node_types = frozenset(planning_input.focus_node_types)
    analysis_focus_nodes = tuple(
        node
        for node in sorted(
            bundle.nodes, key=lambda candidate: (candidate.order_index, candidate.id)
        )
        if node.node_type in focus_node_types
    )
    if planning_input.max_focus_nodes_per_unit <= 0:
        raise ValueError("Analysis unit max_focus_nodes_per_unit must be positive.")
    units = tuple(
        _analysis_unit(
            representation_id=bundle.representation.id,
            task_type=planning_input.task_type,
            focus_nodes=group,
            dependency_nodes=tuple(
                node
                for node in {
                    dependency.id: dependency
                    for focus in group
                    for dependency in _definition_nodes_for_focus(focus, bundle)
                }.values()
            ),
            policy_id=planning_input.policy_id,
        )
        for group in (
            analysis_focus_nodes[index : index + planning_input.max_focus_nodes_per_unit]
            for index in range(
                0, len(analysis_focus_nodes), planning_input.max_focus_nodes_per_unit
            )
        )
    )
    if planning_input.policy_id == "segment_local_hypothesis_v1":
        units = tuple(
            _analysis_unit(
                representation_id=bundle.representation.id,
                task_type=planning_input.task_type,
                focus_nodes=(node,),
                dependency_nodes=(),
                policy_id=planning_input.policy_id,
                source_segment_label=segment.label,
            )
            for node in analysis_focus_nodes
            for segment in paragraph_source_segments(
                _text_view_by_id(bundle, node.text_view_id).text[node.start_char : node.end_char],
                PARAGRAPH_SEGMENT_V3,
            )
        )
    plan = AnalysisPlan(bundle.representation.id, planning_input.policy_id, units)
    for unit in plan.units:
        _persist_analysis_unit(unit, ledger_repository)
    return plan


def plan_table_cell_analysis_unit(
    planning_input: TableCellAnalysisPlanningInput,
    ledger_repository: ContextPlanningLedger,
) -> TableCellAnalysisPlanningOutcome:
    """Plan a claim task only when the selected value retains complete header ancestry."""
    bundle = _load_acceptable_bundle(planning_input.representation_id, ledger_repository)
    cell = next(
        (
            candidate
            for candidate in bundle.table_cells
            if candidate.id == planning_input.table_cell_id
        ),
        None,
    )
    if cell is None or cell.node_id is None:
        return TableCellAnalysisPlanningOutcome(None, "table_cell_text_unavailable")
    if cell.is_row_header or cell.is_column_header:
        return TableCellAnalysisPlanningOutcome(None, "table_header_is_not_a_claim_value")
    if not cell.row_header_cell_ids:
        return TableCellAnalysisPlanningOutcome(None, "missing_row_header_ancestry")
    if not cell.column_header_cell_ids:
        return TableCellAnalysisPlanningOutcome(None, "missing_column_header_ancestry")
    cells_by_id = {candidate.id: candidate for candidate in bundle.table_cells}
    required_cells = tuple(
        cells_by_id.get(cell_id)
        for cell_id in (*cell.row_header_cell_ids, *cell.column_header_cell_ids)
    )
    if any(header is None or header.node_id is None for header in required_cells):
        return TableCellAnalysisPlanningOutcome(None, "table_header_text_unavailable")
    table = next(candidate for candidate in bundle.tables if candidate.id == cell.table_id)
    annotations_by_id = {item.id: item for item in bundle.table_annotations}
    annotation_nodes = tuple(
        _node_by_id(bundle, annotations_by_id[annotation_id].node_id)
        for annotation_id in table.annotation_ids
    )
    dependencies = (
        tuple(
            _node_by_id(bundle, cast(str, header.node_id))
            for header in required_cells
            if header is not None
        )
        + annotation_nodes
    )
    unit = _analysis_unit(
        representation_id=bundle.representation.id,
        task_type=planning_input.task_type,
        focus_nodes=(_node_by_id(bundle, cell.node_id),),
        dependency_nodes=dependencies,
        policy_id=planning_input.policy_id,
    )
    _persist_analysis_unit(unit, ledger_repository)
    return TableCellAnalysisPlanningOutcome(unit)


def create_analysis_unit_from_retrieval_selection(
    selection: RetrievalSelectionAnalysisUnitInput,
    ledger_repository: ContextPlanningLedger,
) -> AnalysisUnit:
    """Persist a ContextPlanner unit for externally selected authoritative nodes.

    Retrieval supplies identities only; dependency expansion and packing remain owned by
    ContextPlanner when the resulting unit is rendered.
    """
    bundle = _load_acceptable_bundle(selection.representation_id, ledger_repository)
    if not selection.focus_node_ids:
        raise ValueError("Retrieval selection requires at least one focus node.")
    if len(set(selection.focus_node_ids)) != len(selection.focus_node_ids):
        raise ValueError("Retrieval selection focus node IDs must be unique.")
    nodes = tuple(_node_by_id(bundle, node_id) for node_id in selection.focus_node_ids)
    dependencies = tuple(
        sorted(
            {
                dependency.id: dependency
                for node in nodes
                for dependency in _definition_nodes_for_focus(node, bundle)
            }.values(),
            key=lambda node: (node.order_index, node.id),
        )
    )
    unit = _analysis_unit(
        representation_id=bundle.representation.id,
        task_type=selection.task_type,
        focus_nodes=nodes,
        dependency_nodes=dependencies,
        policy_id=selection.policy_id,
    )
    _persist_analysis_unit(unit, ledger_repository)
    return unit


def build_context_manifest(
    manifest_input: ContextManifestInput,
    ledger_repository: ContextPlanningLedger,
    tokenizer: ContextTokenizer,
) -> ContextPlanningOutcome:
    """Pack required context exactly or return a deterministic split or blocked outcome."""
    unit = manifest_input.analysis_unit
    bundle = _load_acceptable_bundle(unit.representation_id, ledger_repository)
    _require_unit_matches_representation(unit, bundle)
    _require_persisted_analysis_unit(unit, ledger_repository)
    candidates = _context_candidates(unit, bundle, tokenizer)
    token_budget = (
        manifest_input.model_profile.model_context_limit
        - manifest_input.model_profile.reserved_output_tokens
        - manifest_input.model_profile.safety_margin_tokens
    )
    if token_budget <= 0:
        return _persist_outcome(
            _blocked_outcome(manifest_input, tokenizer, candidates, "nonpositive_context_budget"),
            ledger_repository,
        )
    required = tuple(candidate for candidate in candidates if candidate.required)
    rendered_input, segments, evidence_candidates = _render_context(
        manifest_input, required, bundle
    )
    if tokenizer.count_tokens(rendered_input) <= token_budget:
        excluded = tuple(
            ExcludedContextCandidate(candidate, "furniture_excluded")
            for candidate in candidates
            if not candidate.required
        )
        return _persist_outcome(
            ContextPlanningOutcome(
                _manifest(
                    manifest_input,
                    tokenizer,
                    selected=required,
                    excluded=excluded,
                    rendered_input=rendered_input,
                    segments=segments,
                    status=ContextManifestStatus.READY,
                    evidence_candidates=evidence_candidates,
                )
            ),
            ledger_repository,
        )
    if len(unit.focus_node_ids) > 1:
        split_units = tuple(
            _analysis_unit(
                representation_id=unit.representation_id,
                task_type=unit.task_type,
                focus_nodes=(_node_by_id(bundle, node_id),),
                dependency_nodes=_definition_nodes_for_focus(_node_by_id(bundle, node_id), bundle),
                policy_id=unit.planner_policy_id,
            )
            for node_id in sorted(
                unit.focus_node_ids,
                key=lambda node_id: (_node_by_id(bundle, node_id).order_index, node_id),
            )
        )
        return _persist_outcome(
            ContextPlanningOutcome(
                _manifest(
                    manifest_input,
                    tokenizer,
                    selected=(),
                    excluded=tuple(
                        ExcludedContextCandidate(candidate, "split_required_context")
                        for candidate in candidates
                    ),
                    rendered_input=b"",
                    segments=(),
                    status=ContextManifestStatus.SPLIT,
                    split_strategy_id=PARAGRAPH_FOCUS_SPLIT_V1,
                    child_analysis_unit_ids=tuple(child.id for child in split_units),
                ),
                split_units=split_units,
            ),
            ledger_repository,
        )
    return _persist_outcome(
        _blocked_outcome(
            manifest_input,
            tokenizer,
            candidates,
            "required_context_exceeds_budget",
        ),
        ledger_repository,
    )


def render_context(
    manifest_id: str,
    ledger_repository: ContextPlanningLedger,
    tokenizer: ContextTokenizer,
    prompt_bytes: bytes,
    schema_bytes: bytes,
) -> bytes:
    """Load and return the byte-exact finalized model input after full verification."""
    return verify_context_manifest(
        manifest_id,
        ledger_repository,
        tokenizer,
        prompt_bytes,
        schema_bytes,
    ).manifest.rendered_input


def _analysis_unit(
    *,
    representation_id: str,
    task_type: str,
    focus_nodes: tuple[DocumentNode, ...],
    dependency_nodes: tuple[DocumentNode, ...],
    policy_id: str,
    source_segment_label: str | None = None,
) -> AnalysisUnit:
    dependency_ids = tuple(node.id for node in dependency_nodes)
    focus_node_ids = tuple(node.id for node in focus_nodes)
    fingerprint = analysis_unit_fingerprint(
        representation_id=representation_id,
        task_type=task_type,
        focus_node_ids=focus_node_ids,
        dependency_node_ids=dependency_ids,
        planner_policy_id=policy_id,
        source_segment_label=source_segment_label,
    )
    return AnalysisUnit(
        id=deterministic_analysis_unit_id(fingerprint),
        representation_id=representation_id,
        task_type=task_type,
        focus_node_ids=focus_node_ids,
        dependency_node_ids=dependency_ids,
        planner_policy_id=policy_id,
        fingerprint=fingerprint,
        source_segment_label=source_segment_label,
    )


def _context_candidates(
    unit: AnalysisUnit,
    bundle: DocumentRepresentationBundle,
    tokenizer: ContextTokenizer,
) -> tuple[ContextCandidate, ...]:
    nodes = {node.id: node for node in bundle.nodes}
    candidates: dict[str, ContextCandidate] = {}
    for focus_id in unit.focus_node_ids:
        focus = _node_by_id(bundle, focus_id)
        candidates[focus.id] = _candidate(
            focus, ContextCandidateRole.FOCUS, "focus_node", True, 1, (), tokenizer, bundle
        )
        ancestor_headings = _ancestor_heading_chain(focus, bundle)
        for index, heading in enumerate(ancestor_headings):
            dependency_path = (
                focus.id,
                *tuple(node.id for node in reversed(ancestor_headings[index:])),
            )
            candidates.setdefault(
                heading.id,
                _candidate(
                    heading,
                    ContextCandidateRole.HEADING,
                    "ancestor_heading",
                    True,
                    3,
                    dependency_path,
                    tokenizer,
                    bundle,
                ),
            )
    for dependency_id in unit.dependency_node_ids:
        dependency = nodes.get(dependency_id)
        if dependency is None:
            raise ValueError(f"AnalysisUnit references missing dependency node: {dependency_id}")
        focus_id = unit.focus_node_ids[0]
        if dependency.node_type in {
            "table_row_header",
            "table_column_header",
            "table_corner_header",
        }:
            role = ContextCandidateRole.TABLE_HEADER
            reason_code = "table_header_ancestry"
        elif dependency.node_type in {"table_caption", "table_unit", "table_note", "footnote"}:
            role = ContextCandidateRole.TABLE_CONTEXT
            reason_code = "table_annotation"
        else:
            role = ContextCandidateRole.DEFINITION
            reason_code = "acronym_definition"
        priority = (
            2
            if role is ContextCandidateRole.TABLE_HEADER
            else (3 if role is ContextCandidateRole.TABLE_CONTEXT else 4)
        )
        candidates[dependency.id] = _candidate(
            dependency,
            role,
            reason_code,
            True,
            priority,
            (focus_id, "acronym", dependency.id),
            tokenizer,
            bundle,
        )
    for node in bundle.nodes:
        if node.node_type == "furniture":
            candidates[node.id] = _candidate(
                node,
                ContextCandidateRole.FURNITURE,
                "furniture_out_of_scope",
                False,
                99,
                (),
                tokenizer,
                bundle,
            )
    return tuple(
        sorted(
            candidates.values(),
            key=lambda candidate: (
                candidate.priority,
                nodes[candidate.node_id].order_index,
                candidate.node_id,
            ),
        )
    )


def _candidate(
    node: DocumentNode,
    role: ContextCandidateRole,
    reason_code: str,
    required: bool,
    priority: int,
    dependency_path: tuple[str, ...],
    tokenizer: ContextTokenizer,
    bundle: DocumentRepresentationBundle,
) -> ContextCandidate:
    rendered = _render_node(node, _text_view_by_id(bundle, node.text_view_id))
    return ContextCandidate(
        node_id=node.id,
        role=role,
        reason_code=reason_code,
        required=required,
        priority=priority,
        dependency_path=dependency_path,
        source_node_ids=(node.id,),
        estimated_tokens=tokenizer.count_tokens(rendered),
    )


def _render_context(
    manifest_input: ContextManifestInput,
    candidates: tuple[ContextCandidate, ...],
    bundle: DocumentRepresentationBundle,
) -> tuple[bytes, tuple[RenderedContextSegment, ...], tuple[EvidenceCandidate, ...]]:
    rendered = bytearray(manifest_input.prompt_bytes + b"\n\n" + manifest_input.schema_bytes)
    segments: list[RenderedContextSegment] = []
    evidence_candidates = _evidence_candidates_for_context(
        manifest_input.evidence_selection_policy_id, candidates, bundle
    )
    evidence_by_node_id = {candidate.node_id: candidate for candidate in evidence_candidates}
    rendered_candidates = candidates
    if (
        manifest_input.source_segment_policy_id
        in {
            PARAGRAPH_SEGMENT_V1,
            PARAGRAPH_SEGMENT_V2,
            PARAGRAPH_SEGMENT_V3,
        }
        and manifest_input.evidence_selection_policy_id != HYBRID_MENTION_EVIDENCE_SELECTION_V1
    ):
        rendered_candidates = tuple(
            candidate for candidate in candidates if candidate.node_id in evidence_by_node_id
        )
    for candidate in rendered_candidates:
        node = _node_by_id(bundle, candidate.node_id)
        evidence_candidate = evidence_by_node_id.get(node.id)
        segment = _render_node(
            node,
            _text_view_by_id(bundle, node.text_view_id),
            evidence_candidate_id=(evidence_candidate.id if evidence_candidate else None),
            include_node_id=manifest_input.evidence_selection_policy_id is None,
            direct_prose=manifest_input.evidence_selection_policy_id
            in {
                DIRECT_PROSE_EVIDENCE_SELECTION_V1,
                PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
                HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            },
            source_segment_policy_id=(
                manifest_input.source_segment_policy_id if evidence_candidate is not None else None
            ),
            source_segment_label=manifest_input.analysis_unit.source_segment_label,
        )
        rendered.extend(b"\n\n")
        start_byte = len(rendered)
        rendered.extend(segment)
        segments.append(RenderedContextSegment(node.id, start_byte, len(rendered)))
    return bytes(rendered), tuple(segments), evidence_candidates


def _render_node(
    node: DocumentNode,
    text_view: TextView,
    *,
    evidence_candidate_id: str | None = None,
    include_node_id: bool = True,
    direct_prose: bool = False,
    source_segment_policy_id: str | None = None,
    source_segment_label: str | None = None,
) -> bytes:
    text = text_view.text[node.start_char : node.end_char]
    evidence_label = (
        "[direct_prose]\n"
        if direct_prose and evidence_candidate_id is not None
        else f"[evidence_candidate:{evidence_candidate_id}]\n"
        if evidence_candidate_id is not None
        else ""
    )
    node_label = f"[{node.node_type}:{node.id}]" if include_node_id else f"[{node.node_type}]"
    if source_segment_policy_id is None:
        rendered_text = text
    elif source_segment_policy_id in {
        PARAGRAPH_SEGMENT_V1,
        PARAGRAPH_SEGMENT_V2,
        PARAGRAPH_SEGMENT_V3,
    }:
        segments = paragraph_source_segments(text, source_segment_policy_id)
        if source_segment_label is not None:
            segments = tuple(
                segment for segment in segments if segment.label == source_segment_label
            )
            if len(segments) != 1:
                raise ValueError("AnalysisUnit references an unknown SourceSegment.")
        rendered_text = "\n".join(
            f"SOURCE SEGMENT: {segment.label}\n"
            f"{_render_source_segment_text(segment, source_segment_policy_id)}"
            for segment in segments
        )
    else:
        raise ValueError(f"Unsupported source segment policy: {source_segment_policy_id}")
    return f"{evidence_label}{node_label}\n{rendered_text}".encode()


def _render_source_segment_text(segment: SourceSegment, policy_id: str) -> str:
    if policy_id == PARAGRAPH_SEGMENT_V3:
        return source_copy_view(segment.exact_text)
    return segment.exact_text


def _evidence_candidates_for_context(
    policy_id: str | None,
    candidates: tuple[ContextCandidate, ...],
    bundle: DocumentRepresentationBundle,
) -> tuple[EvidenceCandidate, ...]:
    if policy_id is None:
        return ()
    if policy_id not in {
        FOCUS_NODE_EVIDENCE_SELECTION_V1,
        DIRECT_PROSE_EVIDENCE_SELECTION_V1,
        PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
        HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    }:
        raise ValueError(f"Unsupported evidence selection policy: {policy_id}")
    focus_nodes = tuple(
        _node_by_id(bundle, candidate.node_id)
        for candidate in candidates
        if candidate.role is ContextCandidateRole.FOCUS
    )
    if policy_id in {
        DIRECT_PROSE_EVIDENCE_SELECTION_V1,
        PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
        HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    }:
        focus_nodes = tuple(
            sorted(
                (node for node in focus_nodes if node.node_type == "paragraph"),
                key=lambda node: node.order_index,
            )
        )
    return tuple(
        EvidenceCandidate(
            id=f"evidence_{index:02d}",
            node_id=node.id,
            text_view_id=node.text_view_id,
            start_char=node.start_char,
            end_char=node.end_char,
            source_region_ids=node.source_region_ids,
        )
        for index, node in enumerate(focus_nodes, start=1)
    )


def _definition_nodes_for_focus(
    focus_node: DocumentNode,
    bundle: DocumentRepresentationBundle,
) -> tuple[DocumentNode, ...]:
    focus_text = _node_text(focus_node, bundle)
    acronyms = tuple(sorted(set(re.findall(r"\b[A-Z]{2,}\b", focus_text))))
    definitions: list[DocumentNode] = []
    for acronym in acronyms:
        matches = tuple(
            node
            for node in bundle.nodes
            if node.order_index < focus_node.order_index
            and node.node_type not in {"document", "furniture"}
            and f"({acronym})" in _node_text(node, bundle)
        )
        if matches:
            definitions.append(max(matches, key=lambda node: (node.order_index, node.id)))
    return tuple(sorted({node.id: node for node in definitions}.values(), key=lambda node: node.id))


def _ancestor_heading_chain(
    focus_node: DocumentNode,
    bundle: DocumentRepresentationBundle,
) -> tuple[DocumentNode, ...]:
    """Return the authoritative heading ancestry from outermost to innermost."""
    nodes_by_id = {node.id: node for node in bundle.nodes}
    ancestors: list[DocumentNode] = []
    parent_id = focus_node.parent_node_id
    while parent_id is not None:
        parent = nodes_by_id[parent_id]
        if parent.node_type == "heading":
            ancestors.append(parent)
        parent_id = parent.parent_node_id
    return tuple(reversed(ancestors))


def _load_acceptable_bundle(
    representation_id: str,
    ledger_repository: ContextPlanningLedger,
) -> DocumentRepresentationBundle:
    bundle = ledger_repository.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError(
            f"Context planning references missing DocumentRepresentation: {representation_id}"
        )
    if bundle.quality_report.analyzability is not RepresentationAnalyzability.ACCEPTABLE:
        raise ValueError("Context planning requires an acceptable DocumentRepresentation.")
    actual_digest = canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
        tables=bundle.tables,
        table_fragments=bundle.table_fragments,
        table_rows=bundle.table_rows,
        table_cells=bundle.table_cells,
        table_annotations=bundle.table_annotations,
        references=bundle.references,
        source_selectors=bundle.source_selectors,
    )
    if actual_digest != bundle.representation.canonical_output_digest:
        raise ValueError("Context planning DocumentRepresentation digest is corrupted.")
    return bundle


def _require_unit_matches_representation(
    unit: AnalysisUnit,
    bundle: DocumentRepresentationBundle,
) -> None:
    validate_analysis_unit_identity(unit)
    if unit.representation_id != bundle.representation.id:
        raise ValueError("AnalysisUnit does not belong to the pinned DocumentRepresentation.")
    if not unit.focus_node_ids:
        raise ValueError("AnalysisUnit requires at least one focus node.")


def _analysis_unit_payload(unit: AnalysisUnit) -> dict[str, object]:
    return {
        "id": unit.id,
        "representation_id": unit.representation_id,
        "task_type": unit.task_type,
        "focus_node_ids": list(unit.focus_node_ids),
        "dependency_node_ids": list(unit.dependency_node_ids),
        "planner_policy_id": unit.planner_policy_id,
        "fingerprint": unit.fingerprint,
        "source_segment_label": unit.source_segment_label,
    }


def analysis_unit_fingerprint(
    *,
    representation_id: str,
    task_type: str,
    focus_node_ids: tuple[str, ...],
    dependency_node_ids: tuple[str, ...],
    planner_policy_id: str,
    source_segment_label: str | None = None,
) -> str:
    """Return the canonical identity digest for one policy-created AnalysisUnit."""
    return _digest(
        {
            "representation_id": representation_id,
            "task_type": task_type,
            "focus_node_ids": focus_node_ids,
            "dependency_node_ids": dependency_node_ids,
            "planner_policy_id": planner_policy_id,
            "source_segment_label": source_segment_label,
        }
    )


def deterministic_analysis_unit_id(fingerprint: str) -> str:
    return f"anu_{fingerprint[:HASH_ID_LENGTH]}"


def validate_analysis_unit_identity(unit: AnalysisUnit) -> None:
    expected_fingerprint = analysis_unit_fingerprint(
        representation_id=unit.representation_id,
        task_type=unit.task_type,
        focus_node_ids=unit.focus_node_ids,
        dependency_node_ids=unit.dependency_node_ids,
        planner_policy_id=unit.planner_policy_id,
        source_segment_label=unit.source_segment_label,
    )
    if unit.fingerprint != expected_fingerprint:
        raise ValueError("AnalysisUnit fingerprint is not derived from its canonical fields.")
    if unit.id != deterministic_analysis_unit_id(expected_fingerprint):
        raise ValueError("AnalysisUnit ID is not derived from its canonical fingerprint.")


def _persist_analysis_unit(unit: AnalysisUnit, ledger_repository: ContextPlanningLedger) -> None:
    validate_analysis_unit_identity(unit)
    ledger_repository.save_analysis_unit_artifact(
        AnalysisUnitArtifact(
            id=unit.id,
            representation_id=unit.representation_id,
            unit_fingerprint=unit.fingerprint,
            payload=cast(dict[str, JsonValue], _analysis_unit_payload(unit)),
        )
    )


def load_analysis_unit(
    analysis_unit_id: str, ledger_repository: ContextPlanningLedger
) -> AnalysisUnit:
    artifact = ledger_repository.get_analysis_unit_artifact(analysis_unit_id)
    if artifact is None:
        raise ValueError(f"AnalysisUnit is not persisted: {analysis_unit_id}")
    unit = _analysis_unit_from_payload(artifact.payload)
    if (
        unit.id != artifact.id
        or unit.representation_id != artifact.representation_id
        or unit.fingerprint != artifact.unit_fingerprint
        or _analysis_unit_payload(unit) != artifact.payload
    ):
        raise ValueError("AnalysisUnit persisted artifact is corrupted.")
    validate_analysis_unit_identity(unit)
    return unit


def _analysis_unit_from_payload(payload: dict[str, JsonValue]) -> AnalysisUnit:
    try:
        return AnalysisUnit(
            id=_required_str(payload, "id"),
            representation_id=_required_str(payload, "representation_id"),
            task_type=_required_str(payload, "task_type"),
            focus_node_ids=_string_tuple(payload, "focus_node_ids"),
            dependency_node_ids=_string_tuple(payload, "dependency_node_ids"),
            planner_policy_id=_required_str(payload, "planner_policy_id"),
            fingerprint=_required_str(payload, "fingerprint"),
            source_segment_label=_optional_str(payload, "source_segment_label"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("AnalysisUnit persisted artifact is malformed.") from exc


def _require_persisted_analysis_unit(
    unit: AnalysisUnit, ledger_repository: ContextPlanningLedger
) -> None:
    validate_analysis_unit_identity(unit)
    if load_analysis_unit(unit.id, ledger_repository) != unit:
        raise ValueError("AnalysisUnit does not match its persisted authoritative artifact.")


def _node_by_id(bundle: DocumentRepresentationBundle, node_id: str) -> DocumentNode:
    node = next((candidate for candidate in bundle.nodes if candidate.id == node_id), None)
    if node is None:
        raise ValueError(f"Context planning references missing DocumentNode: {node_id}")
    return node


def _text_view_by_id(bundle: DocumentRepresentationBundle, text_view_id: str) -> TextView:
    text_view = next((view for view in bundle.text_views if view.id == text_view_id), None)
    if text_view is None:
        raise ValueError(f"Context planning references missing TextView: {text_view_id}")
    return text_view


def _node_text(node: DocumentNode, bundle: DocumentRepresentationBundle) -> str:
    return _text_view_by_id(bundle, node.text_view_id).text[node.start_char : node.end_char]


def _blocked_outcome(
    manifest_input: ContextManifestInput,
    tokenizer: ContextTokenizer,
    candidates: tuple[ContextCandidate, ...],
    reason: str,
) -> ContextPlanningOutcome:
    return ContextPlanningOutcome(
        _manifest(
            manifest_input,
            tokenizer,
            selected=(),
            excluded=tuple(ExcludedContextCandidate(candidate, reason) for candidate in candidates),
            rendered_input=b"",
            segments=(),
            status=ContextManifestStatus.CONTEXT_BUDGET_BLOCKED,
            blocked_reason=reason,
        ),
        blocked_reason=reason,
    )


def _manifest(
    manifest_input: ContextManifestInput,
    tokenizer: ContextTokenizer,
    *,
    selected: tuple[ContextCandidate, ...],
    excluded: tuple[ExcludedContextCandidate, ...],
    rendered_input: bytes,
    segments: tuple[RenderedContextSegment, ...],
    status: ContextManifestStatus,
    evidence_candidates: tuple[EvidenceCandidate, ...] = (),
    split_strategy_id: str | None = None,
    child_analysis_unit_ids: tuple[str, ...] = (),
    blocked_reason: str | None = None,
) -> ContextManifest:
    input_token_count = tokenizer.count_tokens(rendered_input)
    rendered_input_digest = hashlib.sha256(rendered_input).hexdigest()
    payload = {
        "analysis_unit_id": manifest_input.analysis_unit.id,
        "analysis_unit": _analysis_unit_payload(manifest_input.analysis_unit),
        "representation_id": manifest_input.analysis_unit.representation_id,
        "prompt_id": manifest_input.prompt_id,
        "prompt_bytes_base64": b64encode(manifest_input.prompt_bytes).decode("ascii"),
        "prompt_digest": hashlib.sha256(manifest_input.prompt_bytes).hexdigest(),
        "schema_id": manifest_input.schema_id,
        "schema_bytes_base64": b64encode(manifest_input.schema_bytes).decode("ascii"),
        "schema_digest": hashlib.sha256(manifest_input.schema_bytes).hexdigest(),
        "renderer_version": manifest_input.renderer_version,
        "evidence_selection_policy_id": manifest_input.evidence_selection_policy_id,
        "source_segment_policy_id": manifest_input.source_segment_policy_id,
        "source_segment_label": manifest_input.analysis_unit.source_segment_label,
        "planner_policy_id": manifest_input.analysis_unit.planner_policy_id,
        "tokenizer_id": tokenizer.tokenizer_id,
        "model_profile": manifest_input.model_profile.__dict__,
        "selected": [_candidate_payload(candidate) for candidate in selected],
        "excluded": [
            {"candidate": _candidate_payload(item.candidate), "reason_code": item.reason_code}
            for item in excluded
        ],
        "segments": [segment.__dict__ for segment in segments],
        "evidence_candidates": [_evidence_candidate_payload(item) for item in evidence_candidates],
        "rendered_input_digest": rendered_input_digest,
        "input_token_count": input_token_count,
        "status": status.value,
        "split_strategy_id": split_strategy_id,
        "child_analysis_unit_ids": child_analysis_unit_ids,
        "blocked_reason": blocked_reason,
    }
    manifest_digest = _digest(payload)
    return ContextManifest(
        id=f"ctx_{manifest_digest[:HASH_ID_LENGTH]}",
        analysis_unit_id=manifest_input.analysis_unit.id,
        analysis_unit_payload=cast(
            dict[str, JsonValue], _analysis_unit_payload(manifest_input.analysis_unit)
        ),
        representation_id=manifest_input.analysis_unit.representation_id,
        prompt_id=manifest_input.prompt_id,
        prompt_bytes=manifest_input.prompt_bytes,
        prompt_digest=hashlib.sha256(manifest_input.prompt_bytes).hexdigest(),
        schema_id=manifest_input.schema_id,
        schema_digest=hashlib.sha256(manifest_input.schema_bytes).hexdigest(),
        schema_bytes=manifest_input.schema_bytes,
        renderer_version=manifest_input.renderer_version,
        planner_policy_id=manifest_input.analysis_unit.planner_policy_id,
        tokenizer_id=tokenizer.tokenizer_id,
        model_profile_id=manifest_input.model_profile.id,
        model_context_limit=manifest_input.model_profile.model_context_limit,
        reserved_output_tokens=manifest_input.model_profile.reserved_output_tokens,
        safety_margin_tokens=manifest_input.model_profile.safety_margin_tokens,
        selected_candidates=selected,
        excluded_candidates=excluded,
        rendered_segments=segments,
        rendered_input=rendered_input,
        rendered_input_digest=rendered_input_digest,
        input_token_count=input_token_count,
        manifest_digest=manifest_digest,
        status=status,
        evidence_selection_policy_id=manifest_input.evidence_selection_policy_id,
        source_segment_policy_id=manifest_input.source_segment_policy_id,
        source_segment_label=manifest_input.analysis_unit.source_segment_label,
        evidence_candidates=evidence_candidates,
        split_strategy_id=split_strategy_id,
        child_analysis_unit_ids=child_analysis_unit_ids,
        blocked_reason=blocked_reason,
    )


def _persist_outcome(
    outcome: ContextPlanningOutcome,
    ledger_repository: ContextPlanningLedger,
) -> ContextPlanningOutcome:
    manifest = outcome.manifest
    validate_context_manifest_identity(manifest)
    split_unit_ids = tuple(unit.id for unit in outcome.split_units)
    manifest_unit = _analysis_unit_from_payload(manifest.analysis_unit_payload)
    if (
        manifest_unit.id != manifest.analysis_unit_id
        or manifest_unit.representation_id != manifest.representation_id
    ):
        raise ValueError("ContextManifest analysis-unit payload is corrupted.")
    validate_analysis_unit_identity(manifest_unit)
    for split_unit in outcome.split_units:
        validate_analysis_unit_identity(split_unit)
    if manifest.status is ContextManifestStatus.SPLIT:
        if (
            manifest.split_strategy_id is None
            or not split_unit_ids
            or manifest.child_analysis_unit_ids != split_unit_ids
        ):
            raise ValueError("Split ContextManifest does not match its child AnalysisUnits.")
    elif split_unit_ids:
        raise ValueError("Only split ContextManifest records can persist child AnalysisUnits.")
    manifest_artifact = ContextManifestArtifact(
        id=manifest.id,
        analysis_unit_id=manifest.analysis_unit_id,
        representation_id=manifest.representation_id,
        manifest_digest=manifest.manifest_digest,
        payload=cast(dict[str, JsonValue], _artifact_payload(manifest)),
    )
    child_artifacts = tuple(
        AnalysisUnitArtifact(
            id=unit.id,
            representation_id=unit.representation_id,
            unit_fingerprint=unit.fingerprint,
            payload=cast(dict[str, JsonValue], _analysis_unit_payload(unit)),
        )
        for unit in outcome.split_units
    )
    ledger_repository.commit_context_planning_outcome(
        manifest=manifest_artifact,
        child_analysis_units=child_artifacts,
    )
    return outcome


def context_manifest_digest(manifest: ContextManifest) -> str:
    payload = _artifact_payload(manifest)["integrity"]
    assert isinstance(payload, dict)
    return _digest(cast(dict[str, object], payload))


def validate_context_manifest_identity(manifest: ContextManifest) -> None:
    expected_digest = context_manifest_digest(manifest)
    if manifest.manifest_digest != expected_digest:
        raise ValueError("ContextManifest digest is not derived from its canonical payload.")
    if manifest.id != f"ctx_{expected_digest[:HASH_ID_LENGTH]}":
        raise ValueError("ContextManifest ID is not derived from its canonical digest.")


def load_context_manifest(
    manifest_id: str,
    ledger_repository: ContextPlanningLedger,
    *,
    verified_bundle: DocumentRepresentationBundle | None = None,
) -> ContextManifest:
    """Load the sole canonical manifest representation from the immutable Ledger."""
    artifact = ledger_repository.get_context_manifest_artifact(manifest_id)
    if artifact is None:
        raise ValueError(f"ContextManifest is not persisted: {manifest_id}")
    integrity = artifact.payload.get("integrity")
    rendered = artifact.payload.get("rendered_input_base64")
    if not isinstance(integrity, dict) or not isinstance(rendered, str):
        raise ValueError("ContextManifest persisted artifact is malformed.")
    try:
        manifest = ContextManifest(
            id=artifact.id,
            analysis_unit_id=_required_str(integrity, "analysis_unit_id"),
            analysis_unit_payload=_mapping(integrity, "analysis_unit"),
            representation_id=_required_str(integrity, "representation_id"),
            prompt_id=_required_str(integrity, "prompt_id"),
            prompt_bytes=b64decode(_required_str(integrity, "prompt_bytes_base64"), validate=True),
            prompt_digest=_required_str(integrity, "prompt_digest"),
            schema_id=_required_str(integrity, "schema_id"),
            schema_digest=_required_str(integrity, "schema_digest"),
            schema_bytes=b64decode(_required_str(integrity, "schema_bytes_base64"), validate=True),
            renderer_version=_required_str(integrity, "renderer_version"),
            evidence_selection_policy_id=_optional_str(integrity, "evidence_selection_policy_id"),
            source_segment_policy_id=_optional_str(integrity, "source_segment_policy_id"),
            source_segment_label=_optional_str(integrity, "source_segment_label"),
            planner_policy_id=_required_str(integrity, "planner_policy_id"),
            tokenizer_id=_required_str(integrity, "tokenizer_id"),
            model_profile_id=_required_str(_mapping(integrity, "model_profile"), "id"),
            model_context_limit=_required_int(
                _mapping(integrity, "model_profile"), "model_context_limit"
            ),
            reserved_output_tokens=_required_int(
                _mapping(integrity, "model_profile"), "reserved_output_tokens"
            ),
            safety_margin_tokens=_required_int(
                _mapping(integrity, "model_profile"), "safety_margin_tokens"
            ),
            selected_candidates=tuple(
                _candidate_from_payload(item) for item in _mapping_list(integrity, "selected")
            ),
            excluded_candidates=tuple(
                _excluded_from_payload(item) for item in _mapping_list(integrity, "excluded")
            ),
            rendered_segments=tuple(
                _segment_from_payload(item) for item in _mapping_list(integrity, "segments")
            ),
            rendered_input=b64decode(rendered, validate=True),
            rendered_input_digest=_required_str(integrity, "rendered_input_digest"),
            input_token_count=_required_int(integrity, "input_token_count"),
            manifest_digest=artifact.manifest_digest,
            status=ContextManifestStatus(_required_str(integrity, "status")),
            evidence_candidates=tuple(
                _evidence_candidate_from_payload(item)
                for item in _mapping_list(integrity, "evidence_candidates")
            ),
            split_strategy_id=_optional_str(integrity, "split_strategy_id"),
            child_analysis_unit_ids=_string_tuple_or_empty(integrity, "child_analysis_unit_ids"),
            blocked_reason=_optional_str(integrity, "blocked_reason"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("ContextManifest persisted artifact is malformed.") from exc
    validate_context_manifest(manifest, ledger_repository, verified_bundle=verified_bundle)
    return manifest


def load_split_analysis_units(
    manifest_id: str, ledger_repository: ContextPlanningLedger
) -> tuple[AnalysisUnit, ...]:
    """Resolve the persisted ordered child units of one split planning outcome."""
    manifest = load_context_manifest(manifest_id, ledger_repository)
    if manifest.status is not ContextManifestStatus.SPLIT:
        raise ValueError("ContextManifest is not a split planning outcome.")
    return tuple(
        load_analysis_unit(child_id, ledger_repository)
        for child_id in manifest.child_analysis_unit_ids
    )


def verify_context_manifest(
    manifest_id: str,
    ledger_repository: ContextPlanningLedger,
    tokenizer: ContextTokenizer,
    prompt_bytes: bytes,
    schema_bytes: bytes,
) -> VerifiedContextManifest:
    """Independently recompute the task-local context contract before model use."""
    manifest = load_context_manifest(manifest_id, ledger_repository)
    unit = load_analysis_unit(manifest.analysis_unit_id, ledger_repository)
    if _analysis_unit_payload(unit) != manifest.analysis_unit_payload:
        raise ValueError("ContextManifest analysis unit does not match its persisted artifact.")
    if tokenizer.tokenizer_id != manifest.tokenizer_id:
        raise ValueError("ContextManifest tokenizer identity does not match the runtime tokenizer.")
    if hashlib.sha256(prompt_bytes).hexdigest() != manifest.prompt_digest:
        raise ValueError("ContextManifest prompt bytes do not match the pinned prompt digest.")
    if hashlib.sha256(schema_bytes).hexdigest() != manifest.schema_digest:
        raise ValueError("ContextManifest schema bytes do not match the pinned schema digest.")
    if schema_bytes != manifest.schema_bytes:
        raise ValueError("ContextManifest schema bytes do not match the persisted schema bytes.")
    if prompt_bytes != manifest.prompt_bytes:
        raise ValueError("ContextManifest prompt bytes do not match the persisted prompt bytes.")
    bundle = _load_acceptable_bundle(manifest.representation_id, ledger_repository)
    _validate_evidence_candidates(manifest, bundle)
    rendered, segments = _render_verified_input(manifest, bundle, prompt_bytes, schema_bytes)
    if rendered != manifest.rendered_input or segments != manifest.rendered_segments:
        raise ValueError("ContextManifest rendered input or segment boundaries are corrupted.")
    if tokenizer.count_tokens(rendered) != manifest.input_token_count:
        raise ValueError("ContextManifest exact token count is corrupted.")
    budget = (
        manifest.model_context_limit
        - manifest.reserved_output_tokens
        - manifest.safety_margin_tokens
    )
    if manifest.status is ContextManifestStatus.READY and manifest.input_token_count > budget:
        raise ValueError("Ready ContextManifest exceeds its exact token budget.")
    if manifest.status is not ContextManifestStatus.READY and manifest.rendered_input:
        raise ValueError("Non-ready ContextManifest must not contain a model input.")
    if manifest.status is ContextManifestStatus.SPLIT:
        if manifest.split_strategy_id is None or not manifest.child_analysis_unit_ids:
            raise ValueError("Split ContextManifest requires strategy and ordered child units.")
        for child_id in manifest.child_analysis_unit_ids:
            child = load_analysis_unit(child_id, ledger_repository)
            if child.representation_id != manifest.representation_id:
                raise ValueError("Split ContextManifest child belongs to another representation.")
    elif manifest.split_strategy_id is not None or manifest.child_analysis_unit_ids:
        raise ValueError("Only split ContextManifest records can reference child units.")
    if manifest.status is ContextManifestStatus.CONTEXT_BUDGET_BLOCKED:
        if manifest.blocked_reason is None:
            raise ValueError("Blocked ContextManifest requires a blocked reason.")
    elif manifest.blocked_reason is not None:
        raise ValueError("Only blocked ContextManifest records can have a blocked reason.")
    return VerifiedContextManifest(manifest)


def validate_context_manifest(
    manifest: ContextManifest,
    ledger_repository: ContextPlanningLedger,
    *,
    verified_bundle: DocumentRepresentationBundle | None = None,
) -> None:
    """Verify the persisted manifest and every rendered source segment before use."""
    validate_context_manifest_identity(manifest)
    artifact = ledger_repository.get_context_manifest_artifact(manifest.id)
    if artifact is None:
        raise ValueError(f"ContextManifest is not persisted: {manifest.id}")
    if (
        artifact.analysis_unit_id != manifest.analysis_unit_id
        or artifact.representation_id != manifest.representation_id
        or artifact.manifest_digest != manifest.manifest_digest
        or artifact.payload != _artifact_payload(manifest)
    ):
        raise ValueError("ContextManifest persisted artifact does not match the supplied manifest.")
    integrity_payload = artifact.payload.get("integrity")
    if (
        not isinstance(integrity_payload, dict)
        or _digest(integrity_payload) != manifest.manifest_digest
    ):
        raise ValueError("ContextManifest manifest_digest is corrupted.")
    if hashlib.sha256(manifest.rendered_input).hexdigest() != manifest.rendered_input_digest:
        raise ValueError("ContextManifest rendered_input_digest is corrupted.")
    bundle = (
        _load_acceptable_bundle(manifest.representation_id, ledger_repository)
        if verified_bundle is None
        else verified_bundle
    )
    if (
        bundle.representation.id != manifest.representation_id
        or bundle.quality_report.analyzability is not RepresentationAnalyzability.ACCEPTABLE
    ):
        raise ValueError("ContextManifest verified bundle binding is invalid.")
    _validate_evidence_candidates(manifest, bundle)
    rendered_candidates = manifest.selected_candidates
    if (
        manifest.source_segment_policy_id
        in {
            PARAGRAPH_SEGMENT_V1,
            PARAGRAPH_SEGMENT_V2,
            PARAGRAPH_SEGMENT_V3,
        }
        and manifest.evidence_selection_policy_id != HYBRID_MENTION_EVIDENCE_SELECTION_V1
    ):
        evidence_node_ids = {candidate.node_id for candidate in manifest.evidence_candidates}
        rendered_candidates = tuple(
            candidate
            for candidate in manifest.selected_candidates
            if candidate.node_id in evidence_node_ids
        )
    if len(rendered_candidates) != len(manifest.rendered_segments):
        raise ValueError("ContextManifest selected candidates and rendered segments disagree.")
    prior_end = 0
    for candidate, segment in zip(rendered_candidates, manifest.rendered_segments, strict=True):
        if candidate.node_id != segment.node_id or segment.start_byte < prior_end:
            raise ValueError("ContextManifest rendered segment ordering is corrupted.")
        node = _node_by_id(bundle, candidate.node_id)
        if not set(candidate.source_node_ids).issubset({node.id}):
            raise ValueError("ContextManifest candidate source nodes are corrupted.")
        evidence_candidate = next(
            (item for item in manifest.evidence_candidates if item.node_id == candidate.node_id),
            None,
        )
        rendered_node = _render_node(
            node,
            _text_view_by_id(bundle, node.text_view_id),
            evidence_candidate_id=(evidence_candidate.id if evidence_candidate else None),
            include_node_id=manifest.evidence_selection_policy_id is None,
            direct_prose=manifest.evidence_selection_policy_id
            in {
                DIRECT_PROSE_EVIDENCE_SELECTION_V1,
                PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
                HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            },
            source_segment_policy_id=(
                manifest.source_segment_policy_id if evidence_candidate is not None else None
            ),
            source_segment_label=manifest.source_segment_label,
        )
        if manifest.rendered_input[segment.start_byte : segment.end_byte] != rendered_node:
            raise ValueError("ContextManifest rendered segment does not match its DocumentNode.")
        prior_end = segment.end_byte


def _artifact_payload(manifest: ContextManifest) -> dict[str, object]:
    integrity = {
        "analysis_unit_id": manifest.analysis_unit_id,
        "analysis_unit": manifest.analysis_unit_payload,
        "representation_id": manifest.representation_id,
        "prompt_id": manifest.prompt_id,
        "prompt_bytes_base64": b64encode(manifest.prompt_bytes).decode("ascii"),
        "prompt_digest": manifest.prompt_digest,
        "schema_id": manifest.schema_id,
        "schema_digest": manifest.schema_digest,
        "schema_bytes_base64": b64encode(manifest.schema_bytes).decode("ascii"),
        "renderer_version": manifest.renderer_version,
        "evidence_selection_policy_id": manifest.evidence_selection_policy_id,
        "source_segment_policy_id": manifest.source_segment_policy_id,
        "source_segment_label": manifest.source_segment_label,
        "planner_policy_id": manifest.planner_policy_id,
        "tokenizer_id": manifest.tokenizer_id,
        "model_profile": {
            "id": manifest.model_profile_id,
            "model_context_limit": manifest.model_context_limit,
            "reserved_output_tokens": manifest.reserved_output_tokens,
            "safety_margin_tokens": manifest.safety_margin_tokens,
        },
        "selected": [_candidate_payload(candidate) for candidate in manifest.selected_candidates],
        "excluded": [
            {"candidate": _candidate_payload(item.candidate), "reason_code": item.reason_code}
            for item in manifest.excluded_candidates
        ],
        "segments": [segment.__dict__ for segment in manifest.rendered_segments],
        "evidence_candidates": [
            _evidence_candidate_payload(item) for item in manifest.evidence_candidates
        ],
        "rendered_input_digest": manifest.rendered_input_digest,
        "input_token_count": manifest.input_token_count,
        "status": manifest.status.value,
        "split_strategy_id": manifest.split_strategy_id,
        "child_analysis_unit_ids": manifest.child_analysis_unit_ids,
        "blocked_reason": manifest.blocked_reason,
    }
    payload = {
        "integrity": integrity,
        "rendered_input_base64": b64encode(manifest.rendered_input).decode("ascii"),
    }
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _render_verified_input(
    manifest: ContextManifest,
    bundle: DocumentRepresentationBundle,
    prompt_bytes: bytes,
    schema_bytes: bytes,
) -> tuple[bytes, tuple[RenderedContextSegment, ...]]:
    rendered = bytearray(prompt_bytes + b"\n\n" + schema_bytes)
    segments: list[RenderedContextSegment] = []
    evidence_by_node_id = {
        candidate.node_id: candidate for candidate in manifest.evidence_candidates
    }
    rendered_candidates = manifest.selected_candidates
    if (
        manifest.source_segment_policy_id
        in {
            PARAGRAPH_SEGMENT_V1,
            PARAGRAPH_SEGMENT_V2,
            PARAGRAPH_SEGMENT_V3,
        }
        and manifest.evidence_selection_policy_id != HYBRID_MENTION_EVIDENCE_SELECTION_V1
    ):
        evidence_node_ids = {candidate.node_id for candidate in manifest.evidence_candidates}
        rendered_candidates = tuple(
            candidate
            for candidate in manifest.selected_candidates
            if candidate.node_id in evidence_node_ids
        )
    for candidate in rendered_candidates:
        node = _node_by_id(bundle, candidate.node_id)
        evidence_candidate = evidence_by_node_id.get(node.id)
        segment = _render_node(
            node,
            _text_view_by_id(bundle, node.text_view_id),
            evidence_candidate_id=(evidence_candidate.id if evidence_candidate else None),
            include_node_id=manifest.evidence_selection_policy_id is None,
            direct_prose=manifest.evidence_selection_policy_id
            in {
                DIRECT_PROSE_EVIDENCE_SELECTION_V1,
                PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
                HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            },
            source_segment_policy_id=(
                manifest.source_segment_policy_id if evidence_candidate is not None else None
            ),
            source_segment_label=manifest.source_segment_label,
        )
        rendered.extend(b"\n\n")
        start_byte = len(rendered)
        rendered.extend(segment)
        segments.append(RenderedContextSegment(node.id, start_byte, len(rendered)))
    return bytes(rendered), tuple(segments)


def _mapping(value: dict[str, JsonValue], key: str) -> dict[str, JsonValue]:
    candidate = value[key]
    if not isinstance(candidate, dict):
        raise TypeError(key)
    return candidate


def _mapping_list(value: dict[str, JsonValue], key: str) -> list[dict[str, JsonValue]]:
    candidate = value[key]
    if not isinstance(candidate, list) or not all(isinstance(item, dict) for item in candidate):
        raise TypeError(key)
    return [cast(dict[str, JsonValue], item) for item in candidate]


def _required_str(value: dict[str, JsonValue], key: str) -> str:
    candidate = value[key]
    if not isinstance(candidate, str):
        raise TypeError(key)
    return candidate


def _required_int(value: dict[str, JsonValue], key: str) -> int:
    candidate = value[key]
    if not isinstance(candidate, int):
        raise TypeError(key)
    return candidate


def _required_bool(value: dict[str, JsonValue], key: str) -> bool:
    candidate = value[key]
    if not isinstance(candidate, bool):
        raise TypeError(key)
    return candidate


def _optional_str(value: dict[str, JsonValue], key: str) -> str | None:
    candidate = value.get(key)
    if candidate is not None and not isinstance(candidate, str):
        raise TypeError(key)
    return candidate


def _string_tuple(value: dict[str, JsonValue], key: str) -> tuple[str, ...]:
    candidate = value[key]
    if not isinstance(candidate, list) or not all(isinstance(item, str) for item in candidate):
        raise TypeError(key)
    return tuple(cast(str, item) for item in candidate)


def _string_tuple_or_empty(value: dict[str, JsonValue], key: str) -> tuple[str, ...]:
    if key not in value:
        return ()
    return _string_tuple(value, key)


def _candidate_from_payload(value: dict[str, JsonValue]) -> ContextCandidate:
    return ContextCandidate(
        node_id=_required_str(value, "node_id"),
        role=ContextCandidateRole(_required_str(value, "role")),
        reason_code=_required_str(value, "reason_code"),
        required=_required_bool(value, "required"),
        priority=_required_int(value, "priority"),
        dependency_path=_string_tuple(value, "dependency_path"),
        source_node_ids=_string_tuple(value, "source_node_ids"),
        estimated_tokens=_required_int(value, "estimated_tokens"),
    )


def _evidence_candidate_from_payload(value: dict[str, JsonValue]) -> EvidenceCandidate:
    return EvidenceCandidate(
        id=_required_str(value, "id"),
        node_id=_required_str(value, "node_id"),
        text_view_id=_required_str(value, "text_view_id"),
        start_char=_required_int(value, "start_char"),
        end_char=_required_int(value, "end_char"),
        source_region_ids=_string_tuple(value, "source_region_ids"),
    )


def _excluded_from_payload(value: dict[str, JsonValue]) -> ExcludedContextCandidate:
    return ExcludedContextCandidate(
        _candidate_from_payload(_mapping(value, "candidate")), _required_str(value, "reason_code")
    )


def _segment_from_payload(value: dict[str, JsonValue]) -> RenderedContextSegment:
    return RenderedContextSegment(
        _required_str(value, "node_id"),
        _required_int(value, "start_byte"),
        _required_int(value, "end_byte"),
    )


def _candidate_payload(candidate: ContextCandidate) -> dict[str, object]:
    return {
        "node_id": candidate.node_id,
        "role": candidate.role.value,
        "reason_code": candidate.reason_code,
        "required": candidate.required,
        "priority": candidate.priority,
        "dependency_path": candidate.dependency_path,
        "source_node_ids": candidate.source_node_ids,
        "estimated_tokens": candidate.estimated_tokens,
    }


def _evidence_candidate_payload(candidate: EvidenceCandidate) -> dict[str, object]:
    return {
        "id": candidate.id,
        "node_id": candidate.node_id,
        "text_view_id": candidate.text_view_id,
        "start_char": candidate.start_char,
        "end_char": candidate.end_char,
        "source_region_ids": candidate.source_region_ids,
    }


def _validate_evidence_candidates(
    manifest: ContextManifest,
    bundle: DocumentRepresentationBundle,
) -> None:
    if manifest.evidence_selection_policy_id is None:
        if manifest.evidence_candidates:
            raise ValueError("ContextManifest has evidence candidates without a selection policy.")
        return
    if manifest.evidence_selection_policy_id not in {
        FOCUS_NODE_EVIDENCE_SELECTION_V1,
        DIRECT_PROSE_EVIDENCE_SELECTION_V1,
        PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
        HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    }:
        raise ValueError("ContextManifest references an unsupported evidence selection policy.")
    if manifest.status is not ContextManifestStatus.READY:
        if manifest.evidence_candidates:
            raise ValueError("Only ready ContextManifest records can expose evidence candidates.")
        return
    expected = _evidence_candidates_for_context(
        manifest.evidence_selection_policy_id,
        manifest.selected_candidates,
        bundle,
    )
    if manifest.evidence_candidates != expected:
        raise ValueError("ContextManifest evidence candidate catalogue is corrupted.")
    if manifest.source_segment_policy_id not in {
        None,
        PARAGRAPH_SEGMENT_V1,
        PARAGRAPH_SEGMENT_V2,
        PARAGRAPH_SEGMENT_V3,
    }:
        raise ValueError("ContextManifest references an unsupported source segment policy.")
    if manifest.source_segment_policy_id in {
        PARAGRAPH_SEGMENT_V1,
        PARAGRAPH_SEGMENT_V2,
        PARAGRAPH_SEGMENT_V3,
    }:
        if manifest.evidence_selection_policy_id not in {
            PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            HYBRID_MENTION_EVIDENCE_SELECTION_V1,
        }:
            raise ValueError("Paragraph segments require a supported paragraph evidence policy.")
        if len(manifest.evidence_candidates) != 1:
            raise ValueError("Paragraph segments require exactly one evidence candidate.")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
