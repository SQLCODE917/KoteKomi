# Testing Rules

## Purpose

Tests verify contracts and prevent boundary drift.

Prefer data-in/data-out tests.

Use fixtures at real boundaries.

Fixtures must be internally coherent unless the fixture name identifies it as a negative fixture.

Treat repeated mocking as a coupling smell.

Happy-path fixtures must be internally coherent.

Negative fixtures must name the failure class.

Negative fixture tests must assert the exact failure.

Port contract tests use Application Layer fake Ports and Adapter tests for the same contract.

## Domain Core Tests

Domain Core tests use data-in/data-out assertions.

Domain Core tests do not use Adapters.

Domain Core tests verify validation rules, status transitions, and confidence semantics.

## Adapter Tests

Adapter tests use fixtures.

Adapter tests verify tool-native shape mapping.

Adapter tests verify error behavior at the tool boundary.

Adapter tests do not weaken Domain Core rules.

Adapter tests prove deterministic invalid input fails fast.

Adapter tests prove the Adapter satisfies its Application Layer Port contract.

## Pipeline Tests

Pipeline tests run against disposable Ledger and Archive fixtures.

Pipeline tests verify canonical state changes.

Pipeline tests verify generated files when the Pipeline writes files.

Pipeline tests verify ProvenanceActivity records.

Pipeline tests that create accepted Ledger records verify cross-record references.

Pipeline tests verify derived state can rebuild from the Ledger and Archive.

Pipeline tests verify record-type dispatch fails on unsupported record types.

## Briefing Tests

Briefing tests verify visible text.

Briefing tests verify Source IDs through structured citation registry data.

Briefing tests verify EvidenceTarget IDs through structured citation registry data.

Briefing tests verify analytic inference labels.

Briefing tests verify changed state against the previous Briefing.

Briefing tests verify the orthogonal Briefing sections use numbered citations when source-backed.

Briefing tests verify citation numbers resolve through structured registry data.

Briefing tests must not require agents to parse Markdown to resolve citations.

Briefing tests verify default human-facing Markdown does not expose raw canonical Domain IDs.

## Bug Fix Rule

Every bug fix adds or updates the narrowest test that proves the fix.

Every boundary validation bug adds a negative test that proves invalid deterministic input cannot enter accepted state.

## Done Checks

Use `docs/CHECK_PLAN.md` for task-level verification.

## Capability Evidence

Follow [Pipeline Improvement](pipeline-improvement.md#evidence-and-claims) when interpreting test and assessment results.
Characterization tests lock in existing behavior before a refactor.
A reproduced defect requires a failing regression rather than preserving the defect as expected behavior.
Structural or grammar assertions alone do not prove that an Assertion preserves complete source meaning.
For semantic corrections, test required content and a counterexample that exposes truncation or over-capture.
Exercise the production boundary that the operator uses; substitute external outputs through validated fixtures.
Distinguish synthetic construction tests, captured-input regressions, failure-injection tests, and independently assessed cases.
Do not seed the intended outcome or accepted prerequisites to claim that the ingestion-to-review path works.
Existing accepted-state fixtures remain valid for narrower tests that explicitly declare that starting state.

Use captured-input replay before fresh ingestion for deterministic changes when the retained boundary is sufficient.
Tie live-run and timing claims to the tested revision and declared protocol.
Record agent-assisted assessment separately from human effort.
Preserve reviewed expectations and historical evidence according to their declared contracts.
Passing the suite does not waive an unmet product acceptance gate.
