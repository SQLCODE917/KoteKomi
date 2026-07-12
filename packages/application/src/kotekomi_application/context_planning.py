"""Deterministic bounded context planning over pinned Document representations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentationBundle,
    RepresentationAnalyzability,
    TextView,
    canonical_representation_digest,
)

HASH_ID_LENGTH = 24


class ContextCandidateRole(StrEnum):
    FOCUS = "focus"
    HEADING = "heading"
    DEFINITION = "definition"
    FURNITURE = "furniture"


class ContextManifestStatus(StrEnum):
    READY = "ready"
    SPLIT = "split"
    CONTEXT_BUDGET_BLOCKED = "context_budget_blocked"


class ContextPlanningLedger(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class ContextTokenizer(Protocol):
    @property
    def tokenizer_id(self) -> str: ...

    def count_tokens(self, rendered_input: bytes) -> int: ...


@dataclass(frozen=True)
class AnalysisUnitPlanningInput:
    representation_id: str
    policy_id: str
    task_type: str


@dataclass(frozen=True)
class AnalysisUnit:
    id: str
    representation_id: str
    task_type: str
    focus_node_ids: tuple[str, ...]
    dependency_node_ids: tuple[str, ...]
    planner_policy_id: str
    fingerprint: str


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


@dataclass(frozen=True)
class ContextManifest:
    id: str
    analysis_unit_id: str
    representation_id: str
    prompt_id: str
    schema_id: str
    renderer_version: str
    planner_policy_id: str
    tokenizer_id: str
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


@dataclass(frozen=True)
class ContextPlanningOutcome:
    manifest: ContextManifest
    split_units: tuple[AnalysisUnit, ...] = ()
    blocked_reason: str | None = None


def plan_analysis_units(
    planning_input: AnalysisUnitPlanningInput,
    ledger_repository: ContextPlanningLedger,
) -> AnalysisPlan:
    """Create one deterministic paragraph analysis unit from each pinned paragraph node."""
    bundle = _load_acceptable_bundle(planning_input.representation_id, ledger_repository)
    units = tuple(
        _analysis_unit(
            representation_id=bundle.representation.id,
            task_type=planning_input.task_type,
            focus_node=node,
            dependency_nodes=_definition_nodes_for_focus(node, bundle),
            policy_id=planning_input.policy_id,
        )
        for node in sorted(
            bundle.nodes, key=lambda candidate: (candidate.order_index, candidate.id)
        )
        if node.node_type == "paragraph"
    )
    return AnalysisPlan(bundle.representation.id, planning_input.policy_id, units)


def build_context_manifest(
    manifest_input: ContextManifestInput,
    ledger_repository: ContextPlanningLedger,
    tokenizer: ContextTokenizer,
) -> ContextPlanningOutcome:
    """Pack required context exactly or return a deterministic split or blocked outcome."""
    unit = manifest_input.analysis_unit
    bundle = _load_acceptable_bundle(unit.representation_id, ledger_repository)
    _require_unit_matches_representation(unit, bundle)
    candidates = _context_candidates(unit, bundle, tokenizer)
    token_budget = (
        manifest_input.model_profile.model_context_limit
        - manifest_input.model_profile.reserved_output_tokens
        - manifest_input.model_profile.safety_margin_tokens
    )
    if token_budget <= 0:
        return _blocked_outcome(manifest_input, tokenizer, candidates, "nonpositive_context_budget")
    required = tuple(candidate for candidate in candidates if candidate.required)
    rendered_input, segments = _render_context(manifest_input, required, bundle)
    if tokenizer.count_tokens(rendered_input) <= token_budget:
        excluded = tuple(
            ExcludedContextCandidate(candidate, "furniture_excluded")
            for candidate in candidates
            if not candidate.required
        )
        return ContextPlanningOutcome(
            _manifest(
                manifest_input,
                tokenizer,
                selected=required,
                excluded=excluded,
                rendered_input=rendered_input,
                segments=segments,
                status=ContextManifestStatus.READY,
            )
        )
    if len(unit.focus_node_ids) > 1:
        split_units = tuple(
            _analysis_unit(
                representation_id=unit.representation_id,
                task_type=unit.task_type,
                focus_node=_node_by_id(bundle, node_id),
                dependency_nodes=_definition_nodes_for_focus(_node_by_id(bundle, node_id), bundle),
                policy_id=unit.planner_policy_id,
            )
            for node_id in sorted(unit.focus_node_ids)
        )
        return ContextPlanningOutcome(
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
            ),
            split_units=split_units,
        )
    return _blocked_outcome(
        manifest_input,
        tokenizer,
        candidates,
        "required_context_exceeds_budget",
    )


def render_context(manifest: ContextManifest) -> bytes:
    """Return the byte-exact finalized model input committed by a ContextManifest."""
    if hashlib.sha256(manifest.rendered_input).hexdigest() != manifest.rendered_input_digest:
        raise ValueError("ContextManifest rendered_input_digest is corrupted.")
    return manifest.rendered_input


def _analysis_unit(
    *,
    representation_id: str,
    task_type: str,
    focus_node: DocumentNode,
    dependency_nodes: tuple[DocumentNode, ...],
    policy_id: str,
) -> AnalysisUnit:
    dependency_ids = tuple(node.id for node in dependency_nodes)
    fingerprint = _digest(
        {
            "representation_id": representation_id,
            "task_type": task_type,
            "focus_node_ids": (focus_node.id,),
            "dependency_node_ids": dependency_ids,
            "planner_policy_id": policy_id,
        }
    )
    return AnalysisUnit(
        id=f"anu_{fingerprint[:HASH_ID_LENGTH]}",
        representation_id=representation_id,
        task_type=task_type,
        focus_node_ids=(focus_node.id,),
        dependency_node_ids=dependency_ids,
        planner_policy_id=policy_id,
        fingerprint=fingerprint,
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
        heading = _nearest_ancestor_heading(focus, bundle)
        if heading is not None:
            candidates[heading.id] = _candidate(
                heading,
                ContextCandidateRole.HEADING,
                "ancestor_heading",
                True,
                3,
                (focus.id, heading.id),
                tokenizer,
                bundle,
            )
    for dependency_id in unit.dependency_node_ids:
        dependency = nodes.get(dependency_id)
        if dependency is None:
            raise ValueError(f"AnalysisUnit references missing dependency node: {dependency_id}")
        focus_id = unit.focus_node_ids[0]
        candidates[dependency.id] = _candidate(
            dependency,
            ContextCandidateRole.DEFINITION,
            "acronym_definition",
            True,
            4,
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
                len(candidate.dependency_path),
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
) -> tuple[bytes, tuple[RenderedContextSegment, ...]]:
    rendered = bytearray(manifest_input.prompt_bytes + b"\n\n" + manifest_input.schema_bytes)
    segments: list[RenderedContextSegment] = []
    for candidate in candidates:
        node = _node_by_id(bundle, candidate.node_id)
        segment = _render_node(node, _text_view_by_id(bundle, node.text_view_id))
        rendered.extend(b"\n\n")
        start_byte = len(rendered)
        rendered.extend(segment)
        segments.append(RenderedContextSegment(node.id, start_byte, len(rendered)))
    return bytes(rendered), tuple(segments)


def _render_node(node: DocumentNode, text_view: TextView) -> bytes:
    text = text_view.text[node.start_char : node.end_char]
    return f"[{node.node_type}:{node.id}]\n{text}".encode()


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
            and f"({acronym})" in _node_text(node, bundle)
        )
        if matches:
            definitions.append(max(matches, key=lambda node: (node.order_index, node.id)))
    return tuple(sorted({node.id: node for node in definitions}.values(), key=lambda node: node.id))


def _nearest_ancestor_heading(
    focus_node: DocumentNode,
    bundle: DocumentRepresentationBundle,
) -> DocumentNode | None:
    headings = tuple(
        node
        for node in bundle.nodes
        if node.node_type == "heading" and node.order_index < focus_node.order_index
    )
    return max(headings, key=lambda node: (node.order_index, node.id), default=None)


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
    )
    if actual_digest != bundle.representation.canonical_output_digest:
        raise ValueError("Context planning DocumentRepresentation digest is corrupted.")
    return bundle


def _require_unit_matches_representation(
    unit: AnalysisUnit,
    bundle: DocumentRepresentationBundle,
) -> None:
    if unit.representation_id != bundle.representation.id:
        raise ValueError("AnalysisUnit does not belong to the pinned DocumentRepresentation.")
    if not unit.focus_node_ids:
        raise ValueError("AnalysisUnit requires at least one focus node.")


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
) -> ContextManifest:
    input_token_count = tokenizer.count_tokens(rendered_input)
    rendered_input_digest = hashlib.sha256(rendered_input).hexdigest()
    payload = {
        "analysis_unit_id": manifest_input.analysis_unit.id,
        "representation_id": manifest_input.analysis_unit.representation_id,
        "prompt_id": manifest_input.prompt_id,
        "schema_id": manifest_input.schema_id,
        "renderer_version": manifest_input.renderer_version,
        "planner_policy_id": manifest_input.analysis_unit.planner_policy_id,
        "tokenizer_id": tokenizer.tokenizer_id,
        "model_profile": manifest_input.model_profile.__dict__,
        "selected": [_candidate_payload(candidate) for candidate in selected],
        "excluded": [
            {"candidate": _candidate_payload(item.candidate), "reason_code": item.reason_code}
            for item in excluded
        ],
        "segments": [segment.__dict__ for segment in segments],
        "rendered_input_digest": rendered_input_digest,
        "input_token_count": input_token_count,
        "status": status.value,
    }
    manifest_digest = _digest(payload)
    return ContextManifest(
        id=f"ctx_{manifest_digest[:HASH_ID_LENGTH]}",
        analysis_unit_id=manifest_input.analysis_unit.id,
        representation_id=manifest_input.analysis_unit.representation_id,
        prompt_id=manifest_input.prompt_id,
        schema_id=manifest_input.schema_id,
        renderer_version=manifest_input.renderer_version,
        planner_policy_id=manifest_input.analysis_unit.planner_policy_id,
        tokenizer_id=tokenizer.tokenizer_id,
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


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
