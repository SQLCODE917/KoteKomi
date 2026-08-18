# TDD Merged Feature Branch Reconciliation

## Context & Problem

The feature branch flow requires a no-fast-forward merge and successful main CI before task closure.

Two earlier feature branches reached `main` before the Harness produced complete promotion evidence.

The Harness retains their candidate CI records.

One recorded candidate CI failure reflects a missing later dependency.

The Harness does not yet bind those historic merges to final main CI.

The Harness does not yet write a portable result tag or delete those merged feature branches.

The **candidate commit** is commit `C` in existing `candidate_commit` evidence.

The **main base** is the first parent `H` of an existing merge commit.

The **merge commit** is commit `M` with ordered parents `H` and `C`.

The **final main commit** is commit `F` at `origin/main` after `M`.

The **result tag** is the annotated Git tag `kotekomi/tasks/<task-id>/result`.

The **reconciliation** records an existing merge, final main CI, result tag, and branch cleanup.

Primary end-to-end flow:

1. An operator supplies `M`, `F`, and a successful CI result for `F`.

2. The reconciliation producer validates the task evidence and existing Git topology.

3. The reconciliation producer records the existing merge and ready main lifecycle evidence for `M`.

4. The reconciliation producer records successful final main CI evidence for `F`.

5. The reconciliation producer pushes the result tag at `F`.

6. The reconciliation producer deletes the local and remote feature branch.

7. The workflow marks the run complete after it validates result and cleanup evidence.

## Goals

- An operator can close any eligible already-merged feature branch with portable evidence.

- The Harness preserves historical failed candidate CI evidence.

- The result tag identifies the final main revision that CI validated.

- The Harness removes a reconciled feature branch after it publishes the result tag.

- Metrics report reconciled closure without requiring a receipt-chain record.

## Requirements

### Reconciliation boundary

- RB-01: `kotekomi-agent reconcile-merged-feature-branch` requires task, run, promotion, final-main, CI-result, and state-root arguments.
- RB-02: The command reads valid Task Manifest V2, specification revision, feature-branch, and candidate-commit evidence.
- RB-03: The command derives the only permitted branch name as `feature/<task-id>`.
- RB-04: The command resolves `M` from `--promotion` and `F` from `--final-main` as local commits.
- RB-05: The command requires `F` to equal `origin/main`.
- RB-06: The command requires `M` to be an ancestor of `F`.
- RB-07: The command requires `M` to have exactly two ordered parents.
- RB-08: The command requires the first parent of `M` to equal specification revision `H`.
- RB-09: The command requires the second parent of `M` to equal candidate commit `C`.
- RB-10: The command requires the remote feature tip to equal `C` before cleanup.
- RB-11: The command requires a valid CI result with `conclusion = success` and `head_sha = F`.
- RB-12: The command does not replace candidate CI evidence.
- RB-13: The command blocks before it writes reconciliation evidence when any RB validation fails.

### Main evidence boundary

- ME-01: The command writes merge main-promotion evidence with commits `M`, `H`, and `C`.
- ME-02: The command writes ready main-lifecycle evidence for `M` after it validates RB-07 through RB-09.
- ME-03: The command writes successful main-CI evidence for `F` that binds promotion `M`.
- ME-04: The evidence catalog trusts `validated_promotion_commit` in `main_ci` evidence.
- ME-05: The workflow requires reconciliation main CI to bind the recorded promotion commit.

### Result and cleanup boundary

- RC-01: The command creates the annotated result tag at `F` after it writes successful final main CI evidence.
- RC-02: The result tag message is canonical JSON with the fields in the reconciliation result-tag model.
- RC-03: The result tag message sets `outcome = completed`.
- RC-04: The command pushes the result tag to `origin` without force.
- RC-05: A matching existing result tag makes a retry succeed.
- RC-06: A different existing result tag blocks branch deletion.
- RC-07: The command writes `task_result` evidence after `origin` contains the matching result tag.
- RC-08: Task-result evidence uses phase `complete`, subject ID `result`, canonical path, and state path scope.
- RC-09: Task-result evidence contains the fields in the task-result model.
- RC-10: The evidence catalog trusts every field in RC-09.
- RC-11: The command deletes local `feature/<task-id>` after it pushes the result tag.
- RC-12: The command deletes `origin/feature/<task-id>` after local deletion.
- RC-13: The command uses non-force branch deletion.
- RC-14: The command writes cleanup evidence after every local or remote deletion attempt.
- RC-15: Cleanup evidence is complete only when neither feature ref remains.
- RC-16: A result-tag publication failure retains the branch and writes no task-result evidence.
- RC-17: A branch deletion failure retains task-result evidence and writes incomplete cleanup evidence.

### Workflow and metrics boundary

- WM-01: The workflow reports terminal complete from completed task-result evidence and complete cleanup evidence.
- WM-02: The workflow evaluates WM-01 before candidate CI gates.
- WM-03: The workflow accepts normal or reconciliation main CI that binds the recorded promotion commit.
- WM-04: The workflow retains normal feature-flow requirements when task-result evidence is absent.
- WM-05: The workflow updates active or blocked run records and index entries to complete after WM-01 succeeds.
- WM-06: The workflow retains `terminal_reason = null` for a completed run.
- WM-07: Metrics use valid task-result evidence instead of receipt-chain-status evidence for completion.
- WM-08: Metrics retain the recorded candidate CI conclusion and repair history.

## Proposed Architecture

The reconciliation producer owns validation, result publication, and feature-branch deletion.

The evidence catalog owns records and evidence events.

The workflow owns terminal run status.

The metrics collector owns completion metrics.

```text
Operator -> Reconciliation producer -> origin result tag
                   |                         |
                   v                         v
            Main evidence              Feature branch deletion
                   |                         |
                   +--------> Evidence catalog <--------+
                                      |
                                      v
                              Workflow and metrics
```

## Key Interactions

```text
Operator -> Reconciliation producer: M, F, and CI result for F
Reconciliation producer -> Git: validate H, C, M, F, and feature tip
Reconciliation producer -> Evidence catalog: main promotion, lifecycle, and CI
Reconciliation producer -> origin: push result tag at F
Reconciliation producer -> origin: delete feature branch
Reconciliation producer -> Evidence catalog: task result and cleanup
Workflow -> Run index: mark run complete
```

## Data Model

The reconciliation main CI record adds this field:

```text
validated_promotion_commit: full commit ID
```

The reconciliation result tag message uses this shape:

```text
schema_version: 1
task_id: string
implementation_run_id: string
outcome: completed
promotion_commit: full commit ID
final_main_commit: full commit ID
main_ci_sha256: SHA-256 digest
```

The task-result record uses this shape:

```text
schema_version: 1
outcome: completed
tag: kotekomi/tasks/<task-id>/result
target_commit: full commit ID
tag_message_sha256: SHA-256 digest
diagnostics: []
```

## APIs / Interfaces

```text
kotekomi-agent reconcile-merged-feature-branch
  --task-id <task-id>
  --run <implementation-run-id>
  --promotion <merge-commit>
  --final-main <main-commit>
  --ci-result <ci-result-json>
  --state-root <state-root>
```

## Behavior & Domain Rules

The command reconciles existing Git facts and does not create a merge commit.

The command does not change `origin/main`.

The command preserves candidate CI evidence, including failure records.

The command does not create receipt-chain-status evidence.

The command creates no direct-main evidence.

The command never deletes `main`.

The command returns exit code `0` after result-tag publication and cleanup evidence writing.

The command returns exit code `2` for invalid evidence, topology, CI, tag conflict, or deletion failure.

## Acceptance Criteria

- AC-RB-01: Disposable Git tests prove reconciliation of an existing two-parent merge and later final main commit.
- AC-RB-02: Tests prove changed main, wrong parents, wrong candidate, wrong feature tip, and failed CI block first.
- AC-RB-03: Tests prove a failed candidate CI record remains unchanged after reconciliation.
- AC-ME-01: Evidence catalog tests prove reconciliation main CI trusts and indexes its promotion binding.
- AC-RC-01: Tests prove the command pushes the required annotated result tag at final main.
- AC-RC-02: Tests prove matching tag retries succeed and tag conflicts retain the feature branch.
- AC-RC-03: Tests prove successful reconciliation deletes local and remote feature branches without force.
- AC-RC-04: Tests prove deletion failure records incomplete cleanup after task-result evidence.
- AC-WM-01: Workflow tests prove a valid task result and cleanup complete a blocked run.
- AC-WM-02: Workflow tests prove final main CI binds its validated promotion commit.
- AC-WM-03: Metrics tests prove task-result evidence replaces only receipt-chain-status evidence.

## Reference Implementations

- Git and CI evidence: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

- Evidence records: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Workflow status: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

- Metrics records: follow `packages/devtools/src/kotekomi_devtools/tdd_metrics.py`.

## Constraints and Halt Conditions

The implementation does not alter historical candidate CI evidence.

The implementation does not reconcile a single-parent direct-main commit.

The implementation does not delete a branch before result-tag publication.

The implementation does not force-push a branch or result tag.

The implementation halts before evidence publication when Git topology does not identify the task candidate.
