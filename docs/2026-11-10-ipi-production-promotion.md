# Retain the IPI Production Improvements

## Context & Problem

An operator reviews an Event, accepts its identity prerequisites, and recomposes a proposed Assertion.
The baseline can truncate an argument before its essential noun complement and holds supported time expressions.
An Assertion states one atomic meaning; a ProposedChange holds that proposed record pending human review.
IPI demonstrated partial development gains at `d001544` and `2ec4737` relative to `7dc9a44`.
The misplaced time validator also accepts whitespace-only content.
This promotion retains those corrections with stricter deterministic validation.
It does not start another improvement cycle.

Primary end-to-end flow:

1. The operator opens a packet built from captured ingestion records.
2. Selection supplies complete supported arguments and derivation supplies exact supported time text.
3. The operator records the required identity and classification decisions.
4. Recomposition persists a pending Assertion ProposedChange with replayable statement evidence.
5. Saved replay displays the same content, qualifiers, and evidence.

## Goals

- The operator sees complete supported participant and object phrases.
- The operator sees the exact supported time expression in the packet and proposed Assertion.
- Invalid deterministic input fails explicitly before it can affect review state.

## Requirements

- SEL-01: Application Layer selection preserves exact-match priority and existing typed gaps.
- SEL-02: Selection expands only one covering candidate that excludes the trigger.
- SEL-03: Added tokens form the same contiguous noun phrase with at most one direct outer prepositional complement.
  Nested content in that complement remains supported.
  Unrelated attachments, clauses, appositives, coordination, and unsupported relations retain existing gaps.
- TIME-01: `TriggerTimeQualifier` rejects whitespace-only text during construction and JSON loading.
- TIME-02: Derivation validates source coordinates and token/source agreement before interpreting time.
- TIME-03: The proposition validates that its qualifier identifies the same Event.
- TIME-04: Derivation preserves supported recognition, source characters, punctuation treatment, and unsupported-oblique holds.
- FLOW-01: The Pipeline preserves selected text and time through review, statement evidence, construction, persistence, and replay.
- FLOW-02: Retry creates one matching pending Assertion ProposedChange and no accepted Assertion.
  Transaction failures preserve the existing atomicity contract.
- ID-01: Assertion identity includes time content.

## Proposed Architecture

The Application Layer owns selection, time derivation, proposition validation, and Assertion construction.
The existing review Pipeline composes these operations and controls Ledger transactions.
SQLite and file Adapters store canonical records and composition outcomes.
Replay reads the retained records.

```text
Operator -> Review Pipeline -> Application Layer -> Domain Core
                 |                  |
                 +--> SQLite / Archive Adapters
                 |
                 +--> saved replay
```

## Key Interactions

```text
Operator       Review Pipeline       Application Layer       Ledger / Archive
   | packet          |                      |                       |
   |---------------->| load captured inputs |---------------------->|
   |                 | select / derive      |                       |
   |                 |--------------------->|                       |
   |<----------------| exact packet         |                       |
   | decision        |                      |                       |
   |---------------->| validate / accept prerequisites ------------>|
   | recompose       |                      |                       |
   |---------------->| compose / construct ->|                      |
   |                 | pending proposal and evidence -------------->|
   | replay          | read saved result -------------------------->|
   |<----------------| proposed Assertion and source spans          |
```

## Data Model

Retain `TriggerTimeQualifier` with `event_id` and `exact_range`.
Retain the optional `adjunct_qualifier` on `DecontextualizedProposition`.
Retain the existing Assertion qualifier map with the `time` key.
Use existing Ledger records and Archive artifacts without a Domain Core schema change or migration.

## APIs / Interfaces

Retain the selector entry point, result types, and existing review commands.
Retain the packet's optional time coordinates and text.
The packet serializer exposes these fields through the existing command.
No additional command, model call, date normalization, or general exporter is introduced.

## Behavior & Domain Rules

Selection labels, selected boundaries, composed content, and supporting spans identify the same source content.
Invalid source bindings raise validation errors; unsupported linguistic content produces typed holds.
Review accepts prerequisites only through existing use cases.
Assertion construction leaves the Assertion proposed until a separate human review.

## Acceptance Criteria

- AC-SEL: Captured development parses and synthetic counterexamples verify SEL-01 through SEL-03.
- AC-TIME: Direct, JSON, source-binding, foreign-Event, date, relative-time, and unsupported-oblique tests verify TIME-01 through TIME-04.
- AC-FLOW: Portable captured-input SQLite journeys verify FLOW-01, FLOW-02, and ID-01.
  Cases cover Department of Defense and its policy with `in  2012`, Amodei's semiconductor criticism,
  and integration of Anthropic's services with `Prior to the dispute`.
  Fixtures seed ingestion inputs only, without accepted review prerequisites or composition outcomes.
- AC-CHECKS: Focused tests, whole-tree formatting, lint, and typecheck pass.
  The human starts the full suite with durable logs and a deterministic terminal-status probe.
  Readiness requires inspection of its terminal result.

Implementation verification establishes tested contracts only.
Captured-input regressions establish behavior on those development inputs, not independent extraction accuracy.
IPI's recorded development result improved from 0/8 to 3/8; reserved remained 0/8.
The delegated assessment did not establish reduced human effort.
The package target remains **Target not met**.

## Reference Implementations

- Selection: `packages/application/src/kotekomi_application/source_grounded_selection.py`.
- Review: `packages/pipelines/src/kotekomi_pipelines/event_review_workflow.py`.
- Disposable Ledger journey: `packages/pipelines/tests/test_operator_journey.py`.
- Saved replay: `packages/pipelines/tests/support/replay_fixtures.py`.

## Constraints and Halt Conditions

Promote from `7dc9a44` on `ipi-production-promotion` in a separate worktree.
Exclude measurement and custody tooling and package-history edits from the promotion.
Preserve reserved material, original operator Ledgers, historical contracts, and uncommitted guidance.
Use reviewed meanings as acceptance authority; do not regenerate expectations from changed output.
Stop after retention and verification; another capability cycle requires a separate scope decision.
Push and merge require separate authorization.
