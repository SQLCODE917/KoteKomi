# TDD: Shared Ingestion Workflow and Final Live Refresh

- Status: Accepted
- Deliverable: ISC-01
- Parent: [Ingestion Stabilization](2026-11-03-ingestion-stabilization-agile-package.md)
- Starting revision: `317723f`

## 1. User outcome

An operator receives the same persisted composition outcomes from terminal and Textual ingestion.
The live screen shows the final composition outcomes without reopening replay.

## 2. Current behavior

Three fresh-ingestion interfaces exist today.

| Interface | Entry point | Derives composition |
|---|---|---|
| `kotekomi ingest` | `cli.ingest_user_file` | No |
| `kotekomi-live-replay --plain` | `live.main` plain branch calls `ingest_user_file` | No |
| `kotekomi-live-replay` Textual | `IngestionProcess` starts `run_ingestion_worker` | Yes |

`run_ingestion_worker` calls `ingest_user_file`, then calls
`ingestion_composition_pass.compose_ingested_run`, then reports the finished frame.
The presenter publishes paragraph snapshots during extraction only.
The composition outcome therefore never reaches the open live screen, and two of the
three interfaces never persist composition outcomes at all.

The observed consequence is recorded in the package evidence: the operator run
`igr_3a167add040a4fcc8aec6aba36363502` produced 167 Event composition outcomes, while the
same operator using `kotekomi ingest` produces none.

## 3. Ownership

`kotekomi_pipelines.ingestion_workflow` owns the shared fresh-ingestion workflow.
It composes two Application Layer use cases in order: user ingestion, then the derived
composition pass.

Every fresh-ingestion interface calls that workflow and keeps its own presentation.
No interface calls `ingest_user_file` directly after this change.

`kotekomi_application.inspection_session.InspectionSession` owns snapshot refresh.
It re-publishes its last stored snapshot for each paragraph with freshly persisted
composition annotations.

## 4. Contract

### 4.1 `run_ingestion_workflow`

Inputs are the ingestion arguments (`config_path`, `source_file_path`, `source_url`),
the output streams, the optional progress callbacks, the optional run ID factory, and an
optional post-composition callback.

The workflow performs these steps in order:

1. It calls `ingest_user_file` with a recording run ID factory.
2. It stops and returns the ingestion exit code when that code is non-zero.
3. It runs `compose_ingested_run` bound to the assigned IngestionRun ID.
4. It calls the post-composition callback with the derived records.
5. It returns an `IngestionWorkflowResult`.

`IngestionWorkflowResult` carries the ingestion exit code, the assigned IngestionRun ID,
the derived composition records, and the derived-pass error text.

### 4.2 Assigned run binding

The workflow wraps the caller's run ID factory in a recorder.
The recorder returns the same ID as the wrapped factory and stores it.
The composition pass receives the stored ID.
A caller that supplies `AssignedIngestionRunIdFactory` keeps its assigned identity.
A caller that supplies no factory receives a generated identity and still binds composition
to that identity.

### 4.3 Derived-pass failure

A derived composition failure changes neither the ingestion exit code nor the ingestion
records.
The workflow writes one diagnostic line to the caller's error stream.
The workflow reports the error text in `IngestionWorkflowResult.composition_error`.
The workflow skips the post-composition callback when the derived pass fails.

### 4.4 Live refresh

`InspectionSession.refresh_composition()` re-emits every stored snapshot whose persisted
composition annotations changed.
A snapshot without a composition change is not re-emitted.
The live presenter receives these snapshots through its existing snapshot callback, so the
Textual application and the plain renderer both update without a restart.

### 4.5 Behavior preserved

The workflow preserves these behaviors.

- Ingestion exit codes and their relation to canonical state.
- Coverage report content, paragraph receipts, and Event discovery.
- Stored replay starts no ingestion and remains read-only.
- Bounded cancellation of the spawned worker.
- Presentation failures never change canonical ingestion state.

## 5. Acceptance tests

| Check | Test |
|---|---|
| ISC-01-A | `test_all_fresh_interfaces_persist_the_same_composition_outcomes` |
| ISC-01-B | `test_all_fresh_interfaces_persist_the_same_composition_outcomes` compares outcome semantics and excludes run IDs and timestamps |
| ISC-01-C | `test_live_session_receives_final_composition_outcomes` |
| ISC-01-D | `test_stored_replay_starts_no_ingestion`, `test_replay_cancellation.py`, `test_replay_process_startup.py` |

The characterization test `test_ingestion_extraction_is_interface_independent` runs against
the current implementation first and must keep passing.
The correction regressions fail against the current implementation because two interfaces
persist no composition outcomes and the live session publishes no composition annotations.

## 6. Verification

Baseline `317723f`, before the change:

- `test_ingestion_extraction_is_interface_independent` passes. Extraction is already
  interface-independent.
- `test_stored_replay_starts_no_ingestion` passes. Stored replay is already read-only.
- `test_failure_reports_on_the_error_stream_only` passes.
- `test_all_fresh_interfaces_persist_the_same_composition_outcomes` fails. `kotekomi ingest`
  and plain live replay persist no composition outcomes.
- `test_live_session_receives_final_composition_outcomes` fails. The last published snapshot
  carries `composition=()`.

After the change:

- All five tests in `packages/pipelines/tests/test_ingestion_workflow.py` pass.
- `PYTHONPATH=. uv run pytest packages/pipelines/tests/test_replay_live_cli.py
  packages/pipelines/tests/test_replay_cancellation.py
  packages/pipelines/tests/test_replay_process_startup.py
  packages/pipelines/tests/test_user_ingestion_run.py
  packages/pipelines/tests/test_r20_ingestion_transition.py
  packages/pipelines/tests/test_ingestion_composition_transition.py
  packages/pipelines/tests/test_ingestion_workflow.py -q` passes 53 tests.
- `uv run ruff format --check` and `uv run ruff check` pass on changed files.
- `uv run pyright` reports no error on changed files.

One preserved test patched `live.ingest_user_file`. That seam no longer exists because the
plain and interactive interfaces call the workflow. The test keeps its assertions and now
patches only `live.IngestionProcess`, which is the seam it actually exercises.

