# TDD Receipt-Aware Reconciliation

## Context & Problem

The Merged Feature Branch Reconciliation TDD requires the merge second parent to equal `candidate_commit` evidence.

The Feature Branch Verification Receipt flow merges the passed portable receipt commit instead.

The implementation candidate is the commit in `candidate_commit` evidence.

The portable receipt is the passed `candidate_verification_receipt` with profile `portable-local`.

The verified merge parent is the merge second parent.

The verified merge parent equals either the implementation candidate or the portable receipt commit.

Primary end-to-end flow:

1. An operator invokes `reconcile-merged-feature-branch` for an existing merge.
2. The reconciliation producer reads candidate and portable receipt evidence.
3. The reconciliation producer validates the verified merge parent.
4. The reconciliation producer records the verified merge parent in main evidence.
5. The reconciliation producer deletes the feature branch only after result-tag publication.

## Goals

- The Harness closes historic receipt-based feature merges with portable result and cleanup evidence.
- The Harness retains reconciliation for merges that use the implementation candidate directly.
- The Harness rejects a receipt that does not bind the recorded candidate and specification.

## Requirements

### Reconciliation producer

- RAR-01: The reconciliation producer reads `candidate_commit` evidence before it validates the merge.
- RAR-02: The reconciliation producer reads the portable receipt when the merge second parent differs from `candidate_commit`.
- RAR-03: The reconciliation producer accepts the merge second parent when it equals the implementation candidate.
- RAR-04: The reconciliation producer accepts the merge second parent when it equals the portable receipt commit.
- RAR-05: The portable receipt must report `outcome = passed`.
- RAR-06: The portable receipt must report `candidate_revision` equal to the implementation candidate.
- RAR-07: The portable receipt must report `specification_revision` equal to specification evidence.
- RAR-08: The reconciliation producer blocks before reconciliation evidence when the merge second parent matches neither accepted value.
- RAR-09: The reconciliation producer requires the remote feature tip to equal the verified merge parent before cleanup.

### Main evidence

- RME-01: The reconciliation producer writes `verified_parent_commit` equal to the verified merge parent.
- RME-02: The reconciliation producer writes `validated_promotion_commit` equal to the merge commit.
- RME-03: The workflow validates receipt-based main promotion against the portable receipt commit.

## Proposed Architecture

The reconciliation producer owns verified merge parent selection.

The evidence catalog retains the candidate and portable receipt records.

The workflow validates recorded main evidence.

```text
candidate_commit ------> Reconciliation producer -----> main evidence
portable receipt ------>             |
                                        v
                                feature cleanup
```

## Key Interactions

```text
Operator -> Reconciliation producer: existing merge
Reconciliation producer -> Evidence catalog: candidate and portable receipt
Reconciliation producer -> Git: merge parent and feature tip
Reconciliation producer -> Evidence catalog: main evidence and cleanup
```

## Data Model

The existing `main_promotion.verified_parent_commit` stores the verified merge parent.

The existing `main_ci.validated_promotion_commit` stores the merge commit.

This TDD adds no record type.

## APIs / Interfaces

`kotekomi-agent reconcile-merged-feature-branch` retains its existing arguments.

## Behavior & Domain Rules

The reconciliation producer selects the implementation candidate when the merge second parent equals that commit.

The reconciliation producer selects the portable receipt commit when RAR-05 through RAR-07 hold.

The reconciliation producer uses the selected value for RAR-09 and RME-01.

The reconciliation producer retains candidate CI evidence without replacement.

## Acceptance Criteria

- AC-RAR-01: Disposable Git tests prove reconciliation accepts a merge whose second parent equals the implementation candidate.
- AC-RAR-02: Disposable Git tests prove reconciliation accepts a merge whose second parent equals a bound passed portable receipt.
- AC-RAR-03: Tests prove failed, unbound, and wrong-specification receipts block before reconciliation evidence.
- AC-RAR-04: Tests prove cleanup requires the remote feature tip to equal the verified merge parent.
- AC-RME-01: Workflow tests prove receipt-based main promotion uses the portable receipt commit.

## Reference Implementations

- Reconciliation producer: follow `packages/devtools/src/kotekomi_devtools/feature_branch_reconciliation.py`.
- Receipt validation: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Evidence records: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

## Constraints and Halt Conditions

The implementation does not change candidate CI evidence.

The implementation does not accept an unbound receipt commit.

The implementation does not delete a feature branch before result-tag publication.
