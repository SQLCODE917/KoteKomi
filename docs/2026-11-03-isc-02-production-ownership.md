# TDD: Production Ownership of Shared Contracts and Construction

- Status: Accepted
- Deliverable: ISC-02
- Parent: [Ingestion Stabilization](2026-11-03-ingestion-stabilization-agile-package.md)

## 1. User outcome

Production composition owns the contracts it uses.
A production change does not inherit an experiment module, an experiment identifier
contract, or an experiment timestamp assumption.

## 2. Current behavior

`source_grounded_reference_composition.py` is the production composition module.
Before this change it imported three things from experiment-specific modules:

- `AssertionConstructionInputs`, `AssertionConstructionStatus`, and
  `construct_inspectable_assertion` from `deterministic_residual_composition_completion`
  (the R19 experiment module).
- `AttachmentSourceRange` from `competitive_attachment_review_verification`
  (a review-verification module).
- `DecontextualizedProposition` and its statuses from `decontextualization_composition`.

The R19 module also held the only `Assertion` construction in the codebase and imposed
`_R19_ASSERTION_EPOCH` on every constructed Assertion, including live ones.
The Application Layer default export eagerly imported the R19 module.

## 3. Ownership after this change

| Contract | Owner |
|---|---|
| One source-exact range | `kotekomi_application.source_ranges.SourceRange` |
| Construction inputs, outcome, block reasons, constructor | `kotekomi_application.assertion_construction` |
| Reviewed decision texts and signal definitions | `kotekomi_application.semantic_selection_contract` |
| R19 logical epoch | `kotekomi_pipelines.deterministic_residual_composition_completion` |

`competitive_attachment_review_verification` consumes `SourceRange` from its production
owner.
The R19 runner consumes the shared construction and supplies its own epoch.
Live recomposition consumes the same construction and supplies the current time.

## 4. Timestamp contract

`AssertionConstructionInputs` declares a required `constructed_at: datetime`.
The constructor copies that value to the Assertion `created_at` and `updated_at`.
The constructor never reads a clock and never supplies a default.

- A live workflow passes `datetime.now(UTC)` at the call site.
- The R19 workflow passes `R19_ASSERTION_EPOCH`, a declared logical epoch, because an
  R19 Assertion is proposed and never persisted with a wall-clock creation time.

## 5. Identifier contracts

The construction module declares one event identifier pattern that accepts the reviewed
experiment residual identifiers and the live source-grounded event identifiers.
Experiment code passes its identifiers explicitly at its own boundary.
No module keeps a second definition of the same source range or construction contract.

## 6. Default exports

The Application Layer loads historical experiment modules lazily.
A fresh `import kotekomi_application` imports none of them; the facade resolves an
experiment name on first access.
Three modules stay in the default import because production constituent generation reaches
them through the containment router: `competitive_attachment_review_verification`,
`competitive_attachment_selection`, and
`deterministic_dependency_path_attachment_router`.
`test_fresh_import_does_not_load_historical_experiments` runs a fresh interpreter and fails
on any new eager experiment dependency.
`construct_inspectable_assertion`, `AssertionConstructionInputs`,
`AssertionConstructionStatus`, `AssertionConstructionOutcome`, `AssertionBlockReason`, and
`SourceRange` stay exported because production composition uses them.
`complete_deterministic_residual_composition` and its outcome types are reachable only
through `kotekomi_application.deterministic_residual_composition_completion`.

## 7. Acceptance tests

| Check | Test |
|---|---|
| ISC-02-A | `test_production_composition_has_no_experiment_dependency` reads the production module AST and rejects experiment imports |
| ISC-02-B | existing selection, composition, identity acceptance, R19, and R20 regressions |
| ISC-02-C | `test_construction_uses_the_caller_supplied_timestamp` plus the R19 closure regression that keeps its sealed fingerprint |
| ISC-02-D | `test_default_exports_do_not_load_historical_experiment_modules` |

## 8. Verification

- `uv run pytest packages/application/tests packages/pipelines/tests packages/adapters/tests -q`
- `uv run ruff format --check`, `uv run ruff check`, and `uv run pyright` on changed files.
