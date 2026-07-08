from pathlib import Path

FORBIDDEN_IMPORT_TOKENS = (
    "sqlite3",
    "lancedb",
    "networkx",
    "ollama",
    "llama_cpp",
    "vllm",
    "trafilatura",
    "markdown",
    "kotekomi_adapters",
)


def test_domain_core_imports_no_forbidden_tool_packages() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "kotekomi_domain"
    python_files = sorted(source_root.rglob("*.py"))

    assert python_files
    for path in python_files:
        text = path.read_text()
        for token in FORBIDDEN_IMPORT_TOKENS:
            assert f"import {token}" not in text
            assert f"from {token}" not in text
