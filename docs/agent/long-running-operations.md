# Long-Running Operations

## Purpose

Keep model time and human attention out of passive monitoring loops.

Preserve enough evidence to inspect each completed operation deterministically.

## Operation Handoff

Treat an operation as long-running when it can exceed 60 seconds.

Treat an operation as long-running when it depends on a model runtime or remote service.

Give the human one exact command to start the operation.

Give the human every expected output path known before execution.

Give the human one bounded command that reports terminal status.

Give the human one bounded command that reports durable evidence.

State the exact success criteria.

Do not monitor the operation after the handoff.

Resume inspection after the human reports a terminal result.

## Durable Evidence

Use an existing lifecycle record as the correlation key.

Use `IngestionRun` for user ingestion.

Use `AnalysisRun` and `AnalysisItemAttempt` for analysis work.

Use `ModelRun` for model invocation diagnostics.

Use `ExtractionStageTrace` for exact extraction stage input and output.

Use Hybrid Pipeline receipts and coverage reports for document closeout.

The Ledger stores typed status, identity, digest, and reference fields.

The Archive stores raw model output, stage evidence, receipts, and coverage reports.

`ProvenanceActivity` records accepted Ledger changes.

Derived diagnostics do not become accepted Ledger state.

## Inspection Boundary

Inspection commands are read-only.

Default inspection commands return bounded summaries.

Default summaries exclude Source text, prompts, and raw model output.

An explicit trace command can return exact `ExtractionStageTrace` input and output.

Inspection commands validate every referenced record and digest before returning it.

Inspection commands fail when referenced evidence is missing or inconsistent.

Do not infer correlation from timestamps or directory order.

Do not discover one run by parsing human-readable logs.

## Agent Workflow

Run focused unit and contract tests directly.

Hand off full test suites, canonical ingestions, and live model experiments.

Use `kotekomi ingestions show <run-id> --format json` as an ingestion completion probe.

Use `kotekomi ingestions artifacts <run-id> --format jsonl` to inspect evidence identities.

Use `kotekomi model runs --ingestion-run <run-id> --format json` for model diagnostics.

Use `kotekomi extraction traces --ingestion-run <run-id> --format jsonl` for exact stage traces.

Report a pushed branch and commit instead of polling CI.
