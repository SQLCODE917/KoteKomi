# Architecture Rules

## Purpose

Keep KoteKomi orthogonal.

Keep Domain Core pure.

Keep tool-specific behavior behind Adapters.

## Layers

KoteKomi uses these layers:

```text
Domain Core
  types, value objects, ontology rules, validation rules

Application Layer
  use cases and Ports

Adapters
  SQLite, file storage, model runtimes, vector index, graph analysis, web fetchers

Pipelines
  command-line workflows that compose use cases

Presentation
  Markdown Briefings, CLI output, future UI
```

## Dependency Rule

Dependencies point inward.

```text
Pipelines -> Application Layer -> Domain Core
Adapters -> Application Layer -> Domain Core
Domain Core -> no external package
```

## Domain Core Boundary

The Domain Core defines:

- domain objects
- controlled vocabularies
- validation rules
- status transitions
- confidence dimensions
- provenance semantics
- ontology mappings

The Domain Core must not import:

- SQLite libraries
- LanceDB libraries
- NetworkX
- Ollama clients
- llama.cpp clients
- vLLM clients
- web scraping libraries
- Markdown renderers
- RDF libraries

## Application Layer Boundary

The Application Layer defines use cases.

The Application Layer defines Ports.

The Application Layer depends on the Domain Core.

The Application Layer does not depend on specific tools.

The Application Layer owns domain decisions.

The Application Layer owns status transitions.

The Application Layer defines the atomic read, validate, write, and provenance unit for each use case.

Public Application Layer use cases use explicit input and result DTOs.

The Application Layer validates cross-record references before accepted Ledger writes.

The Application Layer rejects accepted records that reference missing Ledger records.

## Adapter Boundary

Adapters implement Ports.

Adapters validate external input.

Adapters map tool-native shapes into Application Layer DTOs or Domain Core objects.

Adapters do not pass tool-native shapes across the Application Layer boundary.

Adapters do not decide Domain meaning.

Adapters do not decide status transitions.

Adapters do not decide review outcomes.

Adapters do not repair invalid deterministic records.

## Boundary Validation

Domain Core records validate record shape and intrinsic rules.

Application Layer DTOs validate Port message shape.

Every Port, Adapter, and Pipeline boundary parses inbound structured values through the declared Domain Core record or Application Layer DTO.

Every Port, Adapter, and Pipeline boundary serializes outbound structured values from the declared Domain Core record or Application Layer DTO.

Deterministic project-owned boundaries fail fast when parsing or validation fails.

Deterministic project-owned boundaries do not drop, repair, coerce, skip, or clean up invalid values.

Accepted Ledger writes validate both Domain Core record shape and cross-record references before commit.

Required accepted-state invariants live in Domain Core validation or Application Layer reference validation.

Model output is the only boundary that can use explicit recovery for invalid structured values.

Model recovery must produce rejection, quarantine, a validation error, or a reviewable ProposedChange.

Model recovery must not produce accepted state.

## Mapping and Dispatch

Nontrivial boundary mappings use named mapping functions.

Outbound structured values come from Domain Core records or Application Layer DTOs.

Record-type dispatch covers every supported Domain Core record type explicitly or fails.

## Pipeline Boundary

Pipelines compose Application Layer use cases.

Pipelines expose user-visible commands.

Pipelines write canonical state through the Application Layer.

Pipelines write generated files into the Archive.

Pipeline commands open Ledger transactions around Application Layer use cases.

Pipeline commands do not split one use case's atomic write unit across multiple transactions.

## Provenance

Every accepted Ledger state change creates or references a ProvenanceActivity.

Use cases record ProvenanceActivity IDs on accepted records that require provenance.

## Source of Truth

The Ledger stores canonical records.

The Archive stores raw Sources, extracted Documents, generated Briefings, and exports.

The vector index is derived state.

The graph projection is derived state.

Markdown Briefings are derived artifacts.

Derived state must be rebuildable from the Ledger and Archive.
