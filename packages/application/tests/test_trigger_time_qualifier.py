"""IPI-04 captured-parse tests for the trigger time qualifier.

Positive and negative cases use real Stanza tokens captured from the stored IRA
acceptance run, sliced to the trigger's sentence with offsets re-based.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.trigger_time_qualifier import (
    TriggerTimeUnsupported,
    derive_trigger_time_qualifier,
)

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


def _derive(event_id: str):
    text, tokens, start, end = _fixture(event_id)
    return derive_trigger_time_qualifier(
        event_id=event_id,
        source_text=text,
        tokens=tokens,
        trigger_head_start=start,
        trigger_head_end=end,
    )


def test_year_adjunct_becomes_a_time_qualifier() -> None:
    """`in  2012` on `established` is one exact time expression."""
    qualifier = _derive("sge_c0ff4b58ad8962717514c9f3")
    assert qualifier is not None
    assert qualifier.exact_range.text == "in  2012"


def test_place_adjunct_stays_unsupported() -> None:
    """`in The New York Times` carries no temporal evidence."""
    with pytest.raises(TriggerTimeUnsupported):
        _derive("sge_9210fac53e77650e874eba68")


def test_instrumental_adjunct_stays_unsupported() -> None:
    """`with the firms ...` carries coordination and no time meaning."""
    with pytest.raises(TriggerTimeUnsupported):
        _derive("sge_1569c3a9d96f8f9c1ccf8495")


def test_event_without_a_plain_oblique_has_no_qualifier() -> None:
    """`That month` is parsed as `obl:unmarked`, which this rule leaves alone."""
    assert _derive("sge_e8d444a0222b3344ab28d1d8") is None
