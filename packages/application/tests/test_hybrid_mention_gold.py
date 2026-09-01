from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from kotekomi_application import ContextualKind, DiscourseRole, Referentiality

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GOLD_PATH = REPOSITORY_ROOT / "docs" / "hp1-contextual-mention-gold-v1.json"
ONTOLOGY_CARD_PATH = REPOSITORY_ROOT / "prompts" / "hybrid_mention_ontology_card_v1.md"


def test_hp1_gold_binds_exact_source_characters_and_complete_labels() -> None:
    gold = _object(json.loads(GOLD_PATH.read_text(encoding="utf-8")))
    fixture_path = REPOSITORY_ROOT / _string(gold, "source_fixture_path")
    fixture_bytes = fixture_path.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == _string(gold, "source_fixture_sha256")
    fixture = _object(json.loads(fixture_bytes))
    paragraphs = {
        _string(item, "case_id"): item
        for item in (_object(value) for value in _list(fixture, "paragraphs"))
    }
    referentiality: set[Referentiality] = set()
    contextual_kinds: set[ContextualKind] = set()
    discourse_roles: set[DiscourseRole] = set()
    for raw_case in _list(gold, "cases"):
        case = _object(raw_case)
        case_id = _string(case, "case_id")
        paragraph = paragraphs[case_id]
        assert _string(case, "representation_id") == _string(paragraph, "representation_id")
        assert _string(case, "paragraph_node_id") == _string(paragraph, "paragraph_node_id")
        source_text = _string(paragraph, "text")
        assert hashlib.sha256(source_text.encode()).hexdigest() == _string(
            case, "source_text_sha256"
        )
        candidate = _object(case["candidate"])
        start = _integer(candidate, "start")
        end = _integer(candidate, "end")
        assert source_text[start:end] == _string(candidate, "text")
        hints = tuple(_strings(case, "proposal_type_hints"))
        assert hints == tuple(sorted(set(hints)))
        assert all(
            ContextualKind(value) not in {ContextualKind.OTHER, ContextualKind.UNCLEAR}
            for value in hints
        )
        expected = _object(case["expected"])
        referentiality.add(Referentiality(_string(expected, "referentiality")))
        contextual_kinds.add(ContextualKind(_string(expected, "contextual_kind")))
        discourse_roles.add(DiscourseRole(_string(expected, "discourse_role")))
        assert _string(case, "reviewer_notes")

    assert referentiality == set(Referentiality)
    assert {
        ContextualKind.ORGANIZATION,
        ContextualKind.GOVERNMENT,
        ContextualKind.PLACE,
        ContextualKind.PROJECT,
        ContextualKind.INITIATIVE,
        ContextualKind.PRODUCT,
        ContextualKind.UNCLEAR,
    }.issubset(contextual_kinds)
    assert {
        DiscourseRole.ACTOR,
        DiscourseRole.ORIGIN,
        DiscourseRole.LOCATION,
        DiscourseRole.OBJECT,
        DiscourseRole.MODIFIER,
    }.issubset(discourse_roles)


def test_hp1_ontology_card_defines_positive_and_negative_examples_for_every_label() -> None:
    lines = ONTOLOGY_CARD_PATH.read_text(encoding="utf-8").splitlines()
    for label in Referentiality:
        _assert_example_line(lines, f"Referentiality `{label.value}`")
    for label in ContextualKind:
        _assert_example_line(lines, f"Contextual kind `{label.value}`")
    for label in DiscourseRole:
        _assert_example_line(lines, f"Discourse role `{label.value}`")


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _list(value: dict[str, object], key: str) -> list[object]:
    result = value[key]
    assert isinstance(result, list)
    return cast(list[object], result)


def _string(value: dict[str, object], key: str) -> str:
    result = value[key]
    assert isinstance(result, str)
    return result


def _strings(value: dict[str, object], key: str) -> list[str]:
    result = _list(value, key)
    assert all(isinstance(item, str) for item in result)
    return cast(list[str], result)


def _integer(value: dict[str, object], key: str) -> int:
    result = value[key]
    assert type(result) is int
    return result


def _assert_example_line(lines: list[str], prefix: str) -> None:
    matching = [line for line in lines if line.startswith(prefix)]
    assert len(matching) == 1
    assert "; do not use" in matching[0]
