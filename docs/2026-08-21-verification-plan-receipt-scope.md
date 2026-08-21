# TDD Verification Plan Receipt Scope

## Context & Problem

The Harness commits a Verification Receipt after it verifies an implementation candidate.

The scope audit excludes a valid receipt-only commit from the implementation change set.

The verification planner currently includes the same receipt file in its changed-path list.

The planner then blocks the candidate because a Task Manifest cannot name a future receipt path.

The **receipt-only commit** is a one-parent commit that changes one candidate Verification Receipt.

The **trusted receipt-only commit** is a receipt-only commit whose path, parent, and JSON identity agree.

Primary end-to-end flow:

1. An implementation candidate changes the paths that its Task Manifest allows.
2. The independent verifier commits a Verification Receipt that binds the candidate.
3. The verification planner reads the specification-to-candidate revision range.
4. The planner excludes each trusted receipt-only commit from the changed-path list.
5. The planner keeps every other changed path and applies its normal fail-closed coverage rule.

## Goals

- A valid Verification Receipt does not make its verified candidate unplannable.
- The planner rejects arbitrary files under the receipt directory.
- The planner reports the same implementation paths that the scope audit reports.

## Requirements

### Verification planner

- VP-01: The planner excludes the path from a trusted receipt-only commit before it checks Task Manifest coverage.
- VP-02: The planner excludes the path from a trusted receipt-only commit before it selects touched-path checks.
- VP-03: The planner preserves sorted changed-path order after it excludes trusted receipt paths.

### Trusted receipt boundary

- TR-01: A trusted receipt-only commit has exactly one parent and changes exactly one path.
- TR-02: The path is `.agent/receipts/verification/<task-id>/<candidate-revision>/<profile>/attempt-<ordinal>.json`.
- TR-03: `<profile>` is `portable-local` or `authoritative-linux`.
- TR-04: `<ordinal>` has four decimal digits and represents an integer greater than zero.
- TR-05: The receipt JSON is an object.
- TR-06: The receipt JSON contains `receipt_kind`, `task_id`, `candidate_revision`, `profile`, and `attempt` values that equal the path values.
- TR-07: The receipt JSON has `receipt_kind` equal to `candidate_verification`.
- TR-08: The candidate revision in the path and receipt equals the only parent of the commit.

### Failure behavior

- FB-01: The planner applies normal changed-path coverage to a receipt path when any trusted receipt rule fails.
- FB-02: The planner does not add a path-prefix allowlist for `.agent/receipts/verification/`.
- FB-03: The planner does not change the Task Manifest schema.

## Proposed Architecture

```text
Git revision range
        |
        v
Verification planner
   |             |
   v             v
Receipt validator Changed-path coverage
   |             |
   +-- trusted --+-- exclude receipt path
   |
   +-- invalid ---- retain receipt path
```

The verification planner owns receipt-only commit recognition for its revision range.

The existing scope audit keeps its existing receipt-only commit behavior.

The Task Manifest continues to own implementation-path coverage.

## Key Interactions

```text
Verifier -> Git: commit receipt R with candidate C as parent
Planner -> Git: inspect commits from S through C
Planner -> Receipt validator: validate each one-path commit
Receipt validator -> Planner: trusted or invalid
Planner -> Verification plan: changed paths and required checks
```

## Data Model

This TDD does not create a record or change an existing schema.

The planner reads the existing Verification Receipt JSON at the changed path in each commit.

## APIs / Interfaces

The public `kotekomi-agent verification-plan` command keeps its current arguments and result shape.

## Behavior & Domain Rules

The planner evaluates receipt trust per commit rather than per path prefix.

The planner retains a malformed receipt path in the changed-path list.

The planner retains a receipt path when its commit also changes another path.

The planner retains a receipt path when its receipt binds a candidate other than the commit parent.

The planner retains a receipt path when its path and receipt fields disagree.

## Acceptance Criteria

- AC-VP-01: A disposable Git repository proves that the planner excludes one valid receipt-only commit and reports the candidate implementation path.
- AC-VP-02: Tests prove that a receipt-only commit does not create an uncovered-path diagnostic or touched-path check.
- AC-TR-01: Tests prove that a malformed receipt, a mismatched receipt, and a receipt commit with another changed path remain uncovered and block the plan.
- AC-FB-01: Tests prove that an arbitrary receipt-directory file remains uncovered and blocks the plan.
- AC-FB-02: Existing scope and budget receipt tests continue to pass.

## Reference Implementations

- Receipt-only commit recognition: follow `packages/devtools/src/kotekomi_devtools/task_scope.py`.
- Candidate receipt validation: follow `packages/devtools/src/kotekomi_devtools/candidate_verifier.py`.
- Planner contract tests: follow `packages/devtools/tests/acceptance/test_verification_plan_contract.py`.

## Constraints and Halt Conditions

The implementation must halt if receipt validation requires a Task Manifest schema change.

The implementation must not add a compatibility path or accept a receipt that fails a listed trusted receipt rule.
