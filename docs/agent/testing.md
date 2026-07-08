# Testing Rules

## Purpose

Tests verify contracts and prevent boundary drift.

Prefer data-in/data-out tests.

Use fixtures at real boundaries.

Treat repeated mocking as a coupling smell.

## Domain Core Tests

Domain Core tests use data-in/data-out assertions.

Domain Core tests do not use Adapters.

Domain Core tests verify validation rules, status transitions, and confidence semantics.

## Adapter Tests

Adapter tests use fixtures.

Adapter tests verify tool-native shape mapping.

Adapter tests verify error behavior at the tool boundary.

Adapter tests do not weaken Domain Core rules.

## Pipeline Tests

Pipeline tests run against disposable Ledger and Archive fixtures.

Pipeline tests verify canonical state changes.

Pipeline tests verify generated files when the Pipeline writes files.

Pipeline tests verify ProvenanceActivity records.

## Briefing Tests

Briefing tests verify visible text.

Briefing tests verify Source IDs.

Briefing tests verify EvidenceSpan IDs.

Briefing tests verify analytic inference labels.

Briefing tests verify changed state against the previous Briefing.

## Bug Fix Rule

Every bug fix adds or updates the narrowest test that proves the fix.

## Done Checks

Use `docs/CHECK_PLAN.md` for task-level verification.
