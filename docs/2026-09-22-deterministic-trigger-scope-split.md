# TDD: Deterministic Trigger-Scope Split

- Status: Accepted
- Deliverable ID: D3
- Package: [Event Attribution Production Wiring](2026-09-22-event-attribution-wiring-package.md)
- Depends on: none

## Context & Problem

A source-grounded proposition can carry an outer attribution clause and an inner reported clause.
Example source: "According to Semafor, Trump officials chastised Anthropic's hiring."
The outer clause `According to Semafor` is the reporting carrier.
The inner clause `Trump officials chastised Anthropic's hiring` is the governed complement.
The proposition-scope experiment proved that losing either part loses source truth.
The current Event expression keeps the trigger and its evidence.
It does not deterministically separate the reporting carrier from the governed complement.
The gap is the missing model-free split.

**Reporting carrier** means the governing source clause that names who delivered the reported content.
**Governed complement** means the subordinate content clause that the reporting carrier reports.
**Trigger scope** means the exact source ranges of the reporting carrier and the governed complement.

### Primary Flow

1. KoteKomi loads one source-grounded Event and its pinned linguistic evidence.
2. KoteKomi finds the reporting predicate that governs the Event trigger.
3. KoteKomi bounds the reporting carrier from that predicate.
4. KoteKomi bounds the governed complement as the dependent content clause.
5. KoteKomi emits exact source ranges for both parts.
6. A proposition that yields only one part becomes a typed held result.

This deliverable produces derived state and invokes no model.

## Goals

- An operator inspects the reporting carrier and the governed complement separately.
- The split is deterministic and model-free.
- The split always preserves both the reporting carrier and the governed complement.
- A partial split becomes an explicit held result, never a merged proposition.

## Requirements

### Deterministic construction

- TSS-DET-01: The splitter invokes no model.
- TSS-DET-02: The splitter consumes pinned linguistic and dependency evidence.
- TSS-DET-03: The splitter uses exact authoritative source characters.

### Reporting carrier

- TSS-RC-01: The splitter identifies the governing reporting clause.
- TSS-RC-02: The splitter classifies the reporting predicate using the existing governed evidence.
- TSS-RC-03: The reporting carrier emits one exact source range.

### Governed complement

- TSS-GC-01: The splitter bounds the governed complement as the dependent content clause.
- TSS-GC-02: The governed complement emits one exact source range.
- TSS-GC-03: The governed complement retains its negation, modality, purpose, comparison, and time.

### Preservation

- TSS-PRV-01: The splitter never drops the reporting carrier.
- TSS-PRV-02: The splitter never drops the governed complement.
- TSS-PRV-03: A failed split returns a typed held result.
- TSS-PRV-04: A typed held result never becomes a merged proposition.

### Derived state

- TSS-DER-01: The split result is derived state.
- TSS-DER-02: The split result rebuilds from the Ledger and Archive.

## Proposed Architecture

```text
source-grounded Event
        +
pinned linguistic evidence
        |
        v
trigger-scope splitter
        |
        +--> reporting carrier
        |     (reporting governing clause)
        |
        +--> governed complement
              (dependent content clause)
        |
        +--> typed held result on failure
```

## Key Interactions

```text
Application -> Domain Core: parse SourceGroundedEventDraft
Application -> Domain Core: parse EventTriggerDraft
Application -> linguistic evidence: read dependency paths
Application -> Archive: publish the split result
```

## Data Model

No new Domain Core record exists.
The split result is a derived Application Layer value.
The split result carries two exact source ranges with their governing evidence.

## APIs / Interfaces

The splitter exposes one deterministic result carrying:

```text
reporting_carrier  = exact source range
governed_complement = exact source range
status              = complete or held
hold_reason        = typed reason when held
```

## Behavior & Domain Rules

- TSS-RUL-01: The splitter runs without a model call.
- TSS-RUL-02: The splitter never repairs an exact source range.
- TSS-RUL-03: The splitter never emits a proposition missing one part.
- TSS-RUL-04: The splitter publishes derived state only.
- TSS-RUL-05: The splitter feeds the D1 and D2 wiring and does not replace review.

## Acceptance Criteria

- AC-TSS-DET-01: The splitter produces one split result without a model call.
- AC-TSS-RC-01: `According to Semafor, Trump officials chastised Anthropic's hiring` splits with `According to Semafor` as the reporting carrier.
- AC-TSS-GC-01: The same source splits with `Trump officials chastised Anthropic's hiring` as the governed complement.
- AC-TSS-GC-02: `Sacks stated that Anthropic ran a sophisticated regulatory strategy` keeps `stated` content inside the governed complement.
- AC-TSS-PRV-01: A source with only a governed complement and no reporting clause returns a typed held result.
- AC-TSS-PRV-02: A held result never merges the two parts into one proposition.
- AC-TSS-DER-01: The split result rebuilds from the same Ledger and Archive inputs.
- AC-TSS-RUL-03: No split result emits a proposition missing one part.

## Reference Implementations

- Event governed semantics: `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.
- Deterministic proposition construction: `packages/application/src/kotekomi_application/source_grounded_proposition_scope.py`.
- Governed-complement path recognition: `packages/application/src/kotekomi_application/competitive_attachment_selection.py`.
- Trigger evidence: `packages/application/src/kotekomi_application/hybrid_event_triggers.py`.
- Gold taxonomy: `PropositionGoldFragmentRequirement` in `packages/pipelines/src/kotekomi_pipelines/source_grounded_proposition_stage_local.py`.

## Constraints and Halt Conditions

Halt if the reporting carrier cannot be identified without a model call.
Halt if the governed complement requires a new Domain Core record.
Halt if the split must change authoritative source characters.
Halt if a partial split tries to become a full proposition instead of a held result.