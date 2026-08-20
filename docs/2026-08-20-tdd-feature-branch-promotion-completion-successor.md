# TDD Feature Branch Promotion Completion Successor

- **Status:** Accepted

## Context & Problem

The original Feature Branch Promotion and Completion task ended with a historical abandoned result tag before it produced a verifier-compatible candidate.

That tag remains immutable historical evidence.

The successor task is this task with a distinct task identity and result tag.

The accepted [Feature Branch Promotion and Completion TDD](2026-08-18-tdd-feature-branch-promotion-completion.md) defines the promotion, completion, and abandonment behavior.

This TDD adds successor identity rules for one corrected implementation.

Primary end-to-end flow:

1. The Harness creates a successor feature branch from its committed specification.
2. The implementing agent produces and verifies a promotion candidate.
3. The independent verifier writes a receipt commit on the successor feature branch.
4. Candidate CI validates the receipt commit.
5. The Harness creates and pushes a no-fast-forward merge to main.
6. Main CI validates the merge commit.
7. The Harness publishes the successor result tag and removes the successor feature branch.

## Goals

- The Harness promotes a verified feature branch without a manual merge.
- The Harness records a portable completed result for the successor task.
- The Harness deletes the successor feature branch only after successful main CI.
- The historical abandoned tag remains unchanged.

## Requirements

### Successor identity

- SI-01: The successor uses this TDD path and its own task ID.
- SI-02: The successor result tag uses `kotekomi/tasks/<successor-task-id>/result`.
- SI-03: The successor does not read, replace, or delete the original task result tag.

### Promotion and completion

- PC-01: The implementation satisfies PB-01 through PB-17, MC-01 through MC-03, RT-01 through RT-18, CL-01 through CL-08, WF-01 through WF-05, and CR-01 through CR-06 of the accepted Promotion and Completion TDD.
- PC-02: The implementation records `main_lifecycle.ready = true` only for the ordered merge required by PB-10.
- PC-03: The completion producer binds `main_ci_sha256` to the original main CI result bytes.
- PC-04: The completion producer verifies that origin contains its annotated result tag before it writes task-result evidence.
- PC-05: The completion producer retains the remote feature branch when local non-force deletion fails.

## Proposed Architecture

The successor uses the original promotion, CI, completion, evidence catalog, and workflow components.

```text
Successor feature branch -> Promotion producer -> origin/main
                                              |
                                              v
                                      Completion producer
                                              |
                                              v
                              Successor tag and branch cleanup
```

## Key Interactions

```text
Implementing agent -> Harness: create successor candidate
Independent verifier -> feature branch: receipt commit
CI -> Harness: candidate and main CI records
Harness -> origin/main: no-fast-forward merge
Harness -> origin: successor result tag and feature deletion
```

## Data Model

The successor uses the result-tag and task-result record shapes in the accepted Promotion and Completion TDD.

The successor creates no record shape that the accepted Promotion and Completion TDD does not define.

The successor stores all evidence under its own task ID and implementation run ID.

## APIs / Interfaces

The successor uses the command interfaces in the accepted Promotion and Completion TDD.

## Behavior & Domain Rules

The successor begins from a main commit that contains its Task Manifest.

The successor Task Manifest sets `baseline_revision` to the parent main commit.

The verifier uses that baseline revision and the persisted successor specification revision.

## Acceptance Criteria

- AC-SI-01: Disposable Git tests prove the successor result tag differs from the original abandoned result tag.
- AC-PC-01: The original TDD acceptance criteria pass for the successor task.
- AC-PC-02: Tests prove the historical original tag remains unchanged after successor completion.

## Reference Implementations

- Original behavior: follow `docs/2026-08-18-tdd-feature-branch-promotion-completion.md`.
- Bootstrap abort: follow `docs/2026-08-20-tdd-bootstrap-run-abort.md`.

## Constraints and Halt Conditions

The implementation does not change the original abandoned result tag.

The implementation does not use direct-main promotion.
