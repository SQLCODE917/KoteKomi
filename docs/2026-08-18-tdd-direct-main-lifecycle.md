# TDD Direct Main Lifecycle

## Context & Problem

The Harness records direct main promotion evidence when a candidate commit reaches `origin/main`.

The main lifecycle checker only accepts a two-parent merge commit.

The workflow advances when a main lifecycle record exists, even when the record reports `ready: false`.

The cleanup producer requires a branch name, even when direct-to-main work created no candidate branch.

**Direct promotion** is a one-parent commit where `head` equals the verified candidate commit.

**Merge promotion** is a two-parent commit where the first parent is the main base and the second parent is the verified candidate commit.

Primary end-to-end Flow:

1. An operator records candidate CI and a direct or merge main promotion.
2. The operator runs the main lifecycle check with main base, verified candidate, and promotion head revisions.
3. The lifecycle checker records ready main lifecycle evidence only for the matching topology.
4. The workflow blocks on non-ready main lifecycle evidence.
5. The cleanup producer records empty complete cleanup evidence only for a direct promotion with no candidate branch.

## Goals

- An operator can close a valid direct-to-main Harness run without inventing a candidate branch.

- An operator can close a valid merge Harness run with ordered parent validation.

- The workflow cannot advance past non-ready main lifecycle evidence.

## Requirements

Main lifecycle boundary:

- ML-01: `lifecycle-check --phase main` keeps `--main-base`, `--verified`, and `--head` as required inputs.

- ML-02: The checker reports `promotion-topology` and `main-ci-record` as main required checks.

- ML-03: The checker reports ready for a direct promotion only when `head` equals `verified` and `head` has one parent equal to `main_base`.

- ML-04: The checker reports ready for a merge promotion only when `head` has ordered parents `main_base`, then `verified`.

- ML-05: The checker reports not ready for a direct mismatch with `task_lifecycle.direct_promotion_mismatch` and rule `main_requires_expected_direct_promotion`.

- ML-06: The checker reports not ready for a merge mismatch with `task_lifecycle.merge_parent_mismatch` and rule `main_requires_expected_merge_parents`.

- ML-07: The checker reports not ready for root or octopus promotion topology with `task_lifecycle.unsupported_promotion_topology` and rule `main_requires_direct_or_merge_promotion`.

Workflow boundary:

- WF-01: The workflow reads `ready` from canonical main lifecycle evidence after it validates main promotion association.

- WF-02: The workflow blocks in phase `main` when main lifecycle `ready` is not exactly true.

- WF-03: The workflow reports `workflow.main_lifecycle_not_ready` with rule `main_lifecycle_is_ready` for WF-02.

- WF-04: The workflow selects main CI or cleanup only after main lifecycle `ready` is true.

Cleanup boundary:

- CL-01: `record-branch-cleanup` accepts zero or more `--branch` values.

- CL-02: The producer preserves current duplicate validation and branch lookup when the operator supplies branches.

- CL-03: The producer accepts zero branches only after it validates canonical main promotion evidence for the task and run.

- CL-04: The producer writes complete cleanup evidence with an empty `remaining_branches` list when zero branches and direct promotion evidence exist.

- CL-05: The producer blocks before it writes cleanup evidence when zero branches and merge, missing, or invalid main promotion evidence exist.

## Proposed Architecture

The lifecycle checker owns Git promotion topology validation.

The workflow owns lifecycle readiness gating.

The cleanup producer owns direct promotion cleanup evidence.

```text
Operator -> Lifecycle checker -> Evidence catalog -> Workflow
    |              |                  |               |
    |              v                  v               v
    +------> Cleanup producer ----> Cleanup record -> Completion
```

## Key Interactions

```text
Operator       Lifecycle checker      Workflow       Cleanup producer
   |                  |                  |                  |
   | main revisions   |                  |                  |
   |----------------->|                  |                  |
   |                  | main record      |                  |
   |                  |----------------->|                  |
   |                  |                  | read ready       |
   |                  |                  |----------------->|
   | zero branches    |                  |                  |
   |-------------------------------------------------------->|
   |                  |                  | direct record    |
   |                  |                  |----------------->|
```

## Data Model

The main lifecycle record keeps its existing `ready` and `diagnostics` fields.

The cleanup record keeps its existing `branch_cleanup_complete` and `remaining_branches` fields.

The evidence catalog schema does not change.

## APIs / Interfaces

```text
kotekomi-agent lifecycle-check <manifest> --phase main
  --main-base <revision> --verified <revision> --head <revision>
```

```text
kotekomi-agent record-branch-cleanup
  [--branch <branch-name> ...] --task-id <task-id> --run <run-id>
```

## Behavior & Domain Rules

The checker resolves all main revisions before it validates promotion topology.

The checker uses Git parent order for merge promotion validation.

The checker treats a one-parent head as direct before it compares `head` and `verified`.

The cleanup producer reads only validated canonical main promotion evidence for zero-branch cleanup.

The cleanup producer does not delete branches.

The workflow treats a non-ready main lifecycle record as a terminal blocked state for the run status response.

## Acceptance Criteria

- AC-ML-01: CLI tests prove valid direct and merge main lifecycle results.

- AC-ML-02: CLI tests prove direct mismatch, merge mismatch, root, and octopus results use the required diagnostics.

- AC-WF-01: Workflow tests prove a false main lifecycle record blocks even when main CI and cleanup records exist.

- AC-WF-02: Workflow tests prove a true main lifecycle record advances to the next missing main evidence.

- AC-CL-01: CLI tests prove zero-branch cleanup writes complete evidence only for validated direct main promotion evidence.

- AC-CL-02: CLI tests prove zero-branch cleanup blocks for merge, missing, and invalid main promotion evidence.

## Reference Implementations

- Main lifecycle checks: follow `packages/devtools/src/kotekomi_devtools/task_lifecycle.py`.

- Lifecycle CLI evidence: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

- Cleanup evidence: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

- Workflow status: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

## Constraints and Halt Conditions

The implementer stops when Git cannot resolve a required revision.

The implementer does not change existing main lifecycle evidence fields.

The implementer does not accept zero-branch cleanup without validated direct main promotion evidence.
