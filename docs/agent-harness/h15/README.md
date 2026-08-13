# H15 deterministic receipt-chain status command

H15 adds a deterministic operator command that reports whether a task receipt chain is complete for a requested phase. The command must read existing receipt files and emit machine-readable status without asking an implementation agent to infer or manually summarize roadmap state.

The command should make receipt chains visible, detect missing required receipts, detect digest mismatches where expected digests are provided, and keep output stable enough for scripts to gate follow-up steps.
