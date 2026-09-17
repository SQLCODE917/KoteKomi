# Hybrid Intelligence Extraction Pipeline

- Status: Design accepted for incremental implementation
- Program ID: `hybrid-pipeline`
- Parent: [Candidate Ingestion Review Program](2026-08-24-candidate-ingestion-review-program.md)
- Architecture envelope: [Staged Model Extraction](2026-07-11-staged-model-extraction.md)
- First deliverable: [HP-1 Hybrid Mention Interpretation MVP](2026-09-01-hybrid-mention-interpretation-mvp.md)
- Document orchestration baseline: [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Document orchestration evaluation: [HP-8 Document Orchestration Evaluation](2026-09-03-hp8-document-orchestration-evaluation.md)
- Standing-fact extension: [HP-10 Paragraph Standing Facts MVP](2026-09-05-paragraph-standing-facts-mvp.md)
- Semantic quality follow-up: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Current evaluation contract: [Source-Grounded Evaluation Cutover](2026-09-13-source-grounded-evaluation-cutover.md)
- Current Event boundary: [SourceOccurrence to Event Trigger Boundary](2026-09-10-source-occurrence-event-trigger-boundary.md)
- Current Event admission: [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md)
- Current semantic-assignment experiment:
  [Event-Entity Connection Experiment](2026-09-12-event-entity-connection-experiment.md)
- Supersedes: [Model and Ontology Boundary Program](2026-08-25-model-ontology-boundary-program.md)
- Supersedes: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Supersedes: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Supersedes: [Organization Mention Reconciliation Program](2026-08-28-organization-mention-reconciliation-program.md)

## Context and problem

KoteKomi builds a local-first intelligence Ledger from authoritative Sources.

KoteKomi uses specialized models and a local language model to interpret source text.

Earlier experiments assigned overlapping semantic work to Qwen2.5, GLiNER, and ReFinED.

GLiNER and Qwen2.5 propose useful but incomplete Organization spans.

Deterministic boundary rules resolve safe proposal conflicts without losing candidate evidence.

ReFinED identifies known entities quickly and consistently.

ReFinED does not apply KoteKomi's contextual Organization policy.

Qwen2.5 interprets source context better than ReFinED.

Qwen2.5 also produces ambiguous and invalid outputs in bounded qualification tasks.

The current Pipeline assigns one bounded responsibility to each model and deterministic component.

The Pipeline preserves each intermediate decision as derived evidence.

The Pipeline gives only KoteKomi authority to construct records and change Ledger state.

### Program statement

```text
authoritative SourceSegment
    -> SourceOccurrences
    -> source-valid MentionCandidates
    -> contextual MentionInterpretations
    -> ReferenceDecisions
    -> EntityLinkCandidates
    -> EventHeadCandidates
    -> EventTriggerDrafts
    -> source-grounded Events with EventMentions
    -> experimental source-backed Event-entity connections
    -> optional Event type assignments
    -> later source-backed semantic assignments
    -> ProposedChanges
    -> reviewer decision
    -> accepted Ledger records
```

## Terms

**MentionObservation** records one proposed source span, producer identity, and type hints.

**SourceOccurrence** means one exact ordered token-like range in a SourceSegment.

**MentionCandidate** means one source-valid span that retains every MentionObservation.

**Effective MentionCandidate** means one deterministically accepted or semantically complete MentionCandidate.

**MentionInterpretation** means one contextual judgment about a MentionCandidate.

**ReferenceDecision** means one resolved, ambiguous, or unresolved treatment of a source expression.

**CoreferenceObservation** means one fallible specialist proposal over exact source spans.

**EntityLinkCandidate** means one external identity proposed for a specific MentionCandidate.

**OntologyGuidelineCard** means one bounded set of definitions and examples for a model task.

**OntologySlice** means the entity kinds, frame types, roles, and predicates for one task.

**EventTriggerDraft** means one exact source trigger with one diagnostic open event label.

**EventHeadCandidate** means one source-bound verb or eventive noun selected for bounded semantic review.

**Routing Judgment** means one finite semantic answer bound to one EventHeadCandidate and one ModelRun.

**EventMention** means one Event link to exact head, expression, and support EvidenceTargets.

**Event Type Assignment** means optional derived classification under one pinned vocabulary.

**EventSemanticDraft** means optional derived enrichment under the governed event profile.

**SupportJudgment** means one semantic judgment about direct source support for a KoteKomi-constructed CompleteProposition.

**HybridExtractionPreview** means derived evidence from an incomplete Hybrid Pipeline run.

The HybridExtractionPreview cannot authorize a ProposedChange or an accepted Ledger write.

## User outcome

A user can ingest one document and receive a reviewable candidate change set.

Each candidate record traces to exact source text and every contributing model run.

The user can distinguish model ambiguity from invalid output and deterministic rejection.

The user can inspect why one source expression received its contextual type and role.

The user can review unresolved identities and references without losing source evidence.

Only an explicit review decision changes accepted Ledger state.

## Invariable decisions

### Authority

The Archive and accepted DocumentRepresentationBundle remain authoritative for source content.

The Ledger remains authoritative for accepted intelligence and review history.

Every model input comes from one verified ContextManifest.

Every model-visible source span maps to exact authoritative characters.

Every model output remains non-authoritative until KoteKomi validates and maps it.

KoteKomi derives all source offsets, record IDs, digests, and storage references.

KoteKomi creates all Domain records and ProposedChanges.

A reviewer remains the only actor that accepts model-derived intelligence.

### Model responsibilities

| Component | Responsibility | Output authority |
| --- | --- | --- |
| GLiNER | Propose broad source spans and type hints. | Fallible derived evidence. |
| F-Coref | Propose antecedent candidates over exact source spans. | Fallible derived evidence. |
| ReFinED | Propose external identities for specific mentions. | Fallible derived evidence. |
| Stanza | Annotate exact tokens, lemmas, parts of speech, and dependencies. | Fallible derived evidence. |
| QANom | Score source-bound common nouns as nominal Event candidates. | Fallible derived evidence. |
| Qwen2.5 | Answer one bounded semantic question about supplied source-valid choices. | Fallible derived evidence. |
| NLI challenger | Challenge one optional enriched CompleteProposition against exact source text. | Fallible derived evidence. |
| KoteKomi | Validate source characters, references, ontology rules, and state changes. | Deterministic project authority. |
| Reviewer | Accept, reject, or edit one ProposedChange. | Human review authority. |

The Pipeline does not convert a model score into evidence confidence.

The Pipeline does not use model voting as an acceptance rule.

The Pipeline retains NIL, ambiguous, unresolved, and abstained outcomes.

The Pipeline preserves every failed model attempt and complete observable output.

### Ontology responsibilities

One versioned ontology profile defines KoteKomi's entity kinds and relationship meanings.

The Application Layer selects one OntologySlice for each model task.

The Application Layer derives each OntologyGuidelineCard from that OntologySlice.

The Application Layer validates model-derived structures against the complete ontology profile.

An external knowledge-base type does not override a contextual MentionInterpretation.

Ontology conformance does not prove that source text supports a claim.

Textual support and ontology conformance remain separate validation results.

### Evidence and replay

Every stage emits one versioned ExtractionStageTrace.

Every model stage references one immutable ExtractionTask and ModelRun.

Every trace records exact input identities, complete output identities, and parent traces.

Every deterministic stage produces the same output for the same validated input.

Every derived preview remains rebuildable from the Ledger, Archive, and retained model outputs.

No later stage silently deletes an earlier candidate or disagreement.

## Current implemented boundary architecture

The production data path and stage-local verification path have different responsibilities.

The production path creates derived extraction evidence.

The verification path measures that evidence and authorizes development of the next boundary.

### Production data path

```text
authoritative SourceSegment
          |
          v
1. SourceOccurrence selection
          |
          v
Qwen + GLiNER + deterministic reference-marker observations
          |
          v
deterministic boundary reconciliation
          |
          +--> ambiguous component --> exact-target boundary challenge
          |                                  |
          +----------------------------------+
                                             v
                                  Effective MentionCandidates
                                             |
          +----------------------------------+--------------------+
          |                                                       |
          v                                                       v
2. deterministic reference routing                    contextual interpretation
          |                                                       |
          +---------------------------+---------------------------+
                                      v
                       aliases + bounded antecedent candidates
                                      |
                                      v
3. exact-target reference challenge
                                      |
                                      v
4. conservative specialist/LLM reconciliation
                                      |
                                      v
                              ReferenceDecisions
                                      |
                                      v
                           entity identity grounding
                                      |
                                      v
                              Event-trigger boundary
                                      |
                                      v
                          source-grounded Event
                                      |
                                      v
                   source-grounded Proposition Scope
                    (current bounded experiment only)
```

### Verification control path

```text
immutable mention and reference stage evidence
                    |
                    v
          5. corrected evaluator
                    |
                    v
     6. diagnostics-first verification
                    |
                    v
          Event-trigger Gold testing
```

The evaluator does not sit inside production ingestion.

The evaluator cannot create a MentionCandidate, ReferenceDecision, ProposedChange, or accepted Ledger record.

### 1. Select source occurrences and mention boundaries

The ContextPlanner supplies one authoritative paragraph through a verified ContextManifest.

KoteKomi divides that paragraph into authoritative SourceSegments.

KoteKomi derives ordered SourceOccurrence records from each SourceSegment without changing its characters.

Qwen2.5 selects contiguous occurrence ranges instead of copying source text or creating offsets.

GLiNER independently proposes source spans and type hints.

KoteKomi adds deterministic observations for exact reference markers.

KoteKomi validates every observation against authoritative characters and fuses equal spans.

KoteKomi resolves safe boundary cases deterministically.

Qwen2.5 judges only ambiguous overlap components using task-local candidate labels.

The result is one accountable set of Effective MentionCandidates.

### 2. Route deterministic references

KoteKomi marks exact reference expressions before contextual mention interpretation.

Those candidates bypass ontology-kind interpretation and enter reference resolution directly.

Ordinary Effective MentionCandidates receive contextual interpretation once per equal SourceSegment expression.

KoteKomi resolves unique explicit document aliases without a model call.

KoteKomi retains conflicting aliases as ambiguous and missing declarations as unresolved.

### 3. Challenge one exact reference target

F-Coref proposes source-valid antecedent candidates for one visibly delimited target.

KoteKomi supplements an empty specialist result with up to eight nearest same-paragraph candidates.

The bounded context stops at 1,024 input tokens.

Qwen2.5 sees task-local `aN` labels, exact expressions, and bounded occurrence context.

Qwen2.5 never receives canonical candidate IDs or creates source ranges.

A unique specialist candidate receives a binary validation task first.

An unsupported or unclear validation can trigger one complete-catalog contrastive task.

### 4. Reconcile specialist and semantic evidence conservatively

KoteKomi resolves a specialist candidate when Qwen2.5 validates it as supported.

KoteKomi also resolves it when a contrastive task independently selects the same candidate.

KoteKomi records specialist and Qwen2.5 disagreement as ambiguous.

KoteKomi records malformed, failed, and out-of-catalog output as typed non-resolution.

KoteKomi maps valid task-local labels back to exact source spans.

KoteKomi constructs every terminal ReferenceDecision and its causal execution lineage.

### 5. Evaluate the correct target

The stage-local evaluator binds each decision to the target MentionCandidate's SourceSegment identity.

Expanded reference context cannot replace that identity.

The evaluator compares actual and Gold outcomes one-to-one.

An evaluator mistake produces a pinned correction record instead of rewriting Gold or model output.

The evaluator reports contract completeness separately from focus-item accuracy.

### 6. Verify diagnostics before expanding scope

Each experiment runs a small diagnostic set before replaying the development and validation partitions.

Each report retains exact model-visible input, raw output, parsed output, deterministic mapping, and elapsed time.

Each rejected line and unresolved candidate remains visible.

The mention and reference replay currently passes thirty-nine of forty reviewed items.

The remaining item preserves one F-Coref and Qwen2.5 disagreement as an intended ambiguity.

The historical validation partition participated in iteration and no longer proves unseen generalization.

### 7. Propose external identities

ReFinED receives only specific MentionCandidates and their source context.

ReFinED returns ranked EntityLinkCandidates or NIL.

Qwen2.5 can rank only EntityLinkCandidates that KoteKomi supplies.

The Event-trigger stage preserves this grounding lineage without treating it as source authority.

### 8. Discover source-bound Event triggers

KoteKomi derives a fresh SourceOccurrence catalog from the same authoritative SourceSegment.

Stanza supplies source-bound grammatical annotations.

QANom proposes source-bound nominal Event candidates.

KoteKomi selects EventHeadCandidates and records a disposition for every SourceOccurrence.

Qwen2.5 answers one finite Semantic Route for one supplied candidate at a time.

KoteKomi reconciles those answers and creates exact EventTriggerDraft records.

The current Gold replay reproduces all eighty-seven reviewed Events exactly.

### 9. Construct source-grounded Events

KoteKomi maps each EventTriggerDraft head and expression to exact EvidenceTargets.

KoteKomi embeds those targets in one EventMention.

KoteKomi proposes an Event whose label preserves the exact source expression.

The Event does not require one governed frame.

Governed classification remains optional derived enrichment.

Later bounded tasks assign source-backed participants and other Event semantics.

The Event-Entity Connection experiment first tested a smaller assignment boundary.

KoteKomi supplies one source-grounded Event and one exact Actor or Organization candidate.

Qwen2.5 answers only whether that entity is involved in that Event.

KoteKomi maps the finite answer into a traced derived connection draft.

Its corrected evaluator scores every exact candidate occurrence directly against raw Gold.

The corrected evidence shows that identity-only summaries had hidden occurrence drift and false
positives.

The next bounded experiment therefore identifies the complete source-grounded proposition before
asking what role any entity plays.

KoteKomi proposes exact Event, entity, dependency, and governing-context fragments.

KoteKomi includes the exact Event expression deterministically.

Qwen2.5 receives one marked exact Fragment Candidate and answers only `Y`, `N`, or `U`.

KoteKomi maps that answer back to source offsets and constructs an ordered
SourceGroundedPropositionScope.

The scope preserves attribution, negation, modality, purpose, comparison, and temporal language as
source text.

For example, it preserves `Sacks stated` with the attributed Anthropic content instead of flattening
the proposition into an unqualified statement about Anthropic.

This experiment does not normalize a proposition, assign semantic roles, create ProposedChanges, or
change accepted Ledger state.

Semantic Argument Assignment remains blocked until the proposition-scope experiment passes its
reviewed development and validation catalog.

### 10. Create reviewable state

The Application Layer creates ProposedChanges from complete validated drafts.

The review flow remains the only path to accepted Ledger records.

## Incremental delivery

Each deliverable leaves KoteKomi working.

Corrective deliverables can replace obsolete derived stages when the accepted design requires a clean break.

Each deliverable produces evidence that defines the next TDD.

HP-1 through HP-8 provide the document-level Hybrid Pipeline path.

HP-9, HP-10, and the Hybrid Semantic Quality Program refine that path through bounded successors.

Each linked TDD owns the implementation and verification status of its boundary.

| Deliverable | User story | Precondition | Postcondition |
| --- | --- | --- | --- |
| [HP-1 Hybrid Mention Interpretation MVP](2026-09-01-hybrid-mention-interpretation-mvp.md) | A reviewer can inspect source-valid mentions and their separate contextual dimensions. | Authoritative paragraphs, proposer Adapters, ORG-R1 rules, and stage traces exist. | One paragraph produces a durable HybridExtractionPreview with no ProposedChange or accepted state change. |
| [HP-2 Document Reference Resolution](2026-09-01-hybrid-document-reference-resolution.md) | A reviewer can inspect explicit aliases and unresolved document references. | HP-1 preserves ontology-neutral MentionCandidates and interpretations. | The Pipeline emits ReferenceDecisions without inventing antecedents. |
| [HP-3 Entity Identity Grounding](2026-09-01-hybrid-entity-identity-grounding.md) | A reviewer can inspect known identity candidates only for specific mentions. | HP-2 identifies specific mentions and document-local aliases. | ReFinED emits ranked EntityLinkCandidates or NIL after contextual interpretation. |
| [HP-4 Event Frame Drafts](2026-09-01-hybrid-event-frame-drafts.md) | Historical: a reviewer could inspect source-grounded open event frames. | HP-3 preserved verified source lineage. | Superseded by HSQ-6 trigger discovery. |
| [HP-5 Atomic Claims and Ontology Validation](2026-09-02-hybrid-atomic-claims-ontology-validation.md) | Historical: a reviewer could inspect open-label atomic claims and ontology violations. | The retired HP-4 supplied EventFrameDrafts. | Superseded and removed by HSQ-6. |
| [HP-6 Qualified Event Semantics and Source Support](2026-09-02-qualified-event-semantics-source-support.md) | A reviewer can inspect governed events, qualified roles, explicit gaps, and independent source support. | Current HP-4 supplies exact source-bound EventTriggerDrafts. | KoteKomi emits typed semantic drafts and support judgments without changing accepted wiki state. |
| [HP-7 ProposedChange Integration](2026-09-03-hybrid-proposed-change-integration.md) | Historical: a reviewer could inspect governed HP-6 events through the existing review flow. | HP-6 supplied governed semantic drafts with complete source-support evidence. | Its Event admission gate is superseded by the Source-Grounded Event Boundary. |
| [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md) | A user receives one reviewable candidate change set from an ingested document. | HP-7 converts one HP-6 Preview into a reviewable proposal batch. | One ingestion runs the Hybrid Pipeline over its planned document scope and closes one IngestionChangeSet. |
| [HP-8.1 Mention Interpretation Batching](2026-09-03-hp8-mention-interpretation-batching.md) | Determine whether bounded interpretation batching can reduce model work without losing meaning. | HP-8 records complete model and paragraph evidence. | The rejected experiment preserves its full evidence and leaves production mention behavior unchanged. |
| [HP-8.2 Semantic Support Batching](2026-09-03-hp8-semantic-support-batching.md) | Determine whether support judgments can share one model request without losing statement-level meaning. | HP-8 supplies complete source-support and model evidence. | The rejected experiment preserves its full evidence and leaves production support behavior unchanged. |
| [HP-9 Evidence-Backed Document Entity Reconciliation](2026-09-04-evidence-backed-document-entity-reconciliation.md) | A reviewer sees one candidate identity with every source mention. | HP-8 accounts for every paragraph HP-7 Plan. | HP-8 submits one document-level proposal batch that uses reconciled Actor and Organization identities. |
| [HP-10 Paragraph Standing Facts MVP](2026-09-05-paragraph-standing-facts-mvp.md) | A reviewer receives source-bound standing relationships and literal attributes. | HP-8 and HP-9 submit reconciled event proposals from every paragraph. | Each eligible paragraph can add standing-fact proposals to the same reconciled review batch. |

## Validation strategy

HP-1 reuses source and boundary labels from the reviewed Organization mention catalogs.

HP-1 adds reviewed contextual labels for one fixed diagnostic subset.

Each later deliverable adds Gold labels only for its new semantic boundary.

Development and validation SourceSegment identities remain disjoint within one replay.

The current validation partition participated in iterative diagnosis.

A new independently reviewed corpus must test generalization beyond the current Gold catalog.

Each evaluation reports stage-local precision, recall, abstention, invalid output, latency, and stability.

Each evaluation reports exact source validity and trace completeness.

The complete feature requires zero accepted Ledger writes before review.

The complete feature requires complete source and model lineage for every ProposedChange.

## Research basis

[TAC Entity Discovery and Linking](https://catalog.ldc.upenn.edu/docs/LDC2019T02/guidelines/TAC_KBP_2015_EDL_Guidelines_V1.2.pdf)
separates mention discovery, contextual type, and identity linking.

[GLiNER](https://aclanthology.org/2024.naacl-long.300/) provides broad parallel span proposals.

[ReFinED](https://aclanthology.org/2022.naacl-industry.24/) provides mention and entity-link evidence.

[GoLLIE](https://openreview.net/pdf?id=Y3wpuxd7u9) demonstrates the value of explicit IE guidelines.

[DyGIE++](https://aclanthology.org/D19-1585/) connects entity, relation, event, and coreference context.

[SPIRES](https://pmc.ncbi.nlm.nih.gov/articles/PMC10924283/) combines schema prompts and ontology grounding.

[Prompt Me One More Time](https://aclanthology.org/2024.textgraphs-1.5/) separates extraction from ontology verification.

[Claimify](https://aclanthology.org/2025.acl-long.348/) evaluates claim coverage and decontextualization.

## Stop conditions

Stop when a model task requires canonical IDs or storage paths in its prompt.

Stop when one stage cannot preserve its exact input and complete observable output.

Stop when one ontology rule must infer textual support.

Stop when one model decision can write accepted Ledger state without review.

Stop when a new dependency cannot run on a supported local hardware profile.
