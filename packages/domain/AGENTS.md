# Domain Core Agent Guidelines

## Required Reads

Read before editing `packages/domain`:

1. `docs/agent/domain.md`
2. `docs/agent/architecture.md`
3. `docs/agent/testing.md`

## Boundary

The Domain Core defines domain types, value objects, ontology rules, validation rules, status transitions, and confidence semantics.

The Domain Core imports no Adapter, database, model runtime, vector index, graph library, web fetcher, or Markdown renderer.

## Checks

Run Domain Core tests after each change.

Domain Core tests use data-in/data-out assertions.

Domain Core tests do not use Adapters.
