# Implementing a TDD

## Work on one PR

The PR and its branch are the unit of work.
Read its Agile package, current discussion, and the package-level instructions before editing.
Check the assigned branch before writing and keep one writer per checkout.
The implementing agent owns code, tests, package corrections, and a concise review request.
The reviewer inspects the diff and existing check results.
The operator decides product tradeoffs, accepts UAT, and merges.

Update the package on the same branch when implementation reveals an ordinary correction.
Explain meaningful changes in the review request.
Ask the operator when the promised outcome changes or a product decision is needed.
Do not weaken acceptance criteria merely to make failing code pass.
Git history preserves earlier specifications and implementations.

Routine work needs no Task Manifest, specification pin, Harness run, amendment command, receipt commit, promotion record, or scorecard.
Older Harness commands and their historical evidence are not prerequisites for this workflow.
Older TDD workflow requirements are superseded by this guide; their product behavior and regression tests remain useful.
Do not run two orchestration listeners against the same agent conversation.

## Implement and verify

Capture a failing regression or a concrete before-example for the intended behavior.
Run focused tests during editing.
Run `./scripts/verify.sh fast` before submitting a candidate.
Use the additional checks in [Check Plan](../CHECK_PLAN.md) that exercise the changed behavior.
Commit and push the candidate, then request review with the behavior change, checks, and any remaining question.
Review the requested commit through Git; a shared checkout need not move for a read-only review.
Send one consolidated revision request when changes are needed.
Continue on the same PR and rerun checks affected by the correction.

Full PR CI supplies the full-suite merge gate.
A reviewer uses existing results and runs additional probes only to resolve a concrete concern.
Do not repeat full verification solely to produce an independent receipt.
A test result describes the commit it tested; new code requires current evidence.

## Long checks and CI

An authorized background runner can execute checks under the caller's existing permissions.
Submit once, end the agent turn, and continue from the completion notification.
Keep command output and exit status outside the checkout.
Do not poll from model turns or blindly replay an uncertain command.
Without a runner, hand the command to the operator under [Long-Running Operations](long-running-operations.md).

For CI, a deterministic observer can use `gh run watch <run-id> --repo <owner/name> --exit-status` with a 30-minute deadline.
Use the PR workflow for the current head and check its terminal result before recommending merge.
If it fails, inspect the failing job and fix the cause on the same branch.
If observation ends without a terminal result, report it as pending rather than restarting implementation.
GitHub retains CI evidence; do not copy it into a second lifecycle store.

## UAT and completion

After code approval and successful required checks, provide concrete UAT steps and mark the PR ready for review.
The operator's UAT acceptance and merge close the work.
No separate completion ledger is required.
