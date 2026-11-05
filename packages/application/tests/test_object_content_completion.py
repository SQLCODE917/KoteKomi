"""Bounded object-complement completion on stored source and tokens.

The fixture carries the authoritative paragraph text and the pinned dependency
 tokens from the saved Anthropic-DoD ingestion run. No model call is involved.
"""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false, reportArgumentType=false

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    AssertionConstructionInputs,
    DecontextualizationEntityRef,
    EventEntityLinguisticToken,
    EventEntityReferences,
    ReferenceResolution,
    build_constituent_candidate_inventory,
    compose_event_from_resolution,
)
from kotekomi_application.decontextualization_composition import (
    ObjectContentCompletion,
    derive_object_content_completion,
)
from kotekomi_domain import AssertionType, AttributionBasis, SourceAuthority

EXPECTED_PHRASE = (
    'a blog post rebuffing "inaccurate claims" '
    "from the Trump administration on Anthropic's policies"
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "ira"
    / "blog_post_case.json"
)


def _case() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _tokens(case: dict[str, object]) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        EventEntityLinguisticToken.model_validate(item)
        for item in case["tokens"]  # type: ignore[index]
    )


def _selection(case: dict[str, object]):
    from kotekomi_application.source_grounded_selection import (
        select_source_grounded_constituents,
    )

    tokens = _tokens(case)
    source_text = str(case["source_text"])
    event_id = str(case["event_id"])
    inventory = build_constituent_candidate_inventory(
        source_text=source_text,
        event_id=event_id,
        tokens=tokens,
        event_expression_start=int(case["trigger_start"]),  # type: ignore[arg-type]
        event_expression_end=int(case["trigger_end"]),  # type: ignore[arg-type]
    )
    return inventory, select_source_grounded_constituents(
        event_id=event_id,
        source_text=source_text,
        inventory=inventory,
        trigger_head_start=int(case["trigger_start"]),  # type: ignore[arg-type]
        trigger_head_end=int(case["trigger_end"]),  # type: ignore[arg-type]
        tokens=tokens,
    )


SIMPLE_TEXT = "Amodei published a post praising fraud"


def _simple_tokens():
    """One coherent sentence: Amodei published a post praising fraud."""
    from kotekomi_application import EventEntityLinguisticToken

    def token(token_id, text, start, end, pos, relation, head):
        return EventEntityLinguisticToken(
            token_id=token_id,
            sentence_id="s1",
            text=text,
            start=start,
            end=end,
            lemma=text.casefold(),
            part_of_speech=pos,
            dependency_relation=relation,
            head_token_id=head,
        )

    return (
        token("t1", "Amodei", 0, 6, "PROPN", "nsubj", "t2"),
        token("t2", "published", 7, 16, "VERB", "root", None),
        token("t3", "a", 17, 18, "DET", "det", "t4"),
        token("t4", "post", 19, 23, "NOUN", "obj", "t2"),
        token("t5", "praising", 24, 32, "VERB", "acl", "t4"),
        token("t6", "fraud", 33, 38, "NOUN", "obj", "t5"),
    )


def test_participial_complement_completes_the_object() -> None:
    """A simple complement completes the phrase source-exactly."""
    from kotekomi_application import SourceRange
    from kotekomi_application.decontextualization_composition import (
        derive_object_content_completion,
    )

    completion = derive_object_content_completion(
        event_id="sge_simple_complement",
        source_text=SIMPLE_TEXT,
        tokens=_simple_tokens(),
        selected_object_range=SourceRange(start=17, end=23, text="a post"),
    )

    assert completion is not None
    assert completion.completed_range.text == "a post praising fraud"


def test_blog_post_complement_is_unsupported_because_it_governs_a_clause() -> None:
    """The stored blog-post complement governs an advcl, so it is held, not truncated."""
    from kotekomi_application.decontextualization_composition import (
        ObjectComplementUnsupported,
    )

    case = _case()
    _, selection = _selection(case)
    object_role = next(role for role in selection.realized_roles if role.role.value == "object")

    with pytest.raises(ObjectComplementUnsupported):
        derive_object_content_completion(
            event_id=str(case["event_id"]),
            source_text=str(case["source_text"]),
            tokens=_tokens(case),
            selected_object_range=object_role.conjuncts[0].canonical_boundary,
        )


def test_coordinated_complement_is_unsupported() -> None:
    """A complement that governs coordination is an explicit unsupported outcome."""
    from kotekomi_application import EventEntityLinguisticToken, SourceRange
    from kotekomi_application.decontextualization_composition import (
        ObjectComplementUnsupported,
    )

    text = "a post praising fraud and hiding losses"
    tokens = (
        EventEntityLinguisticToken(
            token_id="t1",
            sentence_id="s1",
            text="a",
            start=0,
            end=1,
            lemma="a",
            part_of_speech="DET",
            dependency_relation="det",
            head_token_id="t2",
        ),
        EventEntityLinguisticToken(
            token_id="t2",
            sentence_id="s1",
            text="post",
            start=2,
            end=6,
            lemma="post",
            part_of_speech="NOUN",
            dependency_relation="obj",
            head_token_id="t9",
        ),
        EventEntityLinguisticToken(
            token_id="t3",
            sentence_id="s1",
            text="praising",
            start=7,
            end=15,
            lemma="praise",
            part_of_speech="VERB",
            dependency_relation="acl",
            head_token_id="t2",
        ),
        EventEntityLinguisticToken(
            token_id="t4",
            sentence_id="s1",
            text="fraud",
            start=16,
            end=21,
            lemma="fraud",
            part_of_speech="NOUN",
            dependency_relation="obj",
            head_token_id="t3",
        ),
        EventEntityLinguisticToken(
            token_id="t5",
            sentence_id="s1",
            text="and",
            start=22,
            end=25,
            lemma="and",
            part_of_speech="CCONJ",
            dependency_relation="cc",
            head_token_id="t6",
        ),
        EventEntityLinguisticToken(
            token_id="t6",
            sentence_id="s1",
            text="hiding",
            start=26,
            end=32,
            lemma="hide",
            part_of_speech="VERB",
            dependency_relation="conj",
            head_token_id="t3",
        ),
        EventEntityLinguisticToken(
            token_id="t7",
            sentence_id="s1",
            text="losses",
            start=33,
            end=39,
            lemma="loss",
            part_of_speech="NOUN",
            dependency_relation="obj",
            head_token_id="t6",
        ),
        EventEntityLinguisticToken(
            token_id="t8",
            sentence_id="s1",
            text="published",
            start=40,
            end=49,
            lemma="publish",
            part_of_speech="VERB",
            dependency_relation="root",
            head_token_id=None,
        ),
        EventEntityLinguisticToken(
            token_id="t9",
            sentence_id="s1",
            text="published",
            start=40,
            end=49,
            lemma="publish",
            part_of_speech="VERB",
            dependency_relation="root",
            head_token_id=None,
        ),
    )

    with pytest.raises(ObjectComplementUnsupported):
        derive_object_content_completion(
            event_id="sge_complement_case",
            source_text=text,
            tokens=tokens,
            selected_object_range=SourceRange(start=0, end=6, text="a post"),
        )


def _compose_from(*, text, tokens, trigger, subject, completion, event_id, digest):
    """Compose one Event from an explicit source, token graph, and completion."""
    from kotekomi_application import (
        SourceRange,
        build_constituent_candidate_inventory,
    )

    inventory = build_constituent_candidate_inventory(
        source_text=text,
        event_id=event_id,
        tokens=tokens,
        event_expression_start=trigger[0],
        event_expression_end=trigger[1],
    )
    entity = "org_complement_probe"
    resolution = ReferenceResolution(
        references=EventEntityReferences(
            entities=(
                DecontextualizationEntityRef(
                    entity_id=entity,
                    entity_kind="organization",
                    canonical_name="probe",
                    accepted_source_occurrences=(
                        SourceRange(
                            start=subject[0],
                            end=subject[1],
                            text=text[subject[0] : subject[1]],
                        ),
                    ),
                ),
            ),
            subject_value_authorizations=(),
        ),
        diagnostics=(),
    )
    inputs = AssertionConstructionInputs(
        predicate_by_label={"published": "published"},
        identity_by_entity={entity: entity},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_complement_probe",
        evidence_target_id="etg_complement_probe",
        constructed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return compose_event_from_resolution(
        event_id=event_id,
        source_text=text,
        source_text_sha256=digest,
        inventory=inventory,
        trigger_head_start=trigger[0],
        trigger_head_end=trigger[1],
        tokens=tokens,
        resolution=resolution,
        assertion_inputs=inputs,
        object_completion=completion,
    )


def _simple_compose(completion):
    import hashlib

    return _compose_from(
        text=SIMPLE_TEXT,
        tokens=_simple_tokens(),
        trigger=(7, 16),
        subject=(0, 6),
        completion=completion,
        event_id="sge_simple_complement",
        digest=hashlib.sha256(SIMPLE_TEXT.encode()).hexdigest(),
    )


def test_missing_completion_holds_instead_of_truncating() -> None:
    """A required completion that the caller omits produces an explicit hold."""
    record = _simple_compose(None)

    assert record.status.value == "held"
    assert record.hold_reason == "object_complement_required"
    assert record.assertion is None


def test_supplied_completion_reaches_the_assertion() -> None:
    """The validated completion becomes the Assertion object value."""
    from kotekomi_application import SourceRange
    from kotekomi_application.decontextualization_composition import (
        derive_object_content_completion,
    )

    completion = derive_object_content_completion(
        event_id="sge_simple_complement",
        source_text=SIMPLE_TEXT,
        tokens=_simple_tokens(),
        selected_object_range=SourceRange(start=17, end=23, text="a post"),
    )
    record = _simple_compose(completion)

    assert record.status.value == "composed"
    assert record.assertion is not None
    assert record.assertion.object_value == "a post praising fraud"


def test_invented_completion_text_is_rejected() -> None:
    """A shape-valid but source-false completion cannot reach the Assertion."""
    from kotekomi_application import SourceRange

    invented = ObjectContentCompletion(
        event_id="sge_simple_complement",
        selected_object_range=SourceRange(start=17, end=23, text="a post"),
        completed_range=SourceRange(start=17, end=38, text="X" * 21),
    )

    with pytest.raises(ValueError, match="permitted derivation"):
        _simple_compose(invented)


def test_unsupported_complement_holds_even_without_a_supplied_completion() -> None:
    """Omitting the completion cannot bypass a required-but-unsupported complement."""
    import hashlib

    case = _case()
    record = _compose_from(
        text=str(case["source_text"]),
        tokens=_tokens(case),
        trigger=(int(case["trigger_start"]), int(case["trigger_end"])),
        subject=(int(case["subject_start"]), int(case["subject_end"])),
        completion=None,
        event_id=str(case["event_id"]),
        digest=str(case["source_text_sha256"]),
    )

    assert record.status.value == "held"
    assert record.hold_reason == "unsupported_object_complement"
    assert record.assertion is None
    assert hashlib.sha256(str(case["source_text"]).encode()).hexdigest()
