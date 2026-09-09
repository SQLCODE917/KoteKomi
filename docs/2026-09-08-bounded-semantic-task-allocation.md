# TDD: Bounded Semantic Task Allocation

- Status: Accepted for implementation
- Deliverable ID: HSQ-7
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [Source-Bound Governed Event Extraction](2026-09-07-source-bound-governed-event-extraction.md)
- Development Gold: [Amodei Task-Allocation Gold](hsq-task-allocation-amodei-gold-v1.json)
- Held-out Gold: [Anthropic Task-Allocation Gold](hsq-task-allocation-anthropic-gold-v1.json)

## Context & Problem

HSQ-6 removed open EventFrameDraft translation but left too much semantic work in two model calls.

Trigger discovery asks Qwen to discover an occurrence, transcribe its exact source text, invent a local event ID, and label its type in one batch.

One inflection or transcription error can invalidate every otherwise useful trigger in that SourceSegment.

Governed event normalization asks Qwen to choose among sixteen frames, inspect fifty-two roles, assign every role, choose polarity, choose modality, choose attribution, and copy qualifiers in one response.

That task permits one mistake to erase several correct semantic decisions.

The support stage then asks Qwen to judge every mechanically derived component separately.

One auxiliary component judgment can veto a CompleteProposition that Qwen and NLI otherwise support.

The standing-fact route is suppressed before semantic qualification whenever the same SourceSegment contains an event trigger.

F-Coref currently proposes a source-span cluster and KoteKomi can treat its unique candidate as the terminal semantic resolution.

The specialist model is useful for candidate generation, but it must not own the semantic identity decision.

These boundaries produced three reviewable Dario Amodei items from twenty source-backed core items.

**Source occurrence** means one deterministic token-like span with a KoteKomi-owned local ID and exact authoritative source range.

**Frame selection task** means one model decision among supplied governed frame IDs for one selected source occurrence.

**Role selection task** means one model decision for one supplied role of one already selected frame.

**Event presentation task** means one model decision over polarity, modality, and attribution for one already constructed event meaning.

**Reference challenge task** means one model decision among supplied, source-valid antecedent candidate IDs or the typed outcomes `ambiguous` and `unresolved`.

**Ontology gap** means a source-backed meaning for which the current governed profile has no accurate representation.

### Primary end-to-end flow

1. KoteKomi derives source occurrences from one authoritative SourceSegment.
2. Qwen selects occurrence IDs that evoke explicit events.
3. KoteKomi validates each output line independently and constructs exact EventTriggerDraft records.
4. Qwen selects one governed frame or `unresolved` for one trigger.
5. Qwen selects one target for one governed role at a time.
6. Qwen classifies event presentation without selecting the frame or roles again.
7. KoteKomi constructs one CompleteProposition and sends only that proposition through the support gate.
8. Event and standing-fact routes may both produce derived candidates from one SourceSegment.
9. KoteKomi admits, deduplicates, or retains typed gaps after semantic qualification.
10. F-Coref narrows antecedent candidates, Qwen selects among source-valid IDs, and KoteKomi constructs the terminal reference decision.

## Goals

- A reviewer sees substantially more source-backed Amodei intelligence without weakening evidence or review boundaries.
- Qwen performs one bounded semantic decision per task.
- KoteKomi owns source spans, identities, ontology catalogs, deterministic construction, and admission.
- One malformed model-output line cannot erase another valid line.
- A source-backed but currently unrepresentable meaning remains an inspectable ontology gap.
- A prompt tuned on Amodei does not lose Anthropic-wide coverage.
- Every task records exact model-visible input, raw output, parsed output, and terminal decision.

## Requirements

### Gold and evaluation

- BTA-GOL-01: The development catalog contains exactly twenty Dario Amodei intelligence items.
- BTA-GOL-02: The development catalog contains the seventeen previously missing core items and the three previously demonstrated items.
- BTA-GOL-03: The held-out catalog contains exactly twenty Anthropic intelligence items.
- BTA-GOL-04: Each item preserves complete authoritative source text, source digest, expected meaning, expected route, and task-allocation tags.
- BTA-GOL-05: Each catalog distinguishes representable items from typed ontology gaps.
- BTA-GOL-06: Evaluation reports exact expected and actual stage outcomes per item instead of only aggregate counts.
- BTA-GOL-07: Development results cannot change held-out expectations.

### Source-owned trigger occurrences

- BTA-TRG-01: KoteKomi deterministically derives ordered SourceOccurrence records from exact SourceSegment characters.
- BTA-TRG-02: Each SourceOccurrence contains a local occurrence ID, exact text, and half-open source range.
- BTA-TRG-03: The trigger task supplies the ordered occurrence catalog to Qwen.
- BTA-TRG-04: Qwen returns only supplied occurrence IDs and diagnostic open labels.
- BTA-TRG-05: Qwen does not transcribe trigger text or create source ranges.
- BTA-TRG-06: KoteKomi validates each event line independently.
- BTA-TRG-07: An invalid event line becomes a typed line rejection and cannot erase valid event lines.
- BTA-TRG-08: KoteKomi constructs EventTriggerDraft text and ranges only from the selected SourceOccurrence.
- BTA-TRG-09: Deterministic overlap reconciliation retains one selected occurrence according to the pinned policy.

### Bounded governed semantics

- BTA-EVT-01: One frame-selection task receives one trigger and only the governed frame ID and definition catalog.
- BTA-EVT-02: Frame selection returns one supplied frame ID or `unresolved`.
- BTA-EVT-03: One role-selection task receives one selected frame, one supplied role, exact source, local candidates, and validated reference metadata.
- BTA-EVT-04: Required and useful optional roles use the same one-role task contract.
- BTA-EVT-05: One role result cannot overwrite another valid role result.
- BTA-EVT-06: One event-presentation task receives the selected trigger, frame, and source-backed role selections.
- BTA-EVT-07: The presentation task does not select the frame or role targets again.
- BTA-EVT-08: KoteKomi constructs every event, role assignment, qualifier, EvidenceTarget, identifier, and digest.
- BTA-EVT-09: A model failure affects only the bounded decision that used that model call.
- BTA-EVT-10: `unresolved` frame selection produces an `unmapped_frame` SemanticCoverageGap.

### Proposition admission

- BTA-SUP-01: KoteKomi deterministically renders one CompleteProposition from the complete governed event.
- BTA-SUP-02: Qwen judges the CompleteProposition against exact source text once.
- BTA-SUP-03: NLI independently challenges the same CompleteProposition.
- BTA-SUP-04: Component SemanticStatements remain inspectable deterministic explanations.
- BTA-SUP-05: Component statements do not receive separate model calls and cannot independently veto the CompleteProposition.
- BTA-SUP-06: HP-7 requires exactly one supported PropositionDecision plus complete required roles and no hard source-alignment gap.

### Parallel semantic routes

- BTA-ROU-01: Event-trigger presence does not suppress standing-fact semantic qualification.
- BTA-ROU-02: Event and standing-fact routes can both produce derived candidates from one mixed SourceSegment.
- BTA-ROU-03: KoteKomi deterministically suppresses only semantically duplicate final proposals.
- BTA-ROU-04: A standing fact cannot replace a bounded event merely because the standing route also found it.

### Specialist reference boundary

- BTA-REF-01: F-Coref remains a fallible antecedent candidate proposer.
- BTA-REF-02: KoteKomi validates every F-Coref span against authoritative source characters.
- BTA-REF-03: A bounded reference challenge receives the target and an ordered catalog of source-valid candidate IDs.
- BTA-REF-04: Qwen returns one supplied candidate ID, `ambiguous`, or `unresolved`.
- BTA-REF-05: Qwen cannot copy or invent an antecedent literal, source range, or Entity ID.
- BTA-REF-06: KoteKomi constructs the terminal ReferenceDecision from the validated candidate and model judgment.
- BTA-REF-07: A malformed, out-of-catalog, or contradictory challenge result cannot become a resolved reference.
- BTA-REF-08: Exact alias declarations remain deterministic and do not require a model challenge.

### Traceability

- BTA-TRC-01: Every bounded model task writes one ExtractionStageTrace with exact model-visible input.
- BTA-TRC-02: Each trace records raw-output digest, parsed output, rejection records, and terminal status.
- BTA-TRC-03: Deterministic construction traces name all upstream task and evidence IDs.
- BTA-TRC-04: Canonical evaluation names the first failed allocation stage for every missing Gold item.
- BTA-TRC-05: Replay uses pinned stage evidence and performs zero model calls.

## Proposed Architecture

```text
authoritative SourceSegment
          |
          v
KoteKomi SourceOccurrence catalog
          |
          v
Qwen occurrence-ID selection
          |
          v
exact EventTriggerDraft
          |
          +--> Qwen frame selection
          |          |
          |          v
          +--> one Qwen role selection per role
          |          |
          |          v
          +--> Qwen event presentation
                     |
                     v
          KoteKomi CompleteProposition
                     |
                 +---+---+
                 |       |
               Qwen     NLI
                 |       |
                 +---+---+
                     v
          deterministic admission
```

F-Coref and Qwen have separate responsibilities.

F-Coref proposes which source-valid antecedents merit consideration.

Qwen judges the meaning of one reference among those supplied choices.

KoteKomi owns the resulting range, identity, decision record, and trace.

## Data Model

`SourceOccurrence` is a derived Application DTO with local ID, exact text, start, and end.

`EventTriggerSelection` contains one supplied occurrence ID and one diagnostic open label.

`EventTriggerLineRejection` records one rejected raw line and reason.

`EventFrameSelection` contains one governed frame ID or `unresolved` and one reason.

`EventPresentationSelection` contains polarity, modality, attribution selection, and independently parsed optional qualifiers.

`SemanticReferenceChallenge` records one selected antecedent candidate ID or a typed non-resolution.

Existing EventTriggerDraft, EventSemanticDraft, CompleteProposition, PropositionDecision, EvidenceTarget, ProposedChange, and accepted Ledger records remain the downstream contracts.

## Behavior & Domain Rules

- BTA-RUL-01: A local model never creates a canonical identifier, digest, source offset, or Ledger record.
- BTA-RUL-02: Model tasks choose only among KoteKomi-supplied IDs or typed non-resolution values.
- BTA-RUL-03: A source-backed meaning outside the governed profile is not evidence of model failure.
- BTA-RUL-04: An ontology gap cannot be silently mapped to the nearest frame.
- BTA-RUL-05: A regression on an already demonstrated Gold item blocks acceptance.
- BTA-RUL-06: The held-out catalog is evaluated only after development behavior is frozen.
- BTA-RUL-07: Retrieval confidence, specialist score, model confidence, and evidence confidence remain distinct.
- BTA-RUL-08: All intelligence remains pending until human review.

## Acceptance Criteria

- AC-BTA-GOL-01: Catalog tests prove twenty Amodei and twenty Anthropic items with exact source digests.
- AC-BTA-TRG-01: Tests prove `has rebuked` cannot be returned because Qwen can select only the supplied occurrence for `rebuked`.
- AC-BTA-TRG-02: Tests prove one invalid trigger line does not erase another valid line.
- AC-BTA-EVT-01: Tests prove frame selection input excludes the role catalog.
- AC-BTA-EVT-02: Tests prove every role task contains exactly one target role.
- AC-BTA-EVT-03: Tests prove an optional assessment and publication outlet can be retained without changing required roles.
- AC-BTA-SUP-01: Tests prove one supported CompleteProposition is not vetoed by an auxiliary attribution explanation.
- AC-BTA-ROU-01: Tests prove one mixed SourceSegment can retain both an event and a non-duplicate standing fact.
- AC-BTA-REF-01: Tests prove F-Coref cannot resolve `his` when Qwen selects a different candidate or returns ambiguity.
- AC-BTA-GAP-01: Tests prove relationship termination and unsupported composite meanings terminate as typed ontology gaps.
- AC-BTA-TRC-01: Tests inspect exact data in and data out for every model-facing stage.
- AC-BTA-REG-01: Focused deterministic tests retain all previously demonstrated event behavior.
- AC-BTA-REG-02: Canonical evaluation reports all forty Gold items and no wrong forced frame.
- AC-BTA-REG-03: Candidate Wiki evaluation lists the Gold items that reached review and the first failed stage for each omission.
- AC-BTA-REG-04: Tests prove no model output writes accepted Ledger state.

## Reference Implementations and Research Basis

- Use `ExtractionStageTrace` for exact data-in and data-out records.
- [Multi-turn event extraction](https://aclanthology.org/2020.findings-emnlp.73/)
  separates trigger and argument questions.
- [UIE](https://aclanthology.org/2022.acl-long.395/) supplies a target schema as task guidance.
- [Document-level argument extraction](https://aclanthology.org/2021.naacl-main.69/)
  retains document context while it resolves event roles.
- [GoLLIE](https://aclanthology.org/2025.naacl-long.259/) supplies task guidelines with labels.
- [LangExtract](https://github.com/google/langextract/blob/main/README.md) grounds output in
  exact Source text and splits long documents into bounded work.
- KoteKomi combines these patterns as one semantic choice over one supplied catalog.
- KoteKomi derives final source ranges from authoritative Source text.
- [LM Studio structured output](https://beta.lmstudio.ai/docs/developer/openai-compat/structured-output)
  can constrain transport syntax.
- KoteKomi validation remains the authority for each model result.

## Superseded HSQ-6 Decisions

- BTA-SUP-01: This TDD supersedes SGE-TRG-03 and SGE-EVT-04 through SGE-EVT-08 where they require copied trigger literals or one complete governed-profile normalization task.
- BTA-SUP-02: This TDD supersedes SGE-CON-03 and SGE-CON-04 by using one role-selection contract for required and useful optional roles.
- BTA-SUP-03: This TDD supersedes HSQ-RUL-10 where trigger presence preemptively excludes the standing route.
- BTA-SUP-04: Existing HSQ-6 derived artifacts remain historical evidence and receive no compatibility reader.

## Constraints and Halt Conditions

Stop if a bounded task requires Qwen to invent source text or a canonical identity.

Stop if one malformed output line erases another independently valid line.

Stop if the development improvement loses one previously demonstrated behavior.

Stop if held-out Anthropic quality regresses while Amodei quality improves.

Stop if a model or specialist result bypasses ProposedChange review into accepted Ledger state.
