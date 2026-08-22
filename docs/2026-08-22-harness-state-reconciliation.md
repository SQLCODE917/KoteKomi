# Harness State Reconciliation

## Context & Problem

The Harness can abandon a run.
The current workflow creates a new active run after it abandons the named run.
The workflow can then create an unwanted feature branch.

The Harness can record a superseded task result.
The current closure producer does not change the named run record to `superseded`.
The run record then disagrees with its canonical result evidence.

The current closure producer accepts only equal delivery patch IDs.
A completed delivery can contain a historic delivery plus required additional changes.
The Harness must retain a historic contributor only when it can prove that containment.

An **orphan branch** is a feature branch that a prior workflow defect created after a task already has a superseded result.
An orphan branch has no independent task result.

### Primary end-to-end flow

1. An operator abandons one active or blocked run.
2. The workflow records that run as terminal and reports no next action.
3. An operator closes a historic contributor with an exact or contained delivery relation.
4. The closure producer records the superseded result, updates the historic run, and removes its feature references.
5. The branch cleanup producer removes an orphan branch without changing the existing superseded result.

## Goals

- Operators can abandon one run without starting another run.
- Operators can see a run record that agrees with its terminal result evidence.
- Operators can close a contained historic delivery with reviewable Git proof.
- Operators can remove an orphan branch without replacing historic task evidence.

## Requirements

### Workflow

- WR-01: `implement-tdd --abandon-run <run-id>` accepts one active or blocked run.
- WR-02: The workflow changes only the named run to `abandoned` with terminal reason `operator_abandoned`.
- WR-03: The workflow returns the abandoned run as terminal with no next action.
- WR-04: The workflow creates no run, feature branch, specification record, or lifecycle record during abandonment.
- WR-05: A repeated abandonment of the same abandoned run returns the same terminal result.
- WR-06: A normal workflow query reports the latest abandoned run as terminal.
- WR-07: Only `--new-run` can create a run after an abandoned run.

### Superseded closure

- SC-01: `close-superseded-task` accepts `--delivery-relation exact` or `--delivery-relation contained`.
- SC-02: The command uses `exact` when the operator omits the option.
- SC-03: The command accepts `exact` only when the historic and successor delivery patch IDs match.
- SC-04: The command accepts `contained` only when the historic delivery diff reverses cleanly from the successor candidate tree.
- SC-05: The command computes the historic delivery diff from the receipt-aware delivery base and delivery head.
- SC-06: The command rejects an empty historic delivery diff for `contained`.
- SC-07: The command records `delivery_relation`, `historic_delivery_diff_sha256`, and both delivery patch IDs in the superseded result and handoff tag.
- SC-08: The command records no result, tag, cleanup, or run-state change when delivery proof fails.
- SC-09: After it writes valid superseded result and cleanup evidence, the command changes the named run to `superseded` with terminal reason `superseded_by_successor`.
- SC-10: A closure retry with matching existing superseded result and complete cleanup evidence repairs the named run state without requiring a feature branch.

### Orphan branch cleanup

- OB-01: `abandon-feature-branch` accepts an abandoned run that owns an orphan branch.
- OB-02: The producer detects an existing superseded task result from another run of the same task.
- OB-03: The producer validates the existing result tag and result evidence before cleanup.
- OB-04: The producer retains the existing superseded result tag and result evidence.
- OB-05: The producer deletes local and remote orphan branches without force.
- OB-06: The producer writes cleanup evidence for the abandoned run after both feature references are absent.
- OB-07: The producer blocks when existing terminal evidence conflicts or a feature reference remains.

## Proposed Architecture

The workflow owns run transitions.
The closure producer owns delivery proof, result evidence, and superseded transitions.
The branch cleanup producer owns orphan feature references.
The evidence catalog stores canonical result and cleanup records.

```text
Operator -> Workflow -> run record
Operator -> Closure producer -> result and handoff tags
Closure producer -> Evidence catalog -> run record
Operator -> Branch cleanup producer -> feature references
```

## Key Interactions

```text
Operator -> Workflow: abandon named run
Workflow -> Run record: write abandoned state
Workflow -> Operator: terminal result

Operator -> Closure producer: historic run and delivery relation
Closure producer -> Git: prove exact or contained delivery
Closure producer -> Evidence catalog: write superseded result and cleanup
Closure producer -> Run record: write superseded state
```

## Data Model

The superseded task-result record and handoff tag add these fields.

```text
delivery_relation: exact | contained
historic_delivery_diff_sha256: SHA-256
delivery_patch_id: SHA-1 patch ID
successor_delivery_patch_id: SHA-1 patch ID
```

An orphan branch cleanup record uses the existing cleanup shape.
It adds `terminal_result_preserved: true` only when the producer retains a superseded task result.

## APIs / Interfaces

```text
kotekomi-agent implement-tdd <tdd-path> --abandon-run <implementation-run-id>

kotekomi-agent close-superseded-task
  --task-id <task-id>
  --run <implementation-run-id>
  --successor-task-id <task-id>
  --successor-run <implementation-run-id>
  --handoff-commit <commit>
  [--delivery-relation exact|contained]

kotekomi-agent abandon-feature-branch
  --task-id <task-id>
  --run <implementation-run-id>
```

## Behavior & Domain Rules

The workflow rejects abandonment of a complete or superseded run.
The workflow never creates a branch during abandonment.

The closure producer uses the successor candidate tree for contained delivery proof.
The closure producer preserves all receipt-aware delivery history through the existing handoff tag.
The closure producer does not treat a TDD statement or a commit message as containment proof.

The orphan cleanup producer writes no `task_result` record.
The orphan cleanup producer never replace a superseded tag with an abandoned tag.

## Acceptance Criteria

- AC-WR-01: Workflow and CLI tests prove abandonment records one terminal run and creates no replacement run.
- AC-WR-02: Tests prove repeated abandonment is terminal and `--new-run` remains explicit.
- AC-SC-01: Disposable Git tests prove exact closure retains existing behavior.
- AC-SC-02: Disposable Git tests prove contained closure accepts a reversible historic delivery diff.
- AC-SC-03: Disposable Git tests prove empty, non-contained, and malformed receipt deliveries block before mutation.
- AC-SC-04: Tests prove valid existing supersession evidence repairs a stale run record without a branch.
- AC-OB-01: Disposable Git tests prove orphan cleanup preserves a matching superseded result and deletes both feature references.
- AC-OB-02: Tests prove conflicting terminal evidence and failed cleanup remain explicit.
- AC-EC-01: Evidence catalog tests prove the new supersession and cleanup fields validate and rebuild.

## Reference Implementations

- Workflow records: `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Superseded closure: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.
- Feature cleanup: `packages/devtools/src/kotekomi_devtools/feature_branch_promotion.py`.
- Canonical evidence: `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

## Constraints and Halt Conditions

The implementation must not force-push or force-delete a Git reference.
The implementation must not modify `origin/main`.
The implementation must not create historic candidate, verification, promotion, or CI evidence.
The implementation must preserve a historic reference when strict Git proof fails.
