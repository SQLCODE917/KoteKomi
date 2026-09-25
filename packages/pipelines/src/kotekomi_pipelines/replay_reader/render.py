"""Plain-text rendering for the replay reader.

Renders a ``ParagraphAnnotationProfile`` into a deterministic, terminal-safe
block. This module imports only the model's plain dataclasses and constants; it
has no knowledge of Application records or storage. It also provides
``run_replay`` as a thin presentation driver that optionally reveals the block
line by line.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Collection, Iterable
from typing import TextIO

from kotekomi_pipelines.replay_reader.model import (
    STAGE_LABELS,
    STAGE_ORDER,
    EventAnnotation,
    GroundingAnnotation,
    MentionAnnotation,
    ParagraphAnnotationProfile,
    ProposalPlanAnnotation,
    ReferenceAnnotation,
    Span,
    StandingFactAnnotation,
    TriggerAnnotation,
)


def _span(span: Span) -> str:
    return f'"{span.text}" ({span.start}:{span.end})'


def _mention_lines(mentions: Iterable[MentionAnnotation]) -> list[str]:
    lines: list[str] = []
    for mention in mentions:
        kinds = ",".join(mention.type_hints)
        selected = " [selected]" if mention.selected else ""
        lines.append(
            f"  - {_span(mention.span)} type={kinds} producers={mention.producers}{selected}"
        )
    return lines


def _reference_lines(references: Iterable[ReferenceAnnotation]) -> list[str]:
    lines: list[str] = []
    for reference in references:
        targets = ", ".join(_span(target) for target in reference.target_spans)
        lines.append(
            f"  - {_span(reference.source_span)} -> {targets} "
            f"{reference.kind}/{reference.status}/{reference.reason}"
        )
    return lines


def _grounding_lines(groundings: Iterable[GroundingAnnotation]) -> list[str]:
    lines: list[str] = []
    for grounding in groundings:
        identity = grounding.top_id or "NIL"
        label = f" {grounding.top_label}" if grounding.top_label else ""
        score = f"score={grounding.score:.3f}" if grounding.score is not None else "score=n/a"
        lines.append(f"  - {_span(grounding.span)} -> {identity}{label} {score}")
    return lines


def _trigger_lines(triggers: Iterable[TriggerAnnotation]) -> list[str]:
    lines: list[str] = []
    for trigger in triggers:
        lines.append(
            f"  - {_span(trigger.span)} event_type={trigger.label} head={_span(trigger.head_span)}"
        )
    return lines


def _event_lines(events: Iterable[EventAnnotation]) -> list[str]:
    lines: list[str] = []
    for event in events:
        trigger_ref: str = (
            _span(event.trigger_span) if event.trigger_span is not None else "<unresolved>"
        )
        lines.append(
            f'  - head="{event.head_text}" expression="{event.expression_text}" '
            f"trigger={trigger_ref} ({event.trigger_label})"
        )
    return lines


def _standing_fact_lines(facts: Iterable[StandingFactAnnotation]) -> list[str]:
    lines: list[str] = []
    for fact in facts:
        subject: str = (
            _span(fact.subject_span) if fact.subject_span is not None else f"[{fact.subject_label}]"
        )
        object_ref = (
            _span(fact.object_span) if fact.object_span is not None else fact.object_selector
        )
        lines.append(f"  - {subject} --{fact.relation_label}-> {object_ref} [{fact.disposition}]")
    return lines


def _proposal_plan_lines(proposals: Iterable[ProposalPlanAnnotation]) -> list[str]:
    lines: list[str] = []
    for proposal in proposals:
        lines.append(f'  - event "{proposal.event_text}" ({proposal.event_id})')
        for change in proposal.proposed_changes:
            lines.append(f'      * {change.record_type} "{change.name}" ({change.record_id})')
    return lines


def section_lines(
    stage: str,
    mentions: Iterable[MentionAnnotation],
    references: Iterable[ReferenceAnnotation],
    groundings: Iterable[GroundingAnnotation],
    triggers: Iterable[TriggerAnnotation],
    events: Iterable[EventAnnotation],
    standing_facts: Iterable[StandingFactAnnotation],
    proposals: Iterable[ProposalPlanAnnotation],
) -> list[str]:
    sections: dict[str, list[str]] = {
        "hp1_mentions": _mention_lines(mentions),
        "hp2_references": _reference_lines(references),
        "hp3_grounding": _grounding_lines(groundings),
        "hp4_event_triggers": _trigger_lines(triggers),
        "hp6_event_semantics": _event_lines(events),
        "hp10_standing_facts": _standing_fact_lines(standing_facts),
        "hp7_proposal_plan": _proposal_plan_lines(proposals),
    }
    return sections.get(stage, [])


def render_annotated_paragraph(
    profile: ParagraphAnnotationProfile,
    reveal_stages: Collection[str] | None = None,
) -> str:
    """Render the profile as a deterministic annotated-paragraph block."""
    revealed = set(profile.present_stages) if reveal_stages is None else set(reveal_stages)
    visible = [
        stage for stage in STAGE_ORDER if stage in profile.present_stages and stage in revealed
    ]
    lines: list[str] = [
        "stages: " + " ".join(visible),
        "",
        profile.text,
        "",
    ]
    for stage in STAGE_ORDER:
        if stage not in profile.present_stages or stage not in revealed:
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
        if section:
            lines.append(f"{STAGE_LABELS[stage]} ({stage}):")
            lines.extend(section)
            continue
        lines.append(f"{STAGE_LABELS[stage]} ({stage}): <not rendered>")
    return "\n".join(lines)


def run_replay(
    profile: ParagraphAnnotationProfile,
    *,
    delay: float = 0.0,
    stream: TextIO | None = None,
) -> None:
    """Write the annotated block, optionally revealing it line by line."""
    out = sys.stdout if stream is None else stream
    block = render_annotated_paragraph(profile)
    if delay <= 0:
        out.write(block + "\n")
        out.flush()
        return
    for line in block.splitlines():
        out.write(line + "\n")
        out.flush()
        time.sleep(delay)


def render_live_block(
    profile: ParagraphAnnotationProfile,
    completed_stages: Collection[str],
) -> str:
    """Render one paragraph's in-progress block for in-place live display.

    Unlike :func:`render_annotated_paragraph`, pending stages are omitted rather
    than rendered as ``<not rendered>``, so the block grows as each stage
    completes. The paragraph text is always shown.
    """
    completed = set(completed_stages)
    visible = [stage for stage in STAGE_ORDER if stage in completed]
    lines: list[str] = [
        "stages: " + " ".join(visible),
        "",
        profile.text,
        "",
    ]
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
        if section:
            lines.append(f"{STAGE_LABELS[stage]} ({stage}):")
            lines.extend(section)
    return "\n".join(lines)
