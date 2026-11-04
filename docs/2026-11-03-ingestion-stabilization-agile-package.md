# Ingestion Stabilization Agile Package

- Status: Accepted
- Program ID: `ingestion-stabilization`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Predecessor: [R20 Ingestion Live References](2026-10-30-ingestion-live-references.md)
- First deliverable: ISC-01, Shared ingestion workflow
- Next deliverable: ISC-03
- Implementation prompt: [Unattended implementation](agent/implement-ingestion-stabilization.md)

## User Outcome

An operator receives the same persisted extraction and composition outcomes through terminal and Textual ingestion.
The live screen shows the final composition outcomes without requiring a restart.
Developers can change production code without maintaining unrelated experiment contracts.
Developers can run the documented tests without adding shell-specific import paths.

This package prepares the existing ingestion path for the next capability increment.
It does not complete the broader source-grounded attachment program.

## Context and Evidence

R19 demonstrated deterministic residual closure through the composition workflow.
R20 connected accepted identity occurrences, live references, composition, and replay to ingestion.
Those increments reused experiment code to establish the path quickly.
The production path now needs explicit ownership and consistent orchestration.

The operator run `igr_3a167add040a4fcc8aec6aba36363502` processed 36 paragraphs in about 90 minutes.
Its coverage report records 17 complete paragraphs and 19 paragraphs with gaps.
Its 167 Event composition outcomes all report `assertion_inputs_unavailable`.
Those results identify the next capability problem, but this package addresses maintenance and workflow consistency first.

The repository inspection on 2026-11-03 established these cleanup targets:

| Current behavior | Observable consequence | Deliverable |
|---|---|---|
| The interactive worker runs composition; terminal and plain-output ingestion call ingestion directly | Presentation mode changes the persisted results | ISC-01 |
| The worker writes composition outcomes after the last extraction snapshots | The open live screen does not automatically receive the final composition results | ISC-01 |
| Live composition imports shared contracts and Assertion construction from experiment-specific modules | Production changes inherit experimental module ownership, identifiers, and timestamp assumptions | ISC-02 |
| Application code and command scripts write composition JSON separately | Persistence and validation rules have several owners | ISC-03 |
| Current R18 regression tests bind entire shared implementation modules | Routine edits require manual rebinding of a current-test contract | ISC-04 |
| Spawned tests import fixtures from other test modules | Some checks require `PYTHONPATH=.` | ISC-05 |
| Whole-tree formatting reports 23 files, and operator instructions describe divergent ingestion paths | Mechanical drift and stale instructions obstruct verification and use | ISC-06 |

The Application Layer export module also eagerly imports a broad experimental surface.
ISC-02 narrows that surface as part of correcting production ownership.
Module length alone is not a deletion criterion.

## Scope and Preservation Rules

The package covers ingestion orchestration, shared composition contracts, persistence, verification, and their instructions.
The package preserves source text, source coordinates, selection policy, model prompts, and review requirements.
Accepted Ledger writes continue through the existing validated Application Layer use cases.
An unavailable reference or reviewed construction input continues to produce an explicit hold.

Historical R16-R19 reports, reviewed fixtures, approval evidence, and frozen contracts remain byte-identical.
Historical reproduction continues through the pinned revisions documented in [CHECK_PLAN.md](CHECK_PLAN.md).
The separately identified R18 current-test contract is development verification, not historical acceptance evidence.
ISC-04 can replace that development mechanism while retaining its regression coverage.

The package preserves the saved operator run as evidence.
The package does not delete experiments merely because their deliverables are complete.
It removes superseded implementations and imports only after their callers use the single retained implementation.
It adds no compatibility branches or duplicate DTOs to preserve old module paths.

The package excludes:

- New model experiments, model substitutions, and prompt refinement.
- New selection, grounding, predicate, polarity, modality, or identity-resolution policies.
- Automatic acceptance of candidates or removal of review gates.
- Cross-view reference resolution.
- Independent held-out validation or claims of improved extraction accuracy.
- A general report framework, plugin system, or storage abstraction beyond the actual workflows.
- A repository-wide rewrite of the CLI, Domain Core models, or every experimental module.

## Deliverable Tracker

Each deliverable ships and reverts independently.
`Planned` means implementation and its acceptance evidence are outstanding.
`In progress` means work has started but an acceptance check remains open.
`Complete` requires the checks below and linked verification evidence.

| ID | Deliverable | Depends on | Status | TDD / implementation / evidence |
|---|---|---|---|---|
| ISC-01 | Shared ingestion workflow and final live refresh | Startup and warning fixes recorded separately | Complete | [TDD](2026-11-03-isc-01-shared-ingestion-workflow.md); `run_ingestion_workflow` in `packages/pipelines/src/kotekomi_pipelines/ingestion_workflow.py`; `PYTHONPATH=. uv run pytest packages/pipelines/tests/test_ingestion_workflow.py -q` passes 5; preserved replay, cancellation, startup, R20, and composition suites pass 53 |
| ISC-02 | Production ownership of shared contracts and construction | ISC-04 | Complete | [TDD](2026-11-03-isc-02-production-ownership.md); `assertion_construction.py` and `source_ranges.py` own the shared contracts; `uv run pytest packages/application/tests/test_production_composition_ownership.py -q` passes 3; full application, pipelines, and adapters suites pass with `EXIT=0` |
| ISC-03 | One Adapter for composition persistence | ISC-02 | Planned | Not started |
| ISC-04 | Separate historical reproduction from current regressions | None | Complete | `data/r18-current-regression/` reviewed expectations; `scripts/run_semantic_instruction_discrimination.py` adopts the live binding; `uv run pytest packages/pipelines/tests/test_semantic_instruction_discrimination_runner.py -q` passes 16; historical reproduction passed at pinned `c46d5e6` with fingerprint `5cdc12f0ed884cd73cfd99ada8a7af8d4b063d33b0a2abd45022800d02ecdce5` |
| ISC-05 | Self-contained test fixtures and subprocess imports | None | Planned | Not started |
| ISC-06 | Formatting and operator documentation | ISC-01 through ISC-05 | Planned | Not started |

### ISC-01: Shared ingestion workflow and final live refresh

One Pipeline orchestration path coordinates ingestion and the derived composition pass.
`kotekomi ingest`, fresh interactive `kotekomi-live-replay`, and its plain-output mode use that path.
Textual and terminal output retain their own presentation.
Stored replay remains read-only and starts no ingestion.
The orchestration binds composition to the assigned IngestionRun.
The live presenter receives final persisted composition outcomes before it reports operation completion.
The deliverable preserves bounded cancellation and explicit reporting of derived-pass failures.

Acceptance:

- [x] ISC-01-A: Deterministic tests invoke all three fresh-ingestion interfaces and compare their persisted semantic outcomes.
- [x] ISC-01-B: Comparison accounts explicitly for independently assigned IDs and execution timestamps.
- [x] ISC-01-C: The live screen displays the final Event holds or Assertions without reopening replay.
- [x] ISC-01-D: Tests preserve assigned-run isolation, stored replay, fresh-process startup, and cancellation.

### ISC-02: Production ownership of shared contracts and construction

Shared source ranges, constituent contracts, selection, and Assertion construction have production responsibilities and module ownership.
Production composition does not import an experiment runner or review-verification module to obtain those contracts.
Experiment modules consume the same production implementations.
The default Application Layer exports do not eagerly load historical experiment machinery.
Each identifier contract has one owner; fixture identifiers remain explicit at experiment boundaries.
The construction contract declares the timestamp input used by live workflows and historical runners.
An R19-specific epoch is supplied by the historical workflow rather than imposed by shared live construction.
The focused TDD pins that timestamp contract before implementation.

Acceptance:

- [x] ISC-02-A: Import-boundary checks prove production composition has no dependency on experiment-specific modules.
- [x] ISC-02-B: Existing selection, composition, identity acceptance, and R19/R20 behavioral regressions pass.
- [x] ISC-02-C: Tests prove historical timestamp reproduction and the declared live timestamp behavior separately.
- [x] ISC-02-D: Superseded definitions and exports are removed; callers use one contract for each shared concept.

### ISC-03: One Adapter for composition persistence

The Application Layer owns the composition record and its validation.
A Port defines the persistence operations that ingestion, recomposition, and inspection require.
A filesystem Adapter implements the operations using the existing replay source location.
Pipelines and command scripts compose that Adapter instead of writing composition JSON independently.
The Adapter replaces files atomically so a reader observes either the previous complete record or the new complete record.
Malformed records and invalid deterministic bindings fail validation.

Acceptance:

- [ ] ISC-03-A: Ingestion, recomposition, and replay use the same validated persistence implementation.
- [ ] ISC-03-B: An interrupted replacement preserves the previous readable record.
- [ ] ISC-03-C: Corrupt records raise validation errors rather than becoming empty results or ordinary missing-input holds.
- [ ] ISC-03-D: Saved R20 outcomes remain readable and preserve their Event, source binding, Assertion, and spans.

### ISC-04: Separate historical reproduction from current regressions

Historical reproduction verifies the original evidence and implementation at the pinned revision.
Current regression tests verify behavior against reviewed expectations and negative counterexamples.
Routine moves, import changes, and formatting do not require manually rebinding an old current-test contract.
New execution reports continue to record and validate their implementation provenance.
The implementation preserves response replay, approval membership, route binding, comparison recomputation, and tamper rejection.
A changed behavioral expectation requires an explicit reviewed change, not regenerated expected answers from the implementation.

Acceptance:

- [x] ISC-04-A: A behavior-preserving shared-module edit leaves current regressions runnable without a manual rebind.
- [x] ISC-04-B: Negative tests still reject changed evidence, stale signals, wrong routes, and impossible report comparisons.
- [x] ISC-04-C: Historical R17 and R18 reproduction retain their recorded fingerprints and frozen inputs.
- [x] ISC-04-D: The check plan distinguishes historical commands from current regressions and removes superseded rebind instructions.

### ISC-05: Self-contained test fixtures and subprocess imports

Shared fixture builders live in explicit test support modules.
Production code imports no test module.
Tests do not depend on execution order or importing another test file to initialize runtime resources.
Repository test configuration supplies the required import paths to spawned interpreters.
Tests continue to exercise real SQLite transactions, worker processes, and Textual boundaries where those boundaries matter.

Acceptance:

- [ ] ISC-05-A: The R20 transition, cold-start, and cancellation checks pass with `PYTHONPATH` unset.
- [ ] ISC-05-B: Each affected test file passes alone and in the combined run.
- [ ] ISC-05-C: Subprocess tests resolve the checkout under test rather than packages installed from another worktree.
- [ ] ISC-05-D: Fixture moves preserve parser validation and the existing review, rollback, and replay assertions.

### ISC-06: Formatting and operator documentation

Formatting ships in a separate mechanical commit after source-bound verification has been reconciled.
Operator documentation describes the shared workflow delivered by ISC-01.
Instructions distinguish fresh ingestion, saved replay, review, and explicit recomposition.
Instructions identify the runtime configuration, durable output paths, completion checks, and warning-output controls.
Living roadmap entries link to the current deliverables without editing frozen reviewed snapshots.

Acceptance:

- [ ] ISC-06-A: Whole-tree `ruff format --check .`, `ruff check .`, and `pyright` pass.
- [ ] ISC-06-B: Local documentation links resolve and operator commands match CLI help and tested launch paths.
- [ ] ISC-06-C: The formatting commit changes no model prompt, reviewed fixture, historical evidence, or extraction policy.
- [ ] ISC-06-D: The current check plan runs without the removed import-path or contract-rebind workarounds.

## Execution Order

Prerequisites are committed: `5616064` fixes cold-start worker launch, and `875acea` preserves warning output.
Those fixes passed 46 focused output, Textual, launch, and cancellation tests before commit.
They are prerequisites, not completed cleanup deliverables.

Execute ISC-01, ISC-04, ISC-02, ISC-03, ISC-05, then ISC-06.
ISC-04 precedes shared-contract moves and formatting to avoid repeated manual digest maintenance.
Write one focused TDD when beginning a deliverable that changes a boundary contract.
Use this package's checklist for the mechanical formatting work.
Keep design, implementation, and operator-run evidence in separate commits when all three are required.

Update one tracker row after each deliverable passes its checks.
Add its TDD link, implementation commit, verification command, and result to that row's evidence entry.
Record failed or unrun checks explicitly.
Do not close a row using a passing test that bypasses its stated user boundary.

### Behavior-preserving implementation loop

The original committed implementation supplies the behavioral baseline within the repository's authority order.
Before refactoring, write tests that characterize the observed behavior and prove they pass against that baseline.
Treat each intended correction specified by this package as a behavior change with its own failing regression test.
For another suspected bug, first reproduce the failure and identify the violated requirement.
Change expectations only for an explicit, justified correction within this package's scope.
Refactor the retained implementation and require the same characterization tests to pass.
Keep expected results independent of the refactored implementation.
Commit each completed deliverable and continue to the next without another routine approval request.

## Verification and Completion

Each implementation adds its repeatable checks to [CHECK_PLAN.md](CHECK_PLAN.md).
For this package, the operator authorizes unattended deterministic local verification and historical reproduction, including checks exceeding 60 seconds.
This authorization overrides the human-start requirement in the [long-running operations rules](agent/long-running-operations.md) for those checks only.
Each long check retains its command, revision, terminal status, and validated result through the existing verification machinery.
External-runtime checks still require the documented handoff with command, durable result location, completion probe, and success criteria.
The authorization excludes live model calls, accepted-state writes outside disposable test Ledgers, pushes, and merges.
A new 90-minute model ingestion is not a prerequisite for each structural cleanup.

The package completes when all six tracker rows are Complete and every acceptance checkbox has evidence.
Completion requires preserved historical evidence, consistent ingestion outcomes across interfaces, and a green current verification path.
Completion does not claim more correct Assertions or reduced model latency.
The next capability increment measures correct source-grounded Assertions and operator review effort using saved ingestion results.

## Implementation References

- Ingestion interfaces: [CLI](../packages/pipelines/src/kotekomi_pipelines/cli.py), [live and stored replay](../packages/pipelines/src/kotekomi_pipelines/replay_reader/live.py), and [worker](../packages/pipelines/src/kotekomi_pipelines/replay_reader/ingestion_worker.py).
- Shared composition: [source-grounded reference composition](../packages/application/src/kotekomi_application/source_grounded_reference_composition.py) and [R19 construction](../packages/application/src/kotekomi_application/deterministic_residual_composition_completion.py).
- Current regression: [semantic selection contract](../packages/application/src/kotekomi_application/semantic_selection_contract.py) and [reviewed expectations](../data/r18-current-regression/reviewed_expectations.json).
- Production regression: [normal-ingestion transition](../packages/pipelines/tests/test_r20_ingestion_transition.py), [cold start](../packages/pipelines/tests/test_replay_process_startup.py), and [cancellation](../packages/pipelines/tests/test_replay_cancellation.py).
