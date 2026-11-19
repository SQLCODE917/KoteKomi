# Specification Commit Selection

## Context & Problem

The Harness `implement-tdd` start requires a clean local `main` equal to `origin/main`.
The same-branch workflow places the TDD and Task Manifest V2 on an existing feature branch.
That branch also carries implementation commits and review feedback.
The current check rejects a valid, immutable specification commit on that branch.
The operator selects the specification commit explicitly.
The Harness records that commit and its digests before implementation advances the branch.

Primary end-to-end flow:

1. The operator commits the TDD and Task Manifest V2 on the existing feature branch.
2. The operator pushes the branch.
3. The operator runs `implement-tdd <tdd-path> --specification-commit <sha>`.
4. The Harness resolves the full commit SHA and requires it to be an ancestor of `HEAD`.
5. The Harness validates the TDD and Task Manifest at that commit against the TDD binding.
6. The Harness records the specification commit, manifest digest, and existing branch.
7. Later implementation commits and pushes do not change the recorded specification commit.

## Goals

- A valid specification commit on the existing branch starts a V2 run.
- The recorded specification commit remains immutable after implementation pushes.
- Missing or mismatched specification input blocks with a durable blocked status.
- The existing `main` start path retains its behavior.

## Requirements

### Specification commit selection

- SCS-01: `implement-tdd` accepts `--specification-commit <sha>`.
- SCS-02: The option requires a full lowercase 40-character commit SHA.
- SCS-03: The selected commit must be an ancestor of `HEAD`.
- SCS-04: The worktree must be clean.
- SCS-05: The selected commit's TDD bytes must match the TDD binding digest.
- SCS-06: The selected commit's Task Manifest bytes must match the working-tree Task Manifest.
- SCS-07: The Task Manifest at the selected commit must validate and bind to the TDD.
- SCS-08: The Harness records `specification_revision` as the selected commit and `manifest_sha256` as the selected manifest digest.
- SCS-09: A persisted specification record with the same manifest digest is reused; a different selected commit blocks.
- SCS-10: A later `HEAD` advance does not change a persisted specification record.

### Existing branch

- SCS-11: With `--specification-commit`, the Harness records the current non-`main` branch as the feature branch.
- SCS-12: The existing branch must have a remote ref that contains the selected commit.
- SCS-13: The Harness does not create or push a new feature branch in this mode.
- SCS-14: The recorded feature branch keeps the selected specification revision.

### Blocked status

- SCS-15: Invalid or missing specification input returns exit code 1 with a clear diagnostic.
- SCS-16: The same blocked status and diagnostics persist in the run record.
- SCS-17: Repeating the command resumes the blocked run.

### Retained behavior

- SCS-18: `implement-tdd` without `--specification-commit` retains the clean current-main path.
- SCS-19: Existing verification, receipt, and candidate checks remain unchanged.

## Proposed Architecture

The implementation workflow owns specification commit selection.
The Task Manifest validator owns manifest validation.
The lifecycle evidence producer owns existing-branch evidence.

```text
Operator -> implement-tdd -> selected commit
                             -> TDD binding
                             -> Task Manifest
                             -> run specification evidence
                             -> existing feature branch evidence
```

## Data Model

The existing specification record and feature branch record remain the canonical records.
The specification record stores the selected commit and manifest digest.
The feature branch record stores the existing branch and its revisions.
No new record type is introduced.

## APIs / Interfaces

`kotekomi-agent implement-tdd <tdd-path> --specification-commit <sha>`.

## Behavior & Domain Rules

The selected commit is immutable.
The working tree must match the selected TDD and Task Manifest bytes.
The Harness reuses persisted specification evidence.
The Harness does not merge the specification branch.

## Acceptance Criteria

- AC-SCS-01: Acceptance tests prove a valid specification commit on an existing non-main branch starts a run.
- AC-SCS-02: Acceptance tests prove the default main-only gate rejects the same branch without the option.
- AC-SCS-03: Acceptance tests prove an implementation commit and push do not change the persisted specification revision.
- AC-SCS-04: Acceptance tests prove a mismatched TDD at the selected commit blocks with a clear diagnostic.
- AC-SCS-05: Acceptance tests prove the blocked status and diagnostics persist in the run record.
- AC-SCS-06: Existing feature branch default tests remain passing.

## Reference Implementations

- Workflow: `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Feature branch evidence: `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.
- CLI: `packages/devtools/src/kotekomi_devtools/cli.py`.
- Existing tests: `packages/devtools/tests/acceptance/test_feature_branch_default_contract.py`.

## Constraints and Halt Conditions

The implementation does not change the `main` start path.
The implementation does not create or push a new feature branch in the explicit specification mode.
The implementation does not modify the CLI classification fix.
