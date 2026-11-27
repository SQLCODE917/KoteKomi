# Agent Guidelines for KoteKomi Devtools

## Purpose

Build repository-local agent harness tooling.

Keep task execution boundaries explicit, deterministic, and independently verifiable.

The devtools package is not part of the KoteKomi product architecture.

## Read Order

Before changing this package, read:

1. Root `AGENTS.md`.
2. This file.
3. The active Agile package and the public contracts changed by this task.
4. `docs/agent/testing.md`.
5. `docs/CHECK_PLAN.md` before requesting review.

Ordinary devtools PRs follow `docs/agent/implement-tdd-workflow.md`.
Existing Harness commands are tools under test, not prerequisites for working on this package.
For maintenance of a historical Harness contract, read its TDD and schema as the behavior being tested.

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

The active Agile package states intended behavior and any changes to earlier contracts.
Update schemas, examples, tests, and documentation together when a public contract changes.
Existing regression tests remain useful evidence; do not weaken them to hide a failure.
Product or public-contract decisions beyond the agreed outcome go to the operator.

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

Update acceptance tests when an authorized contract changes; retain coverage of unchanged behavior.

Add implementation-focused unit tests under `packages/devtools/tests/unit/`.

Test public CLI behavior through subprocess boundaries.

Use temporary directories and disposable repositories for later Git-facing leaves.

Do not require network access in package tests.

## Verification

Run focused unit and public CLI contract tests for the changed commands.
CLI dispatch changes must exercise delimiter and failure cases, not only a success smoke test.
Verification-plan changes must exercise its selection and unknown-path behavior through the existing contract tests.
Then run the normal fast checks and use full PR CI as the merge gate.
No task manifest, Harness run, lifecycle gate, or independent receipt is required to develop devtools.

## Receipt-chain status edits

Receipt-chain status must stay deterministic and read-only. Compute status
from receipt files, expected record names, and optional expected SHA-256
values; do not infer completion from chat context, roadmap prose, or
implementation-agent memory.
