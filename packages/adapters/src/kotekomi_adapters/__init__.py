"""KoteKomi Adapters."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kotekomi_adapters.docling_pdf_parser import (
        DoclingPdfParser,
        DoclingPdfParserConfig,
        preflight_pdf_source,
    )
    from kotekomi_adapters.gliner_organization_mention_proposer import (
        GlinerMentionProposer,
        GlinerOrganizationMentionProposer,
    )
    from kotekomi_adapters.llama_server_embeddings import LlamaServerEmbeddingAdapter
    from kotekomi_adapters.llama_server_model_runtime import LlamaServerModelRuntime
    from kotekomi_adapters.lm_studio_embeddings import LMStudioEmbeddingAdapter
    from kotekomi_adapters.lm_studio_model_runtime import LMStudioModelRuntime
    from kotekomi_adapters.local_archive import LocalArchiveStore
    from kotekomi_adapters.model_http import HttpResponse, JsonHttpClient
    from kotekomi_adapters.ollama_embeddings import OllamaEmbeddingAdapter
    from kotekomi_adapters.ollama_model_runtime import OllamaModelRuntime
    from kotekomi_adapters.pdf_evidence_overlay_renderer import PdfiumEvidenceOverlayRenderer
    from kotekomi_adapters.sqlite_document_retrieval import SQLiteDocumentRetrievalAdapter
    from kotekomi_adapters.sqlite_knowledge_graph_retrieval import (
        SQLiteKnowledgeGraphRetrievalAdapter,
    )
    from kotekomi_adapters.sqlite_ledger import (
        REQUIRED_LEDGER_TABLES,
        ImmutableCommitDisposition,
        ImmutableRecordConflict,
        NonDeterministicParserOutputConflict,
        SQLiteLedgerInitializer,
        SQLiteLedgerRepository,
        sqlite_ledger_transaction,
    )
    from kotekomi_adapters.sqlite_ledger_retrieval import SQLiteLedgerRetrievalAdapter
    from kotekomi_adapters.structured_news import GenericArticleAdapter, NewsMLG2Adapter

__all__ = [
    "DoclingPdfParser",
    "DoclingPdfParserConfig",
    "HttpResponse",
    "GenericArticleAdapter",
    "GlinerOrganizationMentionProposer",
    "GlinerMentionProposer",
    "JsonHttpClient",
    "ImmutableCommitDisposition",
    "ImmutableRecordConflict",
    "NonDeterministicParserOutputConflict",
    "LlamaServerModelRuntime",
    "LMStudioModelRuntime",
    "LlamaServerEmbeddingAdapter",
    "LMStudioEmbeddingAdapter",
    "LocalArchiveStore",
    "NewsMLG2Adapter",
    "OllamaModelRuntime",
    "OllamaEmbeddingAdapter",
    "PdfiumEvidenceOverlayRenderer",
    "REQUIRED_LEDGER_TABLES",
    "SQLiteLedgerInitializer",
    "SQLiteLedgerRepository",
    "SQLiteDocumentRetrievalAdapter",
    "SQLiteLedgerRetrievalAdapter",
    "SQLiteKnowledgeGraphRetrievalAdapter",
    "sqlite_ledger_transaction",
    "preflight_pdf_source",
]


def __getattr__(name: str) -> object:
    if name in {"GlinerMentionProposer", "GlinerOrganizationMentionProposer"}:
        from kotekomi_adapters.gliner_organization_mention_proposer import (
            GlinerMentionProposer,
            GlinerOrganizationMentionProposer,
        )

        return {
            "GlinerMentionProposer": GlinerMentionProposer,
            "GlinerOrganizationMentionProposer": GlinerOrganizationMentionProposer,
        }[name]
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
    if name == "LlamaServerModelRuntime":
        from kotekomi_adapters.llama_server_model_runtime import LlamaServerModelRuntime

        return LlamaServerModelRuntime
    if name == "LMStudioModelRuntime":
        from kotekomi_adapters.lm_studio_model_runtime import LMStudioModelRuntime

        return LMStudioModelRuntime
    if name == "LlamaServerEmbeddingAdapter":
        from kotekomi_adapters.llama_server_embeddings import LlamaServerEmbeddingAdapter

        return LlamaServerEmbeddingAdapter
    if name == "LMStudioEmbeddingAdapter":
        from kotekomi_adapters.lm_studio_embeddings import LMStudioEmbeddingAdapter

        return LMStudioEmbeddingAdapter
    if name == "LocalArchiveStore":
        from kotekomi_adapters.local_archive import LocalArchiveStore

        return LocalArchiveStore
    if name in {"HttpResponse", "JsonHttpClient"}:
        from kotekomi_adapters.model_http import HttpResponse, JsonHttpClient

        return {"HttpResponse": HttpResponse, "JsonHttpClient": JsonHttpClient}[name]
    if name == "OllamaModelRuntime":
        from kotekomi_adapters.ollama_model_runtime import OllamaModelRuntime

        return OllamaModelRuntime
    if name == "OllamaEmbeddingAdapter":
        from kotekomi_adapters.ollama_embeddings import OllamaEmbeddingAdapter

        return OllamaEmbeddingAdapter
    if name == "PdfiumEvidenceOverlayRenderer":
        from kotekomi_adapters.pdf_evidence_overlay_renderer import (
            PdfiumEvidenceOverlayRenderer,
        )

        return PdfiumEvidenceOverlayRenderer
    if name in {"GenericArticleAdapter", "NewsMLG2Adapter"}:
        from kotekomi_adapters.structured_news import GenericArticleAdapter, NewsMLG2Adapter

        return {
            "GenericArticleAdapter": GenericArticleAdapter,
            "NewsMLG2Adapter": NewsMLG2Adapter,
        }[name]
    if name in {
        "REQUIRED_LEDGER_TABLES",
        "ImmutableCommitDisposition",
        "ImmutableRecordConflict",
        "NonDeterministicParserOutputConflict",
        "SQLiteLedgerInitializer",
        "SQLiteLedgerRepository",
        "sqlite_ledger_transaction",
    }:
        from kotekomi_adapters.sqlite_ledger import (
            REQUIRED_LEDGER_TABLES,
            ImmutableCommitDisposition,
            ImmutableRecordConflict,
            NonDeterministicParserOutputConflict,
            SQLiteLedgerInitializer,
            SQLiteLedgerRepository,
            sqlite_ledger_transaction,
        )

        return {
            "REQUIRED_LEDGER_TABLES": REQUIRED_LEDGER_TABLES,
            "ImmutableCommitDisposition": ImmutableCommitDisposition,
            "ImmutableRecordConflict": ImmutableRecordConflict,
            "NonDeterministicParserOutputConflict": NonDeterministicParserOutputConflict,
            "SQLiteLedgerInitializer": SQLiteLedgerInitializer,
            "SQLiteLedgerRepository": SQLiteLedgerRepository,
            "sqlite_ledger_transaction": sqlite_ledger_transaction,
        }[name]
    if name == "SQLiteDocumentRetrievalAdapter":
        from kotekomi_adapters.sqlite_document_retrieval import SQLiteDocumentRetrievalAdapter

        return SQLiteDocumentRetrievalAdapter
    if name == "SQLiteLedgerRetrievalAdapter":
        from kotekomi_adapters.sqlite_ledger_retrieval import SQLiteLedgerRetrievalAdapter

        return SQLiteLedgerRetrievalAdapter
    if name == "SQLiteKnowledgeGraphRetrievalAdapter":
        from kotekomi_adapters.sqlite_knowledge_graph_retrieval import (
            SQLiteKnowledgeGraphRetrievalAdapter,
        )

        return SQLiteKnowledgeGraphRetrievalAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
