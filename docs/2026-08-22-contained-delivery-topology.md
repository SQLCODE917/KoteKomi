# Contained Delivery Topology

## Context & Problem

The Harness proves a contained delivery by reverse-applying the historic delivery diff to the successor candidate tree.
That proof accepts equivalent patches from separate Git lineages.
The closure producer also requires the remote historic feature tip to be an ancestor of the successor target.
That extra condition blocks an equivalent historic branch even when the strict diff proof succeeds.

**Handoff commit** is the commit that identifies the historic feature delivery.
**Contained delivery** is a historic delivery whose receipt-aware diff reverse-applies cleanly from the successor candidate tree.

### Primary end-to-end flow

1. An operator names a historic task run, its handoff commit, and a completed successor run.
2. The closure producer confirms that the local and remote feature tips equal the handoff commit.
3. The closure producer computes the receipt-aware historic delivery diff.
4. The closure producer reverse-applies that diff to the successor candidate tree.
5. The closure producer records supersession evidence and removes both matching feature references.

## Goals

- Operators can close an equivalent historic delivery from a separate Git lineage.
- The closure producer retains both feature references when either feature tip differs from the named handoff commit.
- The strict diff proof remains the acceptance rule for a contained delivery.

## Requirements

### Superseded closure

- CT-01: The closure producer requires the local feature tip to equal the handoff commit.
- CT-02: The closure producer requires the remote feature tip to equal the handoff commit.
- CT-03: The closure producer uses exact patch equality for an `exact` delivery relation.
- CT-04: The closure producer uses receipt-aware reverse application for a `contained` delivery relation.
- CT-05: The closure producer does not require the remote feature tip to be an ancestor of the successor target for a `contained` delivery relation.
- CT-06: The closure producer writes no result, tag, cleanup record, or run-state change when either tip check or delivery proof fails.

## Proposed Architecture

The closure producer owns feature-tip identity checks and delivery proof.
Git provides the local tip, remote tip, and candidate tree.
The evidence catalog stores the resulting superseded result and cleanup records.

```text
Historic feature refs ----> Closure producer
                                  |
                                  v
                       matching handoff commit
                                  |
                                  v
                      receipt-aware delivery diff
                                  |
                                  v
                     successor candidate tree proof
                                  |
                                  v
                            superseded result
```

## Key Interactions

```text
Operator -> Closure producer: task, run, handoff, successor
Closure producer -> Git: read local and remote feature tips
Closure producer -> Git: read historic diff and successor tree
Closure producer -> Evidence catalog: write result after proof
Closure producer -> Git: delete matching feature references
```

## Data Model

The existing superseded task-result and cleanup records remain unchanged.
This task adds no persistent record type.

## APIs / Interfaces

`kotekomi-agent close-superseded-task` retains its current arguments.
The `contained` relation accepts separate Git lineage only after the existing strict reverse-application proof passes.

## Behavior & Domain Rules

The closure producer compares both feature tips with the handoff commit before it computes delivery proof.
The closure producer treats an equal local and remote handoff as the feature-reference identity proof.
The closure producer treats a clean reverse application as the contained-delivery proof.
The closure producer does not infer containment from ancestry for a contained relation.

## Acceptance Criteria

- AC-CT-01: A disposable-Git test proves a contained closure accepts an equivalent historic delivery that is not an ancestor of the successor target.
- AC-CT-02: A disposable-Git test proves a remote tip that differs from the handoff blocks without mutation.
- AC-CT-03: Existing exact and non-contained delivery contract tests pass.
- AC-CT-04: The Harness regression checks pass through the generated verification plan.

## Reference Implementations

- Closure producer: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.
- Closure contracts: `packages/devtools/tests/acceptance/test_superseded_task_closure_contract.py`.

## Constraints and Halt Conditions

The implementation must not weaken the reverse-application proof.
The implementation must not delete a feature reference whose tip differs from the named handoff commit.
The implementation must not force-delete a Git reference.
