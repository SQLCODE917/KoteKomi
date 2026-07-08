# Adapter Rules

## Purpose

Adapters connect KoteKomi to tools.

Adapters implement Ports from the Application Layer.

## Adapter Boundary

Add an Adapter when KoteKomi needs a new tool boundary.

Every Adapter implements one or more Ports.

Every Adapter validates external input before it passes data inward.

Every Adapter maps external data into Application Layer DTOs or Domain Core objects.

Do not pass tool-native shapes across the Application Layer boundary.

Adapters translate, validate, persist, and load records.

Adapters do not decide Domain meaning, status transitions, review outcomes, or repair policy.

Adapters parse inbound structured values through the declared Domain Core record or Application Layer DTO.

Adapters serialize outbound structured values from the declared Domain Core record or Application Layer DTO.

Deterministic Adapter boundaries fail fast when external input violates the declared contract.

Adapters do not silently drop, repair, coerce, skip, or clean up invalid deterministic input.

Adapters can recover from invalid model output only through explicit rejection, quarantine, validation errors, or reviewable ProposedChange records.

Nontrivial Adapter mappings use named mapping functions.

Adapter outbound structured values come from Domain Core records or Application Layer DTOs.

## MVP Adapters

| Port | MVP Adapter | Later Adapter |
|---|---|---|
| `LedgerRepository` | SQLite | Postgres |
| `ArchiveStore` | local filesystem | object storage |
| `VectorIndex` | LanceDB or sqlite-vec | Qdrant |
| `ModelRuntime` | Ollama or llama.cpp | MLX, vLLM, cloud LLM |
| `GraphAnalyzer` | NetworkX | Neo4j |
| `SourceFetcher` | trafilatura/manual file import | browser capture, search API |
| `BriefingWriter` | Markdown file writer | web UI, email, task output |

## Adapter Tests

Adapter tests use fixtures.

Adapter tests verify external shape mapping.

Adapter tests verify failure behavior at the tool boundary.

Adapter tests must not weaken Domain Core rules.

Adapter tests prove the Adapter satisfies the same Port contract as Application Layer fake Ports.

Adapter tests prove deterministic invalid input fails fast.

## Add an Adapter

1. Add or update the Port in `packages/application`.
2. Implement the Adapter in `packages/adapters`.
3. Add Adapter tests with fixture inputs.
4. Add a command example when the Adapter is user-visible.
5. Run applicable checks from `docs/CHECK_PLAN.md`.
