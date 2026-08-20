# TDD Bootstrap Run Abort

## Context & Problem

A Bootstrap Run has specification and feature-branch evidence.

A Bootstrap Run has no candidate commit evidence.

A Bootstrap Abort record reports one attempt to remove the unchanged feature refs for a Bootstrap Run.

A Bootstrap Run can fail before any task code becomes a candidate.

The current `abandon-feature-branch` command creates a result tag for every abandoned run.

That tag makes a later retry of the same task identity impossible.

This TDD defines a non-result abort path for a Bootstrap Run.

Primary end-to-end flow:

1. The operator requests `abort-bootstrap-run` for one Bootstrap Run.
2. The Harness verifies that the remote feature tip equals the recorded specification commit.
3. The Harness deletes the unchanged local and remote feature refs with non-force Git commands.
4. The Harness writes Bootstrap Abort evidence and marks the run `bootstrap_aborted`.
5. The operator starts a later run with the same task identity.

## Goals

- The Harness removes an unchanged Bootstrap Run branch without a result tag.
- The Harness preserves result tags for runs that reached a candidate.
- The Harness permits a later run after a complete Bootstrap Abort.
- The Harness exposes incomplete branch cleanup as canonical evidence.

## Requirements

### Bootstrap abort command

- BA-01: `abort-bootstrap-run` requires `--task-id`, `--run`, and `--state-root`.
- BA-02: The command accepts an active or blocked Bootstrap Run.
- BA-03: The command requires specification and feature-branch evidence.
- BA-04: The command blocks when candidate commit, receipt, candidate CI, main promotion, main CI, task result, or cleanup evidence exists.
- BA-05: The command requires the feature branch name `feature/<task-id>`.
- BA-06: The command requires the local and remote feature tips to equal the specification revision.
- BA-07: The command deletes the local feature branch with `git branch -d`.
- BA-08: The command deletes the remote feature branch only after local deletion succeeds.
- BA-09: The command writes a Bootstrap Abort record after every deletion attempt.
- BA-10: The command never creates, deletes, or changes a result tag.
- BA-11: The command marks the run `bootstrap_aborted` only when no requested feature ref remains.
- BA-12: The command returns exit code `0` for complete branch cleanup.
- BA-13: The command returns exit code `2` with an incomplete Bootstrap Abort record when a requested feature ref remains.
- BA-14: A repeated command accepts a `bootstrap_aborted` run only when its Bootstrap Abort record reports complete branch cleanup and both feature refs remain absent.

### Run workflow

- RW-01: The workflow treats `bootstrap_aborted` as terminal.
- RW-02: The workflow permits `--new-run` after a `bootstrap_aborted` run.
- RW-03: The workflow does not require task-result evidence for a `bootstrap_aborted` run.

### Historical records

- HR-01: The Harness retains existing abandoned result tags as read-only historical records.
- HR-02: The Bootstrap Abort command does not reinterpret or replace an existing abandoned result tag.
- HR-03: A successor task identity owns a corrected implementation after a historical abandoned result tag.

## Proposed Architecture

The Bootstrap Abort producer owns Bootstrap Run validation, branch deletion, and Bootstrap Abort evidence.

The workflow owns terminal run selection.

```text
Operator -> Bootstrap Abort producer -> local and origin feature refs
                    |
                    v
             Evidence catalog -> run status
```

## Key Interactions

```text
Operator -> Harness: abort-bootstrap-run
Harness -> Evidence catalog: read specification and feature branch
Harness -> Git: verify unchanged feature tips
Harness -> Git: delete local feature branch
Harness -> Git: delete remote feature branch
Harness -> Evidence catalog: write Bootstrap Abort evidence
Harness -> Run index: mark bootstrap_aborted
```

## Data Model

The evidence catalog adds `bootstrap_abort` evidence.

The evidence type uses phase `candidate` and subject ID `bootstrap`.

The canonical state path is `<run-root>/lifecycle/bootstrap-abort.json`.

The evidence entry uses `path_scope = state` and the path `experiments/<task-id>/runs/<implementation-run-id>/lifecycle/bootstrap-abort.json`.

The record contains `schema_version`, `status`, `branch_cleanup_complete`, `remaining_branches`, and `diagnostics`.

The status value is `complete` or `incomplete`.

The evidence catalog trusts `schema_version`, `status`, `branch_cleanup_complete`, `remaining_branches`, and `diagnostics`.

The run index adds terminal status `bootstrap_aborted`.

## APIs / Interfaces

```text
kotekomi-agent abort-bootstrap-run
  --task-id <task-id> --run <implementation-run-id> --state-root <state-root>
```

## Behavior & Domain Rules

The command writes no Bootstrap Abort record before it validates BA-02 through BA-06.

The command retains the remote branch when local deletion fails.

The command writes incomplete evidence when remote deletion fails after local deletion.

The command returns exit code `0` without a new Git operation when BA-14 succeeds.

The command returns exit code `2` when existing Bootstrap Abort evidence conflicts with observed feature refs.

## Acceptance Criteria

- AC-BA-01: Disposable Git tests prove complete Bootstrap Abort deletes unchanged local and remote feature refs without a tag.
- AC-BA-02: Tests prove candidate and receipt evidence block Bootstrap Abort before branch deletion.
- AC-BA-03: Tests prove changed local or remote feature tips block Bootstrap Abort before branch deletion.
- AC-BA-04: Tests prove a local deletion failure retains the remote feature branch and writes incomplete evidence.
- AC-BA-05: Tests prove a repeated complete Bootstrap Abort succeeds only when both feature refs remain absent.
- AC-RW-01: Workflow tests prove `bootstrap_aborted` permits a new run without task-result evidence.
- AC-HR-01: Tests prove Bootstrap Abort never changes an existing result tag.

## Reference Implementations

- Branch cleanup: follow `packages/devtools/src/kotekomi_devtools/feature_branch_reconciliation.py`.
- Run status: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Canonical evidence: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

## Constraints and Halt Conditions

The implementation does not delete a branch that contains a candidate commit.

The implementation does not create a result tag.

The implementation does not change an existing result tag.
