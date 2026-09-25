"""Deterministic unit coverage for the ANSI-colour replay TUI.

These tests only exercise the pure string-composition seams: the width-justified
word wrapper and the span-highlighted frame renderer. No persisted state, no
terminal, no model runtime is required.
"""

from __future__ import annotations

from kotekomi_pipelines.replay_reader.model import (
    MentionAnnotation,
    ParagraphAnnotationProfile,
    ProposalPlanAnnotation,
    Span,
)
from kotekomi_pipelines.replay_reader.tui import render_tui_block, wrap_text


def _profile(
    text: str,
    mentions: tuple[MentionAnnotation, ...] = (),
    proposal_plan: tuple[ProposalPlanAnnotation, ...] = (),
    present_stages: frozenset[str] = frozenset(),
) -> ParagraphAnnotationProfile:
    return ParagraphAnnotationProfile(
        text=text,
        segments=(),
        mentions=mentions,
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        standing_facts=(),
        present_stages=present_stages,
        proposal_plan=proposal_plan,
    )


def test_wrap_text_preserves_offsets_and_width() -> None:
    text = "Hegseth rebuked Anthropic chief executive Dario Amodei"
    lines = wrap_text(text, 20)
    assert lines
    for line in lines:
        assert line.text == text[line.start : line.end]
        assert 0 <= line.start < line.end <= len(text)
        assert len(line.text) <= 20
    for index in range(len(lines) - 1):
        prev = lines[index]
        nxt = lines[index + 1]
        gap = nxt.start - prev.end
        assert gap in (0, 1)
        if gap == 1:
            assert text[prev.end] == " "


def test_wrap_text_splits_overlong_word() -> None:
    lines = wrap_text("supercalifragilisticexpialidocious", 10)
    assert len(lines) == 4
    assert all(len(line.text) <= 10 for line in lines)


def test_render_tui_block_colors_mention_span() -> None:
    profile = _profile(
        "Acme Corp acquired Widget Co.",
        mentions=(
            MentionAnnotation(
                span=Span(0, 9, "Acme Corp"),
                type_hints=("ORG",),
                selected=True,
                producers=1,
            ),
        ),
        present_stages=frozenset({"hp1_mentions"}),
    )
    rendered = render_tui_block(
        profile,
        completed_stages={"hp1_mentions"},
        width=80,
        color=True,
    )
    assert "paragraph 1/1" in rendered
    assert "\033[96mAcme Corp\033[0m" in rendered
    assert "\033[96m^^^^^^^^^\033[0m" in rendered
    assert "Mentions (hp1_mentions)" in rendered


def test_render_tui_block_omits_pending_stages() -> None:
    profile = _profile(
        "Acme Corp acquired Widget Co.",
        mentions=(
            MentionAnnotation(
                span=Span(0, 9, "Acme Corp"),
                type_hints=("ORG",),
                selected=True,
                producers=1,
            ),
        ),
        proposal_plan=(
            ProposalPlanAnnotation(event_id="evt_1", event_text="acquired", proposed_changes=()),
        ),
        present_stages=frozenset({"hp1_mentions", "hp7_proposal_plan"}),
    )
    rendered = render_tui_block(
        profile,
        completed_stages={"hp1_mentions"},
        width=80,
        color=True,
    )
    assert "Mentions (hp1_mentions)" in rendered
    assert "Proposal plan" not in rendered


def test_render_tui_block_plain_has_no_ansi() -> None:
    profile = _profile(
        "Acme Corp acquired Widget Co.",
        mentions=(
            MentionAnnotation(
                span=Span(0, 9, "Acme Corp"),
                type_hints=("ORG",),
                selected=True,
                producers=1,
            ),
        ),
        present_stages=frozenset({"hp1_mentions"}),
    )
    rendered = render_tui_block(
        profile,
        completed_stages={"hp1_mentions"},
        width=80,
        color=False,
    )
    assert "\033" not in rendered
    assert "^" in rendered
    assert "Mentions (hp1_mentions)" in rendered


def test_render_tui_block_caret_count_matches_covered_columns() -> None:
    text = "Hegseth rebuked Anthropic"
    profile = _profile(
        text,
        mentions=(
            MentionAnnotation(
                span=Span(0, 7, "Hegseth"),
                type_hints=("person",),
                selected=True,
                producers=1,
            ),
            MentionAnnotation(
                span=Span(15, 24, "Anthropic"),
                type_hints=("organization",),
                selected=True,
                producers=1,
            ),
        ),
        present_stages=frozenset({"hp1_mentions"}),
    )
    covered = set(range(0, 7)) | set(range(15, 24))
    rendered = render_tui_block(
        profile,
        completed_stages={"hp1_mentions"},
        width=80,
        color=True,
    )
    assert rendered.count("^") == len(covered)
