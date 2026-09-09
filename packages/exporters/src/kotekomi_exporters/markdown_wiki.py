"""Deterministic Markdown renderer for a Candidate Wiki plan."""

from __future__ import annotations

import hashlib
import html
import json
import posixpath
from pathlib import PurePosixPath

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    RenderedCandidateWiki,
    RenderedWikiFile,
    WikiAssertionPresentation,
    WikiBuildFileEntry,
    WikiBuildManifest,
    WikiDetail,
    WikiEventPresentation,
    WikiEvidenceReference,
    WikiLink,
    WikiOntologyEdge,
    WikiPageInput,
    WikiPresentation,
    candidate_wiki_build_id,
    canonical_wiki_audit_bytes,
    canonical_wiki_citations_bytes,
    canonical_wiki_manifest_bytes,
)


class MarkdownCandidateWikiRenderer:
    """Render validated page inputs without consulting state or a model."""

    def render(self, plan: CandidateWikiPlan) -> RenderedCandidateWiki:
        build_id = candidate_wiki_build_id(
            view_policy_id=plan.view_policy_id,
            renderer_policy_id=plan.renderer_policy_id,
            ingestion_run_id=plan.ingestion_run_id,
            ingestion_change_set_id=plan.ingestion_change_set_id,
            candidate_snapshot_digest=plan.candidate_snapshot_digest,
            counts=plan.counts,
        )
        citations = canonical_wiki_citations_bytes(plan.citation_registry)
        audit = canonical_wiki_audit_bytes(plan.audit_catalog)
        evidence_by_number = {
            item.citation_number: item for item in plan.citation_registry.citations
        }
        rendered_pages = tuple(
            RenderedWikiFile(
                page.relative_path,
                _render_page(page, build_id=build_id, evidence_by_number=evidence_by_number),
            )
            for page in plan.pages
        )
        content_files = (
            *rendered_pages,
            RenderedWikiFile("audit.json", audit),
            RenderedWikiFile("citations.json", citations),
        )
        page_fingerprints = {page.relative_path: page.input_fingerprint for page in plan.pages}
        structured_fingerprints = {
            "audit.json": hashlib.sha256(audit).hexdigest(),
            "citations.json": hashlib.sha256(citations).hexdigest(),
        }
        entries = tuple(
            WikiBuildFileEntry(
                relative_path=item.relative_path,
                input_fingerprint=(
                    page_fingerprints[item.relative_path]
                    if item.relative_path in page_fingerprints
                    else structured_fingerprints[item.relative_path]
                ),
                content_sha256=hashlib.sha256(item.payload).hexdigest(),
            )
            for item in sorted(content_files, key=lambda file: file.relative_path)
        )
        manifest = WikiBuildManifest(
            schema_version="candidate_wiki_manifest_v2",
            build_id=build_id,
            view_policy_id=plan.view_policy_id,
            renderer_policy_id=plan.renderer_policy_id,
            ingestion_run_id=plan.ingestion_run_id,
            ingestion_change_set_id=plan.ingestion_change_set_id,
            candidate_snapshot_digest=plan.candidate_snapshot_digest,
            files=entries,
            counts=plan.counts,
        )
        manifest_file = RenderedWikiFile("manifest.json", canonical_wiki_manifest_bytes(manifest))
        return RenderedCandidateWiki(
            manifest=manifest,
            files=tuple(
                sorted((*content_files, manifest_file), key=lambda file: file.relative_path)
            ),
        )


def _render_page(
    page: WikiPageInput,
    *,
    build_id: str,
    evidence_by_number: dict[int, WikiEvidenceReference],
) -> bytes:
    lines = [
        "---",
        f"kotekomi_wiki_build_id: {_frontmatter_value(build_id)}",
        f"kotekomi_page_kind: {_frontmatter_value(page.page_kind)}",
    ]
    if page.record_id is not None:
        lines.append(f"kotekomi_record_id: {_frontmatter_value(page.record_id)}")
    lines.extend(
        (
            'kotekomi_projection_state: "candidate"',
            "---",
            "",
            f"# {_markdown_text(page.display_label)}",
            "",
            "> [!WARNING]",
            "> Unpublished Candidate Wiki. Pending records are not accepted intelligence.",
            "",
        )
    )
    if page.state is not None:
        lines.extend((f"Review state: **{page.state.upper()}**", ""))
    lines.extend(_details(page.details, page.relative_path))
    lines.extend(_links(page.links, page.relative_path))
    lines.extend(_at_a_glance(page.presentations, page.relative_path, evidence_by_number))
    lines.extend(_relationships(page.presentations, page.relative_path, evidence_by_number))
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _details(details: tuple[WikiDetail, ...], current_path: str) -> list[str]:
    if not details:
        return []
    lines = ["## Details", ""]
    for detail in details:
        value = (
            _wiki_link(detail.value, detail.relative_path, current_path)
            if detail.relative_path is not None
            else _markdown_text(detail.value)
        )
        lines.append(f"- **{_markdown_text(detail.label)}:** {value}")
    return [*lines, ""]


def _links(links: tuple[WikiLink, ...], current_path: str) -> list[str]:
    if not links:
        return []
    lines = ["## Records", ""]
    for link in links:
        lines.append(
            f"- [{link.state.upper()}] `{_code_text(link.record_id)}` · {link.record_type}: "
            f"{_wiki_link(link.label, link.relative_path, current_path)}"
        )
    return [*lines, ""]


def _at_a_glance(
    presentations: tuple[WikiPresentation, ...],
    current_path: str,
    evidence_by_number: dict[int, WikiEvidenceReference],
) -> list[str]:
    events = tuple(item for item in presentations if isinstance(item, WikiEventPresentation))
    if not events:
        return []
    lines = ["## At a glance", ""]
    for event in events:
        lines.append(
            f"- [{event.state.upper()}] `{_code_text(event.event_id)}` · "
            f"**{_markdown_text(_event_label(event))}**"
        )
        role_parts: list[str] = []
        for edge in event.edges:
            role_id = next(
                (item.value for item in edge.qualifiers if item.key == "frame_role_id"),
                None,
            )
            if role_id is None:
                continue
            role_parts.append(
                f"{_markdown_text(_human_label(role_id.rsplit('.', maxsplit=1)[-1]).casefold())} "
                f"{_edge_object(edge, current_path)}"
            )
        if role_parts:
            lines.append(f"  - **Extracted roles:** {'; '.join(role_parts)}")
        for issue in event.issues:
            lines.append(f"  - **Review issue:** {_markdown_text(issue)}")
        for evidence in _event_evidence(event, evidence_by_number):
            lines.append(f"  - **{_source_label(evidence.page_numbers)}:**")
            lines.append(f"    > {_markdown_text(evidence.exact_text)}")
    return [*lines, ""]


def _event_evidence(
    event: WikiEventPresentation,
    evidence_by_number: dict[int, WikiEvidenceReference],
) -> tuple[WikiEvidenceReference, ...]:
    return _presentation_evidence(event.citation_numbers, evidence_by_number)


def _presentation_evidence(
    citation_numbers: tuple[int, ...],
    evidence_by_number: dict[int, WikiEvidenceReference],
) -> tuple[WikiEvidenceReference, ...]:
    evidence: list[WikiEvidenceReference] = []
    seen: set[tuple[object, ...]] = set()
    for number in citation_numbers:
        reference = evidence_by_number.get(number)
        if reference is None:
            raise ValueError(f"Candidate Wiki presentation cites missing evidence number: {number}")
        identity = (
            reference.source_id,
            reference.document_id,
            reference.text_view_id,
            reference.start_char,
            reference.end_char,
            reference.exact_text,
            reference.page_numbers,
        )
        if identity not in seen:
            seen.add(identity)
            evidence.append(reference)
    return tuple(evidence)


def _source_label(page_numbers: tuple[int, ...]) -> str:
    if len(page_numbers) == 1:
        return f"Source, page {page_numbers[0]}"
    if page_numbers:
        return f"Source, pages {', '.join(str(number) for number in page_numbers)}"
    return "Source"


def _relationships(
    presentations: tuple[WikiPresentation, ...],
    current_path: str,
    evidence_by_number: dict[int, WikiEvidenceReference],
) -> list[str]:
    assertions = tuple(
        item for item in presentations if isinstance(item, WikiAssertionPresentation)
    )
    if not assertions:
        return []
    lines: list[str] = []
    for state, section in (
        ("accepted", "Relationships"),
        ("pending", "Relationships requiring review"),
    ):
        section_items = tuple(item for item in assertions if item.state == state)
        if not section_items:
            continue
        lines.extend((f"## {section}", ""))
        for presentation in section_items:
            lines.extend(
                (
                    f"- [{presentation.state.upper()}] "
                    f"`{_code_text(presentation.edge.assertion_id)}`",
                    f"  - {_relationship_edge(presentation.edge, current_path)}",
                )
            )
            for evidence in _presentation_evidence(
                presentation.citation_numbers, evidence_by_number
            ):
                lines.append(f"  - **{_exact_source_label(evidence.page_numbers)}:**")
                lines.append(f"    > {_markdown_text(evidence.exact_text)}")
        lines.append("")
    return lines


def _exact_source_label(page_numbers: tuple[int, ...]) -> str:
    if len(page_numbers) == 1:
        return f"Exact source, page {page_numbers[0]}"
    if page_numbers:
        return f"Exact source, pages {', '.join(str(number) for number in page_numbers)}"
    return "Exact source"


def _wiki_link(label: str, relative_path: str, current_path: str) -> str:
    current_dir = PurePosixPath(current_path).parent.as_posix()
    target = posixpath.relpath(relative_path, current_dir)
    return f"[{_markdown_text(label)}]({target})"


def _wiki_link_or_text(label: str, relative_path: str | None, current_path: str) -> str:
    if relative_path is None or relative_path == current_path:
        return _markdown_text(label)
    return _wiki_link(label, relative_path, current_path)


def _relationship_edge(edge: WikiOntologyEdge, current_path: str) -> str:
    subject = _wiki_link_or_text(edge.subject_label, edge.subject_path, current_path)
    predicate = _markdown_text(edge.predicate)
    return f"{subject} — **{predicate}** → {_edge_object(edge, current_path)}"


def _edge_object(edge: WikiOntologyEdge, current_path: str) -> str:
    if edge.object_path is not None:
        return _wiki_link_or_text(edge.object_label, edge.object_path, current_path)
    return f"**{_markdown_text(edge.object_label)}**"


def _event_label(event: WikiEventPresentation) -> str:
    label = f"{_human_label(event.frame_id)} Event"
    return label if event.complete else f"Incomplete {label}"


def _frontmatter_value(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _markdown_text(value: str) -> str:
    return (
        html.escape(value, quote=False)
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def _code_text(value: str) -> str:
    return html.escape(value, quote=False).replace("`", "\\`").replace("\n", " ")


def _human_label(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()
