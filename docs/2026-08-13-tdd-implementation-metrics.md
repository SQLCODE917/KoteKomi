# TDD Implementation Metrics

## Context & Problem

A user wants to compare the effectiveness of Technical Design Documents.

The user knows each Technical Design Document by local file path.

The Harness records evidence during implementation, but it does not yet collect that evidence into TDD implementation metrics.

The user cannot compare TDDs unless the Harness normalizes lifecycle, verification, repair, CI, cleanup, and receipt evidence for each TDD.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `implementation run` for one attempt to implement one TDD from intake through completion or block.

This TDD uses the term `TDD metrics` for the normalized facts that the Harness collects for one implementation run.

This TDD uses the term `repair count` for the number of failed or blocked evidence events before the final status.

Primary end-to-end Flow:

1. The user asks for metrics for one TDD path or for all known TDDs.

2. The Harness resolves each TDD path to a TDD binding.

3. The Harness resolves implementation runs for each task identifier.

4. The Harness reads the evidence index and evidence event log for each implementation run.

5. The Harness validates each evidence record through type-specific trusted fields.

6. The Harness computes TDD metrics for each selected implementation run.

7. The Harness writes run-scoped metrics records and a metrics collection report.

## Goals

- The user can inspect raw implementation facts for one TDD path.

- The user can inspect raw implementation facts for all known TDDs.

- The user can see whether a TDD produced a clean first pass.

- The user can see whether a TDD produced repair work.

- The user can use the same metrics schema for all TDD implementations.

## Requirements

Metrics input boundary:

- MI-01: The metrics collector reads one TDD binding when the user supplies a TDD path.

- MI-02: The metrics collector reads all known TDD bindings when the user supplies no TDD path.

- MI-03: The metrics collector reads all runs for the selected TDD when the user supplies no run selector.

- MI-04: The metrics collector reads one run when the user supplies `--run <implementation-run-id>`.

- MI-05: The metrics collector reads the latest run by run ordinal when the user supplies `--latest`.

- MI-05A: The metrics collector returns blocked status when the user supplies `--latest` without a TDD path.

- MI-05B: The metrics collector returns blocked status when the user supplies `--run` without a TDD path.

- MI-05C: The metrics collector returns blocked status when the user supplies both `--run` and `--latest`.

- MI-06: The metrics collector reads the evidence index for each selected implementation run.

- MI-07: The metrics collector reads the evidence event log for each selected implementation run.

- MI-08: The metrics collector validates each referenced evidence record digest before it trusts the record.

- MI-09: The metrics collector reads type-specific trusted fields from each evidence record.

Metrics output boundary:

- MO-01: The metrics collector writes one metrics record for one implementation run.

- MO-02: The metrics collector writes a metrics collection for each command invocation.

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

- MO-21: Each metrics record includes required evidence count.

- MO-22: Each metrics record includes present evidence count.

- MO-23: Each metrics record includes missing evidence count.

- MO-24: The metrics collection includes `metrics_collection_path`.

- MO-25: The metrics collection includes `metrics_record_paths`.

Diagnostics boundary:

- DI-01: The metrics collector reports missing TDD binding as blocked status for one TDD path.

- DI-02: The metrics collector reports missing evidence index as blocked status for that metrics record.

- DI-03: The metrics collector reports missing optional evidence as partial status.

- DI-04: The metrics collector reports digest mismatch as blocked status for that metrics record.

## Proposed Architecture

The metrics command owns the operator boundary.

The TDD binding store owns TDD lookup.

The run index owns implementation run lookup.

The evidence catalog owns evidence discovery.

The metrics collector owns metric normalization.

The metrics report writer owns JSON and Markdown output.

```text
+------------------+      +------------------+      +-------------------+
| Operator         | ---> | Metrics command  | ---> | TDD binding store |
+------------------+      +------------------+      +-------------------+
                                      |                         |
                                      v                         v
                            +-------------------+      +------------------+
                            | Run index         | ---> | Evidence catalog |
                            +-------------------+      +------------------+
                                      |                         |
                                      v                         v
                            +-------------------+      +------------------+
                            | Metrics collector | <--- | Evidence records |
                            +-------------------+      +------------------+
                                      |
                                      v
                            +-------------------+
                            | Metrics reports   |
                            +-------------------+
```

## Key Interactions

Single TDD sequence:

```text
Operator      Metrics command      Binding store      Run index      Evidence catalog      Report writer
   |                |                    |                |                 |                  |
   | metrics path   |                    |                |                 |                  |
   |--------------->|                    |                |                 |                  |
   |                | read binding       |                |                 |                  |
   |                |------------------->|                |                 |                  |
   |                | binding            |                |                 |                  |
   |                |<-------------------|                |                 |                  |
   |                | read runs          |                |                 |                  |
   |                |------------------------------------>|                 |                  |
   |                | runs               |                |                 |                  |
   |                |<------------------------------------|                 |                  |
   |                | read evidence      |                |                 |                  |
   |                |---------------------------------------------------->|                  |
   |                | metrics records    |                |                 |                  |
   |                |<----------------------------------------------------|                  |
   |                | write report       |                |                 |                  |
   |                |------------------------------------------------------------------------>|
   | metrics result |                    |                |                 |                  |
   |<---------------|                    |                |                 |                  |
```

## Data Model

The canonical metrics record path is `<state-root>/experiments/<task-id>/runs/<implementation-run-id>/metrics/tdd-metrics.json`.

The per-task metrics collection path is `<state-root>/experiments/<task-id>/metrics/tdd-metrics.collection.json`.

The all-known metrics global report path is `<state-root>/tdds/reports/metrics/all-known.metrics.json`.

Metrics collection records are aggregate reports.

Metrics collection records do not appear in a run evidence index.

Run-scoped metrics records appear in the run evidence index.

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

- `required_evidence_count`

- `present_evidence_count`

- `missing_evidence_count`

- `diagnostics`

The metrics collection record has these fields:

- `schema_version`

- `status`

- `metrics_collection_path`

- `metrics_record_paths`

- `metrics`

- `diagnostics`

The `metrics_record_paths` map uses implementation run identifiers as keys and state-root-relative metrics record paths as values.

## APIs / Interfaces

The metrics CLI contracts are:

```text
kotekomi-agent tdd-metrics [<tdd-path>] [--run <implementation-run-id>] [--latest] [--output <metrics-json>] [--markdown <metrics-md>]
```

The command with no TDD path returns metrics for all known TDDs and all known runs.

The command with a TDD path and no run selector returns metrics for all runs for that TDD.

The `--run` selector returns metrics for one run.

The command with no TDD path and no selector returns metrics for all known TDDs and all runs.

The command with a TDD path and no selector returns metrics for all runs for that TDD.

The `--latest` selector requires a TDD path.

The `--latest` selector returns metrics for the latest run from the run index.

The `--run` selector requires a TDD path.

The `--run` selector returns metrics for exactly one implementation run.

The `--run` selector is mutually exclusive with `--latest`.

The command prints JSON to stdout by default.

The optional `--output` path writes a JSON copy.

The optional `--markdown` path writes a Markdown copy.

## Behavior & Domain Rules

The metrics collector treats missing TDD binding as blocked status for one TDD path.

The metrics collector treats missing evidence index as blocked status for that metrics record.

The metrics collector treats digest mismatch as blocked status for that metrics record.

The metrics collector treats missing final evidence as partial status when earlier evidence is usable.

The metrics collector reads lifecycle readiness from `ready` in lifecycle records.

The metrics collector counts budget violations from lifecycle diagnostic codes with prefix `task_budget.`.

The metrics collector counts protected artifact violations from lifecycle diagnostic codes with prefix `protected_artifact.`.

The metrics collector reads planned check count from `verification_plan.planned_checks` unless `verify_checks` provides a stronger count.

The metrics collector reads executed, verified, and failed check counts from `verify_checks`.

The metrics collector reads individual failed check outcomes from `run_check` records when `verify_checks` is missing.

The metrics collector reads candidate CI and main CI conclusions from CI records.

The metrics collector reads branch cleanup status from the cleanup record.

The metrics collector reads receipt total, present, missing, and digest mismatch counts from receipt-chain status.

The metrics collector computes required evidence count from the phase-to-required-evidence matrix.

The metrics collector computes present evidence count from validated current entries in the evidence index.

The metrics collector computes missing evidence count as required evidence count minus present evidence count.

The metrics collector treats missing evidence count below zero as a blocked metrics diagnostic.

The metrics collector computes repair count from the evidence event log.

The metrics collector increments repair count for failed or blocked candidate lifecycle, run-check, verify-checks, candidate CI, main lifecycle, or main CI events before the final complete event.

The metrics collector records final success separately from repair count.

The metrics collector does not read chat transcript text.

The metrics collector does not include full log text in the metrics record.

## Acceptance Criteria

- AC-MI-01: Acceptance tests prove the collector reads one TDD binding when the user supplies a TDD path.

- AC-MI-02: Acceptance tests prove the collector reads all known TDD bindings when the command has no TDD path.

- AC-MI-03: Acceptance tests prove the collector reads all runs when no run selector exists.

- AC-MI-04: Acceptance tests prove `--run` selects one run.

- AC-MI-05: Acceptance tests prove `--latest` selects the latest run from the run index.

- AC-MI-05A: CLI tests prove `--latest` without a TDD path returns blocked status.

- AC-MI-05B: CLI tests prove `--run` without a TDD path returns blocked status.

- AC-MI-05C: CLI tests prove `--run` and `--latest` are mutually exclusive.

- AC-MI-06: Acceptance tests prove the collector reads the evidence index.

- AC-MI-07: Acceptance tests prove the collector reads the evidence event log.

- AC-MI-08: Acceptance tests prove digest mismatch in an indexed record blocks metrics for that run.

- AC-MO-01: Acceptance tests prove one metrics record exists for one implementation run.

- AC-MO-02: Acceptance tests prove all-runs output contains one record per selected implementation run.

- AC-MO-03: Schema tests prove each metrics record includes `task_id`.

- AC-MO-04: Schema tests prove each metrics record includes `primary_tdd_path`.

- AC-MO-05: Schema tests prove each metrics record includes `tdd_paths`.

- AC-MO-06: Schema tests prove the metrics collection includes `metrics_record_paths`.

- AC-MO-07: Fixture tests prove receipt counts.

- AC-MO-08: Fixture tests prove digest mismatch counts.

- AC-MO-09: Fixture tests prove lifecycle readiness values.

- AC-MO-10: Fixture tests prove planned check count.

- AC-MO-11: Fixture tests prove executed check count.

- AC-MO-12: Fixture tests prove verified check count.

- AC-MO-13: Fixture tests prove failed check count.

- AC-MO-14: Fixture tests prove candidate CI conclusion.

- AC-MO-15: Fixture tests prove main CI conclusion.

- AC-MO-16: Fixture tests prove repair count from evidence events.

- AC-MO-17: Fixture tests prove budget violation count from lifecycle diagnostics.

- AC-MO-18: Fixture tests prove protected artifact violation count from lifecycle diagnostics.

- AC-MO-19: Fixture tests prove branch cleanup status from cleanup evidence.

- AC-MO-20: Fixture tests prove required evidence count from the phase-to-required-evidence matrix.

- AC-MO-21: Fixture tests prove present evidence count from validated current evidence index entries.

- AC-MO-22: Fixture tests prove missing evidence count equals required evidence count minus present evidence count.

- AC-DI-01: Fixture tests prove missing TDD binding returns blocked status.

- AC-DI-02: Fixture tests prove missing evidence index returns blocked status.

- AC-DI-03: Fixture tests prove missing final evidence returns partial status.

- AC-DI-04: Fixture tests prove digest mismatch returns blocked status.

## Reference Implementations

- TDD binding: follow `packages/devtools/src/kotekomi_devtools/tdd_binding.py`.

- Evidence catalog: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Verification execution records: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.

- Task lifecycle records: follow `packages/devtools/src/kotekomi_devtools/task_lifecycle.py`.

- Receipt-chain status: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

## Constraints and Halt Conditions

The implementer must halt if existing run-check records do not expose stable check identifiers and outcomes.

The implementer must halt if receipt-chain status cannot expose total, present, missing, and digest mismatch counts.

The implementer must halt if lifecycle diagnostics cannot expose stable diagnostic codes.
