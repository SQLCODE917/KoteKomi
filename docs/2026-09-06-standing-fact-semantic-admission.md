# TDD: Standing-Fact Semantic Admission

- Status: Corrective deterministic Event-boundary integration implemented; canonical verification pending
- Deliverable ID: HSQ-5
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [HSQ-4 Bounded Semantic Reference Resolution](2026-09-06-bounded-semantic-reference-resolution.md)

## Context & Problem

HP-10 validates source spans and candidate references before it creates standing-Assertion proposals.

It does not validate whether the complete binary proposition preserves source meaning.

It can therefore flatten events or substitute an incomplete subject.

**StandingFactQualification** means one semantic classification of a complete standing-Assertion proposition.

### Primary end-to-end flow

1. Qwen proposes one standing-Assertion draft.
2. KoteKomi validates source spans and references.
3. KoteKomi renders one CompleteProposition.
4. Qwen classifies the complete proposition.
5. The NLI Adapter challenges source entailment.
6. KoteKomi creates a ProposedChange only for a qualified standing Assertion.

## Goals

- A reviewer sees standing Assertions that preserve source participants and meaning.
- Event-like material remains in the Event route.
- Every held draft exposes one specific reason.

## Requirements

### Domain Core

- SFA-DOM-01: StandingFactQualification outcomes are `supported_standing_fact`, `event_not_standing`, `incomplete_or_wrong_arguments`, `unsupported`, and `ambiguous`.
- SFA-DOM-02: A StandingFactDecision records the qualification and proposition decision.

### Application Layer

- SFA-APP-01: KoteKomi renders the complete subject, predicate, and object proposition.
- SFA-APP-02: Qwen judges the complete proposition against exact source text.
- SFA-APP-03: The NLI Port evaluates the same source and proposition.
- SFA-APP-04: Admission requires `supported_standing_fact` and NLI entailment.
- SFA-APP-05: `event_not_standing` produces `event_route_required` without a standing ProposedChange.
- SFA-APP-06: An unresolved reference holds the draft.
- SFA-APP-07: An absent semantic subject holds the draft.
- SFA-APP-08: A standing draft over a SourceSegment with an explicit Event trigger is held as `event_route_required` before model qualification.

## Proposed Architecture

```text
StandingFactDraft
       |
       v
CompleteProposition
     /   \
    v     v
  Qwen   NLI
    \     /
     v   v
StandingFactDecision
       |
       v
eligible ProposedChange or typed hold
```

## Key Interactions

```text
Application -> Qwen: exact source plus standing proposition
Application -> NLI Adapter: exact source plus standing proposition
Application -> Domain Core: qualification and proposition evidence
Application -> review flow: eligible ProposedChange only
```

## Data Model

The StandingFactPlan stores each CompleteProposition and qualification record.

The plan retains held drafts and exact stage evidence.

## Behavior & Domain Rules

- SFA-RUL-01: A bounded event uses an Event record.
- SFA-RUL-02: A standing Assertion uses one complete subject-predicate-object meaning.
- SFA-RUL-03: Model agreement does not accept the Assertion into the Ledger.

## Acceptance Criteria

- AC-SFA-APP-01: The accurate `cut ties with` standing relation remains eligible.
- AC-SFA-APP-02: `urged associates to vote` does not become a binary Amodei-to-Harris standing Assertion.
- AC-SFA-APP-03: `Amodei's statement included views` does not substitute Amodei as subject.
- AC-SFA-APP-04: `effort executor` event material receives `event_route_required`.
- AC-SFA-APP-05: Every decision retains exact Qwen, NLI, source, and deterministic validation evidence.
- AC-SFA-APP-06: Qwen and NLI agreement cannot admit a binary Assertion that bypasses an Event discovered in the same source segment.

## Reference Implementations

- Standing plans: follow `packages/application/src/kotekomi_application/hybrid_standing_facts.py`.
- Complete proposition evidence: follow HSQ-3 records and Ports.
