"""KoteKomi Adapters."""

from typing import TYPE_CHECKING

from kotekomi_adapters.fixture_model_runtime import FixtureModelRuntime
from kotekomi_adapters.llama_server_model_runtime import LlamaServerModelRuntime
from kotekomi_adapters.local_archive import LocalArchiveStore
from kotekomi_adapters.model_http import HttpResponse, JsonHttpClient
from kotekomi_adapters.networkx_graph_analyzer import NetworkXGraphAnalyzer
from kotekomi_adapters.ollama_model_runtime import OllamaModelRuntime
from kotekomi_adapters.sqlite_ledger import (
    REQUIRED_LEDGER_TABLES,
    ImmutableCommitDisposition,
    ImmutableRecordConflict,
    NonDeterministicParserOutputConflict,
    SQLiteLedgerInitializer,
    SQLiteLedgerRepository,
    sqlite_ledger_transaction,
)

if TYPE_CHECKING:
    from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig

__all__ = [
    "FixtureModelRuntime",
    "DoclingPdfParser",
    "DoclingPdfParserConfig",
    "HttpResponse",
    "JsonHttpClient",
    "ImmutableCommitDisposition",
    "ImmutableRecordConflict",
    "NonDeterministicParserOutputConflict",
    "LlamaServerModelRuntime",
    "LocalArchiveStore",
    "NetworkXGraphAnalyzer",
    "OllamaModelRuntime",
    "REQUIRED_LEDGER_TABLES",
    "SQLiteLedgerInitializer",
    "SQLiteLedgerRepository",
    "sqlite_ledger_transaction",
]


def __getattr__(name: str) -> object:
    if name in {"DoclingPdfParser", "DoclingPdfParserConfig"}:
        from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig

        return {
            "DoclingPdfParser": DoclingPdfParser,
            "DoclingPdfParserConfig": DoclingPdfParserConfig,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
