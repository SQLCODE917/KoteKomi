# Reduce Harness Coordination

Status: Authorized by the operator as the KoteKomi increment of Spymaster's coordination work.

## Context & Problem

The implementing agent delivers code on a feature branch while the Spymaster reviews its commits.
PR 11 required three Harness runs after cumulative line counts and manifest changes blocked the same task.
The accepted behavior did not change between those runs.
This increment will keep code-size feedback advisory and preserve one run through a bounded manifest amendment.
A Task Manifest defines the implementation boundary.
An amendment changes allowed paths or budget values while preserving the accepted behavior and verification requirements.

Primary end-to-end flow:

1. The implementing agent commits a correction and reads the Harness report.
2. The Harness reports code-size excess as advisory feedback.
3. The Spymaster commits an authorized manifest amendment when the same task needs another implementation path.
4. The Spymaster applies the amendment to the idle run with a reason.
5. The Harness preserves earlier evidence and requires fresh candidate verification in that run.

The operator authorized this tooling increment and a subsequent bounded product correction.
The operator retains UAT acceptance and merge decisions.

## Goals

- The implementing agent continues an in-scope task after exceeding its estimated code size.
- The Spymaster adjusts implementation paths without abandoning the current task or losing prior evidence.
- Reviewers can distinguish current verification from evidence produced before an amendment.

## Requirements

### Budget audit

- B-01: The budget audit retains cumulative counts, thresholds, status, and diagnostics as review information.
- B-02: The budget audit returns success when size excess is its only diagnostic.
- B-03: The budget audit retains nonzero results for invalid manifests, unavailable revisions, and scope violations.
- B-04: Candidate lifecycle excludes size excess from blocking diagnostics.

### Implementation workflow

- A-01: The workflow accepts an explicit amendment reason and full specification commit on the existing run.
- A-02: The workflow permits only `allowed_paths` and `budget` to differ between manifest revisions.
- A-03: The workflow verifies unchanged TDD and protected files against their original bytes and digests.
- A-04: The workflow requires a clean current feature branch and an active or blocked run.
- A-05: The workflow preserves the task ID, run ID, original baseline, branch, and previous evidence.
- A-06: The workflow invalidates candidate, check, receipt, CI, and promotion evidence after an amendment.
- A-07: Repeating an applied amendment preserves newer evidence and produces no new run.
- A-08: An interrupted amendment remains blocked until the same operation finishes from preserved evidence.
- A-09: The caller applies amendments while all agents and checks for that checkout are idle.

### Long operations

- L-01: A caller can delegate an authorized long command to a deterministic job runner with a deadline and durable results.
- L-02: The agent ends its turn after submitting the job and resumes from the completion report.
- L-03: The agent uses existing Harness commands for verification and closeout.

## Proposed Architecture

The Harness owns manifest validation, budget results, run evidence, and amendment recovery.
Spymaster owns job execution and PR notifications outside the project.
KoteKomi product packages remain independent of both tools.

```text
Spymaster / implementing agent --> Harness CLI --> manifest + run evidence
               |
               +--> local job runner --> Harness CLI
                          |
                          +--> PR completion report
```

## Key Interactions

```text
Spymaster       Git             Harness            Run evidence
    | commit amended manifest      |                    |
    |------------>|                |                    |
    | apply amendment + reason --->| validate boundaries |
    |                              | archive old records>|
    |                              | reset current checks|
    |<--------- same run, candidate phase ---------------|
```

## Data Model

Existing manifests and canonical run records retain their formats.
An amendment archive stores the previous run records and the old manifest bytes.
An amendment record identifies the previous and new specification commits and the reason.
An incomplete amendment has an explicit pending record outside the replaced run records.
Archives remain outside active evidence discovery.

## APIs / Interfaces

The existing `implement-tdd` command gains `--amend-reason TEXT`.
The caller supplies `--specification-commit SHA` with that option.
The option is mutually exclusive with new-run and abandon-run operations.
The command returns the existing workflow JSON and existing run ID.
`budget-audit` retains its JSON shape and status vocabulary.

## Behavior & Domain Rules

A-02 preserves acceptance commands, protected artifact declarations, task identity, and the original baseline.
An amendment author cannot use this operation to approve new product behavior or weaken verification.
A-06 returns the run to candidate verification even when the previous candidate passed.
An applied amendment records history without changing earlier commits or immutable receipts.
A-08 resumes filesystem work only; it never reruns check commands.
A-09 follows the existing single-writer policy rather than adding a distributed scheduler.
L-01 extends the human-started operation policy to an explicitly authorized deterministic runner.
The project continues to work without Spymaster installed.

## Acceptance Criteria

- AC-B: CLI tests prove size-only excess succeeds while scope and invalid-manifest controls fail.
- AC-A: Disposable-repository tests prove same-run amendment, archived evidence, and fresh verification requirements.
- AC-A-negative: Tests reject changed acceptance, baseline, TDD, protected content, dirty checkout, and terminal run.
- AC-A-recovery: Tests prove duplicate application preserves new evidence and pending application resumes safely.
- AC-L: A fresh product correction uses the runner and receives a completion report in the existing conversation.
- Engineering verification runs the generated Harness plan, formatting, lint, type checks, and matching CI.
- Product capability evidence belongs to the subsequent correction's TDD and PR.

## Reference Implementations

- Workflow and specification pinning: `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Canonical evidence: `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.
- Disposable Git repositories: `packages/devtools/tests/acceptance/test_specification_commit_selection_contract.py`.
- Budget diagnostics: `packages/devtools/src/kotekomi_devtools/task_budget.py`.
