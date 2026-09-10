# TDD: Bounded Semantic Task Allocation

- Status: Accepted for implementation
- Deliverable ID: HSQ-7
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [Source-Bound Governed Event Extraction](2026-09-07-source-bound-governed-event-extraction.md)
- Development Gold: [Amodei Task-Allocation Gold](hsq-task-allocation-amodei-gold-v1.json)
- Held-out Gold: [Anthropic Task-Allocation Gold](hsq-task-allocation-anthropic-gold-v1.json)
- Pinned baseline: [September 8 Task-Allocation Baseline](hsq-task-allocation-baseline-2026-09-08.json)
- Historical stage-local split: [Mention and Reference Evaluation Split v1](hsq-stage-local-split-v1.json)
- Corrected stage-local split: [Mention and Reference Evaluation Split v2](hsq-stage-local-split-v2.json)
- Evaluator corrections: [Stage-Local Evaluator Corrections](hsq-stage-local-evaluator-corrections-v1.json)

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

**Event trigger expression** means one contiguous range of supplied SourceOccurrences plus one supplied head occurrence that identifies the event-bearing word inside that range.

**Frame selection task** means one model decision among supplied governed frame IDs for one selected source occurrence.

**Frame-fit challenge task** means one binary model decision about whether a selected governed frame accurately represents one Event trigger expression.

**Role selection task** means one model decision for one supplied role of one already selected frame.

**Event presentation task** means one model decision over polarity, modality, and attribution for one already constructed event meaning.

**Reference challenge task** means one model decision among supplied, source-valid antecedent candidate IDs or the typed outcomes `ambiguous` and `unresolved`.

**Ontology gap** means a source-backed meaning for which the current governed profile has no accurate representation.

**Boundary candidate judgment** means one model judgment about whether one supplied source span is a
complete expression.

**Effective MentionCandidate** means one candidate selected by deterministic reconciliation or judged
`complete` by semantic boundary adjudication.

### Primary end-to-end flow

1. KoteKomi derives source occurrences from one authoritative SourceSegment.
2. Qwen selects one contiguous occurrence range, one head occurrence inside that range, and one diagnostic label for each explicit event.
3. KoteKomi validates each output line independently, rejects non-event heads, and constructs exact EventTriggerDraft records.
4. Qwen selects one governed frame or `unresolved` for one trigger.
5. A separate binary task confirms that the selected frame accurately represents the trigger expression.
6. Qwen selects one target for one governed role at a time with sibling-role context.
7. Qwen classifies event presentation without selecting the frame or roles again.
8. KoteKomi constructs one CompleteProposition and sends only that proposition through the support gate.
9. Event and standing-fact routes may both produce derived candidates from one SourceSegment.
10. KoteKomi gives event semantics ownership of source-bound event relations and retains non-event standing facts.
11. F-Coref proposes antecedent candidates, Qwen selects among a bounded source-valid catalog, and KoteKomi constructs the terminal reference decision.

Before mention interpretation, KoteKomi sends each ambiguous overlap component to one bounded semantic
boundary task.

Qwen judges each supplied candidate as `complete`, `incomplete`, or `unclear`.

KoteKomi derives the Effective MentionCandidates from deterministic selections and `complete` judgments.

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
- BTA-GOL-08: A finding that changes only evaluator judgment is a separately pinned correction record linked to the finalized parent evidence; it does not rewrite Gold or system output.

### Source-owned mention occurrences

- BTA-MEN-01: KoteKomi deterministically derives an ordered SourceOccurrence catalog from exact SourceSegment characters before Qwen mention proposal.
- BTA-MEN-02: Qwen selects only the first and last supplied occurrence IDs of one contiguous mention expression.
- BTA-MEN-02A: Occurrence IDs are SourceSegment-local `oN` values; the SourceSegment label remains a separate output field and is never repeated as an occurrence-ID prefix.
- BTA-MEN-03: Qwen does not transcribe mention text, create source offsets, or assign an ontology kind during mention proposal.
- BTA-MEN-04: KoteKomi reconstructs each MentionObservation's exact text and half-open source range from the selected occurrence range.
- BTA-MEN-05: Invalid selection lines remain isolated and cannot erase another valid occurrence selection.

### Semantic boundary adjudication

- BTA-BND-01: Deterministic boundary reconciliation preserves every source-valid MentionCandidate.
- BTA-BND-02: KoteKomi sends only ambiguous overlap components to semantic boundary adjudication.
- BTA-BND-03: One task receives exact source text and at most eight source-bound candidate labels.
- BTA-BND-04: Qwen returns only a supplied candidate label and `complete`, `incomplete`, or `unclear`.
- BTA-BND-04A: The requested form is `cN | status`; the parser also accepts the semantically identical `candidate: cN | status` form because the redundant prefix carries no authority.
- BTA-BND-05: Qwen does not return source text, offsets, ontology kinds, or canonical identities.
- BTA-BND-06: KoteKomi maps valid local labels to MentionCandidate identities.
- BTA-BND-07: KoteKomi treats omitted, malformed, unknown, and duplicate lines as unresolved.
- BTA-BND-08: One invalid line cannot erase a valid sibling judgment.
- BTA-BND-09: Two overlapping candidates can both become effective when each expresses a complete meaning.
- BTA-BND-09A: A proper-name possessor remains independently complete when a larger possessed expression also expresses a complete meaning.
- BTA-BND-09B: KoteKomi proves a candidate ending immediately before a source possessive clitic complete and asks Qwen to judge only the residual overlapping candidates.
- BTA-BND-09C: The adjudication trace separates deterministically complete candidate IDs from model-visible candidate labels.
- BTA-BND-10: KoteKomi routes only Effective MentionCandidates to mention interpretation.
- BTA-BND-11: Every downstream mention consumer uses the same Effective MentionCandidate rule.
- BTA-BND-12: A component with more than eight candidates remains unresolved without a model call.
- BTA-BND-13: A failed adjudication keeps its candidates and produces a partial Preview.
- BTA-BND-14: Adjudication creates derived evidence and cannot create accepted Ledger state.

### Source-owned trigger occurrences

- BTA-TRG-01: KoteKomi deterministically derives ordered SourceOccurrence records from exact SourceSegment characters.
- BTA-TRG-02: Each SourceOccurrence contains a local occurrence ID, exact text, and half-open source range.
- BTA-TRG-03: The trigger task supplies the ordered occurrence catalog to Qwen.
- BTA-TRG-04: Qwen returns only a supplied contiguous occurrence range, one supplied head occurrence inside that range, and one diagnostic open label.
- BTA-TRG-05: Qwen does not transcribe trigger text or create source ranges.
- BTA-TRG-06: KoteKomi validates each event line independently.
- BTA-TRG-07: An invalid event line becomes a typed line rejection and cannot erase valid event lines.
- BTA-TRG-08: KoteKomi constructs EventTriggerDraft expression text, expression range, head text, and head range only from selected SourceOccurrences.
- BTA-TRG-09: KoteKomi rejects auxiliary and function-word heads before EventTriggerDraft construction.
- BTA-TRG-10: Deterministic overlap reconciliation retains one selected expression according to the pinned policy.

### Bounded governed semantics

- BTA-EVT-01: One frame-selection task receives one trigger and only the governed frame ID and definition catalog.
- BTA-EVT-02: Frame selection returns one supplied frame ID or `unresolved`.
- BTA-EVT-03: A selected frame receives one separate binary frame-fit challenge using only the source, trigger expression, frame ID, and governed definition.
- BTA-EVT-04: A failed frame-fit challenge produces an `unmapped_frame` SemanticCoverageGap.
- BTA-EVT-05: One role-selection task receives one selected frame, one supplied target role, the complete sibling-role catalog, prior sibling selections, exact source, local candidates, and validated reference metadata.
- BTA-EVT-06: Required roles run first in governed declaration order and optional roles run afterward in governed declaration order.
- BTA-EVT-07: Every selected role span is the smallest meaning-complete source expression for that role.
- BTA-EVT-08: One role result cannot overwrite another valid role result.
- BTA-EVT-09: One event-presentation task receives the selected trigger, frame, and source-backed role selections.
- BTA-EVT-10: The presentation task does not select the frame or role targets again.
- BTA-EVT-11: KoteKomi constructs every event, role assignment, qualifier, EvidenceTarget, identifier, and digest.
- BTA-EVT-12: A model failure affects only the bounded decision that used that model call.
- BTA-EVT-13: `unresolved` frame selection, rejected frame fit, and invalid required frame-fit output cannot silently select a governed frame.

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
- BTA-ROU-03: A standing-fact proposal selects its relation as a supplied contiguous SourceOccurrence range.
- BTA-ROU-04: KoteKomi reconstructs standing relation text and offsets from authoritative source characters.
- BTA-ROU-05: A standing relation that overlaps a validated event trigger in the same SourceSegment is held as `event_route_required`.
- BTA-ROU-06: Non-overlapping standing facts in a mixed SourceSegment remain eligible.
- BTA-ROU-07: A standing fact cannot replace a bounded or unmapped event merely because the standing route also found it.

### Specialist reference boundary

- BTA-REF-01: F-Coref remains a fallible antecedent candidate proposer.
- BTA-REF-02: KoteKomi validates every F-Coref span against authoritative source characters.
- BTA-REF-03: A bounded reference challenge receives the target and an ordered catalog of source-valid candidate IDs.
- BTA-REF-04: Qwen returns one supplied candidate ID, `ambiguous`, or `unresolved`.
- BTA-REF-05: Qwen cannot copy or invent an antecedent literal, source range, or Entity ID.
- BTA-REF-06: KoteKomi constructs the terminal ReferenceDecision from the validated candidate and model judgment.
- BTA-REF-07: A malformed, out-of-catalog, or contradictory challenge result cannot become a resolved reference.
- BTA-REF-08: Exact alias declarations remain deterministic and do not require a model challenge.
- BTA-REF-09: When F-Coref supplies no usable antecedent, KoteKomi supplies up to eight nearest preceding source-valid specific-entity candidates from the same paragraph.
- BTA-REF-10: Semantic-reference context remains bounded to the same paragraph and 1,024 input tokens.
- BTA-REF-11: An unresolved or ambiguous generic reference cannot create an Entity, fill an Entity role, or produce a Wiki page.
- BTA-REF-12: A source-valid marker produced by the deterministic reference-marker policy routes directly to reference resolution and does not require Qwen mention interpretation.
- BTA-REF-13: The challenge input visibly separates source context before the exact target, the exact target reference, and source context after the exact target.
- BTA-REF-14: When Qwen selects a source-valid antecedent outside a non-empty F-Coref proposal set, KoteKomi records `ambiguous` with both alternatives rather than a resolved reference.

### Traceability

- BTA-TRC-01: Every bounded model task writes one ExtractionStageTrace with exact model-visible input.
- BTA-TRC-02: Each trace records raw-output digest, parsed output, rejection records, and terminal status.
- BTA-TRC-03: Deterministic construction traces name all upstream task and evidence IDs.
- BTA-TRC-04: Canonical evaluation names the first failed allocation stage for every missing Gold item.
- BTA-TRC-05: Replay uses pinned stage evidence and performs zero model calls.
- BTA-TRC-06: Candidate Wiki evaluation uses stable proposed record identity plus authoritative source digest and never depends on run-specific ProposedChange identity.
- BTA-TRC-07: Evaluation attributes each omission to the actual first failed stage rather than the first absent downstream aggregate.
- BTA-TRC-08: The canonical report compares each Gold item and aggregate cost against the pinned September 8 baseline.

### Stage-local mention and reference evaluation

- BTA-SLE-01: Stage-local evaluation starts from exact authoritative SourceSegment text.
- BTA-SLE-02: Stage-local evaluation does not run downstream event, standing-fact, support, review, or Wiki stages.
- BTA-SLE-03: The split contains twenty development items and twenty locked validation items.
- BTA-SLE-04: One SourceSegment digest cannot occur in both split phases.
- BTA-SLE-05: Locked validation describes previously inspected cases and is not a pristine held-out set.
- BTA-SLE-06: One unique SourceSegment execution supplies every Gold item bound to that SourceSegment.
- BTA-SLE-07: Evaluation checks mention proposal before mention interpretation and reference resolution.
- BTA-SLE-08: Reference evaluation binds decisions through the target MentionCandidate SourceSegment identity.
- BTA-SLE-09: Expanded reference context digests cannot replace the target SourceSegment identity.
- BTA-SLE-10: Every model execution records exact rendered input, exact raw output, parsed output, deterministic validation, and elapsed time.
- BTA-SLE-11: Every rejected model observation remains visible with its line and reason.
- BTA-SLE-12: A development change cannot lose an already demonstrated result.
- BTA-SLE-13: Locked validation evidence becomes immutable after finalization.
- BTA-SLE-14: Stage-local evaluation creates no ProposedChange or accepted Ledger record.
- BTA-SLE-15: Each experiment names its parent, changed hypothesis, prompt digest, schema digest, and policy digest.

The historical v1 stage-local experiment tested cumulative changes in this order.

1. Qwen receives separate proposal and interpretation contracts.
2. KoteKomi isolates malformed proposal lines from valid proposal lines.
3. KoteKomi normalizes reference-marker whitespace and possessive morphology without changing source offsets.
4. KoteKomi forms the challenge catalog from a monotonic union of specialist and deterministic candidates.
5. KoteKomi restricts legal reference outcomes to the supplied candidate cardinality.
6. KoteKomi measures source-derived alias rescue without granting it source authority.
7. KoteKomi measures selective interpretation only after correctness gates pass.

The experiment can measure alias rescue without activating it in production.

The experiment can measure selective interpretation without activating it in production.

Production adopts either optional change only after development and locked validation pass without regression.

The v2 pre-trigger correction experiment changes only the already isolated mention and reference stages.

1. Qwen mention proposal selects KoteKomi-supplied SourceOccurrence ranges without copying text or assigning ontology kinds.
2. Deterministic reference markers route directly to reference resolution without an interpretation call.
3. Reference prompts visibly delimit the one exact target from its surrounding source context.
4. Qwen and F-Coref disagreement produces an auditable `ambiguous` result.
5. ANT-14's previously shortened evaluator literal is corrected through a pinned evaluator-correction record.
6. The four diagnostic cases run first, followed by the unchanged twenty-item development and twenty-item validation partitions.

The four diagnostic cases are AMO-08, ANT-01, ANT-14, and ANT-16.

The finalized v1 validation evidence remains immutable and is the named parent of the v2 experiment.

The first v2 diagnostic run passed AMO-08, ANT-14, and ANT-16 and stopped at 3/4 before the full replay.

ANT-01 showed that the source-owned-range design was sound but its rendered notation was not: Qwen selected the correct numeric ranges as `s5` through `s9` and `s17` through `s17` after seeing catalog IDs such as `s1:o5` and `s1:o17`.

The v3 refinement removes the redundant SourceSegment prefix from each catalog occurrence, renders only SourceSegment-local `oN` IDs, keeps strict rejection of the malformed `sN` shorthand, and reruns the same four diagnostics before any forty-item replay.

The completed v3 replay passed thirty-three of forty Gold items.

It fixed AMO-08, ANT-01, ANT-14, and ANT-16.

It regressed AMO-05, AMO-06, AMO-10, AMO-11, ANT-06, and ANT-11.

In each regression, deterministic reconciliation preserved a correct narrow candidate and an overlapping
long candidate.

The unresolved overlap rule selected neither candidate.

AMO-12 remains a separate reference ambiguity between Qwen and F-Coref.

The v4 correction adds only semantic boundary adjudication after deterministic reconciliation.

The six regression items run first.

The first v4 diagnostic passed five of six regression items.

ANT-06 failed because Qwen treated `complete` as the longest noun phrase and marked the source-valid
proper-name possessor incomplete when both the possessor and possessed expression denoted complete
meanings.

The v4 prompt refinement states the general proper-name possessor rule explicitly and forbids
longest-expression preference.

The second v4 diagnostic made the correct ANT-06 semantic judgment but passed only two of six items.

Four items failed because Qwen omitted the redundant `candidate:` prefix while returning valid supplied
labels and valid statuses.

The parser refinement requests the smaller `cN | status` form and accepts either unambiguous spelling.

Both forms undergo the same label, status, duplicate, omission, and line-isolation validation, and the
exact raw line remains in evidence.

The third v4 diagnostic returned to five of six items.

ANT-06 remained unstable: Qwen again marked the exact proper-name possessor incomplete even though the
same substantive prompt had produced the correct result in the preceding run.

The next refinement removes this grammatical decision from Qwen.

KoteKomi proves the boundary immediately before `'s` or `’s` from authoritative source characters,
records that deterministic selection, and supplies only residual overlapping candidates to Qwen.

The fourth v4 diagnostic passed all six regression items.

The exact-possessor rule retained the source-valid possessor independently, Qwen judged only residual
candidates, and no diagnostic item regressed.

The unchanged twenty-item development and twenty-item validation partitions run after the diagnostic set.

The v4 correction accepts only a result that passes thirty-nine of forty items with AMO-12 as the sole hold.

## Proposed Architecture

```text
preserved MentionCandidates
          |
          v
deterministic boundary reconciliation
          |
          +--> resolved selections ------------------+
          |                                          |
          +--> ambiguous overlap --> Qwen judgment --+
                                                     |
                                                     v
                                      Effective MentionCandidates
                                                     |
                                                     v
                                         mention interpretation
```

```text
authoritative SourceSegment
          |
          v
KoteKomi SourceOccurrence catalog
          |
          v
Qwen expression-range and head selection
          |
          v
exact EventTriggerDraft
          |
          +--> Qwen frame selection
          |          |
          |          v
          +--> Qwen binary frame-fit challenge
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

`MentionOccurrenceSelection` contains one supplied SourceSegment label and the first and last supplied SourceOccurrence IDs of one mention expression.

`BoundaryCandidateJudgment` contains one task-local candidate label and one of `complete`, `incomplete`, or `unclear`.

`MentionBoundaryAdjudication` records its parent boundary decision, source digest, mapped judgments, rejected lines, task identity, run identity, and trace identity.

`StageLocalEvaluatorCorrection` records the parent evaluator evidence, original expectation, accepted exact source boundary, observed output, classification, and rationale.

`EventTriggerSelection` contains one supplied expression range, one supplied head occurrence ID, and one diagnostic open label.

`EventTriggerLineRejection` records one rejected raw line and reason.

`EventFrameSelection` contains one governed frame ID or `unresolved` and one reason.

`EventFrameFitDecision` contains one binary `fits` value and one reason.

`EventPresentationSelection` contains polarity, modality, attribution selection, and independently parsed optional qualifiers.

`SemanticReferenceChallenge` records one selected antecedent candidate ID or a typed non-resolution.

`StandingFactDraft` contains a source-bound relation range reconstructed from supplied SourceOccurrences.

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
- BTA-RUL-09: Deterministic boundary reconciliation remains unchanged by semantic adjudication.
- BTA-RUL-10: `incomplete`, `unclear`, and unresolved candidates remain inspectable but do not route downstream.

## Acceptance Criteria

- AC-BTA-GOL-01: Catalog tests prove twenty Amodei and twenty Anthropic items with exact source digests.
- AC-BTA-MEN-01: Tests prove Qwen can select both occurrences of the same literal by different supplied occurrence IDs and KoteKomi reconstructs both exact source ranges.
- AC-BTA-MEN-02: Tests prove the mention-selection prompt and output contract contain no ontology-kind field and require no copied source text.
- AC-BTA-MEN-03: Tests prove the model-visible catalog uses SourceSegment-local `oN` IDs, contains no redundant `sN:oN` identifiers, and rejects an `sN` value supplied as an occurrence ID.
- AC-BTA-BND-01: Parser tests prove both unambiguous line spellings map identically while malformed, unknown, duplicate, and omitted lines leave valid sibling judgments intact.
- AC-BTA-BND-02: Tests prove `Amodei` remains effective beside incomplete `Amodei wrote` and longer clause fragments.
- AC-BTA-BND-03: Tests prove `Anthropic` remains effective beside incomplete `Anthropic's technology achieved`.
- AC-BTA-BND-04: Tests prove `Anthropic` and complete `Anthropic's services` can both remain effective.
- AC-BTA-BND-04A: Prompt-contract tests prove the possessor rule uses a generic example and contains no diagnostic-catalog entity names.
- AC-BTA-BND-04B: Tests prove the proper-name possessor is absent from model-visible candidate choices, remains effective, and is separately identified in the adjudication trace.
- AC-BTA-BND-04C: Tests prove Qwen can reject an attached predicate in the residual candidate without vetoing the exact possessor boundary.
- AC-BTA-BND-05: Tests prove deterministic resolved and uncontested components bypass the model task.
- AC-BTA-BND-06: Tests prove failed and over-limit adjudications remain partial and create no accepted state.
- AC-BTA-BND-07: Tests inspect exact model-visible input, raw output, mapped judgments, rejected lines, and lineage.
- AC-BTA-TRG-01: Tests prove `has publicly rebuked` can be retained as the expression while `rebuked` is the required event head and `has` is rejected as a head.
- AC-BTA-TRG-02: Tests prove one invalid trigger line does not erase another valid line.
- AC-BTA-EVT-01: Tests prove frame selection input excludes the role catalog.
- AC-BTA-EVT-02: Tests prove a mismatched selected frame is rejected by the binary frame-fit challenge.
- AC-BTA-EVT-03: Tests prove every role task contains exactly one target role plus sibling definitions and prior sibling selections.
- AC-BTA-EVT-04: Tests prove an optional assessment and publication outlet can be retained without changing required roles.
- AC-BTA-EVT-05: Tests prove complete publication, meeting, and characterization targets are not truncated to syntactically adjacent fragments.
- AC-BTA-SUP-01: Tests prove one supported CompleteProposition is not vetoed by an auxiliary attribution explanation.
- AC-BTA-ROU-01: Tests prove one mixed SourceSegment can retain both an event and a non-duplicate standing fact.
- AC-BTA-ROU-02: Tests prove an event-overlapping standing relation is held before it can flatten the event.
- AC-BTA-REF-01: Tests prove F-Coref cannot resolve `his` when Qwen selects a different candidate or returns ambiguity.
- AC-BTA-REF-02: Tests prove an F-Coref abstention still permits a bounded challenge over preceding candidates.
- AC-BTA-REF-03: Tests prove an unresolved generic reference cannot create a typed Entity or Wiki page.
- AC-BTA-REF-04: Tests prove a deterministic `the  company's` marker reaches reference resolution without a MentionInterpretation.
- AC-BTA-REF-05: Tests inspect a challenge task containing distinct before-target, target-reference, and after-target fields.
- AC-BTA-REF-06: Tests prove disagreement between a non-empty F-Coref proposal and Qwen's selection produces `ambiguous` with both source-valid spans.
- AC-BTA-GAP-01: Tests prove relationship termination and unsupported composite meanings terminate as typed ontology gaps.
- AC-BTA-TRC-01: Tests inspect exact data in and data out for every model-facing stage.
- AC-BTA-REG-01: Focused deterministic tests retain all previously demonstrated event behavior.
- AC-BTA-REG-02: Canonical evaluation reports all forty Gold items and no wrong forced frame.
- AC-BTA-REG-03: Candidate Wiki evaluation lists the Gold items that reached review and the first failed stage for each omission.
- AC-BTA-REG-04: Tests prove no model output writes accepted Ledger state.
- AC-BTA-REG-05: Canonical comparison reports no demonstrated-item regression and at least one newly complete item in each Gold catalog.
- AC-BTA-SLE-01: Tests reject a split that leaks one SourceSegment digest across phases.
- AC-BTA-SLE-02: Tests prove proposal and interpretation use distinct prompts and schemas.
- AC-BTA-SLE-03: Tests prove one malformed proposal line preserves another valid proposal line.
- AC-BTA-SLE-04: Tests prove `the  company's` remains source-exact and receives an anaphoric classification.
- AC-BTA-SLE-05: Tests prove an F-Coref proposal cannot remove another source-valid challenge candidate.
- AC-BTA-SLE-06: Tests prove one supplied candidate cannot produce an ambiguous decision.
- AC-BTA-SLE-07: Tests inspect exact stage-local data in and data out.
- AC-BTA-SLE-08: Tests prove stage-local execution creates no ProposedChange or accepted Ledger state.
- AC-BTA-SLE-09: Development and locked validation reports show per-case results and producer-specific timing.
- AC-BTA-SLE-10: Tests prove split v1 retains the original ANT-14 expectation while split v2 applies the pinned source-bound evaluator correction.
- AC-BTA-SLE-11: The v2 runner supports a pinned four-case diagnostic subset without changing either twenty-item partition.
- AC-BTA-SLE-12: The v4 diagnostic passes AMO-05, AMO-06, AMO-10, AMO-11, ANT-06, and ANT-11.
- AC-BTA-SLE-13: The v4 replay passes thirty-nine of forty items with AMO-12 as the sole hold.
- AC-BTA-SLE-14: The v4 replay creates zero ProposedChanges and zero accepted Ledger records.

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
