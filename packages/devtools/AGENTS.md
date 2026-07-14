# Agent Guidelines for KoteKomi Devtools

## Purpose

Build repository-local agent harness tooling.

Keep task execution boundaries explicit, deterministic, and independently verifiable.

The devtools package is not part of the KoteKomi product architecture.

## Read Order

Before changing this package, read:

1. Root `AGENTS.md`.
2. This file.
3. The accepted Leaf TDD named by the task manifest.
4. The protected JSON Schema named by the Leaf TDD.
5. `docs/2026-07-14-terra-high-harness-series-plan.md`.
6. `docs/agent/testing.md`.
7. `docs/CHECK_PLAN.md` before reporting candidate completion.

## Package Boundary

`kotekomi-devtools` must not import:

- `kotekomi-domain`;
- `kotekomi-application`;
- `kotekomi-adapters`;
- `kotekomi-pipelines`;
- `kotekomi-briefing`.

KoteKomi product packages must not import `kotekomi-devtools`.

The package can use Python standard-library modules and explicitly declared harness dependencies.

## Contract Authority

The accepted Leaf TDD owns public behavior.

The protected JSON Schema owns Task Manifest shape.

Protected acceptance tests own black-box examples.

The implementation agent cannot edit a protected artifact.

Report a specification gap when protected authorities conflict.

## CLI Rules

Use argument arrays rather than shell command strings.

Do not invoke a shell unless a later accepted TDD explicitly requires it.

Emit deterministic machine-readable output.

Expected invalid input must not emit a traceback.

Do not hide expected validation failures behind broad exception handling.

Map every expected failure to the diagnostic contract.

## Determinism Rules

Preserve input array order.

Sort only fields whose contract requires sorting.

Use stable JSON serialization.

Do not include clocks, random identifiers, temporary paths, or process-specific values in contract output.

## Filesystem Rules

Treat paths inside Task Manifest V1 as inert repository-relative values.

H1 must not check path existence, resolve symlinks, inspect Git, or execute manifest commands.

Later leaves can add those behaviors only through accepted contracts.

## Test Rules

Protected acceptance tests are read-only.

Add implementation-focused unit tests under `packages/devtools/tests/unit/`.

Test public CLI behavior through subprocess boundaries.

Use temporary directories and disposable repositories for later Git-facing leaves.

Do not require network access in package tests.

## H1 Implementation Scope

The H1 task manifest defines the exact allowed paths.

Do not change the Leaf TDD, task manifest, JSON Schema, this file, acceptance tests, or fixture inputs.

The implementer can report candidate completion only.

Independent verification determines whether H1 is complete.
