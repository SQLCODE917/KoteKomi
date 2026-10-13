"""Source-attached annotation projection shared by Textual and plain output."""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from dataclasses import dataclass

from kotekomi_application.ingestion_inspection import (
    STAGE_ORDER,
    ParagraphAnnotationProfile,
    Span,
)
from rich.cells import cell_len, split_graphemes
from rich.style import Style
from rich.text import Text

STAGE_LABELS = dict(
    zip(
        STAGE_ORDER,
        (
            "Mentions",
            "References",
            "Grounding",
            "Event triggers",
            "Events",
            "Proposal plan",
            "Standing facts",
        ),
        strict=True,
    )
)


STAGE_COLORS = dict(
    zip(
        STAGE_ORDER,
        (
            "bright_cyan",
            "bright_magenta",
            "bright_green",
            "bright_yellow",
            "bright_red",
            "bright_blue",
            "bright_white",
        ),
        strict=True,
    )
)


@dataclass(frozen=True)
class Annotation:
    key: str
    stage: str
    span: Span
    label: str
    details: str
    related_spans: tuple[Span, ...] = ()


def profile_annotations(profile: ParagraphAnnotationProfile) -> tuple[Annotation, ...]:
    """Project every phase explicitly, preserving independent overlapping layers."""
    entries: dict[str, list[tuple[Span, str, str, tuple[Span, ...]]]] = {
        stage: [] for stage in STAGE_ORDER
    }
    mention_records = {r.key: r for r in profile.records if r.stage == "hp1_mentions"}
    for index, item in enumerate(profile.mentions):
        record = mention_records.get(f"hp1_mentions:{index}")
        interpretation = record.data.get("contextual_kind") if record else None
        kinds = str(interpretation) if interpretation else ", ".join(item.type_hints) or "untyped"
        state = "selected candidate" if item.selected else "unselected candidate"
        label = f"Mention · {kinds} · {state}"
        entries["hp1_mentions"].append(
            (
                item.span,
                label,
                f"{label}\nRaw hints: {', '.join(item.type_hints)}\nProducers: {item.producers}",
                (),
            )
        )
    for item in profile.references:
        targets = (
            "\n".join(
                f'"{target.text}" · node {target.node_id} · TextView {target.text_view_id} '
                f"({target.start_char}:{target.end_char})"
                for target in item.targets
            )
            or "No resolved target"
        )
        entries["hp2_references"].append(
            (
                item.source_span,
                f"Reference · {item.kind} · {item.status}",
                f"{item.reason}\n{targets}",
                tuple(
                    target.local_span for target in item.targets if target.local_span is not None
                ),
            )
        )
    for item in profile.groundings:
        identity = item.top_id or "NIL"
        label = f"Grounding · {item.top_label or identity}"
        score = f"{item.score:.3f}" if item.score is not None else "n/a"
        entries["hp3_grounding"].append(
            (
                item.span,
                label,
                f"Candidate identity: {identity}\nLabel: {item.top_label}\nScore: {score}",
                (),
            )
        )
    for item in profile.triggers:
        entries["hp4_event_triggers"].append(
            (
                item.span,
                f"Event trigger · {item.label}",
                f'Head: "{item.head_span.text}"\nTrigger: {item.trigger_id}',
                (item.head_span,),
            )
        )
    for item in profile.events:
        entries["hp6_event_semantics"].append(
            (
                item.trigger_span,
                f"Event · {item.expression_text}",
                f'Proposed Event: {item.event_id}\nHead: "{item.head_text}"\n'
                f"Type: {item.trigger_label}",
                (),
            )
        )
    for item in profile.proposal_plan:
        kinds = ", ".join(change.record_type for change in item.proposed_changes)
        details = "\n".join(
            f'{change.record_type}: "{change.name}" · {change.record_id} · {change.change_id}'
            for change in item.proposed_changes
        )
        entries["hp7_proposal_plan"].append(
            (
                item.trigger_span,
                f"Proposal · {kinds or 'no changes'}",
                f"Planned ProposedChanges; awaiting review\nEvent: {item.event_id}\n{details}",
                (),
            )
        )
    for item in profile.standing_facts:
        related = tuple(span for span in (item.subject_span, item.object_span) if span is not None)
        entries["hp10_standing_facts"].append(
            (
                item.relation_span,
                f"Standing fact · {item.relation_label} · {item.disposition}",
                f"{item.subject_label} --{item.relation_label}-> {item.object_selector}\n"
                f"Disposition: {item.disposition}",
                related,
            )
        )
    records = {r.key: r for r in profile.records}
    result: list[Annotation] = []
    for stage in STAGE_ORDER:
        if stage not in profile.present_stages:
            continue
        for index, (span, label, details, related) in enumerate(entries[stage]):
            for anchor in (span, *related):
                if not (0 <= anchor.start < anchor.end <= len(profile.text)):
                    raise ValueError("annotation span is outside the paragraph.")
                if profile.text[anchor.start : anchor.end] != anchor.text:
                    raise ValueError("annotation span text does not match the paragraph.")
            key = f"{stage}:{index}"
            record = records.get(key)
            if record is not None:
                details += f"\nRecord: {record.record_id}\n" + json.dumps(
                    record.data, ensure_ascii=False, indent=2
                )
            result.append(Annotation(key, stage, span, label, details, related))
    return tuple(result)


@dataclass(frozen=True)
class SourceLine:
    start: int
    end: int
    text: str
    columns: tuple[int, ...]
    display_offsets: tuple[int, ...]


def source_lines(text: str, width: int) -> tuple[SourceLine, ...]:
    """Wrap source graphemes in terminal cells, retaining original character coordinates."""
    width = max(2, width)
    lines: list[SourceLine] = []
    position = 0
    for logical in text.split("\n"):
        glyphs: list[tuple[int, int, str, int]] = []
        for part in re.finditer(r"\t|[^\t]+", logical):
            if part.group() == "\t":
                glyphs.append((part.start(), part.end(), "\t", 0))
            else:
                spans, _ = split_graphemes(part.group())
                for start, end, cells in spans:
                    glyph = part.group()[start:end]
                    if any(ord(char) < 32 or ord(char) == 127 for char in glyph):
                        glyph = glyph.encode("unicode_escape").decode("ascii")
                        cells = cell_len(glyph)
                    glyphs.append((part.start() + start, part.start() + end, glyph, cells))
        start = 0
        display = ""
        columns = [0]
        offsets = [0]
        cells_used = 0
        for glyph_start, glyph_end, glyph, cells in glyphs:
            if glyph == "\t":
                cells = 4 - cells_used % 4
            if cells_used + cells > width and glyph_start > start:
                lines.append(
                    SourceLine(
                        position + start,
                        position + glyph_start,
                        display,
                        tuple(columns),
                        tuple(offsets),
                    )
                )
                start = glyph_start
                display, columns, offsets, cells_used = "", [0], [0], 0
                if glyph == "\t":
                    cells = 4
            if glyph == "\t":
                glyph = " " * min(cells, width)
                cells = len(glyph)
            for _ in range(glyph_end - glyph_start - 1):
                columns.append(cells_used)
                offsets.append(len(display))
            display += glyph
            cells_used += cells
            columns.append(cells_used)
            offsets.append(len(display))
        lines.append(
            SourceLine(
                position + start, position + len(logical), display, tuple(columns), tuple(offsets)
            )
        )
        position += len(logical) + 1
    return tuple(lines)


@dataclass(frozen=True)
class AnnotatedRow:
    text: Text
    source_start: int
    source_end: int
    annotation_key: str | None = None


def _source_style_range(line: SourceLine, span: Span) -> tuple[int, int] | None:
    left, right = max(span.start, line.start), min(span.end, line.end)
    if left >= right:
        return None
    left_index, right_index = left - line.start, right - line.start
    # A character range inside a grapheme paints the whole visible grapheme.
    # Source coordinates and exact text remain unchanged.
    while (
        right_index < line.end - line.start
        and line.display_offsets[right_index] == line.display_offsets[right_index - 1]
    ):
        right_index += 1
    return line.display_offsets[left_index], line.display_offsets[right_index]


def annotated_rows(
    profile: ParagraphAnnotationProfile,
    visible_stages: Collection[str],
    width: int,
    selected_key: str | None = None,
    *,
    color: bool = True,
) -> tuple[AnnotatedRow, ...]:
    visible = [item for item in profile_annotations(profile) if item.stage in visible_stages]
    selected = next((item for item in visible if item.key == selected_key), None)
    result: list[AnnotatedRow] = []
    for line in source_lines(profile.text, width):
        source = Text(line.text, no_wrap=True)
        for item in visible:
            for span in (item.span, *item.related_spans):
                extent = _source_style_range(line, span)
                if extent is not None:
                    source.stylize("underline", *extent)
        if selected is not None:
            for span in (selected.span, *selected.related_spans):
                extent = _source_style_range(line, span)
                if extent is not None:
                    source.stylize("bold reverse", *extent)
        result.append(AnnotatedRow(source, line.start, line.end))
        anchored = sorted(
            (item for item in visible if line.start <= item.span.start < line.end),
            key=lambda item: (STAGE_ORDER.index(item.stage), item.span.start, item.key),
        )
        for item in anchored:
            column = line.columns[item.span.start - line.start]
            indent = column
            label = Text(
                " " * indent + "└─ " + " ".join(item.label.split()),
                no_wrap=True,
                overflow="ellipsis",
            )
            label.truncate(max(2, width), overflow="ellipsis")
            label.stylize(
                Style(
                    color=STAGE_COLORS[item.stage] if color else None,
                    bold=item.key == selected_key,
                    meta={"annotation": item.key},
                )
            )
            result.append(AnnotatedRow(label, item.span.start, item.span.end, item.key))
    return tuple(result)


def render_annotated_paragraph(
    profile: ParagraphAnnotationProfile,
    reveal_stages: Collection[str] | None = None,
    *,
    width: int = 100,
) -> str:
    revealed = profile.present_stages if reveal_stages is None else reveal_stages
    lines = ["stages: " + " ".join(stage for stage in STAGE_ORDER if stage in revealed), ""]
    lines.extend(row.text.plain for row in annotated_rows(profile, revealed, width, color=False))
    for item in profile_annotations(profile):
        if item.stage in revealed:
            lines.extend(
                (
                    "",
                    f"{STAGE_LABELS[item.stage]} · {item.span.start}:{item.span.end}",
                    item.details,
                )
            )
    return "\n".join(lines)


def render_live_block(
    profile: ParagraphAnnotationProfile, completed_stages: Collection[str]
) -> str:
    return render_annotated_paragraph(profile, completed_stages)
