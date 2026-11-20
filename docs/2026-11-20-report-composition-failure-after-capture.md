# Report Composition Failure After Capture

## User Story

As a Ledger operator, I want the live ingestion view to tell me when Composition failed after the Source was captured, so I can inspect what was saved without mistaking it for completed Composition or ingesting the Source again.

## Evidence and Scope

`run_ingestion_workflow` already returns the assigned IngestionRun ID and a separate composition error while deliberately preserving extraction's exit code. The live worker emits only that exit code as its terminal event. The Textual screen and copied debug snapshot can show completion while an error reports failed Composition. This is a reporting correction at the existing worker boundary; it is not a new Ledger status or a change to which Assertions can compose.

This slice applies to fresh Textual ingestion. Keep exit codes, plain CLI behavior, stored replay behavior, error diagnostics, cancellation, and all Ledger and Archive writes unchanged. A typed held Event is a valid Composition result, not an exception. Do not imply complete extraction coverage, rollback, or that no Composition results were saved. A temporary state root remains temporary; retention after exit is verified only with an explicit persistent state root.

## Checkpoints

1. **Reproduce and preserve.** Use the existing deterministic ingestion fixture in `test_ingestion_workflow.py`. Inject a failure at the Composition boundary after real fixture capture and extraction; do not replace the top-level workflow. Before production edits retain the red trace showing the existing worker reporting success without a separate terminal disposition, the Composition diagnostic, the IngestionRun ID, and saved Source/extraction evidence. Do not run a live model.
2. **Carry a typed terminal fact.** Use the existing Application Layer worker event and its Adapter receive path to convey that Composition failed after capture, with the actual IngestionRun ID. Preserve the ingestion exit code and do not route this case through the existing stopped/failed-ingestion finalizer. Do not parse stderr, add a second status store, or generate a replacement ID. Check the encoded worker frame and the real durable capture on the failure fixture. Existing success and pre-admission failure keep their behavior.
3. **Report and keep inspection available.** The live terminal view shows “Source captured; composition failed” and the IngestionRun ID, not “Ingestion complete”; the diagnostic and already available Source remain browseable. The copied debug snapshot must not claim completion on that path. A successful pass with held Events still shows normal completion. Pre-admission failure must not claim capture. Keep cancellation and saved replay behavior unchanged.

## Composition of the Slice

The workflow remains the authority for whether Composition raised. Its result reaches the operator through a typed terminal event rather than inferred log text. The same terminal fact drives the visible status and debug snapshot; the existing IngestionRun identifies the capture and is not rewritten. Prove persistence with the explicit state root and verify the headless Textual readout without introducing a second ingestion or a new retry command.

## Verification and Stop Conditions

- Keep one fixture journey to prove failed Composition alongside retained capture and unchanged process exit code. Use the existing headless TUI suite for the operator result and clipboard check, and nearby controls for normal completion, pre-admission failure, cancellation, and read-only replay.
- Retain the pre-fix behavior and final checks as evidence before recording the candidate receipt. Summarize them in the PR closeout. Continue through candidate closeout per [Implementing a TDD](agent/implement-tdd-workflow.md#candidate-closeout-on-the-same-pr) without a second closeout instruction.
- Stop for a scope decision if the fixture does not substantiate the mismatch, or if truthful reporting requires a Ledger schema change, re-ingestion, generic worker redesign, or a different CLI exit contract. No changes to parsing, inference, semantic hold rules, or historical lifecycle state.
