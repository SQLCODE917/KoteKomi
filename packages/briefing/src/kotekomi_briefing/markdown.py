"""Deterministic Markdown Briefing renderer."""

from __future__ import annotations

from kotekomi_application import BriefingMarkdown, BriefingRenderInput


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
    lines.extend(_citation_register_section(render_input))
    lines.extend(_source_quality_register_section(render_input))
    lines.extend(_appendix_trace_section(render_input))
    lines.extend(_collection_requirement_section(render_input))
    lines.extend(_entity_event_index_section(render_input))
    return lines


def _appendix_trace_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Analytic Trace", ""]
    analytic_trace = render_input.narrative.reference_appendix.analytic_trace
    if not analytic_trace:
        return [*lines, "- None", ""]
    lines.append("| Finding | Support | Relation | Confidence |")
    lines.append("|---|---|---|---:|")
    for trace in analytic_trace:
        finding = _sentence_text(trace.finding, trace.citation_numbers)
        lines.append(
            f"| {finding} | {trace.support} | {trace.relation} | {trace.confidence_label} |"
        )
    return [*lines, ""]


def _citation_register_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Citation Register", ""]
    if not render_input.citation_registry.citations:
        return [*lines, "- None", ""]
    lines.append("| Number | Type | Summary | Confidence |")
    lines.append("|---:|---|---|---:|")
    for citation in render_input.citation_registry.citations:
        citation_type = _citation_type_label(citation.label, citation.is_analytic_inference)
        lines.append(
            f"| [{citation.number}] | {citation_type} | "
            f"{_citation_summary(citation.summary)} | "
            f"{citation.confidence_label} |"
        )
    return [*lines, ""]


def _citation_type_label(label: str, is_analytic_inference: bool) -> str:
    if is_analytic_inference:
        return "Analytic inference"
    if label == "ArgumentEdge":
        return "Support link"
    return label


def _source_quality_register_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Source Quality Register", ""]
    if not render_input.narrative.evidence_quality:
        return [*lines, "- None", ""]
    lines.append("| Claim | SourceAuthority | AttributionBasis | Sources | EvidenceSpans |")
    lines.append("|---|---:|---:|---:|---:|")
    for quality in render_input.narrative.evidence_quality:
        claim = _sentence_text(quality.claim.text, quality.claim.citation_numbers)
        lines.append(
            f"| {claim} | {_enum_label(quality.source_authority.value)} | "
            f"{_enum_label(quality.attribution_basis.value)} | {quality.source_count} | "
            f"{quality.evidence_span_count} |"
        )
    return [*lines, ""]


def _collection_requirement_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Collection Requirements", ""]
    requirements = render_input.narrative.reference_appendix.collection_requirements
    if not requirements:
        return [*lines, "- None", ""]
    lines.append("| Gap | Evidence That Would Close It |")
    lines.append("|---|---|")
    for requirement in requirements:
        gap = _sentence_text(requirement.gap, requirement.citation_numbers)
        lines.append(f"| {gap} | {requirement.closes_with} |")
    return [*lines, ""]


def _entity_event_index_section(render_input: BriefingRenderInput) -> list[str]:
    lines = ["### Entity and Event Index", ""]
    index_rows = render_input.narrative.reference_appendix.entity_event_index
    if not index_rows:
        return [*lines, "- None", ""]
    lines.append("| Type | Name | Context |")
    lines.append("|---|---|---|")
    for row in index_rows:
        lines.append(f"| {row.record_type} | {row.name} | {row.context} |")
    return [*lines, ""]


def _sentence_text(text: str, citation_numbers: tuple[int, ...]) -> str:
    if not citation_numbers:
        return text
    return f"{text}{_citation_markers(citation_numbers)}"


def _citation_markers(citation_numbers: tuple[int, ...]) -> str:
    return "".join(f"[{citation_number}]" for citation_number in citation_numbers)


def _citation_summary(summary: str) -> str:
    cleaned = summary
    for prefix in (
        "Source-backed Assertion: ",
        "ArgumentEdge: ",
        "Relationship: ",
        "Outcome: ",
    ):
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    return cleaned


def _enum_label(value: str) -> str:
    return value.replace("_", " ").title()
