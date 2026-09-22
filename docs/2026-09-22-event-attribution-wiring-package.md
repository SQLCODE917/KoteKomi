# Event Attribution Production Wiring Package

- Status: Planned
- Program ID: `event-attribution-production-wiring`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Predecessor evidence:
  [Source-Grounded Proposition Scope Experiment](2026-09-17-source-grounded-proposition-scope-experiment.md),
  [Standing-Fact Semantic Admission](2026-09-06-standing-fact-semantic-admission.md)

## Context & Problem

The governed Event path proposes Event records.
The governed Event path does not propose the Assertion that preserves source attribution.
The standing-fact path proposes `source_report` Assertions.
Neither path proposes an `attributed_statement` Assertion with `attributed_to_id`.
The source-grounded proposition experiment falsified marker-free reconstruction because attribution, negation, and modality were lost.
The gap is the missing construction wiring between the governed Event and its attribution.

**Event-vs-attribution gap** means the missing Event-path construction of `attributed_statement` Assertions,
their `attributed_to_id`, their `supports` ArgumentEdges, and the deterministic reporting-carrier split.

**Deliverable** means one independently shippable and revertable construction-wiring unit.

This package changes no Domain Core schema and no Application Layer DTO.
It wires existing fields and enums into new construction paths.

## Deliverables

| Deliverable | Title | Produces | Depends on |
|---|---|---|---|
| D1 | Attributed-statement construction | `attributed_statement` ProposedAssertion with `attributed_to_id` | none (uses existing `EventSemanticDraft` attribution) |
| D2 | `supports` ArgumentEdge | first production `supports` ArgumentEdge | D1 |
| D3 | Deterministic trigger-scope split | reporting carrier plus governed complement signal | none |

## Order

D3 runs first and produces the deterministic signal.
D1 runs in parallel using the existing `EventSemanticDraft` attribution signal.
D2 runs after D1 endpoints exist.
D1, D2, and D3 each ship and revert independently.

The exact specification for each deliverable lives in its TDD:

- [D1 Attributed-Statement Construction](2026-09-22-attributed-statement-construction.md)
- [D3 Deterministic Trigger-Scope Split](2026-09-22-deterministic-trigger-scope-split.md)
- [D2 Supports ArgumentEdge](2026-09-22-supports-argument-edge.md)

## Completion

The package completes when all three deliverable TDDs pass their acceptance criteria.
The package completes when `docs/CHECK_PLAN.md` gains one verification step per deliverable.
The package completes when production constructs, reviews, and projects an attributed Event proposition
without losing the reporting carrier or the governed complement.