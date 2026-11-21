# Inspect Current Composition Outcomes

## User Story

As a Ledger operator, I want to inspect the current saved Composition outcomes for Events in a retained IngestionRun, so I can distinguish saved Assertions and holds from Events that still have no saved outcome without ingesting the Source again.

## Contract

Add `kotekomi --config <path> ingestions composition <ingestion-run-id> --format text|json`.
Require an explicit run ID. The selected run's stored paragraphs define the denominator: unique realized Event IDs, not trigger candidates or paragraph count. Read only current outcome files for those IDs. The store is keyed by Event ID and later reviewed recomposition can replace an outcome. Reused paragraph receipts can share Event IDs between runs. The result describes current saved outcomes for Events in the selected run, not historical completion of that attempt, nor complete extraction coverage.

Report the selected run, total realized Events, and counts of `composed`, `held`, `missing`, and `invalid`. Include Event IDs and one-based paragraph locations for missing and invalid outcomes and the exact hold reason for held outcomes. Text and JSON report the same counts and rows in stable order. A no-Event paragraph contributes nothing; zero Events is not a completed-Composition claim. A valid saved hold can be inspectable evidence of a failure, not a composed Assertion. Only an absent outcome file is missing; unreadable, malformed, or mismatched data is invalid, with a diagnostic and nonzero result, never counted as a saved outcome. Do not silently pick another run or fall back to mismatched data. Keep existing `ingestions show` and replay outputs unchanged.

## Checkpoints

1. **Establish the denominator.** Use the existing initialized-Ledger guard and `load_paragraph_inputs` to resolve the exact run through its archived evidence. Identify Events from validated stored paragraphs using existing profile construction. Keep repeated occurrences of the same Event from inflating counts; conflicting paragraph evidence must not silently be deduplicated. Record a pre-change witness with fixture run ID, expected IDs, and what the current interface lacks.
2. **Account for saved outcomes.** Use the existing outcome store's per-Event read, never a directory scan. Validate the record Event ID, paragraph source text SHA-256, and existing DTO. Assert the mixed state on one retained run: one saved composed result, one typed hold, one later realized Event missing an outcome, and a no-Event paragraph. Control for a malformed or mismatched matching file, an unrelated file, and a reused Event with a newer saved outcome. Show the newer outcome without claiming what the earlier attempt did.
3. **Expose a bounded read-only command.** Wire the same result to text and JSON. Verify a real fixture can be reopened and inspected after the failure without an analyzer, new IngestionRun, or changed Ledger/Archive data. Keep default summaries free of Source text or raw model output. Missing saved outcomes are reported, not repaired; invalid evidence is actionable.

## Stop Conditions

No re-ingestion, retry, historical status, inference, TUI changes, new persistence, or outcome schema change. If the retained representation cannot identify realized Events, stop and show the counterexample rather than inferring them. Retain red and final fixture evidence and continue to same-run candidate closeout without a second prompt.
