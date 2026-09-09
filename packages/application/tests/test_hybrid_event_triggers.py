from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    HybridEventTriggerStatus,
    build_hybrid_event_trigger_preview,
    canonical_hybrid_event_trigger_preview_bytes,
    derive_source_copy_view,
    hybrid_event_trigger_preview_from_bytes,
)
from kotekomi_application.hybrid_event_trigger_model_output import (
    EventTriggerAbstention,
    EventTriggerProposal,
    EventTriggerProposalBatch,
    parse_event_trigger_output,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    select_non_overlapping_trigger_proposals,
    source_occurrences,
)


def test_trigger_contract_preserves_multiple_source_literal_events() -> None:
    result = parse_event_trigger_output(b"event: o2 | publication\nevent: o5 | characterization\n")

    assert isinstance(result, EventTriggerProposalBatch)
    assert [(item.occurrence_id, item.event_type_label) for item in result.proposals] == [
        ("o2", "publication"),
        ("o5", "characterization"),
    ]
    assert result.rejections == ()


def test_trigger_contract_preserves_explicit_empty_result() -> None:
    result = parse_event_trigger_output(b"abstain: no explicit event in the target segment\n")

    assert result == EventTriggerAbstention("no explicit event in the target segment")


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"abstain: \n",
    ],
)
def test_trigger_contract_rejects_invalid_structure(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_trigger_output(payload)


def test_trigger_contract_isolates_bad_lines_and_keeps_valid_occurrence_selections() -> None:
    result = parse_event_trigger_output(
        b"event: o2 | publication\nevent: o999 | Too Broad\nevent: o5 | characterization\n"
    )

    assert isinstance(result, EventTriggerProposalBatch)
    assert [item.occurrence_id for item in result.proposals] == ["o2", "o5"]
    assert [(item.line_number, item.code) for item in result.rejections] == [
        (2, "invalid_event_label")
    ]


def test_trigger_reconciliation_keeps_distinct_source_owned_occurrences() -> None:
    source = "Amodei published an op-ed describing Trump as a feudal warlord."
    source_copy = derive_source_copy_view(source)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy)}
    selected = select_non_overlapping_trigger_proposals(
        (
            EventTriggerProposal(1, "o2", "publication"),
            EventTriggerProposal(2, "o5", "characterization"),
        ),
        occurrences=occurrences,
        source_copy=source_copy,
    )

    assert [item.occurrence_id for item in selected] == ["o2", "o5"]


def test_source_occurrences_are_exact_ordered_source_choices() -> None:
    source_copy = derive_source_copy_view("Hegseth has publicly rebuked Amodei.")

    result = source_occurrences(source_copy)

    assert [(item.occurrence_id, item.text) for item in result] == [
        ("o1", "Hegseth"),
        ("o2", "has"),
        ("o3", "publicly"),
        ("o4", "rebuked"),
        ("o5", "Amodei"),
    ]


def test_empty_complete_preview_uses_canonical_content_identity() -> None:
    preview = build_hybrid_event_trigger_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_ids=("ctx_trigger",),
        terminal_status=HybridEventTriggerStatus.COMPLETE,
    )

    payload = canonical_hybrid_event_trigger_preview_bytes(preview)

    assert hybrid_event_trigger_preview_from_bytes(payload) == preview
    assert preview.id.startswith("htp_")
    assert hashlib.sha256(payload).hexdigest()


def test_blocked_preview_requires_visible_diagnostic() -> None:
    with pytest.raises(ValueError, match="requires only diagnostics"):
        build_hybrid_event_trigger_preview(
            parent_preview_id="hgp_" + "1" * 24,
            parent_preview_sha256="a" * 64,
            reference_preview_id="hrp_" + "2" * 24,
            reference_preview_sha256="b" * 64,
            mention_preview_id="hxp_" + "3" * 24,
            mention_preview_sha256="c" * 64,
            representation_id="rep_fixture",
            paragraph_node_id="nod_fixture",
            context_manifest_ids=("ctx_trigger",),
            terminal_status=HybridEventTriggerStatus.BLOCKED,
        )
