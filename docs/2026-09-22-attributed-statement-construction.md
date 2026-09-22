# TDD: Attributed-Statement Construction

- Status: Planned
- Deliverable ID: D1
- Package: [Event Attribution Production Wiring](2026-09-22-event-attribution-wiring-package.md)
- Depends on: none

## Context & Problem

The governed Event path proposes one Event record per source-grounded Event.
The governed Event path does not propose the Assertion that preserves source attribution.
The source may report that one Actor or Organization stated the Event content.
Example source: "Sacks stated that Anthropic ran a sophisticated regulatory strategy."
The Event path currently keeps that content as an Event record.
It loses that Sacks stated the content.
The standing-fact path proposes `source_report` Assertions.
That path has no attribution target.
The gap is the missing Event-path constructor for `attributed_statement` Assertions.

**Attribution target** means the named Actor or Organization that the Source credits with the reported content.
**Attributed statement** means an Assertion with `epistemic_scope = attributed_statement`.
**Event path** means the HP-6 governed semantics and HP-7 proposal flow.
**Standing-fact path** means the HP-10 standing-fact proposal flow.
**Reporting carrier** means the source clause that names the attribution target.
**Governed complement** means the reported content clause.

### Primary Flow

1. KoteKomi loads one immutable HP-6 Preview.
2. KoteKomi reads each `EventSemanticDraft` and its attribution.
3. KoteKomi dispatches on `attribution_kind`.
4. KoteKomi resolves a targeted attribution to an Actor or Organization.
5. KoteKomi constructs one `attributed_statement` ProposedAssertion.
6. The existing review flow approves, edits, or rejects that Assertion.
7. An unresolved attribution raises a typed failure and creates no attributed-statement Assertion.

## Goals

- A reviewer inspects an Event proposition that names who stated the content.
- The attributed statement preserves the reporting carrier and governed complement.
- The standing-fact path keeps its `source_report` Assertion.
- An unresolved attribution never becomes accepted state.

## Requirements

### Attribution dispatch

- ASC-ATR-01: The constructor reads `EventSemanticDraft.attribution_kind`.
- ASC-ATR-02: The constructor reads `EventSemanticDraft.attribution_target_id` when one exists.
- ASC-ATR-03: `attribution_kind = source_narrator` produces no attributed-statement Assertion.
- ASC-ATR-04: `attribution_kind = mention_candidate` enters target resolution.
- ASC-ATR-05: `attribution_kind = source_span` enters target resolution.
- ASC-ATR-06: `attribution_kind = unresolved` fails fast for that Event and produces no attributed-statement Assertion.

### Target resolution

- ASC-RES-01: Resolution reuses the existing typed-candidate reference resolution.
- ASC-RES-02: A resolved attribution target must be an Actor or an Organization.
- ASC-RES-03: A `source_span` target resolves only when the span denotes a named Actor or Organization.
- ASC-RES-04: An attribution that cannot resolve to an Actor or Organization fails fast for that Event.

### Record construction

- ASC-REC-01: The proposed record is a `ProposedAssertion`.
- ASC-REC-02: The record sets `assertion_type = source_claim`.
- ASC-REC-03: The record sets `epistemic_scope = attributed_statement`.
- ASC-REC-04: The record sets `attributed_to_id` to the resolved Actor or Organization ID.
- ASC-REC-05: The record sets `attribution_basis = reported_by_source`.
- ASC-REC-06: The record sets `source_ids` and `evidence_target_ids` to the exact Source and EvidenceTarget.
- ASC-REC-07: The record passes `ProposedAssertion` validation before publication.

### Standing-fact scope

- ASC-SCOPE-01: The standing-fact path keeps `epistemic_scope = source_report`.
- ASC-SCOPE-02: D1 does not change standing-fact construction.

## Proposed Architecture

```text
HybridEventSemanticsPreview
         |
         v
attributed-statement constructor
      (dispatch on attribution_kind)
       /        |          \
      v         v           v
 source_     mention_    source_
 narrator   candidate     span
   |          \            /
   |           v          v
   |      resolve attribution target
   |           |
   |           v
   |      Actor or Organization
   |           |
   |           v
   |      ProposedAssertion
   |      attributed_statement
   |
   +--> no attribution Assertion
```

## Key Interactions

```text
Application -> Domain Core: parse EventSemanticDraft
Application -> Domain Core: parse ProposedAssertion
Application -> Ledger Port: validate referenced Actor or Organization
Application -> Ledger Port: commit one ProposedChange batch
```

## Data Model

No new Domain Core record exists.
No new Application Layer DTO exists.
The constructor produces `ProposedAssertion` records whose fields already exist.
The reviewer assigns the canonical predicate when they accept the Assertion.

## APIs / Interfaces

The produced `ProposedAssertion` carries these contract fields:

```text
assertion_type    = source_claim
epistemic_scope   = attributed_statement
attributed_to_id  = <ActorId or OrganizationId>
attribution_basis = reported_by_source
source_ids        = (source.id,)
evidence_target_ids = (support target,)
```

A targeted attribution always sets `attributed_to_id`.
`source_narrator` sets no attributed-statement Assertion.
`unresolved` produces a typed failure instead of a record.

## Behavior & Domain Rules

- ASC-RUL-01: An attributed statement uses `epistemic_scope = attributed_statement`.
- ASC-RUL-02: An attributed statement requires `attributed_to_id`.
- ASC-RUL-03: The constructor never fabricates an attribution target.
- ASC-RUL-04: The constructor never silently drops an unresolved attribution.
- ASC-RUL-05: The constructor runs without a model call.
- ASC-RUL-06: The constructor creates no accepted state.
- ASC-RUL-07: The constructor writes reviewable ProposedChanges only.
- ASC-RUL-08: An unresolved attribution leaves the existing Event proposal unchanged.

## Acceptance Criteria

- AC-ASC-ATR-01: A `mention_candidate` Event produces one `attributed_statement` ProposedAssertion.
- AC-ASC-ATR-02: A `source_span` Event that names an Organization produces one `attributed_statement` ProposedAssertion.
- AC-ASC-ATR-03: A `source_narrator` Event produces no attributed-statement Assertion.
- AC-ASC-ATR-04: An `unresolved` Event raises a typed failure and produces no attributed-statement Assertion.
- AC-ASC-RES-01: A `source_span` Event that does not denote an Actor or Organization fails fast for that Event and produces no attributed-statement Assertion.
- AC-ASC-REC-01: The produced record sets `attributed_to_id` to the resolved Actor or Organization ID.
- AC-ASC-REC-02: The produced record sets `attribution_basis = reported_by_source`.
- AC-ASC-REC-03: The produced record passes `ProposedAssertion` validation.
- AC-ASC-SCOPE-01: A standing-fact draft still produces `source_report`.
- AC-ASC-SCOPE-02: No standing-fact test changes behavior.
- AC-ASC-RUL-05: No model task runs during construction.

## Reference Implementations

- Event governed semantics: `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.
- Attribution resolution: `packages/application/src/kotekomi_application/hybrid_event_semantics_preview.py`.
- Event proposal construction: `packages/application/src/kotekomi_application/hybrid_proposed_changes.py`.
- Standing-fact Assertion construction: `packages/application/src/kotekomi_application/hybrid_standing_facts.py`.
- Assertion validation: `packages/domain/src/kotekomi_domain/models.py`.

## Constraints and Halt Conditions

Halt if `attributed_to_id` cannot be captured without a new Domain Core record.
Halt if `source_narrator` requires setting `attributed_to_id`.
Halt if the Event path must distinguish `direct_document` from `quoted_statement`; that distinction is a later deliverable.
Halt if a model call becomes necessary to resolve attribution.