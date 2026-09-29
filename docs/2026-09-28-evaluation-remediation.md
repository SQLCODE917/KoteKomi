# TDD: Evaluation Remediation

- Status: Proposed
- Deliverable ID: `R5`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Depends on: [R4 Decontextualization Composition](2026-09-28-decontextualization-composition.md)
- Held-out partition: [Attachment Proposition Held-Out Annotation Packet](2026-09-24-attachment-proposition-held-out-annotation-packet.md)
- Transfer Gold: [Anthropic DoD Attachment Proposition Held-Out Gold](anthropic-dod-attachment-proposition-held-out-gold-v1.json)

## 1. Context & Problem

KoteKomi composes one source-grounded proposition through four stages.

R1 through R4 repair stages two and three.

R1 routes attachment with dependency syntax.

R3 turns the parser constituents into candidates and lets the local model only select among them.

R4 composes one content triple and attribution from the selected fragments.

Every R1-through-R4 decision shipped against development and validation evidence.

No deliverable measured transfer on a partition that never informed a decision.

The package therefore cannot yet claim transfer without selection.

The Competitive Event Attachment Program reserves an Independent held-out evaluation as CEA-5.

This package pulls that evaluation forward as its final deliverable.

A fresh Held-out partition now exists.

The human reviewed 53 Events of one Anthropic-DoD dispute Document.

That Gold carries `human_reviewed_held_out_gold` and a `development_overlap_count` of `0`.

R1 through R4 never read that partition.

R5 measures transfer on that partition.

R5 adds logprob capture to the model selection step.

R5 produces one error-type census.

R5 gates each error class instead of exact-set equality.

### Terms

**Held-out partition** means one authoritative Source Document that never informed a Competitive Event Attachment decision.

**Held-out Event** means one Event of the Held-out partition.

**Transfer** means measured quality on the Held-out partition without selection.

**Transfer Gold** means the reviewed Proposition Gold of the Held-out partition.

**Gold fragment** means one exact `fragments` entry of the Transfer Gold.

**Token Probability Evidence** means the runtime-reported token, natural-log probability, bytes, and alternatives for one output position.

**Selection Score** means the first-position natural-log probability for one allowed selection label.

**Censored selection label** means an allowed selection label that falls below the returned alternative-token inventory.

**Error type** means one named way a Held-out Event outcome disagrees with Transfer Gold.

**Error-type census** means one closed record that counts and lists every error type.

**Error-class gate** means a per-error-type accounting and listing gate; the exact-set score does not gate acceptance.

### Primary flow

1. The runner binds the frozen Transfer Gold, the fixture, and the pinned Stanza runtime by SHA-256.
2. The runner derives the Held-out triggers, entity connections, and one Constituent Candidate Inventory per Event without a model.
3. The local model returns one Constituent Selection per Event; the runner preserves Token Probability Evidence with every answer.
4. The composer builds one DecontextualizedProposition or one typed hold per Event.
5. The evaluator assigns one error type to each failing Event outcome and applies error-class gates.
6. The runner writes the transfer report and Markdown review with zero canonical writes.

## 2. Goals

- An operator can read one measured transfer result on a partition that never informed a decision.
- An operator can inspect every Held-out Event, Event meaning, composed proposition, and error type.
- An operator can distinguish one firm selection from one marginal selection by Selection Score.
- An operator can verify that no Held-out Event was used to tune a decision.
- An operator can verify that the exact-set score does not gate acceptance.

## 3. Requirements

### Frozen evidence

- R5-EVD-01: The runner binds the Transfer Gold `docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json` by its SHA-256 digest `3bbfd1bc76d3f78e8853e84303c47e46aa1d430ed3a5cc3b22391adceca4a270`.
- R5-EVD-02: The runner binds the fixture `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf` by its SHA-256 digest `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`.
- R5-EVD-03: The runner binds the representation `rep_e84869f6fcd4ed02c70a550a` and the source segment policy `paragraph_segment_v3`.
- R5-EVD-04: The runner binds the pinned Stanza runtime by its SHA-256 digest `4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3`.
- R5-EVD-05: The runner requires exactly 53 Held-out Events, each with `phase` equal to `held_out`.
- R5-EVD-06: The runner requires `development_overlap_count` equal to `0` and rejects a nonzero value.

### Deterministic Held-out derivation

- R5-DRV-01: The runner derives one Event trigger per Held-out Event from the pinned dependency tree, without a model.
- R5-DRV-02: The runner derives one entity connection per Held-out Event from the pinned dependency tree, without a model.
- R5-DRV-03: The runner derives one Constituent Candidate Inventory per Held-out Event, without a model.
- R5-DRV-04: Every derived constituent stays source-exact.
- R5-DRV-05: The derivation reads no Transfer Gold.
- R5-DRV-06: The runner freezes every derived input by digest before the model executes.

### Model selection with logprob capture

- R5-SEL-01: The runner renders one finite selection task per Held-out Event over that Event's Constituent Candidate Inventory.
- R5-SEL-02: The local model returns one Constituent Selection per task and never draws a span boundary.
- R5-SEL-03: The runner requests bounded top-alternative Token Probability Evidence for every selection execution.
- R5-SEL-04: The runner preserves the unmodified runtime alternatives in the execution receipt.
- R5-SEL-05: The runner records one Selection Score per allowed label, including a censored value for a missing label.
- R5-SEL-06: The model runs under the same pinned runtime and model identity as R3.

### Composition

- R5-COM-01: The composer builds one DecontextualizedProposition or one typed hold per Held-out Event from the Selected Constituent Set.
- R5-COM-02: The composer never invents a subject, object, or attribution target.
- R5-COM-03: A rejected, empty, or incomplete selection produces a typed hold.

### Error-type census

The census uses one closed error-type set over Transfer Gold fragments and meanings.

- R5-CEN-01: The evaluator counts a `boundary_miss` error when one Gold fragment has no exact-span constituent in the Event inventory.
- R5-CEN-02: The evaluator counts a `selection_error` when a covered Gold fragment is unselected or a selected constituent is not a Gold fragment.
- R5-CEN-03: The evaluator counts a `composition_hold` error when the Selected Constituent Set holds but the Gold fragments would compose.
- R5-CEN-04: The evaluator counts a `content_error` when a composed relation label, subject, or object disagrees with the `core_event`, `temporal`, or `purpose` Gold fragments.
- R5-CEN-05: The evaluator counts an `attribution_error` when the composed attribution kind or reporting carrier disagrees with the `attribution` Gold fragment.
- R5-CEN-06: The evaluator counts a `polarity_modality_error` when the composed polarity or modality disagrees with the `negation` or `modality` Gold fragment.
- R5-CEN-07: The evaluator counts `ok` for each Held-out Event with no error type.
- R5-CEN-08: The census lists the member Event IDs for every error type.

### Error-class gates

- R5-GAT-01: The report records the exact-set score and does not gate acceptance on it.
- R5-GAT-02: The report gates every error type on its own count and member list.
- R5-GAT-03: The report does not gate composition on exact string equality of an Event meaning.
- R5-GAT-04: The report lists every `boundary_miss` Gold fragment by fragment ID.

### Safety and report

- R5-SAF-01: The runner creates zero canonical Ledger writes.
- R5-SAF-02: The runner creates zero ProposedChanges.
- R5-SAF-03: The runner executes zero models during derivation, composition, and census phases.
- R5-SAF-04: No Gold fragment or Event meaning enters a model task.
- R5-SAF-05: The runner writes one transfer report and one Markdown review.

## 4. Proposed Architecture

```text
frozen Transfer Gold + fixture + pinned Stanza runtime
                |
                +--> deterministic Held-out derivation
                |      (trigger, entity connection, Constituent Candidate Inventory)
                v
        one finite selection task per Held-out Event
                |
                +--> local model + Token Probability Evidence
                v
        one DecontextualizedProposition or typed hold per Event
                |
                +--> error-type census
                v
        error-class gates -> transfer report + Markdown review
```

## 5. Key Interactions

```text
Runner    -> frozen bindings             : verify SHA-256 digests
Deriver   -> pinned Stanza tree          : trigger, entity connection, constituents
Renderer  -> Constituent Candidate Inventory : one finite selection task
Model     -> one Constituent Selection   : emission + Token Probability Evidence
Composer  -> Selected Constituent Set    : proposition or typed hold
Evaluator -> Transfer Gold               : one error type per failing Event
Runner    -> error-class gates           : transfer report + Markdown review
```

## 6. Data Model

`SelectionProbabilityReceipt` stores one Event ID, one model execution ID, and the unmodified runtime alternative inventory.

`SelectionScore` stores one allowed label, one first-position natural-log probability, and one censored flag.

`HeldOutErrorType` stores one of `boundary_miss`, `selection_error`, `composition_hold`, `content_error`, `attribution_error`, or `polarity_modality_error`.

`HeldOutErrorCensus` stores one count and one member list per `HeldOutErrorType`, plus one `ok` count.

`HeldOutTransferReport` stores the Held-out census, the Selection Scores, the exact-set score, one model execution count, and one canonical write count.

These records are derived evaluation evidence.

They do not change accepted Ledger state.

## 7. APIs / Interfaces

The runner exposes a `prepare` phase that binds and derives without a model.

The runner exposes an `execute` phase that runs one selection per Event with logprob capture.

The runner exposes a `score` phase that builds the error-type census without a model.

The runner exposes a `report` phase that applies error-class gates and writes the review.

The evaluator accepts the frozen Transfer Gold and typed Held-out outcomes and returns one `HeldOutErrorCensus`.

No record replaces a predecessor.

## 8. Behavior & Domain Rules

The Transfer Gold is the evaluation authority for the Held-out partition.

The runner compares attachments by exact source span, never by string similarity.

The runner compares composition against Gold fragments and meanings, never by exact string equality.

An Event can appear in more than one error-type member list.

The Selection Score is captured evidence and does not gate acceptance.

The Held-out partition is evaluated exactly once and never read to tune a decision.

The runner never sends a Gold fragment, Event meaning, or boundary byte into a model task.

The report records the exact-set score alongside the error-type census.

## 9. Acceptance Criteria

- AC-R5-EVD-01: Tests reject a changed Transfer Gold, fixture, representation, or Stanza digest.
- AC-R5-EVD-02: Tests reject a held-out catalog with a nonzero development overlap count.
- AC-R5-DRV-01: Tests prove trigger, entity connection, and inventory derivation produce no model execution.
- AC-R5-DRV-02: Tests reject a derived constituent that does not stay source-exact.
- AC-R5-SEL-01: Tests prove one bounded selection task per Held-out Event with no boundary byte in the task.
- AC-R5-SEL-02: Tests prove Token Probability Evidence preserves the unmodified runtime alternatives.
- AC-R5-SEL-03: Tests prove a censored Selection Score records for a missing label.
- AC-R5-CEN-01: Tests prove each error type counts and lists its member Events over a frozen fixture.
- AC-R5-CEN-02: Tests prove an Event with no error type counts as `ok`.
- AC-R5-GAT-01: Tests prove the exact-set score does not gate acceptance.
- AC-R5-GAT-02: Tests prove every `boundary_miss` Gold fragment lists by fragment ID.
- AC-R5-SAF-01: The report records zero canonical writes and zero ProposedChanges.
- AC-R5-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Event trigger derivation: `packages/application/src/kotekomi_application/hybrid_event_triggers.py`.
- Entity connection derivation: `packages/application/src/kotekomi_application/event_entity_connections.py`.
- Constituent derivation: `packages/application/src/kotekomi_application/source_grounded_proposition_scope.py`.
- Constituent selection and censuses: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py`.
- Decontextualization composition: `packages/application/src/kotekomi_application/decontextualization_composition.py`.
- Token Probability Evidence pattern: `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_calibration.py`.
- Runner pattern: `scripts/run_parser_constituent_candidate_generation.py` and `scripts/run_decontextualization_composition.py`.
- LM Studio runtime: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`.

## 11. Constraints and Halt Conditions

- Stop when the Held-out catalog changes from the frozen digest.
- Stop when one derived constituent cannot materialize to exact source characters.
- Stop when a Held-out Event lacks one trigger or one entity connection.
- Stop when the Held-out partition is read to tune a decision.
- Stop when a Gold fragment or Event meaning would enter a model task.
- Stop when any phase would write canonical intelligence.
- Stop when the exact-set score alone is used to gate acceptance.
