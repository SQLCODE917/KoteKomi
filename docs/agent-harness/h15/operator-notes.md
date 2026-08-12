# H15 operator notes

The receipt-chain status command should be deterministic, read-only, and file-backed. It is not a substitute for `write-receipt`, `verification-plan`, `run-check`, or `verify-checks`; it is a status surface over receipts those commands already create.

Do not ask an implementation agent to manually maintain receipt chain state or rewrite structured receipt summaries. The command owns status calculation from files and expected-record configuration.
