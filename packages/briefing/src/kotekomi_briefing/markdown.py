"""Deterministic Markdown Briefing renderer."""

from __future__ import annotations

from kotekomi_application import BriefingMarkdown, BriefingRenderInput
from kotekomi_domain import (
    ArgumentEdge,
    Assertion,
    AssertionType,
    Relationship,
    Source,
)


class MarkdownBriefingRenderer:
    def render(self, render_input: BriefingRenderInput) -> BriefingMarkdown:
        lines = [
            f"# {render_input.title}",
            "",
            f"Briefing ID: `{render_input.briefing_id}`",
            f"Generated: `{render_input.generated_at}`",
            f"Previous Briefing: `{render_input.previous_briefing_id or 'none'}`",
            "",
        ]
        lines.extend(_source_section(render_input.sources))
        lines.extend(_assertion_section(render_input.assertions))
        lines.extend(_relationship_section(render_input.relationships))
        lines.extend(_argument_edge_section(render_input.argument_edges))
        lines.extend(_analytic_inference_section(render_input))
        return BriefingMarkdown(markdown="\n".join(lines).rstrip() + "\n")


def _source_section(sources: tuple[Source, ...]) -> list[str]:
    lines = ["## New Sources", ""]
    if not sources:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{source.id}`: {source.title}"
            for source in sorted(sources, key=lambda record: record.id)
        ),
        "",
    ]


def _assertion_section(assertions: tuple[Assertion, ...]) -> list[str]:
    lines = ["## Changed Assertions", ""]
    if not assertions:
        return [*lines, "- None", ""]
    for assertion in sorted(assertions, key=lambda record: record.id):
        label = (
            "Analytic inference"
            if assertion.assertion_type is AssertionType.ANALYTIC_INFERENCE
            else "Assertion"
        )
        lines.append(f"- `{assertion.id}` ({label}): {assertion.predicate}")
        lines.append(f"  - Subject: `{assertion.subject_entity_id}`")
        if assertion.object_entity_id is not None:
            lines.append(f"  - Object: `{assertion.object_entity_id}`")
        if assertion.source_ids:
            lines.append(f"  - Sources: {_id_list(assertion.source_ids)}")
        if assertion.evidence_span_ids:
            lines.append(f"  - EvidenceSpans: {_id_list(assertion.evidence_span_ids)}")
        if assertion.current_assessment:
            lines.append(f"  - Assessment: {assertion.current_assessment}")
    return [*lines, ""]


def _relationship_section(relationships: tuple[Relationship, ...]) -> list[str]:
    lines = ["## Changed Relationships", ""]
    if not relationships:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{relationship.id}`: `{relationship.subject_id}` "
            f"{relationship.predicate} `{relationship.object_id}` "
            f"(Assertions: {_id_list(relationship.assertion_ids)})"
            for relationship in sorted(relationships, key=lambda record: record.id)
        ),
        "",
    ]


def _argument_edge_section(argument_edges: tuple[ArgumentEdge, ...]) -> list[str]:
    lines = ["## Changed ArgumentEdges", ""]
    if not argument_edges:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{argument_edge.id}`: `{argument_edge.from_assertion_id}` "
            f"{argument_edge.relation.value} `{argument_edge.to_assertion_id}` "
            f"(EvidenceSpans: {_id_list(argument_edge.evidence_span_ids)})"
            for argument_edge in sorted(argument_edges, key=lambda record: record.id)
        ),
        "",
    ]


def _analytic_inference_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Analytic Inferences", ""]
    if not render_input.analytic_inference_assertion_ids:
        return [*lines, "- None", ""]
    evidence_span_ids = sorted({span.id for span in render_input.evidence_spans})
    source_ids = sorted({source.id for source in render_input.sources})
    return [
        *lines,
        *(
            f"- Analytic inference `{assertion_id}` "
            f"(Sources: {_id_list(source_ids)}; EvidenceSpans: {_id_list(evidence_span_ids)})"
            for assertion_id in render_input.analytic_inference_assertion_ids
        ),
        "",
    ]


def _id_list(record_ids: tuple[str, ...] | list[str]) -> str:
    if not record_ids:
        return "`none`"
    return ", ".join(f"`{record_id}`" for record_id in record_ids)
