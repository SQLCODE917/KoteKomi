from __future__ import annotations

import pytest
from kotekomi_application.hybrid_event_semantics import (
    SupportOutcome,
    resolve_unique_source_literal,
)
from kotekomi_application.hybrid_event_semantics_model_output import (
    event_semantic_role_target_schema_bytes,
    event_semantic_schema_bytes,
    parse_event_semantic_output,
    parse_event_semantic_role_target_output,
    parse_semantic_support_output,
    semantic_support_schema_bytes,
)


def test_event_semantic_parser_preserves_role_targets_and_local_labels() -> None:
    proposal = parse_event_semantic_output(
        b"frame: causation\n"
        b"argument: causation.cause | e1\n"
        b"argument: causation.effect | mass resignations\n"
        b"qualifier: q1\n"
        b"reason: The source explicitly links the cause and effect.\n"
    )

    assert proposal.frame_id == "causation"
    assert proposal.arguments[1].target_value == "mass resignations"
    assert proposal.qualifiers[0].qualifier_label == "q1"


@pytest.mark.parametrize(
    "payload",
    (
        b"frame: causation\nargument: causation.effect | missing reason\n",
        b"frame: unresolved\nqualifier: q1\nreason: none fits\n",
        b"frame: causation\nreason: ok\nextra: bad\n",
        b"frame: causation\nattribution: source_narrator\nreason: ok\n",
    ),
)
def test_event_semantic_parser_rejects_changed_or_ambiguous_contracts(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_semantic_output(payload)


def test_event_semantic_parser_preserves_explicit_unresolved_result() -> None:
    proposal = parse_event_semantic_output(
        b"frame: unresolved\nreason: No governed frame accurately represents this event.\n"
    )

    assert proposal.frame_id is None
    assert proposal.arguments == ()


def test_role_target_parser_preserves_literal_and_explicit_absence() -> None:
    proposal = parse_event_semantic_role_target_output(
        b"target: an investment in Anthropic\nreason: The source identifies the abandoned asset.\n"
    )
    absent = parse_event_semantic_role_target_output(
        b"target: absent\nreason: No explicit target fills this role.\n"
    )

    assert proposal.target_value == "an investment in Anthropic"
    assert absent.target_value is None


@pytest.mark.parametrize(
    "payload",
    (
        b"frame: investment_abandonment\ntarget: eN\nreason: wrong shape\n",
        b"target: c1\n",
        b"target: c1\nreason: ok\nextra: bad\n",
    ),
)
def test_role_target_parser_rejects_changed_contracts(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_semantic_role_target_output(payload)


@pytest.mark.parametrize("outcome", tuple(SupportOutcome))
def test_semantic_support_parser_accepts_every_governed_outcome(
    outcome: SupportOutcome,
) -> None:
    parsed = parse_semantic_support_output(
        f"outcome: {outcome.value}\nreason: This is a bounded source-support judgment.\n".encode()
    )

    assert parsed.outcome is outcome


def test_semantic_task_schemas_are_literal_text_contracts() -> None:
    assert b"<supplied label or source literal>" in event_semantic_schema_bytes()
    assert b"target: <supplied cN or eN label" in event_semantic_role_target_schema_bytes()
    assert b"directly_supported" in semantic_support_schema_bytes()
    assert b'"properties"' not in event_semantic_schema_bytes()


def test_source_literal_resolution_preserves_authoritative_whitespace() -> None:
    source = "The  agency  authorized its workers."

    exact, start = resolve_unique_source_literal(source, "agency authorized its workers")

    assert exact == "agency  authorized its workers"
    assert source[start : start + len(exact)] == exact


def test_source_literal_resolution_rejects_ambiguous_normalized_text() -> None:
    with pytest.raises(ValueError, match="source_literal_not_unique"):
        resolve_unique_source_literal("the  agency and the agency", "the agency")
