# Source-Grounded Proposition Scope Experiment

- Status: Implemented through the mandatory human Gold-review gate
- Parent: [Event-Entity Measurement Integrity](2026-09-17-event-entity-measurement-integrity.md)
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)

## 1. Context & Problem

KoteKomi currently asks whether one entity belongs to one Event.

That question omits the proposition that gives the Event its complete source meaning.

The omission exposes Qwen to every entity in a SourceSegment.

The omission also makes attribution, negation, modality, purpose, comparison, and time easy to lose.

For example, the Source may state that Sacks attributed a regulatory strategy to Anthropic.

The proposition must retain `Sacks stated` with the attributed content.

The proposition cannot reduce that Source report to world truth about Anthropic.

**Proposition Fragment** means one ordered exact source range that contributes to one Event meaning.

**Source-Grounded Proposition Scope** means the complete ordered fragment set for one Event.

**Fragment Candidate** means one exact range that deterministic linguistic analysis offers for review.

**Candidate Gap** means deterministic evidence cannot represent one reviewed Proposition Fragment.

### Primary Flow

1. KoteKomi loads one approved source-grounded Event and its exact SourceSegment.
2. KoteKomi derives Fragment Candidates from pinned linguistic and entity evidence.
3. The Pipeline proves that the candidates can cover every reviewed Gold fragment.
4. KoteKomi retains the Event expression without model judgment.
5. Qwen judges one remaining Fragment Candidate with `Y`, `N`, or `U`.
6. KoteKomi maps each answer to the exact candidate and merges included ranges.
7. The Pipeline compares the Source-Grounded Proposition Scope with reviewed Gold.
8. The corrected Event-entity evaluator measures the scoped candidate inventory.

This experiment writes derived evidence only.

## 2. Goals

- An operator can inspect the exact source fragments that define each Event proposition.
- Event propositions preserve source attribution and qualification.
- Qwen answers one semantic membership question without constructing records or source ranges.
- KoteKomi measures candidate generation separately from model judgment.
- Held-out proposition scope reduces irrelevant entity candidates without losing expected entities.

## 3. Requirements

### Gold Contract

- SGP-G01: Proposition Gold binds approved Connection Gold and Trigger Gold by digest.
- SGP-G02: Proposition Gold contains twenty development and twenty validation Events.
- SGP-G03: Each Gold Event records ordered, non-overlapping exact Proposition Fragments.
- SGP-G04: Each Gold fragment replays byte-for-byte against its SourceSegment.
- SGP-G05: Gold preserves attribution, negation, modality, purpose, comparison, and time.
- SGP-G06: A human approves Proposition Gold before scored model execution.
- SGP-G07: The evaluator reads Gold fragments directly from Proposition Gold.

### Candidate Construction

- SGP-C01: KoteKomi consumes the existing Event trigger and pinned linguistic evidence.
- SGP-C02: KoteKomi validates every linguistic token against authoritative characters.
- SGP-C03: KoteKomi always proposes the exact Event expression.
- SGP-C04: KoteKomi proposes same-sentence exact entity occurrences.
- SGP-C05: KoteKomi proposes exact predicate-dependent subtrees.
- SGP-C06: KoteKomi proposes exact governing context outside the Event complement.
- SGP-C07: Governing context includes an attribution source and reporting predicate.
- SGP-C08: Candidate construction preserves coordination, control, and relative-clause evidence.
- SGP-C09: KoteKomi combines equal ranges and preserves every proposal reason.
- SGP-C10: KoteKomi records a Candidate Gap when candidates cannot cover one Gold fragment.

### Model Judgment

- SGP-M01: Qwen receives the complete authoritative SourceSegment.
- SGP-M02: Qwen receives one marked Event expression.
- SGP-M03: Qwen receives one marked Fragment Candidate.
- SGP-M04: Qwen receives no source offset or KoteKomi identifier.
- SGP-M05: Qwen answers exactly `Y`, `N`, or `U`.
- SGP-M06: `Y` means the fragment must remain to preserve the Event's complete source meaning.
- SGP-M07: `N` means the fragment belongs only to another proposition or incidental context.
- SGP-M08: `U` means the SourceSegment does not decide fragment membership.
- SGP-M09: One failed judgment leaves only that Fragment Candidate unresolved.

### Deterministic Scope

- SGP-S01: KoteKomi includes the Event expression deterministically.
- SGP-S02: KoteKomi maps each model answer to its supplied candidate.
- SGP-S03: KoteKomi merges included overlapping ranges.
- SGP-S04: KoteKomi preserves separated ranges as ordered Proposition Fragments.
- SGP-S05: Every merged fragment records its contributing candidate IDs.
- SGP-S06: A Source-Grounded Proposition Scope identifies its Event and SourceSegment digest.
- SGP-S07: The scope records `complete` only when every candidate has a terminal decision.
- SGP-S08: The scope contains no normalized paraphrase or entity role.

### Evaluation

- SGP-E01: Preflight reports Gold fragment coverage before model execution.
- SGP-E02: The report separates candidate-generation gaps from judgment errors.
- SGP-E03: The report measures exact fragment precision, recall, and character coverage.
- SGP-E04: The report measures required qualification-fragment recall.
- SGP-E05: The report measures expected entity occurrence retention.
- SGP-E06: The report replays scoped entities through corrected occurrence measurement.
- SGP-E07: Development uses three repetitions.
- SGP-E08: Validation uses one frozen held-out repetition.
- SGP-E09: Every report contains exact input, raw output, parsed answer, and mapped decision.
- SGP-E10: The experiment records zero ProposedChanges and zero accepted Ledger writes.

## 4. Proposed Architecture

```text
SourceSegment + Event + linguistic evidence
                    |
                    v
       Deterministic Candidate Builder
                    |
          +---------+---------+
          |                   |
          v                   v
   Gold Preflight       Fragment Candidates
                              |
                              v
                      Qwen Y / N / U
                              |
                              v
                  Deterministic Scope Builder
                              |
                              v
              Source-Grounded Proposition Scope
                              |
                              v
                      Pipeline Evaluator
```

The Application Layer owns candidate and scope construction.

The Pipeline owns Gold comparison and experiment reports.

The existing model runtime records bounded executions.

The Domain Core receives no new record.

## 5. Key Interactions

```text
Operator        Pipeline        Application Layer        Qwen
   |               |                    |                  |
   | run phase     |                    |                  |
   |-------------->| load Event         |                  |
   |               |------------------->| build candidates |
   |               |<-------------------|                  |
   |               | preflight Gold     |                  |
   |               |------------------->| one candidate    |
   |               |                    |----------------->|
   |               |                    | Y / N / U        |
   |               |                    |<-----------------|
   |               |<-------------------| build scope      |
   | report paths  | evaluate and write |                  |
   |<--------------|                    |                  |
```

## 6. Data Model

`PropositionFragmentCandidate` records one exact proposed source range and its proposal reasons.

`PropositionFragmentDecision` records one deterministic or model disposition.

`SourceGroundedPropositionFragment` records one selected merged exact range.

`SourceGroundedPropositionScope` records the ordered fragments for one Event.

`PropositionScopeCaseEvaluation` records one Event's Gold comparison.

`PropositionScopePhaseReport` records one complete development or validation result.

These records remain derived experiment evidence.

## 7. APIs / Interfaces

The candidate builder accepts source text, one Event trigger, one Event, linguistic evidence, and
Event-entity candidates.

The model task accepts one Fragment Candidate and returns one finite answer.

The scope builder accepts the complete candidate and decision inventories.

The Pipeline runner writes typed execution, report, review, and manifest files.

## 8. Behavior & Domain Rules

The Source-Grounded Proposition Scope preserves complete source meaning.

Attribution remains part of an attributed Event proposition.

Negation and modality remain part of the proposition they qualify.

Temporal language remains source text without temporal normalization.

One Source-Grounded Proposition Scope can contain multiple exact fragments.

Candidate overlap is evidence fusion, not duplicate meaning.

Classification under a governed Event vocabulary remains optional enrichment.

Semantic Argument Assignment starts after this experiment passes.

## 9. Acceptance Criteria

- AC-SGP-G01: Catalog tests prove exact 20/20 approved parent bindings.
- AC-SGP-G02: Catalog tests reject missing, overlapping, reordered, or changed fragments.
- AC-SGP-C01: Application tests cover attribution, coordination, control, and relative clauses.
- AC-SGP-C02: Application tests reject changed token and source digests.
- AC-SGP-M01: Parser tests accept only one exact `Y`, `N`, or `U` answer.
- AC-SGP-M02: Fake-Port tests preserve exact model input and raw output lineage.
- AC-SGP-S01: Scope tests prove deterministic inclusion and exact range merging.
- AC-SGP-S02: Scope tests preserve discontinuous fragments and unresolved decisions.
- AC-SGP-E01: Preflight covers every reviewed Gold fragment before model execution.
- AC-SGP-E02: Development and validation retain every required qualification fragment.
- AC-SGP-E03: Scoped evaluation retains every expected entity occurrence.
- AC-SGP-E04: Validation occurrence recall does not regress from the corrected baseline.
- AC-SGP-E05: Validation false positives decrease from the corrected baseline.
- AC-SGP-E06: Three development result fingerprints match.
- AC-SGP-E07: Reports record zero canonical writes.
- AC-SGP-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Exact linguistic evidence: follow `event_entity_predicate_arguments.py`.
- Bounded model execution: follow `event_entity_connection_preview.py`.
- Gold evaluation: follow `event_entity_connection_stage_local.py`.

## 11. Constraints and Halt Conditions

The Pipeline halts before model execution until a human approves Proposition Gold.

The Pipeline halts when candidate preflight cannot cover one required Gold fragment.

This TDD does not assign entity roles.

This TDD does not create a normalized CompleteProposition.

The next role TDD remains undefined until this experiment passes review.

## 12. Current Evidence and Required Human Boundary

The Application Layer now constructs exact Fragment Candidates, asks one finite `Y`, `N`, or `U`
question per non-Event candidate, preserves exact data-in/data-out traces, and constructs one typed
SourceGroundedPropositionScope without a normalized paraphrase or semantic role.

The attributed fixture preserves `Sacks stated` with `Anthropic was running a strategy` rather than
turning the attributed content into unqualified world truth.

The Pipeline now validates parent Gold, checks candidate coverage before model execution, scores
exact source characters, measures qualification and expected-entity retention, and writes typed
phase evidence with zero canonical writes.

The proposed 20/20 catalog is
[`hsq-source-grounded-proposition-gold-v1.json`](hsq-source-grounded-proposition-gold-v1.json).

The human-readable review is
[`hsq-source-grounded-proposition-gold-review-v1.md`](hsq-source-grounded-proposition-gold-review-v1.md).

The first development preflight observed 344 candidates over twenty Events and correctly blocked
model execution because the proposed sentence-bound Gold ranges were still unreviewed and all twenty
included source material outside the deterministic candidate coverage.

That result is a successful halt, not experiment acceptance.

A human must narrow or split each proposed range, approve the catalog, and rerun preflight before
Qwen execution is allowed.
