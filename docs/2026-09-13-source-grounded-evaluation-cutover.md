# TDD: Source-Grounded Evaluation Cutover

- Status: Complete
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Event contract: [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md)
- Standing Fact contract: [Paragraph Standing Facts MVP](2026-09-05-paragraph-standing-facts-mvp.md)

## 1. Context & Problem

KoteKomi now admits Events from exact source expressions.

The canonical verifier still runs checks that require governed frames and roles.

Those checks describe a retired Event admission design.

The verifier can pass while it displays failures from that retired design.

The mention and reference evaluator also imports the retired evaluation contract.

The reviewed source segments remain useful for current mention and reference evaluation.

The verifier currently tests one Standing Fact through the retired contract.

**Front-Half Gold** records reviewed mention and reference expectations for exact SourceSegments.

**Standing Fact Gold** records reviewed standing relationships for exact SourceSegments.

**Normalized Event Comparison** maps human Gold locators and runtime records to exact source ranges.

**Current Evaluation Report** contains only checks for the accepted Hybrid Pipeline architecture.

### Primary Flow

1. The Pipeline loads Front-Half Gold for mention and reference evaluation.
2. The Pipeline maps Event Gold and Event records into Normalized Event Comparisons.
3. The Pipeline evaluates Standing Fact Gold against Standing Fact records and ProposedChanges.
4. The canonical verifier combines only these current evaluation results.
5. The operator receives one report whose pass status agrees with every displayed check.

## 2. Goals

- An operator can understand each expected and actual Event comparison directly.
- An operator sees only checks for the accepted Hybrid Pipeline architecture.
- Reviewed mention and reference expectations remain available after the cutover.
- Every reviewed Standing Fact receives a dedicated current evaluation.
- The canonical pass result agrees with every required evaluation.

## 3. Requirements

### Front-Half Gold

- SGC-F01: Front-Half Gold stores exact source text and its SHA-256 digest.
- SGC-F02: Front-Half Gold stores one focus entity and its accepted source literals.
- SGC-F03: Front-Half Gold stores reviewed reference expressions and accepted antecedent texts.
- SGC-F04: Front-Half Gold stores no Event frame, role, qualifier, or proposal expectation.
- SGC-F05: One split assigns every Front-Half Gold item to one evaluation phase.
- SGC-F06: The split prevents one SourceSegment digest from crossing evaluation phases.
- SGC-F07: Gold stores every accepted antecedent alternative directly.

### Event Evaluation

- SGC-E01: The evaluator resolves each Gold SourceOccurrence ID against exact source text.
- SGC-E02: A Normalized Event Comparison stores the expected head text and range.
- SGC-E03: A Normalized Event Comparison stores every accepted expression and range.
- SGC-E04: A Normalized Event Comparison stores the actual head text and range.
- SGC-E05: A Normalized Event Comparison stores the actual expression text and range.
- SGC-E06: A Normalized Event Comparison stores runtime Event and evidence identities.
- SGC-E07: The evaluator assigns `exact`, `missing`, `extra`, or `incorrectly_grounded`.
- SGC-E08: Human diagnostic meaning remains separate from the scored comparison.

### Standing Fact Evaluation

- SGC-S01: Standing Fact Gold contains `AMO-02`, `AMO-07`, and `ANT-11`.
- SGC-S02: Each item stores exact subject, accepted relation text, and exact object text.
- SGC-S03: Each item stores its expected proposal disposition.
- SGC-S04: The evaluator validates subject, relation, and object against source characters.
- SGC-S05: The evaluator validates the Standing Fact decision and ProposedChange.
- SGC-S06: The evaluator follows the deterministic document-reconciliation parent proposal mapping and validates Candidate Wiki visibility by the reconciled stable record identity.
- SGC-S07: One missing current result fails only its Standing Fact item.

### Canonical Verification

- SGC-C01: The Current Evaluation Report uses one new schema version.
- SGC-C02: The report contains Front-Half, Event, Standing Fact, and Candidate Wiki results.
- SGC-C03: The report summary contains counts from current evaluators only.
- SGC-C04: Every failed required evaluation creates one finding.
- SGC-C05: The report passes exactly when its findings collection is empty.
- SGC-C06: The verifier emits no retired task-allocation or baseline field.

### Clean Cutover

- SGC-R01: The repository removes the retired task-allocation evaluator.
- SGC-R02: The repository removes its Gold schema, baseline, correction catalog, and split files.
- SGC-R03: The repository removes checks that require a governed frame for Event admission.
- SGC-R04: Optional Event Type Assignment remains derived enrichment.
- SGC-R05: Active documentation names only current evaluation contracts.
- SGC-R06: The repository provides no compatibility reader, alias, or dual-schema path.

## 4. Proposed Architecture

```text
Reviewed Gold ------------------------+
                                      |
Hybrid Pipeline evidence --> evaluators --> Current Evaluation Report
                                      |                |
Candidate Wiki -----------------------+                v
                                                   operator
```

The Pipeline package owns Gold parsing and read-only evaluation.

The canonical verifier composes current evaluation results.

The Application Layer continues to own extraction and proposal decisions.

The Candidate Wiki remains a derived projection.

## 5. Key Interactions

```text
Verifier        Gold        Archive/Ledger       Evaluators       Operator
   |              |                |                  |               |
   |-- load ----->|                |                  |               |
   |---------------- read evidence ------------------>|               |
   |---------------- evaluate current contracts ---->|               |
   |<--------------- typed results ------------------|               |
   |---------------- Current Evaluation Report --------------------->|
```

## 6. Data Model

Front-Half Gold stores catalog identity, Source records, focus entity literals, and reference expectations.

The Front-Half split stores catalog pins and disjoint phase item IDs.

Standing Fact Gold stores catalog identity, fixture identity, and reviewed Standing Fact items.

Each Standing Fact item stores exact source text, source digest, and expected triple text.

Normalized Event Comparison stores resolved Gold ranges beside runtime ranges and identities.

The Current Evaluation Report stores typed evaluator results and one findings collection.

These records are derived evaluation evidence.

They do not change accepted Ledger state.

## 7. APIs / Interfaces

The Front-Half loader accepts only the new Front-Half Gold schema.

The Standing Fact evaluator accepts Standing Fact Gold and canonical paragraph evidence.

The Event evaluator returns Normalized Event Comparisons inside its segment results.

The canonical verifier emits only the Current Evaluation Report schema.

## 8. Behavior & Domain Rules

The evaluator compares normalized source ranges instead of raw DTO equality.

The evaluator preserves runtime identities for audit without making them Gold inputs.

The verifier fails when any required current evaluator fails.

The verifier reports each current failure once at its owning boundary.

The cutover deletes superseded executable contracts.

Git history preserves deleted implementation history.

## 9. Acceptance Criteria

- AC-SGC-F01: Contract tests reject a Front-Half item with a retired semantic field.
- AC-SGC-F02: Front-Half replay preserves the reviewed 20/20 split.
- AC-SGC-F03: Front-Half replay preserves the accepted `ANT-14` antecedent alternative.
- AC-SGC-E01: Event tests render Gold occurrence IDs as exact text and ranges.
- AC-SGC-E02: Event tests reproduce all 87 reviewed Event triggers.
- AC-SGC-E03: Source-grounded tests report zero missing, extra, or incorrect Events.
- AC-SGC-S01: Standing Fact tests evaluate all three reviewed items independently.
- AC-SGC-S02: Standing Fact tests reject non-source text and broken proposal lineage.
- AC-SGC-S03: Candidate Wiki tests identify each visible Standing Fact by stable record identity.
- AC-SGC-C01: Verifier tests reject any retired report key.
- AC-SGC-C02: Verifier tests prove report pass state equals an empty findings collection.
- AC-SGC-R01: Repository search finds no executable task-allocation evaluator or baseline contract.
- AC-SGC-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Event Gold mapping: follow `packages/pipelines/src/kotekomi_pipelines/event_trigger_stage_local.py`.
- Source grounding: follow `packages/pipelines/src/kotekomi_pipelines/source_grounded_event_evaluation.py`.
- Standing Fact records: follow `packages/application/src/kotekomi_application/hybrid_standing_facts.py`.

## 11. Constraints and Halt Conditions

Stop if the cutover requires one model invocation.

Stop if an evaluator can write a ProposedChange or accepted Ledger record.

Stop if optional Event classification controls Event admission.
