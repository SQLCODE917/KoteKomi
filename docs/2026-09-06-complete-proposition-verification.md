# TDD: Complete Proposition Verification

- Status: Implemented; resource-backed verification pending
- Deliverable ID: HSQ-3
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [HSQ-2 Monotonic Role Completion](2026-09-06-monotonic-role-completion.md)

## Context & Problem

HP-6 judges each frame and role statement separately.

Individually plausible statements can combine into one unsupported event.

The same Qwen runtime proposes and judges the semantics.

**NliObservation** means one non-authoritative entailment, contradiction, or neutral classification.

**CompleteProposition** means one deterministic sentence that includes the frame and all selected roles.

**PropositionDecision** means KoteKomi's typed admission result over Qwen and NLI evidence.

### Primary end-to-end flow

1. KoteKomi renders one CompleteProposition from one governed event.
2. Qwen judges the CompleteProposition against exact source text.
3. a DeBERTa NLI Adapter evaluates the same source and CompleteProposition.
4. KoteKomi records both observations and one PropositionDecision.
5. Only a supported PropositionDecision can enter ProposedChange construction.

## Goals

- A reviewer can inspect why a complete event passed or failed source support.
- An independent specialist challenges Qwen's support judgment.
- The Pipeline holds malformed combinations before human review.

## Requirements

### Domain Core

- CPV-DOM-01: A CompleteProposition binds one semantic event and exact deterministic text.
- CPV-DOM-02: An NliObservation records all three label scores and one selected label.
- CPV-DOM-03: A PropositionDecision records `supported` or `held` and one reason.

### Application Layer

- CPV-APP-01: A frame-specific deterministic renderer creates each CompleteProposition.
- CPV-APP-02: Qwen judges the complete proposition in one task.
- CPV-APP-03: The NLI Port receives the exact source premise and CompleteProposition hypothesis.
- CPV-APP-04: Admission requires direct Qwen support and calibrated NLI entailment.
- CPV-APP-05: Neutral, contradiction, low-confidence, or unavailable NLI evidence holds the proposition.

### Adapter

- CPV-ADP-01: The Adapter uses pinned `cross-encoder/nli-deberta-v3-base` resources.
- CPV-ADP-02: The Adapter loads resources from local storage only during ingestion.
- CPV-ADP-03: The Adapter returns typed scores without deciding admission.

## Proposed Architecture

```text
EventSemanticDraft
        |
        v
CompleteProposition
      /   \
     v     v
   Qwen   NLI Adapter
     \     /
      v   v
PropositionDecision
```

## Key Interactions

```text
Application -> Qwen: source plus CompleteProposition
Application -> NLI Adapter: source plus CompleteProposition
Qwen -> Application: SupportOutcome
NLI Adapter -> Application: NliObservation
Application -> Domain Core: PropositionDecision
```

## Data Model

The HybridEventSemanticsPreview stores CompletePropositions, NliObservations, and PropositionDecisions.

The Preview records the NLI Resource Installation identity.

## Behavior & Domain Rules

- CPV-RUL-01: NLI output remains derived evidence.
- CPV-RUL-02: NLI scores do not become confidence dimensions.
- CPV-RUL-03: Atomic support judgments remain diagnostic evidence.
- CPV-RUL-04: The development partition selects the NLI threshold before held-out evaluation.

## Acceptance Criteria

- AC-CPV-APP-01: A supported complete event receives two inspectable supporting observations.
- AC-CPV-APP-02: An event with individually supported but mismatched roles is held.
- AC-CPV-APP-03: NLI contradiction and neutral outcomes hold the event.
- AC-CPV-ADP-01: Adapter tests prove exact label mapping and local-only loading.
- AC-CPV-RUL-01: The existing HP-6 Gold events pass the calibrated gate.

## Reference Implementations

- Model resources: follow `packages/adapters/src/kotekomi_adapters/model_resources.py`.
- Bounded Qwen tasks: follow `packages/application/src/kotekomi_application/staged_model_extraction.py`.
