# TDD: Event Attribution Wiring Composition

- Status: Accepted
- Deliverable ID: D4
- Package: [Event Attribution Production Wiring](2026-09-22-event-attribution-wiring-package.md)
- Depends on: D1, D2, D3

## Context & Problem

D1, D2, and D3 each shipped an independent, deterministically tested construction unit:

- D3 `split_trigger_scope` splits one governed Event trigger into its reporting carrier and
  governed complement.
- D1 `construct_attributed_statement` converts one governed `EventSemanticDraft` plus its
  resolved attribution target into an `attributed_statement` `ProposedAssertion`.
- D2 `produce_support_edge` binds an accepted evidence-carrying Assertion to an accepted
  supported Assertion with a `supports` `ArgumentEdge`.

None of them composes the other two, and no production path runs all three over one governed
Event such that an `attributed_statement` is constructed without losing the reporting carrier
or the governed complement. The gap is the missing composition between the three deliverables.

## Goals

- One governed Event yields one reporting carrier, one governed complement, and one
  `attributed_statement` proposal in a single deterministic call.
- A held split blocks the attributed-statement construction instead of silently merging the
  two parts.
- The D2 support edge recipe is pinned the moment the attributed statement is constructed.
- The composition runs without a model call and writes no canonical state.

## Requirements

### Composition

- WIR-CMP-01: The composer runs D3, then D1, and pins D2's inputs in one call.
- WIR-CMP-02: The composer runs without a model call.
- WIR-CMP-03: A complete split carries both the reporting carrier and the governed complement.
- WIR-CMP-04: A held split produces a typed held result and constructs no assertion.
- WIR-CMP-05: A constructed outcome produces one `attributed_statement` `ProposedAssertion`.
- WIR-CMP-06: The pinned D2 input names the evidence-carrying Assertion as
  `from_assertion_id` and the constructed assertion as `to_assertion_id`.
- WIR-CMP-07: The pinned D2 input carries non-empty rationale, a finite confidence, the exact
  evidence target IDs, and the support decision, judgment, and NLI observation IDs.
- WIR-CMP-08: A `source_narrator` Event produces a no-assertion outcome and no D2 input.
- WIR-CMP-09: An `unresolved` Event produces a typed failed outcome and no D2 input.

## Proposed Architecture

```text
governed Event + trigger + linguistic evidence
        |
        v
split_trigger_scope (D3) -> complete or held
        |
        v
construct_attributed_statement (D1) -> proposed assertion or typed non-record
        |
        v
pin produce_support_edge (D2) input recipe
```

The composer is model-free and writes nothing. Review and acceptance of the
`attributed_statement`, the actual D2 write, and the evidence-graph projection rebuild remain
separate Application Layer use cases composed by the Pipeline.

## Data Model

No new Domain Core record exists. The composer returns a composition result whose fields reuse
`TriggerScopeSplit`, `AttributedStatementOutcome`, and `ProduceSupportEdgeInput`.

## APIs / Interfaces

```text
wire_event_attribution(wiring_input, resolver) -> EventAttributionWiringResult
```

- `wiring_input` pins the governed Event, its trigger, its linguistic evidence, its semantic
  draft, its attribution target, its content triple (`subject_entity_id` /
  `relation_label` / `object_entity_id | object_value`), its source and evidence target IDs,
  its prospective assertion ID, and the D2 ingredients.
- `resolver` resolves the attribution target to an `ActorId` or `OrganizationId`.
- `EventAttributionWiringResult` carries one of four terminal statuses:
  `constructed`, `held`, `no_assertion`, `failed`.

## Behavior & Domain Rules

- WIR-RUL-01: The composer never merges a held split into a proposition.
- WIR-RUL-02: The composer never invents a support relationship.
- WIR-RUL-03: The composer never converts model output into accepted state.
- WIR-RUL-04: The composer creates no canonical state.

## Acceptance Criteria

- AC-WIR-CMP-01: A targeted Event with a complete split produces a `constructed` outcome with
  both carrier and complement, one `attributed_statement` proposal, and a pinned D2 input.
- AC-WIR-CMP-02: A governed-complement-only source produces a `held` outcome, no assertion,
  and no D2 input.
- AC-WIR-CMP-03: A `source_narrator` Event produces a `no_assertion` outcome and no D2 input.
- AC-WIR-CMP-04: An `unresolved` Event produces a `failed` outcome and no D2 input.
- AC-WIR-CMP-05: The pinned D2 input sets `to_assertion_id` to the constructed assertion ID.
- AC-WIR-CMP-06: No model task runs during composition.

## Reference Implementations

- D3: `packages/application/src/kotekomi_application/trigger_scope_split.py`.
- D1: `packages/application/src/kotekomi_application/attributed_statement_construction.py`.
- D2: `packages/application/src/kotekomi_application/support_edge_production.py`.
- Event drafts: `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.
- Linguistic evidence: `packages/application/src/kotekomi_application/event_entity_connections.py`.