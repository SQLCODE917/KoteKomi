# Reuse Validated Inputs Within One Review Command

## Context & Problem

An operator recomposes a reviewed Event into a pending Assertion ProposedChange.
An Event identifies a happening; the Assertion states its meaning with evidence.
Recomposition currently loads paragraph inputs once for its packet and again for composition.
It also repeats Event lookup, token loading, and candidate inventory construction.
The [successor task](2026-11-11-ingestion-improvements-task.md) selects this second bounded correction after announcement integration.
The behavior below is planned.

Primary end-to-end flow:

1. The operator requests a packet, decision, or recomposition through the existing command.
2. The Pipeline loads and validates the paragraph, Event, tokens, and candidate inventory once.
3. Packet construction uses those validated values and reads current review state.
4. Recomposition uses the same values and reads current review and proposal state inside its transaction.
5. The transaction commits the proposal before the derived composition outcome is saved.

## Goals

- A review command performs one load of its ingestion inputs.
- Operators retain the same proposed Assertions, evidence, review decisions, and failure behavior.
- Separate commands observe changed or corrupt inputs through fresh validation.

## Requirements

### Review Pipeline

- CTX-01: Each command owns one private context containing its validated paragraph, Event, token artifact, and inventory.
- CTX-02: Packet construction and recomposition share that context within one command only.
- CTX-03: Every new command reloads and validates its ingestion inputs.
  Corrupt or stale Source bindings fail before composition or proposal persistence.
- TX-01: Existing transactions load current review, identity, evidence, and proposal state.
  Reuse must preserve review prerequisites, proposal idempotency, validation rollback, and derived-file recovery.
- API-01: Existing public function signatures, commands, result types, and stored schemas remain unchanged.

## Proposed Architecture

The review Pipeline owns request-scoped input reuse.
Existing Application Layer validators retain boundary validation and composition decisions.
SQLite and file Adapters retain persistence responsibilities.

```text
Operator -> Review Pipeline -> Application Layer -> Domain Core
                 |
                 +-> validated inputs for this command
                 |
                 +-> SQLite / Archive Adapters
```

## Key Interactions

```text
Operator       Review Pipeline       Validators          Ledger / Archive
   | recompose      |                    |                      |
   |--------------->| load inputs ----------------------------->|
   |                | validate ---------->|                     |
   |                | packet from validated inputs              |
   |                | read current review --------------------->|
   |                | compose using same inputs                 |
   |                | validate evidence and save proposal ------>|
   |                | commit; save derived outcome ------------>|
   |<---------------| same proposed Assertion                   |
```

## Data Model

The private context exists only in memory for one command.
It contains existing validated objects and creates no new Ledger or Archive record type.
No persistent cache, migration, or cross-command cache is introduced.

## APIs / Interfaces

Public packet, decision, and recomposition signatures remain unchanged under API-01.
Private composition wiring passes the context explicitly.
The context carries no cached construction review or proposal state.

## Behavior & Domain Rules

Existing validators remain mandatory on the initial load under CTX-01 and CTX-03.
Packet construction still validates its Source bindings.
The composition use case still validates its structured inputs and evidence.
TX-01 retains the accepted review prerequisites and the separate Assertion acceptance operation.
The correction introduces no stale-state fallback.

## Acceptance Criteria

- AC-CTX: A captured production journey counts one paragraph load, token load, and inventory construction per recomposition command.
- AC-FRESH: A subsequent command rejects a corrupted token artifact, verifying CTX-03.
- AC-TX: Existing retry, rollback, derived-file recovery, acceptance, and replay tests verify TX-01.
- AC-API: Existing supported command tests verify API-01.
- AC-CHECKS: Whole-tree formatting, lint, typecheck, schema drift, and the human-started full suite pass before integration.

Observed durations come from the focused command outputs without a timing threshold.
They describe those runs only and establish no human-effort reduction or whole-suite speedup.

## Reference Implementations

- Review Pipeline: `packages/pipelines/src/kotekomi_pipelines/event_review_workflow.py`.
- Input validation: `packages/pipelines/src/kotekomi_pipelines/replay_reader/transport.py`.
- Captured acceptance: `packages/pipelines/tests/test_announcement_review.py`.
- Transaction failures: `packages/pipelines/tests/test_ipi_production_promotion.py`.

## Constraints and Halt Conditions

Use the successor task's remaining correction budget and integration gates.
Keep paragraph discovery and further linguistic rules outside this increment.
Freeze implementation before selecting the two additional development statements for assessment.
