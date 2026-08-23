import json
from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import Document, Source, SourceType
from kotekomi_pipelines.cli import main


def test_public_lineage_proposal_then_review_acceptance(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger.sqlite"
    assert main(["ledger", "init", "--ledger-path", str(ledger_path)]) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for source_id in ("src_first", "src_second"):
            ledger.save_source(
                Source(
                    id=source_id,
                    source_type=SourceType.PDF,
                    identity_policy_id="test-v1",
                    canonical_identity_key=f"https://example.test/{source_id}",
                )
            )
        for document_id, source_id in (
            ("doc_first", "src_first"),
            ("doc_second", "src_second"),
        ):
            ledger.save_document(
                Document(id=document_id, source_id=source_id, content_sha256="a" * 64)
            )

    assert (
        main(
            [
                "lineage",
                "propose-verbatim-republication",
                "--ledger-path",
                str(ledger_path),
                "--document-id",
                "doc_second",
                "--document-id",
                "doc_first",
                "--proposer",
                "test-analyst",
                "--rationale",
                "The archived bytes are identical.",
                "--format",
                "json",
            ]
        )
        == 0
    )
    proposal = json.loads(capsys.readouterr().out)
    assert proposal["status"] == "pending"

    assert (
        main(
            [
                "review",
                "approve",
                "--ledger-path",
                str(ledger_path),
                "--proposed-change-id",
                proposal["proposed_change_id"],
                "--reviewer",
                "test-reviewer",
            ]
        )
        == 0
    )
    with sqlite_ledger_transaction(ledger_path) as ledger:
        relations = ledger.list_source_lineage_relations()
    assert len(relations) == 1
    assert relations[0].document_ids == ("doc_first", "doc_second")
