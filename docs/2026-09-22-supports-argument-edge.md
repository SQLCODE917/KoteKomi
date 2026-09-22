# TDD: Supports ArgumentEdge

- Status: Planned
- Deliverable ID: D2
- Package: [Event Attribution Production Wiring](2026-09-22-event-attribution-wiring-package.md)
- Depends on: D1

## Context & Problem

The graph projection consumes `ArgumentEdge` relations.
The projection recognizes only `contradicts`.
No production path produces a `supports` ArgumentEdge.
The AIF `supports` relation means the source Assertion increases confidence in the target Assertion.
A reviewed source-support decision already binds evidence to a supported proposition.
The gap is the missing production `supports` producer and its projection consumption.

**Supports edge** means an ArgumentEdge with `relation = supports`.
**Evidence-carrying Assertion** means the Direct Assertion that carries the exact EvidenceTarget.
**Supported Assertion** means the Assertion whose claim the evidence backs.
**Source-support decision** means the reviewed `PropositionDecision` with `disposition = supported`.

### Primary Flow

1. KoteKomi reads a reviewed, accepted source-support decision.
2. KoteKomi binds the evidence-carrying Assertion.
3. KoteKomi binds the supported Assertion.
4. KoteKomi constructs one `supports` ArgumentEdge.
5. KoteKomi records one ProvenanceActivity.
6. The graph projection recognizes the `supports` edge.

The producer is model-free and creates no accepted intelligence beyond the edge.

## Goals

- A reviewer traces which Assertion supports which Assertion.
- The graph projection exposes support alongside contradiction.
- The supports edge preserves its rationale, evidence, and confidence.
- A missing endpoint fails fast and creates no edge.

## Requirements

### Producer

- SPT-PRD-01: The producer emits an `ArgumentEdge` with `relation = supports`.
- SPT-PRD-02: The producer runs without a model call.
- SPT-PRD-03: The producer consumes a reviewed, accepted source-support decision.
- SPT-PRD-04: `from_assertion_id` names the evidence-carrying Assertion.
- SPT-PRD-05: `to_assertion_id` names the supported Assertion.
- SPT-PRD-06: `rationale` is non-empty and comes from the source-support decision.
- SPT-PRD-07: `evidence_target_ids` names the exact supporting targets.
- SPT-PRD-08: `confidence` is present.
- SPT-PRD-09: The producer records one ProvenanceActivity.

### Cross-reference validation

- SPT-REF-01: Both endpoints must be accepted Assertions.
- SPT-REF-02: A missing endpoint fails fast and creates no edge.
- SPT-REF-03: A non-accepted endpoint fails fast and creates no edge.

### Projection

- SPT-PRJ-01: The graph projection reads `supports` edges.
- SPT-PRJ-02: The graph projection exposes a support dimension beside the contradiction dimension.
- SPT-PRJ-03: The projection remains derived state.

## Proposed Architecture

```text
accepted source-support decision
        |
        v
supports producer
        |
        +--> evidence-carrying Assertion
        +--> supported Assertion
        |
        v
ArgumentEdge(relation = supports)
        |
        v
graph projection consumes supports
```

## Key Interactions

```text
Application -> Ledger Port: load two accepted Assertions
Application -> Domain Core: parse ArgumentEdge
Application -> Ledger Port: commit one ArgumentEdge and ProvenanceActivity
Application -> graph projection: consume supports edges
```

## Data Model

No new Domain Core record exists.
The producer creates `ArgumentEdge` records whose fields already exist.
The `confidence` field reuses the existing `Confidence` value.

## APIs / Interfaces

The produced `ArgumentEdge` carries these contract fields:

```text
relation            = supports
from_assertion_id   = evidence-carrying Assertion ID
to_assertion_id     = supported Assertion ID
rationale           = non-empty reviewed reason
evidence_target_ids = exact supporting targets
confidence          = present
```

## Behavior & Domain Rules

- SPT-RUL-01: A supports edge connects an evidence-carrying Assertion to the Assertion it supports.
- SPT-RUL-02: The producer never invents a support relationship.
- SPT-RUL-03: The producer never converts model output into the edge directly.
- SPT-RUL-04: The producer creates no accepted intelligence beyond the edge.
- SPT-RUL-05: The graph projection treats the edge as derived state.

## Acceptance Criteria

- AC-SPT-PRD-01: A reviewed supported decision produces one `supports` ArgumentEdge.
- AC-SPT-PRD-02: The edge sets `from_assertion_id` to the evidence-carrying Assertion.
- AC-SPT-PRD-03: The edge sets `to_assertion_id` to the supported Assertion.
- AC-SPT-PRD-04: The edge keeps a non-empty rationale.
- AC-SPT-PRD-05: The edge keeps the exact evidence target IDs.
- AC-SPT-REF-01: A missing endpoint raises a typed failure and creates no edge.
- AC-SPT-REF-02: A non-accepted endpoint raises a typed failure and creates no edge.
- AC-SPT-PRJ-01: The graph projection reports the supports edge in its support dimension.
- AC-SPT-PRJ-02: The contradiction dimension still reports only `contradicts` edges.
- AC-SPT-RUL-02: No model task runs during production.

## Reference Implementations

- ArgumentEdge model: `packages/domain/src/kotekomi_domain/models.py`.
- Graph projection: `packages/application/src/kotekomi_application/evidence_graph_projection.py`.
- Source-support decisions: `packages/application/src/kotekomi_application/semantic_proposition.py`.
- Semantic support judgments: `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.
- Attributed-statement endpoint: D1.

## Constraints and Halt Conditions

Halt if the supported Assertion still exists only as an Event record.
Halt if D1 has not yet produced a bindable Evidence-carrying Assertion.
Halt if the edge requires a model call.
Halt if the projection must store support outside the Ledger and Archive.