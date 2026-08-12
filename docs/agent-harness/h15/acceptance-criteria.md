# H15 acceptance criteria

1. Add the H15 task manifest and H15 documentation set.
2. Add a CLI command for deterministic receipt-chain status.
3. The command must read receipt paths supplied explicitly by the operator or by deterministic task/phase defaults; it must not infer completion from chat history, agent context, or prose notes.
4. The command must emit JSON with a stable schema containing task id, phase, status, receipt entries, diagnostics, and missing required records.
5. The command must support a human-readable Markdown or text output mode for local operator review.
6. Missing receipts and digest mismatches must fail closed with nonzero exit status and actionable diagnostics.
7. Unit and acceptance tests must cover complete chains, missing receipt chains, digest mismatches, and stable output fields.
8. H15 must dogfood the normal candidate and main sequence with lifecycle, verification-plan, run-check, verify-checks, CI, cleanup, and final status receipts.
