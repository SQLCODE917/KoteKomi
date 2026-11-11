"""Captured announcement contracts and explicit counterexamples; no model calls."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from kotekomi_application import (
    EventEntityLinguisticToken,
    SourceRange,
    build_constituent_candidate_inventory,
    derive_object_content_completion,
    derive_trigger_time_qualifier,
    select_source_grounded_constituents,
)
from kotekomi_application.decontextualization_composition import ObjectComplementUnsupported
from kotekomi_application.source_grounded_selection import (
    SourceGroundedBoundaryGap,
    SourceGroundedSelectionStatus,
)
from kotekomi_application.trigger_time_qualifier import TriggerTimeUnsupported

EVENT = "sge_6edd8bd8752b6a2621725489"
EXPECTED_SUBJECT = "secretary  of  defense  Pete  Hegseth"
EXPECTED_OBJECT = (
    "GenAI.mil,  an  artificial  intelligence platform  for  the  Department  of  Defense"
)


def captured_case() -> tuple[str, tuple[EventEntityLinguisticToken, ...]]:
    payload = json.loads((Path(__file__).parent / "fixtures" / "ipi" / f"{EVENT}.json").read_text())
    return payload["sentence_text"], tuple(
        EventEntityLinguisticToken.model_validate(token) for token in payload["tokens"]
    )


def select(text: str, tokens: tuple[EventEntityLinguisticToken, ...]):
    inventory = build_constituent_candidate_inventory(
        source_text=text,
        event_id=EVENT,
        tokens=tokens,
        event_expression_start=60,
        event_expression_end=69,
    )
    return select_source_grounded_constituents(
        event_id=EVENT,
        source_text=text,
        inventory=inventory,
        tokens=tokens,
        trigger_head_start=60,
        trigger_head_end=69,
    )


def completion(text: str, tokens: tuple[EventEntityLinguisticToken, ...]):
    return derive_object_content_completion(
        event_id=EVENT,
        source_text=text,
        tokens=tokens,
        selected_object_range=SourceRange(start=71, end=80, text="GenAI.mil"),
    )


def time(text: str, tokens: tuple[EventEntityLinguisticToken, ...]):
    return derive_trigger_time_qualifier(
        event_id=EVENT,
        source_text=text,
        tokens=tokens,
        trigger_head_start=60,
        trigger_head_end=69,
    )


def replace_token(
    tokens: tuple[EventEntityLinguisticToken, ...], token_id: str, **changes: object
) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        EventEntityLinguisticToken.model_validate({**token.model_dump(), **changes})
        if token.token_id == token_id
        else token
        for token in tokens
    )


def test_captured_title_and_core_object_selection() -> None:
    text, tokens = captured_case()
    selected = select(text, tokens)
    assert selected.status is SourceGroundedSelectionStatus.SELECTED
    roles = {r.role.value: r.conjuncts[0].canonical_boundary.text for r in selected.realized_roles}
    assert roles == {"subject": EXPECTED_SUBJECT, "object": "GenAI.mil"}


def test_captured_nominal_appositive_preserves_complete_description() -> None:
    text, tokens = captured_case()
    result = completion(text, tokens)
    assert result is not None
    assert result.selected_object_range.text == "GenAI.mil"
    assert result.completed_range == SourceRange(start=71, end=155, text=EXPECTED_OBJECT)


def test_exact_name_candidate_has_priority_over_valid_descriptive_title() -> None:
    from kotekomi_application.parser_constituent_candidate_generation import (
        ConstituentCandidateInventory,
        ParserConstituent,
        parser_constituent_id,
    )

    text, tokens = captured_case()
    inventory = build_constituent_candidate_inventory(
        source_text=text,
        event_id=EVENT,
        tokens=tokens,
        event_expression_start=60,
        event_expression_end=69,
    )
    name = ParserConstituent(
        constituent_id=parser_constituent_id(inventory.source_text_sha256, 45, 58),
        event_id=EVENT,
        source_text_sha256=inventory.source_text_sha256,
        constituent_range=SourceRange(start=45, end=58, text="Pete  Hegseth"),
        token_ids=("t8", "t9"),
    )
    expanded = ConstituentCandidateInventory(
        event_id=EVENT,
        source_text_sha256=inventory.source_text_sha256,
        constituents=tuple(
            sorted(
                (*inventory.constituents, name),
                key=lambda c: (c.constituent_range.start, c.constituent_range.end),
            )
        ),
    )
    selected = select_source_grounded_constituents(
        event_id=EVENT,
        source_text=text,
        inventory=expanded,
        tokens=tokens,
        trigger_head_start=60,
        trigger_head_end=69,
    )
    assert selected.status is SourceGroundedSelectionStatus.SELECTED
    subject = next(r for r in selected.realized_roles if r.role.value == "subject")
    assert subject.conjuncts[0].canonical_boundary == name.constituent_range
    label = subject.conjuncts[0].selected_label
    assert expanded.constituents[int(label[1:]) - 1] == name


def test_captured_month_year_preserves_exact_text_without_boundary_comma() -> None:
    text, tokens = captured_case()
    result = time(text, tokens)
    assert result is not None
    assert result.exact_range == SourceRange(start=0, end=18, text="In  December  2025")


@pytest.mark.parametrize(
    ("token_id", "changes"),
    [
        ("t7", {"dependency_relation": "conj"}),
        ("t7", {"dependency_relation": "acl:relcl", "part_of_speech": "VERB"}),
        ("t7", {"head_token_id": "t11"}),
        ("t7", {"dependency_relation": "nmod:desc", "head_token_id": "t8"}),
        ("t5", {"part_of_speech": "VERB"}),
    ],
)
def test_unsupported_title_retains_boundary_gap(token_id: str, changes: dict[str, object]) -> None:
    text, tokens = captured_case()
    selected = select(text, replace_token(tokens, token_id, **changes))
    assert selected.status is SourceGroundedSelectionStatus.BOUNDARY_GAP
    assert selected.boundary_gap is SourceGroundedBoundaryGap.UNSUPPORTED_RELATION


@pytest.mark.parametrize(
    ("token_id", "changes"),
    [
        ("t19", {"dependency_relation": "appos", "head_token_id": "t11"}),
        ("t19", {"dependency_relation": "conj"}),
        ("t19", {"dependency_relation": "acl:relcl", "part_of_speech": "VERB"}),
        ("t16", {"part_of_speech": "VERB"}),
        ("t14", {"head_token_id": "t10"}),
        ("t21", {"dependency_relation": "nmod", "head_token_id": "t16"}),
    ],
)
def test_unsupported_appositive_is_an_explicit_hold(
    token_id: str, changes: dict[str, object]
) -> None:
    text, tokens = captured_case()
    with pytest.raises(ObjectComplementUnsupported):
        completion(text, replace_token(tokens, token_id, **changes))


@pytest.mark.parametrize(
    ("token_id", "changes"),
    [
        ("t2", {"lemma": "headquarters"}),
        ("t3", {"part_of_speech": "NOUN"}),
        ("t3", {"head_token_id": "t1"}),
        ("t4", {"dependency_relation": "amod", "head_token_id": "t3"}),
    ],
)
def test_unmarked_year_requires_month_context(token_id: str, changes: dict[str, object]) -> None:
    text, tokens = captured_case()
    with pytest.raises(TriggerTimeUnsupported):
        time(text, replace_token(tokens, token_id, **changes))


@pytest.mark.parametrize("operation", [select, completion, time])
def test_malformed_source_binding_fails_before_derivation(
    operation: Callable[[str, tuple[EventEntityLinguisticToken, ...]], object],
) -> None:
    text, tokens = captured_case()
    with pytest.raises(ValueError, match="source|Source"):
        operation(text, replace_token(tokens, "t19", text="X" * 10))
