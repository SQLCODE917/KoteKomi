"""KoteKomi Adapters."""

from typing import TYPE_CHECKING

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
    from kotekomi_adapters.docling_pdf_parser import (
        DoclingPdfParser,
        DoclingPdfParserConfig,
        preflight_pdf_source,
    )

__all__ = [
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
    "preflight_pdf_source",
]


def __getattr__(name: str) -> object:
    if name in {"DoclingPdfParser", "DoclingPdfParserConfig", "preflight_pdf_source"}:
        from kotekomi_adapters.docling_pdf_parser import (
            DoclingPdfParser,
            DoclingPdfParserConfig,
            preflight_pdf_source,
        )

        return {
            "DoclingPdfParser": DoclingPdfParser,
            "DoclingPdfParserConfig": DoclingPdfParserConfig,
            "preflight_pdf_source": preflight_pdf_source,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
