# Complete Announcement Statements

## Context & Problem

An operator opens an Event review packet and requests a complete proposed Assertion.
An Event identifies a happening; an Assertion states its atomic meaning with evidence.
A ProposedChange keeps that Assertion pending review.
The captured GenAI.mil announcement currently fails selection on unsupported descriptive attachments.
Its month/year structure also fails temporal derivation.
The [successor task](2026-11-11-ingestion-improvements-task.md) freezes the required meaning and delivery gates.
The behavior below is planned.

Primary end-to-end flow:

1. The operator opens the captured announcement's packet.
2. Selection retains the subject phrase and the selected core object.
3. Completion adds the platform description, and temporal derivation retains the exact month/year.
4. The operator records identity, predicate, and classification decisions through supported commands.
5. Recomposition persists one pending Assertion ProposedChange with complete statement evidence.
6. Saved replay displays the same proposed meaning and evidence.

## Goals

- The operator sees the full announcement, platform description, and date in the proposed Assertion.
- Unsupported descriptions remain explicit holds.
- The three promoted development cases continue to work.

## Requirements

### Application Layer selection

- SEL-01: Selection permits one attached `nmod:desc` nominal title in a contiguous subject phrase.
  The title can contain noun modifiers and one outer prepositional complement with nested noun content.
- SEL-02: Selection preserves exact-match priority, existing result types, and the core object boundary.
  An object's `appos` dependent defers completion to CMP-01.
- SEL-03: Multiple titles, clauses, coordination, unrelated roles, and disconnected title content retain explicit existing gaps.

### Application Layer completion

- CMP-01: `ObjectContentCompletion` extends the selected object through one contiguous nominal appositive description.
  The nominal head carries one outer prepositional complement at most, including nested noun content.
- CMP-02: Completion preserves exact Source characters and the selected object's starting coordinate.
  Packet, proposed Assertion, supporting object span, and statement EvidenceTarget must agree.
- CMP-03: Multiple descriptions, clauses, coordination, disconnected content, and invalid Source bindings fail explicitly.
  Existing participial completion remains supported.

### Application Layer time derivation

- TIME-01: A month head can carry one numeric four-digit year through `nmod:unmarked`.
  The year must attach directly to that month and carry no additional content.
- TIME-02: Derivation preserves exact characters and existing treatment of boundary punctuation.
  Place and instrumental obliques retain their holds.

### Review Pipeline

- FLOW-01: Supported review operations carry CMP-02 and TIME-02 through persistence and saved replay.
- FLOW-02: Retry retains one matching pending Assertion ProposedChange.
  Existing transaction rollback and recovery after derived-file failure remain intact.
- FLOW-03: A separate delegated review can accept a verified Assertion through the supported review operation.
  Reloaded accepted state must validate evidence, references, proposal status, and ProvenanceActivity.
- FLOW-04: Recomposition validates statement evidence through the existing evidence-validation use case.
  The proposal must name that successful attempt in its explicit direct-support evidence-link specification.
  Validation and proposal writes share the recomposition transaction.
  Retry replays the existing validation instead of creating duplicate attempts.

## Proposed Architecture

The Application Layer owns selection, completion, time derivation, and Assertion construction.
The review Pipeline composes use cases and owns transaction boundaries.
SQLite and file Adapters persist canonical records and derived composition outcomes.

```text
Operator -> Review Pipeline -> Application Layer -> Domain Core
                 |                    |
                 +-> SQLite / Archive Adapters
                 |
                 +-> saved replay
```

## Key Interactions

```text
Operator       Review Pipeline       Application Layer       Ledger / Archive
   | packet          |                      |                       |
   |---------------->| load validated inputs ---------------------->|
   |                 | select / complete / derive                   |
   |                 |--------------------->|                       |
   |<----------------| complete packet      |                       |
   | decisions       |                      |                       |
   |---------------->| review prerequisites ----------------------->|
   | recompose       |                      |                       |
   |---------------->| construct ---------->|                       |
   |                 | pending proposal and evidence -------------->|
   | replay          | read saved result -------------------------->|
   |<----------------| proposed Assertion and exact spans           |
```

## Data Model

Retain existing Domain Core schemas, `ObjectContentCompletion`, packet fields, and time qualifier records.
The Assertion qualifier map retains the existing `time` key.
No migration or new stored record type is required.

## APIs / Interfaces

Retain public selector results and command signatures.
The selected object label continues to identify its original candidate.
The existing explicit completion input carries the extended range into composition.
No named-person lexical rule or inferred identity is introduced.

## Behavior & Domain Rules

Invalid deterministic Source bindings raise validation errors before review writes.
Unsupported linguistic content retains typed gaps or `unsupported_object_complement` holds.
Identity requires an explicit review decision even when selection includes a descriptive title.
Ordinary no-time Assertion identity and existing participial completion remain unchanged.
The proposal stays pending until a separate supported review accepts it.

## Acceptance Criteria

- AC-SEL: Failing-first captured and negative regressions verify SEL-01 through SEL-03.
- AC-CMP: Exact appositive content and malformed, competing, clausal, coordinated, and disconnected cases verify CMP-01 through CMP-03.
- AC-TIME: Captured month/year and contextual negative cases verify TIME-01 and TIME-02.
- AC-FLOW: Disposable SQLite journeys verify FLOW-01 through FLOW-04 without seeded review prerequisites or composition outcomes.
- AC-REG: The three promoted cases, ordinary no-time identity, and participial completion pass.
- AC-CHECKS: Whole-tree formatting, lint, typecheck, and the human-started full suite pass before integration.

Engineering verification and demonstrated capability remain separate decisions in the successor task.
The successor's additional-case target applies only after implementation freezes.

## Reference Implementations

- Selection: `packages/application/src/kotekomi_application/source_grounded_selection.py`.
- Completion: `packages/application/src/kotekomi_application/decontextualization_composition.py`.
- Temporal derivation: `packages/application/src/kotekomi_application/trigger_time_qualifier.py`.
- Review: `packages/pipelines/src/kotekomi_pipelines/event_review_workflow.py`.
- Captured journeys: `packages/pipelines/tests/test_ipi_production_promotion.py`.

## Constraints and Halt Conditions

Use retained captures; this correction changes no model extraction boundary.
Keep paragraph discovery and recomposition latency changes outside this increment.
Apply the successor task's cycle budget and integration gates.
