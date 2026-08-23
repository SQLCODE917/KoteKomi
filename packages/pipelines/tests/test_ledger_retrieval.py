from pathlib import Path

from kotekomi_pipelines.cli import main
from pytest import MonkeyPatch


def test_build_ledger_retrieval_routes_to_the_public_pipeline(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_build_ledger_retrieval_index(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.build_ledger_retrieval_index", fake_build_ledger_retrieval_index
    )

    assert (
        main(["retrieval", "build-ledger", "--ledger-path", str(tmp_path / "ledger.sqlite")]) == 0
    )
    assert captured["rebuild"] is False


def test_query_ledger_retrieval_routes_canonical_filters(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_query_ledger_retrieval_index(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.query_ledger_retrieval_index", fake_query_ledger_retrieval_index
    )

    assert (
        main(
            [
                "retrieval",
                "query-ledger",
                "--ledger-path",
                str(tmp_path / "ledger.sqlite"),
                "--record-id",
                "ast_directive_current",
                "--record-type",
                "assertion",
                "--policy",
                "audit-history",
                "--maximum-hits",
                "5",
                "--context-profile",
                "retrieval-validation-v1",
            ]
        )
        == 0
    )
    assert captured["record_id"] == "ast_directive_current"
    assert captured["policy"] == "audit-history"
