from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ADAPTER_SOURCE = Path(__file__).parents[1] / "src" / "kotekomi_adapters" / "structured_news.py"
FIXTURES = Path(__file__).parent / "fixtures" / "news"


def test_provider_adapters_are_data_only_and_network_free() -> None:
    source = ADAPTER_SOURCE.read_text()
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported_roots.isdisjoint(
        {"httpx", "requests", "sqlite3", "urllib", "kotekomi_adapters"}
    )
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not any(
        name.startswith(("save_", "commit_", "append_", "record_")) for name in called_attributes
    )
    assert not {"src_", "doc_", "rep_", "ptf_"}.intersection(source.split())


def test_repository_external_conformance_harness_runs_the_public_contract() -> None:
    result = subprocess.run(
        (
            sys.executable,
            str(Path(__file__).parents[3] / "scripts" / "verify_private_news_conformance.py"),
            "--provider",
            "synthetic",
            "--fixture-dir",
            str(FIXTURES / "private-harness"),
            "--adapter-factory",
            "kotekomi_adapters:NewsMLG2Adapter",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
