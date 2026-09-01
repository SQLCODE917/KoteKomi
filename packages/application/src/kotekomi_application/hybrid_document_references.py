"""Deterministic HP-2 document alias and reference evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain import DocumentNode, DocumentRepresentationBundle, TextView
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.context_planning import PARAGRAPH_SEGMENT_V2, paragraph_source_segments
from kotekomi_application.document_aliases import parse_parenthetical_alias
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
    Referentiality,
    hybrid_source_segment_id,
)

HYBRID_REFERENCE_POLICY_ID = "hybrid_document_reference_v1"
ALIAS_DECLARATION_RULE_ID = "exact_parenthetical_initialism_v1"

_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_ID_PATTERN = r"^[a-z]+_[a-f0-9]{24}$"
_ALIAS_MARKER = re.compile(r"\((?P<alias>[A-Za-z0-9.]{2,16})\)")
_NAME_TOKEN = re.compile(r"[^\W_](?:[\w.'’&/-]*[^\W_])?\.?", re.UNICODE)
_CLAUSE_BOUNDARY = re.compile(r"[!?;:\n,]")
_ALIAS_EXPRESSION = re.compile(r"[A-Z0-9.]{2,16}")
_LEADING_FUNCTION_WORDS = frozenset({"a", "an", "and", "at", "for", "in", "of", "on", "the", "to"})


class ReferenceKind(StrEnum):
    EXPLICIT_ALIAS = "explicit_alias"
    ANAPHORIC = "anaphoric"


class ReferenceStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ReferenceReason(StrEnum):
    UNIQUE_EXPLICIT_ALIAS = "unique_explicit_alias"
    CONFLICTING_EXPLICIT_ALIAS = "conflicting_explicit_alias"
    EXPLICIT_ALIAS_MISSING = "explicit_alias_missing"
    SEMANTIC_RESOLUTION_DEFERRED = "semantic_resolution_deferred"


class ReferenceSpan(BaseModel):
    """One exact absolute range in an authoritative TextView."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^rsp_[a-f0-9]{24}$")]
    representation_id: Annotated[str, Field(min_length=1)]
    node_id: Annotated[str, Field(min_length=1)]
    text_view_id: Annotated[str, Field(min_length=1)]
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    text_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("ReferenceSpan requires a valid half-open range.")
        if self.text_sha256 != hashlib.sha256(self.text.encode()).hexdigest():
            raise ValueError("ReferenceSpan digest does not match its text.")
        expected = _id(
            "rsp",
            self.representation_id,
            self.node_id,
            self.text_view_id,
            str(self.start_char),
            str(self.end_char),
            self.text_sha256,
        )
        if self.id != expected:
            raise ValueError("ReferenceSpan ID does not match its source range.")
        return self


class AliasDeclaration(BaseModel):
    """One source-valid expanded-name and initialism declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ald_[a-f0-9]{24}$")]
    expanded_span: ReferenceSpan
    alias_span: ReferenceSpan
    rule_id: Literal["exact_parenthetical_initialism_v1"] = ALIAS_DECLARATION_RULE_ID
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            self.expanded_span.representation_id,
            self.expanded_span.node_id,
            self.expanded_span.text_view_id,
        ) != (
            self.alias_span.representation_id,
            self.alias_span.node_id,
            self.alias_span.text_view_id,
        ):
            raise ValueError("AliasDeclaration spans must share one source node.")
        if self.expanded_span.end_char >= self.alias_span.start_char:
            raise ValueError("AliasDeclaration expanded text must precede its alias.")
        parsed = parse_parenthetical_alias(f"{self.expanded_span.text} ({self.alias_span.text})")
        if parsed is None or not parsed[2]:
            raise ValueError("AliasDeclaration text does not form a valid initialism.")
        expected = _id("ald", self.expanded_span.id, self.alias_span.id, self.rule_id)
        if self.id != expected:
            raise ValueError("AliasDeclaration ID does not match its source spans.")
        return self


class ReferenceDecision(BaseModel):
    """One terminal HP-2 decision for one selected MentionCandidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^rfd_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=_ID_PATTERN)]
    reference_span: ReferenceSpan
    reference_kind: ReferenceKind
    status: ReferenceStatus
    declaration_ids: tuple[Annotated[str, Field(pattern=r"^ald_[a-f0-9]{24}$")], ...] = ()
    antecedent_span_ids: tuple[Annotated[str, Field(pattern=r"^rsp_[a-f0-9]{24}$")], ...] = ()
    reason: ReferenceReason
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _require_ordered_distinct("declaration IDs", self.declaration_ids)
        _require_ordered_distinct("antecedent span IDs", self.antecedent_span_ids)
        if self.status is ReferenceStatus.RESOLVED:
            if (
                self.reference_kind is not ReferenceKind.EXPLICIT_ALIAS
                or self.reason is not ReferenceReason.UNIQUE_EXPLICIT_ALIAS
                or not self.declaration_ids
                or not self.antecedent_span_ids
            ):
                raise ValueError("Resolved ReferenceDecision requires unique alias evidence.")
        elif self.status is ReferenceStatus.AMBIGUOUS:
            if (
                self.reference_kind is not ReferenceKind.EXPLICIT_ALIAS
                or self.reason is not ReferenceReason.CONFLICTING_EXPLICIT_ALIAS
                or len(self.declaration_ids) < 2
                or len(self.antecedent_span_ids) < 2
            ):
                raise ValueError("Ambiguous ReferenceDecision requires conflicting aliases.")
        elif self.declaration_ids or self.antecedent_span_ids:
            raise ValueError("Unresolved ReferenceDecision cannot name an antecedent.")
        if self.status is ReferenceStatus.UNRESOLVED and self.reason not in {
            ReferenceReason.EXPLICIT_ALIAS_MISSING,
            ReferenceReason.SEMANTIC_RESOLUTION_DEFERRED,
        }:
            raise ValueError("Unresolved ReferenceDecision requires an unresolved reason.")
        if (
            self.reason is ReferenceReason.SEMANTIC_RESOLUTION_DEFERRED
            and self.reference_kind is not ReferenceKind.ANAPHORIC
        ):
            raise ValueError("Deferred semantic resolution requires an anaphoric reference.")
        expected = _id(
            "rfd",
            self.candidate_id,
            self.reference_span.id,
            self.reference_kind.value,
            self.status.value,
            self.reason.value,
            *self.declaration_ids,
            *self.antecedent_span_ids,
        )
        if self.id != expected:
            raise ValueError("ReferenceDecision ID does not match its evidence.")
        return self


class HybridReferencePreview(BaseModel):
    """Immutable derived evidence for one complete HP-2 replay."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_reference_preview_v1"] = "hybrid_reference_preview_v1"
    id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    representation_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_document_reference_v1"] = HYBRID_REFERENCE_POLICY_ID
    alias_declarations: tuple[AliasDeclaration, ...] = ()
    reference_decisions: tuple[ReferenceDecision, ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: Literal["complete"] = "complete"
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _require_ordered_distinct("diagnostics", self.diagnostics)
        if tuple(sorted(self.alias_declarations, key=_declaration_key)) != self.alias_declarations:
            raise ValueError("HybridReferencePreview declarations must use source order.")
        if tuple(sorted(self.reference_decisions, key=_decision_key)) != self.reference_decisions:
            raise ValueError("HybridReferencePreview decisions must use source order.")
        if tuple(sorted(self.traces, key=_trace_key)) != self.traces:
            raise ValueError("HybridReferencePreview traces must be ordered.")
        declaration_by_id = {item.id: item for item in self.alias_declarations}
        if len(declaration_by_id) != len(self.alias_declarations):
            raise ValueError("HybridReferencePreview repeats an AliasDeclaration.")
        decision_ids = {item.id for item in self.reference_decisions}
        if len(decision_ids) != len(self.reference_decisions):
            raise ValueError("HybridReferencePreview repeats a ReferenceDecision.")
        trace_ids = {item.id for item in self.traces}
        if len(trace_ids) != len(self.traces):
            raise ValueError("HybridReferencePreview repeats an ExtractionStageTrace.")
        if any(item.trace_id not in trace_ids for item in self.alias_declarations):
            raise ValueError("HybridReferencePreview declaration trace is missing.")
        if any(item.trace_id not in trace_ids for item in self.reference_decisions):
            raise ValueError("HybridReferencePreview decision trace is missing.")
        for decision in self.reference_decisions:
            if not set(decision.declaration_ids).issubset(declaration_by_id):
                raise ValueError("ReferenceDecision references an unknown declaration.")
            expected_spans = {
                declaration_by_id[item].expanded_span.id for item in decision.declaration_ids
            }
            if set(decision.antecedent_span_ids) != expected_spans:
                raise ValueError("ReferenceDecision antecedent spans do not match declarations.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        for trace_run in traces_by_run.values():
            validate_extraction_stage_trace_chain(tuple(trace_run))
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridReferencePreview ID does not match its contents.")
        return self


def build_hybrid_reference_preview(
    *,
    parent_preview: HybridExtractionPreview,
    parent_preview_sha256: str,
    bundle: DocumentRepresentationBundle,
) -> HybridReferencePreview:
    """Resolve deterministic document aliases from one verified HP-1 Preview."""
    if parent_preview.terminal_status is HybridPreviewStatus.BLOCKED:
        raise ValueError("HP-2 cannot consume a blocked HybridExtractionPreview.")
    if bundle.representation.id != parent_preview.representation_id:
        raise ValueError("HP-2 representation does not match its parent Preview.")
    paragraph_node = _node(bundle, parent_preview.paragraph_node_id)
    if paragraph_node.node_type != "paragraph":
        raise ValueError("HP-2 parent Preview node is not a paragraph.")
    declarations, declaration_traces = find_alias_declarations(bundle)
    segment_sources = _parent_segment_sources(bundle, paragraph_node)
    selected_ids = {
        candidate_id
        for decision in parent_preview.boundary_decisions
        for candidate_id in decision.selected_candidate_ids
    }
    interpretation_by_candidate = {
        interpretation.candidate_id: interpretation
        for interpretation in parent_preview.interpretations
    }
    declarations_by_alias: dict[str, list[AliasDeclaration]] = defaultdict(list)
    for declaration in declarations:
        declarations_by_alias[declaration.alias_span.text].append(declaration)
    decisions: list[ReferenceDecision] = []
    decision_traces: list[ExtractionStageTrace] = []
    for candidate in parent_preview.candidates:
        if candidate.id not in selected_ids:
            continue
        segment = segment_sources.get(candidate.source_segment_id)
        if segment is None:
            raise ValueError("HP-2 cannot reconstruct a parent Preview SourceSegment.")
        source_text, segment_start = segment
        if hashlib.sha256(source_text.encode()).hexdigest() != candidate.source_text_sha256:
            raise ValueError("HP-2 MentionCandidate source digest drifted.")
        if (
            candidate.end > len(source_text)
            or source_text[candidate.start : candidate.end] != candidate.text
        ):
            raise ValueError("HP-2 MentionCandidate does not match source characters.")
        reference_span = _span(
            bundle.representation.id,
            paragraph_node,
            _text_view(bundle, paragraph_node.text_view_id),
            paragraph_node.start_char + segment_start + candidate.start,
            paragraph_node.start_char + segment_start + candidate.end,
        )
        matching = tuple(
            sorted(declarations_by_alias.get(candidate.text, ()), key=_declaration_key)
        )
        if matching:
            expanded_literals = {item.expanded_span.text for item in matching}
            if len(expanded_literals) == 1:
                kind = ReferenceKind.EXPLICIT_ALIAS
                status = ReferenceStatus.RESOLVED
                reason = ReferenceReason.UNIQUE_EXPLICIT_ALIAS
            else:
                kind = ReferenceKind.EXPLICIT_ALIAS
                status = ReferenceStatus.AMBIGUOUS
                reason = ReferenceReason.CONFLICTING_EXPLICIT_ALIAS
        elif _is_alias_expression(candidate.text):
            kind = ReferenceKind.EXPLICIT_ALIAS
            status = ReferenceStatus.UNRESOLVED
            reason = ReferenceReason.EXPLICIT_ALIAS_MISSING
        elif (
            candidate.id in interpretation_by_candidate
            and interpretation_by_candidate[candidate.id].referentiality is Referentiality.ANAPHORIC
        ):
            kind = ReferenceKind.ANAPHORIC
            status = ReferenceStatus.UNRESOLVED
            reason = ReferenceReason.SEMANTIC_RESOLUTION_DEFERRED
        else:
            continue
        declaration_ids = tuple(sorted(item.id for item in matching))
        antecedent_span_ids = tuple(sorted({item.expanded_span.id for item in matching}))
        decision_id = _decision_id(
            candidate.id,
            reference_span.id,
            kind,
            status,
            reason,
            declaration_ids,
            antecedent_span_ids,
        )
        trace = build_extraction_stage_trace(
            trace_run_id=_id("hrr", parent_preview.id, candidate.id),
            ordinal=0,
            stage_id="document_reference_resolution",
            stage_version=HYBRID_REFERENCE_POLICY_ID,
            producer_id="kotekomi_application",
            source_segment_id=candidate.source_segment_id,
            source_text_sha256=candidate.source_text_sha256,
            input_record_ids=tuple(sorted((parent_preview.id, candidate.id, *declaration_ids))),
            configuration={"policy_id": HYBRID_REFERENCE_POLICY_ID},
            input_payload={
                "candidate_id": candidate.id,
                "candidate_text": candidate.text,
                "declaration_ids": list(declaration_ids),
                "source_text": source_text,
            },
            output_payload={
                "decision_id": decision_id,
                "reference_kind": kind.value,
                "status": status.value,
                "reason": reason.value,
                "antecedent_span_ids": list(antecedent_span_ids),
            },
            status=ExtractionStageStatus.COMPLETED,
        )
        decisions.append(
            ReferenceDecision(
                id=decision_id,
                candidate_id=candidate.id,
                reference_span=reference_span,
                reference_kind=kind,
                status=status,
                declaration_ids=declaration_ids,
                antecedent_span_ids=antecedent_span_ids,
                reason=reason,
                trace_id=trace.id,
            )
        )
        decision_traces.append(trace)
    return build_hybrid_reference_preview_record(
        parent_preview_id=parent_preview.id,
        parent_preview_sha256=parent_preview_sha256,
        representation_id=bundle.representation.id,
        alias_declarations=declarations,
        reference_decisions=tuple(sorted(decisions, key=_decision_key)),
        traces=tuple(sorted((*declaration_traces, *decision_traces), key=_trace_key)),
    )


def find_alias_declarations(
    bundle: DocumentRepresentationBundle,
) -> tuple[tuple[AliasDeclaration, ...], tuple[ExtractionStageTrace, ...]]:
    """Find every valid explicit initialism declaration in paragraph source text."""
    declarations: list[AliasDeclaration] = []
    traces: list[ExtractionStageTrace] = []
    for node in sorted(bundle.nodes, key=lambda item: (item.order_index, item.id)):
        if node.node_type != "paragraph":
            continue
        view = _text_view(bundle, node.text_view_id)
        source_text = view.text[node.start_char : node.end_char]
        found = _declaration_ranges(source_text)
        for ordinal, (expanded_start, expanded_end, alias_start, alias_end) in enumerate(found):
            expanded_span = _span(
                bundle.representation.id,
                node,
                view,
                node.start_char + expanded_start,
                node.start_char + expanded_end,
            )
            alias_span = _span(
                bundle.representation.id,
                node,
                view,
                node.start_char + alias_start,
                node.start_char + alias_end,
            )
            declaration_id = _id("ald", expanded_span.id, alias_span.id, ALIAS_DECLARATION_RULE_ID)
            trace = build_extraction_stage_trace(
                trace_run_id=_id("hrr", bundle.representation.id, node.id, "aliases"),
                ordinal=ordinal,
                stage_id="alias_declaration",
                stage_version=ALIAS_DECLARATION_RULE_ID,
                producer_id="kotekomi_application",
                source_segment_id=node.id,
                source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
                configuration={"rule_id": ALIAS_DECLARATION_RULE_ID},
                input_payload={"source_text": source_text},
                output_payload={
                    "declaration_id": declaration_id,
                    "expanded_span_id": expanded_span.id,
                    "alias_span_id": alias_span.id,
                },
                status=ExtractionStageStatus.COMPLETED,
            )
            declarations.append(
                AliasDeclaration(
                    id=declaration_id,
                    expanded_span=expanded_span,
                    alias_span=alias_span,
                    trace_id=trace.id,
                )
            )
            traces.append(trace)
    return tuple(sorted(declarations, key=_declaration_key)), tuple(sorted(traces, key=_trace_key))


def canonical_hybrid_reference_preview_bytes(preview: HybridReferencePreview) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_reference_preview_sha256(preview: HybridReferencePreview) -> str:
    return hashlib.sha256(canonical_hybrid_reference_preview_bytes(preview)).hexdigest()


def hybrid_reference_preview_from_bytes(payload: bytes) -> HybridReferencePreview:
    return HybridReferencePreview.model_validate_json(payload)


def _declaration_ranges(source_text: str) -> tuple[tuple[int, int, int, int], ...]:
    values: list[tuple[int, int, int, int]] = []
    for marker in _ALIAS_MARKER.finditer(source_text):
        alias = marker.group("alias")
        clause_start = 0
        boundaries = tuple(_CLAUSE_BOUNDARY.finditer(source_text, 0, marker.start()))
        if boundaries:
            clause_start = boundaries[-1].end()
        tokens = tuple(_NAME_TOKEN.finditer(source_text, clause_start, marker.start()))[-16:]
        valid: list[tuple[int, int, int, int]] = []
        for token in tokens:
            expanded = source_text[token.start() : marker.start()].rstrip()
            if not expanded or source_text[token.start() : marker.start()].rstrip() != expanded:
                continue
            if token.group().casefold() in _LEADING_FUNCTION_WORDS:
                continue
            if source_text[token.start() + len(expanded) : marker.start()].strip():
                continue
            parsed = parse_parenthetical_alias(f"{expanded} ({alias})")
            if parsed is not None and parsed[2]:
                valid.append(
                    (
                        token.start(),
                        token.start() + len(expanded),
                        marker.start("alias"),
                        marker.end("alias"),
                    )
                )
        if valid:
            values.append(min(valid, key=lambda item: item[0]))
    return tuple(values)


def _parent_segment_sources(
    bundle: DocumentRepresentationBundle,
    node: DocumentNode,
) -> dict[str, tuple[str, int]]:
    view = _text_view(bundle, node.text_view_id)
    paragraph = view.text[node.start_char : node.end_char]
    return {
        hybrid_source_segment_id(bundle.representation.id, node.id, segment): (
            segment.exact_text,
            segment.start_char,
        )
        for segment in paragraph_source_segments(paragraph, PARAGRAPH_SEGMENT_V2)
    }


def _span(
    representation_id: str,
    node: DocumentNode,
    view: TextView,
    start_char: int,
    end_char: int,
) -> ReferenceSpan:
    if node.representation_id != representation_id or view.representation_id != representation_id:
        raise ValueError("ReferenceSpan source belongs to another representation.")
    if start_char < node.start_char or end_char > node.end_char or end_char <= start_char:
        raise ValueError("ReferenceSpan lies outside its DocumentNode.")
    text = view.text[start_char:end_char]
    digest = hashlib.sha256(text.encode()).hexdigest()
    return ReferenceSpan(
        id=_id(
            "rsp",
            representation_id,
            node.id,
            view.id,
            str(start_char),
            str(end_char),
            digest,
        ),
        representation_id=representation_id,
        node_id=node.id,
        text_view_id=view.id,
        start_char=start_char,
        end_char=end_char,
        text=text,
        text_sha256=digest,
    )


def _node(bundle: DocumentRepresentationBundle, node_id: str) -> DocumentNode:
    try:
        return next(item for item in bundle.nodes if item.id == node_id)
    except StopIteration as error:
        raise ValueError("HP-2 parent Preview references a missing DocumentNode.") from error


def _text_view(bundle: DocumentRepresentationBundle, text_view_id: str) -> TextView:
    try:
        return next(item for item in bundle.text_views if item.id == text_view_id)
    except StopIteration as error:
        raise ValueError("HP-2 source node references a missing TextView.") from error


def _is_alias_expression(text: str) -> bool:
    return bool(_ALIAS_EXPRESSION.fullmatch(text)) and any(
        character.isalpha() for character in text
    )


def _decision_id(
    candidate_id: str,
    reference_span_id: str,
    kind: ReferenceKind,
    status: ReferenceStatus,
    reason: ReferenceReason,
    declaration_ids: tuple[str, ...],
    antecedent_span_ids: tuple[str, ...],
) -> str:
    return _id(
        "rfd",
        candidate_id,
        reference_span_id,
        kind.value,
        status.value,
        reason.value,
        *declaration_ids,
        *antecedent_span_ids,
    )


def build_hybrid_reference_preview_record(**values: object) -> HybridReferencePreview:
    """Construct one strictly validated HybridReferencePreview DTO."""
    payload = dict(values)
    payload.setdefault("schema_version", "hybrid_reference_preview_v1")
    payload.setdefault("policy_id", HYBRID_REFERENCE_POLICY_ID)
    payload.setdefault("terminal_status", "complete")
    payload.setdefault("diagnostics", ())
    json_payload = cast(dict[str, JsonValue], _json_copy(payload))
    json_payload["id"] = _preview_id(json_payload)
    return HybridReferencePreview.model_validate_json(_canonical_json(json_payload))


def _preview_id(payload: dict[str, JsonValue]) -> str:
    return f"hrp_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_copy(value: object) -> JsonValue:
    return cast(JsonValue, json.loads(json.dumps(value, default=_json_default)))


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    raise TypeError(f"Unsupported HybridReferencePreview value: {type(value).__name__}")


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(chr(31).join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _require_ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"Hybrid reference {label} must be ordered and distinct.")


def _declaration_key(item: AliasDeclaration) -> tuple[int, int, str]:
    return item.expanded_span.start_char, item.alias_span.end_char, item.id


def _decision_key(item: ReferenceDecision) -> tuple[int, int, str]:
    return item.reference_span.start_char, item.reference_span.end_char, item.id


def _trace_key(item: ExtractionStageTrace) -> tuple[str, int, str]:
    return item.trace_run_id, item.ordinal, item.id
