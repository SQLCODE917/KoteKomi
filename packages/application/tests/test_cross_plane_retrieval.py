from types import SimpleNamespace
from typing import Any, cast

from kotekomi_application.cross_plane_retrieval import (
    CrossPlaneFailureCode,
    QueryCrossPlaneCommand,
    query_cross_plane,
)
from kotekomi_application.knowledge_graph_retrieval import KnowledgeGraphRetrievalFailureCode
from kotekomi_domain import LedgerContextResult


class RecordStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def save_cross_plane_query_record(self, record: object) -> None:
        self.records.append(record)


def _ledger_result(*, selected: tuple[str, ...] = ("rel_policy",)) -> object:
    return SimpleNamespace(
        status="complete",
        retrieval_query_id="lrq_contract",
        index_manifest_id="lrm_contract",
        selected_record_ids=selected,
        failure=None,
    )


def _graph_result(*, failure: object = None) -> object:
    context = LedgerContextResult(
        representation_id="rep_contract",
        focus_node_ids=("nod_contract",),
        analysis_unit_id="anu_contract",
        context_manifest_id="ctx_contract",
        status="ready",
    )
    hit = SimpleNamespace(selected=True, terminal_evidence_target_ids=("etg_contract",))
    return SimpleNamespace(
        status="failed" if failure is not None else "complete",
        retrieval_query_id="grq_contract",
        index_manifest_id="grm_contract",
        selected_record_ids=() if failure is not None else ("rel_policy",),
        hits=() if failure is not None else (hit,),
        context_results=() if failure is not None else (context,),
        failure=failure,
    )


def test_cross_plane_query_records_role_aware_transitions(
    monkeypatch: Any,
) -> None:
    store = RecordStore()

    def ledger_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _ledger_result()

    def graph_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _graph_result()

    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_ledger_retrieval",
        ledger_query,
    )
    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_knowledge_graph",
        graph_query,
    )

    result = query_cross_plane(
        QueryCrossPlaneCommand(query_text="Anthropic"),
        ledger_repository=cast(Any, object()),
        ledger_projection=cast(Any, object()),
        graph_projection=cast(Any, store),
        tokenizer=cast(Any, object()),
    )

    assert result.status == "complete"
    assert result.terminal_evidence_target_ids == ("etg_contract",)
    assert [item.phase.value for item in result.transitions] == [
        "ledger_discovery",
        "graph_expansion",
        "document_evidence",
        "context_planning",
    ]
    assert len(store.records) == 1


def test_cross_plane_query_maps_graph_seed_ambiguity_to_its_typed_result(
    monkeypatch: Any,
) -> None:
    store = RecordStore()

    def ledger_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _ledger_result()

    def graph_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _graph_result(failure=KnowledgeGraphRetrievalFailureCode.SEED_AMBIGUOUS)

    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_ledger_retrieval",
        ledger_query,
    )
    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_knowledge_graph",
        graph_query,
    )

    result = query_cross_plane(
        QueryCrossPlaneCommand(query_text="Anthropic"),
        ledger_repository=cast(Any, object()),
        ledger_projection=cast(Any, object()),
        graph_projection=cast(Any, store),
        tokenizer=cast(Any, object()),
    )

    assert result.status == "failed"
    assert result.failure is CrossPlaneFailureCode.SEED_AMBIGUOUS
    assert result.transitions[-1].failure_code == "knowledge_graph_seed_ambiguous"


def test_cross_plane_query_blocks_when_ledger_discovery_selects_nothing(
    monkeypatch: Any,
) -> None:
    store = RecordStore()

    def ledger_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _ledger_result(selected=())

    def graph_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("Graph traversal must not run after an empty Ledger result.")

    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_ledger_retrieval", ledger_query
    )
    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_knowledge_graph", graph_query
    )

    result = query_cross_plane(
        QueryCrossPlaneCommand(query_text="missing"),
        ledger_repository=cast(Any, object()),
        ledger_projection=cast(Any, object()),
        graph_projection=cast(Any, store),
        tokenizer=cast(Any, object()),
    )

    assert result.status == "failed"
    assert result.failure is CrossPlaneFailureCode.LEDGER_EMPTY
    assert [item.phase.value for item in result.transitions] == ["ledger_discovery"]


def test_cross_plane_query_maps_a_missing_graph_seed_to_its_typed_result(
    monkeypatch: Any,
) -> None:
    store = RecordStore()

    def ledger_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _ledger_result()

    def graph_query(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _graph_result(failure=KnowledgeGraphRetrievalFailureCode.SEED_MISSING)

    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_ledger_retrieval", ledger_query
    )
    monkeypatch.setattr(
        "kotekomi_application.cross_plane_retrieval.query_knowledge_graph", graph_query
    )

    result = query_cross_plane(
        QueryCrossPlaneCommand(query_text="unresolvable"),
        ledger_repository=cast(Any, object()),
        ledger_projection=cast(Any, object()),
        graph_projection=cast(Any, store),
        tokenizer=cast(Any, object()),
    )

    assert result.status == "failed"
    assert result.failure is CrossPlaneFailureCode.SEED_MISSING
    assert result.transitions[-1].failure_code == "knowledge_graph_seed_missing"
