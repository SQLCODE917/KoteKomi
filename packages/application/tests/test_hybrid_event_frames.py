from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
from kotekomi_application.hybrid_event_frames import (
    EventModality,
    EventPolarity,
    HybridEventFrameStatus,
    build_hybrid_event_frame_preview,
    canonical_hybrid_event_frame_preview_bytes,
    hybrid_event_frame_preview_from_bytes,
)
from kotekomi_application.hybrid_event_model_output import (
    EventFrameAbstention,
    EventFrameProposal,
    EventTriggerAbstention,
    EventTriggerProposalBatch,
    parse_event_frame_output,
    parse_event_trigger_output,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEVELOPMENT_CATALOG = REPOSITORY_ROOT / "docs" / "hp4-event-frame-development-v1.json"


def test_trigger_contract_preserves_multiple_source_literal_events() -> None:
    result = parse_event_trigger_output(
        b"event: e1 | s1 | established | policy_establishment\n"
        b"event: e2 | s1 | intensified | effort_intensification\n"
    )

    assert isinstance(result, EventTriggerProposalBatch)
    assert [
        (item.event_label, item.trigger_text, item.event_type_label) for item in result.proposals
    ] == [
        ("e1", "established", "policy_establishment"),
        ("e2", "intensified", "effort_intensification"),
    ]


def test_trigger_contract_preserves_explicit_empty_result() -> None:
    result = parse_event_trigger_output(b"abstain: no explicit event in the target segment\n")

    assert result == EventTriggerAbstention("no explicit event in the target segment")


@pytest.mark.parametrize(
    "payload",
    [
        b"event: e2 | s1 | established | policy_establishment\n",
        b"event: e1 | s1 | established | Too Broad\n",
        b"event: e1 | s1 | established\n",
        b"event: e1 | s1 | established | policy_establishment\n"
        b"event: e1 | s1 | intensified | effort_intensification\n",
    ],
)
def test_trigger_contract_rejects_invalid_structure(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_trigger_output(payload)


def test_frame_contract_preserves_roles_qualifiers_and_attribution() -> None:
    result = parse_event_frame_output(
        b"event: e1\n"
        b"polarity: affirmed\n"
        b"modality: actual\n"
        b"attribution: c3\n"
        b"argument: c1 | policy_establisher | s1\n"
        b"argument: c2 | established_policy | s1\n"
        b"qualifier: time | s1 | 2012\n"
        b"qualifier: place | s2 | United States\n"
    )

    assert isinstance(result, EventFrameProposal)
    assert result.polarity is EventPolarity.AFFIRMED
    assert result.modality is EventModality.ACTUAL
    assert result.attribution_candidate_labels == ("c3",)
    assert [item.role_label for item in result.arguments] == [
        "policy_establisher",
        "established_policy",
    ]
    assert [(item.kind.value, item.literal_text) for item in result.qualifiers] == [
        ("time", "2012"),
        ("place", "United States"),
    ]


@pytest.mark.parametrize("modality", list(EventModality))
def test_frame_contract_accepts_each_modality(modality: EventModality) -> None:
    result = parse_event_frame_output(
        (
            "event: e1\n"
            "polarity: negated\n"
            f"modality: {modality.value}\n"
            "attribution: source_narrator\n"
        ).encode()
    )

    assert isinstance(result, EventFrameProposal)
    assert result.modality is modality
    assert result.source_narrator_attribution is True


def test_frame_contract_preserves_explicit_abstention() -> None:
    result = parse_event_frame_output(b"abstain: source does not assign participants\n")

    assert result == EventFrameAbstention("source does not assign participants")


def test_frame_contract_treats_empty_separator_lines_as_insignificant() -> None:
    result = parse_event_frame_output(
        b"event: e1\n"
        b"polarity: affirmed\n"
        b"modality: actual\n"
        b"attribution: source_narrator\n"
        b"\n"
        b"argument: c1 | actor | s1\n"
        b"\n"
        b"qualifier: time | s1 | 2012\n"
    )

    assert isinstance(result, EventFrameProposal)
    assert result.arguments[0].candidate_label == "c1"
    assert result.qualifiers[0].literal_text == "2012"


@pytest.mark.parametrize(
    "payload",
    [
        b"event: e1\npolarity: asserted\nmodality: actual\nattribution: source_narrator\n",
        b"event: e1\npolarity: affirmed\nmodality: factual\nattribution: source_narrator\n",
        b"event: e1\npolarity: affirmed\nmodality: actual\nattribution: c9,c9\n",
        b"event: e1\npolarity: affirmed\nmodality: actual\nattribution: source_narrator\n"
        b"qualifier: time | s1 | 2012\nargument: c1 | actor | s1\n",
        b"event: e1\npolarity: affirmed\nmodality: actual\nattribution: source_narrator\n"
        b"argument: c1 | Policy Actor | s1\n",
    ],
)
def test_frame_contract_rejects_unknown_or_conflicting_values(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_frame_output(payload)


def test_empty_complete_preview_uses_canonical_content_identity() -> None:
    preview = build_hybrid_event_frame_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        trigger_context_manifest_id="ctx_trigger",
        frame_context_manifest_id="ctx_frame",
        terminal_status=HybridEventFrameStatus.COMPLETE,
    )

    payload = canonical_hybrid_event_frame_preview_bytes(preview)

    assert hybrid_event_frame_preview_from_bytes(payload) == preview
    assert preview.id.startswith("hep_")
    assert hashlib.sha256(payload).hexdigest()


def test_blocked_preview_requires_visible_diagnostic() -> None:
    with pytest.raises(ValueError, match="requires a diagnostic"):
        build_hybrid_event_frame_preview(
            parent_preview_id="hgp_" + "1" * 24,
            parent_preview_sha256="a" * 64,
            reference_preview_id="hrp_" + "2" * 24,
            reference_preview_sha256="b" * 64,
            mention_preview_id="hxp_" + "3" * 24,
            mention_preview_sha256="c" * 64,
            representation_id="rep_fixture",
            paragraph_node_id="nod_fixture",
            trigger_context_manifest_id="ctx_trigger",
            frame_context_manifest_id="ctx_frame",
            terminal_status=HybridEventFrameStatus.BLOCKED,
        )


def test_hp4_development_catalog_binds_twelve_distinct_reviewed_paragraphs() -> None:
    catalog = _object(json.loads(DEVELOPMENT_CATALOG.read_text(encoding="utf-8")))
    cases = [_object(item) for item in _list(catalog, "cases")]

    assert _string(catalog, "schema_version") == "hp4_event_frame_development_v1"
    assert _string(catalog, "policy_id") == "hybrid_event_frame_v1"
    assert _string(catalog, "annotation_status") == "reviewed_semantic_expectations"
    assert len(cases) == 12
    assert len({_string(item, "case_id") for item in cases}) == 12
    assert len({_string(item, "paragraph_anchor") for item in cases}) == 12
    assert all(_string(item, "expected_semantic_work") for item in cases)


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
