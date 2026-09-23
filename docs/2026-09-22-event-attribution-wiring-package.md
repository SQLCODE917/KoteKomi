# Event Attribution Production Wiring Package

- Status: In Progress
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
| D4 | Wiring composition | one governed Event into carrier + complement + `attributed_statement` proposal + pinned D2 recipe | D1, D2, D3 |
| D5 | Event attribution submission manifest | a validated `EventAttributionManifest` reconstructed into `EventAttributionWiringInput` | D4 |
| D6 | Reviewed attributed-statement submission | a pending or recorded `attributed_statement` ProposedChange plus its ProvenanceActivity, or a typed non-record | D4, D5 |

## Order

D3 runs first and produces the deterministic signal.
D1 runs in parallel using the existing `EventSemanticDraft` attribution signal.
D2 runs after D1 endpoints exist.
D1, D2, and D3 each ship and revert independently.

D5 ships after D4 and pins one `EventAttributionManifest` per submission.
D6 ships after D5 and submits the reviewed proposal through the reviewed submitter.
The `submit-attribution` CLI command wires D5 plus D6 into the pipelines CLI.

The exact specification for each deliverable lives in its TDD:

- [D1 Attributed-Statement Construction](2026-09-22-attributed-statement-construction.md)
- [D3 Deterministic Trigger-Scope Split](2026-09-22-deterministic-trigger-scope-split.md)
- [D2 Supports ArgumentEdge](2026-09-22-supports-argument-edge.md)
- [D4 Wiring Composition](2026-09-22-event-attribution-wiring-composition.md)

D5 and D6 ship through `packages/pipelines/src/kotekomi_pipelines/event_attribution_stage_local.py`
with the `event_attribution_submission_v1` fixture and its fixture-backed tests.

## Completion

The package completes when every deliverable passes its acceptance criteria.
The package completes when `docs/CHECK_PLAN.md` gains one verification step per deliverable.
The package completes when the `submit-attribution` CLI command submits a reviewed manifest as a
pending `attributed_statement` ProposedChange without losing the reporting carrier or the governed
complement.