# TDD: Event-Entity Connection Experiment

- Status: Accepted; implementation in progress
- Parent: [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md)
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Gold: `hsq-event-entity-connection-gold-v1.json`

## 1. Context & Problem

KoteKomi now creates one source-grounded Event for each approved Event trigger.

The base Event contains no Actor or Organization connections.

The former role task requires a governed frame before it selects an entity.

That requirement drops source-grounded Events that lack a governed classification.

The former task also asks Qwen to interpret a frame, select a role, and select source text.

This TDD tests one smaller semantic question before KoteKomi adopts a production contract.

**Event-Entity Connection Candidate** means one KoteKomi-owned pair of one Event and one entity.

**Entity Involvement Judgment** means one `Y`, `N`, or `U` answer about that pair.

**Event-Entity Connection Draft** means one derived source-backed positive connection.

**Connection Gold** means the complete reviewed entity inventory for selected Events.

**Contextual Exclusion** means an exact source expression that must not become an Actor or
Organization candidate for the selected Event because it denotes another contextual kind.

An entity is involved when the Event expression makes that entity part of what happened.

This meaning includes an entity whose approach, statement, work, or decision is involved.

It does not assert a semantic role for the entity.

### Primary Flow

1. The Pipeline loads reviewed source-grounded Events and their upstream extraction evidence.
2. KoteKomi constructs Event-Entity Connection Candidates from effective entity mentions.
3. KoteKomi proves that every reviewed Gold entity is available as a candidate and that no typed
   candidate gap remains.
4. Qwen judges one Event-Entity Connection Candidate with one finite answer.
5. KoteKomi maps each answer to a typed disposition.
6. KoteKomi constructs Event-Entity Connection Drafts for `Y` answers.
7. The evaluator compares the complete result with Connection Gold.

This flow writes derived experiment evidence only.

## 2. Goals

- An operator can inspect every entity considered for one Event.
- An operator can inspect the exact input and output for every model judgment.
- The experiment preserves source-grounded entity involvement without governed frames.
- The development and validation sets reproduce their complete reviewed inventories.
- The experiment identifies a production contract without changing accepted Ledger state.

## 3. Requirements

### Candidate Construction

- EEC-C01: KoteKomi consumes approved source-grounded Events.
- EEC-C02: KoteKomi consumes existing MentionCandidates and ReferenceDecisions.
- EEC-C03: KoteKomi selects only effective Actor and Organization MentionCandidates.
- EEC-C04: KoteKomi treats a government Actor expression as an Organization candidate.
- EEC-C05: KoteKomi resolves one candidate through one resolved ReferenceDecision.
- EEC-C06: KoteKomi preserves the source mention and resolved antecedent evidence.
- EEC-C07: KoteKomi creates one candidate for each distinct Event and entity identity.
- EEC-C08: KoteKomi preserves every source mention that supports a deduplicated candidate.
- EEC-C09: KoteKomi validates every range against authoritative SourceSegment characters.
- EEC-C10: An ambiguous entity type produces a typed candidate gap.
- EEC-C11: An ambiguous or unresolved reference produces a typed candidate gap.
- EEC-C12: An exact expression used as an Event does not become an Actor or Organization merely
  because the same name can identify an Organization elsewhere.

### Model Judgment

- EEC-M01: Qwen receives one Event-Entity Connection Candidate per invocation.
- EEC-M02: Qwen receives the complete authoritative SourceSegment.
- EEC-M03: Qwen receives one marked Event expression.
- EEC-M04: Qwen receives one marked entity expression.
- EEC-M05: Qwen receives the resolved antecedent text for a resolved reference.
- EEC-M06: The model-visible input contains no KoteKomi identifier or source offset.
- EEC-M07: Qwen returns exactly one answer from `Y`, `N`, or `U`.
- EEC-M08: `Y` means the entity forms part of the Event meaning.
- EEC-M09: `N` means the SourceSegment excludes the entity from that Event meaning.
- EEC-M10: `U` means the SourceSegment does not decide the question.
- EEC-M11: KoteKomi rejects malformed or additional model output.
- EEC-M12: One failed judgment leaves only its candidate unresolved.

### Deterministic Reconciliation

- EEC-R01: KoteKomi maps `Y` to `connected`.
- EEC-R02: KoteKomi maps `N` to `not_connected`.
- EEC-R03: KoteKomi maps `U` to `unresolved`.
- EEC-R04: KoteKomi creates an Event-Entity Connection Draft only for `connected`.
- EEC-R05: Each draft identifies its Event and entity identity.
- EEC-R06: Each draft identifies all supporting mention and reference records.
- EEC-R07: Each draft identifies the exact Event EvidenceTargets and exact entity source spans.
- EEC-R08: Each draft identifies its ModelRun and ExtractionStageTrace.
- EEC-R09: A draft contains no frame, frame role, or UpperRole.
- EEC-R10: Reconciliation derives every identifier and EvidenceTarget deterministically.

### Experiment Evidence

- EEC-E01: Connection Gold references the approved Event Trigger Gold digest.
- EEC-E02: Connection Gold contains twenty development Events.
- EEC-E03: Connection Gold contains twenty validation Events.
- EEC-E04: Each Gold Event records its complete expected Actor and Organization inventory.
- EEC-E04A: Every accepted source expression exists byte-for-byte in the selected Event's exact
  authoritative SourceSegment; normalized names and aliases belong only in the accepted entity-name
  inventory.
- EEC-E05: Gold can record an exact source expression as a contextual exclusion with its observed
  non-Actor/Organization kind and rationale.
- EEC-E05A: Preflight and final evaluation fail when an Actor or Organization candidate uses a
  contextually excluded expression.
- EEC-E05B: Every other eligible same-segment Actor or Organization is an implicit negative for the
  selected Event.
- EEC-E06: A human approves Connection Gold before any scored model replay.
- EEC-E06A: Preparation compares every expected Gold entity with the candidates supplied by
  immutable upstream evidence.
- EEC-E06B: A missing expected candidate or typed candidate gap produces `upstream_blocked` before
  Qwen runs.
- EEC-E06C: The preflight report preserves the exact SourceSegment, expected entities, actual
  candidate inventory, and typed gaps.
- EEC-E07: The evaluator matches expected and actual entities one-to-one.
- EEC-E08: The report counts missing, extra, wrong, and unresolved connections.
- EEC-E09: Each execution record preserves exact input, raw output, parsed output, and disposition.
- EEC-E10: Three development repetitions produce identical results.
- EEC-E11: The validation run uses one frozen prompt, policy, and runtime configuration.
- EEC-E12: Validation results cannot change the approved Gold or frozen policy.
- EEC-E13: The evaluator writes no ProposedChange or accepted Ledger record.

## 4. Proposed Architecture

```text
source-grounded Event + EventMention
                 |
MentionCandidates + ReferenceDecisions
                 |
                 v
   deterministic candidate builder
                 |
                 v
      one Event-entity pair
                 |
                 v
       bounded Qwen judgment
                 |
                 v
     deterministic reconciler
                 |
                 v
 Event-Entity Connection Draft + trace
```

The Application Layer owns candidate construction and reconciliation.

The ModelRuntime Port supplies one bounded semantic judgment.

The Pipeline owns stage-local composition and Gold evaluation.

## 5. Key Interactions

```text
Pipeline       Application       Qwen       Evaluator
   |                |              |             |
   |-- evidence --->|              |             |
   |                |-- one pair ->|             |
   |                |<-- Y/N/U ----|             |
   |                |-- reconcile  |             |
   |<-- drafts -----|              |             |
   |-------------------------------------------> Gold
   |<----------------------------------------- report
```

## 6. Data Model

`EventEntityConnectionCandidate` stores one Event and entity pair with source lineage.

`EntityInvolvementJudgment` stores one finite answer and model execution lineage.

`EventEntityConnectionDecision` stores one deterministic terminal disposition.

`EventEntityConnectionDraft` stores one positive source-backed connection.

`EventEntityConnectionPreview` stores complete derived stage evidence.

These records remain derived experiment evidence in the Archive.

## 7. APIs / Interfaces

The stage-local runner provides `prepare`, `run`, `finalize`, and `compare` commands.

`prepare` validates manifest-authorized upstream Event, mention, and reference evidence.

It writes a candidate preflight and returns `gold_review_required`, `upstream_blocked`, or
`prepared` without invoking Qwen.

`run` writes one result for each selected source-grounded Event.

`finalize` validates complete execution evidence and writes the Gold report.

`compare` joins development and validation reports without changing either run.

## 8. Behavior & Domain Rules

- EEC-B01: The experiment does not populate Event participant fields.
- EEC-B02: The experiment does not create a Relationship or Assertion.
- EEC-B03: The exact Event expression preserves source phenomenology.
- EEC-B04: An Event-Entity Connection Draft expresses involvement, not a semantic role.
- EEC-B05: The former governed role route remains an optional comparison baseline.
- EEC-B06: A validation failure leaves the production contract unproven.
- EEC-B07: Validation evidence cannot become new development evidence in this TDD.

## 9. Acceptance Criteria

- AC-EEC-C01: Tests prove candidate ranges replay exact authoritative characters.
- AC-EEC-C02: Tests prove candidate deduplication preserves all source evidence.
- AC-EEC-C03: Tests prove reference ambiguity produces a typed gap.
- AC-EEC-C04: Tests prove an Event-denoting expression is explicitly absent from Actor and
  Organization candidates.
- AC-EEC-M01: Fake-Port tests prove each invocation contains one Event and one entity.
- AC-EEC-M02: Parser tests accept only one `Y`, `N`, or `U` token.
- AC-EEC-R01: Tests prove only `Y` creates an Event-Entity Connection Draft.
- AC-EEC-R02: Tests prove every draft has complete source and execution lineage.
- AC-EEC-E01: Catalog tests prove Connection Gold contains twenty Events per phase.
- AC-EEC-E01A: Tests prove preflight attributes a missing expected entity to upstream evidence.
- AC-EEC-E01B: The runner cannot invoke Qwen before Gold approval and a passing preflight.
- AC-EEC-E01C: Catalog loading fails when any accepted source expression is absent from its exact
  SourceSegment.
- AC-EEC-E02: Development and validation reports contain no missing or extra connections.
- AC-EEC-E03: Development and validation reports contain no wrong connections.
- AC-EEC-E04: Development and validation reports contain no unresolved connections.
- AC-EEC-E05: Three development repetitions have identical content fingerprints.
- AC-EEC-E06: Tests prove the evaluator writes no canonical state.

### Implementation State

The Application contracts, bounded model task, deterministic reconciliation, stage-local evaluator,
and experiment runner are implemented.

A refreshed read-only preparation replay against canonical coverage report
`hdc_531970a43dc9a886c345846b` found all twenty development Events.

That preparation retained 99 upstream mention instances, constructed 84 distinct Event-entity
candidates, and preserved five typed candidate gaps without rerunning mention, reference, or Event
extraction.

A deterministic pre-model comparison against the proposed Gold initially found thirteen expected
development entities that upstream evidence could not supply.

Human review established that the World Economic Forum denotes its gathering in the reviewed
attendance context rather than the Organization.

Review also added Joe Biden to the two Events involving his Executive Order while preserving him as
an implicit negative for the separate discussions Event.

Human review later rejected TGE-020 as a standalone source-grounded Event because the source embeds
attendance under TGE-019's decision without establishing that attendance occurred or will occur.
The experiment removed TGE-020 and replaced it with approved source-grounded Event TGE-054 to retain
the twenty-Event development partition.
Human review approved TGE-054's three-Organization inventory.
TGE-019 now includes Trump because his inauguration is the stated alternative in Amodei's decision.
Human review approved the changed TGE-019 inventory.

Human review also rejected TGE-010 as a standalone source-grounded Event.
The phrase `ahead of the 2024 presidential election` supplies anticipated temporal context without
establishing that the election occurred.
The experiment removed TGE-010 and selected approved source-grounded Event TGE-060 to retain the
twenty-Event validation partition.
Human review approved TGE-060's Anthropic inventory.

The last preflight before the exact TGE-019 expression correction evaluated 42 expected entities,
found 32 available, and preserved both contextual exclusions without a violation. It left ten
provisional missing entities plus five typed candidate gaps. All three TGE-054 entities were
available.

The exact TGE-019 correction changed its source-grounded Event identity. Current preparation now
halts before Qwen because the September 12 canonical evidence contains only the superseded
`decision`-named Event. The current Gold contains 43 expected entities, but their availability cannot
be evaluated until a fresh trigger and source-grounded replay precedes the next connection preflight.

An exact-source audit found twenty-six accepted source expressions across nineteen Events that were
normalized aliases, expanded names, possessive variants, or normalized PDF whitespace rather than
literal substrings of their authoritative SourceSegments. The Gold catalog and its human review copy
now preserve only literal source expressions in `accepted_source_texts`; normalized identity aliases
remain separately in `accepted_entity_names`. Catalog loading enforces this boundary and the corrected
catalog has zero absent accepted source expressions.

Focused contract tests pass.

Human review approved all forty Connection Gold Events on September 13, 2026.

A fresh trigger and source-grounded replay must precede the next connection preflight.
Three development model repetitions and one frozen validation replay then remain before this TDD can
establish a production contract.

## 10. Reference Implementations

- Event grounding: follow `packages/application/src/kotekomi_application/source_grounded_events.py`.
- Bounded judgments: follow `packages/application/src/kotekomi_application/hybrid_event_trigger_preview.py`.
- Stage evaluation: follow `packages/pipelines/src/kotekomi_pipelines/event_trigger_stage_local.py`.
- Stage runner: follow `scripts/run_hsq7_stage_local.py`.

## 11. Constraints and Halt Conditions

The TDD halts before model execution when Connection Gold lacks human approval.

The TDD returns `upstream_blocked` before model execution when an expected entity is unavailable or
an upstream candidate gap remains.

The experiment records that upstream failure instead of repairing it in this boundary.

The TDD halts when validation differs from Connection Gold.

The next TDD can integrate only an experimentally verified connection contract.
