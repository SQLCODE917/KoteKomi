# TDD Feature Branch Promotion and Completion

## Context & Problem

The feature branch flow produces a verified receipt commit `R` and candidate CI evidence for `R`.

The Harness does not yet merge `R` into `main`.

The Harness does not yet record one portable terminal task result.

The Harness does not yet delete a completed feature branch.

This TDD closes a feature-branch task after verification and candidate CI pass.

The **main base** is the `origin/main` commit `H` before promotion.

The **merge commit** is the two-parent commit `M` with ordered parents `H` and `R`.

The **result tag** is the annotated Git tag `kotekomi/tasks/<task-id>/result`.

The **completed result** is a result tag that points to `M` after successful main CI.

The **abandoned result** is a result tag that points to the final feature tip.

Primary end-to-end flow:

1. The Harness validates receipt evidence for `R` and candidate CI evidence for `R`.
2. The Harness creates and pushes no-fast-forward merge commit `M` to `origin/main`.
3. The Harness records main promotion and main lifecycle evidence for `M`.
4. Main CI validates `M`.
5. The Harness pushes the completed result tag and deletes the feature branch.
6. The Harness tags and deletes an abandoned feature branch without promoting its code.

## Goals

- The Harness promotes a verified feature tip without a manual merge step.
- Main CI validates the exact merge commit before the Harness deletes the branch.
- Every terminal task has one portable result tag.
- The Harness removes completed and abandoned feature branches automatically.
- The Harness retains direct-main records only as historical input.

## Requirements

### Promotion boundary

- PB-01: `kotekomi-agent promote-feature-branch` requires `--task-id`, `--run`, and `--state-root`.
- PB-02: The command reads valid specification, feature-branch, candidate-commit, and receipt evidence.
- PB-03: The command requires passed portable-local receipt evidence.
- PB-04: The command requires candidate CI evidence with `conclusion = success` and `head_sha = R`.
- PB-05: The command resolves `origin/main` as main base `H`.
- PB-06: The command resolves `origin/feature/<task-id>` as receipt commit `R`.
- PB-07: The command requires `R` to equal receipt evidence `receipt_commit`.
- PB-08: The command requires `R` to have only parent `C`.
- PB-09: The command requires `R` to change only the receipt evidence `receipt_path`.
- PB-10: The command creates merge commit `M` with `--no-ff` and ordered parents `H` and `R`.
- PB-11: The command blocks before it pushes when Git reports a merge conflict.
- PB-12: The command pushes `M` to `origin/main` without force.
- PB-13: A changed remote main ref causes exit code `2` and writes no main evidence.
- PB-14: The command writes main promotion evidence after `origin/main` contains `M`.
- PB-15: The command writes ready main lifecycle evidence after it validates `M`.
- PB-16: Main promotion evidence uses `promotion_kind = merge`.
- PB-17: Main promotion evidence writes `promotion_commit = M`, `parent_commit = H`, and `verified_parent_commit = R`.

### Main CI boundary

- MC-01: `record-main-ci` requires a CI result with `head_sha = M`.
- MC-02: The workflow blocks when main CI has a conclusion other than `success`.
- MC-03: The workflow reports `complete_feature_branch` after successful main CI.

### Result tag boundary

- RT-01: `complete-feature-branch` requires valid main promotion and successful main CI evidence.
- RT-02: The command creates the completed result tag at `M`.
- RT-03: `abandon-feature-branch` requires an abandoned run record.
- RT-04: The command creates the abandoned result tag at the final feature tip.
- RT-05: The result tag message is canonical JSON with `schema_version`, `task_id`, `implementation_run_id`, and `outcome`.
- RT-06: A completed result tag message contains `promotion_commit`, `receipt_commit`, and `main_ci_sha256`.
- RT-07: An abandoned result tag message contains `feature_tip` and `terminal_reason`.
- RT-08: The result tag is an annotated Git tag.
- RT-09: The command pushes the result tag to `origin` without force.
- RT-10: A matching existing result tag makes a repeated command succeed without a new tag.
- RT-11: A different existing result tag blocks branch deletion.
- RT-12: The evidence catalog adds `task_result` evidence with phase `complete` and subject ID `result`.
- RT-13: The canonical task-result record path is `results/task-result.json` with path scope `state`.
- RT-14: Task-result evidence contains `schema_version`, `outcome`, `tag`, `target_commit`, and `tag_message_sha256`.
- RT-15: Task-result evidence contains `diagnostics`.
- RT-16: The evidence catalog trusts every field in RT-14.
- RT-17: Completion commands write task-result evidence only after `origin` contains the matching result tag.
- RT-18: Evidence-index rebuilding discovers task-result evidence at the canonical task-result path.

### Cleanup boundary

- CL-01: Completion commands delete local `feature/<task-id>` after they push the result tag.
- CL-02: Completion commands delete `origin/feature/<task-id>` after they delete the local branch.
- CL-03: Completion commands use non-force branch deletion.
- CL-04: Completion commands block and retain the branch when result tag publication fails.
- CL-05: Completion commands write cleanup evidence after every local or remote feature-branch deletion attempt.
- CL-06: Cleanup evidence lists every requested feature ref that remains locally or on `origin`.
- CL-07: Cleanup evidence has `branch_cleanup_complete = true` only when no requested feature ref remains.
- CL-08: Completion commands never delete `main`.

### Workflow boundary

- WF-01: The workflow requires merge promotion and ready main lifecycle evidence in the `main` phase.
- WF-02: The workflow blocks on direct main promotion evidence.
- WF-03: The workflow requires successful main CI before completion.
- WF-04: The workflow reports `complete_feature_branch` after successful main CI.
- WF-05: The workflow reports terminal `complete` only after matching task-result evidence and complete cleanup evidence exist.

### Command result boundary

- CR-01: `promote-feature-branch` returns exit code `0` after it writes main evidence.
- CR-02: A merge conflict returns exit code `1` and leaves `origin/main` unchanged.
- CR-03: Invalid evidence or a changed remote ref returns exit code `2` without main evidence.
- CR-04: Completion commands return exit code `0` after tag publication and cleanup evidence.
- CR-05: A tag conflict returns exit code `2` without task-result or cleanup evidence.
- CR-06: A branch deletion failure returns exit code `2` with task-result evidence and incomplete cleanup evidence.

## Proposed Architecture

The promotion producer owns merge creation and main evidence publication.

The CI producer owns main CI evidence.

The completion producer owns result tags and branch deletion.

The evidence catalog owns main, task-result, and cleanup records.

The workflow owns promotion and completion gates.

```text
Feature branch -> Promotion producer -> origin/main
                      |                   |
                      v                   v
                Main evidence          Main CI evidence
                                              |
                                              v
                                  Completion producer -> Result tag and cleanup
```

## Key Interactions

```text
Promotion producer -> origin/main: read H and merge R
Promotion producer -> origin/main: push merge commit M
Main CI -> Evidence catalog: record successful CI for M
Completion producer -> origin: push result tag for M
Completion producer -> origin: delete feature branch
Completion producer -> Evidence catalog: write task-result and cleanup evidence
```

## Data Model

The completed result tag message uses this shape:

```text
schema_version: 1
task_id: string
implementation_run_id: string
outcome: completed
promotion_commit: full commit ID
receipt_commit: full commit ID
main_ci_sha256: SHA-256 digest
```

The abandoned result tag message uses this shape:

```text
schema_version: 1
task_id: string
implementation_run_id: string
outcome: abandoned
feature_tip: full commit ID
terminal_reason: operator_abandoned
```

The Harness writes this task-result record:

```text
schema_version: 1
outcome: completed | abandoned
tag: kotekomi/tasks/<task-id>/result
target_commit: full commit ID
tag_message_sha256: SHA-256 digest
diagnostics: []
```

## APIs / Interfaces

```text
kotekomi-agent promote-feature-branch
  --task-id <task-id> --run <implementation-run-id> --state-root <state-root>
```

```text
kotekomi-agent complete-feature-branch
  --task-id <task-id> --run <implementation-run-id> --state-root <state-root>
```

```text
kotekomi-agent abandon-feature-branch
  --task-id <task-id> --run <implementation-run-id> --state-root <state-root>
```

## Behavior & Domain Rules

The promotion producer uses a clean detached worktree for merge creation.

The promotion producer preserves feature branch `R` when a merge conflict occurs.

The completed result tag identifies main CI that passed after promotion.

The abandoned result tag records task closure without promoting feature code.

The completion producer deletes a branch only after it pushes its result tag.

The completion producer writes incomplete cleanup evidence when any feature ref remains after a deletion attempt.

The completion producer writes complete cleanup evidence only after Git no longer exposes the feature branch.

## Acceptance Criteria

- AC-PB-01: Disposable Git repository tests prove the command creates ordered-parent merge `M` from `H` and `R`.
- AC-PB-02: Tests prove receipt, candidate CI, remote main, and receipt topology mismatches block promotion.
- AC-PB-03: Tests prove a merge conflict leaves remote main and feature branch unchanged.
- AC-PB-04: Tests prove successful promotion writes matching main promotion and lifecycle evidence.
- AC-MC-01: Workflow tests prove main CI must validate `M` before completion.
- AC-RT-01: Tests prove completed and abandoned result tags use the required names, targets, and messages.
- AC-RT-02: Tests prove matching tag retries succeed and conflicting tags block cleanup.
- AC-RT-03: Evidence catalog tests prove task-result evidence identifies a published matching result tag.
- AC-CL-01: Tests prove completion deletes local and remote feature branches after result tag publication.
- AC-CL-02: Tests prove tag publication and branch deletion failure retain a recoverable branch state with incomplete cleanup evidence.
- AC-WF-01: Workflow tests prove direct promotion evidence blocks an active run.
- AC-WF-02: Workflow tests prove cleanup evidence completes the active feature flow.

## Reference Implementations

- Promotion evidence: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

- Lifecycle checks: follow `packages/devtools/src/kotekomi_devtools/task_lifecycle.py`.

- Evidence indexing: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Workflow status: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

## Constraints and Halt Conditions

The implementation does not create or resume direct-main runs.

The implementation does not delete a feature branch before result tag publication.

The implementation does not force-push `main`, a feature branch, or a result tag.

The implementation halts without main evidence when `origin` rejects the non-force `main` update.

The implementation halts with incomplete cleanup evidence when `origin` rejects feature-branch deletion after result-tag publication.
