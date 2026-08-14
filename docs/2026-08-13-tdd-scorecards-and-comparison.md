# TDD Scorecards and Comparison

## Context & Problem

A user wants to compare the effectiveness of Technical Design Documents.

The user knows each Technical Design Document by local file path.

TDD metrics provide raw facts for one implementation run.

The user still needs a scorecard that converts those facts into comparable dimensions.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `TDD scorecard` for the scored report for one TDD implementation run.

This TDD uses the term `score dimension` for one named score derived from TDD metrics.

This TDD uses the term `TDD comparison` for a report that compares two or more TDD scorecards.

Primary end-to-end Flow:

1. The user gives the Harness one TDD path or asks for all known scorecards.

2. The Harness reads or computes TDD metrics.

3. The Harness computes one or more TDD scorecards.

4. The user gives the Harness two or more TDD paths or scorecards for comparison.

5. The Harness computes a TDD comparison.

6. The user reads raw metrics, score dimensions, and confidence diagnostics.

## Goals

- The user can score one TDD from its TDD path.

- The user can score all known TDDs without giving a TDD path.

- The user can compare TDDs by final success and implementation friction.

- The user can distinguish a good final result from a high-friction implementation.

- The user can see raw metrics beside derived scores.

- The user can compare repeated implementation runs for the same TDD.

## Requirements

Scorecard boundary:

- SC-01: The scorecard generator reads one TDD metrics collection when the user supplies a TDD path.

- SC-02: The scorecard generator reads all known TDD metrics when the user supplies no TDD path.

- SC-03: The scorecard generator writes one TDD scorecard for each selected metrics record.

- SC-04: Each TDD scorecard includes the primary TDD path.

- SC-05: Each TDD scorecard includes TDD paths.

- SC-06: Each TDD scorecard includes the TDD digest.

- SC-07: Each TDD scorecard includes the task identifier.

- SC-08: Each TDD scorecard includes the implementation run identifier.

- SC-09: Each TDD scorecard includes raw metrics.

- SC-10: Each TDD scorecard includes score dimensions.

- SC-11: Each TDD scorecard includes diagnostics.

Score dimension boundary:

- SD-01: The scorecard includes `scope_discipline`.

- SD-02: The scorecard includes `verification_completeness`.

- SD-03: The scorecard includes `first_pass_effectiveness`.

- SD-04: The scorecard includes `repair_efficiency`.

- SD-05: The scorecard includes `lifecycle_completeness`.

- SD-06: The scorecard includes `evidence_confidence`.

- SD-07: The scorecard includes `provisional_overall_score` when the scorecard status is complete or partial.

- SD-08: The scorecard includes `overall_score` only when `ranking_eligible` is true.

- SD-09: The scorecard includes `ranking_eligible`.

Comparison boundary:

- CP-01: The comparison generator reads two or more TDD paths.

- CP-02: The comparison generator reads two or more TDD scorecards.

- CP-03: The comparison generator writes a comparison JSON report.

- CP-04: The comparison generator writes a comparison Markdown report when requested.

- CP-05: The comparison report ranks only scorecards with `ranking_eligible` true.

- CP-06: The comparison report shows raw metric deltas.

- CP-07: The comparison report shows score dimension deltas.

- CP-08: The comparison report shows evidence confidence for each scorecard.

- CP-09: The comparison identifier is deterministic from input scorecard digests.

## Proposed Architecture

The scorecard command owns scorecard generation.

The comparison command owns comparison generation.

The metrics command owns metrics creation when no metrics record exists.

The score engine owns deterministic score dimensions.

The report writer owns JSON and Markdown output.

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

The canonical scorecard record path is `<state-root>/experiments/<task-id>/runs/<implementation-run-id>/scorecard/tdd-scorecard.json`.

The per-task scorecard collection path is `<state-root>/experiments/<task-id>/scorecards/tdd-scorecards.collection.json`.

The all-known scorecard global report path is `<state-root>/tdds/reports/scorecards/all-known.scorecards.json`.

The comparison global report path is `<state-root>/tdds/reports/comparisons/<comparison-id>.json`.

Scorecard collection records are aggregate reports.

Scorecard collection records do not appear in a run evidence index.

Comparison reports are global reports.

Comparison reports do not appear in a run evidence index.

Run-scoped scorecard records appear in the run evidence index.

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

- `provisional_overall_score`

- `overall_score`

- `ranking_eligible`

- `diagnostics`

The score dimensions object has these fields:

- `scope_discipline`

- `verification_completeness`

- `first_pass_effectiveness`

- `repair_efficiency`

- `lifecycle_completeness`

- `evidence_confidence`

The scorecard collection record has these fields:

- `schema_version`

- `status`

- `scorecard_collection_path`

- `scorecard_record_paths`

- `scorecards`

- `diagnostics`

The comparison report has these fields:

- `schema_version`

- `comparison_id`

- `scorecards`

- `ranking`

- `raw_metric_deltas`

- `score_dimension_deltas`

- `diagnostics`

## APIs / Interfaces

The scorecard CLI contract is:

```text
kotekomi-agent tdd-score [<tdd-path>] [--run <implementation-run-id>] [--latest] [--output <scorecard-json>] [--markdown <scorecard-md>]
```

The comparison CLI contract for TDD paths is:

```text
kotekomi-agent tdd-compare <tdd-path> <tdd-path> [<tdd-path>...] [--output <comparison-json>] [--markdown <comparison-md>]
```

The comparison CLI contract for scorecards is:

```text
kotekomi-agent tdd-compare --scorecard <scorecard-json> --scorecard <scorecard-json> [--scorecard <scorecard-json>...] [--output <comparison-json>] [--markdown <comparison-md>]
```

All commands print JSON to stdout by default.

The optional `--output` path writes a JSON copy.

The optional `--markdown` path writes a Markdown copy.

## Behavior & Domain Rules

The scorecard generator computes scores from TDD metrics.

The scorecard generator computes metrics when no metrics record exists for the selected TDD path and run.

The scorecard generator computes scorecards for all known TDDs and all runs when the command has no TDD path and no selector.

The scorecard generator computes scorecards for all runs for one TDD when the command has a TDD path and no selector.

The `--latest` selector requires a TDD path.

The `--run` selector requires a TDD path.

The `--run` selector is mutually exclusive with `--latest`.

The scorecard generator preserves raw metrics in the TDD scorecard.

The scorecard generator records blocked status when TDD metrics status is blocked.

The scorecard generator records partial status when TDD metrics status is partial.

The scorecard generator records complete status when TDD metrics status is complete.

The score engine computes `evidence_confidence` as `100 - min(100, receipt_missing_count * 20 + digest_mismatch_count * 40 + missing_evidence_count * 15)`.

The score engine sets `verification_completeness` to 100 when `planned_check_count` is 0 and `verified_check_count` is 0.

The score engine computes `verification_completeness` as `100 * verified_check_count / planned_check_count` when `planned_check_count` is greater than 0.

The score engine computes `lifecycle_completeness` as the average of five components.

The candidate lifecycle component is 100 when `candidate_lifecycle_ready` is true and 0 otherwise.

The main lifecycle component is 100 when `main_lifecycle_ready` is true and 0 otherwise.

The candidate CI component is 100 when `candidate_ci_conclusion` is `success` and 0 otherwise.

The main CI component is 100 when `main_ci_conclusion` is `success` and 0 otherwise.

The cleanup component is 100 when `branch_cleanup_complete` is true and 0 otherwise.

The score engine computes `scope_discipline` as `100 - min(100, budget_violation_count * 25 + protected_artifact_violation_count * 50)`.

The score engine computes `first_pass_effectiveness` as `100 - min(100, repair_count * 20 + failed_check_count * 10 + candidate_ci_penalty)`.

The candidate CI penalty is 0 when `candidate_ci_conclusion` is `success`.

The candidate CI penalty is 25 when `candidate_ci_conclusion` is not `success`.

The score engine computes `repair_efficiency` as `100 - min(100, repair_count * 15)`.

The score engine treats missing numeric fields in partial metrics as 0.

The score engine treats missing boolean fields in partial metrics as false.

The score engine treats missing string conclusion fields in partial metrics as a non-success value.

The score engine adds a diagnostic for each missing field used by a partial scorecard dimension.

The provisional score uses these weights:

- `evidence_confidence`: 20 percent

- `verification_completeness`: 20 percent

- `lifecycle_completeness`: 20 percent

- `scope_discipline`: 15 percent

- `first_pass_effectiveness`: 15 percent

- `repair_efficiency`: 10 percent

The score engine computes each raw dimension value before rounding.

The score engine clamps each raw dimension value to the range 0 through 100 before rounding.

The score engine rounds each clamped dimension score to the nearest integer.

The score engine rounds fractional values ending in exactly `.5` away from zero.

The score engine computes the weighted provisional score from rounded dimension scores.

The score engine clamps the raw provisional score to the range 0 through 100 before rounding.

The score engine rounds the clamped provisional score to the nearest integer with the same `.5` tie rule.

A blocked scorecard has no provisional or comparable score.

A partial scorecard computes all dimensions with missing inputs set to the fallback values in this TDD.

A partial scorecard lowers evidence confidence through missing evidence count.

A partial scorecard records the computed value as `provisional_overall_score`.

A partial scorecard with zero evidence confidence sets `overall_score` to null.

A partial scorecard with zero evidence confidence sets `ranking_eligible` to false.

A partial scorecard with positive evidence confidence sets `overall_score` to `provisional_overall_score`.

A partial scorecard with positive evidence confidence sets `ranking_eligible` to true.

A complete scorecard sets both scores to the computed value.

A complete scorecard sets `ranking_eligible` to true.

The comparison generator excludes ineligible scorecards from `ranking`.

The comparison generator retains ineligible scorecards in the report for diagnostic analysis.

The comparison generator orders complete scorecards before partial scorecards when comparable scores are equal.

The comparison generator orders higher comparable scores before lower comparable scores.

The comparison generator orders equal scores by higher evidence confidence.

The comparison generator orders remaining ties by lexicographic implementation run identifier.

The comparison generator shows repair count separately from final CI conclusions.

The comparison generator does not overwrite input scorecards.

The scorecard digest is the SHA-256 digest of canonical scorecard JSON bytes.

The canonical scorecard JSON uses UTF-8, sorted keys, and no insignificant whitespace.

The comparison input is a UTF-8 JSON array of scorecard digest strings sorted lexicographically with no insignificant whitespace.

The comparison identifier is `compare-` plus the first 16 lowercase hexadecimal characters of SHA-256 over the comparison input.

The comparison command rejects duplicate scorecard digests.

## Acceptance Criteria

- AC-SC-01: CLI tests prove the scorecard command reads one TDD path.

- AC-SC-02: CLI tests prove the scorecard command reads all known TDDs when the command has no TDD path.

- AC-SC-03: CLI tests prove the scorecard command writes one scorecard per selected metrics record.

- AC-SC-03A: CLI tests prove `--latest` without a TDD path returns blocked status.

- AC-SC-03B: CLI tests prove `--run` without a TDD path returns blocked status.

- AC-SC-03C: CLI tests prove `--run` and `--latest` are mutually exclusive.

- AC-SC-04: Schema tests prove each scorecard includes the primary TDD path.

- AC-SC-05: Schema tests prove each scorecard includes TDD paths.

- AC-SC-06: Schema tests prove each scorecard includes the TDD digest.

- AC-SC-07: Schema tests prove each scorecard includes the task identifier.

- AC-SC-08: Schema tests prove each scorecard includes the implementation run identifier.

- AC-SC-09: Schema tests prove each scorecard includes raw metrics.

- AC-SC-10: Schema tests prove each scorecard includes score dimensions.

- AC-SC-11: Schema tests prove each scorecard includes diagnostics.

- AC-SD-01: Unit tests prove `scope_discipline` changes when budget violations change.

- AC-SD-02: Unit tests prove `verification_completeness` changes when verified check count changes.

- AC-SD-03: Unit tests prove `first_pass_effectiveness` changes when repair count changes.

- AC-SD-04: Unit tests prove `repair_efficiency` changes when repair count changes.

- AC-SD-05: Unit tests prove `lifecycle_completeness` changes when lifecycle readiness changes.

- AC-SD-06: Unit tests prove `evidence_confidence` changes when missing receipt count changes.

- AC-SD-06A: Unit tests prove `evidence_confidence` changes when missing evidence count changes.

- AC-SD-07: Unit tests prove `provisional_overall_score` uses the weights from this TDD.

- AC-SD-07A: Unit tests prove zero planned checks produce 100 verification completeness when verified check count is 0.

- AC-SD-07B: Unit tests prove candidate CI penalty changes first-pass effectiveness.

- AC-SD-07C: Unit tests prove partial scorecards with zero evidence confidence have no comparable score.

- AC-SD-07D: Unit tests prove partial scorecards retain a provisional score when evidence confidence is zero.

- AC-SD-07E: Unit tests prove `ranking_eligible` follows evidence confidence and scorecard status.

- AC-SD-08: Unit tests prove `.5` scores round away from zero.

- AC-CP-01: CLI tests prove comparison reads two or more TDD paths.

- AC-CP-02: CLI tests prove comparison reads two or more scorecards.

- AC-CP-03: CLI tests prove comparison writes JSON by default.

- AC-CP-04: CLI tests prove optional Markdown output works.

- AC-CP-05: Unit tests prove comparison order by status, score, evidence confidence, and run identifier.

- AC-CP-06: Unit tests prove raw metric deltas appear in comparison output.

- AC-CP-07: Unit tests prove score dimension deltas appear in comparison output.

- AC-CP-08: Unit tests prove evidence confidence appears for each scorecard.

- AC-CP-09: Unit tests prove comparison identifier derivation is deterministic.

- AC-CP-10: Unit tests prove duplicate scorecard digests are rejected.

## Reference Implementations

- Metrics input: follow `packages/devtools/src/kotekomi_devtools/tdd_metrics.py`.

- Receipt diagnostics: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- Markdown reports: follow existing verification-plan Markdown output.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if the score formula cannot preserve raw metrics beside derived scores.

The implementer must halt if comparison cannot distinguish complete, partial, and blocked scorecards.
