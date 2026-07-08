# Agent Guidelines for KoteKomi

## Purpose

Build KoteKomi as a local-first intelligence ledger and Briefing generator.

Optimize for explicit boundaries, narrow state, testable records, and easy review.

Prefer simple code over clever abstractions.

Prefer explicit data contracts over inferred behavior.

## Read Order

Before changing code, read:

1. This file.
2. The nearest package-level `AGENTS.md`, when it exists.
3. The task-specific file in `docs/agent/`.
4. `docs/2026-07-08-KoteKomi.md`.
5. `docs/CHECK_PLAN.md` before finishing the task.

## Task Routing

| Task | Read |
|---|---|
| writing a TDD | `docs/agent/writing-tdds.md`, `docs/agent/documentation-style.md` |
| changing documentation | `docs/agent/documentation-style.md` |
| changing Domain Core | `docs/agent/domain.md`, `docs/agent/architecture.md`, `docs/agent/testing.md` |
| changing Application Layer | `docs/agent/architecture.md`, `docs/agent/domain.md`, `docs/agent/testing.md` |
| adding an Adapter | `docs/agent/adapters.md`, `docs/agent/architecture.md`, `docs/agent/testing.md` |
| adding a Pipeline | `docs/agent/pipelines.md`, `docs/agent/testing.md` |
| changing model behavior | `docs/agent/model-runtime.md`, `docs/agent/domain.md`, `docs/agent/testing.md` |
| changing Briefing output | `docs/agent/domain.md`, `docs/agent/pipelines.md`, `docs/agent/output-format.md`, `docs/agent/testing.md` |
| changing exporters | `docs/agent/adapters.md`, `docs/agent/domain.md`, `docs/agent/testing.md` |
| changing tests | `docs/agent/testing.md` |

## Authority Order

When files conflict, use this order:

1. `docs/2026-07-08-KoteKomi.md`
2. accepted TDDs in `docs/`
3. `packages/domain`
4. `schemas/*.schema.json`
5. `packages/application`
6. `packages/adapters`
7. `packages/pipelines`
8. `prompts/*.md`
9. fixtures and generated examples

Update the higher-authority file first.

Then update dependent files.

## Project Status

KoteKomi is greenfield and pre-release.

No API, schema, file format, database shape, prompt, or Pipeline output is a published contract.

When design and old code conflict, update the old code.

When design and stale fixture data conflict, regenerate the fixture data.

Prefer clean breaking changes over compatibility code.

Delete superseded code in the same change.

Do not add migration logic, compatibility shims, fallback branches, dual-read paths, dual-write paths, deprecation markers, or legacy branches unless a TDD requires them.

## Architecture Rule

Dependencies point inward.

```text
Pipelines -> Application Layer -> Domain Core
Adapters -> Application Layer -> Domain Core
Domain Core -> no external package
```

The Domain Core must not import Adapter code, database code, model runtime code, web scraping code, vector index code, graph library code, or Markdown rendering code.

The Application Layer defines Ports.

Adapters implement Ports.

Pipelines compose Application Layer use cases.

## Boundary Validation Rule

Domain Core records and Application Layer DTOs are the source of truth for boundary shape.

At every Port, Adapter, and Pipeline boundary, parse inbound structured values through the declared Domain Core record or Application Layer DTO.

Serialize outbound structured values from the declared Domain Core record or Application Layer DTO.

Deterministic project-owned boundaries must fail fast on invalid shape, missing required references, or impossible state.

Do not silently drop, repair, coerce, skip, or clean up invalid deterministic values.

Accepted Ledger writes must validate both Domain Core record shape and cross-record references before commit.

Only non-deterministic outputs, such as local model output, can enter explicit recovery paths.

Recovery must be visible as rejection, quarantine, a validation error, or a reviewable ProposedChange.

Do not convert invalid model output into accepted state.

## Code Quality Rules

Application Layer use cases own domain decisions, status transitions, and transaction intent.

Adapters translate, validate, persist, and load records.

Adapters do not decide Domain meaning, review outcomes, or repair policy.

Public Application Layer use cases use explicit input and result DTOs.

Each accepted Ledger state change creates or references a ProvenanceActivity.

Required accepted-state invariants live in Domain Core validation or Application Layer reference validation.

Record-type dispatch must cover every supported Domain Core record type explicitly or fail.

Nontrivial boundary mappings use named mapping functions.

The Ledger and Archive store canonical state.

Graph projections, vector indexes, Briefings, and exports are derived state.

Derived state must be rebuildable from the Ledger and Archive.

Happy-path fixtures must be internally coherent.

Malformed fixtures must be named as negative fixtures and assert the exact failure.

## Canonical Terms

Use the canonical terms in `docs/agent/domain.md`.

Do not introduce synonyms for canonical terms.

## Check Plan

`docs/CHECK_PLAN.md` is the verification checklist.

Run the applicable checks before finishing a task.

Update `docs/CHECK_PLAN.md` when a new contract needs a repeatable verification step.

## Done Means

A change is done when applicable checks pass.

Done includes:

- formatting passes
- lint passes
- typecheck passes
- relevant tests pass
- fixtures match current contracts
- documentation matches current contracts
- no naming drift
- no dead code
- no accidental coupling

## Output Formatting

Use `docs/agent/output-format.md` for implementation summaries.

Report tests run and tests not run.
