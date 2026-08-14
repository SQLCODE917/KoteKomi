# TDD Implementation Metrics

## Context & Problem

A user wants to compare the effectiveness of Technical Design Documents.

The user knows each Technical Design Document by local file path.

A TDD can have one implementation run or many implementation runs.

The Harness records evidence during implementation, but it does not yet collect that evidence into TDD implementation metrics.

The user cannot compare TDDs unless the Harness normalizes lifecycle, verification, repair, CI, and receipt evidence for each TDD.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `implementation run` for one attempt to implement one TDD from intake through completion or block.

This TDD uses the term `TDD metrics` for the normalized facts that the Harness collects for one implementation run.

This TDD uses the term `metrics collection` for the report that contains metrics for more than one implementation run.

This TDD uses the term `repair count` for the number of failed candidate or main attempts before the final status.

Primary end-to-end Flow:

1. The user asks for metrics for one TDD path or for all known TDDs.

2. The Harness resolves each TDD path to a TDD binding through the TDD index.

3. The Harness validates the canonical TDD binding for each resolved TDD.

4. The Harness reads run records, receipts, lifecycle records, run-check records, and CI records for each task identifier.

5. The Harness computes TDD metrics for the selected implementation runs.

6. The Harness writes metrics records and a metrics collection.

7. The user can pass the metrics collection to the scoring command.

## Goals

- The user can inspect raw implementation facts for one TDD path.

- The user can inspect raw implementation facts for all runs of one TDD path.

- The user can inspect raw implementation facts for all known TDDs.

- The user can inspect raw implementation facts for one selected implementation run.

- The user can see whether a TDD produced a clean first pass.

- The user can see whether a TDD produced repair work.

- The user can use the same metrics schema for all TDD implementations.

## Requirements

Metrics input boundary:

- MI-01: The metrics collector reads one TDD binding when the user supplies a TDD path.

- MI-02: The metrics collector reads all known TDD bindings when the user supplies no TDD path.

- MI-03: The metrics collector validates canonical TDD bindings after TDD index lookup.

- MI-04: The metrics collector reads the run index for each task identifier.

- MI-05: The metrics collector reads run records for each selected implementation run.

- MI-06: The metrics collector reads the receipt-chain status for each task identifier.

- MI-07: The metrics collector reads verification-plan output for each task identifier.

- MI-08: The metrics collector reads run-check records for each selected implementation run.

- MI-09: The metrics collector reads verify-checks output for each selected implementation run.

- MI-10: The metrics collector reads candidate CI records for each selected implementation run.

- MI-11: The metrics collector reads main CI records for each selected implementation run.

- MI-12: The metrics collector reads lifecycle diagnostics for each selected implementation run.

Run selection boundary:

- RS-01: The metrics command with one TDD path and no run selector emits metrics for all runs of that TDD.

- RS-02: The metrics command with no TDD path emits metrics for all runs of all known TDDs.

- RS-03: The metrics command with `--run` emits metrics for one implementation run.

- RS-04: The metrics command with `--latest` emits metrics for the highest ordinal run for the selected TDD.

- RS-05: The metrics command blocks when `--run` and `--latest` appear together.

Metrics output boundary:

- MO-01: The metrics collector writes one metrics record for one implementation run.

- MO-02: The metrics collector writes a metrics collection for one or more metrics records.

- MO-03: Each metrics record includes `task_id`.

- MO-04: Each metrics record includes `primary_tdd_path`.

- MO-05: Each metrics record includes `tdd_paths`.

- MO-06: Each metrics record includes `tdd_sha256`.

- MO-07: Each metrics record includes `implementation_run_id`.

- MO-08: Each metrics record includes receipt completeness counts.

- MO-09: Each metrics record includes digest mismatch counts.

- MO-10: Each metrics record includes lifecycle readiness values.

- MO-11: Each metrics record includes planned check count.

- MO-12: Each metrics record includes executed check count.

- MO-13: Each metrics record includes verified check count.

- MO-14: Each metrics record includes failed check count.

- MO-15: Each metrics record includes candidate CI conclusion.

- MO-16: Each metrics record includes main CI conclusion.

- MO-17: Each metrics record includes repair count.

- MO-18: Each metrics record includes budget violation count.

- MO-19: Each metrics record includes protected artifact violation count.

- MO-20: Each metrics record includes branch cleanup status.

- MO-21: The metrics collection includes `metrics_collection_path`.

- MO-22: The metrics collection includes `metrics_record_paths`.

Diagnostics boundary:

- DI-01: The metrics collector reports missing TDD binding as blocked status for one TDD path.

- DI-02: The metrics collector reports missing receipt-chain status as blocked status for that metrics record.

- DI-03: The metrics collector reports missing optional evidence as partial status.

- DI-04: The metrics collector reports digest mismatch as blocked status for that metrics record.

- DI-05: The metrics collector reports a missing run record as blocked status for that metrics record.

## Proposed Architecture

The metrics command owns the operator boundary.

The TDD binding store owns TDD lookup.

The run state manager owns run selection.

The metrics collector owns evidence loading and metric normalization.

The existing Harness files own source evidence.

The metrics report writer owns stdout JSON and optional report copies.

```text
+------------------+      +------------------+      +-------------------+
| Operator         | ---> | Metrics command  | ---> | TDD binding store |
+------------------+      +------------------+      +-------------------+
                                      |                         |
                                      v                         v
                              +---------------+         +----------------+
                              | Run state     | <------ | TDD bindings   |
                              +---------------+         +----------------+
                                      |
                                      v
                            +-------------------+
                            | Metrics collector |
                            +-------------------+
                                      |
             +------------------------+------------------------+
             |                        |                        |
             v                        v                        v
   +------------------+     +------------------+      +------------------+
   | Receipts         |     | Run records      |      | CI records       |
   +------------------+     +------------------+      +------------------+
                                      |
                                      v
                            +-------------------+
                            | Metrics reports   |
                            +-------------------+
```

## Key Interactions

Single TDD sequence:

```text
Operator      Metrics command      Binding store      Run state      Metrics collector
   |                |                    |                 |                 |
   | metrics path   |                    |                 |                 |
   |--------------->|                    |                 |                 |
   |                | read binding       |                 |                 |
   |                |------------------->|                 |                 |
   |                | binding            |                 |                 |
   |                |<-------------------|                 |                 |
   |                | select runs        |                 |                 |
   |                |------------------------------------->|                 |
   |                | selected runs      |                 |                 |
   |                |<-------------------------------------|                 |
   |                | collect evidence   |                 |                 |
   |                |----------------------------------------------------->|
   |                | metrics records    |                 |                 |
   |                |<-----------------------------------------------------|
   | metrics result |                    |                 |                 |
   |<---------------|                    |                 |                 |
```

All known TDDs sequence:

```text
Operator      Metrics command      Binding store      Run state      Metrics collector
   |                |                    |                 |                 |
   | metrics all    |                    |                 |                 |
   |--------------->|                    |                 |                 |
   |                | read all bindings  |                 |                 |
   |                |------------------->|                 |                 |
   |                | bindings           |                 |                 |
   |                |<-------------------|                 |                 |
   |                | select all runs    |                 |                 |
   |                |------------------------------------->|                 |
   |                | selected runs      |                 |                 |
   |                |<-------------------------------------|                 |
   |                | collect all        |                 |                 |
   |                |----------------------------------------------------->|
   |                | metrics records    |                 |                 |
   |                |<-----------------------------------------------------|
   | metrics result |                    |                 |                 |
   |<---------------|                    |                 |                 |
```

## Data Model

The Harness will create one TDD metrics record per implementation run.

The metrics record path is:

```text
<state-root>/experiments/<task-id>/runs/<implementation-run-id>/metrics/tdd-metrics.json
```

The metrics collection path for one task is:

```text
<state-root>/experiments/<task-id>/metrics/tdd-metrics-collection.json
```

The metrics collection path for all known TDDs is:

```text
<state-root>/tdds/metrics/tdd-metrics-collection.json
```

The TDD metrics record has these fields:

- `schema_version`

- `task_id`

- `primary_tdd_path`

- `tdd_paths`

- `tdd_sha256`

- `implementation_run_id`

- `status`

- `receipt_total_count`

- `receipt_present_count`

- `receipt_missing_count`

- `digest_mismatch_count`

- `candidate_lifecycle_ready`

- `main_lifecycle_ready`

- `planned_check_count`

- `executed_check_count`

- `verified_check_count`

- `failed_check_count`

- `candidate_ci_conclusion`

- `main_ci_conclusion`

- `repair_count`

- `budget_violation_count`

- `protected_artifact_violation_count`

- `branch_cleanup_complete`

- `diagnostics`

The metrics collection record has these fields:

- `schema_version`

- `status`

- `metrics_collection_path`

- `metrics_record_paths`

- `metrics`

- `diagnostics`

The `metrics_record_paths` value maps implementation run identifiers to metrics record paths.

The Harness will access metrics records by `primary_tdd_path`.

The Harness will access metrics records by `task_id`.

The Harness will access metrics records by `tdd_sha256`.

The Harness will access metrics records by `implementation_run_id`.

## APIs / Interfaces

The all-runs single TDD CLI contract is:

```text
kotekomi-agent tdd-metrics <tdd-path> [--output <metrics-json>] [--markdown <metrics-md>]
```

The one-run CLI contract is:

```text
kotekomi-agent tdd-metrics <tdd-path> --run <implementation-run-id> [--output <metrics-json>] [--markdown <metrics-md>]
```

The latest-run CLI contract is:

```text
kotekomi-agent tdd-metrics <tdd-path> --latest [--output <metrics-json>] [--markdown <metrics-md>]
```

The all known TDDs CLI contract is:

```text
kotekomi-agent tdd-metrics [--output <metrics-json>] [--markdown <metrics-md>]
```

The CLI prints the metrics collection JSON to stdout when `--output` is absent.

The `--output` file is an optional JSON copy.

The `--markdown` file is an optional Markdown copy.

The metrics record JSON contract is:

```text
schema_version
task_id
primary_tdd_path
tdd_paths
tdd_sha256
implementation_run_id
status
receipt_total_count
receipt_present_count
receipt_missing_count
digest_mismatch_count
candidate_lifecycle_ready
main_lifecycle_ready
planned_check_count
executed_check_count
verified_check_count
failed_check_count
candidate_ci_conclusion
main_ci_conclusion
repair_count
budget_violation_count
protected_artifact_violation_count
branch_cleanup_complete
diagnostics
```

The metrics collection JSON contract is:

```text
schema_version
status
metrics_collection_path
metrics_record_paths
metrics
diagnostics
```

## Behavior & Domain Rules

The metrics collector treats missing TDD binding as blocked status for one TDD path.

The metrics collector treats digest mismatch as blocked status for that metrics record.

The metrics collector treats missing run record as blocked status for that metrics record.

The metrics collector treats missing final evidence as partial status when earlier evidence is usable.

The metrics collector counts failed candidate attempts as repair count.

The metrics collector counts failed main attempts as repair count.

The metrics collector records final success separately from repair count.

The metrics collector reads all known TDD bindings when the command has no TDD path.

The metrics collector returns a collection by default when one TDD has more than one run.

The metrics collector does not read chat transcript text.

The metrics collector does not include full log text in the metrics record.

## Acceptance Criteria

- AC-MI-01: Acceptance tests prove the collector reads one TDD binding when the user supplies a TDD path.

- AC-MI-02: Acceptance tests prove the collector reads all known TDD bindings when the command has no TDD path.

- AC-MI-03: Acceptance tests prove the collector validates canonical bindings after index lookup.

- AC-MI-04: Acceptance tests prove the collector reads the run index.

- AC-MI-05: Acceptance tests prove the collector reads run records.

- AC-MI-06: Acceptance tests prove the collector reads receipt-chain status.

- AC-MI-07: Acceptance tests prove the collector reads verification-plan output.

- AC-MI-08: Acceptance tests prove the collector reads run-check records.

- AC-MI-09: Acceptance tests prove the collector reads verify-checks output.

- AC-MI-10: Acceptance tests prove the collector reads candidate CI records.

- AC-MI-11: Acceptance tests prove the collector reads main CI records.

- AC-MI-12: Acceptance tests prove the collector reads lifecycle diagnostics.

- AC-RS-01: CLI tests prove one TDD path with no run selector emits all runs for that TDD.

- AC-RS-02: CLI tests prove no TDD path emits all runs for all known TDDs.

- AC-RS-03: CLI tests prove `--run` emits one implementation run.

- AC-RS-04: CLI tests prove `--latest` emits the highest ordinal run.

- AC-RS-05: CLI tests prove `--run` with `--latest` returns blocked status.

- AC-RS-06: CLI tests prove `kotekomi-agent tdd-metrics <tdd-path>` runs as documented.

- AC-RS-07: CLI tests prove `kotekomi-agent tdd-metrics` runs as documented.

- AC-RS-08: CLI tests prove `--output` writes an optional JSON copy.

- AC-RS-09: CLI tests prove `--markdown` writes an optional Markdown copy.

- AC-MO-01: Acceptance tests prove one metrics record exists for one implementation run.

- AC-MO-02: Acceptance tests prove a metrics collection exists for one or more metrics records.

- AC-MO-03: Schema tests prove each metrics record includes `task_id`.

- AC-MO-04: Schema tests prove each metrics record includes `primary_tdd_path`.

- AC-MO-05: Schema tests prove each metrics record includes `tdd_paths`.

- AC-MO-06: Schema tests prove the metrics collection includes `metrics_record_paths`.

- AC-MO-07: Schema tests prove each metrics record includes `implementation_run_id`.

- AC-MO-08: Fixture tests prove receipt counts.

- AC-MO-09: Fixture tests prove digest mismatch counts.

- AC-MO-10: Fixture tests prove lifecycle readiness values.

- AC-MO-11: Fixture tests prove planned check count.

- AC-MO-12: Fixture tests prove executed check count.

- AC-MO-13: Fixture tests prove verified check count.

- AC-MO-14: Fixture tests prove failed check count.

- AC-MO-15: Fixture tests prove candidate CI conclusion.

- AC-MO-16: Fixture tests prove main CI conclusion.

- AC-MO-17: Fixture tests prove repair count.

- AC-MO-18: Fixture tests prove budget violation count.

- AC-MO-19: Fixture tests prove protected artifact violation count.

- AC-MO-20: Fixture tests prove branch cleanup status.

- AC-MO-21: Schema tests prove the metrics collection includes `metrics_collection_path`.

- AC-DI-01: Fixture tests prove missing TDD binding returns blocked status.

- AC-DI-02: Fixture tests prove missing receipt-chain status returns blocked status.

- AC-DI-03: Fixture tests prove missing final evidence returns partial status.

- AC-DI-04: Fixture tests prove digest mismatch returns blocked status.

- AC-DI-05: Fixture tests prove missing run record returns blocked status.

## Reference Implementations

- TDD binding: follow `packages/devtools/src/kotekomi_devtools/tdd_binding.py`.

- Run state: follow `packages/devtools/src/kotekomi_devtools/implement_tdd.py`.

- Receipt-chain status: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- Verification execution records: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.

- Verification checks: follow `packages/devtools/src/kotekomi_devtools/verify_checks.py`.

- Lifecycle diagnostics: follow `packages/devtools/src/kotekomi_devtools/lifecycle_check.py`.

## Constraints and Halt Conditions

The implementer must halt if existing run-check records do not expose stable enough fields for executed and failed counts.

The implementer must halt if receipt-chain status cannot expose missing receipt and digest mismatch counts.

The implementer must halt if run records cannot distinguish active, blocked, complete, and abandoned runs.
