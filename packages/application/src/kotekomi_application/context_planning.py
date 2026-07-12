"""Deterministic bounded context planning over pinned Document representations."""

from __future__ import annotations

import hashlib
import json
import re
from base64 import b64decode, b64encode
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

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
    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None: ...
    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None: ...
    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None: ...
    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None: ...


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
    """Create one deterministic paragraph analysis unit from each pinned paragraph node."""
    bundle = _load_acceptable_bundle(planning_input.representation_id, ledger_repository)
    paragraphs = tuple(
        node
        for node in sorted(
            bundle.nodes, key=lambda candidate: (candidate.order_index, candidate.id)
        )
        if node.node_type == "paragraph"
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
            paragraphs[index : index + planning_input.max_focus_nodes_per_unit]
            for index in range(0, len(paragraphs), planning_input.max_focus_nodes_per_unit)
        )
    )
    plan = AnalysisPlan(bundle.representation.id, planning_input.policy_id, units)
    for unit in plan.units:
        persist_analysis_unit(unit, ledger_repository)
    return plan


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
    rendered_input, segments = _render_context(manifest_input, required, bundle)
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
) -> AnalysisUnit:
    dependency_ids = tuple(node.id for node in dependency_nodes)
    fingerprint = _digest(
        {
            "representation_id": representation_id,
            "task_type": task_type,
            "focus_node_ids": tuple(node.id for node in focus_nodes),
            "dependency_node_ids": dependency_ids,
            "planner_policy_id": policy_id,
        }
    )
    return AnalysisUnit(
        id=f"anu_{fingerprint[:HASH_ID_LENGTH]}",
        representation_id=representation_id,
        task_type=task_type,
        focus_node_ids=tuple(node.id for node in focus_nodes),
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


def _analysis_unit_payload(unit: AnalysisUnit) -> dict[str, object]:
    return {
        "id": unit.id,
        "representation_id": unit.representation_id,
        "task_type": unit.task_type,
        "focus_node_ids": list(unit.focus_node_ids),
        "dependency_node_ids": list(unit.dependency_node_ids),
        "planner_policy_id": unit.planner_policy_id,
        "fingerprint": unit.fingerprint,
    }


def persist_analysis_unit(unit: AnalysisUnit, ledger_repository: ContextPlanningLedger) -> None:
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
    payload = artifact.payload
    try:
        unit = AnalysisUnit(
            id=_required_str(payload, "id"),
            representation_id=_required_str(payload, "representation_id"),
            task_type=_required_str(payload, "task_type"),
            focus_node_ids=_string_tuple(payload, "focus_node_ids"),
            dependency_node_ids=_string_tuple(payload, "dependency_node_ids"),
            planner_policy_id=_required_str(payload, "planner_policy_id"),
            fingerprint=_required_str(payload, "fingerprint"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("AnalysisUnit persisted artifact is malformed.") from exc
    if (
        unit.id != artifact.id
        or unit.representation_id != artifact.representation_id
        or unit.fingerprint != artifact.unit_fingerprint
        or _analysis_unit_payload(unit) != artifact.payload
    ):
        raise ValueError("AnalysisUnit persisted artifact is corrupted.")
    return unit


def _require_persisted_analysis_unit(
    unit: AnalysisUnit, ledger_repository: ContextPlanningLedger
) -> None:
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
        "analysis_unit": _analysis_unit_payload(manifest_input.analysis_unit),
        "representation_id": manifest_input.analysis_unit.representation_id,
        "prompt_id": manifest_input.prompt_id,
        "prompt_bytes_base64": b64encode(manifest_input.prompt_bytes).decode("ascii"),
        "prompt_digest": hashlib.sha256(manifest_input.prompt_bytes).hexdigest(),
        "schema_id": manifest_input.schema_id,
        "schema_bytes_base64": b64encode(manifest_input.schema_bytes).decode("ascii"),
        "schema_digest": hashlib.sha256(manifest_input.schema_bytes).hexdigest(),
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
    )


def _persist_outcome(
    outcome: ContextPlanningOutcome,
    ledger_repository: ContextPlanningLedger,
) -> ContextPlanningOutcome:
    manifest = outcome.manifest
    ledger_repository.save_context_manifest_artifact(
        ContextManifestArtifact(
            id=manifest.id,
            analysis_unit_id=manifest.analysis_unit_id,
            representation_id=manifest.representation_id,
            manifest_digest=manifest.manifest_digest,
            payload=cast(dict[str, JsonValue], _artifact_payload(manifest)),
        )
    )
    return outcome


def persist_context_manifest(
    manifest: ContextManifest,
    ledger_repository: ContextPlanningLedger,
) -> None:
    _persist_outcome(ContextPlanningOutcome(manifest), ledger_repository)


def context_manifest_digest(manifest: ContextManifest) -> str:
    payload = _artifact_payload(manifest)["integrity"]
    assert isinstance(payload, dict)
    return _digest(cast(dict[str, object], payload))


def load_context_manifest(
    manifest_id: str, ledger_repository: ContextPlanningLedger
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
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("ContextManifest persisted artifact is malformed.") from exc
    validate_context_manifest(manifest, ledger_repository)
    return manifest


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
    return VerifiedContextManifest(manifest)


def validate_context_manifest(
    manifest: ContextManifest,
    ledger_repository: ContextPlanningLedger,
) -> None:
    """Verify the persisted manifest and every rendered source segment before use."""
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
    bundle = _load_acceptable_bundle(manifest.representation_id, ledger_repository)
    if len(manifest.selected_candidates) != len(manifest.rendered_segments):
        raise ValueError("ContextManifest selected candidates and rendered segments disagree.")
    prior_end = 0
    for candidate, segment in zip(
        manifest.selected_candidates, manifest.rendered_segments, strict=True
    ):
        if candidate.node_id != segment.node_id or segment.start_byte < prior_end:
            raise ValueError("ContextManifest rendered segment ordering is corrupted.")
        node = _node_by_id(bundle, candidate.node_id)
        if not set(candidate.source_node_ids).issubset({node.id}):
            raise ValueError("ContextManifest candidate source nodes are corrupted.")
        rendered_node = _render_node(node, _text_view_by_id(bundle, node.text_view_id))
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
        "rendered_input_digest": manifest.rendered_input_digest,
        "input_token_count": manifest.input_token_count,
        "status": manifest.status.value,
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
    for candidate in manifest.selected_candidates:
        node = _node_by_id(bundle, candidate.node_id)
        segment = _render_node(node, _text_view_by_id(bundle, node.text_view_id))
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


def _string_tuple(value: dict[str, JsonValue], key: str) -> tuple[str, ...]:
    candidate = value[key]
    if not isinstance(candidate, list) or not all(isinstance(item, str) for item in candidate):
        raise TypeError(key)
    return tuple(cast(str, item) for item in candidate)


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


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
