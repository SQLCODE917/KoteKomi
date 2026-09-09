from __future__ import annotations

import hashlib

from kotekomi_application import (
    StandingFactDraft,
    StandingFactHoldReason,
    standing_fact_source_hold_reasons,
)
from kotekomi_application.hybrid_standing_fact_model_output import StandingFactObjectKind


def test_event_bearing_source_does_not_preempt_an_independent_standing_fact() -> None:
    source = "Dario Amodei is Anthropic's chief executive and criticized Stargate."
    draft = _draft(
        relation="is",
        object_literal="Anthropic's chief executive",
    )

    reasons = standing_fact_source_hold_reasons(draft, source)

    assert reasons == ()
    assert StandingFactHoldReason.EVENT_ROUTE_REQUIRED not in reasons


def test_parallel_route_still_rejects_a_literal_absent_from_authoritative_source() -> None:
    draft = _draft(relation="is", object_literal="Anthropic's founder")

    reasons = standing_fact_source_hold_reasons(
        draft,
        "Dario Amodei is Anthropic's chief executive and criticized Stargate.",
    )

    assert reasons == (StandingFactHoldReason.LITERAL_NOT_IN_SOURCE,)


def _draft(*, relation: str, object_literal: str) -> StandingFactDraft:
    parts = (
        "seg_fixture",
        "c1",
        "candidate_amodei",
        relation,
        StandingFactObjectKind.LITERAL.value,
        object_literal,
        "",
        "ext_fixture",
        "mrn_fixture",
    )
    return StandingFactDraft(
        id="sfd_" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24],
        source_segment_id=parts[0],
        subject_label=parts[1],
        subject_candidate_id=parts[2],
        relation_label=relation,
        object_kind=StandingFactObjectKind.LITERAL,
        object_label_or_literal=object_literal,
        extraction_task_id=parts[7],
        model_run_id=parts[8],
    )
