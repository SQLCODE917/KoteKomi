# Long-Running Operation Observability

## Context & Problem

KoteKomi records ingestion, analysis, model, and Hybrid Pipeline evidence.

The public CLI does not correlate those records by `IngestionRun`.

An agent must inspect implementation code or raw storage to explain a completed ingestion.

Passive monitoring also consumes agent time without improving the result.

An **operation handoff** gives a human an exact start command and deterministic inspection commands.

An **ingestion summary** is a bounded read-only view of one `IngestionRun`.

An **evidence listing** identifies validated evidence without exposing its contents.

Primary flow:

1. The Pipeline creates an `IngestionRun` before expensive work and prints its ID.
2. The human monitors the ingestion command.
3. The agent reads the terminal ingestion summary by `IngestionRun` ID.
4. The agent lists validated evidence and model diagnostics by the same ID.
5. The agent requests exact stage traces only when diagnosis requires their contents.

## Goals

- A user can inspect one ingestion without reading raw storage.
- An agent can hand off long work without polling it.
- Every model diagnostic resolves through explicit analysis membership.
- Exact stage diagnostics remain available without entering default summaries.
- Pipeline plans describe how to execute and inspect their next command.

## Requirements

### User Ingestion Pipeline

- UIP-01: The Pipeline prints the new `IngestionRun` ID before source capture starts.
- UIP-02: The Pipeline preserves the existing progress output after the ID line.
- UIP-03: The Pipeline does not print Source text, prompts, or model output in default output.

### Application Layer

- AL-01: The Application Layer resolves inspection from one explicit `IngestionRun` ID.
- AL-02: The Application Layer rejects a missing `IngestionRun`.
- AL-03: The ingestion summary reports lifecycle IDs, status, timing, failures, and counts.
- AL-04: The evidence listing reports authority, record type, ID, digest, and Archive path.
- AL-05: The model summary includes only `ModelRun` records linked by `AnalysisItemAttempt`.
- AL-06: Hybrid inspection requires a link for every stage-recorded `ModelRun`.
- AL-07: The trace listing returns validated `ExtractionStageTrace` records.
- AL-08: The Application Layer rejects missing or digest-mismatched Hybrid Pipeline evidence.

### Hybrid Pipeline Closeout

- HPC-01: Closeout links each contributing `ModelRun` to its paragraph item.
- HPC-02: Each link uses one `AnalysisItemAttempt` with its Hybrid stage as execution role.
- HPC-03: Closeout reuses an identical existing link and rejects a conflicting link.

### Archive Adapter

- AA-01: The Adapter finds a Hybrid coverage report by its exact SHA-256 digest.
- AA-02: The Adapter validates each candidate through the declared coverage report DTO.
- AA-03: The Adapter returns no ID for a missing digest and rejects invalid candidate records.

### Command-Line Interface

- CLI-01: `ingestions list` accepts a positive `--limit` and `text` or `json` format.
- CLI-02: `ingestions show <run-id>` returns one bounded ingestion summary.
- CLI-03: `ingestions artifacts <run-id>` returns one evidence listing.
- CLI-04: `model runs --ingestion-run <run-id>` filters by explicit analysis membership.
- CLI-05: `extraction traces --ingestion-run <run-id>` returns exact traces.
- CLI-06: JSON Lines commands write one JSON object per line in deterministic order.

### Pipeline Planning

- PP-01: Each `PipelineCommandPlan` names its execution class.
- PP-02: Each executable plan provides completion-probe and evidence command arguments.
- PP-03: Each executable plan names its expected record types.
- PP-04: A non-executable plan uses empty inspection arguments and expected record types.

## Proposed Architecture

```text
Human
  |
  v
KoteKomi CLI
  |
  v
Ingestion Observability Use Case
  |                         |
  v                         v
Ledger Port             Archive Port
  |                         |
  v                         v
SQLite Adapter          Local Archive Adapter
```

The Application Layer owns correlation, validation, and bounded result DTOs.

The SQLite Adapter loads the explicit lifecycle references.

The Local Archive Adapter locates bytes by the trusted coverage digest.

The Pipeline renders DTOs and does not decide correlation rules.

## Key Interactions

```text
Human -> Pipeline: ingest file
Pipeline -> Ledger: create IngestionRun
Pipeline -> Human: print IngestionRun ID
Pipeline -> Hybrid Pipeline: analyze document
Hybrid Pipeline -> Ledger: link contributing ModelRuns
Human -> CLI: show IngestionRun ID
CLI -> Application Layer: inspect IngestionRun ID
Application Layer -> Ledger: load explicit lifecycle graph
Application Layer -> Archive: validate referenced evidence
Application Layer -> CLI: return bounded summary
```

## Data Model

This change uses existing `IngestionRun`, `AnalysisRun`, and `PlannedAnalysisItem` records.

This change uses existing `AnalysisItemAttempt` and `ModelRun` records.

This change uses existing Hybrid Pipeline manifests, receipts, reports, previews, and traces.

This change adds no canonical record type and no database migration.

## APIs / Interfaces

The ingestion summary includes:

- `ingestion_run_id`, display filename, requested Source URL, and status;
- start, completion, and elapsed milliseconds;
- canonical Source, Document, representation, provenance, analysis, and change-set IDs;
- safe failure stage, code, and message;
- analysis state, paragraph counts, model-run counts, and evidence counts.

Each evidence entry includes:

- `authority` as `canonical` or `derived`;
- `record_type`;
- `record_id`;
- `sha256` when the referenced contract supplies one;
- `archive_path` for Archive records.

Each command plan includes:

- `execution_class` as `interactive` or `long_running`;
- `completion_probe_argv`;
- `evidence_argv`;
- `expected_record_types`.

## Behavior & Domain Rules

Default summary commands return at most the requested positive limit.

Evidence listings order entries by record type and record ID.

Trace listings order traces by Source segment, ordinal, and trace ID.

Model listings order records by start time and ID in descending order.

An errored ingestion needs no analysis evidence.

A captured Hybrid Pipeline ingestion requires a valid coverage report and all referenced evidence.

The CLI exits nonzero when inspection detects missing or inconsistent evidence.

Inspection does not write the Ledger or Archive.

## Acceptance Criteria

- AC-UIP-01: A Pipeline test observes the `IngestionRun` ID before progress output.
- AC-AL-01: Fake-Port tests resolve one complete ingestion through all explicit references.
- AC-AL-02: Fake-Port tests reject missing and inconsistent references.
- AC-HPC-01: Closeout tests prove every contributing `ModelRun` has one item link.
- AC-AA-01: Adapter tests prove digest lookup, missing evidence, and invalid evidence behavior.
- AC-CLI-01: CLI tests cover list, show, artifacts, filtered model runs, and exact traces.
- AC-CLI-02: CLI tests prove default summaries exclude exact Source and model content.
- AC-PP-01: Pipeline plan tests prove execution and inspection metadata for every stage.
- AC-CQ-01: Formatting, lint, typecheck, and focused tests pass.

## Reference Implementations

- Safe model summaries: `packages/application/src/kotekomi_application/model_run_logging.py`.
- Lifecycle correlation: `packages/application/src/kotekomi_application/analysis_coverage.py`.
- Hybrid replay: `packages/application/src/kotekomi_application/hybrid_document_orchestration.py`.
- CLI rendering: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Archive validation: `packages/adapters/src/kotekomi_adapters/local_archive.py`.

## Constraints and Halt Conditions

The implementation does not add a background job service.

The implementation does not store CI state in the Ledger.

The implementation does not correlate records by timestamps, directory order, or log text.
