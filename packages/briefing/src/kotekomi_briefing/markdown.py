"""Deterministic Markdown Briefing renderer."""

from __future__ import annotations

from kotekomi_application import BriefingMarkdown, BriefingRenderInput
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionType,
    Document,
    Entity,
    Event,
    Organization,
    Outcome,
    Place,
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
        lines.extend(_entity_section(render_input.entities))
        lines.extend(_organization_section(render_input.organizations))
        lines.extend(_actor_section(render_input.actors))
        lines.extend(_place_section(render_input.places))
        lines.extend(_event_section(render_input.events))
        lines.extend(_outcome_section(render_input.outcomes))
        lines.extend(_document_section(render_input.documents))
        lines.extend(_source_section(render_input.sources))
        lines.extend(_assertion_section(render_input.assertions))
        lines.extend(_relationship_section(render_input.relationships))
        lines.extend(_argument_edge_section(render_input.argument_edges))
        lines.extend(_analytic_inference_section(render_input))
        return BriefingMarkdown(markdown="\n".join(lines).rstrip() + "\n")


def _entity_section(entities: tuple[Entity, ...]) -> list[str]:
    lines = ["## Key Entities", ""]
    if not entities:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{entity.id}`: {entity.canonical_name} ({entity.entity_kind.value})"
            for entity in sorted(entities, key=lambda record: record.id)
        ),
        "",
    ]


def _organization_section(organizations: tuple[Organization, ...]) -> list[str]:
    lines = ["## Key Organizations", ""]
    if not organizations:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{organization.id}`: {organization.name}"
            for organization in sorted(organizations, key=lambda record: record.id)
        ),
        "",
    ]


def _actor_section(actors: tuple[Actor, ...]) -> list[str]:
    lines = ["## Key Actors", ""]
    if not actors:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{actor.id}`: {actor.name}"
            f"{_optional_parenthetical('Roles', actor.role_names)}"
            f"{_optional_parenthetical('Organizations', actor.organization_ids)}"
            for actor in sorted(actors, key=lambda record: record.id)
        ),
        "",
    ]


def _place_section(places: tuple[Place, ...]) -> list[str]:
    lines = ["## Key Places", ""]
    if not places:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{place.id}`: {place.name}"
            for place in sorted(places, key=lambda record: record.id)
        ),
        "",
    ]


def _event_section(events: tuple[Event, ...]) -> list[str]:
    lines = ["## Key Events", ""]
    if not events:
        return [*lines, "- None", ""]
    for event in sorted(events, key=lambda record: record.id):
        lines.append(f"- `{event.id}`: {event.name}")
        if event.start_at is not None:
            lines.append(f"  - Start: `{event.start_at.isoformat()}`")
        if event.participant_actor_ids:
            lines.append(f"  - Actors: {_id_list(event.participant_actor_ids)}")
        if event.participant_organization_ids:
            lines.append(f"  - Organizations: {_id_list(event.participant_organization_ids)}")
        if event.place_id is not None:
            lines.append(f"  - Place: `{event.place_id}`")
    return [*lines, ""]


def _outcome_section(outcomes: tuple[Outcome, ...]) -> list[str]:
    lines = ["## Outcomes", ""]
    if not outcomes:
        return [*lines, "- None", ""]
    for outcome in sorted(outcomes, key=lambda record: record.id):
        lines.append(f"- `{outcome.id}`: {outcome.description}")
        if outcome.actor_ids:
            lines.append(f"  - Actors: {_id_list(outcome.actor_ids)}")
        if outcome.organization_ids:
            lines.append(f"  - Organizations: {_id_list(outcome.organization_ids)}")
        if outcome.event_ids:
            lines.append(f"  - Events: {_id_list(outcome.event_ids)}")
        if outcome.assertion_ids:
            lines.append(f"  - Assertions: {_id_list(outcome.assertion_ids)}")
    return [*lines, ""]


def _document_section(documents: tuple[Document, ...]) -> list[str]:
    lines = ["## Documents", ""]
    if not documents:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- `{document.id}`: Source `{document.source_id}`; "
            f"raw `{document.raw_path}`; text `{document.extracted_text_path or 'none'}`"
            for document in sorted(documents, key=lambda record: record.id)
        ),
        "",
    ]


def _source_section(sources: tuple[Source, ...]) -> list[str]:
    lines = ["## Sources and Evidence", ""]
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


def _optional_parenthetical(label: str, values: tuple[str, ...]) -> str:
    if not values:
        return ""
    return f" ({label}: {_id_list(values)})"
