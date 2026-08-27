# Paragraph Hypothesis Development Program

- Status: Proposed
- Program ID: `paragraph-hypothesis-development`
- Parent: [Candidate Ingestion Review Program](2026-08-24-candidate-ingestion-review-program.md)
- Related program: [Model and Ontology Boundary Program](2026-08-25-model-ontology-boundary-program.md)
- Evaluation corpus: [CIR Evaluation Annotation Packet](2026-08-26-cir-evaluation-annotation-packet.md)

## Context and problem

KoteKomi stores Sources, Documents, DocumentRepresentationBundles, EvidenceTargets, and accepted Assertions.
KoteKomi uses a local model to interpret source text.
The model must not create accepted Ledger state.

CIR-2.2.1 asks the model for one SemanticDraft from one eligible paragraph.
That path proves direct prose grounding.
It cannot represent several independently supported relations in one relationship-rich paragraph.

This program turns one authoritative paragraph into a bounded set of reviewable atomic hypotheses.
KoteKomi verifies each hypothesis against exact source spans.
KoteKomi normalizes verified hypotheses into pending ProposedChanges.
A reviewer decides whether a pending hypothesis becomes an accepted Assertion.

### Program statement

```text
DocumentRepresentationBundle
    -> paragraph DocumentNode
    -> KoteKomi source segments
    -> model hypothesis batch
    -> deterministic verification
    -> pending ProposedChanges
    -> reviewer decision
    -> accepted Assertions and derived Relationships
```

## Terms

**Paragraph** means one authoritative `DocumentNode` with `node_type = paragraph`.

**Source segment** means one KoteKomi-derived contiguous character span inside one Paragraph.

**Atomic hypothesis** means one proposed subject, relation label, object, and supporting Source segment.

**Hypothesis batch** means all Atomic hypotheses that one model response proposes for one Paragraph.

**Verification** means KoteKomi checks source-segment labels and exact source mentions.

**Normalization** means KoteKomi derives pending record references from verified source mentions.

## Invariable decisions

The Archive and the accepted DocumentRepresentationBundle remain the authority for source content.

The SourceSegment remains the smallest model input unit in this program.

KoteKomi derives every Source segment from the Paragraph before it calls a model.

KoteKomi sends the model original paragraph text and task-local Source-segment labels.

The model receives no Ledger IDs, Archive paths, character offsets, page regions, or storage details.

The model returns ordinary-language hypothesis text.

The model does not create record IDs, source ranges, EvidenceTargets, Organizations, Assertions, Relationships, or ProvenanceActivities.

Every Atomic hypothesis identifies its supporting Source segment through a task-local label.

KoteKomi binds that label to exact character offsets and source provenance.

KoteKomi archives every raw model response before it validates the Hypothesis batch.

KoteKomi records malformed or ungrounded model output as a visible ModelRun outcome.

KoteKomi creates no ProposedChange from an invalid Hypothesis batch.

KoteKomi creates pending records only after Verification succeeds.

A reviewer remains the only actor that accepts a proposed hypothesis into the Ledger.

The reviewer supplies governed canonical predicate meaning through the CIR-2.2 review contract.

Derived retrieval, graph, Wiki, and Briefing projections remain disposable.

## Evaluation corpus role

The annotation packet contains 50 authoritative paragraph spans from three deposited PDFs.

The packet includes direct claims, multiple relations, attribution, uncertainty, modality, recommendation, and identity controls.

The packet is a human-review corpus.

The packet becomes a release corpus only after independent reviewers confirm its labels and expected alternatives.

The MVP records packet outcomes without claiming a quality threshold.

The eight-claim batch limit is an initial PHP-1 design decision.

The program evaluates that limit after PHP-1 produces reviewed corpus evidence.

## Incremental delivery

Each deliverable leaves the prior working path intact.

Only the MVP has a complete TDD.

Each later TDD is written after the preceding deliverable produces reviewed evidence.

| Deliverable | User story | Precondition | Postcondition |
| --- | --- | --- | --- |
| [PHP-1 Bounded Paragraph Hypothesis MVP](2026-08-26-paragraph-hypothesis-mvp.md) | A reviewer sees several direct organization hypotheses from one Paragraph. | CIR-2.2.1 creates paragraph-bound ModelRuns and pending review records. | KoteKomi creates zero through eight verified pending hypotheses from one Paragraph. |
| [PHP-1.1 Literal Output Hardening](2026-08-26-paragraph-hypothesis-literal-output-hardening.md) | A reviewer sees valid PHP-1 outcomes without avoidable source-label failures. | PHP-1 records raw batch outcomes. | KoteKomi uses literal labels, exact-copy instructions, and bounded source-order selection. |
| [PHP-1.2 Segment-Local Hypothesis Extraction](2026-08-26-segment-local-hypothesis-extraction.md) | A reviewer sees one model outcome for one exact source sentence. | PHP-1.1 records paragraph-wide outcomes. | KoteKomi sends one source segment to each model task. |
| [PHP-1.3 Deterministic Sentence Segmentation](2026-08-26-paragraph-hypothesis-deterministic-sentence-segmentation.md) | A reviewer sees complete source sentences instead of fragments. | PHP-1.2 creates one work item for each `paragraph_segment_v1` segment. | KoteKomi derives exact, reconstructible sentences with `paragraph_segment_v2`. |
| [PHP-1.4 Provisional Eligibility Labels](2026-08-26-paragraph-hypothesis-provisional-eligibility-labels.md) | An operator can distinguish in-scope abstentions from expected exclusions. | The packet records a case class but no extraction eligibility decision. | The packet records one reviewable provisional eligibility label for every row. |
| [PHP-1.5 Literal Prompt Calibration](2026-08-26-paragraph-hypothesis-literal-prompt-calibration.md) | A reviewer receives fewer avoidable formatting and grounding rejections. | PHP-1.3 records raw sentence outcomes. | The Pipeline pins a prompt that teaches literal copying through bounded examples. |
| [PHP-1.6 Eight-Claim Evaluation](2026-08-26-paragraph-hypothesis-eight-claim-evaluation.md) | An operator can decide whether the PHP-1 limit suppresses eligible claims. | PHP-1 records a bounded result for each work item. | A diagnostic report separates the limit effect from other rejection causes. |
| [PHP-1.7 Semantic Faithfulness Verifier](2026-08-26-paragraph-hypothesis-semantic-faithfulness-verifier.md) | A reviewer receives only hypotheses that a second model task judges faithful to direct prose. | PHP-1.5 produces deterministically grounded hypotheses. | KoteKomi records an independent verifier outcome before it creates pending ProposedChanges. |
| [PHP-1.8 Reliability and Evaluation](2026-08-26-php1-reliability-and-evaluation.md) | A reviewer receives source-grounded PHP-1 results without PDF-layout copy failures. | PHP-1.7 records source-segment results and verifier outcomes. | KoteKomi uses a derived Source copy view and reports segment-scoped PHP-1 evaluation. |
| [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md) | An operator can improve PHP-1 from a trustworthy source-segment baseline. | PHP-1.8 records source-segment outcomes. | The program delivers H0 through H4 one TDD at a time. |
| PHP-2 Coverage evaluation | A reviewer sees which expected paragraph facts received no hypothesis. | PHP-1 records a replayable outcome for each processed Paragraph. | KoteKomi reports complete, abstained, invalid, and missing expected hypothesis outcomes. |
| PHP-3 Multi-segment support | A reviewer sees one hypothesis with all required direct prose spans. | PHP-2 identifies claims that one Source segment cannot support. | KoteKomi verifies one bounded set of Source segments for one hypothesis. |
| PHP-4 Extended object types | A reviewer sees Actors, Events, Places, and typed values proposed with direct evidence. | PHP-3 proves multi-segment evidence handling. | KoteKomi creates pending typed candidates without changing accepted ontology state. |
| PHP-5 Semantic verification and recovery | A reviewer sees the reason for every rejected or retried model result. | PHP-4 produces reviewed error classes from real corpus runs. | KoteKomi applies bounded, visible verification and recovery rules. |
| PHP-6 Corpus release gate | A maintainer sees measured extraction quality across independently reviewed source spans. | PHP-5 produces stable replay records and reviewed corpus labels. | KoteKomi runs a versioned quality gate without hidden exclusions. |

## Validation strategy

PHP-1 uses project-owned text fixtures for CI contract tests.

PHP-1 uses selected rows from the annotation packet as a local diagnostic acceptance run.

PHP-2 defines corpus-wide measures after reviewers inspect the MVP outcomes.

PHP-3 includes bounded same-paragraph antecedent resolution.

PHP-3 supplies nearest preceding sentences first and stops at 1,024 input tokens.

No deliverable uses model output as its own gold label.
