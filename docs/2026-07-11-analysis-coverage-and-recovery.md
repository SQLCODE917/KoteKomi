# TDD: Analysis Coverage and Recovery

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** PDF/news ingestion, context planning, and staged extraction

## 1. Context and problem

A document can appear successfully ingested even when pages, tables, sections, or model tasks were skipped, blocked, failed, or silently produced nothing. Without a frozen plan and terminal outcome for every unit, absence of claims is indistinguishable from absence of analysis. Recovery can also duplicate or erase work unless attempts and artifact validity are explicit.

## 2. Goals

- Freeze and identify the intended analysis scope for each run.
- Record a terminal status for every planned unit and task.
- Distinguish valid no-result, abstention, quality block, budget block, validation failure, runtime failure, and cancellation.
- Resume interrupted work without duplicating committed artifacts or hiding previous attempts.
- Produce machine-readable document and run coverage reports.
- Make “complete” a strict derived state, never a human-friendly label applied to partial work.

## 3. Non-goals and forbidden approaches

This TDD does not require every source unit to yield a claim.

Forbidden:

- deriving coverage only from the presence of proposals;
- deleting failed attempts after retry;
- reporting a run complete while planned units lack terminal outcomes;
- retrying with changed parser/context/model inputs under the same attempt identity;
- silently skipping low-quality pages or over-budget units;
- treating operator cancellation as success;
- using logs as the only failure record.

## 4. Requirements

1. An `AnalysisRun` references a pinned document representation, plan/policy versions, and a frozen set of units/tasks.
2. Every planned item has a stable identity and expected task sequence.
3. Every execution references one append-only `ProcessingAttempt` and its immutable `ProcessingAttemptOutcome`, or one immutable `ModelRun`.
4. Terminal statuses are typed and mutually exclusive.
5. Run completeness is calculated from planned scope and terminal outcomes.
6. Required blocks/failures prevent a `complete` status even when all items are terminal.
7. Valid `processed_no_proposals` and `abstained` outcomes count as analyzed but remain separately reportable.
8. Recovery identifies reusable artifacts by fingerprint and reruns only missing, invalid, or policy-selected work.
9. A retry creates a new underlying attempt or model run and preserves every prior record.
10. Cancellation reaches a consistent boundary and records unstarted/planned items appropriately.
11. Coverage reports expose counts and identities by page, node/unit, task type, status, and reason.
12. CLI/API operations return machine-readable state and non-zero exit codes for incomplete/failed required work.

## 5. Status model

Coverage terminal statuses:

```text
processed_with_proposals
processed_no_proposals
abstained
parse_quality_blocked
context_budget_blocked
model_failed
validation_failed
not_applicable
cancelled
```

Run states:

```text
planned → running → complete
                  ↘ incomplete
                  ↘ failed
                  ↘ cancelled
```

`complete` means every required planned item has a successful terminal status under the run's policy. `incomplete` means work is terminal or paused but one or more required items did not succeed. `failed` is reserved for run-level integrity failures that prevent trustworthy accounting.

## 6. Invariants

- The frozen planned-item set never shrinks after work begins.
- Every terminal item references at least one underlying execution or an explicit planning-time `not_applicable` decision.
- An `AnalysisItemAttempt` is orchestration metadata only and has no independent status transition.
- `ProcessingAttempt` and `ModelRun` own execution identity, input fingerprints, timing, errors, and terminal state.
- Every `ProcessingAttempt` has exactly one immutable `ProcessingAttemptOutcome` after normal completion.
- A successful retry does not alter an earlier ProcessingAttempt, ProcessingAttemptOutcome, or ModelRun.
- Completion calculation is deterministic under a versioned policy.
- Proposal count is never used as a proxy for analyzed-unit count.
- A report's totals reconcile exactly to its listed unit statuses.
- Recovery never reuses an artifact whose fingerprint or validation state is stale.

## 7. Data model and interfaces

`AnalysisItemAttempt` points to exactly one `ProcessingAttempt` or `ModelRun`.

It indexes orchestration work and does not define execution state, timestamps, errors, or outcomes.

```yaml
AnalysisRun:
  analysis_run_id:
  document_id:
  representation_id:
  analysis_plan_id:
  coverage_policy_id:
  frozen_plan_digest:
  state:
  started_at:
  completed_at:

PlannedAnalysisItem:
  planned_item_id:
  analysis_run_id:
  analysis_unit_id:
  task_type:
  required:
  dependencies:
  input_fingerprint:

AnalysisItemAttempt:
  analysis_item_attempt_id:
  planned_item_id:
  processing_attempt_id:
  model_run_id:
  execution_role:

CoverageRecord:
  coverage_record_id:
  planned_item_id:
  terminal_status:
  selected_model_run_id:
  selected_proposal_ids:
  all_model_run_ids:
  policy_decision:
  blocking_reason:
  abstention_reason:
```

Outcome selection is an explicit versioned Application policy:

```python
class CoveragePolicy(Protocol):
    @property
    def policy_id(self) -> str: ...

    def select_current_attempt(
        self,
        planned_item: PlannedAnalysisItem,
        attempts: tuple[AnalysisItemAttempt, ...],
    ) -> SelectedCoverageOutcome: ...
```

The initial policy is `latest_completed_valid_attempt_v1`. An `AnalysisRun`
pins that exact identity. An unavailable or unknown policy is an integrity
failure, not an invitation to apply a default. The policy selects the latest
valid linked execution by immutable completion time and then stable execution
identity.

`selected_proposal_ids` are loaded only from `selected_model_run_id`.
`all_model_run_ids` is historical accounting and cannot affect the current
terminal status or selected proposal set.

Run-scope accounting failures are returned as a `CoverageReport` with
`state = failed`; they are not downgraded to ordinary incomplete work or
hidden behind reconciliation exceptions. The initial typed integrity reasons
are:

```text
missing_manifest
multiple_manifests
unexpected_manifest
missing_selected_run
run_task_mismatch
proposal_run_mismatch
split_cycle
```

An item whose frozen scope intentionally has no `expected_manifest_id` is
pending work, not corrupt state. It reports `incomplete` with item-local
`blocking_reason = missing_manifest`. A non-null selected manifest identity
that cannot be loaded is the `failed / missing_manifest` integrity case.

Item-local failures use the same exact reason in `blocking_reason`. A
proposal/run mismatch exposes no selected proposals. Report construction may
still fail fast when the requested AnalysisRun itself, its frozen plan, or its
document representation cannot be identified at all.

Required operations:

```python
start_analysis_run(command) -> AnalysisRun
record_coverage_outcome(command) -> CoverageRecord | PendingState
resume_analysis_run(run_id, recovery_policy_id) -> RecoveryPlan
build_coverage_report(run_id) -> CoverageReport
```

## 8. Key interactions and domain rules

### No claims in a paragraph

A successful validated no-claim result becomes `processed_no_proposals`. It contributes to analyzed coverage without implying model abstention or failure.

### Ambiguous source text

A schema-valid abstention becomes `abstained` with a reason code and model run. Policy decides whether the run may still be complete; the report always exposes it.

### Crash between model output and proposal commit

The raw ModelRun remains archived. Recovery checks the transactional boundary and either deterministically completes validation/proposal construction or creates a new ModelRun. It never duplicates proposal batches.

### Changed policy or representation

The old run remains historical. Work under changed pinned inputs starts a new run or planned item identity rather than mutating fingerprints inside the old run.

### Operator cancellation

In-flight operations finish or roll back at declared atomic boundaries. Remaining planned items become terminal `cancelled` or remain explicitly pending according to the cancellation policy; the run cannot be `complete`.

## 9. Coverage report contract

A report SHALL include at minimum:

- total pages and page extraction statuses;
- total structural/analysis units planned and terminal;
- counts by task type and terminal status;
- blocked page/node/unit identities and reason codes;
- ProcessingAttempts, ProcessingAttemptOutcomes, ModelRuns, retries, and selected executions;
- proposal and abstention counts;
- evidence-validation pass/fail counts;
- run state, completeness policy, and report digest.

Human summaries are generated from these reconciled fields, not separately maintained counters.

## 10. Compatibility and delivery

- Existing fixture pipelines may create one analysis run with one unit and one staged task sequence.
- Coverage records are additive and do not alter accepted ledger history.
- Initial recovery may be single-process; correctness cannot depend on a distributed queue.
- Transaction boundaries and idempotency are tested with the same repositories used in production adapters.

## 11. Completion gates

### Correctness criteria

- Every frozen planned item in each test run reconciles to exactly one current terminal/pending state.
- Completion is impossible with a missing, blocked, failed, invalid, or cancelled required item.
- `processed_no_proposals`, `abstained`, and `model_failed` remain distinguishable in storage, API, report, and CLI exit behavior.
- Failure injection before and after every artifact/proposal commit boundary produces no duplicate or orphaned current outcome.
- Resume reruns only stale/missing work and preserves every prior ProcessingAttempt, ProcessingAttemptOutcome, and ModelRun.
- Report totals equal the enumerated records and the report digest is stable.
- A changed input fingerprint cannot be attached to an existing ProcessingAttempt or ModelRun.
- SQLite proves that unrelated documents and alternate plans over one representation cannot contaminate a run-scoped report.
- SQLite proves that the selected run alone determines current proposal status across succeeded-no-proposal, abstained, invalid-output, and publish-failed retries.
- Every SQLite coverage case closes and reopens the Ledger and reproduces the identical report digest and policy decision.

### Success criteria

- An interrupted multi-page run resumes to completion with the same final authoritative proposals as an uninterrupted run under deterministic fixtures.
- Operators can identify every unprocessed page/unit and exact blocking reason without reading logs.
- Batch orchestration can select incomplete runs and retry only eligible statuses.
- The integrated gold corpus has 100% terminal accounting, including no-claim and abstention cases.
- CLI/API callers can reliably distinguish success, incomplete work, cancellation, and integrity failure.

### Failure criteria

This deliverable is incomplete if:

- “ingestion succeeded” can coexist with unaccounted planned work;
- retry overwrites attempt history or duplicates proposals;
- zero proposals is interpreted as complete analysis;
- coverage exists only in logs or aggregate counters;
- cancellation or parser/model failure returns a success exit status;
- recovery reuses artifacts after parser, context, prompt, schema, or model inputs changed;
- report totals cannot be reconciled to individual units.

## 12. Halt conditions

Stop and revise when a pipeline stage lacks an atomic boundary that can be recovered safely, or when the planned scope cannot be frozen before model work begins.
