from __future__ import annotations

import pytest
from kotekomi_application.hybrid_event_semantics import (
    SupportOutcome,
    resolve_unique_source_literal,
)
from kotekomi_application.hybrid_event_semantics_model_output import (
    event_frame_fit_schema_bytes,
    event_frame_selection_schema_bytes,
    event_presentation_schema_bytes,
    event_semantic_role_target_schema_bytes,
    parse_event_frame_fit_output,
    parse_event_frame_selection_output,
    parse_event_presentation_output,
    parse_event_semantic_role_target_output,
    parse_semantic_support_output,
    semantic_support_schema_bytes,
)


def test_frame_selection_parser_preserves_one_governed_choice() -> None:
    parsed = parse_event_frame_selection_output(
        b"frame: causation\nreason: The target occurrence expresses a cause and an effect.\n"
    )

    assert parsed.frame_id == "causation"


def test_frame_selection_parser_preserves_explicit_unresolved_result() -> None:
    parsed = parse_event_frame_selection_output(
        b"frame: unresolved\nreason: No governed frame accurately represents this occurrence.\n"
    )

    assert parsed.frame_id is None


@pytest.mark.parametrize(
    "payload",
    (
        b"frame: causation\n",
        b"frame: invented.dot.extra\nreason: invalid identifier\n",
        b"reason: wrong order\nframe: causation\n",
    ),
)
def test_frame_selection_parser_rejects_changed_contracts(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_frame_selection_output(payload)


def test_frame_fit_parser_preserves_binary_fit_and_rejection() -> None:
    accepted = parse_event_frame_fit_output(
        b"fit: yes\nreason: The governed definition represents the target event.\n"
    )
    rejected = parse_event_frame_fit_output(
        b"fit: no\nreason: The selected frame describes a different event family.\n"
    )

    assert accepted.fits is True
    assert rejected.fits is False


@pytest.mark.parametrize(
    "payload",
    (
        b"fit: maybe\nreason: This is not a binary decision.\n",
        b"fit: yes\n",
        b"reason: wrong order\nfit: yes\n",
    ),
)
def test_frame_fit_parser_rejects_changed_contracts(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_frame_fit_output(payload)


def test_event_presentation_parser_preserves_classification_and_qualifiers() -> None:
    parsed = parse_event_presentation_output(
        b"polarity: affirmed\n"
        b"modality: actual\n"
        b"attribution: source_narrator\n"
        b"qualifier: time | after | o4-o5\n"
        b"reason: The source presents this as an actual event.\n"
    )

    selection = parsed.selection
    assert selection.polarity == "affirmed"
    assert selection.modality == "actual"
    assert selection.attribution_selector == "source_narrator"
    assert selection.qualifiers[0].source_selector == "o4-o5"
    assert selection.qualifiers[0].temporal_relation is not None
    assert selection.qualifiers[0].temporal_relation.value == "after"
    assert parsed.rejections == ()


@pytest.mark.parametrize(
    "payload",
    (
        b"frame: causation\nargument: causation.effect | missing reason\n",
        b"frame: unresolved\npolarity: affirmed\nmodality: actual\n"
        b"attribution: source_narrator\nqualifier: place | London\nreason: none fits\n",
        b"frame: causation\npolarity: asserted\nmodality: actual\n"
        b"attribution: source_narrator\nreason: bad polarity\n",
        b"frame: causation\npolarity: affirmed\nmodality: factual\n"
        b"attribution: source_narrator\nreason: bad modality\n",
    ),
)
def test_event_presentation_parser_rejects_changed_envelopes(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_presentation_output(payload)


def test_event_presentation_parser_isolates_invalid_optional_lines() -> None:
    parsed = parse_event_presentation_output(
        b"polarity: affirmed\n"
        b"modality: actual\n"
        b"attribution: source_narrator\n"
        b"qualifier: time | someday | o1-o2\n"
        b"reason: The source presents this as an actual event.\n"
    )

    assert parsed.selection.qualifiers == ()
    assert len(parsed.rejections) == 1
    assert parsed.rejections[0].line_number == 4


def test_role_target_parser_preserves_source_selector_and_explicit_absence() -> None:
    proposal = parse_event_semantic_role_target_output(
        b"target: o4-o7\nreason: The source identifies the abandoned asset.\n"
    )
    absent = parse_event_semantic_role_target_output(
        b"target: absent\nreason: No explicit target fills this role.\n"
    )

    assert proposal.target_selector == "o4-o7"
    assert absent.target_selector is None


@pytest.mark.parametrize(
    "payload",
    (
        b"frame: investment_abandonment\ntarget: eN\nreason: wrong shape\n",
        b"target: c1\n",
        b"target: c1\nreason: ok\nextra: bad\n",
        b"target: copied source text\nreason: literals are forbidden\n",
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
    assert b"<supplied_frame_id>" in event_frame_selection_schema_bytes()
    assert event_frame_fit_schema_bytes().startswith(b"fit: yes|no")
    assert b"polarity: affirmed|negated" in event_presentation_schema_bytes()
    assert b"target: <supplied cN or oN[-oN] selector" in event_semantic_role_target_schema_bytes()
    assert b"directly_supported" in semantic_support_schema_bytes()
    assert b'"properties"' not in event_frame_selection_schema_bytes()


def test_source_literal_resolution_preserves_authoritative_whitespace() -> None:
    source = "The  agency  authorized its workers."

    exact, start = resolve_unique_source_literal(source, "agency authorized its workers")

    assert exact == "agency  authorized its workers"
    assert source[start : start + len(exact)] == exact


def test_source_literal_resolution_rejects_ambiguous_normalized_text() -> None:
    with pytest.raises(ValueError, match="source_literal_not_unique"):
        resolve_unique_source_literal("the  agency and the agency", "the agency")
