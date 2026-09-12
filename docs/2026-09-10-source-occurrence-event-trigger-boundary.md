# SourceOccurrence to Event Trigger Boundary

- Status: Accepted; implemented and experimentally verified
- Parent: [Bounded Semantic Task Allocation](2026-09-08-bounded-semantic-task-allocation.md)

## Context & Problem

KoteKomi must find each explicit Event in one authoritative SourceSegment.

The prior event task asked Qwen to find and serialize an open list of Event expressions.

That task omitted Events and returned invalid internal identifiers.

The prior task also asked one small model to discover candidates, interpret them, and map them.

This TDD assigns those jobs to bounded specialist, semantic, and deterministic components.

### Terms

**SourceOccurrence** is one ordered exact token-like range in a SourceSegment.

**LinguisticToken** is one fallible source-bound Stanza annotation.

**NominalizationCandidate** is one fallible source-bound QANom noun score.

**EventHeadCandidate** is one SourceOccurrence selected for semantic Event review.

**Candidate Disposition** explains KoteKomi's treatment of one SourceOccurrence.

**Semantic Route** is one bounded question about one EventHeadCandidate.

**Routing Judgment** binds one finite semantic answer to one KoteKomi-owned candidate.

**Event Trigger Decision** is KoteKomi's deterministic final decision for one candidate.

**EventTriggerDraft** is one derived Event head mapped to exact authoritative characters.

**Trigger Gold** is the reviewed complete Event inventory for one SourceSegment.

**Bounded Nominal Reference** has a determiner, number, possessive, or nominal complement.

### Primary Flow

1. KoteKomi derives an ordered SourceOccurrence catalog from one SourceSegment.
2. Stanza annotates grammar, and QANom proposes eventive nouns over the same characters.
3. KoteKomi validates both results and selects source-bound EventHeadCandidate records.
4. Qwen answers one bounded Semantic Route at a time with one finite answer.
5. KoteKomi reconciles the Routing Judgments and creates exact EventTriggerDraft records.
6. The stage evaluator compares those records with Trigger Gold and preserves full traces.

## Goals

- An operator can inspect the exact input and output for every semantic judgment.
- An operator can account for every SourceOccurrence and EventHeadCandidate.
- One malformed model answer cannot erase valid sibling evidence.
- Each EventTriggerDraft resolves to exact authoritative source characters.
- The development and validation splits reproduce their reviewed Event inventories exactly.
- Event discovery creates no ProposedChange or accepted Ledger record.

## Requirements

### Source Boundary

- SOB-01: The Application Layer derives SourceOccurrence records in source order.
- SOB-02: Each SourceOccurrence stores an exact half-open source range and local identity.
- SOB-03: Repeated text receives one SourceOccurrence per exact occurrence.
- SOB-04: The source map preserves Unicode characters without normalization.
- SOB-05: KoteKomi rejects an accepted range that differs from the SourceSegment.

### Specialist Analyzers

- SAN-01: The Application Layer defines LinguisticAnalyzer and NominalizationAnalyzer Ports.
- SAN-02: The Stanza Adapter uses the pinned English EWT model without network access.
- SAN-03: Stanza returns exact ranges, lemmas, universal parts of speech, and dependencies.
- SAN-04: The QANom Adapter uses its pinned classifier and lexical resources offline.
- SAN-05: QANom returns one source-bound score for every Stanza common noun.
- SAN-06: Each Adapter validates its output against exact SourceSegment characters.
- SAN-07: A missing, changed, or invalid Resource Installation blocks before Qwen runs.

### Candidate Policy

- ECP-01: KoteKomi includes each Stanza `VERB` except an `amod` or `case` dependent.
- ECP-02: KoteKomi includes a common noun only when QANom's lexical test passes.
- ECP-03: The included common noun must meet the pinned `0.45` QANom threshold.
- ECP-04: KoteKomi records one Candidate Disposition per SourceOccurrence.
- ECP-05: KoteKomi exposes unmatched and conflicting specialist output as a disposition.
- ECP-06: Candidate selection creates no source text, offset, or canonical identity.

### Semantic Routes

- ESR-01: The verb-role route answers `E`, `S`, or `H` for one marked verb.
- ESR-02: `E` means a particular occurrence expressed by the marked verb.
- ESR-03: `S` means a standing state or relationship.
- ESR-04: `H` means another expression carries the particular occurrence.
- ESR-05: The noun-inventory route answers `E` or `N` for one marked noun.
- ESR-06: `E` means the noun heads a particular occurrence in the sentence.
- ESR-07: Each remaining route answers exactly `Y` or `N`.
- ESR-08: Binary routes test similarity, dependent kind, media kind, distinctness, reaction, and standing state.
- ESR-09: Each invocation contains the sentence and exact marked expression.
- ESR-10: A two-target noun route contains one marked noun and its governing verb.
- ESR-11: The model-visible task contains no internal identity or linguistic annotation.
- ESR-12: Each prompt describes only its Semantic Route and finite answer vocabulary.
- ESR-13: Each invocation permits two output tokens for one finite answer.
- ESR-14: KoteKomi rejects every malformed, missing, or additional answer token.

### Deterministic Reconciliation

- DRC-01: KoteKomi evaluates noun candidates before verb candidates.
- DRC-02: A gerundive compound can represent its own Event.
- DRC-03: A support verb yields to its accepted direct-object Event noun.
- DRC-04: An inventory-rejected noun remains rejected by default.
- DRC-05: KoteKomi reconsiders it only as a direct object with a Bounded Nominal Reference.
- DRC-06: It requires negative dependent-kind, positive distinctness, and positive reaction judgments.
- DRC-07: KoteKomi rejects document, content, plan, media, and standing-state nouns.
- DRC-08: KoteKomi preserves bounded nominal Events used as temporal references.
- DRC-09: KoteKomi rejects an Event noun when a finite relative clause carries its occurrence.
- DRC-10: KoteKomi rejects a verb with an `S` role.
- DRC-11: KoteKomi suppresses an `H` verb only when a linked accepted noun corroborates it.
- DRC-12: KoteKomi retains an uncorroborated `H` verb as source-bound Event evidence.
- DRC-13: KoteKomi rejects a bare `have` proform without a content complement.
- DRC-14: KoteKomi rejects an `E` verb that expresses only standing similarity.
- DRC-15: KoteKomi records one final disposition and reason for every classified candidate.
- DRC-16: A failed Semantic Route leaves only its candidate unclassified.
- DRC-17: KoteKomi maps each accepted decision to the exact head characters.
- DRC-18: KoteKomi derives the diagnostic event label from the Stanza lemma.

### Trigger Gold

- TGL-01: Trigger Gold covers all twenty-six unique HSQ SourceSegments.
- TGL-02: Trigger Gold lists all reviewed explicit Events in each SourceSegment.
- TGL-03: Each Gold Event stores one exact head and at least one accepted expression range.
- TGL-04: Trigger Gold marks an Event-free SourceSegment explicitly.
- TGL-05: A human approves Trigger Gold before KoteKomi freezes its digest.
- TGL-06: One SourceSegment digest occurs in only one evaluation phase.

### Stage Evaluator

- STE-01: The Pipeline reuses one result for Gold items from the same SourceSegment.
- STE-02: The Pipeline consumes manifest-authorized upstream evidence without rerunning it.
- STE-03: The evaluator matches actual and Gold Events one-to-one by exact ranges.
- STE-04: The report counts missing, extra, duplicate, failed, and unclassified outcomes.
- STE-05: The report records exact head and expression accuracy.
- STE-06: Each trace preserves exact task input, raw output, parsed answer, and lineage.
- STE-07: The report accounts for every source occurrence, candidate, and model execution.
- STE-08: The evaluator records zero ProposedChanges and zero accepted Ledger writes.
- STE-09: The finalizer requires complete trigger evidence for every prepared SourceSegment.

## Proposed Architecture

```text
authoritative SourceSegment
          |
          v
SourceOccurrence builder
          |
          v
Stanza + QANom Adapters
          |
          v
Application candidate policy
          |
          v
bounded Qwen Semantic Routes
          |
          v
deterministic reconciler --> EventTriggerDraft + stage traces
```

The Application Layer owns source validation, candidate policy, routing, and reconciliation.

The Adapters expose fallible source-bound observations through Application Layer Ports.

The Pipeline composes immutable stage-local runs and evaluates their derived evidence.

## Key Interactions

```text
Pipeline       Application       Specialists       Qwen       Evaluator
   |                |                 |               |             |
   |-- segment ---->|                 |               |             |
   |                |-- analyze ---->|               |             |
   |                |<-- annotations-|               |             |
   |                |-- one route ------------------>|             |
   |                |<-- finite answer --------------|             |
   |                |-- reconcile                    |             |
   |<-- drafts -----|                                 |             |
   |-------------------------------------------------------------> Gold
   |<----------------------------------------------------------- report
```

## Data Model

`SourceOccurrence` already records one exact source token-like range.

`LinguisticAnalysis` stores one immutable Stanza observation set.

`NominalizationAnalysis` stores one immutable QANom observation set.

`EventHeadCandidateSelection` stores candidates and complete Candidate Dispositions.

`EventRoutingJudgment` stores one validated finite answer and execution lineage.

`EventTriggerDecision` stores one deterministic decision and reason.

`EventTriggerDraft` stores exact source ranges and derived diagnostic labeling.

`HybridEventTriggerPreview` stores terminal derived evidence and complete stage traces.

These records remain disposable derived evidence in the Archive.

## APIs / Interfaces

The stage-local runner provides `prepare`, `run-triggers`, `finalize`, and `compare` commands.

`prepare --upstream-run-root` validates and copies only manifest-authorized parent evidence.

Validation preparation requires the parent run's valid `FINALIZED` marker.

`run-triggers` writes one result per unique SourceSegment digest.

`finalize` validates complete execution evidence before it writes evaluation reports.

`compare` joins development and validation summaries without changing either run.

## Behavior & Domain Rules

- BDR-01: A zero-candidate SourceSegment completes without a model execution.
- BDR-02: A valid sibling decision survives one malformed model answer.
- BDR-03: An invalid model answer cannot become an implicit non-Event decision.
- BDR-04: A partial Preview names each unclassified candidate.
- BDR-05: A blocked Preview contains diagnostics and no EventTriggerDraft.
- BDR-06: Trigger evaluation cannot create a ProposedChange or accepted Ledger record.
- BDR-07: Specialist annotations remain fallible derived observations.
- BDR-08: A diagnostic event label does not assert ontology conformance.
- BDR-09: This Gold corpus measures current bounded-corpus behavior, not generalization.

The final fresh replay produced these results on September 12, 2026.

- Development returned all 50 Gold Events across 12 SourceSegments exactly.
- Validation returned all 37 Gold Events across 14 SourceSegments exactly.
- Both phases had zero missing, extra, duplicate, failed, or unclassified outcomes.
- Development used 162 Qwen executions and 306,216 model milliseconds.
- Validation used 142 Qwen executions and 269,968 model milliseconds.

The validation split participated in iterative diagnosis before final acceptance.

A later program increment must use a new independently reviewed corpus to test generalization.

## Acceptance Criteria

- AC-SOB-01: Tests prove exact ordered Unicode ranges and repeated-text identities.
- AC-SAN-01: Port and Adapter tests prove exact Stanza and QANom mappings.
- AC-SAN-02: Tests prove changed or missing Resource Installations block before Qwen runs.
- AC-ECP-01: Tests prove complete candidate and disposition coverage.
- AC-ECP-02: Both Gold phases report 100 percent Gold candidate recall.
- AC-ESR-01: Tests inspect exact input and raw output for every Semantic Route.
- AC-ESR-02: Tests prove each finite answer parser rejects additional content.
- AC-ESR-03: Tests prove every route requests exactly two output tokens.
- AC-DRC-01: Tests prove every deterministic reconciliation rule.
- AC-DRC-02: Tests prove a general topic noun cannot displace its evaluation verb.
- AC-DRC-03: Tests prove a Bounded Nominal Reference can preserve a distinct Event.
- AC-DRC-04: Tests prove one failed route preserves valid sibling evidence.
- AC-TGL-01: Catalog tests prove approved, digest-locked, disjoint phase coverage.
- AC-STE-01: Tests prove immutable upstream evidence rehydration and source-level reuse.
- AC-STE-02: Both fresh phase reports match all 87 Gold Events exactly.
- AC-STE-03: Both fresh phase reports contain complete data-in and data-out traces.
- AC-STE-04: Both fresh phase reports record zero canonical state changes.

## Reference Implementations

- Application use case: `packages/application/src/kotekomi_application/hybrid_event_trigger_preview.py`.
- Domain DTOs: `packages/application/src/kotekomi_application/hybrid_event_triggers.py`.
- Stanza Adapter: `packages/adapters/src/kotekomi_adapters/stanza_linguistic_analysis.py`.
- QANom Adapter: `packages/adapters/src/kotekomi_adapters/qanom_nominalization.py`.
- Stage runner: `scripts/run_hsq7_stage_local.py`.
- Gold catalog: `docs/hsq-event-trigger-gold-v1.json`.

## Constraints and Halt Conditions

Stop if Qwen must invent source text, offsets, or KoteKomi identities.

Stop if trigger work changes frame selection or a later extraction stage.

Stop if one SourceSegment digest crosses evaluation phases.

Stop if a specialist annotation becomes source authority or accepted Ledger state.

Stop if event discovery creates a ProposedChange or accepted Ledger record.
