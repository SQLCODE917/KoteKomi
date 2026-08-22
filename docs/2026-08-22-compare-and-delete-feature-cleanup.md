# TDD Compare-and-Delete Feature Cleanup

## Context & Problem

The Harness publishes a result tag before it deletes a feature branch.

The current cleanup producer uses Git's merge-only local branch deletion.

Git rejects that deletion for an abandoned branch because `main` does not contain its final feature tip.

The producer then retains both feature refs after it has published an abandoned result tag.

This TDD supersedes CL-03 in `2026-08-18-tdd-feature-branch-promotion-completion.md`.

The **expected feature tip** is the final remote feature commit that the result tag preserves.

The **compare-and-delete operation** deletes a named feature ref only when its current commit equals the expected feature tip.

The operation leaves a mismatching ref unchanged.

Primary end-to-end flow:

1. The operator abandons a run through `implement-tdd`.
2. The completion producer publishes the abandoned result tag at the expected feature tip.
3. The cleanup producer compares the local feature ref with the expected feature tip.
4. The cleanup producer deletes the matching local feature ref.
5. The cleanup producer deletes the matching remote feature ref with a Git lease.
6. The cleanup producer writes complete cleanup evidence after Git exposes neither feature ref.

## Goals

- The Harness deletes an abandoned feature branch after it preserves the final commit with a result tag.
- The Harness retains a feature ref whose commit changed after validation.
- The Harness reports the exact remaining feature refs after a failed cleanup attempt.

## Requirements

### Result boundary

- RB-01: `abandon-feature-branch` publishes the abandoned result tag before it deletes a feature ref.
- RB-02: The abandoned result tag points to the expected feature tip.
- RB-03: A matching existing result tag permits a cleanup retry.
- RB-04: A conflicting result tag blocks cleanup.

### Local ref boundary

- LR-01: The cleanup producer derives the local feature ref from `feature/<task-id>`.
- LR-02: The cleanup producer uses the expected feature tip as the required old value for local deletion.
- LR-03: The cleanup producer deletes the local ref only when Git confirms that required old value.
- LR-04: A local ref with another commit remains present.
- LR-05: A worktree that checks out the feature ref blocks deletion when it has uncommitted changes.
- LR-06: The cleanup producer detaches a clean feature worktree at the result target before it deletes the local ref.

### Remote ref boundary

- RR-01: The cleanup producer deletes the remote feature ref only after local deletion succeeds.
- RR-02: The cleanup producer uses the expected feature tip as the remote lease value.
- RR-03: Git rejects remote deletion when the remote ref differs from the lease value.
- RR-04: A rejected remote deletion leaves the remote ref present.
- RR-05: The cleanup producer never uses an unrestricted ref deletion.

### Evidence boundary

- EB-01: The cleanup producer writes cleanup evidence after each deletion attempt.
- EB-02: Cleanup evidence sets `branch_cleanup_complete = true` only when no local or remote feature ref remains.
- EB-03: Cleanup evidence lists each remaining local or remote feature ref.
- EB-04: A repeated successful cleanup command reports complete cleanup evidence.

## Proposed Architecture

The completion producer owns result-tag publication.

The cleanup producer owns compare-and-delete operations.

Git owns ref equality checks and lease enforcement.

The evidence catalog owns cleanup evidence.

```text
Abandoned run -> Completion producer -> Result tag
                                      |
                                      v
                               Cleanup producer
                                  |         |
                                  v         v
                            Local feature  Remote feature
                                  \         /
                                   v       v
                               Cleanup evidence
```

## Key Interactions

```text
Completion producer -> origin: publish result tag at expected feature tip
Cleanup producer -> local Git: compare and delete local feature ref
Cleanup producer -> origin: compare lease and delete remote feature ref
Cleanup producer -> Evidence catalog: write cleanup status
```

## Data Model

The existing cleanup record remains the cleanup record for this TDD.

The cleanup record contains `branch_cleanup_complete`, `remaining_branches`, and `diagnostics`.

The result tag remains the authority that preserves the expected feature tip before deletion.

## APIs / Interfaces

This TDD changes the existing command.

```text
kotekomi-agent abandon-feature-branch
  --task-id <task-id> --run <implementation-run-id> --state-root <state-root>
```

The command output remains the existing completion result contract.

## Behavior & Domain Rules

The cleanup producer uses compare-and-delete for every local feature ref.

The cleanup producer uses a lease-protected delete for every remote feature ref.

The expected feature tip is the receipt commit for a completed task.

The expected feature tip is the final remote feature commit for an abandoned task.

The result target can differ from the expected feature tip for a completed task.

The cleanup producer does not treat a result target as a feature-ref deletion value.

The cleanup producer retains a ref when a compare or lease check fails.

## Acceptance Criteria

- AC-RB-01: Disposable Git tests prove an abandoned result tag exists before the cleanup producer deletes either feature ref.
- AC-LR-01: Disposable Git tests prove the cleanup producer deletes a tagged unmerged local feature ref with a matching expected feature tip.
- AC-LR-02: Tests prove a changed local feature ref remains present.
- AC-LR-03: Tests prove a dirty feature worktree remains present.
- AC-RR-01: Disposable Git tests prove the cleanup producer deletes the matching remote feature ref after local deletion.
- AC-RR-02: Tests prove a changed remote feature ref remains present.
- AC-EB-01: Tests prove complete and incomplete cleanup evidence lists the correct remaining refs.
- AC-EB-02: Tests prove a cleanup retry after a completed deletion reports success.

## Reference Implementations

- Result tags: follow `packages/devtools/src/kotekomi_devtools/feature_branch_promotion.py`.

- Superseded ref cleanup: follow `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.

## Constraints and Halt Conditions

Stop when result-tag publication does not prove the expected feature tip.

Stop when a local ref or remote ref changes after the expected feature tip is resolved.

Do not change promotion, result-tag, or evidence-record fields.
