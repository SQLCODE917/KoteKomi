"""Deterministic Markdown renderer for a Candidate Wiki plan."""

from __future__ import annotations

import hashlib
import posixpath
from pathlib import PurePosixPath

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    RenderedCandidateWiki,
    RenderedWikiFile,
    WikiBuildFileEntry,
    WikiBuildManifest,
    WikiCitationRegistry,
    WikiDetail,
    WikiLink,
    WikiPageInput,
    WikiStatement,
    candidate_wiki_build_id,
    canonical_wiki_citations_bytes,
    canonical_wiki_manifest_bytes,
)


class MarkdownCandidateWikiRenderer:
    """Render validated page inputs without consulting state or a model."""

    def render(self, plan: CandidateWikiPlan) -> RenderedCandidateWiki:
        citations = canonical_wiki_citations_bytes(plan.citation_registry)
        rendered_pages = tuple(
            RenderedWikiFile(page.relative_path, _render_page(page, plan.citation_registry))
            for page in plan.pages
        )
        content_files = (*rendered_pages, RenderedWikiFile("citations.json", citations))
        page_fingerprints = {page.relative_path: page.input_fingerprint for page in plan.pages}
        citation_fingerprint = hashlib.sha256(citations).hexdigest()
        entries = tuple(
            WikiBuildFileEntry(
                relative_path=item.relative_path,
                input_fingerprint=page_fingerprints.get(item.relative_path, citation_fingerprint),
                content_sha256=hashlib.sha256(item.payload).hexdigest(),
            )
            for item in sorted(content_files, key=lambda file: file.relative_path)
        )
        build_id = candidate_wiki_build_id(
            view_policy_id=plan.view_policy_id,
            renderer_policy_id=plan.renderer_policy_id,
            ingestion_run_id=plan.ingestion_run_id,
            ingestion_change_set_id=plan.ingestion_change_set_id,
            candidate_snapshot_digest=plan.candidate_snapshot_digest,
            files=entries,
            counts=plan.counts,
        )
        manifest = WikiBuildManifest(
            schema_version="candidate_wiki_manifest_v1",
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


def _render_page(page: WikiPageInput, registry: WikiCitationRegistry) -> bytes:
    lines = [
        f"# {_markdown_text(page.display_label)}",
        "",
        "> [!WARNING]",
        "> Unpublished Candidate Wiki. Pending records are not accepted intelligence.",
        "",
    ]
    if page.state is not None:
        lines.extend((f"Review state: **{page.state.upper()}**", ""))
    lines.extend(_details(page.details, page.relative_path))
    lines.extend(_links(page.links, page.relative_path))
    lines.extend(_statements("Statements", page.outgoing_statements, page.relative_path))
    lines.extend(_statements("Inbound statements", page.inbound_statements, page.relative_path))
    lines.extend(_evidence(page.citation_numbers, registry))
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
        citations = _citation_markers(link.citation_numbers)
        lines.append(
            f"- [{link.state.upper()}] {link.record_type}: "
            f"{_wiki_link(link.label, link.relative_path, current_path)}{citations}"
        )
    return [*lines, ""]


def _statements(title: str, statements: tuple[WikiStatement, ...], current_path: str) -> list[str]:
    if not statements:
        return []
    lines = [f"## {title}", ""]
    for statement in statements:
        subject = _wiki_link(statement.subject_label, statement.subject_path, current_path)
        object_text = (
            _wiki_link(statement.object_label, statement.object_path, current_path)
            if statement.object_path is not None
            else f"`{_code_text(statement.object_label)}`"
        )
        relation_kind = "proposed relation" if statement.state == "pending" else "relation"
        lines.append(
            f"- [{statement.state.upper()}] {subject} — {relation_kind} "
            f"`{_code_text(statement.relation_label)}` → {object_text}"
            f"{_citation_markers(statement.citation_numbers)}"
        )
    return [*lines, ""]


def _evidence(citation_numbers: tuple[int, ...], registry: WikiCitationRegistry) -> list[str]:
    if not citation_numbers:
        return []
    by_number = {item.citation_number: item for item in registry.citations}
    lines = ["## Evidence", ""]
    for number in sorted(set(citation_numbers)):
        citation = by_number[number]
        page_label = (
            ", ".join(str(page) for page in citation.page_numbers)
            if citation.page_numbers
            else "unavailable"
        )
        lines.extend(
            (
                f"{number}. Pages: {page_label}; characters "
                f"{citation.start_char}–{citation.end_char}.",
                "",
                f"> {_quote_text(citation.exact_text)}",
                "",
            )
        )
    return lines


def _wiki_link(label: str, relative_path: str, current_path: str) -> str:
    current_directory = PurePosixPath(current_path).parent.as_posix()
    target = posixpath.relpath(relative_path, start=current_directory)
    return f"[{_markdown_text(label)}]({target})"


def _citation_markers(numbers: tuple[int, ...]) -> str:
    return "".join(f" [{number}]" for number in numbers)


def _markdown_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def _code_text(value: str) -> str:
    return value.replace("`", "\\`").replace("\n", " ")


def _quote_text(value: str) -> str:
    return value.replace("\n", "\n> ")
