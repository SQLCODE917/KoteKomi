# TDD: Stanza Predicate-Argument Diagnostic

- Status: Complete
- Parent: [Event-Entity Connection Experiment](2026-09-12-event-entity-connection-experiment.md)
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Gold: `hsq-event-entity-connection-gold-v2.json`

## 1. Context & Problem

The Event-Entity Connection Experiment supplies every reviewed entity occurrence to Qwen.

The v6 replay proved that complete candidate availability does not produce reliable judgments.

The replay matched 21 of 47 development entities and 28 of 43 validation entities.

The replay also created 44 development extras and 20 validation extras.

KoteKomi already stores one pinned Stanza dependency trace for every selected SourceSegment.

KoteKomi has not measured how much Event-entity structure that trace exposes before semantic judgment.

**Predicate Anchor** means the Stanza token at the exact Event trigger head range.

**Entity Anchor** means the Stanza token that heads one exact entity occurrence.

**Dependency Path** means the ordered Stanza dependency edges between two anchors.

**Structural Hypothesis** means one deterministic interpretation of a Dependency Path.

**Semantic Remainder** means a source-valid pair whose Dependency Path does not justify a structural
hypothesis.

**Diagnostic Gap** means a typed failure to construct one exact anchor or Dependency Path.

### Primary Flow

1. The Pipeline loads the approved 40-case Gold catalog and canonical Event evidence.
2. The Pipeline reuses each persisted Stanza trace and constructs exact Event-entity candidates.
3. The Application Layer maps each Event trigger and entity occurrence to Stanza tokens.
4. The Application Layer records one Dependency Path and Structural Hypothesis per candidate.
5. The Pipeline compares those observations with Gold after analysis completes.
6. The Pipeline writes exact JSON and Markdown reports for development and validation.

The diagnostic writes derived experiment evidence only.

## 2. Goals

- An operator can inspect the exact dependency evidence for every Event-entity candidate.
- An operator can distinguish structural coverage from semantic-model work.
- An operator can measure structural precision and recall on development and validation separately.
- An operator can reproduce the same report without a model runtime.
- A later TDD can use the measured evidence to define a smaller semantic task.

## 3. Requirements

### Prepared Input

- PAD-I01: The Pipeline uses all 20 development Events and all 20 validation Events.
- PAD-I02: The Pipeline requires the approved v2 Event-entity Gold catalog.
- PAD-I03: The Pipeline loads the exact `EventTriggerDraft` for every source-grounded Event.
- PAD-I04: The Pipeline validates the trigger ID, source digest, expression, head, and character ranges.
- PAD-I05: The Pipeline reuses the existing completed `linguistic_analysis` trace.
- PAD-I06: The Pipeline validates the Stanza producer, model version, and resource identity.
- PAD-I07: The Pipeline creates no model task, ModelRun, ProposedChange, or accepted Ledger record.

### Dependency Analysis

- PAD-D01: The Application Layer maps the trigger head range to exactly one Predicate Anchor.
- PAD-D02: The Application Layer maps each primary entity span to one Entity Anchor.
- PAD-D03: The Application Layer chooses the entity token whose dependency head leaves the span.
- PAD-D04: The Application Layer records a Diagnostic Gap when PAD-D03 finds zero or multiple heads.
- PAD-D05: The Application Layer constructs the complete tree path between same-sentence anchors.
- PAD-D06: Every path edge records direction, dependency relation, and both token identities.
- PAD-D07: Every anchor and path token preserves its exact authoritative character range.
- PAD-D08: The Application Layer records a different-sentence Structural Hypothesis without a path.
- PAD-D09: The Application Layer records a Diagnostic Gap for an invalid or disconnected token tree.

### Structural Hypotheses

- PAD-H01: A direct core dependency produces `direct_argument`.
- PAD-H02: A core dependency plus coordination or apposition produces `coordinated_argument`.
- PAD-H03: A relative-clause antecedent path produces `relative_clause_argument`.
- PAD-H04: A predicate bridge plus an inherited core dependency produces `inherited_argument`.
- PAD-H05: A core dependency plus a nominal qualifier path produces `qualified_argument`.
- PAD-H06: Every other valid same-sentence path produces `semantic_remainder`.
- PAD-H07: A Structural Hypothesis remains derived evidence and does not decide Event involvement.

### Evaluation and Reports

- PAD-E01: The evaluator applies Gold labels after the Application Layer returns all observations.
- PAD-E02: The evaluator scores exact candidate occurrences before entity identity consolidation.
- PAD-E03: The evaluator reports expected structural matches and expected Semantic Remainders.
- PAD-E04: The evaluator reports implicit negatives that receive structural hypotheses.
- PAD-E05: The evaluator reports each Diagnostic Gap and its first failed mapping boundary.
- PAD-E06: The evaluator reports structural precision and recall by hypothesis class.
- PAD-E07: The evaluator reports the candidate count that a structural route could remove from Qwen.
- PAD-E08: The evaluator reports development and validation metrics separately.
- PAD-E09: The Markdown report shows exact input, exact output, expected result, and actual result.
- PAD-E10: The report records zero model executions and zero accepted Ledger writes.
- PAD-E11: Equal inputs produce byte-identical diagnostic observations and result fingerprints.

## 4. Proposed Architecture

```text
Approved Gold + canonical Event evidence
                    |
                    v
       Pipeline input preparation
                    |
                    v
   Application dependency analyzer
                    |
                    v
    Predicate-argument observations
                    |
                    v
       Pipeline Gold evaluator
                    |
                    v
        JSON + Markdown reports
```

The Pipeline owns canonical evidence loading and Gold evaluation.

The Application Layer owns source validation, token mapping, paths, and Structural Hypotheses.

Stanza supplies pinned linguistic evidence only.

## 5. Key Interactions

```text
Operator        Pipeline        Application Layer        Gold evaluator
   |                |                    |                      |
   | run diagnostic |                    |                      |
   |--------------->|                    |                      |
   |                | load 40 inputs     |                      |
   |                |------------------->|                      |
   |                |                    | map anchors + paths  |
   |                |                    |--------------------->|
   |                | observations       |                      |
   |                |<-------------------|                      |
   |                | compare after analysis ------------------>|
   |                |<------------------------- typed results   |
   |                | write reports       |                      |
   | report paths   |                    |                      |
   |<---------------|                    |                      |
```

## 6. Data Model

`PredicateArgumentToken` records one exact source token and its dependency facts.

`PredicateArgumentPathStep` records one directed dependency edge.

`PredicateArgumentObservation` records both anchors, the Dependency Path, and one result.

`PredicateArgumentCaseEvaluation` records Gold comparison for one Event and candidate occurrence.

`PredicateArgumentPhaseReport` records one complete development or validation result.

These records are derived experiment evidence.

The diagnostic stores no new canonical Domain Core record.

## 7. APIs / Interfaces

The diagnostic runner accepts a configuration path, coverage report ID, Gold path, and run root.

The runner writes `diagnostic.json`, `review.md`, `summary.json`, and `manifest.json`.

The runner exits zero when all 40 cases produce complete source-valid diagnostic evidence.

The summary exposes a separate `routing_hypothesis_supported` result.

That result is true only when both phases contain a Gold-positive structural match and no
Gold-negative structural match.

## 8. Behavior & Domain Rules

The analyzer receives no Gold expectation.

The evaluator cannot change an observation.

The analyzer preserves the complete Dependency Path even when it emits `semantic_remainder`.

The analyzer treats `different_sentence` as structural evidence from the existing routing policy.

The analyzer treats malformed deterministic input as an error.

The analyzer treats a valid structure that lacks one unique anchor as a Diagnostic Gap.

The diagnostic does not change the production Event-entity connection policy.

## 9. Acceptance Criteria

- AC-I01: A fixture run proves PAD-I01 through PAD-I07 for all 40 approved Events.
- AC-D01: Application tests prove PAD-D01 through PAD-D09 with exact source ranges.
- AC-H01: Application tests prove PAD-H01 through PAD-H07 with synthetic dependency trees.
- AC-E01: Pipeline tests prove PAD-E01 through PAD-E11 with data-in/data-out assertions.
- AC-E02: Two diagnostic runs over equal inputs produce equal observations and fingerprints.
- AC-E03: The final report identifies every expected structural miss and every structural extra.
- AC-E04: The final report proves zero model executions and zero accepted Ledger writes.

## 10. Reference Implementations

- Prepared input: follow `scripts/run_event_entity_connection_experiment.py`.
- Stanza mapping: follow `event_entity_linguistic_evidence_from_trace`.
- Gold evaluation: follow `event_entity_connection_stage_local.py`.
- Exact review output: follow the Event-entity connection experiment review.

## 11. Constraints and Halt Conditions

The diagnostic halts when the Gold catalog lacks approval.

The diagnostic halts when canonical evidence lacks one selected Event or Stanza trace.

The diagnostic records a failed routing hypothesis instead of changing production routing.

The next TDD can adopt structural routing only after this diagnostic reports its measured behavior.

## 12. Observed Result

The model-free diagnostic completed all 20 development and 20 held-out validation Events on
September 16, 2026.

It recorded zero model executions and zero accepted Ledger writes.

Two equal-input runs produced byte-identical `diagnostic.json`, `review.md`, `summary.json`, and
`manifest.json` files.

Development contained 177 exact candidate occurrences across 20 Events.

The dependency analyzer structurally covered 46 of 47 expected entity identities and classified the
remaining identity as Semantic Remainder.

At occurrence level it produced 61 Gold matches and 95 structural extras, for structural precision
of `0.3910`.

Held-out validation contained 115 exact candidate occurrences across 20 Events.

The analyzer structurally covered 36 of 43 expected entity identities and classified the remaining
seven as Semantic Remainders.

At occurrence level it produced 41 Gold matches and 40 structural extras, for structural precision
of `0.5062`.

Direct arguments were the strongest class: development produced 12 matches and zero extras, while
held-out validation produced 16 matches and two extras.

The two held-out extras expose the semantic limit of dependency distance alone.

`That month` is a temporal adjunct of `criticized`, and `Semafor` is the attribution source in
`According to Semafor`; neither is an Event participant even though each has a short direct path to
the predicate.

Coordination, inherited arguments, relative clauses, and qualified arguments also preserved useful
candidate evidence but produced substantial structural extras.

The diagnostic therefore falsifies structural auto-acceptance and broad structural removal of Qwen
work.

Its useful result is a narrower task boundary: deterministic syntax may describe and partition
candidate paths, while semantic judgment must still distinguish participants from temporal,
attribution, neighboring-clause, and other nonparticipant relations.
