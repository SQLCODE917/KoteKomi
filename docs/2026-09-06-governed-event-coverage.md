# TDD: Governed Event Coverage

- Status: Implemented; focused verification complete
- Deliverable ID: HSQ-1
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [HP-6 Qualified Event Semantics](2026-09-02-qualified-event-semantics-source-support.md)

## Context & Problem

The current governed profile contains seven event frames.

Qwen therefore maps unsupported event families to nearby frames or returns a gap.

The canonical Anthropic source exposed missing criticism, publication, and rebuttal meanings.

**Criticism** means one party communicates a negative judgment about a target.

**Publication** means one party makes a work available.

**Rebuttal** means one party challenges a claim.

### Primary end-to-end flow

1. Qwen detects each literal event trigger in one source segment.
2. Qwen selects one supplied governed frame for each trigger.
3. KoteKomi validates every role target against authoritative source characters.
4. KoteKomi emits one event or one explicit unmapped-frame gap.

## Goals

- A reviewer sees criticism, publication, and rebuttal as distinct event meanings.
- A reviewer sees separate events for separate source triggers.
- Existing governed event behavior remains available.

## Requirements

### Domain Core

- GEC-DOM-01: The governed profile uses identity `hybrid_event_semantics_v2`.
- GEC-DOM-02: The profile defines `criticism` with required `critic` and `target` roles.
- GEC-DOM-03: The `criticism` frame defines optional `reason` and `topic` roles.
- GEC-DOM-04: The profile defines `publication` with required `publisher` and `published_work` roles.
- GEC-DOM-05: The `publication` frame defines optional `topic` and `audience` roles.
- GEC-DOM-06: The profile defines `rebuttal` with required `rebutter` and `challenged_claim` roles.
- GEC-DOM-07: The `rebuttal` frame defines optional `claim_source` and `medium` roles.

### Application Layer

- GEC-APP-01: The normalization task supplies every governed frame and role.
- GEC-APP-02: The Application Layer emits separate events for separate triggers.
- GEC-APP-03: The Application Layer records an unmapped-frame gap for an unsupported family.

## Proposed Architecture

```text
EventTriggerDraft
      |
      v
governed profile v2
      |
      v
EventSemanticDraft or SemanticCoverageGap
```

## Key Interactions

```text
Application -> Qwen: source trigger plus governed frames
Qwen -> Application: selected frame and role targets
Application -> Domain Core: validate frame and roles
Domain Core -> Application: governed EventSemanticDraft
```

## Data Model

The existing `EventFrameDefinition` and `FrameRoleDefinition` records remain the contract.

The profile adds the three frames and changes its identity to version 2.

## APIs / Interfaces

The Application Layer exports `HYBRID_EVENT_SEMANTICS_V2` as the current profile.

Existing derived version-1 previews must rebuild from their authoritative parents.

## Behavior & Domain Rules

- GEC-RUL-01: One trigger maps to at most one governed frame.
- GEC-RUL-02: One governed event retains its literal trigger.
- GEC-RUL-03: The Pipeline does not use a catch-all event frame.

## Acceptance Criteria

- AC-GEC-DOM-01: Domain tests prove the complete version-2 frame and role inventory.
- AC-GEC-APP-01: The Amodei `criticized` case produces a criticism event.
- AC-GEC-APP-02: The `published` and `rebuffing` case produces two events.
- AC-GEC-APP-03: The seven HP-6 Gold events retain their governed meanings.
- AC-GEC-RUL-01: An unknown event family produces an unmapped-frame gap.

## Reference Implementations

- Governed profile: follow `packages/domain/src/kotekomi_domain/hybrid_event_ontology.py`.
- Event construction: follow `packages/application/src/kotekomi_application/hybrid_event_semantics_preview.py`.
