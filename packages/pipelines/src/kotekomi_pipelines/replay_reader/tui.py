"""ANSI-colour terminal UI for the live replay reader.

Renders a ``ParagraphAnnotationProfile`` as one width-justified, in-place frame:

* a status header with the paragraph index and per-stage progress;
* the paragraph text with every annotation span tinted by its source stage;
* a caret ruler directly beneath the text tying each tinted span to a colour;
* a colour-keyed annotation panel reproducing the plain renderer's entries.

The module is pure: it composes strings from the model's dataclasses and
constants only. It never touches the Ledger, the Archive, or any Application
record.
"""

from __future__ import annotations

import os
import re
from collections.abc import Collection
from dataclasses import dataclass

from kotekomi_pipelines.replay_reader.model import (
    STAGE_LABELS,
    STAGE_ORDER,
    ParagraphAnnotationProfile,
    Span,
)
from kotekomi_pipelines.replay_reader.render import section_lines

RESET = "\033[0m"

_STAGE_COLORS: dict[str, int] = {
    "hp1_mentions": 96,
    "hp2_references": 95,
    "hp3_grounding": 92,
    "hp4_event_triggers": 93,
    "hp6_event_semantics": 91,
    "hp7_proposal_plan": 94,
    "hp10_standing_facts": 97,
}

_SGR = re.compile(r"\033\[[0-9;]*m")

_DEFAULT_COLOR_ENABLED = os.environ.get("NO_COLOR") is None and os.environ.get("TERM", "") != "dumb"


@dataclass(frozen=True)
class _Line:
    start: int
    end: int
    text: str


def wrap_text(text: str, width: int) -> tuple[_Line, ...]:
    """Word-wrap ``text`` into lines of at most ``width`` columns.

    Source offsets are preserved: every line's ``start``/``end`` are absolute
    offsets into ``text`` and ``text[start:end] == line.text``. Breaks prefer
    spaces; an overlong glyph run is split mid-word exactly at ``width``.
    """
    if width < 1:
        width = 1
    lines: list[_Line] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "\n":
            lines.append(_Line(i, i + 1, "\n"))
            i += 1
            continue
        if n - i <= width:
            lines.append(_Line(i, n, text[i:n]))
            break
        limit = i + width
        brk = limit
        for k in range(i + 1, limit):
            if text[k] == " " or text[k] == "\n":
                brk = k
        if brk == limit:
            lines.append(_Line(i, limit, text[i:limit]))
            i = limit
        else:
            lines.append(_Line(i, brk, text[i:brk]))
            i = brk + 1
    return tuple(lines)


def _visible_len(text: str) -> int:
    return len(_SGR.sub("", text))


def _style(text: str, fg: int | None, color: bool, *, bold: bool = False) -> str:
    if not color:
        return text
    codes = ""
    if fg is not None:
        codes += f"\033[{fg}m"
    if bold:
        codes += "\033[1m"
    if not codes:
        return text
    return f"{codes}{text}{RESET}"


def _dim(text: str, color: bool) -> str:
    if not color:
        return text
    return f"\033[2m{text}{RESET}"


def _stage_spans(profile: ParagraphAnnotationProfile, stage: str) -> tuple[Span, ...]:
    if stage == "hp1_mentions":
        return tuple(mention.span for mention in profile.mentions)
    if stage == "hp2_references":
        spans: list[Span] = []
        for reference in profile.references:
            spans.append(reference.source_span)
            spans.extend(reference.target_spans)
        return tuple(spans)
    if stage == "hp3_grounding":
        return tuple(grounding.span for grounding in profile.groundings)
    if stage == "hp4_event_triggers":
        return tuple(trigger.span for trigger in profile.triggers)
    if stage == "hp6_event_semantics":
        return tuple(
            event.trigger_span for event in profile.events if event.trigger_span is not None
        )
    if stage == "hp10_standing_facts":
        spans = []
        for fact in profile.standing_facts:
            if fact.subject_span is not None:
                spans.append(fact.subject_span)
            spans.append(fact.relation_span)
            if fact.object_span is not None:
                spans.append(fact.object_span)
        return tuple(spans)
    return ()


def _column_colors(
    profile: ParagraphAnnotationProfile, completed: Collection[str]
) -> list[int | None]:
    colors: list[int | None] = [None] * len(profile.text)
    for stage in STAGE_ORDER:
        if stage not in completed or stage not in profile.present_stages:
            continue
        code = _STAGE_COLORS[stage]
        for span in _stage_spans(profile, stage):
            for index in range(span.start, span.end):
                colors[index] = code
    return colors


def _runs(colors: list[int | None]) -> list[tuple[int, int, int | None]]:
    runs: list[tuple[int, int, int | None]] = []
    i = 0
    while i < len(colors):
        code = colors[i]
        j = i + 1
        while j < len(colors) and colors[j] == code:
            j += 1
        runs.append((i, j, code))
        i = j
    return runs


def _paint_text(
    text: str,
    runs: list[tuple[int, int, int | None]],
    start: int,
    end: int,
    color: bool,
) -> str:
    out: list[str] = []
    for run_start, run_end, code in runs:
        run_start = max(run_start, start)
        run_end = min(run_end, end)
        if run_start >= run_end:
            continue
        segment = text[run_start:run_end]
        out.append(_style(segment, code, color) if code is not None else segment)
    return "".join(out)


def _has_caret(colors: list[int | None], start: int, end: int) -> bool:
    return any(colors[index] is not None for index in range(start, end))


def _paint_carets(colors: list[int | None], start: int, end: int, color: bool) -> str:
    out: list[str] = []
    run_start = start
    current = colors[start]
    for index in range(start + 1, end):
        code = colors[index]
        if code != current:
            length = index - run_start
            out.append(
                _style("^" * length, current, color) if current is not None else " " * length
            )
            run_start = index
            current = code
    length = end - run_start
    out.append(_style("^" * length, current, color) if current is not None else " " * length)
    return "".join(out)


def _render_paragraph(
    profile: ParagraphAnnotationProfile,
    colors: list[int | None],
    width: int,
    color: bool,
) -> list[str]:
    runs = _runs(colors)
    lines: list[str] = []
    for line in wrap_text(profile.text, width):
        lines.append(_paint_text(profile.text, runs, line.start, line.end, color))
        if _has_caret(colors, line.start, line.end):
            lines.append(_paint_carets(colors, line.start, line.end, color))
    return lines


def _progress_bar(completed: Collection[str], color: bool) -> list[str]:
    tokens: list[str] = []
    for stage in STAGE_ORDER:
        mark = "\u2713" if stage in completed else "\u00b7"
        token = f"{stage}{mark}"
        if stage in completed:
            tokens.append(_style(token, _STAGE_COLORS[stage], color))
        else:
            tokens.append(_dim(token, color))
    return tokens


def _truncate_progress(tokens: list[str], width: int, color: bool) -> str:
    out: list[str] = []
    used = 0
    for token in tokens:
        length = _visible_len(token)
        if used + length > width:
            break
        out.append(token)
        used += length
    text = " ".join(out)
    return text + (RESET if color and out else "")


def _wrap_panel(prefix: str, body: str, width: int, code: int, color: bool) -> list[str]:
    hang = " " * len(prefix)
    lines: list[str] = []
    combined = wrap_text(prefix + body, width)
    for index, line in enumerate(combined):
        if index == 0:
            lines.append(_style(line.text, code, color))
            continue
        for cont in wrap_text(line.text, width - len(hang)):
            lines.append(_style(hang + cont.text, code, color))
    return lines


def _panel(
    profile: ParagraphAnnotationProfile,
    completed: Collection[str],
    width: int,
    color: bool,
) -> list[str]:
    lines: list[str] = []
    for stage in STAGE_ORDER:
        if stage not in completed or stage not in profile.present_stages:
            continue
        section = section_lines(
            stage,
            profile.mentions,
            profile.references,
            profile.groundings,
            profile.triggers,
            profile.events,
            profile.standing_facts,
            profile.proposal_plan,
        )
        if not section:
            continue
        code = _STAGE_COLORS[stage]
        heading = f"\u25b8 {STAGE_LABELS[stage]} ({stage})"
        lines.append(_style(_clip(heading, width), code, color, bold=True))
        for entry in section:
            if entry.startswith("  - "):
                body = entry[4:]
            elif entry.startswith("  "):
                body = entry[2:]
            else:
                body = entry
            lines.extend(_wrap_panel("\u25b8 ", body, width, code, color))
    return lines


def _clip(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "\u2026"


def render_tui_block(
    profile: ParagraphAnnotationProfile,
    completed_stages: Collection[str],
    *,
    width: int = 80,
    ordinal: int = 0,
    total: int = 1,
    color: bool | None = None,
) -> str:
    """Render one paragraph's in-progress frame for in-place live display."""
    enabled = _DEFAULT_COLOR_ENABLED if color is None else color
    completed = set(completed_stages)
    colors = _column_colors(profile, completed)

    lines: list[str] = [
        _style(
            f"KOTEKOMI \u00b7 HP-8 live replay \u00b7 paragraph {ordinal + 1}/{total}",
            None,
            enabled,
            bold=True,
        ),
        _truncate_progress(_progress_bar(completed, enabled), width, enabled),
        "",
    ]
    lines.extend(_render_paragraph(profile, colors, width, enabled))
    lines.append("")
    lines.extend(_panel(profile, completed, width, enabled))
    return "\n".join(lines)
