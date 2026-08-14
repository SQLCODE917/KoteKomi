# TDD Scorecards and Comparison

## Context & Problem

A user wants to compare the effectiveness of Technical Design Documents.

The user knows each Technical Design Document by local file path.

A TDD can have one implementation run or many implementation runs.

TDD metrics provide raw facts for one implementation run.

The user still needs a scorecard that converts those facts into comparable dimensions.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `TDD scorecard` for the scored report for one TDD implementation run.

This TDD uses the term `score dimension` for one named score derived from TDD metrics.

This TDD uses the term `TDD comparison` for a report that compares two or more TDD scorecards.

Primary end-to-end Flow:

1. The user gives the Harness one TDD path or asks for all known scorecards.

2. The Harness reads or computes TDD metrics for the selected runs.

3. The Harness computes one or more TDD scorecards.

4. The user gives the Harness two or more TDD paths or scorecards for comparison.

5. The Harness computes a TDD comparison.

6. The user reads raw metrics, score dimensions, and confidence diagnostics.

## Goals

- The user can score all runs for one TDD path.

- The user can score one selected implementation run.

- The user can score all known TDDs without giving a TDD path.

- The user can compare TDDs by final success and implementation friction.

- The user can distinguish a good final result from a high-friction implementation.

- The user can see raw metrics beside derived scores.

- The user can compare repeated implementation runs for the same TDD.

## Requirements

Scorecard boundary:

- SC-01: The scorecard generator reads TDD metrics for all runs when the user supplies one TDD path and no run selector.

- SC-02: The scorecard generator reads all known TDD metrics when the user supplies no TDD path.

- SC-03: The scorecard generator reads one TDD metrics record when the user supplies `--run`.

- SC-04: The scorecard generator reads the highest ordinal TDD metrics record when the user supplies `--latest`.

- SC-05: The scorecard generator writes one TDD scorecard for each metrics record.

- SC-06: Each TDD scorecard includes the primary TDD path.

- SC-07: Each TDD scorecard includes all TDD paths.

- SC-08: Each TDD scorecard includes the TDD digest.

- SC-09: Each TDD scorecard includes the task identifier.

- SC-10: Each TDD scorecard includes the implementation run identifier.

- SC-11: Each TDD scorecard includes raw metrics.

- SC-12: Each TDD scorecard includes score dimensions.

- SC-13: Each TDD scorecard includes diagnostics.

- SC-14: The scorecard collection includes `scorecard_collection_path`.

- SC-15: The scorecard collection includes `scorecard_record_paths`.

Score dimension boundary:

- SD-01: The scorecard includes `scope_discipline`.

- SD-02: The scorecard includes `verification_completeness`.

- SD-03: The scorecard includes `first_pass_effectiveness`.

- SD-04: The scorecard includes `repair_efficiency`.

- SD-05: The scorecard includes `lifecycle_completeness`.

- SD-06: The scorecard includes `evidence_confidence`.

- SD-07: The scorecard includes `overall_score` for complete and partial scorecards.

- SD-08: The scorecard has no `overall_score` for blocked scorecards.

Score formula boundary:

- SF-01: `evidence_confidence` starts at 100 and subtracts 10 for each missing receipt up to 100.

- SF-02: `evidence_confidence` becomes 0 when digest mismatch count is greater than 0.

- SF-03: `verification_completeness` equals verified check count divided by planned check count times 100.

- SF-04: `verification_completeness` equals 0 when planned check count is 0.

- SF-05: `lifecycle_completeness` equals 100 when candidate lifecycle and main lifecycle are ready.

- SF-06: `lifecycle_completeness` equals 50 when exactly one lifecycle value is ready.

- SF-07: `lifecycle_completeness` equals 0 when neither lifecycle value is ready.

- SF-08: `scope_discipline` starts at 100 and subtracts 20 for each budget violation and protected artifact violation up to 100.

- SF-09: `first_pass_effectiveness` equals 100 when repair count is 0 and both CI conclusions are success.

- SF-10: `first_pass_effectiveness` equals 50 when repair count is 0 and exactly one CI conclusion is success.

- SF-11: `first_pass_effectiveness` equals 0 when repair count is greater than 0.

- SF-12: `repair_efficiency` starts at 100 and subtracts 25 for each repair count up to 100.

- SF-13: `overall_score` weights evidence confidence at 20 percent.

- SF-14: `overall_score` weights verification completeness at 20 percent.

- SF-15: `overall_score` weights lifecycle completeness at 20 percent.

- SF-16: `overall_score` weights scope discipline at 15 percent.

- SF-17: `overall_score` weights first-pass effectiveness at 15 percent.

- SF-18: `overall_score` weights repair efficiency at 10 percent.

- SF-19: The score engine rounds each dimension score and overall score to the nearest integer.

- SF-20: The score engine rounds a fractional part of exactly 0.5 away from zero.

- SF-21: The score engine clamps each score to the range 0 through 100 after rounding.

Status boundary:

- SB-01: A complete metrics record produces a complete scorecard.

- SB-02: A partial metrics record produces a partial scorecard.

- SB-03: A blocked metrics record produces a blocked scorecard.

- SB-04: A partial scorecard computes available dimensions and lowers evidence confidence.

- SB-05: A blocked scorecard preserves diagnostics and omits overall score.

Comparison boundary:

- CP-01: The comparison generator reads two or more TDD paths.

- CP-02: The comparison generator reads two or more TDD scorecard files.

- CP-03: The comparison generator writes a comparison JSON report.

- CP-04: The comparison generator writes a comparison Markdown report.

- CP-05: The comparison report orders scorecards by overall score.

- CP-06: The comparison report orders complete scorecards before partial scorecards when overall scores tie.

- CP-07: The comparison report orders partial scorecards before blocked scorecards.

- CP-08: The comparison report orders equal scorecards by primary TDD path and implementation run identifier.

- CP-09: The comparison report shows raw metric deltas.

- CP-10: The comparison report shows score dimension deltas.

- CP-11: The comparison report shows evidence confidence for each scorecard.

- CP-12: The comparison report includes `comparison_report_path`.

- CP-13: The comparison report includes `scorecard_input_paths`.

## Proposed Architecture

The scorecard command owns scorecard generation.

The comparison command owns comparison generation.

The metrics command owns metrics creation when no metrics record exists.

The score engine owns deterministic score dimensions.

The report writer owns stdout JSON and optional report copies.

```text
+------------------+      +-------------------+      +------------------+
| Operator         | ---> | Scorecard command | ---> | Metrics command  |
+------------------+      +-------------------+      +------------------+
                                      |                         |
                                      v                         v
                            +-------------------+      +------------------+
                            | Score engine      | <--- | TDD metrics     |
                            +-------------------+      +------------------+
                                      |
                                      v
                            +-------------------+
                            | TDD scorecard     |
                            +-------------------+
                                      |
                                      v
+------------------+      +-------------------+      +-------------------+
| Operator         | ---> | Compare command   | ---> | Comparison report |
+------------------+      +-------------------+      +-------------------+
```

## Key Interactions

Single scorecard sequence:

```text
Operator      Scorecard command      Metrics command      Score engine      Report writer
   |                  |                    |                  |                 |
   | score path       |                    |                  |                 |
   |----------------->|                    |                  |                 |
   |                  | read metrics       |                  |                 |
   |                  |------------------->|                  |                 |
   |                  | metrics            |                  |                 |
   |                  |<-------------------|                  |                 |
   |                  | compute score      |                  |                 |
   |                  |-------------------------------------->|                 |
   |                  | scorecard          |                  |                 |
   |                  |<--------------------------------------|                 |
   |                  | write report       |                  |                 |
   |                  |------------------------------------------------------>|
   | scorecard result |                    |                  |                 |
   |<-----------------|                    |                  |                 |
```

Comparison sequence:

```text
Operator      Compare command      Scorecard resolver      Report writer
   |                |                       |                  |
   | compare        |                       |                  |
   |--------------->|                       |                  |
   |                | resolve scorecards    |                  |
   |                |---------------------->|                  |
   |                | scorecards            |                  |
   |                |<----------------------|                  |
   |                | write comparison      |                  |
   |                |----------------------------------------->|
   | comparison     |                       |                  |
   |<---------------|                       |                  |
```

## Data Model

The Harness will create one TDD scorecard record per metrics record.

The scorecard record path is:

```text
<state-root>/experiments/<task-id>/runs/<implementation-run-id>/scorecard/tdd-scorecard.json
```

The scorecard collection path for one task is:

```text
<state-root>/experiments/<task-id>/scorecards/tdd-scorecard-collection.json
```

The scorecard collection path for all known TDDs is:

```text
<state-root>/tdds/scorecards/tdd-scorecard-collection.json
```

The TDD scorecard record has these fields:

- `schema_version`

- `task_id`

- `primary_tdd_path`

- `tdd_paths`

- `tdd_sha256`

- `implementation_run_id`

- `status`

- `raw_metrics`

- `score_dimensions`

- `overall_score`

- `diagnostics`

The score dimensions object has these fields:

- `scope_discipline`

- `verification_completeness`

- `first_pass_effectiveness`

- `repair_efficiency`

- `lifecycle_completeness`

- `evidence_confidence`

The scorecard collection has these fields:

- `schema_version`

- `status`

- `scorecard_collection_path`

- `scorecard_record_paths`

- `scorecards`

- `diagnostics`

The `scorecard_record_paths` value maps implementation run identifiers to scorecard record paths.

The comparison report has these fields:

- `schema_version`

- `comparison_report_path`

- `scorecard_input_paths`

- `scorecards`

- `ranking`

- `raw_metric_deltas`

- `score_dimension_deltas`

- `diagnostics`

The Harness will read scorecards by primary TDD path.

The Harness will read scorecards by TDD digest.

The Harness will read scorecards by implementation run identifier.

## APIs / Interfaces

The all-runs single TDD scorecard CLI contract is:

```text
kotekomi-agent tdd-score <tdd-path> [--output <scorecard-json>] [--markdown <scorecard-md>]
```

The one-run scorecard CLI contract is:

```text
kotekomi-agent tdd-score <tdd-path> --run <implementation-run-id> [--output <scorecard-json>] [--markdown <scorecard-md>]
```

The latest-run scorecard CLI contract is:

```text
kotekomi-agent tdd-score <tdd-path> --latest [--output <scorecard-json>] [--markdown <scorecard-md>]
```

The all known scorecards CLI contract is:

```text
kotekomi-agent tdd-score [--output <scorecards-json>] [--markdown <scorecards-md>]
```

The comparison CLI contract for TDD paths is:

```text
kotekomi-agent tdd-compare <tdd-path> <tdd-path> [<tdd-path>...] [--output <comparison-json>] [--markdown <comparison-md>]
```

The comparison CLI contract for scorecards is:

```text
kotekomi-agent tdd-compare --scorecard <scorecard-json> --scorecard <scorecard-json> [--scorecard <scorecard-json>...] [--output <comparison-json>] [--markdown <comparison-md>]
```

Both comparison forms require at least two inputs.

The CLI prints scorecard or comparison JSON to stdout when `--output` is absent.

The `--output` file is an optional JSON copy.

The `--markdown` file is an optional Markdown copy.

Each score dimension uses a numeric range from 0 through 100.

The overall score uses a numeric range from 0 through 100 for complete and partial scorecards.

Blocked scorecards omit overall score.

## Behavior & Domain Rules

The scorecard generator computes scores from TDD metrics.

The scorecard generator computes metrics when no metrics record exists for the selected run.

The scorecard generator computes scorecards for all runs of one TDD when the command has one TDD path and no run selector.

The scorecard generator computes scorecards for all known TDDs when the command has no TDD path.

The scorecard generator blocks when `--run` and `--latest` appear together.

The scorecard generator preserves raw metrics in the TDD scorecard.

The scorecard generator lowers evidence confidence when required evidence is missing.

The scorecard generator records blocked status when TDD metrics status is blocked.

The scorecard generator records partial status when TDD metrics status is partial.

The scorecard generator records complete status when TDD metrics status is complete.

The comparison generator orders scorecards by the comparison boundary rules.

The comparison generator shows repair count separately from final CI conclusions.

The comparison generator does not overwrite input scorecards.

## Acceptance Criteria

- AC-SC-01: CLI tests prove the scorecard command reads all runs for one TDD path.

- AC-SC-02: CLI tests prove the scorecard command reads all known TDDs when the command has no TDD path.

- AC-SC-03: CLI tests prove the scorecard command reads one run with `--run`.

- AC-SC-04: CLI tests prove the scorecard command reads the highest ordinal run with `--latest`.

- AC-SC-05: CLI tests prove the scorecard command writes one scorecard per metrics record.

- AC-SC-EX-01: CLI tests prove `kotekomi-agent tdd-score <tdd-path>` runs as documented.

- AC-SC-EX-02: CLI tests prove `kotekomi-agent tdd-score` runs as documented.

- AC-SC-EX-03: CLI tests prove `--output` writes an optional JSON copy.

- AC-SC-EX-04: CLI tests prove `--markdown` writes an optional Markdown copy.

- AC-SC-06: Schema tests prove each scorecard includes the primary TDD path.

- AC-SC-07: Schema tests prove each scorecard includes all TDD paths.

- AC-SC-08: Schema tests prove each scorecard includes the TDD digest.

- AC-SC-09: Schema tests prove each scorecard includes the task identifier.

- AC-SC-10: Schema tests prove each scorecard includes the implementation run identifier.

- AC-SC-11: Schema tests prove each scorecard includes raw metrics.

- AC-SC-12: Schema tests prove each scorecard includes score dimensions.

- AC-SC-13: Schema tests prove each scorecard includes diagnostics.

- AC-SC-14: Schema tests prove the collection includes `scorecard_collection_path`.

- AC-SC-15: Schema tests prove the collection includes `scorecard_record_paths`.

- AC-SD-01: Unit tests prove the scorecard includes `scope_discipline`.

- AC-SD-02: Unit tests prove the scorecard includes `verification_completeness`.

- AC-SD-03: Unit tests prove the scorecard includes `first_pass_effectiveness`.

- AC-SD-04: Unit tests prove the scorecard includes `repair_efficiency`.

- AC-SD-05: Unit tests prove the scorecard includes `lifecycle_completeness`.

- AC-SD-06: Unit tests prove the scorecard includes `evidence_confidence`.

- AC-SD-07: Unit tests prove complete and partial scorecards include `overall_score`.

- AC-SD-08: Unit tests prove blocked scorecards omit `overall_score`.

- AC-SF-01: Unit tests prove each formula requirement from SF-01 through SF-18.

- AC-SF-02: Unit tests prove half-up rounding for values with a fractional part of exactly 0.5.

- AC-SF-03: Unit tests prove scores clamp to 0 through 100 after rounding.

- AC-SB-01: Unit tests prove complete metrics produce complete scorecards.

- AC-SB-02: Unit tests prove partial metrics produce partial scorecards.

- AC-SB-03: Unit tests prove blocked metrics produce blocked scorecards.

- AC-SB-04: Unit tests prove partial scorecards compute available dimensions and lower evidence confidence.

- AC-SB-05: Unit tests prove blocked scorecards preserve diagnostics and omit overall score.

- AC-CP-01: CLI tests prove comparison reads two or more TDD paths.

- AC-CP-02: CLI tests prove comparison reads two or more scorecards.

- AC-CP-03: CLI tests prove comparison writes JSON.

- AC-CP-04: CLI tests prove comparison writes Markdown.

- AC-CP-05: Unit tests prove comparison order by overall score.

- AC-CP-06: Unit tests prove complete scorecards sort before partial scorecards when overall scores tie.

- AC-CP-07: Unit tests prove partial scorecards sort before blocked scorecards.

- AC-CP-08: Unit tests prove equal scorecards sort by primary TDD path and implementation run identifier.

- AC-CP-EX-01: CLI tests prove `kotekomi-agent tdd-compare <tdd-path> <tdd-path>` runs as documented.

- AC-CP-EX-02: CLI tests prove scorecard-file comparison runs without optional output flags.

- AC-CP-09: Unit tests prove raw metric deltas appear in comparison output.

- AC-CP-10: Unit tests prove score dimension deltas appear in comparison output.

- AC-CP-11: Unit tests prove evidence confidence appears for each scorecard.

- AC-CP-12: Schema tests prove comparison output includes `comparison_report_path`.

- AC-CP-13: Schema tests prove comparison output includes `scorecard_input_paths`.

## Reference Implementations

- Metrics input: follow `packages/devtools/src/kotekomi_devtools/tdd_metrics.py`.

- Receipt diagnostics: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- Markdown reports: follow existing verification-plan Markdown output.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if the score formula cannot preserve raw metrics beside derived scores.

The implementer must halt if comparison cannot distinguish complete, partial, and blocked scorecards.

The implementer must halt if metrics cannot distinguish implementation runs.
