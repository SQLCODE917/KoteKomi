# HP-8 Document Orchestration Evaluation

- Status: Complete
- TDD: [Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Runtime: LM Studio `qwen2.5-14b-instruct`, GLiNER medium 2.1, and pinned offline ReFinED 1.0

## Outcome

The public `kotekomi ingest` path ran HP-1 through HP-8 over all 36 authoritative paragraph nodes.

The run produced 16 clean Paragraph Receipts, 20 Paragraph Receipts with accounted gaps, 236 pending ProposedChanges, one Document Coverage Report, one AnalysisRun, and one IngestionChangeSet.

The Ledger contained zero accepted Actors, Organizations, Events, Assertions, or Relationships after ingestion.

The second ingestion reused all 36 Paragraph Receipts.

It created zero new ExtractionTasks, ModelRuns, or ProposedChanges.

The first and second IngestionChangeSets record `executed` and `reused` origins respectively.

## Reviewed event retention

All seven approved HP-7 Gold events remained visible in HP-4 evidence.

Six reached complete HP-6 and HP-7 lineage and became pending proposal bundles.

The `designated` event remained visible as an exact authoritative trigger but stopped at an explicit HP-4 gap after Qwen returned `not_applicable` as a time qualifier literal.

The known false Amodei `said` event also remained visible in HP-4 evidence.

Its invalid frame mapping created no proposal and no accepted intelligence.

Two reviewed Minab triggers were returned as longer exact source literals: `described as ...` and `said should ...`.

The evaluator records these as `expanded_literal` retention rather than pretending the source characters or event disappeared.

## Exact data in and data out

The clearest complete example is paragraph ordinal 12:

> The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars. [39]

HP-1 produced four source-valid MentionCandidates: `The dispute`, `1789 Capital`, `Donald Trump Jr.`, and `Anthropic`.

Qwen interpreted them as an event, an Organization, a person, and an Organization.

HP-2 retained the mentions without inventing references.

HP-3 retained ReFinED identity evidence as advisory derived state.

HP-4 produced exact authoritative triggers `caused` and `abandon` and two EventFrameDrafts.

HP-5 deterministically produced two EventSubjectDrafts and 13 AtomicClaimDrafts.

HP-6 normalized the events to governed `causation` and `investment_abandonment` frames.

HP-6 also rejected the model's false time qualifier—`1789 Capital, a venture capital firm associated with Donald Trump Jr.`—and recorded explicit `omitted_parent_qualifier` and `omitted_parent_argument` gaps.

HP-7 admitted both safe semantic events and constructed 15 pending ProposedChanges.

Every proposal retains the exact EvidenceTarget, Source, Document, representation, HP-1 through HP-7 record IDs, model-run IDs, support-judgment IDs, and stage-trace IDs.

The paragraph receipt is `hpr_a4f131d59854110da198ed76`.

Its `gap` status is conservative: it preserves the HP-6 omissions while retaining the safe proposal subset.

## Tool-assignment findings

GLiNER is useful as a broad span proposer, not a semantic authority.

For the example paragraph it found all four useful spans but supplied at least one poor type hint.

Qwen correctly interpreted `Anthropic` contextually as an Organization, showing why contextual qualification belongs to the language model rather than GLiNER.

ReFinED provided inspectable external identity candidates but never selected KoteKomi's local identity or authorized a Ledger write.

Qwen was useful for bounded trigger, frame, ontology-normalization, and source-support judgments.

Its failures were also characteristic: expanded trigger phrases, an invalid placeholder qualifier, and occasional malformed or ambiguous outputs.

KoteKomi correctly owned exact offsets, source-character validation, canonical IDs, ontology validation, deterministic claim construction, coverage, persistence, and the review boundary.

No model or specialized-model output became accepted intelligence directly.

## Measured limitations and next hypotheses

The run archived 640 ExtractionTasks and ModelRuns for 36 paragraphs.

Most latency came from sequential HP-6 source-support judgments after dense paragraphs generated many semantic statements.

The next performance experiment should batch only compatible independent support judgments while retaining one typed judgment, one source binding, and one audit record per statement.

The next quality experiment should test whether the event-trigger task can prefer the minimal source-literal trigger without losing the longer phrase as event content.

The next output-contract experiment should make absence explicit in the frame grammar so a model cannot express `not_applicable` as a source qualifier literal.

Those are measured follow-up hypotheses.

They are not HP-8 orchestration defects and must not weaken deterministic rejection or the pending-review boundary.

## Canonical ingestion diagram

```text
+----------------------------- RAW SOURCE (PDF / authoritative text) ------------------------------+
|  SOURCE record -> DOCUMENT record -> representation + text view                                  |
+-------------------------------------------------+--------------------------------------------------+
                                                  |  Hybrid Pipeline Policy manifest splits into ParagraphWork units
                                                  v
                          36 x PARAGRAPH WORK  (paragraph_node + authoritative_text)
                          <- unit = exactly one paragraph gap class
                                                  |
  per paragraph, seven stages run in HYBRID_STAGE_ORDER (dependency fan-in drawn as a chain):
                                                  |
  HP1 MENTIONS -> HP2 REFERENCES -> HP3 GROUNDING -> HP4 EVENT TRIGGERS -> HP6 EVENT SEMANTICS -> HP7 PROPOSAL PLAN -> HP10 STANDING FACTS
     |               |                |                  |                     |                         |                        |
     |               +-----(semantic antecedent / alias decls feed grounding & events)----------------------------------------+
     v               v                v                  v                     v                         v                        v
  stage record   stage record    stage record       stage record          stage record              stage record             stage record
  (complete/     (complete/      (complete/         (...)                 (...)                     (...)                    (...)
   partial)       partial)        partial)
                                                  |
                                                  |  HP8 verifier derives one gap class by precedence (one count per non-complete paragraph)
                                                  v
                          HybridParagraphReceipt (hpr)  <- per-stage status + gap_reasons retained (receipt unchanged)
                                                            HP1 partial -> proposal_rejected
                                                            HP3 partial (HP1 complete) -> inherited_partial
                                                            HP10 partial (HP1 + HP3 complete) -> boundary_held | routed | held
                                                  |
                        +-------------------------+-----------------------------+
                        v                                                          v
  ARCHIVE (derived previews, receipts, model-run outputs)      LEDGER (ProposedChange + ProvenanceActivity)
                        |
                        v
  HP8 DOCUMENT ORCHESTRATION verifier
     -> HybridDocumentCoverageReport (complete + gap counts, unchanged)
     -> CurrentHybridEvaluationSummary.gap_breakdown = {proposal_rejected, boundary_held, routed, held, inherited_partial}
     -> complete_paragraphs + gap_breakdown.total == required_paragraphs
     -> three gold evaluations
```

The HP-8 verifier derives one paragraph gap class per Paragraph Receipt.

The six classes are complete, proposal_rejected, inherited_partial, boundary_held, routed, and held.

A complete paragraph stays outside the five-class gap_breakdown.

HP-1 partial selects proposal_rejected first.

HP-3 partial selects inherited_partial when HP-1 is complete.

HP-10 partial selects boundary_held, routed, or held when HP-1 and HP-3 are complete.

A line or relation boundary rejection selects boundary_held.

An event-route requirement without a rejection selects routed.

Any other HP-10 partial selects held.

The canonical run reports 16 complete paragraphs and 20 non-complete paragraphs.

The 20 non-complete paragraphs split as proposal_rejected 10, boundary_held 9, routed 1, held 0, and inherited_partial 0.

## Verification

The durable canonical report was written to `/private/tmp/kotekomi-hp8-canonical-report.json`.

The isolated Ledger, Archive, policy manifest, raw model outputs, stage traces, receipts, and coverage report were retained under `/private/tmp/kotekomi-hp8-canonical-state-20260903` for local inspection.
