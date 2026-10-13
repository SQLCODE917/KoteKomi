"""The inspection Application stays independent of its presentation Adapters."""

import ast
from pathlib import Path


def imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text())
    return tuple(
        name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names
    ) + tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))


def test_inspection_dependency_direction() -> None:
    packages = Path(__file__).resolve().parents[2]
    application = packages / "application/src/kotekomi_application"
    for filename in (
        "ingestion_inspection.py",
        "ingestion_debug_summary.py",
        "ingestion_inspection_reader.py",
        "inspection_session.py",
        "ingestion_execution.py",
    ):
        assert not any(
            name.startswith(
                (
                    "kotekomi_adapters",
                    "kotekomi_pipelines",
                    "rich",
                    "textual",
                    "sqlite3",
                    "subprocess",
                )
            )
            for name in imports(application / filename)
        ), filename
    for path in (packages / "adapters/src/kotekomi_adapters/extraction_view").glob("*.py"):
        assert not any(name.startswith("kotekomi_pipelines") for name in imports(path)), path.name
