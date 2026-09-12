# Hybrid Semantic Quality Program

- Status: Corrective semantic closure in progress
- Program ID: `hybrid-semantic-quality`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Review basis: [Ingestion Architecture Review](2026-09-04-Ingestion-Architecture-Review.md)
- First deliverable: [HSQ-1 Governed Event Coverage](2026-09-06-governed-event-coverage.md)
- Current front-half deliverable: [HSQ-7 Bounded Semantic Task Allocation](2026-09-08-bounded-semantic-task-allocation.md)
- Verified Event boundary: [SourceOccurrence to Event Trigger Boundary](2026-09-10-source-occurrence-event-trigger-boundary.md)

## Context & Problem

The Hybrid Pipeline preserves exact source evidence and keeps model output out of accepted Ledger state.

Its current semantic stages still create avoidable review errors.

The governed event profile lacks common event families.

Role completion can replace a valid normalization assignment.

Atomic support judgments can approve parts of a malformed complete event.

Deterministic alias rules cannot resolve semantic references such as pronouns.

The standing-fact route admits event-like and argument-incomplete proposals.

Canonical review also exposed overlapping trigger proposals, repeated Event views,
document-local short-name aliases, inconsistent entity types, and common event
families that the governed profile could not represent.

The [Amodei intelligence Gold catalog](hsq-amodei-intelligence-gold-v1.json) captures four source-backed omissions.

Those four cases require five reviewable events on the Amodei Candidate Wiki page.

This program improves those five boundaries without creating another extraction Pipeline.

### Terms

**CompleteProposition** means one deterministic sentence that represents one complete event or standing Assertion draft.

**PropositionDecision** means the combined Qwen and NLI evidence for one CompleteProposition.

**CoreferenceObservation** means one fallible specialist-model link between exact source spans.

**SemanticReferenceDecision** means KoteKomi's validated resolved, ambiguous, or unresolved reference result.

### Primary end-to-end flow

1. KoteKomi derives exact SourceOccurrences from one authoritative SourceSegment.
2. Qwen, GLiNER, and deterministic reference-marker rules produce source-bound mention observations.
3. KoteKomi reconciles safe boundaries and sends only ambiguous components to a bounded challenge.
4. KoteKomi routes exact reference markers and unique aliases without semantic invention.
5. F-Coref proposes antecedents for one exact target.
6. Qwen validates or contrasts only KoteKomi-supplied source-valid antecedents.
7. KoteKomi constructs a conservative ReferenceDecision with complete execution lineage.
8. ReFinED proposes external identities for eligible specific mentions.
9. Stanza and QANom propose EventHeadCandidates from exact SourceOccurrences.
10. Qwen answers finite candidate-local Event questions.
11. KoteKomi reconciles those answers into exact EventTriggerDraft records.
12. Later bounded tasks select governed frames, roles, and presentation.
13. Qwen and an NLI challenger judge one CompleteProposition against exact source text.
14. KoteKomi admits only complete supported Events and standing Assertions to human review.

The stage-local control path evaluates and diagnoses each completed boundary independently.

That control path cannot create production extraction records or accepted Ledger state.

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
- HSQ-DEL-05: Canonical evaluation reports every Amodei Gold event from source through Candidate Wiki.

## Proposed Architecture

```text
authoritative SourceSegment
        |
        v
mention boundary --> reference boundary --> Event-trigger boundary
        |                   |                        |
        +-------------------+------------------------+
                            v
                 governed Event semantics
                            |
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

Adapters expose mention, linguistic, nominalization, coreference, identity-link, and NLI observations through Ports.

The Domain Core owns governed event meanings and typed decision records.

The Pipeline composes the existing Hybrid stages.

The [Hybrid Pipeline architecture](2026-09-01-hybrid-intelligence-extraction-pipeline.md#current-implemented-boundary-architecture) defines the production and verification paths.

## Incremental Delivery

| Deliverable | User story | Precondition | Postcondition |
| --- | --- | --- | --- |
| [HSQ-1](2026-09-06-governed-event-coverage.md) | A reviewer sees criticism, publication, and rebuttal events without forced frame substitutions. | HP-6 emits governed event evidence. | The governed profile represents the adjudicated missing families. |
| [HSQ-2](2026-09-06-monotonic-role-completion.md) | A reviewer sees valid role assignments preserved through completion. | HSQ-1 defines the current governed frames. | Completion fills gaps without overwriting valid normalization output. |
| [HSQ-3](2026-09-06-complete-proposition-verification.md) | A reviewer sees only events whose complete meaning is source-supported. | HSQ-2 constructs complete governed events. | Qwen and NLI evidence qualify one CompleteProposition. |
| [HSQ-4](2026-09-06-bounded-semantic-reference-resolution.md) | A reviewer can trace bounded pronoun and nominal reference decisions. | Exact source spans and document references exist. | F-Coref supplies production-eligible observations that KoteKomi validates. |
| [HSQ-5](2026-09-06-standing-fact-semantic-admission.md) | A reviewer sees standing Assertions without flattened events or substituted arguments. | HSQ-3 and HSQ-4 expose proposition and reference decisions. | The standing-fact route admits only supported standing Assertions. |
| [HSQ-6](2026-09-07-source-bound-governed-event-extraction.md) | A reviewer sees complete source-bound Events without open-frame translation loss. | HSQ-1 through HSQ-5 expose governed meanings and support evidence. | Trigger discovery feeds governed event construction directly and all five Amodei Gold events reach the Candidate Wiki. |
| [HSQ-7](2026-09-08-bounded-semantic-task-allocation.md) | A reviewer retains source-backed intelligence because each model call makes one bounded semantic decision. | HSQ-6 exposes the remaining trigger, normalization, admission, route, and reference losses. | Mention, reference, and Event-trigger boundaries preserve source-owned choices and exact stage-local evidence. |

## Behavior & Domain Rules

- HSQ-RUL-01: An unresolved governed meaning remains a gap.
- HSQ-RUL-02: A later model result cannot overwrite a valid earlier source-bound assignment.
- HSQ-RUL-03: A specialist score cannot become evidence confidence.
- HSQ-RUL-04: A coreference observation cannot create an Entity.
- HSQ-RUL-05: A bounded event uses an Event instead of a binary standing Assertion.
- HSQ-RUL-06: Existing derived previews become stale when their policy identity changes.
- HSQ-RUL-07: Canonical verification evaluates the final review disposition and proposal presence, not merely trigger discovery.
- HSQ-RUL-08: A rejected Gold semantic must be absent or terminate as held with no ProposedChange.
- HSQ-RUL-09: Reference discovery supplies source-literal pronouns and bounded nominal references to the existing HSQ-4 resolver.
- HSQ-RUL-10: An event-bearing SourceSegment cannot also yield a non-stative standing Assertion for the same meaning.
- HSQ-RUL-11: Overlapping trigger proposals retain the shortest source-literal trigger; non-overlapping triggers remain distinct events.
- HSQ-RUL-12: Every materialized Event argument retains its governed frame-role ID and UpperRole qualifier.
- HSQ-RUL-13: Document-local identity reconciliation may join a short name to one uniquely observed same-kind terminal full name, but never guesses through ambiguity or across entity kinds.
- HSQ-RUL-14: Entity-type conflicts remain separate review candidates and produce an explicit diagnostic.
- HSQ-RUL-15: Governed event families are added only from adjudicated omissions and never through a catch-all frame.
- HSQ-RUL-16: Surface trigger wording never becomes the governed relationship vocabulary.
- HSQ-RUL-17: One invalid optional field cannot erase an otherwise parseable event proposal.
- HSQ-RUL-18: A Candidate Wiki event requires governed roles, exact source evidence, and audit lineage.

## Acceptance Criteria

- AC-HSQ-AUT-01: Tests prove no model or specialist output writes accepted Ledger state.
- AC-HSQ-DEL-01: Every TDD passes its focused Gold replay before the next TDD begins.
- AC-HSQ-DEL-02: Stage traces expose exact source input, raw output, parsed output, and admission result.
- AC-HSQ-RUL-01: The canonical Anthropic PDF produces source-aligned review candidates after all five deliverables.
- AC-HSQ-RUL-02: The Candidate Wiki excludes the adjudicated malformed Amodei proposals.
- AC-HSQ-RUL-03: Canonical verification fails when an excluded Gold semantic produces a ProposedChange or an expected proposed event does not.
- AC-HSQ-RUL-04: Deterministic trigger reconciliation suppresses overlapping duplicate trigger graphs while retaining distinct causal events.
- AC-HSQ-RUL-05: Proposal tests prove that governed role qualifiers survive into each reviewable Assertion.
- AC-HSQ-RUL-06: Identity tests prove unique terminal-name reconciliation, ambiguous-name separation, and cross-kind conflict diagnostics.
- AC-HSQ-RUL-07: The Amodei Gold catalog contains four source cases and five expected events.
- AC-HSQ-RUL-08: Canonical evaluation reports each Amodei Gold event's terminal stage and disposition.
- AC-HSQ-RUL-09: All five Amodei Gold events reach the Amodei Candidate Wiki page with exact source text.

## Reference Implementations

- Stage evidence: follow `packages/application/src/kotekomi_application/extraction_stage_trace.py`.
- Model tasks: follow `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Model resources: follow `packages/adapters/src/kotekomi_adapters/model_resources.py`.
- Immutable previews: follow `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.

## Constraints and Halt Conditions

Stop one deliverable when it loses an existing adjudicated correct event.

Stop when a specialist dependency cannot run within the supported local hardware profile.

Stop when a model result would become accepted Ledger state without human review.
