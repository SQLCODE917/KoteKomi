from kotekomi_domain import (
    CrossPlaneQueryPhase,
    CrossPlaneQueryRecord,
    CrossPlaneTransition,
    LedgerContextResult,
    RetrievalPlane,
)
from pytest import raises


def test_cross_plane_query_record_keeps_ordered_plane_provenance() -> None:
    record = CrossPlaneQueryRecord(
        cross_plane_query_id="cpq_contract",
        query_text="Anthropic",
        normalized_query_text="anthropic",
        policy_id="cross_plane_ledger_graph_evidence_v1",
        transitions=(
            CrossPlaneTransition(
                phase=CrossPlaneQueryPhase.LEDGER_DISCOVERY,
                plane=RetrievalPlane.LEDGER,
                status="complete",
                local_query_record_id="lrq_contract",
                index_manifest_id="lrm_contract",
                selected_record_ids=("rel_contract",),
            ),
            CrossPlaneTransition(
                phase=CrossPlaneQueryPhase.GRAPH_EXPANSION,
                plane=RetrievalPlane.KNOWLEDGE_GRAPH,
                status="complete",
                local_query_record_id="grq_contract",
                index_manifest_id="grm_contract",
                selected_record_ids=("rel_contract",),
                terminal_evidence_target_ids=("etg_contract",),
            ),
        ),
        selected_record_ids=("rel_contract",),
        terminal_evidence_target_ids=("etg_contract",),
        context_results=(
            LedgerContextResult(
                representation_id="rep_contract",
                focus_node_ids=("nod_contract",),
                analysis_unit_id="anu_contract",
                context_manifest_id="ctx_contract",
                status="ready",
            ),
        ),
    )

    assert record.transitions[1].terminal_evidence_target_ids == ("etg_contract",)


def test_cross_plane_query_record_requires_ledger_as_its_first_transition() -> None:
    with raises(ValueError, match="starts with Ledger discovery"):
        CrossPlaneQueryRecord(
            cross_plane_query_id="cpq_invalid",
            query_text="Anthropic",
            normalized_query_text="anthropic",
            policy_id="cross_plane_ledger_graph_evidence_v1",
            transitions=(
                CrossPlaneTransition(
                    phase=CrossPlaneQueryPhase.GRAPH_EXPANSION,
                    plane=RetrievalPlane.KNOWLEDGE_GRAPH,
                    status="blocked",
                ),
            ),
        )
