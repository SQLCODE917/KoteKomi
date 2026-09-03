# Hybrid Intelligence Extraction Pipeline

- Status: Design accepted for incremental implementation
- Program ID: `hybrid-pipeline`
- Parent: [Candidate Ingestion Review Program](2026-08-24-candidate-ingestion-review-program.md)
- Architecture envelope: [Staged Model Extraction](2026-07-11-staged-model-extraction.md)
- First deliverable: [HP-1 Hybrid Mention Interpretation MVP](2026-09-01-hybrid-mention-interpretation-mvp.md)
- Completed through: [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Latest evaluation: [HP-8 Document Orchestration Evaluation](2026-09-03-hp8-document-orchestration-evaluation.md)
- Next deliverable: Not yet designed; use the HP-8 whole-document evidence to select it.
- Supersedes: [Model and Ontology Boundary Program](2026-08-25-model-ontology-boundary-program.md)
- Supersedes: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Supersedes: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Supersedes: [Organization Mention Reconciliation Program](2026-08-28-organization-mention-reconciliation-program.md)

## Context and problem

KoteKomi builds a local-first intelligence Ledger from authoritative Sources.

KoteKomi uses specialized models and a local language model to interpret source text.

The current experiments assign overlapping semantic work to Qwen2.5, GLiNER, and ReFinED.

GLiNER and Qwen2.5 propose useful but incomplete Organization spans.

Deterministic boundary rules resolve safe proposal conflicts without losing candidate evidence.

ReFinED identifies known entities quickly and consistently.

ReFinED does not apply KoteKomi's contextual Organization policy.

Qwen2.5 interprets source context better than ReFinED.

Qwen2.5 also produces ambiguous and invalid outputs in bounded qualification tasks.

The new Pipeline assigns one bounded responsibility to each model and deterministic component.

The Pipeline preserves each intermediate decision as derived evidence.

The Pipeline gives only KoteKomi authority to construct records and change Ledger state.

### Program statement

```text
authoritative paragraph
    -> source-valid MentionCandidates
    -> contextual MentionInterpretations
    -> ReferenceDecisions
    -> EntityLinkCandidates
    -> EventFrameDrafts
    -> AtomicClaimDrafts
    -> validation and SupportJudgments
    -> ProposedChanges
    -> reviewer decision
    -> accepted Ledger records
```

## Terms

**MentionObservation** means one model's proposed source span and type hints.

**MentionCandidate** means one source-valid span that retains every MentionObservation.

**MentionInterpretation** means one contextual judgment about a MentionCandidate.

**ReferenceDecision** means one decision that links a source expression to a visible antecedent.

**EntityLinkCandidate** means one external identity proposed for a specific MentionCandidate.

**OntologyGuidelineCard** means one bounded set of definitions and examples for a model task.

**OntologySlice** means the entity kinds, frame types, roles, and predicates for one task.

**EventFrameDraft** means one model proposal for an event and its participant roles.

**AtomicClaimDraft** means one application-owned claim derived from validated model semantics.

**SupportJudgment** means one semantic judgment about direct source support for an AtomicClaimDraft.

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
| Qwen2.5 | Interpret context, references, frames, and source support. | Fallible derived evidence. |
| ReFinED | Propose external identities for specific mentions. | Fallible derived evidence. |
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

## End-to-end feature flow

### 1. Construct authoritative context

The ContextPlanner creates one ContextManifest from an authoritative paragraph.

The ContextManifest includes bounded structural and preceding context.

### 2. Propose source spans

GLiNER and Qwen2.5 produce independent MentionObservations.

The proposers use broad competing entity kinds instead of an Organization-only prompt.

### 3. Reconcile literal boundaries

The Application Layer validates every MentionObservation against source characters.

The Application Layer merges equal spans and applies named safe boundary rules.

The Application Layer preserves each unresolved overlap as ambiguous.

### 4. Resolve deterministic document references

The Application Layer identifies explicit long-form and abbreviation declarations.

The Application Layer records unique document-local aliases before semantic resolution.

### 5. Interpret each mention in context

Qwen2.5 judges referentiality, contextual kind, and discourse role separately.

The Application Layer retains an unclear value for each unresolved dimension.

### 6. Propose external identities

ReFinED receives only specific MentionCandidates and their source context.

ReFinED returns ranked EntityLinkCandidates or NIL.

Qwen2.5 can rank only EntityLinkCandidates that KoteKomi supplies.

### 7. Propose event frames

Qwen2.5 receives qualified mentions, resolved references, and one OntologySlice.

The Pipeline retains HP-3 lineage but does not send fallible EntityLinkCandidates to Qwen2.5.

HP-3 partial or blocked status does not gate event framing.

Qwen2.5 detects source-literal triggers before it assigns roles to one trigger.

Qwen2.5 proposes EventFrameDrafts with task-local mention references.

Event and role labels remain open proposals until HP-5 validates ontology structure.

### 8. Construct atomic claims

The Application Layer maps validated EventFrameDrafts to AtomicClaimDrafts.

The Application Layer creates exact EvidenceTarget references for each AtomicClaimDraft.

### 9. Validate ontology structure

The Application Layer validates entity kinds, frame roles, predicates, and references.

The Application Layer records every violation in an OntologyValidationReport.

### 10. Normalize event semantics and judge source support

Qwen2.5 selects one governed frame and governed frame roles from a bounded ontology profile.

KoteKomi constructs typed event targets and qualified role assignments from authoritative characters.

Separate Qwen2.5 tasks compare deterministic semantic statements with exact evidence.

Each task returns directly supported, partially supported, unsupported, contradicted, or ambiguous.

### 11. Create reviewable state

The Application Layer creates ProposedChanges from complete validated drafts.

The review flow remains the only path to accepted Ledger records.

## Incremental delivery

Each deliverable leaves the prior working path intact.

Each deliverable produces evidence that defines the next TDD.

HP-1 through HP-8 have accepted, implemented, and verified TDDs.

| Deliverable | User story | Precondition | Postcondition |
| --- | --- | --- | --- |
| [HP-1 Hybrid Mention Interpretation MVP](2026-09-01-hybrid-mention-interpretation-mvp.md) | A reviewer can inspect source-valid mentions and their separate contextual dimensions. | Authoritative paragraphs, proposer Adapters, ORG-R1 rules, and stage traces exist. | One paragraph produces a durable HybridExtractionPreview with no ProposedChange or accepted state change. |
| [HP-2 Document Reference Resolution](2026-09-01-hybrid-document-reference-resolution.md) | A reviewer can inspect explicit aliases and unresolved document references. | HP-1 preserves ontology-neutral MentionCandidates and interpretations. | The Pipeline emits ReferenceDecisions without inventing antecedents. |
| [HP-3 Entity Identity Grounding](2026-09-01-hybrid-entity-identity-grounding.md) | A reviewer can inspect known identity candidates only for specific mentions. | HP-2 identifies specific mentions and document-local aliases. | ReFinED emits ranked EntityLinkCandidates or NIL after contextual interpretation. |
| [HP-4 Event Frame Drafts](2026-09-01-hybrid-event-frame-drafts.md) | A reviewer can inspect each source-grounded event with all participant roles. | HP-3 preserves the verified HP-1 and HP-2 lineage plus optional identity evidence. | Qwen2.5 emits bounded EventFrameDrafts with task-local references. |
| [HP-5 Atomic Claims and Ontology Validation](2026-09-02-hybrid-atomic-claims-ontology-validation.md) | A reviewer can inspect atomic claims and every ontology violation. | HP-4 supplies validated EventFrameDrafts. | KoteKomi constructs AtomicClaimDrafts and OntologyValidationReports. |
| [HP-6 Qualified Event Semantics and Source Support](2026-09-02-qualified-event-semantics-source-support.md) | A reviewer can inspect governed event frames, qualified roles, explicit gaps, and independent source support. | HP-5 supplies exact EvidenceTargets and lossless open-label evidence. | KoteKomi emits typed semantic drafts and support judgments without changing wiki state. |
| [HP-7 ProposedChange Integration](2026-09-03-hybrid-proposed-change-integration.md) | A reviewer can inspect governed HP-6 events through the existing review flow. | HP-6 supplies governed semantic drafts with complete source-support evidence. | The Pipeline creates pending ProposedChanges without creating accepted intelligence. |
| [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md) | A user receives one reviewable candidate change set from an ingested document. | HP-7 converts one HP-6 Preview into a reviewable proposal batch. | One ingestion runs the Hybrid Pipeline over its planned document scope and closes one IngestionChangeSet. |

## Validation strategy

HP-1 reuses source and boundary labels from the reviewed Organization mention catalogs.

HP-1 adds reviewed contextual labels for one fixed diagnostic subset.

Each later deliverable adds Gold labels only for its new semantic boundary.

Development evidence and held-out evidence remain disjoint.

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
