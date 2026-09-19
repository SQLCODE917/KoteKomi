from __future__ import annotations

from kotekomi_pipelines.competitive_attachment_selection import (
    build_attachment_rescue_metrics,
    build_candidate_source_oracle,
    build_per_edge_oracle,
    combine_attachment_predictions,
)

EVENT_ONE = "sge_" + "1" * 24
EVENT_TWO = "sge_" + "2" * 24
EVENT_THREE = "sge_" + "3" * 24


def test_selection_set_operations_preserve_occurrence_specific_edges() -> None:
    qwen = {"c1": (EVENT_ONE,), "c2": (EVENT_TWO,)}
    syntax = {"c1": (EVENT_TWO,), "c2": (EVENT_TWO, EVENT_THREE)}

    assert combine_attachment_predictions(qwen, syntax, operation="union") == {
        "c1": (EVENT_ONE, EVENT_TWO),
        "c2": (EVENT_TWO, EVENT_THREE),
    }
    assert combine_attachment_predictions(qwen, syntax, operation="intersection") == {
        "c1": (),
        "c2": (EVENT_TWO,),
    }


def test_rescue_metrics_separate_recovered_gold_from_added_false_edges() -> None:
    gold = {"c1": (EVENT_ONE, EVENT_TWO), "c2": (EVENT_TWO,)}
    qwen = {"c1": (EVENT_ONE,), "c2": ()}
    syntax = {"c1": (EVENT_TWO, EVENT_THREE), "c2": (EVENT_TWO,)}

    result = build_attachment_rescue_metrics(
        gold_sets=gold,
        qwen=qwen,
        syntax=syntax,
    )

    assert result.qwen_false_negative_edge_count == 2
    assert result.added_syntax_edge_count == 3
    assert result.rescued_gold_edge_count == 2
    assert result.added_false_edge_count == 1
    assert result.rescue_precision == 2 / 3
    assert result.qwen_false_negative_coverage == 1.0


def test_gold_dependent_oracles_expose_distinct_selection_ceilings() -> None:
    gold = {"c1": (EVENT_ONE,), "c2": (EVENT_TWO,)}
    qwen = {"c1": (EVENT_ONE, EVENT_THREE), "c2": ()}
    syntax = {"c1": (), "c2": (EVENT_TWO,)}

    assert build_candidate_source_oracle(
        gold_sets=gold,
        qwen=qwen,
        syntax=syntax,
    ) == {
        "c1": (EVENT_ONE, EVENT_THREE),
        "c2": (EVENT_TWO,),
    }
    assert build_per_edge_oracle(
        gold_sets=gold,
        qwen=qwen,
        syntax=syntax,
    ) == {
        "c1": (EVENT_ONE,),
        "c2": (EVENT_TWO,),
    }
