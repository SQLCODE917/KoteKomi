# TDD Feature Branch Verification Receipt

## Context & Problem

The independent verifier currently writes each Verification Receipt to a permanent verification branch.

The workflow cannot discover that receipt from its run evidence catalog.

The feature branch must contain every task commit until promotion.

This TDD moves each active Verification Receipt to the task feature branch.

The **implementation candidate** is the feature-branch code commit `C` that the verifier checks.

The **receipt commit** is the one-parent feature-branch commit `R` that contains one Verification Receipt for `C`.

The **receipt evidence record** is run-scoped evidence that identifies `R` and its receipt file.

The **verification receipt commit** is a commit that changes one receipt file and whose receipt binds its parent.

This TDD supersedes every verification-branch storage rule in
[Independent Verifier Receipt](2026-08-18-tdd-independent-verifier-receipt.md) for active Harness runs.

Primary end-to-end flow:

1. The implementation agent pushes implementation candidate `C` to `feature/<task-id>`.
2. The verifier runs `verify-candidate` in a detached worktree at `C`.
3. The verifier appends passed or failed receipt commit `R` to the feature branch.
4. The verifier records receipt evidence for `R`.
5. Candidate CI validates `R`.
6. A later promotion TDD merges `R` into `main`.

## Goals

- The feature branch contains all active task commits before promotion.
- The workflow and metrics discover verifier results from canonical run evidence.
- A retry preserves each earlier receipt attempt in feature history.
- A candidate CI run validates the exact feature tip that promotion merges.
- The verifier leaves no extra verification branch to clean up.

## Requirements

### Receipt commit boundary

- RC-01: `verify-candidate` keeps CV-01 through CV-10 of the independent verifier receipt TDD.
- RC-02: `verify-candidate` keeps CE-01 through CE-08 of the independent verifier receipt TDD.
- RC-03: The command requires `--task-id`, `--run`, and `--state-root`.
- RC-04: The command requires the Task Manifest task ID to equal `--task-id`.
- RC-05: The command reads valid specification, feature-branch, and candidate-commit evidence.
- RC-06: The command requires specification evidence to equal `S`.
- RC-07: The command requires feature-branch evidence to name `feature/<task-id>` at `S`.
- RC-08: The command requires candidate-commit evidence to equal `C`.
- RC-09: The command requires `origin/feature/<task-id>` to equal `C` before it commits a receipt.
- RC-10: The command recognizes a matching receipt by task ID, candidate ID, and profile.
- RC-11: A matching receipt follows VR-07 through VR-10 of the independent verifier receipt TDD.
- RC-12: A matching receipt uses a verification receipt commit.
- RC-13: The command determines an ordinal from valid matching receipts reachable from `C`.
- RC-14: The command writes each receipt under `.agent/receipts/verification/`.
- RC-15: The command uses the receipt path and ordinal rules from VR-02 through VR-04.
- RC-16: The command creates `R` with `C` as its only parent.
- RC-17: The command changes exactly the new receipt file in `R`.
- RC-18: The command pushes `R` to `origin/feature/<task-id>` without force.
- RC-19: A changed remote feature ref causes exit code `2` and writes no receipt evidence.
- RC-20: A passed audit and check result creates a passed receipt.
- RC-21: A failed audit, plan, or check result creates a failed receipt.

### Repair history boundary

- RH-01: An implementation agent creates a repair commit after a failed receipt commit.
- RH-02: The next implementation candidate can descend from a failed receipt commit.
- RH-03: Scope and budget audits ignore a commit only when it has one parent, changes one Verification Receipt path, and the receipt binds that parent as its candidate revision.
- RH-04: Scope and budget audits validate every non-receipt commit in `S..C`.
- RH-05: An audit rejects a receipt-path change that is not a verification receipt commit.

### Receipt evidence boundary

- RE-01: The evidence catalog adds `candidate_verification_receipt`.
- RE-02: The receipt evidence phase is `verification`.
- RE-03: The receipt evidence subject ID equals its verification profile.
- RE-04: Portable-local receipt evidence uses `receipts/candidate-verification-portable-local.json`.
- RE-05: Authoritative receipt evidence uses `receipts/candidate-verification-authoritative-linux.json`.
- RE-06: Receipt evidence contains `schema_version`, `outcome`, and `profile`.
- RE-07: Receipt evidence contains `receipt_path`, `receipt_sha256`, and `receipt_commit`.
- RE-08: Receipt evidence contains `base_revision`, `specification_revision`, and `candidate_revision`.
- RE-09: Receipt evidence contains `diagnostics`.
- RE-10: The evidence catalog trusts every field in RE-06 through RE-08.
- RE-11: The verifier writes receipt evidence only after `origin/feature/<task-id>` contains `R`.
- RE-12: Evidence-index rebuilding discovers each fixed receipt evidence path.

### Workflow and CI boundary

- WC-01: The workflow requires portable-local receipt evidence in the `verification` phase.
- WC-02: The workflow reports `verify_candidate` when portable-local receipt evidence is missing.
- WC-03: The workflow derives verifier arguments from canonical manifest and run evidence.
- WC-04: The workflow emits `--profile portable-local`.
- WC-05: The workflow blocks when portable-local receipt evidence has `outcome` other than `passed`.
- WC-06: The workflow blocks when receipt candidate or specification revisions differ from run evidence.
- WC-07: Candidate CI evidence must identify receipt commit `R` as `head_sha`.
- WC-08: The workflow blocks when candidate CI `head_sha` differs from receipt commit `R`.
- WC-09: `receipt-chain-status` reads canonical receipt evidence.
- WC-10: The command reads the referenced receipt blob from `receipt_commit`.
- WC-11: The command requires `receipt_commit` to be an ancestor of the main promotion commit.
- WC-12: The command records one present portable-local receipt for a matching receipt.

### Command result boundary

- CR-01: A passed receipt returns exit code `0` and writes receipt evidence.
- CR-02: A failed receipt returns exit code `1` and writes receipt evidence.
- CR-03: An invalid candidate or changed remote feature ref returns exit code `2` without receipt evidence.
- CR-04: The command result contains `status`, `schema_version`, `task_id`, `profile`, and `outcome`.
- CR-05: The command result contains `receipt_path`, `receipt_sha256`, `receipt_commit`, and `diagnostics`.

## Proposed Architecture

The candidate verifier owns receipt creation and feature-tip validation.

The scope and budget auditors own receipt-commit exclusion.

The evidence catalog owns receipt evidence indexing.

The implementation workflow owns receipt and candidate-CI gating.

```text
Verifier -> Candidate verifier -> feature branch
                 |                    |
                 v                    v
          Detached C worktree    Receipt evidence record
                                        |
                                        v
                                  Workflow and candidate CI
```

## Key Interactions

```text
Implementation agent -> feature branch: push implementation candidate C
Verifier -> Candidate verifier: verify C
Candidate verifier -> feature branch: push receipt commit R
Candidate verifier -> Evidence catalog: write receipt evidence for R
Candidate CI -> feature branch: validate R
Workflow -> Evidence catalog: require passed receipt and CI for R
```

## Data Model

The feature branch keeps the existing Verification Receipt JSON shape.

The Harness writes this receipt evidence record:

```text
schema_version: 1
outcome: passed | failed
profile: portable-local | authoritative-linux
receipt_path: repository-relative POSIX path
receipt_sha256: SHA-256 digest
receipt_commit: full commit ID
base_revision: full commit ID
specification_revision: full commit ID
candidate_revision: full commit ID
diagnostics: []
```

The receipt path remains `.agent/receipts/verification/<task-id>/`.

The path contains the candidate ID, profile, and attempt ordinal from the independent verifier receipt TDD.

## APIs / Interfaces

```text
kotekomi-agent verify-candidate --manifest <manifest> --base <B>
  --specification <S> --candidate <C> --profile portable-local
  --task-id <task-id> --run <implementation-run-id> --state-root <state-root>
```

The workflow derives every command argument.

## Behavior & Domain Rules

The verifier creates a receipt commit after it completes detached-worktree checks.

The verifier creates failed receipts for candidate results that fail verification.

The verifier creates no receipt for an invalid candidate.

The verifier never creates or updates a verification branch.

The promotion TDD merges receipt commit `R` into `main`.

Historical direct-main evidence remains readable but produces no new receipt.

## Acceptance Criteria

- AC-RC-01: Disposable Git repository tests prove a passed candidate pushes receipt commit `R` to the feature branch.
- AC-RC-02: Tests prove a failed candidate pushes a failed receipt commit to the feature branch.
- AC-RC-03: Tests prove `R` has parent `C` and changes one receipt file.
- AC-RC-04: Tests prove a repair candidate retains prior failed receipt history.
- AC-RH-01: Audit tests prove valid receipt commits do not violate scope or budget.
- AC-RH-02: Audit tests prove arbitrary receipt-path changes block scope validation.
- AC-RE-01: Tests prove the verifier indexes receipt evidence only after it pushes `R`.
- AC-RE-02: Evidence catalog tests prove receipt evidence has the required path and trusted fields.
- AC-RE-03: Evidence index rebuilding finds the fixed receipt evidence record.
- AC-WC-01: Workflow tests prove missing receipt evidence suggests a complete verifier command.
- AC-WC-02: Workflow tests prove failed and mismatched receipt evidence block the run.
- AC-WC-03: Workflow tests prove candidate CI for `C` blocks after receipt commit `R` exists.
- AC-WC-04: Receipt-chain tests prove receipt commit `R` must reach main promotion ancestry.

## Reference Implementations

- Candidate verification: follow `packages/devtools/src/kotekomi_devtools/candidate_verifier.py`.

- Scope and budget audits: follow `packages/devtools/src/kotekomi_devtools/task_scope.py` and `task_budget.py`.

- Receipt status: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- Evidence catalog: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

## Constraints and Halt Conditions

The implementation does not promote a feature branch.

The implementation does not delete a feature branch.

The implementation does not create or update a verification branch.

The implementation preserves historical direct-main evidence as read-only input.
