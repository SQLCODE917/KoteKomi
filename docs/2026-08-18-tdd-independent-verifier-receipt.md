# Independent Verifier Receipt

## Context & Problem

An implementation agent can create a candidate commit and report local check results.

The Harness does not yet create a record that an independent verifier owns.

The current generic receipt command accepts caller-selected fields and can overwrite a record.

The current verification commands can read records that the implementing agent produced.

The Harness therefore cannot prove that a receipt binds one frozen Task Manifest, one execution base, one candidate commit, and the checks that a verifier ran.

This TDD adds one independent verifier command.

The **specification commit** is Git commit `S`. It contains the accepted Leaf TDD, the Task Manifest, and every protected acceptance artifact for one task.

The **execution base** is Git commit `B`. The Task Manifest identifies `B` in `baseline_revision`.

The **candidate commit** is Git commit `C`. An implementation agent creates `C` after `S`.

The **verification branch** is the canonical Git branch that contains immutable Verification Receipt attempts for one task, candidate, and profile.

The **Verification Receipt** is canonical JSON that binds `B`, `S`, `C`, the Task Manifest, the audit result, the plan, and each check result.

The primary flow is:

1. The planning authority commits the frozen task records at `S`.
2. The implementing agent commits the candidate at `C`.
3. The verifier runs `kotekomi-agent verify-candidate` with `B`, `S`, `C`, and one profile.
4. The verifier runs every planned check in a detached worktree at `C`.
5. The verifier commits one Verification Receipt on the verification branch.

## Goals

- A verifier can produce one immutable receipt for one candidate and profile.
- A receipt identifies the exact execution base, specification commit, candidate commit, manifest bytes, audit result, plan, and check results.
- A candidate that changes a protected artifact after the specification commit receives a failed receipt.
- A verification retry preserves every earlier receipt attempt.
- The command does not use the caller worktree as verification input.

## Requirements

### Candidate topology

- CV-01: `verify-candidate` accepts `--manifest`, `--base`, `--specification`, `--candidate`, and `--profile`.
- CV-02: The command resolves each revision to a full Git commit ID.
- CV-03: The command requires `B` to be an ancestor of `S`.
- CV-04: The command requires `S` to be an ancestor of `C`.
- CV-05: The command rejects a candidate when `S` equals `C`.
- CV-06: The command reads the Task Manifest blob from `S` at `--manifest`.
- CV-07: The command validates that manifest with the existing Task Manifest validator.
- CV-08: The command requires the validated manifest `baseline_revision` to equal `B`.
- CV-09: The command requires the Task Manifest blob at `C` to equal the manifest blob at `S`.
- CV-10: The command requires the bound Leaf TDD blob at `C` to equal the bound Leaf TDD blob at `S`.

### Candidate execution

- CE-01: The command creates a detached temporary worktree at `C`.
- CE-02: The command reads the manifest from that detached worktree for audit and check planning.
- CE-03: The command runs `scope-audit` over `S..C`.
- CE-04: The command builds the existing verification plan over `S..C`.
- CE-05: The command runs every planned check with its exact argument array.
- CE-06: The command records each check exit code, status, argument array, and combined-log SHA-256 digest.
- CE-07: The command produces a failed Verification Receipt when the audit, plan, or a planned check fails.
- CE-08: The command removes its detached worktree after every terminal result.

### Verification receipt

- VR-01: The command derives the verification branch as `refs/heads/kotekomi-verification/<task-id>/<candidate-sha>/<profile>`.
- VR-02: The command derives a receipt path as `.agent/receipts/verification/<task-id>/<candidate-sha>/<profile>/attempt-<ordinal>.json`.
- VR-03: The first receipt has ordinal `0001`.
- VR-04: A later receipt increments the greatest valid prior ordinal by one.
- VR-05: The command rejects an invalid verification branch without changing its ref.
- VR-06: The command writes canonical JSON with stable key ordering and a trailing newline.
- VR-07: The receipt contains `schema_version`, `receipt_kind`, `task_id`, `attempt`, `profile`, `outcome`, `base_revision`, `specification_revision`, `candidate_revision`, `manifest`, `protected_artifacts`, `scope_audit`, `verification_plan`, `check_results`, and `diagnostics`.
- VR-08: `receipt_kind` is `candidate_verification`.
- VR-09: `outcome` is `passed` only when the topology, manifest lock, protected-artifact audit, plan, and every planned check pass.
- VR-10: The receipt does not contain a clock, random value, process identifier, or temporary path.
- VR-11: The verification commit changes exactly one receipt file.
- VR-12: The command advances the verification branch only after it commits the receipt.

### Profile and authority

- PA-01: The command accepts `portable-local` and `authoritative-linux`.
- PA-02: The portable local profile runs on every supported local platform.
- PA-03: The authoritative Linux profile requires a Linux platform.
- PA-04: This TDD records an authoritative Linux profile result but does not establish GitHub Actions identity.
- PA-05: This TDD does not promote a task to `leaf_verified` or modify an Acceptance Registry.

### Command result

- CR-01: A passed receipt causes exit code `0`.
- CR-02: A failed receipt causes exit code `1`.
- CR-03: Invalid revisions, invalid manifest state, invalid verification branch state, and unsupported profile state cause exit code `2` and create no receipt.
- CR-04: Unexpected internal failures use exit code `70`.
- CR-05: The command emits compact JSON with `status`, `schema_version`, `task_id`, `profile`, `outcome`, `receipt_path`, `receipt_sha256`, `verification_branch`, `verification_commit`, and `diagnostics`.

## Proposed Architecture

```text
Verifier
  |
  v
verify-candidate CLI
  |                 \
  v                  v
Candidate verifier   Git repository
  |                  |
  v                  v
Detached C worktree  Verification branch
  |                  |
  +-------> Receipt commit
```

The CLI parses public arguments and renders the result.

The candidate verifier owns revision validation, detached worktrees, audit execution, check execution, receipt validation, and verification-branch updates.

The existing Task Manifest validator owns manifest syntax and Task Manifest V1 rules.

The existing scope audit owns allowed-path and protected-artifact diagnostics.

The existing verification planner owns planned check selection.

The existing verification execution module owns command execution and log digest calculation.

## Key Interactions

```text
Verifier -> CLI: verify-candidate B S C profile
CLI -> Candidate verifier: validate revisions and manifest
Candidate verifier -> Git: create detached C worktree
Candidate verifier -> Scope audit: inspect S..C
Candidate verifier -> Verification planner: plan S..C checks
Candidate verifier -> Check executor: run each planned check
Candidate verifier -> Git: commit immutable receipt and advance verification branch
Candidate verifier -> CLI: return receipt result
```

The verifier creates a receipt branch from `C` when the canonical branch does not exist.

The verifier extends the canonical branch when it already contains valid receipt attempts for the same task, candidate, and profile.

The verifier rejects a branch that contains a different candidate, profile, task, invalid receipt path, invalid receipt JSON, or a non-receipt file change.

## Data Model

The repository stores each receipt under `.agent/receipts/verification/`.

The receipt uses this shape:

```text
schema_version: 1
receipt_kind: candidate_verification
task_id: string
attempt: integer
profile: portable-local | authoritative-linux
outcome: passed | failed
base_revision: full commit ID
specification_revision: full commit ID
candidate_revision: full commit ID
manifest: { path, sha256 }
protected_artifacts: [{ path, sha256 }]
scope_audit: object
verification_plan: { sha256, planned_checks }
check_results: [{ check_id, argv, status, exit_code, log_sha256 }]
diagnostics: [{ code, location, rule }]
```

The verifier sorts protected artifacts by path, check results by check ID, and diagnostics by location, code, and rule.

The verifier preserves manifest acceptance-check order in `planned_checks`.

## APIs / Interfaces

The command has this form:

```bash
kotekomi-agent verify-candidate \
  --manifest .agent/tasks/<task-id>.toml \
  --base <B> \
  --specification <S> \
  --candidate <C> \
  --profile portable-local
```

`--manifest` is a repository-relative POSIX path.

`--profile` is exactly `portable-local` or `authoritative-linux`.

The command does not accept an output path, receipt path, receipt ordinal, branch name, check override, or overwrite option.

## Behavior & Domain Rules

The verifier treats the Task Manifest path and the bound Leaf TDD path as protected artifacts even when the Task Manifest does not list them in `protected_artifacts`.

The verifier records a failed receipt for an audit failure, plan failure, or planned-check failure.

The verifier does not create a receipt for an invalid prerequisite because no candidate result exists to bind.

The verification branch contains only receipt commits. Each receipt commit has one parent. The first parent is `C`. A later parent is the preceding verification commit.

The verifier updates the branch with an expected-old-value Git ref update. A concurrent branch change causes exit code `2` and preserves the new unreferenced commit for operator inspection.

The verifier removes detached worktrees after it creates a receipt or detects an invalid prerequisite.

The later CI integration TDD will add GitHub Actions provenance before an authoritative Linux receipt can promote a task.

## Acceptance Criteria

- AC-CV-01: Disposable Git repository tests prove that a valid `B -> S -> C` candidate creates a passed receipt and one-file verification commit.
- AC-CV-02: Tests prove the receipt binds full `B`, `S`, and `C` IDs and the Task Manifest SHA-256 digest from `S`.
- AC-CV-03: Tests prove invalid ancestry, equal `S` and `C`, missing manifest blobs, manifest drift, and TDD drift exit `2` without a receipt.
- AC-CE-01: Tests prove the verifier reports protected artifact and scope failures in failed receipts.
- AC-CE-02: Tests prove the verifier runs every planned check and records one result for each planned check.
- AC-CE-03: Tests prove a failed planned check creates a failed receipt and exits `1`.
- AC-VR-01: Tests prove two attempts for one candidate/profile use immutable `attempt-0001` and `attempt-0002` receipt paths.
- AC-VR-02: Tests prove a branch with product changes, malformed receipts, or mismatched receipt bindings exits `2` without an update.
- AC-VR-03: Tests prove the command ignores a dirty caller worktree and removes detached worktrees.
- AC-PA-01: Tests prove the portable local profile works on the test host and the authoritative Linux profile rejects a non-Linux host.
- AC-CR-01: CLI tests prove compact result JSON and exit codes `0`, `1`, and `2`.

## Reference Implementations

- Task Manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.
- Scope audit: follow `packages/devtools/src/kotekomi_devtools/task_scope.py`.
- Verification planning: follow `packages/devtools/src/kotekomi_devtools/verification_plan.py`.
- Check execution: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.
- Git evidence records: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

## Constraints and Halt Conditions

The implementation must halt if a public Task Manifest V1 contract cannot identify the frozen manifest or Leaf TDD bytes from `S`.

The implementation must not modify the Acceptance Registry, task lifecycle state, or GitHub Actions workflow.

The implementation must not reuse `write-receipt` for Verification Receipts.
