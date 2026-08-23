from pathlib import Path

from kotekomi_pipelines.cli import main
from pytest import MonkeyPatch


def test_graph_retrieval_commands_route_to_the_public_pipeline(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def build(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    def query(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("kotekomi_pipelines.cli.build_knowledge_graph_retrieval_index", build)
    assert main(["retrieval", "build-graph", "--ledger-path", str(tmp_path / "ledger.sqlite")]) == 0
    assert captured["rebuild"] is False

    monkeypatch.setattr("kotekomi_pipelines.cli.query_knowledge_graph_retrieval_index", query)
    assert (
        main(
            [
                "retrieval",
                "query-graph",
                "--ledger-path",
                str(tmp_path / "ledger.sqlite"),
                "--seed",
                "Anthropic",
                "--maximum-hops",
                "2",
                "--maximum-hits",
                "5",
                "--context-profile",
                "retrieval-validation-v1",
            ]
        )
        == 0
    )
    assert captured["seed"] == "Anthropic"
    assert captured["maximum_hops"] == 2


def test_evidence_graph_commands_route_to_the_public_pipeline(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def build(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("kotekomi_pipelines.cli.build_evidence_graph_projection_index", build)
    assert (
        main(
            [
                "retrieval",
                "build-graph-evidence",
                "--ledger-path",
                str(tmp_path / "ledger.sqlite"),
                "--rebuild",
            ]
        )
        == 0
    )
    assert captured["rebuild"] is True

    def explain(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("kotekomi_pipelines.cli.explain_evidence_graph_relationship_index", explain)
    assert (
        main(
            [
                "retrieval",
                "explain-graph-relationship",
                "--ledger-path",
                str(tmp_path / "ledger.sqlite"),
                "--relationship-id",
                "rel_policy",
                "--context-profile",
                "retrieval-validation-v1",
            ]
        )
        == 0
    )
    assert captured["relationship_id"] == "rel_policy"
