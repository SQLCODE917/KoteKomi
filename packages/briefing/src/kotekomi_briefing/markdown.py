"""Deterministic Markdown Briefing renderer."""

from __future__ import annotations

from kotekomi_application import BriefingMarkdown, BriefingRenderInput
from kotekomi_domain import (
    Actor,
    Entity,
    Event,
    Organization,
    Outcome,
    Place,
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
        lines.extend(_executive_judgment_section(render_input))
        lines.extend(_what_changed_section(render_input))
        lines.extend(_judgment_basis_section(render_input))
        lines.extend(_evidence_quality_section(render_input))
        lines.extend(_collection_gap_section(render_input))
        lines.extend(_indicators_section(render_input))
        lines.extend(_implications_section(render_input))
        lines.extend(_reference_appendix_section(render_input))
        return BriefingMarkdown(markdown="\n".join(lines).rstrip() + "\n")


def _executive_judgment_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Executive Judgment", ""]
    judgment = render_input.narrative.executive_judgment
    if judgment is None:
        return [*lines, "- None", ""]
    return [
        *lines,
        _sentence_text(judgment.text, judgment.citation_numbers),
        "",
    ]


def _what_changed_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## What Changed", ""]
    if not render_input.narrative.what_changed:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- {_sentence_text(sentence.text, sentence.citation_numbers)}"
            for sentence in render_input.narrative.what_changed
        ),
        "",
    ]


def _judgment_basis_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Judgment Basis", ""]
    if not render_input.narrative.judgment_basis:
        return [*lines, "- None", ""]
    for basis in render_input.narrative.judgment_basis:
        lines.append("- Source basis:")
        for sentence in basis.source_basis:
            lines.append(f"  - {_sentence_text(sentence.text, sentence.citation_numbers)}")
        lines.append("- Observed effects:")
        for sentence in basis.observed_effects:
            lines.append(f"  - {_sentence_text(sentence.text, sentence.citation_numbers)}")
        assessment_text = _sentence_text(
            basis.assessment.text,
            basis.assessment.citation_numbers,
        )
        confidence_text = _sentence_text(
            basis.confidence.text,
            basis.confidence.citation_numbers,
        )
        lines.append(f"- Assessment: {assessment_text}")
        lines.append(f"- Confidence: {confidence_text}")
    return [*lines, ""]


def _evidence_quality_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Evidence and Source Quality", ""]
    if not render_input.narrative.evidence_quality:
        return [*lines, "- None", ""]
    lines.append(
        "| Claim | SourceAuthority | AttributionBasis | Sources | EvidenceSpans |"
    )
    lines.append("|---|---:|---:|---:|---:|")
    for quality in render_input.narrative.evidence_quality:
        claim = _sentence_text(quality.claim.text, quality.claim.citation_numbers)
        lines.append(
            f"| {claim} | {_enum_label(quality.source_authority.value)} | "
            f"{_enum_label(quality.attribution_basis.value)} | {quality.source_count} | "
            f"{quality.evidence_span_count} |"
        )
    return [*lines, ""]


def _collection_gap_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Open Questions and Collection Gaps", ""]
    if not render_input.narrative.collection_gaps:
        return [*lines, "- None", ""]
    for gap in render_input.narrative.collection_gaps:
        lines.append(f"- {_sentence_text(gap.text, gap.citation_numbers)}")
    return [*lines, ""]


def _indicators_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Indicators to Watch", ""]
    if not render_input.narrative.indicators_to_watch:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- {_sentence_text(indicator.text, indicator.citation_numbers)}"
            for indicator in render_input.narrative.indicators_to_watch
        ),
        "",
    ]


def _implications_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Implications", ""]
    if not render_input.narrative.implications:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- {_sentence_text(implication.text, implication.citation_numbers)}"
            for implication in render_input.narrative.implications
        ),
        "",
    ]


def _reference_appendix_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["## Reference Appendix", ""]
    lines.extend(_appendix_trace_section(render_input))
    lines.extend(_entity_section(render_input.entities))
    lines.extend(_organization_section(render_input.organizations))
    lines.extend(_actor_section(render_input.actors, render_input.organizations))
    lines.extend(_place_section(render_input.places))
    lines.extend(
        _event_section(
            render_input.events,
            render_input.actors,
            render_input.organizations,
            render_input.places,
        )
    )
    lines.extend(
        _outcome_section(
            render_input.outcomes,
            render_input.actors,
            render_input.organizations,
            render_input.events,
        )
    )
    lines.extend(_source_section(render_input.sources))
    lines.extend(_citation_section(render_input))
    return lines


def _appendix_trace_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Analytic Trace", ""]
    analytic_trace = render_input.narrative.reference_appendix.analytic_trace
    if not analytic_trace:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- {_sentence_text(trace.text, trace.citation_numbers)}"
            for trace in analytic_trace
        ),
        "",
    ]


def _citation_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Citations", ""]
    if not render_input.citation_registry.citations:
        return [*lines, "- None", ""]
    for citation in render_input.citation_registry.citations:
        lines.append(f"- [{citation.number}] {_citation_heading(citation.label, citation.summary)}")
        lines.append(f"  - Confidence: {citation.confidence_label}")
        if citation.is_analytic_inference:
            lines.append("  - Type: Analytic inference")
    return [*lines, ""]


def _entity_section(entities: tuple[Entity, ...]) -> list[str]:
    lines = ["### Key Entities", ""]
    if not entities:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- {entity.canonical_name} ({entity.entity_kind.value})"
            for entity in sorted(entities, key=lambda record: record.id)
        ),
        "",
    ]


def _organization_section(organizations: tuple[Organization, ...]) -> list[str]:
    lines = ["### Key Organizations", ""]
    if not organizations:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(
            f"- {organization.name}"
            for organization in sorted(organizations, key=lambda record: record.id)
        ),
        "",
    ]


def _actor_section(actors: tuple[Actor, ...], organizations: tuple[Organization, ...]) -> list[str]:
    lines = ["### Key Actors", ""]
    if not actors:
        return [*lines, "- None", ""]
    organization_names = {record.id: record.name for record in organizations}
    return [
        *lines,
        *(
            f"- {actor.name}"
            f"{_optional_parenthetical('Roles', actor.role_names)}"
            f"{
                _optional_parenthetical(
                    'Organizations',
                    _names(actor.organization_ids, organization_names),
                )
            }"
            for actor in sorted(actors, key=lambda record: record.id)
        ),
        "",
    ]


def _place_section(places: tuple[Place, ...]) -> list[str]:
    lines = ["### Key Places", ""]
    if not places:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(f"- {place.name}" for place in sorted(places, key=lambda record: record.id)),
        "",
    ]


def _event_section(
    events: tuple[Event, ...],
    actors: tuple[Actor, ...],
    organizations: tuple[Organization, ...],
    places: tuple[Place, ...],
) -> list[str]:
    lines = ["### Key Events", ""]
    if not events:
        return [*lines, "- None", ""]
    actor_names = {record.id: record.name for record in actors}
    organization_names = {record.id: record.name for record in organizations}
    place_names = {record.id: record.name for record in places}
    for event in sorted(events, key=lambda record: record.id):
        lines.append(f"- {event.name}")
        if event.start_at is not None:
            lines.append(f"  - Start: `{event.start_at.isoformat()}`")
        if event.participant_actor_ids:
            lines.append(
                f"  - Actors: {_text_list(_names(event.participant_actor_ids, actor_names))}"
            )
        if event.participant_organization_ids:
            lines.append(
                f"  - Organizations: "
                f"{_text_list(_names(event.participant_organization_ids, organization_names))}"
            )
        if event.place_id is not None:
            lines.append(f"  - Place: {place_names.get(event.place_id, 'Unresolved record')}")
    return [*lines, ""]


def _outcome_section(
    outcomes: tuple[Outcome, ...],
    actors: tuple[Actor, ...],
    organizations: tuple[Organization, ...],
    events: tuple[Event, ...],
) -> list[str]:
    lines = ["### Outcomes", ""]
    if not outcomes:
        return [*lines, "- None", ""]
    actor_names = {record.id: record.name for record in actors}
    organization_names = {record.id: record.name for record in organizations}
    event_names = {record.id: record.name for record in events}
    for outcome in sorted(outcomes, key=lambda record: record.id):
        lines.append(f"- {outcome.description}")
        if outcome.actor_ids:
            lines.append(f"  - Actors: {_text_list(_names(outcome.actor_ids, actor_names))}")
        if outcome.organization_ids:
            lines.append(
                "  - Organizations: "
                f"{_text_list(_names(outcome.organization_ids, organization_names))}"
            )
        if outcome.event_ids:
            lines.append(f"  - Events: {_text_list(_names(outcome.event_ids, event_names))}")
    return [*lines, ""]


def _source_section(sources: tuple[Source, ...]) -> list[str]:
    lines = ["### Sources", ""]
    if not sources:
        return [*lines, "- None", ""]
    return [
        *lines,
        *(f"- {source.title}" for source in sorted(sources, key=lambda record: record.id)),
        "",
    ]


def _sentence_text(text: str, citation_numbers: tuple[int, ...]) -> str:
    if not citation_numbers:
        return text
    return f"{text}{_citation_markers(citation_numbers)}"


def _citation_markers(citation_numbers: tuple[int, ...]) -> str:
    return "".join(f"[{citation_number}]" for citation_number in citation_numbers)


def _citation_heading(label: str, summary: str) -> str:
    for prefix in ("Source report:", "Inference:", "Relationship:", "Outcome:"):
        if summary.startswith(prefix):
            return summary
    return f"{label}: {summary}"


def _enum_label(value: str) -> str:
    return value.replace("_", " ").title()


def _optional_parenthetical(label: str, values: tuple[str, ...]) -> str:
    if not values:
        return ""
    return f" ({label}: {_text_list(values)})"


def _names(record_ids: tuple[str, ...], names_by_id: dict[str, str]) -> tuple[str, ...]:
    return tuple(names_by_id.get(record_id, "Unresolved record") for record_id in record_ids)


def _text_list(values: tuple[str, ...] | list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)
