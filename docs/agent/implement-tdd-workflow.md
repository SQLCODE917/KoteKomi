# Implementing a TDD

## Work on one PR

The PR and its branch are the unit of work.
Read its Agile package, current discussion, and the package-level instructions before editing.
Check the assigned branch before writing and keep one writer per checkout.
The implementing agent owns discovery, implementation choices, code, tests, package corrections, and a concise review request.
The reviewer challenges the observable result, preserved owners, and evidence at the changed boundaries.
The operator decides product tradeoffs, accepts UAT, and merges.

The Agile package owns the authorized outcome and scope.
The active TDD states binding contracts: observable behavior, decision ownership, authorization, identity, and required bounds.
Private decomposition, intermediate representations, work order, and fixture arrangement are proposals unless a stated contract requires them.
The operator decides changes to the promised outcome and binding contracts; implementation choices remain with the implementing agent.
Git history preserves earlier specifications and implementations.

Routine work needs no Task Manifest, specification pin, Harness run, amendment command, receipt commit, promotion record, or scorecard.
Older Harness commands and their historical evidence are not prerequisites for this workflow.
Older TDD workflow requirements are superseded by this guide; their product behavior and regression tests remain useful.
Do not run two orchestration listeners against the same agent conversation.

## Understand and adapt

Trace one representative operation from the operator action through the visible result and finalization.
Distinguish runtime flow, decision ownership, and state lifecycle: what executes, who decides, and what persists or needs cleanup?
Follow state read outside the returned value and the callers that finalize the operation.
Challenge the proposed change with a variation that could invalidate it, such as existing output, a failed write, or cancellation.
Expand the investigation only when it could change the implementation decision or required evidence.
Stop when the affected owners, contracts, and next safe implementation step are clear; keep consequential unknowns explicit.
No separate codebase map or investigation report is required.

When evidence contradicts a proposal, trace the affected boundary and make the smallest contract-preserving correction.
Update the owning design section on the same branch, cite the source or test behind the correction, and continue.
Correcting an inaccurate assumption does not authorize changing existing behavior or weakening acceptance criteria.
A different private design, another affected module, or a missing fixture is not by itself a reason to stop.
Ask the operator when a discovery requires changing authorized scope, promised behavior, decision ownership, permissions, or another binding contract.
Also ask when unresolved ambiguity prevents a safe in-scope next step; continue independent authorized work meanwhile.
Do not introduce a duplicate implementation or broken intermediate step solely to preserve the proposed work order.

## Implement and verify

Use [Testing Rules](testing.md#evidence-at-the-changed-boundary) to select evidence for the promised behavior.
Capture a failing regression for a defect or a concrete before-example for an enhancement.
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
State what the evidence establishes and what remains unverified against the promised outcome.
Preparation for that outcome is not completion; a documented prerequisite suffices only when the package promises that decision scope.
Do not add future features or unrelated verification obligations to close the current slice.
The operator's UAT acceptance and merge close the work.
No separate completion ledger is required.
