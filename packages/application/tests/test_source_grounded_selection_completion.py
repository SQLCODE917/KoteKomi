"""IPI-03 captured-parse tests for noun-phrase boundary completion.

The positive cases use real Stanza tokens captured from the stored IRA acceptance
run, sliced to the trigger's sentence with offsets re-based. The negative cases
construct token sets beside those captures to pin the rejected shapes.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ParserConstituent,
    build_constituent_candidate_inventory,
)
from kotekomi_application.source_grounded_selection import (
    SourceGroundedSelectionResult,
    SourceGroundedSelectionStatus,
    _completion_is_permitted,
    select_source_grounded_constituents,
)
from kotekomi_application.source_ranges import SourceRange

FIXTURES = Path(__file__).parent / "fixtures" / "ipi"


def _fixture(event_id: str) -> tuple[str, tuple[EventEntityLinguisticToken, ...], int, int]:
    payload = json.loads((FIXTURES / f"{event_id}.json").read_text(encoding="utf-8"))
    tokens = tuple(
        EventEntityLinguisticToken(
            token_id=row["token_id"],
            sentence_id=row["sentence_id"],
            text=row["text"],
            start=row["start"],
            end=row["end"],
            lemma=row["lemma"],
            part_of_speech=row["part_of_speech"],
            dependency_relation=row["dependency_relation"],
            head_token_id=row["head_token_id"],
        )
        for row in payload["tokens"]
    )
    return payload["sentence_text"], tokens, payload["trigger_start"], payload["trigger_end"]


def _select(event_id: str) -> SourceGroundedSelectionResult:
    text, tokens, trigger_start, trigger_end = _fixture(event_id)
    inventory = build_constituent_candidate_inventory(
        source_text=text,
        event_id=event_id,
        tokens=tokens,
        event_expression_start=trigger_start,
        event_expression_end=trigger_end,
    )
    return select_source_grounded_constituents(
        event_id=event_id,
        source_text=text,
        inventory=inventory,
        trigger_head_start=trigger_start,
        trigger_head_end=trigger_end,
        tokens=tokens,
    )


def _role_text(result: SourceGroundedSelectionResult, role: str) -> str:
    for selection in result.realized_roles:
        if selection.role.value == role:
            return " ".join(conjunct.canonical_boundary.text for conjunct in selection.conjuncts)
    raise AssertionError(f"role {role} is not realized")


def test_department_of_defense_subject_selects_the_complete_name() -> None:
    """The captured parse stops at `Department`; the complete name is selected."""
    result = _select("sge_c0ff4b58ad8962717514c9f3")
    assert result.status is SourceGroundedSelectionStatus.SELECTED
    assert _role_text(result, "subject") == "The  Department  of  Defense"
    assert _role_text(result, "object") == "a  policy  on  the  use  of  artificial intelligence"


def test_criticized_object_selects_the_complete_prepositional_complement() -> None:
    """The object head `approach` gains its permitted `to ...` complement."""
    result = _select("sge_e8d444a0222b3344ab28d1d8")
    assert result.status is SourceGroundedSelectionStatus.SELECTED
    assert _role_text(result, "subject") == "Amodei"
    assert (
        _role_text(result, "object") == "Trump's approach to export restrictions on semiconductors"
    )


def test_wrote_object_selects_the_hyphenated_noun_phrase() -> None:
    """The tokenizer splits `op-ed`; the complete noun phrase is selected once."""
    result = _select("sge_9210fac53e77650e874eba68")
    assert result.status is SourceGroundedSelectionStatus.SELECTED
    assert _role_text(result, "object") == "an op-ed"


def test_conflicted_subject_selects_the_complete_name() -> None:
    """The lead sentence's subject gains its `of Defense` complement."""
    result = _select("sge_d0093ff082341fd88823576a")
    assert result.status is SourceGroundedSelectionStatus.SELECTED
    assert _role_text(result, "subject") == "the  United  States  Department  of  Defense"


def _token(
    token_id: str, text: str, start: int, relation: str, head: str | None
) -> EventEntityLinguisticToken:
    return EventEntityLinguisticToken(
        token_id=token_id,
        sentence_id="s1",
        text=text,
        start=start,
        end=start + len(text),
        lemma=text.casefold(),
        part_of_speech="PROPN" if text[:1].isupper() else "NOUN",
        dependency_relation=relation,
        head_token_id=head,
    )


def _candidate(tokens: tuple[EventEntityLinguisticToken, ...], start: int, end: int):
    selected = tuple(token for token in tokens if start <= token.start and token.end <= end)
    return cast(
        "ParserConstituent",
        SimpleNamespace(token_ids=tuple(token.token_id for token in selected)),
    )


def test_relative_clause_extra_is_not_a_permitted_completion() -> None:
    tokens = (
        _token("t1", "Department", 0, "nsubj", "t2"),
        _token("t2", "announced", 11, "root", None),
        _token("t3", "of", 22, "case", "t4"),
        _token("t4", "Defense", 25, "nmod", "t1"),
        _token("t5", "that", 33, "mark", "t6"),
        _token("t6", "met", 38, "acl:relcl", "t4"),
    )
    assert not _completion_is_permitted(
        candidate=_candidate(tokens, 0, 41),
        boundary=SourceRange(start=0, end=10, text="Department"),
        tokens_by_id={token.token_id: token for token in tokens},
    )


def test_appositive_extra_is_not_a_permitted_completion() -> None:
    tokens = (
        _token("t1", "Department", 0, "nsubj", "t3"),
        _token("t2", "agency", 17, "appos", "t1"),
        _token("t3", "met", 24, "root", None),
    )
    assert not _completion_is_permitted(
        candidate=_candidate(tokens, 0, 23),
        boundary=SourceRange(start=0, end=10, text="Department"),
        tokens_by_id={token.token_id: token for token in tokens},
    )


def test_coordinated_extra_is_not_a_permitted_completion() -> None:
    tokens = (
        _token("t1", "Department", 0, "nsubj", "t4"),
        _token("t2", "and", 11, "cc", "t3"),
        _token("t3", "Agency", 15, "conj", "t1"),
        _token("t4", "met", 22, "root", None),
    )
    assert not _completion_is_permitted(
        candidate=_candidate(tokens, 0, 21),
        boundary=SourceRange(start=0, end=10, text="Department"),
        tokens_by_id={token.token_id: token for token in tokens},
    )


def test_two_prepositional_complements_are_not_a_permitted_completion() -> None:
    tokens = (
        _token("t1", "Department", 0, "nsubj", "t6"),
        _token("t2", "of", 11, "case", "t3"),
        _token("t3", "Defense", 14, "nmod", "t1"),
        _token("t4", "of", 22, "case", "t5"),
        _token("t5", "State", 25, "nmod", "t1"),
        _token("t6", "met", 31, "root", None),
    )
    assert not _completion_is_permitted(
        candidate=_candidate(tokens, 0, 30),
        boundary=SourceRange(start=0, end=10, text="Department"),
        tokens_by_id={token.token_id: token for token in tokens},
    )


def test_a_candidate_without_extra_content_is_not_a_completion() -> None:
    tokens = (
        _token("t1", "Department", 0, "nsubj", "t2"),
        _token("t2", "met", 11, "root", None),
    )
    assert not _completion_is_permitted(
        candidate=_candidate(tokens, 0, 10),
        boundary=SourceRange(start=0, end=10, text="Department"),
        tokens_by_id={token.token_id: token for token in tokens},
    )
