"""Bounded object-complement completion on stored source and tokens.

The fixture carries the authoritative paragraph text and the pinned dependency
 tokens from the saved Anthropic-DoD ingestion run. No model call is involved.
"""

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


def _normalized(value: str) -> str:
    """Compare meaning while the archive keeps its own whitespace."""
    return " ".join(value.split())


def _case() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _tokens(case: dict[str, object]) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        EventEntityLinguisticToken.model_validate(item)
        for item in case["tokens"]  # type: ignore[index]
    )


def _compose(case: dict[str, object], completion: ObjectContentCompletion | None):
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
    subject_start = int(case["subject_start"])  # type: ignore[arg-type]
    subject_end = int(case["subject_end"])  # type: ignore[arg-type]
    entity_id = "org_object_completion_probe"
    resolution = ReferenceResolution(
        references=EventEntityReferences(
            entities=(
                DecontextualizationEntityRef(
                    entity_id=entity_id,
                    entity_kind="organization",
                    canonical_name="probe",
                    accepted_source_occurrences=(
                        __import__("kotekomi_application").SourceRange(
                            start=subject_start,
                            end=subject_end,
                            text=source_text[subject_start:subject_end],
                        ),
                    ),
                ),
            ),
            subject_value_authorizations=(),
        ),
        diagnostics=(),
    )
    inputs = AssertionConstructionInputs(
        predicate_by_label={str(case["trigger_label"]): "published"},
        identity_by_entity={entity_id: entity_id},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_object_completion",
        evidence_target_id="etg_object_completion",
        constructed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return compose_event_from_resolution(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=str(case["source_text_sha256"]),
        inventory=inventory,
        trigger_head_start=int(case["trigger_start"]),  # type: ignore[arg-type]
        trigger_head_end=int(case["trigger_end"]),  # type: ignore[arg-type]
        tokens=tokens,
        resolution=resolution,
        assertion_inputs=inputs,
        object_completion=completion,
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


def test_completion_derives_the_participial_object_phrase() -> None:
    """The derived completion starts at the selected phrase and covers the acl."""
    case = _case()
    inventory, selection = _selection(case)
    object_role = next(role for role in selection.realized_roles if role.role.value == "object")
    selected = object_role.conjuncts[0].canonical_boundary

    completion = derive_object_content_completion(
        event_id=str(case["event_id"]),
        source_text=str(case["source_text"]),
        tokens=_tokens(case),
        selected_object_range=selected,
    )

    assert completion is not None
    assert completion.selected_object_range == selected
    assert completion.completed_range.start == selected.start
    assert _normalized(completion.completed_range.text) == EXPECTED_PHRASE


def test_completed_object_phrase_reaches_the_proposition() -> None:
    """The completed phrase replaces only the object content."""
    case = _case()
    _, selection = _selection(case)
    object_role = next(role for role in selection.realized_roles if role.role.value == "object")
    completion = derive_object_content_completion(
        event_id=str(case["event_id"]),
        source_text=str(case["source_text"]),
        tokens=_tokens(case),
        selected_object_range=object_role.conjuncts[0].canonical_boundary,
    )

    record = _compose(case, completion)

    assert record.status.value == "composed"
    assert record.object_text is not None
    assert _normalized(record.object_text) == EXPECTED_PHRASE
    assert record.subject_text == "Amodei"
    assert record.assertion is not None
    assert isinstance(record.assertion.object_value, str)
    assert _normalized(record.assertion.object_value) == EXPECTED_PHRASE


def test_complement_completion_is_required_once_derived() -> None:
    """A completion that does not match the selection is rejected."""
    case = _case()
    _, selection = _selection(case)
    object_role = next(role for role in selection.realized_roles if role.role.value == "object")
    completion = derive_object_content_completion(
        event_id=str(case["event_id"]),
        source_text=str(case["source_text"]),
        tokens=_tokens(case),
        selected_object_range=object_role.conjuncts[0].canonical_boundary,
    )
    assert completion is not None

    with pytest.raises(ValueError):
        _compose(
            case,
            completion.model_copy(
                update={
                    "completed_range": completion.completed_range.model_copy(
                        update={"end": completion.completed_range.end + 5}
                    )
                }
            ),
        )
