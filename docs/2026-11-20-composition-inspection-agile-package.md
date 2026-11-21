# Composition Inspection Agile Package

As a Ledger operator, I want to account for saved Composition after reopening an IngestionRun, so I can find missing work without repeating Source capture.

- **Investigate:** [PR #6](https://github.com/SQLCODE917/KoteKomi/pull/6) reports failure during live ingestion. Reopening shows individual saved records but does not account for Events without one. The archived report binds the expected Event set; the mutable Event-keyed store cannot attribute outcomes to a historical attempt.
- **Split and check:** Resolve the exact run using the stored paragraph loader, validate current outcomes in place, then verify the additive inspection command in a retained mixed-state fixture. The [leaf TDD](2026-11-20-inspect-current-composition-outcomes.md) pins one composed result, one hold, one missing outcome, and one paragraph without Events.
- **Synthesize:** One command describes what is saved now. No reruns, inferred history, or writes. Keep implementer-owned closeout and measure review wakes separately. A recovery feature would need its own proof that it preserves reviewed outcomes.
