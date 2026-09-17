# Event-Entity Measurement Integrity

- Status: Implemented; cumulative repository verification pending
- Parent: [Event-Entity Connection Experiment](2026-09-12-event-entity-connection-experiment.md)
- Review input:
  [Event-Entity Connection Second Opinion](2026-09-16-event-entity-connection-second-opinion.md)

## 1. Context & Problem

The Event-Entity Connection experiment records exact candidate occurrences.

The current evaluator summarizes positive drafts by entity identity.

That summary hides occurrence-level false positives and unresolved decisions.

The current result fingerprint omits the complete candidate inventory.

The Stanza diagnostic also stores a derived comparison label beside each observation.

A verifier can accidentally treat that derived label as Gold.

KoteKomi needs trustworthy measurement before it changes semantic task allocation.

**Occurrence Evaluation** means one exact Event and candidate occurrence compared with raw Gold.

**Strict Metrics** treat `unresolved` as a non-positive answer while preserving that disposition.

**Connected Sensitivity** reports the hypothetical result if every unresolved answer became connected.

### Primary Flow

1. The Pipeline loads approved Connection Gold and one complete phase result.
2. The Pipeline matches each exact candidate occurrence directly to raw Gold.
3. The Pipeline records the observed disposition and strict score for every candidate.
4. The Pipeline computes occurrence metrics and separate identity metrics.
5. The Pipeline fingerprints the complete input inventory, decisions, Gold, and scoring policy.
6. A tracked verifier rejects drift in any typed row or aggregate.

This flow writes derived experiment evidence only.

## 2. Goals

- An operator can inspect every candidate occurrence and its score.
- An operator can distinguish abstention from a negative judgment.
- Two experimental arms can prove that they received equal candidate inventories.
- A verifier fails when raw Gold, source ranges, decisions, or metrics drift.
- Correct measurement defines the baseline for the proposition-scope experiment.

## 3. Requirements

### Gold Evaluation

- EMI-G01: The evaluator derives labels from approved Connection Gold v2.
- EMI-G02: The evaluator matches Gold by Event, entity kind, accepted name, and exact source range.
- EMI-G03: One candidate occurrence matches at most one Gold entity.
- EMI-G04: Every unmatched candidate occurrence is an implicit Gold negative.
- EMI-G05: The evaluator validates every candidate range against the authoritative SourceSegment.
- EMI-G06: The evaluator records the Gold entity IDs that match each occurrence.
- EMI-G07: A derived diagnostic comparison field cannot supply a Gold label.

### Occurrence Scoring

- EMI-O01: Each candidate has one `connected`, `not_connected`, or `unresolved` disposition.
- EMI-O02: A Gold positive with `connected` scores as a true positive.
- EMI-O03: A Gold positive with another disposition scores as a false negative.
- EMI-O04: A Gold negative with `connected` scores as a false positive.
- EMI-O05: A Gold negative with another disposition scores as a true negative.
- EMI-O06: The row preserves `unresolved` independently from EMI-O03 and EMI-O05.
- EMI-O07: Strict precision, recall, and F1 use the four strict score counts.
- EMI-O08: Connected Sensitivity changes only unresolved rows.
- EMI-O09: Identity metrics remain separate secondary observations.

### Inventory Identity

- EMI-I01: A candidate signature binds the Event, candidate ID, entity identity, entity kind,
  entity name, source digest, and primary exact source range.
- EMI-I02: A phase report stores all candidate signatures in canonical order.
- EMI-I03: An arm comparison fails when its candidate signatures differ.
- EMI-I04: Repetition stability requires equal occurrence results and equal candidate signatures.

### Report Integrity

- EMI-R01: The phase report uses one current schema.
- EMI-R02: The report derives every aggregate from its typed occurrence rows.
- EMI-R03: The result fingerprint binds the Gold digest, scoring policy, and occurrence rows.
- EMI-R04: Model elapsed time remains diagnostic and does not affect the result fingerprint.
- EMI-R05: The report records zero ProposedChanges and zero accepted Ledger writes.
- EMI-R06: Invalid deterministic input fails instead of producing a partial report.

## 4. Proposed Architecture

```text
Approved Connection Gold          Event Connection Preview
            |                               |
            +---------------+---------------+
                            |
                            v
                 Pipeline Gold Evaluator
                            |
                            v
              Occurrence Evaluation rows
                            |
             +--------------+--------------+
             |                             |
             v                             v
       Strict Metrics             Connected Sensitivity
             |                             |
             +--------------+--------------+
                            |
                            v
                 Typed Phase Report
```

The Application Layer continues to own candidate and decision contracts.

The Pipeline owns Gold comparison and experiment metrics.

The Domain Core receives no new record.

## 5. Key Interactions

```text
Operator        Runner             Gold Evaluator        Verifier
   |              |                      |                  |
   | finalize     |                      |                  |
   |------------->| load typed inputs    |                  |
   |              |--------------------->|                  |
   |              | occurrence rows      |                  |
   |              |<---------------------|                  |
   |              | write report         |                  |
   |              |---------------------------------------->|
   |              |                      | validate report  |
   | report paths |<----------------------------------------|
```

## 6. Data Model

`EventEntityOccurrenceEvaluation` records one candidate signature, raw Gold match, observed
disposition, strict score, and unresolved state.

`EventEntityConfusionMetrics` records TP, FP, FN, TN, precision, recall, and F1.

`EventEntityCaseEvaluation` contains every occurrence for one Event.

`EventEntityPhaseReport` contains all twenty Event results and both metric views.

These records remain derived experiment evidence.

## 7. APIs / Interfaces

The evaluator accepts approved Connection Gold, prepared Event input, and one typed Preview.

The arm comparator accepts complete typed phase reports.

The verifier accepts typed report paths and expected phase metadata.

The report schema replaces its predecessor without a compatibility reader.

## 8. Behavior & Domain Rules

The candidate primary source span defines the scored occurrence.

The evaluator fails when another candidate span with the same candidate ID differs.

One connected occurrence cannot satisfy a different occurrence of the same literal.

Connected Sensitivity is a diagnostic bound.

Connected Sensitivity does not replace Strict Metrics.

The Markdown review renders typed records but does not define metrics.

## 9. Acceptance Criteria

- AC-EMI-G01: Tests derive all labels from raw Gold without diagnostic comparison fields.
- AC-EMI-G02: Tests reject changed Gold digests and invalid source ranges.
- AC-EMI-G03: Tests reject one candidate that matches multiple Gold entities.
- AC-EMI-O01: Tests cover all Gold and disposition combinations.
- AC-EMI-O02: Tests preserve thirteen unresolved TGE-018 candidates as unresolved rows.
- AC-EMI-O03: Tests prove Connected Sensitivity changes each unresolved row once.
- AC-EMI-I01: Tests reject unequal arm candidate inventories.
- AC-EMI-I02: Reordered equal inputs produce equal signatures and fingerprints.
- AC-EMI-R01: Tests reproduce the preserved pairwise and batched benchmark metrics.
- AC-EMI-R02: A tracked verifier exits nonzero after one expected value changes.
- AC-EMI-R03: Reports record zero canonical writes.
- AC-EMI-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Gold loading: follow `event_entity_connection_stage_local.py`.
- Candidate contracts: follow `event_entity_connections.py`.
- Experiment composition: follow `run_event_entity_connection_experiment.py`.

## 11. Constraints and Halt Conditions

This TDD does not change model prompts or candidate construction.

This TDD does not assign semantic roles.

The proposition-scope experiment starts only after this report passes deterministic verification.

## 12. Implementation Evidence

The corrected verifier re-scored the three preserved development repetitions and the preserved
validation run directly from raw Gold and typed execution records without invoking a model.

All three development repetitions received the same candidate inventory.

Their strict aggregate metrics reproduced precision `0.352941`, recall `0.387097`, and F1
`0.369231`.

Their occurrence-level result fingerprints differed, proving that the historical identity-only
fingerprint had hidden decision drift.

The validation run reproduced strict precision `0.607843`, recall `0.645833`, and F1 `0.626263`.

The validation connected-sensitivity bound was precision `0.625`, recall `0.729167`, and F1
`0.673077`.

The tracked verifier is `scripts/verify_event_entity_measurement.py`.
