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
    WikiBuildFileEntry,
    WikiBuildManifest,
    WikiDetail,
    WikiEventPresentation,
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
        rendered_pages = tuple(
            RenderedWikiFile(page.relative_path, _render_page(page, build_id=build_id))
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


def _render_page(page: WikiPageInput, *, build_id: str) -> bytes:
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
    lines.extend(_at_a_glance(page.presentations, page.relative_path))
    lines.extend(_presentations(page.presentations, page.relative_path))
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
        for edge in event.edges:
            role_id = next(
                (item.value for item in edge.qualifiers if item.key == "frame_role_id"),
                None,
            )
            if role_id is None:
                continue
            lines.append(
                f"  - **{_markdown_text(_human_label(role_id.rsplit('.', maxsplit=1)[-1]))}:** "
                f"{_edge_object(edge, current_path)}"
            )
    return [*lines, ""]


def _presentations(
    presentations: tuple[WikiPresentation, ...],
    current_path: str,
) -> list[str]:
    if not presentations:
        return []
    lines: list[str] = []
    for section in (
        "Event details",
        "Incomplete ontology events",
        "Relationships",
        "Relationships requiring review",
    ):
        section_items = tuple(
            item for item in presentations if _presentation_section(item) == section
        )
        if not section_items:
            continue
        lines.extend((f"## {section}", ""))
        for presentation in section_items:
            lines.extend(_presentation(presentation, current_path))
    return lines


def _presentation_section(presentation: WikiPresentation) -> str:
    if isinstance(presentation, WikiEventPresentation):
        return "Event details" if presentation.complete else "Incomplete ontology events"
    return "Relationships requiring review" if presentation.state == "pending" else "Relationships"


def _presentation(
    presentation: WikiPresentation,
    current_path: str,
) -> list[str]:
    if isinstance(presentation, WikiEventPresentation):
        record_id = presentation.event_id
        title = _markdown_text(_event_label(presentation))
        edges = presentation.edges
    else:
        record_id = presentation.edge.assertion_id
        title = "Relationship" if presentation.state == "accepted" else "Proposed relationship"
        edges = (presentation.edge,)
    lines = [
        f"### `{_code_text(record_id)}` · {title}",
        "",
        f"**Review state:** {presentation.state.upper()}",
        "",
    ]
    if isinstance(presentation, WikiEventPresentation) and presentation.issues:
        lines.extend(("> [!CAUTION]", "> This ontology event is incomplete.", ">"))
        lines.extend(f"> - {_markdown_text(issue)}" for issue in presentation.issues)
        lines.append("")
    lines.extend(_ontology_graph(edges, current_path))
    return lines


def _ontology_graph(edges: tuple[WikiOntologyEdge, ...], current_path: str) -> list[str]:
    lines = ["#### Ontology object graph", ""]
    for edge in edges:
        lines.append(f"- `{_code_text(edge.assertion_id)}` · {_edge_inline(edge, current_path)}")
        for qualifier in edge.qualifiers:
            value = (
                _wiki_link_or_text(qualifier.value, qualifier.value_path, current_path)
                if qualifier.value_path is not None
                else f"`{_code_text(qualifier.value)}`"
            )
            lines.append(f"  - `{_code_text(qualifier.key)}` → {value}")
    return [*lines, ""]


def _wiki_link(label: str, relative_path: str, current_path: str) -> str:
    current_dir = PurePosixPath(current_path).parent.as_posix()
    target = posixpath.relpath(relative_path, current_dir)
    return f"[{_markdown_text(label)}]({target})"


def _wiki_link_or_text(label: str, relative_path: str | None, current_path: str) -> str:
    if relative_path is None or relative_path == current_path:
        return _markdown_text(label)
    return _wiki_link(label, relative_path, current_path)


def _edge_inline(edge: WikiOntologyEdge, current_path: str) -> str:
    subject = _wiki_link_or_text(edge.subject_label, edge.subject_path, current_path)
    return f"{subject} — `{_code_text(edge.predicate)}` → {_edge_object(edge, current_path)}"


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
