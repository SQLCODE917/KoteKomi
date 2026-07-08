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

## Adapter Boundary

Adapters implement Ports.

Adapters validate external input.

Adapters map tool-native shapes into Application Layer DTOs or Domain Core objects.

Adapters do not pass tool-native shapes across the Application Layer boundary.

## Pipeline Boundary

Pipelines compose Application Layer use cases.

Pipelines expose user-visible commands.

Pipelines write canonical state through the Application Layer.

Pipelines write generated files into the Archive.

## Source of Truth

The Ledger stores canonical records.

The Archive stores raw Sources, extracted Documents, generated Briefings, and exports.

The vector index is derived state.

The graph projection is derived state.

Markdown Briefings are derived artifacts.

Derived state must be rebuildable from the Ledger and Archive.
