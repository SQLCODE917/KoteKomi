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
