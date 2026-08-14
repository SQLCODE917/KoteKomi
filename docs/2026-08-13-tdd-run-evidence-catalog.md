# TDD Run Evidence Catalog

## Context & Problem

A user wants the Harness to resume a TDD implementation and compute metrics without caller-provided evidence paths.

The Harness already produces lifecycle, verification, check, CI, cleanup, and receipt evidence.

Those records do not yet have one run-scoped discovery contract.

The workflow and metrics commands cannot deterministically find evidence unless each implementation run has a canonical evidence catalog.

This TDD uses the term `implementation run` for one attempt to implement one TDD from intake through completion or block.

This TDD uses the term `run root` for the state directory for one implementation run.

This TDD uses the term `evidence index` for the current catalog of evidence records for one implementation run.

This TDD uses the term `evidence event log` for the append-only history of evidence updates for one implementation run.

This TDD uses the term `evidence entry` for one entry in the evidence index.

This TDD uses the term `evidence key` for the tuple that makes one evidence entry unique.

This TDD uses the term `path scope` for the root that resolves an evidence path.

This TDD uses the term `global report` for a metrics, scorecard, or comparison output that is not owned by one implementation run.

Primary end-to-end Flow:

1. A Harness command receives a task identifier and an implementation run identifier.

2. The command writes a canonical evidence record under the run root or references a repository record.

3. The command computes the evidence record SHA-256 digest.

4. The command updates the evidence index entry for that evidence key.

5. The command appends an evidence event to the evidence event log.

6. The workflow and metrics commands read the evidence index and validate referenced records before they trust them.

## Goals

- The workflow can discover run evidence without caller-provided paths.

- The metrics collector can compute metrics from canonical indexed evidence.

- The scorecard generator can trace run-scoped scorecards to canonical run evidence.

- The Harness can preserve repair history after current evidence entries are replaced.

- The Harness can distinguish repository files from state files without absolute paths.

## Requirements

Run root boundary:

- RR-01: The Harness stores each run under `<state-root>/experiments/<task-id>/runs/<implementation-run-id>/`.

- RR-02: The Harness stores the run record at `<run-root>/run.json`.

- RR-03: The Harness stores the evidence index at `<run-root>/evidence/index.json`.

- RR-04: The Harness stores the evidence event log at `<run-root>/evidence/events.jsonl`.

Path boundary:

- PB-01: Each evidence entry has `path_scope`.

- PB-02: `path_scope = repo` means the path is relative to the repository root.

- PB-03: `path_scope = state` means the path is relative to the state root.

- PB-04: The evidence index never stores absolute paths.

Evidence key boundary:

- EK-01: The evidence key is `(phase, evidence_type, subject_id)`.

- EK-02: The evidence index contains at most one current entry for one evidence key.

- EK-03: The evidence index sorts entries by phase order, evidence type, subject identifier, and path.

- EK-04: The run-check subject identifier is the original check identifier.

- EK-05: The run-check file identifier is the first 16 lowercase hexadecimal characters of SHA-256 over the check identifier encoded as UTF-8.

- EK-06: The run-check canonical file path is `<run-root>/checks/run-checks/<check-file-id>.json`.

- EK-07: The metrics record evidence type uses the implementation run identifier as subject identifier.

- EK-08: The scorecard record evidence type uses the implementation run identifier as subject identifier.

Evidence entry boundary:

- EE-01: Each evidence entry has `phase`.

- EE-02: Each evidence entry has `evidence_type`.

- EE-03: Each evidence entry has `subject_id`.

- EE-04: Each evidence entry has `path_scope`.

- EE-05: Each evidence entry has `path`.

- EE-06: Each evidence entry has `sha256`.

- EE-07: Each evidence entry has `producer_command`.

- EE-08: Each evidence entry has `diagnostics`.

- EE-09: The evidence index owns producer metadata for external records.

- EE-10: Referenced records use type-specific trusted fields.

Replacement boundary:

- RP-01: A producer can replace the current evidence index entry for the same evidence key.

- RP-02: A producer never overwrites immutable receipt files.

- RP-03: A producer appends an evidence event whenever it creates or replaces an evidence index entry.

- RP-04: The old referenced file remains available when that evidence type uses revisioned storage.

Global report boundary:

- GR-01: Aggregate metrics collections are global reports and do not appear in a run evidence index.

- GR-02: Aggregate scorecard collections are global reports and do not appear in a run evidence index.

- GR-03: Comparison reports are global reports and do not appear in a run evidence index.

- GR-04: Global reports do not use the common run evidence producer interface.

- GR-05: The all-known metrics report path is `tdds/reports/metrics/all-known.metrics.json` under the state root.

- GR-06: The all-known scorecards report path is `tdds/reports/scorecards/all-known.scorecards.json` under the state root.

- GR-07: The comparison report path is `tdds/reports/comparisons/<comparison-id>.json` under the state root.

Producer boundary:

- PR-01: Each run-scoped evidence producer command accepts `--task-id <task-id>`.

- PR-02: Each run-scoped evidence producer command accepts `--run <implementation-run-id>`.

- PR-03: Each run-scoped evidence producer command writes its canonical evidence record.

- PR-04: Each run-scoped evidence producer command updates the evidence index.

- PR-05: Each run-scoped evidence producer command appends the evidence event log.

External evidence boundary:

- EX-01: The workflow indexes the canonical TDD binding when it creates or reloads a run.

- EX-02: The workflow indexes the task manifest when the manifest exists.

- EX-03: The workflow indexes task manifest validation after it validates the manifest.

- EX-04: The workflow can replace the TDD binding index entry when an alias update changes the current binding digest.

- EX-05: The workflow can replace the task manifest index entry when the manifest file digest changes.

- EX-06: The workflow can replace task manifest validation after each validation run.

Validation boundary:

- VB-01: The evidence reader resolves each evidence entry by path scope and path.

- VB-02: The evidence reader recomputes the SHA-256 digest of the referenced record.

- VB-03: The evidence reader blocks when the recomputed digest differs from the evidence entry digest.

- VB-04: The evidence reader validates referenced records by evidence type.

- VB-05: The evidence reader does not require external repository records to contain `producer_command` or `diagnostics`.

## Proposed Architecture

The evidence producer owns canonical evidence creation.

The evidence index writer owns current evidence discovery.

The evidence event writer owns historical evidence events.

The evidence reader owns path resolution, digest validation, and type-specific record validation.

The workflow and metrics commands consume validated evidence.

```text
+-------------------+      +----------------------+      +----------------+
| Evidence producer | ---> | Evidence index       | ---> | Evidence reader|
+-------------------+      +----------------------+      +----------------+
          |                         |                           |
          v                         v                           v
+-------------------+      +----------------------+      +----------------+
| Evidence record   |      | Evidence event log   |      | Workflow       |
+-------------------+      +----------------------+      +----------------+
                                                               |
                                                               v
                                                        +--------------+
                                                        | Metrics      |
                                                        +--------------+
```

## Key Interactions

Producer sequence:

```text
Producer command      Evidence record      Evidence index      Evidence event log
       |                    |                    |                     |
       | write record       |                    |                     |
       |------------------->|                    |                     |
       | digest record      |                    |                     |
       |<-------------------|                    |                     |
       | update entry       |                    |                     |
       |---------------------------------------->|                     |
       | append event       |                    |                     |
       |------------------------------------------------------------->|
```

Reader sequence:

```text
Workflow        Evidence reader      Evidence index      Evidence record
   |                  |                    |                    |
   | read evidence    |                    |                    |
   |----------------->|                    |                    |
   |                  | read index         |                    |
   |                  |------------------->|                    |
   |                  | entries            |                    |
   |                  |<-------------------|                    |
   |                  | read record        |                    |
   |                  |---------------------------------------->|
   |                  | record             |                    |
   |                  |<----------------------------------------|
   |                  | validate digest    |                    |
   | evidence facts   |                    |                    |
   |<-----------------|                    |                    |
```

## Data Model

The evidence index has these fields:

- `schema_version`

- `task_id`

- `implementation_run_id`

- `entries`

- `diagnostics`

Each evidence entry has these fields:

- `phase`

- `evidence_type`

- `subject_id`

- `path_scope`

- `path`

- `sha256`

- `producer_command`

- `diagnostics`

Each evidence event has these fields:

- `schema_version`

- `task_id`

- `implementation_run_id`

- `event_type`

- `phase`

- `evidence_type`

- `subject_id`

- `status`

- `sha256`

- `created_at`

The test harness injects the clock for `created_at`.

Byte-stability tests exclude `created_at` when they do not inject a clock.

## APIs / Interfaces

The common producer interface is:

```text
<producer-command> --task-id <task-id> --run <implementation-run-id>
```

The evidence index command is:

```text
kotekomi-agent evidence-index --task-id <task-id> --run <implementation-run-id> [--output <index-json>]
```

The evidence index command prints JSON to stdout by default.

The optional `--output` path writes a JSON copy.

## Behavior & Domain Rules

The phase order is `intake`, `spec`, `candidate`, `verification`, `candidate_ci`, `main`, `main_ci`, and `complete`.

The `tdd_binding` evidence type uses subject identifier `binding`.

The `task_manifest` evidence type uses subject identifier `manifest`.

The `task_manifest_validation` evidence type uses subject identifier `manifest`.

The `candidate_lifecycle` evidence type uses subject identifier `candidate`.

The `candidate_commit` evidence type uses subject identifier `candidate`.

The `verification_plan` evidence type uses subject identifier `plan`.

The `run_check` evidence type uses the check identifier as subject identifier.

The `verify_checks` evidence type uses subject identifier `verify-checks`.

The `candidate_ci` evidence type uses subject identifier `candidate`.

The `main_promotion` evidence type uses subject identifier `main`.

The `main_lifecycle` evidence type uses subject identifier `main`.

The `main_ci` evidence type uses subject identifier `main`.

The `cleanup` evidence type uses subject identifier `cleanup`.

The `receipt_chain_status` evidence type uses subject identifier `receipt-chain`.

The `metrics_record` evidence type uses the implementation run identifier as subject identifier.

The `scorecard_record` evidence type uses the implementation run identifier as subject identifier.

The canonical `task_manifest` path has path scope `repo` and path `.agent/tasks/<task-id>.toml`.

The canonical `tdd_binding` path has path scope `state` and path `experiments/<task-id>/spec/tdd-binding.json`.

The canonical `task_manifest_validation` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/spec/task-manifest-validation.json`.

The canonical `candidate_lifecycle` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/lifecycle/candidate.json`.

The canonical `candidate_commit` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/git/candidate-commit.json`.

The canonical `verification_plan` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/verification/verification-plan.json`.

The canonical `verify_checks` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/checks/verify-checks.json`.

The canonical `candidate_ci` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/ci/candidate.json`.

The canonical `main_promotion` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/git/main-promotion.json`.

The canonical `main_lifecycle` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/lifecycle/main.json`.

The canonical `main_ci` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/ci/main.json`.

The canonical `cleanup` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/cleanup/branch-cleanup.json`.

The canonical `receipt_chain_status` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/receipts/receipt-chain-status.json`.

The canonical `metrics_record` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/metrics/tdd-metrics.json`.

The canonical `scorecard_record` path has path scope `state` and path `experiments/<task-id>/runs/<run-id>/scorecard/tdd-scorecard.json`.

The all-known metrics global report path is `tdds/reports/metrics/all-known.metrics.json` under the state root.

The all-known scorecards global report path is `tdds/reports/scorecards/all-known.scorecards.json` under the state root.

The comparison global report path is `tdds/reports/comparisons/<comparison-id>.json` under the state root.

The run evidence index does not include global report paths.

The `intake` phase requires `tdd_binding` evidence.

The `spec` phase requires `tdd_binding`, `task_manifest`, and `task_manifest_validation` evidence.

The `candidate` phase requires spec evidence, `candidate_lifecycle`, and `candidate_commit` evidence.

The `verification` phase requires candidate evidence, `verification_plan`, all planned `run_check` records, and `verify_checks` evidence.

The `candidate_ci` phase requires verification evidence and `candidate_ci` evidence.

The `main` phase requires candidate CI evidence, `main_promotion`, and `main_lifecycle` evidence.

The `main_ci` phase requires main evidence, `main_ci`, and `cleanup` evidence.

The `complete` phase requires main CI evidence and `receipt_chain_status` evidence.

The `task_manifest` trusted fields are `task_id`, `tdd_path`, and `tdd_sha256`.

The `tdd_binding` trusted fields are `task_id`, `primary_tdd_path`, `tdd_paths`, and `tdd_sha256`.

The `task_manifest_validation` trusted fields are `status`, `task_id`, `tdd_path`, `tdd_sha256`, and `diagnostics`.

The `candidate_lifecycle` and `main_lifecycle` trusted fields are `ready` and `diagnostics`.

The `candidate_commit` trusted fields are `commit_sha` and `parent_sha`.

The `verification_plan` trusted fields are `status` and `planned_checks`.

The `run_check` trusted fields are `check_id`, `outcome`, and `diagnostics`.

The `verify_checks` trusted fields are `status`, `planned_check_count`, `executed_check_count`, `verified_check_count`, and `failed_check_count`.

The `candidate_ci` and `main_ci` trusted fields are `conclusion` and `head_sha`.

The `main_promotion` trusted fields are `promotion_kind`, `promotion_commit`, `parent_commit`, and `verified_parent_commit`.

The `cleanup` trusted fields are `branch_cleanup_complete` and `remaining_branches`.

The `receipt_chain_status` trusted fields are `status`, `receipt_total_count`, `receipt_present_count`, `receipt_missing_count`, `digest_mismatch_count`, `expected_receipts`, `missing_receipts`, `digest_mismatches`, and `diagnostics`.

The `metrics_record` trusted fields are `task_id`, `implementation_run_id`, `status`, `planned_check_count`, `verified_check_count`, `failed_check_count`, `repair_count`, and `diagnostics`.

The `scorecard_record` trusted fields are `task_id`, `implementation_run_id`, `status`, `score_dimensions`, `overall_score`, and `diagnostics`.


## Acceptance Criteria

- AC-RR-01: Acceptance tests prove the run root path is deterministic from task identifier and run identifier.

- AC-RR-02: Acceptance tests prove the evidence index is written under the run root.

- AC-RR-03: Acceptance tests prove the evidence event log is written under the run root.

- AC-PB-01: Schema tests prove each evidence entry has `path_scope`.

- AC-PB-02: Unit tests prove repo-scoped paths resolve from the repository root.

- AC-PB-03: Unit tests prove state-scoped paths resolve from the state root.

- AC-PB-04: Schema tests reject absolute paths in the evidence index.

- AC-EK-01: Unit tests prove evidence keys use phase, evidence type, and subject identifier.

- AC-EK-02: Unit tests prove the evidence index contains at most one current entry for one evidence key.

- AC-EK-03: Unit tests prove evidence index entries sort deterministically.

- AC-EK-04: Unit tests prove run-check file identifiers derive from check identifiers.

- AC-EK-05: Unit tests prove metrics record and scorecard record evidence types use the subject identifiers from this TDD.

- AC-EE-01: Schema tests prove each evidence entry has the required fields.

- AC-RP-01: Acceptance tests prove a producer can replace a current index entry for the same evidence key.

- AC-RP-02: Acceptance tests prove replacement appends an evidence event.

- AC-PR-01: CLI tests prove producer commands accept `--task-id`.

- AC-PR-02: CLI tests prove producer commands accept `--run`.

- AC-EX-01: Acceptance tests prove the workflow indexes TDD binding evidence when it creates a run.

- AC-EX-02: Acceptance tests prove the workflow indexes task manifest evidence when the manifest exists.

- AC-EX-03: Acceptance tests prove the workflow indexes task manifest validation evidence.

- AC-VB-01: Unit tests prove evidence reader validates referenced record SHA-256 digests.

- AC-VB-02: Unit tests prove evidence reader uses type-specific validation.

- AC-VB-03: Unit tests prove external repository records are not required to contain producer metadata.

- AC-MATRIX-01: Unit tests prove each workflow phase has the required evidence types from this TDD.

- AC-METRICS-PATH-01: Unit tests prove the run-scoped metrics record canonical path.

- AC-SCORECARD-PATH-01: Unit tests prove the run-scoped scorecard record canonical path.

- AC-GLOBAL-REPORT-01: Unit tests prove aggregate metrics, aggregate scorecard, and comparison report paths do not appear in the run evidence index.

- AC-RECEIPT-FIELDS-01: Schema tests prove receipt-chain status exposes total, present, missing, and digest-mismatch counts.

## Reference Implementations

- Verification execution records: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.

- Task lifecycle records: follow `packages/devtools/src/kotekomi_devtools/task_lifecycle.py`.

- Receipt status records: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if an existing run-scoped producer cannot accept task and run arguments without changing its public contract.

The implementer must halt if an evidence type cannot provide the trusted fields listed in this TDD.
