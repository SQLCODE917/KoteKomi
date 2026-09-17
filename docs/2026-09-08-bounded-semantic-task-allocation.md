# TDD: Bounded Semantic Task Allocation

- Status: Front-Half implementation retained; evaluation contract superseded by [Source-Grounded Evaluation Cutover](2026-09-13-source-grounded-evaluation-cutover.md)
- Deliverable ID: HSQ-7
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [Source-Bound Governed Event Extraction](2026-09-07-source-bound-governed-event-extraction.md)
- Current Front-Half Gold: [Amodei](hsq-front-half-amodei-gold-v1.json) and [Anthropic](hsq-front-half-anthropic-gold-v1.json)
- Current evaluation split: [Front-Half Evaluation Split](hsq-front-half-split-v1.json)
- Event trigger boundary: [SourceOccurrence to Event Trigger Boundary](2026-09-10-source-occurrence-event-trigger-boundary.md)
- Source-grounded Event boundary: [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md)

## Delivery Status

Implemented and verified:

- authoritative SourceSegment to source-owned MentionObservation and MentionCandidate selection;
- deterministic and bounded semantic mention-boundary reconciliation;
- effective MentionCandidate interpretation and reference-marker routing;
- specialist proposal, one-candidate validation, complete-catalog contrastive fallback, and
  evidence-preserving ReferenceDecision construction;
- Stanza and QANom candidate proposal plus bounded Event routing over all reviewed trigger Gold;
- exact stage data-in/data-out, causal model-run lineage, and zero-write stage-local evaluation.

The September 10 v10 replay passed thirty-nine of forty development-plus-validation Gold items
against the then-current catalog.

Human review on September 15 established that AMO-12 has one clear antecedent: `his` resolves to
Amodei.

The v11 policy removes the rejected specialist candidate's veto after a unique contrastive choice.

A focused live replay remains required to verify that correction against the current Gold.

Implemented with focused verification:

- exact EventTriggerDraft to EventMention and pending Event proposal;
- optional governed classification that cannot control Event admission.

Still pending stage-local implementation and evaluation:

- Semantic Argument Assignments onward through Candidate Wiki evaluation.

## Implemented Front-Half Boundary

```text
authoritative SourceSegment
        |
        v
SourceOccurrence selection
        |
        v
deterministic reference-marker routing
        |
        v
Effective MentionCandidates
        |
        v
exact-target reference challenge
        |
        v
conservative specialist and Qwen reconciliation
        |
        v
ReferenceDecisions
```

The stage-local control path then applies the corrected evaluator and diagnostics-first verification.

That control path determines whether the next extraction boundary is ready for development.

It does not create or transform production extraction records.

The [Hybrid Pipeline architecture](2026-09-01-hybrid-intelligence-extraction-pipeline.md#current-implemented-boundary-architecture) defines each step and its authority boundary.

## Context & Problem

HSQ-6 removed open EventFrameDraft translation but left too much semantic work in two model calls.

The prior trigger task asked Qwen to discover, transcribe, identify, and label Events in one batch.

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

**Event trigger decision** means KoteKomi's final typed decision for one EventHeadCandidate.

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
2. Stanza and QANom propose source-bound EventHeadCandidate records.
3. Qwen answers one finite Semantic Route for one supplied candidate at a time.
4. KoteKomi reconciles those answers and constructs exact EventTriggerDraft records.
5. KoteKomi maps each trigger to exact head, expression, and support EvidenceTargets.
6. KoteKomi embeds those targets in one EventMention.
7. KoteKomi proposes the source-grounded Event before optional classification.
8. Later bounded tasks assign source-backed Event participants and presentation semantics.
9. KoteKomi sends only complete derived propositions through the support gate.
10. Event and standing-fact routes may both produce derived candidates from one SourceSegment.
11. KoteKomi gives event semantics ownership of source-bound event relations and retains non-event standing facts.
12. F-Coref proposes antecedent candidates, Qwen selects among a bounded source-valid catalog, and KoteKomi constructs the terminal reference decision.

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
- BTA-GOL-03: The validation catalog contains exactly twenty Anthropic intelligence items.
- BTA-GOL-04: Each item preserves complete authoritative source text, source digest, expected meaning, expected route, and task-allocation tags.
- BTA-GOL-05: Each catalog distinguishes representable items from typed ontology gaps.
- BTA-GOL-06: Evaluation reports exact expected and actual stage outcomes per item instead of only aggregate counts.
- BTA-GOL-07: Gold expectations remain fixed throughout each replay.
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
- BTA-BND-04A: The requested and accepted form is exactly `cN | status`.
- BTA-BND-04B: Model-visible task input lists every legal task-local output prefix and contains no abstract placeholder that can be mistaken for an output line.
- BTA-BND-04C: Qwen returns exactly one valid terminal judgment for every supplied candidate label.
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
- BTA-BND-15: Missing, malformed, unknown, and duplicate judgments remain visible, affect only their supplied candidate, and make the Preview partial.
- BTA-BND-16: Evaluation reports contract completeness over every supplied boundary candidate independently from Gold focus-item accuracy.

### Source-owned trigger occurrences

- BTA-TRG-01: KoteKomi deterministically derives ordered SourceOccurrence records from exact SourceSegment characters.
- BTA-TRG-02: Each SourceOccurrence contains a local occurrence ID, exact text, and half-open source range.
- BTA-TRG-03: Stanza and QANom propose fallible source-bound candidate evidence.
- BTA-TRG-04: Qwen answers one bounded Semantic Route for one supplied candidate.
- BTA-TRG-05: Qwen does not transcribe trigger text or create source ranges.
- BTA-TRG-06: KoteKomi validates each target-bound answer independently.
- BTA-TRG-07: An invalid answer leaves only its candidate unclassified and cannot erase valid sibling answers.
- BTA-TRG-08: KoteKomi constructs each EventTriggerDraft head from the selected SourceOccurrence and derives its exact expression under the pinned deterministic expression policy.
- BTA-TRG-08A: A nominal Event head with one directly attached `to`-marked infinitival clause retains that clause up to the first strong punctuation boundary.
- BTA-TRG-09: The Event trigger boundary TDD owns candidate routes and reconciliation rules.
- BTA-TRG-10: Reconciliation exposes rejected, accepted, failed, and unclassified outcomes.
- BTA-TRG-11: Each route uses one finite answer under a two-token transport cap.

### Optional governed semantic enrichment

- BTA-EVT-01: When classification is requested, one frame-selection task receives one trigger and only the governed frame ID and definition catalog.
- BTA-EVT-02: Optional frame selection returns one supplied frame ID or `unresolved`.
- BTA-EVT-03: A selected optional frame receives one separate binary frame-fit challenge using only the source, trigger expression, frame ID, and governed definition.
- BTA-EVT-04: A failed frame-fit challenge produces an `unmapped_frame` SemanticCoverageGap without removing the source-grounded Event.
- BTA-EVT-05: When governed role enrichment is requested, one role-selection task receives one selected frame, one supplied target role, the complete sibling-role catalog, prior sibling selections, exact source, local candidates, and validated reference metadata.
- BTA-EVT-06: Required roles run first in governed declaration order and optional roles run afterward in governed declaration order.
- BTA-EVT-07: Every selected role span is the smallest meaning-complete source expression for that role.
- BTA-EVT-08: One role result cannot overwrite another valid role result.
- BTA-EVT-09: One event-presentation task receives the selected trigger, frame, and source-backed role selections.
- BTA-EVT-10: The presentation task does not select the frame or role targets again.
- BTA-EVT-11: KoteKomi constructs every event, role assignment, qualifier, EvidenceTarget, identifier, and digest.
- BTA-EVT-12: A model failure affects only the bounded decision that used that model call.
- BTA-EVT-13: `unresolved` frame selection, rejected frame fit, and invalid required frame-fit output cannot silently select a governed frame.
- BTA-EVT-14: KoteKomi constructs and proposes the source-grounded Event before optional governed enrichment.
- BTA-EVT-15: Classification status cannot control Event identity, admission, review, or default Wiki presentation.
- BTA-EVT-16: Missing classification means classification was not requested, not that the Event is absent.

### Optional proposition admission

- BTA-SUP-01: KoteKomi deterministically renders one CompleteProposition from the complete governed event.
- BTA-SUP-02: Qwen judges the CompleteProposition against exact source text once.
- BTA-SUP-03: NLI independently challenges the same CompleteProposition.
- BTA-SUP-04: Component SemanticStatements remain inspectable deterministic explanations.
- BTA-SUP-05: Component statements do not receive separate model calls and cannot independently veto the CompleteProposition.
- BTA-SUP-06: A separately admitted enriched Assertion requires one supported PropositionDecision,
  complete required roles, and no hard source-alignment gap.

### Parallel semantic routes

- BTA-ROU-01: Event-trigger presence does not suppress standing-fact semantic qualification.
- BTA-ROU-02: Event and standing-fact routes can both produce derived candidates from one mixed SourceSegment.
- BTA-ROU-03: A standing-fact proposal selects its relation as a supplied contiguous SourceOccurrence range.
- BTA-ROU-04: KoteKomi reconstructs standing relation text and offsets from authoritative source characters.
- BTA-ROU-05: A standing relation that overlaps a validated event trigger in the same SourceSegment is held as `event_route_required`.
- BTA-ROU-06: Non-overlapping standing facts in a mixed SourceSegment remain eligible.
- BTA-ROU-07: A standing fact cannot replace a bounded or unmapped event merely because the standing route also found it.
- BTA-ROU-08: Each standing-fact candidate label includes a source-occurrence locator so repeated names remain distinguishable.
- BTA-ROU-09: Literal standing-fact objects are selected from supplied SourceOccurrences and reconstructed by KoteKomi.
- BTA-ROU-10: KoteKomi holds a standing relation that consumes a MentionCandidate boundary rather than repairing model output.
- BTA-ROU-11: KoteKomi renders an eligible standing CompleteProposition from its ordered source-bound component ranges.
- BTA-ROU-12: KoteKomi may complete a post-relation literal's left boundary from authoritative characters when Qwen supplies only its terminal source anchor and no clause boundary intervenes.

### Specialist reference boundary

- BTA-REF-01: F-Coref remains a fallible antecedent candidate proposer.
- BTA-REF-02: KoteKomi validates every F-Coref span against authoritative source characters.
- BTA-REF-03: A bounded reference challenge receives the target and an ordered catalog of task-local `aN` labels bound to source-valid candidate IDs.
- BTA-REF-03A: Each catalog entry supplies the candidate's exact expression and bounded source wording immediately before and after that occurrence.
- BTA-REF-03B: Two occurrences with the same expression remain distinguishable by their task-local labels and occurrence context.
- BTA-REF-03C: When F-Coref proposes exactly one source-valid candidate, Qwen first receives a binary validation task containing only that candidate.
- BTA-REF-04: Qwen returns one supplied task-local `aN` label, `ambiguous`, or `unresolved`.
- BTA-REF-04A: Qwen performs only semantic antecedent selection for the visibly delimited target reference.
- BTA-REF-04B: Binary specialist validation returns exactly `supported`, `unsupported`, or `unclear` plus one diagnostic reason.
- BTA-REF-04C: A source-valid F-Coref candidate becomes resolved only after Qwen returns `supported` for that candidate.
- BTA-REF-04D: An `unsupported` or `unclear` specialist validation may trigger one separate contrastive-selection task over the complete bounded catalog, including the specialist candidate.
- BTA-REF-04E: Agreement between the specialist proposal and contrastive selection resolves that candidate.
- BTA-REF-04F: An `unsupported` specialist validation followed by one different contrastive selection resolves the selected source-valid candidate.
- BTA-REF-04G: An `unclear` specialist validation followed by a different contrastive selection remains ambiguous.
- BTA-REF-04H: A malformed or failed specialist validation terminates as a typed non-resolution and cannot be bypassed by contrastive selection.
- BTA-REF-05: The model-visible output contains only one supplied task-local label or a typed non-resolution plus one diagnostic explanation.
- BTA-REF-06: KoteKomi maps a valid task-local label to its source-valid candidate ID and constructs the terminal ReferenceDecision.
- BTA-REF-06A: The exact label-to-candidate mapping, parsed model selection, mapped candidate selection, and model-output digest remain in stage evidence.
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

The v5 correction hardens the literal boundary-adjudication output contract without changing semantic
scope.

The v4 replay showed that the strict parser protected integrity while the model-visible abstract schema
caused collateral recall loss that focus-item evaluation did not expose.

Qwen copied the abstract `<supplied cN>` placeholder as an actual candidate label in four adjudication
groups across three unique SourceSegments.

Those groups left eleven otherwise meaningful non-focus candidates unresolved while the forty-item
focus score still reached thirty-nine of forty.

The affected SourceSegments contain AMO-10 and AMO-11, AMO-16 and AMO-17, and ANT-12 and ANT-13.

The v5 task renders only the actual legal output prefixes, such as `c1 |` and `c2 |`, and contains no
abstract candidate-label placeholder.

The v5 parser accepts only `cN | status` and does not repair the historical placeholder or the redundant
`candidate:` spelling.

KoteKomi still isolates malformed lines, preserves valid siblings, maps missing or duplicated labels to
explicit unresolved candidates, and marks the Preview partial.

The v5 evaluator adds an all-candidate contract-completeness gate alongside the existing focus-item
quality checks.

Contract completeness requires exactly one valid `complete`, `incomplete`, or `unclear` judgment for
every candidate actually supplied to Qwen.

The gate does not claim that non-Gold candidate judgments are semantically correct; it proves that no
candidate disappeared because the transport contract was malformed.

The three affected SourceSegments run first, followed by the unchanged twenty-item development and
twenty-item validation partitions.

The v5 correction accepts only a result that retains thirty-nine of forty Gold items, keeps AMO-12 as
the sole explicit reference ambiguity, and reports complete boundary-contract coverage with no rejected
boundary lines.

Source-alias rescue and selective interpretation remain measured but inactive.

The v5 diagnostic proved the boundary-output correction independently of downstream stages.

All eighteen candidates supplied across seven ambiguous components received valid terminal judgments,
with no rejected, duplicate, unknown, or unresolved boundary output.

The same diagnostic exposed an adjacent reference-contract defect before the full replay.

Qwen selected `Claude` correctly in its explanation but mistyped one character while reproducing the
opaque `cfa_...` candidate ID, so KoteKomi correctly rejected the out-of-catalog result.

The v6 correction gives Qwen only short task-local antecedent labels such as `a1` and `a2`.

KoteKomi deterministically binds those labels to source-valid CoreferenceAntecedentCandidate IDs before
the call, maps a valid returned label after the call, and preserves both forms in ExtractionStageTrace
evidence.

The model-visible prompt contains only the semantic reference-selection task and its literal output
contract; deterministic KoteKomi responsibilities are not presented as model prohibitions.

The boundary-adjudication prompt likewise retains only task-relevant semantic rules and the positive
literal output contract established by v5.

An unknown, malformed, or mistyped task-local label remains a typed invalid challenge and cannot become
a resolved ReferenceDecision.

The v6 diagnostic proved the short-label transport and trace contract, but it did not pass the semantic
gate.

Qwen returned valid label `a3`, which KoteKomi mapped exactly to `Anthropic`, while F-Coref proposed the
nearer `Claude` occurrence for `if it had`.

KoteKomi correctly retained both alternatives as `ambiguous`, so the failed experiment did not create a
false resolution.

The exact v6 input exposed two missing task inputs.

The candidate catalog contained two different `Claude` occurrences but rendered both as only
`"Claude"`, making their labels semantically indistinguishable, and the prompt asked for a choice without
giving the small model a bounded method for interpreting omitted repeated words.

The v7 diagnostic rendered bounded source wording around every candidate occurrence and asked Qwen to
compare candidate substitutions in the target's local clause after restoring source-supported ellipsis.

That hypothesis failed.

Qwen returned valid label `a2` for `Minab school strike`; its explanation restated the broad source topic
instead of applying the requested substitution to the grammatical subject of `had`.

The v8 correction removes the unproven multi-step linguistic procedure and restores the concise semantic
antecedent instruction that selected `Claude` in v5.

It retains the short task-local labels and bounded occurrence context, so the semantic task no longer
requires opaque-ID transcription and repeated expressions remain distinguishable.

The v8 control also failed.

Qwen again returned valid label `a2` for `Minab school strike`, despite correctly describing the broader
`use of Claude in connection with the Minab school strike` in its reason.

The repeated valid-but-wrong choices under v6, v7, and v8 falsify prompt-only repair for this
seven-candidate task.

The v9 correction changes task allocation instead of adding instructions.

When F-Coref supplies exactly one source-valid candidate, Qwen receives one binary claim: whether the
target refers to that candidate.

Only `supported` resolves it.

An explicit `unsupported` or `unclear` result permits one contrastive choice over the complete bounded
catalog, including the specialist candidate.

Agreement between the specialist and the contrastive choice resolves the reference.

The v10 policy preserved a different contrastive choice as ambiguous.

When F-Coref abstains or proposes more than one distinct candidate, the existing bounded selection task
remains available.

KoteKomi continues to own source ranges, candidate identity, label mapping, validation, disagreement
handling, and the terminal ReferenceDecision.

The v9 three-item diagnostic passed its intended contract.

For AMO-16 and AMO-17, F-Coref supplied the exact `Claude` occurrence, Qwen returned `supported` from
the one-candidate validation task, and KoteKomi resolved both items without invoking alternative
selection.

For AMO-12, Qwen rejected F-Coref's `Trump` proposal and selected `Amodei` from the remaining catalog;
KoteKomi retained the model disagreement as the one expected explicit ambiguity.

All three model executions used valid literal output, all supplied mention-boundary candidates received
terminal judgments, and the diagnostic created no ProposedChange or accepted Ledger write.

The first v9 twenty/twenty replay rejected the correction because it passed only thirty-eight of forty
items.

AMO-12 remained the expected explicit ambiguity, but validation item ANT-01 regressed.

Its source says that the Department of Defense conflicted with `the artificial intelligence company
Anthropic over the use of its products`.

F-Coref selected `Anthropic`, but the isolated binary task returned `unsupported` and incorrectly said
that `its products` belonged to the Department of Defense.

The alternative-only task then received only the Department of Defense and returned `unresolved` while
explaining that either organization remained possible.

In the retained v4 evidence, a single contrastive task over both candidates selected `Anthropic`
correctly.

The v10 correction therefore keeps one-candidate validation as the successful fast path but replaces
alternative-only fallback with one complete-catalog contrastive selection.

This tests the observed hypothesis that Qwen needs an explicit contrast for ANT-01 while preserving the
successful one-candidate result for AMO-16 and AMO-17.

The v10 four-item diagnostic passed this contract.

For ANT-01, the binary task repeated its incorrect `unsupported` judgment, but the complete-catalog
contrastive task selected `Anthropic`; KoteKomi resolved the reference because that final selection
agreed with F-Coref.

AMO-16 and AMO-17 still resolved `it` to `Claude` through one supported validation each without
fallback.

For AMO-12, Qwen rejected F-Coref's `Trump` proposal and selected `Amodei` contrastively.

The v10 policy preserved that processor disagreement as ambiguity.

All five model executions produced valid literal output and causal trace records. The diagnostic
retained a complete boundary contract and created no ProposedChange or accepted Ledger write.

The fresh v10 twenty/twenty replay then passed its acceptance gates with thirty-nine of forty Gold
items.

The development partition passed nineteen of twenty and the locked validation partition passed all
twenty. AMO-12 was the sole hold, at reference resolution, where the specialist/Qwen disagreement
remained explicitly ambiguous.

Across both partitions, all sixty-five supplied boundary candidates received terminal judgments. The
ten semantic-reference traces retained twelve causally ordered model executions: seven specialist
validations, two complete-catalog contrastive selections, and three ordinary catalog selections. Every
literal output parsed, no model-visible input exposed opaque candidate IDs, and input, output, and
terminal-decision task order matched.

The replay created zero ProposedChanges and zero accepted Ledger writes.

Human review later rejected the AMO-12 hold because the authoritative SourceSegment clearly assigns
`his hiring of Biden officials` to Amodei.

The v11 policy treats F-Coref as a proposer rather than a semantic veto.

When one bounded task explicitly rejects its candidate and one complete-catalog task selects a
different exact candidate, KoteKomi resolves the selected candidate and retains both executions.

An `unclear` validation still preserves a different contrastive choice as ambiguous.

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
pinned linguistic annotations
          |
          v
KoteKomi EventHeadCandidate catalog
          |
          v
bounded Qwen Semantic Routes
          |
          v
deterministic reconciliation
          |
          v
exact EventTriggerDraft
          |
          +--> source-grounded Event proposal
          |
          +--> optional Qwen frame selection
                       |
                       v
             Qwen frame-fit challenge
                       |
                       v
             Qwen role selection
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
             optional enrichment admission
```

F-Coref and Qwen have separate responsibilities.

F-Coref proposes which source-valid antecedents merit consideration.

Qwen judges the meaning of one reference among those supplied choices.

KoteKomi owns the resulting range, identity, decision record, and trace.

## Data Model

`SourceOccurrence` is a derived Application DTO with local ID, exact text, start, and end.

`EventHeadCandidate` records one exact supplied SourceOccurrence and its pinned linguistic annotation.

`EventTriggerDecision` binds one invocation target to one `EVENT` or `NOT_EVENT` answer and its task and ModelRun identities.

`EventRoutingJudgment` binds one finite Semantic Route answer to one EventHeadCandidate.

KoteKomi derives the diagnostic event label from the pinned linguistic lemma.

`MentionOccurrenceSelection` contains one supplied SourceSegment label and the first and last supplied SourceOccurrence IDs of one mention expression.

`BoundaryCandidateJudgment` contains one task-local candidate label and one of `complete`, `incomplete`, or `unclear`.

`MentionBoundaryAdjudication` records its parent boundary decision, source digest, mapped judgments, rejected lines, task identity, run identity, and trace identity.

`StageLocalEvaluatorCorrection` records the parent evaluator evidence, original expectation, accepted exact source boundary, observed output, classification, and rationale.

`EventHeadAnswer` contains KoteKomi's strict `EVENT` or `NOT_EVENT` mapping of one model-visible `E` or `N` answer.

`EventFrameSelection` contains one governed frame ID or `unresolved` and one reason.

`EventFrameFitDecision` contains one binary `fits` value and one reason.

`EventPresentationSelection` contains polarity, modality, attribution selection, and independently parsed optional qualifiers.

`SemanticReferenceChallenge` records one selected task-local antecedent label or a typed non-resolution.

`SemanticReferenceCandidateLabelBinding` records the ordered task-local label and its source-valid
candidate ID; the exact model-visible task records the bounded occurrence context rendered beside it.

`SemanticReferenceCandidateValidation` records one `supported`, `unsupported`, or `unclear` judgment for
one exact source-valid specialist candidate.

`SemanticReferenceModelExecutionReference` records every validation and selection task/run pair in
causal order on the terminal SemanticReferenceDecision.

`StandingFactDraft` contains a source-bound relation range reconstructed from supplied SourceOccurrences.

EventTriggerDraft feeds a source-grounded Event with one embedded EventMention.

EventTypeAssignment, EventSemanticDraft, CompleteProposition, and PropositionDecision remain optional
derived enrichment.

EvidenceTarget, ProposedChange, and accepted Ledger records remain downstream contracts.

## Behavior & Domain Rules

- BTA-RUL-01: A local model never creates a canonical identifier, digest, source offset, or Ledger record.
- BTA-RUL-02: Model tasks choose only among KoteKomi-supplied IDs or typed non-resolution values.
- BTA-RUL-03: A source-backed meaning outside the governed profile is not evidence of model failure.
- BTA-RUL-04: An ontology gap cannot be silently mapped to the nearest frame.
- BTA-RUL-05: A regression on an already demonstrated Gold item blocks acceptance.
- BTA-RUL-06: Each frozen replay evaluates validation only after development behavior is fixed.
- BTA-RUL-06A: A new independently reviewed corpus is required to measure unseen generalization.
- BTA-RUL-07: Retrieval confidence, specialist score, model confidence, and evidence confidence remain distinct.
- BTA-RUL-08: All intelligence remains pending until human review.
- BTA-RUL-09: Deterministic boundary reconciliation remains unchanged by semantic adjudication.
- BTA-RUL-10: `incomplete`, `unclear`, and unresolved candidates remain inspectable but do not route downstream.
- BTA-RUL-11: Optional ontology classification cannot veto a source-grounded Event.

## Acceptance Criteria

- AC-BTA-GOL-01: Catalog tests prove twenty Amodei and twenty Anthropic items with exact source digests.
- AC-BTA-MEN-01: Tests prove Qwen can select both occurrences of the same literal by different supplied occurrence IDs and KoteKomi reconstructs both exact source ranges.
- AC-BTA-MEN-02: Tests prove the mention-selection prompt and output contract contain no ontology-kind field and require no copied source text.
- AC-BTA-MEN-03: Tests prove the model-visible catalog uses SourceSegment-local `oN` IDs, contains no redundant `sN:oN` identifiers, and rejects an `sN` value supplied as an occurrence ID.
- AC-BTA-BND-01: Parser tests prove only `cN | status` is accepted while malformed, historical-placeholder, redundant-prefix, unknown, duplicate, and omitted lines leave valid sibling judgments intact.
- AC-BTA-BND-02: Tests prove `Amodei` remains effective beside incomplete `Amodei wrote` and longer clause fragments.
- AC-BTA-BND-03: Tests prove `Anthropic` remains effective beside incomplete `Anthropic's technology achieved`.
- AC-BTA-BND-04: Tests prove `Anthropic` and complete `Anthropic's services` can both remain effective.
- AC-BTA-BND-04A: Prompt-contract tests prove the possessor rule uses a generic example and contains no diagnostic-catalog entity names.
- AC-BTA-BND-04B: Tests prove the proper-name possessor is absent from model-visible candidate choices, remains effective, and is separately identified in the adjudication trace.
- AC-BTA-BND-04C: Tests prove Qwen can reject an attached predicate in the residual candidate without vetoing the exact possessor boundary.
- AC-BTA-BND-05: Tests prove deterministic resolved and uncontested components bypass the model task.
- AC-BTA-BND-06: Tests prove failed and over-limit adjudications remain partial and create no accepted state.
- AC-BTA-BND-07: Tests inspect exact model-visible input, raw output, mapped judgments, rejected lines, and lineage.
- AC-BTA-BND-08: Tests prove model-visible input lists each actual legal `cN |` prefix exactly once and contains no abstract placeholder.
- AC-BTA-BND-09: Tests prove each supplied candidate has exactly one terminal model judgment or one explicit unresolved outcome with diagnostics.
- AC-BTA-TRG-01: Tests prove exact source-bound candidate and EventTriggerDraft ranges.
- AC-BTA-TRG-02: Tests prove one invalid candidate answer does not erase a valid sibling decision.
- AC-BTA-TRG-03: Fresh phase reports reproduce all eighty-seven reviewed Gold Events exactly.
- AC-BTA-EVT-01: Tests prove optional frame selection input excludes the role catalog.
- AC-BTA-EVT-02: Tests prove a mismatched selected frame is rejected by the binary frame-fit challenge.
- AC-BTA-EVT-03: Tests prove every role task contains exactly one target role plus sibling definitions and prior sibling selections.
- AC-BTA-EVT-04: Tests prove an optional assessment and publication outlet can be retained without changing required roles.
- AC-BTA-EVT-05: Tests prove complete publication, meeting, and characterization targets are not truncated to syntactically adjacent fragments.
- AC-BTA-EVT-06: Tests prove classified and unclassified enrichment produce the same source-grounded Event proposal bytes.
- AC-BTA-SUP-01: Tests prove one supported CompleteProposition is not vetoed by an auxiliary attribution explanation.
- AC-BTA-ROU-01: Tests prove one mixed SourceSegment can retain both an event and a non-duplicate standing fact.
- AC-BTA-ROU-02: Tests prove an event-overlapping standing relation is held before it can flatten the event.
- AC-BTA-ROU-03: `AMO-07` reaches standing-fact qualification as `Anthropic's strategy has mirrored Amodei's views toward Trump.` without suppressing its sibling Events.
- AC-BTA-REF-01: Tests prove F-Coref cannot resolve `his` when Qwen selects a different candidate or returns ambiguity.
- AC-BTA-REF-02: Tests prove an F-Coref abstention still permits a bounded challenge over preceding candidates.
- AC-BTA-REF-03: Tests prove an unresolved generic reference cannot create a typed Entity or Wiki page.
- AC-BTA-REF-04: Tests prove a deterministic `the  company's` marker reaches reference resolution without a MentionInterpretation.
- AC-BTA-REF-05: Tests inspect a challenge task containing distinct before-target, target-reference, and after-target fields.
- AC-BTA-REF-06: Tests prove disagreement between a non-empty F-Coref proposal and Qwen's selection produces `ambiguous` with both source-valid spans.
- AC-BTA-REF-07: Tests prove model-visible antecedents use ordered task-local `aN` labels and contain no opaque candidate IDs.
- AC-BTA-REF-08: Tests prove KoteKomi maps a valid `aN` selection to the exact source-valid candidate ID and records both the label and mapping in stage evidence.
- AC-BTA-REF-09: Tests prove an unknown or malformed task-local label becomes an invalid challenge rather than a guessed reference.
- AC-BTA-REF-10: Tests prove repeated identical candidate expressions have distinct labels and bounded source-occurrence context.
- AC-BTA-REF-11: Tests prove candidate-occurrence context and concise semantic-antecedent selection remain model guidance while source ranges and terminal decisions remain deterministic KoteKomi outputs.
- AC-BTA-REF-12: Tests prove a sole F-Coref proposal receives a one-candidate binary validation task rather than a seven-way selection task.
- AC-BTA-REF-13: Tests prove `supported` resolves only the validated specialist candidate.
- AC-BTA-REF-14: Tests prove `unsupported` followed by one different contrastive selection resolves only that selected exact source candidate.
- AC-BTA-REF-15: Tests prove `unclear` followed by a different contrastive selection remains ambiguous with both source spans.
- AC-BTA-REF-16: Tests prove a failed or malformed validation cannot invoke fallback or resolve a reference.
- AC-BTA-REF-17: Tests prove fallback includes the specialist and all remaining bounded candidates in one contrastive task.
- AC-BTA-REF-18: Tests prove specialist and contrastive agreement resolves the specialist candidate.
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
- AC-BTA-SLE-15: The v5 diagnostic covers the four malformed adjudication groups across the three affected SourceSegments and reports complete candidate-contract coverage.
- AC-BTA-SLE-16: The v5 phase reports count supplied candidates, valid terminal judgments, deterministic completions, unresolved candidates, duplicate labels, unknown labels, and rejected lines once per unique adjudication.
- AC-BTA-SLE-17: The v5 replay passes thirty-nine of forty items with AMO-12 as the sole hold at reference resolution.
- AC-BTA-SLE-18: The v5 replay has zero rejected boundary lines, zero contract-caused unresolved candidates, zero ProposedChanges, and zero accepted Ledger records.
- AC-BTA-SLE-19: The v5 comparison records source-alias rescue and selective interpretation as measured but not activated.
- AC-BTA-SLE-20: The v6 diagnostic proves valid task-local-label transport and exact mapping while safely retaining the observed `Anthropic`/`Claude` disagreement as ambiguous.
- AC-BTA-SLE-21: The v7 diagnostic preserves exact occurrence context and mapping but safely rejects the observed `Minab school strike`/`Claude` disagreement as ambiguous.
- AC-BTA-SLE-22: The v8 diagnostic proves the concise control still selects `Minab school strike` rather than the source-supported `Claude` occurrence.
- AC-BTA-SLE-23: The v8 diagnostic preserves valid input, output, and mapping evidence while safely retaining the repeated `Minab school strike`/`Claude` disagreement as ambiguous, thereby falsifying prompt-only repair.
- AC-BTA-SLE-24: The v9 diagnostic resolves the Minab reference through binary validation and preserves AMO-12 as an explicit specialist/alternative disagreement.
- AC-BTA-SLE-25: The rejected v9 replay preserves complete evidence for thirty-eight of forty passing items and identifies ANT-01 as a validation regression caused by alternative-only fallback.
- AC-BTA-SLE-26: The v9 replay creates zero ProposedChanges and zero accepted Ledger records.
- AC-BTA-SLE-27: The retained v10 diagnostic passes ANT-01, AMO-16, and AMO-17 while recording the former AMO-12 specialist/contrastive disagreement.
- AC-BTA-SLE-28: The retained v10 replay preserves the historical thirty-nine-of-forty result against its then-current Gold.
- AC-BTA-SLE-29: The v10 replay creates zero ProposedChanges and zero accepted Ledger records.
- AC-BTA-SLE-30: Current Gold requires AMO-12 `his` to resolve to the exact Amodei occurrence.
- AC-BTA-SLE-31: A v11 focused replay resolves AMO-12 while retaining the rejected F-Coref proposal and both Qwen executions.
- AC-BTA-SLE-32: A v11 development-plus-validation replay passes forty of forty current Gold items without a wrong forced reference.
- AC-BTA-SLE-33: The v11 replay creates zero ProposedChanges and zero accepted Ledger records.

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

Stop if validation Anthropic quality regresses while Amodei quality improves.

Stop if a model or specialist result bypasses ProposedChange review into accepted Ledger state.
