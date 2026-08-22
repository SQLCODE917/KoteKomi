# Historical Merge Handoff Closure

## Context & Problem

The Harness can close a superseded task when one candidate commit has the same patch as a successor candidate.

An older feature branch can contain a receipt merge after its delivered code commits.

The current closure command cannot compare that delivered code range.

The **delivery base** is the original run specification revision.

The **delivery head** is the first-parent commit before the receipt merge lineage at the original feature tip.

The **delivery patch** is the stable Git patch ID for the net diff from delivery base to delivery head.

Primary end-to-end flow:

1. A successor completes and reaches `main`.
2. The closure command reads the original specification and feature-tip history.
3. The command resolves the delivery head through receipt-only and receipt-merge commits.
4. The command compares the original delivery patch with the successor delivery patch.
5. The command retains the original feature tip by tag and deletes the original feature branch when both patches match.

## Goals

- A successor can close a historical task that used a receipt merge.
- The closure records the code range that the successor delivered.
- A receipt-only history difference does not prevent valid supersession.

## Requirements

### Closure producer

- HC-01: The closure command reads the original specification revision from canonical evidence.
- HC-02: The command requires the supplied handoff commit to equal the original local feature tip.
- HC-03: The command requires the remote feature tip to be reachable from the successor target.
- HC-04: The command resolves a delivery head by following first parents through receipt-only commits and receipt merges.
- HC-05: The command stops at the first non-receipt first-parent commit.
- HC-06: The command computes the original delivery patch from delivery base through delivery head.
- HC-07: The command computes the successor delivery patch from successor specification through successor candidate.
- HC-08: The command requires the two delivery patches to match before it publishes a superseded result.

### Receipt history boundary

- RH-01: A receipt-only commit has one parent, changes one canonical Verification Receipt path, and binds that parent.
- RH-02: A receipt merge has two parents and has a valid receipt-only commit as its second parent.
- RH-03: The command rejects a merge that does not satisfy RH-02.
- RH-04: The command does not omit a non-receipt product commit from either delivery patch.

### Evidence

- EV-01: Superseded task-result evidence records delivery base, delivery head, and delivery patch.
- EV-02: The handoff tag remains at the supplied original feature tip.
- EV-03: Existing single-commit handoff closure remains valid when its delivery range has one commit.

## Proposed Architecture

```text
Original feature tip       Completed successor
        |                         |
        v                         v
Historical handoff resolver   Successor evidence
        |                         |
        +------> delivery patches +
                         |
                         v
                Superseded-task closure
```

The closure producer owns receipt lineage validation and delivery patch comparison.

The evidence catalog owns the additional supersession fields.

## Key Interactions

```text
Operator -> Closure producer: original run and successor run
Closure producer -> Git: resolve receipt lineage at feature tip
Closure producer -> Git: compare delivery patches
Closure producer -> Evidence catalog: record superseded result
Closure producer -> Git: tag feature tip and delete feature branch
```

## Data Model

The superseded task-result record adds these fields.

```text
delivery_base_commit: full commit ID
delivery_head_commit: full commit ID
delivery_patch_id: SHA-1 patch ID
successor_delivery_base_commit: full commit ID
successor_delivery_patch_id: SHA-1 patch ID
```

## APIs / Interfaces

`kotekomi-agent close-superseded-task` keeps its public arguments.

## Behavior & Domain Rules

The closure command validates receipt history before it excludes receipt lineage from delivery comparison.

The closure command retains every original feature-tip commit through the handoff tag.

The closure command leaves both feature references unchanged when delivery patches differ.

## Acceptance Criteria

- AC-HC-01: Disposable Git tests prove a receipt merge closes when its first-parent delivery range matches the successor delivery range.
- AC-HC-02: Tests prove a valid receipt-only commit before the original tip does not change the delivery patch.
- AC-RH-01: Tests prove malformed receipt-only commits and invalid receipt merges block closure.
- AC-EV-01: Tests prove superseded result evidence records both delivery ranges and their matching patch ID.
- AC-EV-02: Existing single-commit closure tests continue to pass.

## Reference Implementations

- Existing closure behavior: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.
- Receipt validation: `packages/devtools/src/kotekomi_devtools/task_scope.py`.
- Closure contracts: `packages/devtools/tests/acceptance/test_superseded_task_closure_contract.py`.

## Constraints and Halt Conditions

The implementation must not delete a feature branch before it validates both delivery patches.

The implementation must not accept a receipt directory by path prefix alone.
