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


@pytest.mark.parametrize("load_json", [False, True])
def test_whitespace_only_qualifier_is_invalid(load_json: bool) -> None:
    from kotekomi_application.source_ranges import SourceRange
    from kotekomi_application.trigger_time_qualifier import TriggerTimeQualifier
    from pydantic import ValidationError

    payload = {"event_id": "sge_test", "exact_range": {"start": 0, "end": 2, "text": "  "}}
    with pytest.raises(ValidationError, match="requires text"):
        if load_json:
            TriggerTimeQualifier.model_validate_json(json.dumps(payload))
        else:
            TriggerTimeQualifier(
                event_id="sge_test", exact_range=SourceRange(start=0, end=2, text="  ")
            )


@pytest.mark.parametrize("mutation", ["bounds", "text", "trigger"])
def test_invalid_source_binding_fails_explicitly(mutation: str) -> None:
    text, tokens, start, end = _fixture("sge_c0ff4b58ad8962717514c9f3")
    if mutation == "bounds":
        tokens = (
            *tokens[:-1],
            EventEntityLinguisticToken.model_validate(
                {**tokens[-1].model_dump(), "start": len(text) + 1, "end": len(text) + 2}
            ),
        )
    elif mutation == "text":
        tokens = (
            EventEntityLinguisticToken.model_validate(
                {**tokens[0].model_dump(), "text": "X" * len(tokens[0].text)}
            ),
            *tokens[1:],
        )
    else:
        start, end = -1, 0
    with pytest.raises(ValueError, match="source") as failure:
        derive_trigger_time_qualifier(
            event_id="sge_c0ff4b58ad8962717514c9f3",
            source_text=text,
            tokens=tokens,
            trigger_head_start=start,
            trigger_head_end=end,
        )
    assert not isinstance(failure.value, TriggerTimeUnsupported)


def _synthetic_time(
    source: str, specs: tuple[tuple[str, str, str | None], ...]
) -> tuple[EventEntityLinguisticToken, ...]:
    tokens: list[EventEntityLinguisticToken] = []
    cursor = 0
    for i, (word, relation, head) in enumerate(specs, 1):
        start = source.index(word, cursor)
        cursor = start + len(word)
        tokens.append(
            EventEntityLinguisticToken(
                token_id=f"t{i}",
                sentence_id="s1",
                text=word,
                start=start,
                end=cursor,
                lemma=word.casefold(),
                part_of_speech="NUM" if word.isdigit() else "NOUN",
                dependency_relation=relation,
                head_token_id=head,
            )
        )
    return tuple(tokens)


@pytest.mark.parametrize(
    ("source", "specs", "expected"),
    [
        (
            "met in  2012.",
            (
                ("met", "root", None),
                ("in", "case", "t3"),
                ("2012", "obl", "t1"),
                (".", "punct", "t3"),
            ),
            "in  2012",
        ),
        (
            "met Prior to the dispute,",
            (
                ("met", "root", None),
                ("Prior", "case", "t5"),
                ("to", "fixed", "t2"),
                ("the", "det", "t5"),
                ("dispute", "obl", "t1"),
                (",", "punct", "t5"),
            ),
            "Prior to the dispute",
        ),
    ],
)
def test_supported_time_keeps_characters_and_excludes_trailing_punctuation(
    source: str, specs: tuple[tuple[str, str, str | None], ...], expected: str
) -> None:
    tokens = _synthetic_time(source, specs)
    result = derive_trigger_time_qualifier(
        event_id="sge_time",
        source_text=source,
        tokens=tokens,
        trigger_head_start=0,
        trigger_head_end=3,
    )
    assert result is not None
    assert result.exact_range.text == expected
    assert source[result.exact_range.start : result.exact_range.end] == expected


@pytest.mark.parametrize(
    ("source", "specs", "reason"),
    [
        (
            "met in 2012 and 2013",
            (
                ("met", "root", None),
                ("in", "case", "t3"),
                ("2012", "obl", "t1"),
                ("and", "cc", "t5"),
                ("2013", "conj", "t3"),
            ),
            "cannot represent",
        ),
        (
            "met after they left",
            (
                ("met", "root", None),
                ("after", "case", "t4"),
                ("they", "nsubj", "t4"),
                ("left", "obl", "t1"),
            ),
            "cannot represent",
        ),
        (
            "met in 2012 at noon",
            (
                ("met", "root", None),
                ("in", "case", "t3"),
                ("2012", "obl", "t1"),
                ("at", "case", "t5"),
                ("noon", "obl", "t1"),
            ),
            "more than one oblique",
        ),
    ],
)
def test_unsupported_obliques_remain_held(
    source: str, specs: tuple[tuple[str, str, str | None], ...], reason: str
) -> None:
    with pytest.raises(TriggerTimeUnsupported, match=reason):
        derive_trigger_time_qualifier(
            event_id="sge_time",
            source_text=source,
            tokens=_synthetic_time(source, specs),
            trigger_head_start=0,
            trigger_head_end=3,
        )


def test_packet_time_bindings_require_complete_fields_and_statement_coverage() -> None:
    import hashlib
    from dataclasses import replace

    from kotekomi_application.event_construction_review import (
        EventConstructionReviewError,
        EventReviewPacket,
        validate_packet_bindings,
    )

    text = "met in 2012"
    digest = hashlib.sha256(text.encode()).hexdigest()
    packet = EventReviewPacket(
        ingestion_run_id="igr_fixture",
        event_id="sge_fixture",
        paragraph_node_id="nod_fixture",
        representation_id="rep_fixture",
        text_view_id="tvw_fixture",
        text_view_digest=digest,
        source_text_sha256=digest,
        source_id="src_fixture",
        document_id="doc_fixture",
        node_start_char=0,
        source_text=text,
        trigger_start=0,
        trigger_end=3,
        relation_label="meet",
        subject_start=None,
        subject_end=None,
        subject_text=None,
        object_start=None,
        object_end=None,
        object_text=None,
        statement_start=0,
        statement_end=len(text),
        candidates=(),
        accepted_identity_ids=(),
        required_decisions=(),
        hold_reason=None,
        existing_review_id=None,
        evidence_target_id=None,
        time_qualifier_start=4,
        time_qualifier_end=11,
        time_qualifier_text="in 2012",
    )
    validate_packet_bindings(packet)
    for invalid in (
        replace(packet, time_qualifier_start=None),
        replace(packet, time_qualifier_end=None),
        replace(packet, time_qualifier_text=None),
    ):
        with pytest.raises(EventConstructionReviewError, match="both coordinates and its text"):
            validate_packet_bindings(invalid)
    with pytest.raises(EventConstructionReviewError, match="must cover the time qualifier"):
        validate_packet_bindings(replace(packet, statement_end=3))
    with pytest.raises(EventConstructionReviewError, match="does not match the source text"):
        validate_packet_bindings(replace(packet, time_qualifier_text="in 2013"))
    with pytest.raises(EventConstructionReviewError, match="non-whitespace text"):
        validate_packet_bindings(replace(packet, time_qualifier_text=" " * 7))
