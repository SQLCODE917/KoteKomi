# TDD Metrics Repair History

## Context & Problem

The Harness writes one evidence event after it indexes each evidence record.

Each current event uses `status = ready` to report a successful index update.

The event does not record the outcome in the indexed evidence record.

The metrics collector therefore cannot distinguish a failed check from a passed check in the event log.

The metrics collector can report `repair_count = 0` after an implementation agent repairs a failed check.

The **evidence event** is one immutable JSON line that records one evidence-index update.

The **index status** reports whether the Harness wrote the evidence-index update.

The **evidence outcome** is the normalized result in the indexed evidence record.

The **repair-relevant event** is a candidate lifecycle, run check, check summary, candidate CI, main lifecycle, or main CI event.

The **repair** is one failed or blocked repair-relevant event that a later successful event replaces for the same evidence key.

The **legacy event log** is an event log that lacks an evidence outcome for one repair-relevant event.

Primary end-to-end flow:

1. A Harness producer writes a canonical evidence record.
2. The evidence catalog writes an evidence event with the index status and evidence outcome.
3. A later producer replaces a failed repair-relevant record with a successful record for the same evidence key.
4. The metrics collector counts the repaired failure from the event log.
5. The scorecard generator scores repair dimensions only when repair history is available.

## Goals

- A user can see repaired failures in TDD metrics.
- A user can distinguish unavailable legacy repair history from a clean first pass.
- A scorecard does not treat unavailable repair history as zero repairs.
- The Harness preserves immutable event history for each evidence replacement.

## Requirements

### Evidence event boundary

- EE-01: The evidence catalog writes `index_status = ready` for each indexed evidence record.
- EE-02: The evidence catalog does not write the current ambiguous event field `status`.
- EE-03: Each evidence event contains `evidence_outcome`.
- EE-04: Each evidence event contains `previous_sha256`.
- EE-05: The evidence catalog writes `previous_sha256 = null` for the first event for an evidence key.
- EE-06: The evidence catalog writes the replaced entry digest as `previous_sha256` for a replacement event.
- EE-07: The evidence catalog derives a lifecycle outcome as `ready` or `not_ready` from `ready`.
- EE-08: The evidence catalog derives a run-check outcome as `passed` or `failed` from `status`.
- EE-09: The evidence catalog derives a check-summary outcome as `passed` or `failed` from `status`.
- EE-10: The evidence catalog derives a CI outcome as `success`, `failure`, `cancelled`, or `skipped` from `conclusion`.
- EE-11: The evidence catalog derives a receipt outcome as `passed` or `failed` from `outcome`.
- EE-12: The evidence catalog blocks an indexed record whose evidence type has no defined event outcome rule.

### Metrics boundary

- ME-01: The metrics collector sets `repair_history_available = true` only when every repair-relevant event has `evidence_outcome`.
- ME-02: The metrics collector sets `repair_history_available = false` for a legacy event log.
- ME-03: The metrics collector writes `metrics.repair_history_unavailable` for a legacy event log.
- ME-04: The metrics collector counts each failed or blocked repair-relevant event that precedes a later successful event for the same evidence key.
- ME-05: The metrics collector does not count an unrepaired failed or blocked event as a repair.
- ME-06: The metrics collector retains `repair_count` as an integer.
- ME-07: The metrics collector writes `repair_count = 0` when repair history is unavailable.
- ME-08: The metrics collector requires `repair_history_available = true` before a consumer interprets `repair_count`.

### Scorecard boundary

- SC-01: The scorecard generator omits `first_pass_effectiveness` when repair history is unavailable.
- SC-02: The scorecard generator omits `repair_efficiency` when repair history is unavailable.
- SC-03: The scorecard record lists omitted dimensions in `omitted_score_dimensions`.
- SC-04: The scorecard record writes `scored_weight_total = 0.75` when it omits both repair dimensions.
- SC-05: The scorecard generator divides the remaining weighted dimension total by `scored_weight_total`.
- SC-06: The scorecard generator keeps the existing six-dimension score when repair history is available.
- SC-07: The scorecard generator writes `scorecard.repair_history_unavailable` when it omits repair dimensions.

## Proposed Architecture

The evidence catalog owns immutable evidence events.

The metrics collector owns repair-history availability and repair count.

The scorecard generator owns score-dimension omission and reweighting.

```text
Evidence producer -> Evidence catalog -> Evidence event log
                                      |
                                      v
                             Metrics collector -> Scorecard generator
```

## Key Interactions

```text
Run-check -> Evidence catalog: write failed run-check record
Evidence catalog -> Event log: append failed outcome event
Run-check -> Evidence catalog: replace record with passed result
Evidence catalog -> Event log: append passed outcome and prior digest
Metrics collector -> Event log: count the repaired failure
Scorecard generator -> Metrics record: score available dimensions
```

## Data Model

Each new evidence event contains these fields:

```text
schema_version: 2
task_id: string
implementation_run_id: string
event_type: evidence_indexed
phase: string
evidence_type: string
subject_id: string
index_status: ready
evidence_outcome: normalized outcome
sha256: SHA-256 digest
previous_sha256: SHA-256 digest | null
created_at: ISO-8601 timestamp
```

Each metrics record adds `repair_history_available`.

Each scorecard record adds `omitted_score_dimensions` and `scored_weight_total`.

## APIs / Interfaces

The public Harness commands retain their current arguments and output locations.

`tdd-metrics` returns `repair_history_available` with `repair_count`.

`tdd-score` returns `omitted_score_dimensions` and `scored_weight_total`.

## Behavior & Domain Rules

The evidence catalog writes event schema version 2 after this TDD lands.

The metrics collector treats every existing schema version 1 event as legacy history.

The metrics collector does not reconstruct a legacy outcome from Git history, log files, or chat text.

The scorecard generator keeps status `partial` when the metrics record has partial status.

The scorecard generator computes an overall score from available dimensions for a partial scorecard.

## Acceptance Criteria

- AC-EE-01: Evidence catalog tests prove new events contain index status, outcome, and prior digest.
- AC-EE-02: Evidence catalog tests prove each defined outcome mapping.
- AC-EE-03: Evidence catalog tests prove an unknown outcome mapping blocks event creation.
- AC-ME-01: Metrics tests prove failed then passed run-check events count one repair.
- AC-ME-02: Metrics tests prove two failed events before a passing replacement count two repairs.
- AC-ME-03: Metrics tests prove an unrepaired failure does not count as a repair.
- AC-ME-04: Metrics tests prove legacy events mark repair history unavailable with the required diagnostic.
- AC-SC-01: Scorecard tests prove legacy repair history omits both repair dimensions.
- AC-SC-02: Scorecard tests prove the legacy scorecard uses 0.75 scored weight and reweights its overall score.
- AC-SC-03: Scorecard tests prove complete repair history keeps all six dimensions and existing weights.

## Reference Implementations

- Evidence events: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Metrics records: follow `packages/devtools/src/kotekomi_devtools/tdd_metrics.py`.

- Scorecards: follow `packages/devtools/src/kotekomi_devtools/tdd_scorecards.py`.

## Constraints and Halt Conditions

The implementation does not migrate or infer outcomes for legacy event logs.

The implementation does not change a producer command interface.

The implementation halts if a repair-relevant record cannot expose one deterministic outcome.
