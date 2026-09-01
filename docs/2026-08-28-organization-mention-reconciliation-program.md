# Organization Mention Reconciliation and Resolution Program

- Status: Superseded
- Successor: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Parent: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Development oracle: [PHP-1 Organization Mention Gold](php1-organization-mention-gold-v1.json)
- Held-out annotation packet: [Organization Mention Held-Out Annotation Packet](2026-08-28-organization-mention-held-out-annotation-packet.md)

The ORG-R0 foundation and sealed ORG-R1 and ORG-R2 outcomes remain historical evidence.

The Hybrid Pipeline supersedes ORG-R3 through ORG-R5.

## User outcome

A reviewer receives complete, literal Organization mentions even when fallible proposers disagree about boundaries or the source uses acronyms and references.

Every decision remains traceable to authoritative source characters.

No proposer, classifier, linker, or coreference model writes accepted Ledger state.

## Problem

Qwen2.5 and GLiNER find complementary Organization mentions.

Their raw union improves recall but also contains overlapping boundaries, incomplete names, products, initiatives, events, job titles, and other non-Organizations.

Segment-local extraction cannot reliably resolve later acronyms, `it`, `the institute`, `members`, or country names acting as governments.

These are three different decisions:

1. Which literal source boundary is the best expression?
2. Does that expression denote an Organization in this context?
3. Does it refer to an Organization introduced elsewhere in the Document?

The implementation must keep those decisions separate and observable.

## Invariable decisions

The accepted `DocumentRepresentationBundle` and its `DocumentNode` text remain authoritative.

Proposal spans remain derived, fallible observations.

KoteKomi validates every proposed start, end, and literal text against authoritative source characters.

Overlapping proposals remain visible until a named reconciliation policy reaches a terminal decision.

There is no generic longest-span-wins rule.

KoteKomi performs deterministic work such as exact span validation, duplicate removal, explicit abbreviation-declaration recognition, offset construction, digest calculation, and record construction.

A bounded semantic model performs meaning-dependent work such as Organization qualification and context-dependent reference judgment.

Semantic output remains a proposal or decision input.

KoteKomi constructs every real record and validates every reference.

Uncertain results remain `ambiguous`, `unresolved`, `NIL`, `rejected`, or `blocked` as appropriate.

The system does not invent an antecedent or entity identity to keep the Pipeline moving.

Country-as-government is a contextual institutional reading, not a global alias from a place to an Organization.

The first implementation evaluates candidates and produces derived diagnostic records only.

Production selection requires a separate TDD and no regression on demonstrated behavior.

## Research basis

### Boundary reconciliation

[spaCy SpanFinder](https://spacy.io/api/spanfinder) predicts potentially overlapping spans.

[spaCy span scoring](https://spacy.io/api/scorer) provides overlap-aware scoring, while `filter_spans` is an explicit later choice that prefers longer non-overlapping spans.

[DyGIE++](https://arxiv.org/abs/1909.03546) represents entities, relations, and events with contextualized spans and demonstrates that span decisions can remain explicit inputs to later extraction stages.

KoteKomi will therefore retain overlap as evidence and apply project-owned typed reconciliation rules after proposal collection.

### Semantic Organization qualification

[ReFinED](https://github.com/amazon-science/ReFinED) combines mention detection, fine-grained typing, and entity disambiguation with contextual entity descriptions.

[REL](https://github.com/informagi/REL) separates mention detection from entity disambiguation and can disambiguate caller-supplied spans.

[OntoGPT/SPIRES](https://github.com/monarch-initiative/ontogpt/blob/main/docs/operation.md) separates schema-guided extraction from ontology grounding and retains the input, prompt, raw completion, and extracted object.

KoteKomi will keep qualification and entity resolution as separate fallible stages even when an experimental system performs both internally.

An external result can propose a qualification or entity candidate but cannot become accepted authority.

### Acronym and reference resolution

[scispaCy's AbbreviationDetector](https://github.com/allenai/scispacy/blob/main/README.md#abbreviationdetector) implements the Schwartz-Hearst algorithm for explicit long-form and abbreviation declarations.

[Maverick](https://aclanthology.org/2024.acl-long.722/) produces mention clusters with character positions, and its implementation accepts predefined mentions or starting clusters.

[spaCy's experimental CoreferenceResolver](https://spacy.io/api/coref/) produces token-level coreference clusters and can pair with a span resolver.

KoteKomi will resolve explicit declarations deterministically before invoking bounded semantic reference resolution.

A coreference experiment should receive already reconciled and qualified mentions where the implementation permits it.

The experiment must return source-bound clusters or typed unresolved outcomes, not rewritten prose.

### Dependency posture

The cited systems establish sound approaches, not automatic dependency choices.

ReFinED is a credible qualification and linking experiment because it exposes the relevant stages and has a permissive license.

Maverick is a credible coreference benchmark, but its repository's non-commercial share-alike license requires review before any production adoption.

spaCy coreference remains experimental.

DyGIE++ is useful theory but is not a preferred dependency because its public implementation is tied to the retired AllenNLP stack.

No library enters the production Pipeline until it beats the current path on project-owned development and held-out evidence.

## Planned data flow

```text
Authoritative SourceSegment
    |
    v
MentionProposalObservation[]
    |
    v
MentionBoundaryDecision[]
    |
    v
ReconciledMentionCandidate[]
    |
    v
OrganizationQualificationDecision[]
    |
    v
QualifiedOrganizationMention[]
    |
    +--> explicit abbreviation declarations
    |
    +--> bounded document reference resolver
    |
    v
OrganizationReferenceDecision[]
    |
    v
OrganizationIdentityCandidate[]
    |
    v
Candidate pairs and later hypothesis work
```

Every arrow emits an `ExtractionStageTrace`.

## 1. Deterministic boundary reconciliation

### Purpose

Produce one reviewable terminal decision for each equal, nested, partially overlapping, or adjacent proposal group.

### Initial rules to test

Equal source spans merge proposer provenance.

Exact parenthetical declarations retain the complete expanded expression and the literal alias expression.

Determiners, possessives, punctuation, geographic qualifiers, and legal suffixes follow named source-literal policies.

Nested expressions remain separate when both can independently denote Organizations.

Product, initiative, event, job-title, and Organization alternatives remain ambiguous until semantic qualification resolves their type.

Unresolved partial overlap produces a typed ambiguous decision and no silent deletion.

### Validation

Score exact-boundary precision, recall, F1, ambiguity rate, and regression against the development Gold.

Review every changed span with its source text, proposal provenance, applied rule, and terminal decision.

## 2. Semantic Organization qualification

### Purpose

Judge whether one reconciled literal expression denotes an Organization under KoteKomi's current policy in its exact source context.

### Initial experiment

Compare the current bounded Qwen2.5 qualification task with ReFinED-derived type and entity evidence on the same candidates.

The comparison must preserve separate outputs rather than fusing them before scoring.

Each result records `organization`, `not_organization`, or `ambiguous` plus its producer and execution evidence.

KoteKomi resolves any returned literal expression to authoritative offsets and constructs the typed decision.

### Validation

Measure qualification precision, recall, F1, abstention, ambiguity, latency, and run-to-run stability.

Break errors down by country-as-government, supranational body, media outlet, initiative, event, product, job title, generic class, and citation-only text.

## 3. Cross-segment acronym and reference resolution

### Purpose

Resolve later literal mentions and reference expressions to earlier qualified Organization identities without inventing identity.

### Initial sequence

1. Detect explicit long-form and abbreviation declarations deterministically.
2. Build a document-local alias table from qualified declarations.
3. Resolve exact later abbreviations only when the declaration is unique and in scope.
4. Send remaining bounded references to an experimental resolver with nearby authoritative context and predefined mentions.
5. Validate every returned span and antecedent against source characters.
6. Emit `resolved`, `ambiguous`, `unresolved`, or `NIL` decisions.

### Validation

Measure explicit-acronym resolution separately from pronoun, generic nominal, collective, and country-as-government resolution.

Report exact antecedent accuracy, cluster precision and recall, unresolved rate, false-link rate, context size, latency, and stability.

## 4. Independently annotated held-out catalog

The held-out packet contains 50 exact authoritative paragraphs from fresh isolated test ingestions of the three local PDFs.

Selection does not use Qwen, GLiNER, relation output, or current model errors.

Selection uses source-independent lexical conditions to cover boundary, qualification, acronym, and reference behavior.

No selected paragraph contains a Source segment already present in the development Gold.

The human reviewer has filled every Gold field.

The reviewed Gold contains literal Organization expressions and `resolved:` names for discontinuous or context-dependent references.

A separate deterministic operation must resolve literal expressions to exact offsets.

The same operation must bind each resolved name to its exact source expression and expected reference decision.

The operation must create the machine-readable held-out catalog without model inference.

The held-out catalog must remain sealed from prompt and policy tuning.

## 5. Shared stage-trace envelope

`ExtractionStageTrace` is an Application Layer DTO for derived diagnostic evidence.

One trace run follows one authoritative Source segment through ordered stages.

Every stage records its identity and version, producer, configuration, exact input, complete observable output, terminal status, diagnostics, parent traces, input records, execution records, and SHA-256 digests.

The trace references existing `ModelRun` or other execution records.

It does not replace or duplicate their role as execution evidence.

The trace is not accepted Ledger knowledge and cannot authorize a `ProposedChange`.

## Incremental implementation order

### ORG-R0 — Shared trace and held-out annotation foundation

**User story:** As an operator, I can inspect consistent data-in/data-out evidence and annotate a benchmark that implementation tuning has never seen.

**Precondition:** The development Gold and the three local authoritative fixtures exist.

**Postcondition:** The shared trace contract is tested, current monotonic rescue diagnostics use it, and a disjoint 50-paragraph packet awaits human labels.

### ORG-R1 — Deterministic boundary reconciliation MVP

**User story:** As a reviewer, I see why one literal boundary survived or remained ambiguous when proposers disagree.

**Precondition:** ORG-R0 supplies trace evidence and held-out inputs.

**Postcondition:** Named deterministic rules resolve safe cases and preserve every unresolved conflict without silent loss.

**TDD:** [Organization Mention Boundary Reconciliation MVP](2026-08-31-organization-mention-boundary-reconciliation.md)

**Outcome:** Selected after the frozen development replay and one sealed held-out evaluation; see [Organization Boundary Reconciliation Result](organization-boundary-reconciliation-result-v1.json).

### ORG-R2 — Semantic Organization qualification comparison

**User story:** As a reviewer, I see whether a literal expression denotes an Organization and which fallible system made that judgment.

**Precondition:** ORG-R1 supplies reconciled candidates.

**Postcondition:** Qwen2.5 and at least one established contextual typing or linking approach are compared on identical candidates.

**TDD:** [Organization Semantic Qualification Comparison](2026-08-31-organization-semantic-qualification-comparison.md)

**Outcome:** Qwen2.5 and pinned ReFinED V1 were compared over sealed development and held-out
bundles; neither path entered production. See [Organization Semantic Qualification Result](organization-semantic-qualification-result-v1.json).

### Superseded ORG-R3 — Explicit acronym declarations

**User story:** As a reviewer, I see a source-declared abbreviation resolve to one document-local Organization identity.

**Precondition:** ORG-R2 supplies qualified names.

**Postcondition:** Unique explicit declarations resolve deterministically and conflicting declarations remain ambiguous.

### Superseded ORG-R4 — Bounded reference-resolution experiment

**User story:** As a reviewer, I see whether a later acronym, pronoun, collective, or country expression refers to an earlier Organization.

**Precondition:** ORG-R3 resolves the deterministic subset and the held-out catalog is fully annotated.

**Postcondition:** At least one established coreference approach is compared with KoteKomi's bounded semantic task, with false links treated as integrity failures.

### Superseded ORG-R5 — Production selection

**User story:** As a user, I receive better Organization extraction without losing any demonstrated capability or weakening wiki integrity.

**Precondition:** ORG-R1 through ORG-R4 have completed comparable development and held-out evaluations.

**Postcondition:** One explicitly selected path enters the Pipeline, or production remains unchanged with complete evidence explaining why.

ORG-R1 and ORG-R2 now have detailed TDDs and retained outcomes.

The Hybrid Pipeline replaces ORG-R3 through ORG-R5.

## Stop conditions

Stop an experiment when fixture identity drifts, source offsets do not validate, development inputs appear in held-out tuning, a candidate tool's license is incompatible, or a proposed path loses an already demonstrated ability.

Do not expand the ontology as part of this program.

Do not add accepted Ledger writes as part of an evaluation TDD.
