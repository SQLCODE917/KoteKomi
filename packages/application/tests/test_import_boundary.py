from pathlib import Path

FORBIDDEN_IMPORT_TOKENS = (
    "sqlite3",
    "kotekomi_adapters",
)


def test_application_layer_imports_no_adapter_or_sqlite_packages() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "kotekomi_application"
    python_files = sorted(source_root.rglob("*.py"))

    assert python_files
    for path in python_files:
        text = path.read_text()
        for token in FORBIDDEN_IMPORT_TOKENS:
            assert f"import {token}" not in text
            assert f"from {token}" not in text
