# HP-8 Document Orchestration Evaluation

- Status: Complete
- TDD: [Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Runtime: LM Studio `qwen2.5-14b-instruct`, GLiNER medium 2.1, and pinned offline ReFinED 1.0

## Outcome

The public `kotekomi ingest` path ran HP-1 through HP-8 over all 36 authoritative paragraph nodes.

The run produced 19 clean Paragraph Receipts, 17 Paragraph Receipts with accounted gaps, 115 pending ProposedChanges, one Document Coverage Report, one AnalysisRun, and one IngestionChangeSet.

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

## Verification

The durable canonical report was written to `/private/tmp/kotekomi-hp8-canonical-report.json`.

The isolated Ledger, Archive, policy manifest, raw model outputs, stage traces, receipts, and coverage report were retained under `/private/tmp/kotekomi-hp8-canonical-state-20260903` for local inspection.
