# Hybrid Semantic Quality Program

- Status: Implemented; resource-backed and canonical verification pending
- Program ID: `hybrid-semantic-quality`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Review basis: [Ingestion Architecture Review](2026-09-04-Ingestion-Architecture-Review.md)
- First deliverable: [HSQ-1 Governed Event Coverage](2026-09-06-governed-event-coverage.md)

## Context & Problem

The Hybrid Pipeline preserves exact source evidence and keeps model output out of accepted Ledger state.

Its current semantic stages still create avoidable review errors.

The governed event profile lacks common event families.

Role completion can replace a valid normalization assignment.

Atomic support judgments can approve parts of a malformed complete event.

Deterministic alias rules cannot resolve semantic references such as pronouns.

The standing-fact route admits event-like and argument-incomplete proposals.

This program improves those five boundaries without creating another extraction Pipeline.

### Terms

**CompleteProposition** means one deterministic sentence that represents one complete event or standing Assertion draft.

**PropositionDecision** means the combined Qwen and NLI evidence for one CompleteProposition.

**CoreferenceObservation** means one fallible specialist-model link between exact source spans.

**SemanticReferenceDecision** means KoteKomi's validated resolved, ambiguous, or unresolved reference result.

### Primary end-to-end flow

1. Qwen maps one source event to an expanded governed event profile.
2. KoteKomi preserves valid role assignments and completes only missing roles.
3. Qwen and an NLI challenger judge one CompleteProposition against exact source text.
4. A coreference proposer supplies source-span clusters for bounded semantic reference decisions.
5. KoteKomi admits only complete supported events and standing Assertions to human review.

## Goals

- A reviewer receives fewer malformed event and standing-Assertion proposals.
- A reviewer can inspect every semantic decision and its exact source evidence.
- The Pipeline retains every existing adjudicated correct event.
- The Pipeline resolves bounded references without inventing source identities.
- The Pipeline performs no network access during normal ingestion.

## Requirements

### Authority

- HSQ-AUT-01: The Archive and accepted DocumentRepresentationBundle remain source authority.
- HSQ-AUT-02: Models produce derived evidence only.
- HSQ-AUT-03: KoteKomi derives every source offset, identifier, digest, and record.
- HSQ-AUT-04: A reviewer remains the only actor that accepts model-derived intelligence.

### Delivery

- HSQ-DEL-01: Each deliverable is independently testable and revertable.
- HSQ-DEL-02: Each deliverable must preserve prior Gold behavior.
- HSQ-DEL-03: Each deliverable records exact stage input and output.
- HSQ-DEL-04: Each deliverable updates `docs/CHECK_PLAN.md`.

## Proposed Architecture

```text
DocumentRepresentationBundle
        |
        v
governed event normalization ----> selective role completion
        |                                  |
        +---------------+------------------+
                        v
              CompleteProposition
                        |
                 +------+------+
                 |             |
               Qwen       NLI challenger
                 |             |
                 +------+------+
                        v
             KoteKomi admission
                        |
              pending ProposedChange
```

The Application Layer owns every semantic admission rule.

Adapters expose NLI and coreference observations through Ports.

The Domain Core owns governed event meanings and typed decision records.

The Pipeline composes the existing Hybrid stages.

## Incremental Delivery

| Deliverable | User story | Precondition | Postcondition |
| --- | --- | --- | --- |
| [HSQ-1](2026-09-06-governed-event-coverage.md) | A reviewer sees criticism, publication, and rebuttal events without forced frame substitutions. | HP-6 emits governed event evidence. | The governed profile represents the adjudicated missing families. |
| [HSQ-2](2026-09-06-monotonic-role-completion.md) | A reviewer sees valid role assignments preserved through completion. | HSQ-1 defines the current governed frames. | Completion fills gaps without overwriting valid normalization output. |
| [HSQ-3](2026-09-06-complete-proposition-verification.md) | A reviewer sees only events whose complete meaning is source-supported. | HSQ-2 constructs complete governed events. | Qwen and NLI evidence qualify one CompleteProposition. |
| [HSQ-4](2026-09-06-bounded-semantic-reference-resolution.md) | A reviewer can trace bounded pronoun and nominal reference decisions. | Exact source spans and document references exist. | F-Coref supplies production-eligible observations that KoteKomi validates. |
| [HSQ-5](2026-09-06-standing-fact-semantic-admission.md) | A reviewer sees standing Assertions without flattened events or substituted arguments. | HSQ-3 and HSQ-4 expose proposition and reference decisions. | The standing-fact route admits only supported standing Assertions. |

## Behavior & Domain Rules

- HSQ-RUL-01: An unresolved governed meaning remains a gap.
- HSQ-RUL-02: A later model result cannot overwrite a valid earlier source-bound assignment.
- HSQ-RUL-03: A specialist score cannot become evidence confidence.
- HSQ-RUL-04: A coreference observation cannot create an Entity.
- HSQ-RUL-05: A bounded event uses an Event instead of a binary standing Assertion.
- HSQ-RUL-06: Existing derived previews become stale when their policy identity changes.

## Acceptance Criteria

- AC-HSQ-AUT-01: Tests prove no model or specialist output writes accepted Ledger state.
- AC-HSQ-DEL-01: Every TDD passes its focused Gold replay before the next TDD begins.
- AC-HSQ-DEL-02: Stage traces expose exact source input, raw output, parsed output, and admission result.
- AC-HSQ-RUL-01: The canonical Anthropic PDF produces source-aligned review candidates after all five deliverables.
- AC-HSQ-RUL-02: The Candidate Wiki excludes the adjudicated malformed Amodei proposals.

## Reference Implementations

- Stage evidence: follow `packages/application/src/kotekomi_application/extraction_stage_trace.py`.
- Model tasks: follow `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Model resources: follow `packages/adapters/src/kotekomi_adapters/model_resources.py`.
- Immutable previews: follow `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.

## Constraints and Halt Conditions

Stop one deliverable when it loses an existing adjudicated correct event.

Stop when a specialist dependency cannot run within the supported local hardware profile.

Stop when a model result would become accepted Ledger state without human review.
