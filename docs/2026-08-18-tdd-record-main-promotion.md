# TDD Record Main Promotion

## Context & Problem

The Harness records a main promotion after candidate CI succeeds.

The current producer supports direct and merge promotions.

The producer lacks complete contract proof for direct promotion and invalid Git topology.

This TDD uses the term `main promotion` for a candidate commit that reaches `origin/main`.

The main promotion is direct when it has one parent.

The main promotion is a merge when it has two parents.

Primary end-to-end Flow:

1. An operator records a commit that equals local `origin/main`.
2. The Harness resolves the commit and validates its parent count.
3. The Harness writes canonical `main_promotion` evidence.
4. The workflow validates that promotion against candidate evidence.
5. The workflow selects main CI evidence or blocks on mismatch.

## Goals

- An operator can record a direct or merge main promotion with one command.

- The Harness rejects a commit that does not equal `origin/main`.

- The Harness preserves one canonical promotion record and evidence event.

## Requirements

Producer boundary:

- MP-01: `record-main-promotion` accepts `--commit <revision>` and common run arguments.

- MP-02: The producer resolves the revision and `origin/main` to local Git commits.

- MP-03: The producer blocks unless both resolved commits have the same SHA-1.

- MP-04: The producer blocks unless the promotion has one or two parents.

- MP-05: The producer writes `promotion_kind` as `direct` for one parent and `merge` for two parents.

- MP-06: The producer writes `promotion_commit`, `parent_commit`, and `verified_parent_commit`.

- MP-07: The producer writes null `verified_parent_commit` for a direct promotion.

- MP-08: The producer writes canonical `main_promotion` evidence with phase `main` and subject `main`.

Workflow boundary:

- WF-01: The workflow suggests `record-main-promotion` when main promotion evidence is missing.

- WF-02: The workflow blocks when a direct promotion differs from candidate commit evidence.

- WF-03: The workflow blocks when a merge promotion second parent differs from candidate commit evidence.

- WF-04: The workflow blocks when main CI differs from promotion commit evidence.

## Proposed Architecture

The lifecycle evidence producer owns Git fact validation and canonical record creation.

The evidence catalog owns record discovery and digest validation.

The workflow owns promotion-to-candidate validation.

```text
Operator -> promotion producer -> evidence catalog -> workflow
```

## Key Interactions

```text
Operator       Producer       Git       Evidence catalog
   |              |            |              |
   | command      |            |              |
   |------------->| resolve    |              |
   |              |----------->|              |
   |              | validate   |              |
   |              |-------------------------->|
   | record JSON  |            |              |
   |<-------------|            |              |
```

## Data Model

The producer writes `schema_version`, `promotion_kind`, `promotion_commit`, `parent_commit`, `verified_parent_commit`, and `diagnostics`.

The evidence catalog stores the record at `git/main-promotion.json` under the run root.

## APIs / Interfaces

```text
kotekomi-agent record-main-promotion --commit <revision>
--task-id <task-id> --run <run-id> [--state-root <state-root>]
```

## Behavior & Domain Rules

The producer never changes Git state.

The producer writes report copies only when the operator requests them.

The workflow accepts only `main_promotion` as main promotion evidence.

The workflow requires direct promotion commit equality.

The workflow requires merge second-parent equality.

## Acceptance Criteria

- AC-MP-01: CLI tests prove direct and merge promotion records.

- AC-MP-02: CLI tests prove root, octopus, stale, and absent `origin/main` inputs block.

- AC-MP-03: Evidence tests prove canonical path, index entry, event, and report copies.

- AC-WF-01: Workflow tests prove action selection and direct, merge, and CI mismatch blocking.

- AC-EC-01: Catalog and metrics tests prove only `main_promotion` is recognized.

## Reference Implementations

- Git evidence: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

- Indexing: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Workflow: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

## Constraints and Halt Conditions

The implementer halts when Git is unavailable.

The implementer does not create merge, CI, or remote state.
