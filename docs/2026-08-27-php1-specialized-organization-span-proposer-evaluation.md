# TDD: PHP-1 Specialized Organization Span Proposer Evaluation

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H2.1
- Depends on: [PHP-1 Mention and Relationship Diagnosis](2026-08-27-php1-mention-relationship-diagnosis.md)

## 1. Context & Problem

PHP-1 uses Qwen2.5 to propose Organization mentions from one Source segment.

H2 separates mention proposals from relationship judgments.

H2 shows that a missing Organization mention prevents every later relationship judgment for that pair.

The repository does not compare Qwen2.5 with a specialized named-entity model.

The current 50-case annotation packet does not enumerate every Organization span.

The current packet therefore cannot measure mention precision or recall.

**Gold mention** means one reviewed literal Organization occurrence in one Source segment.

**Mention catalog** means the provisional set of Gold mentions for all 50 packet cases.

**Mention proposer** means a tool that proposes Organization spans from one Source segment.

**Mention proposal** means one proposed text span with one tool score.

**Exact match** means a Mention proposal and Gold mention have equal start and end positions.

**Boundary result** means the exact, truncated, expanded, crossing, or missing result for one Gold mention.

### Primary end-to-end flow

1. The evaluator reloads each authoritative paragraph in the 50-case packet.
2. The evaluator validates every Mention catalog entry against its Source segment.
3. Qwen2.5 and GLiNER each propose Organization mentions from the same Source segments.
4. KoteKomi validates every proposed text span against the Source segment.
5. The evaluator compares each proposer with the Mention catalog.
6. The evaluator writes one reviewable quality, latency, and stability report.

## 2. Goals

- An operator sees Organization mention precision and recall for Qwen2.5 and GLiNER.
- An operator sees complete-name boundary failures for each proposer.
- An operator sees warm inference latency and three-run stability for each proposer.
- An operator can inspect every false positive and false negative against source text.
- A later TDD can select a production Mention proposer from measured evidence.

## 3. Requirements

### Mention catalog

- H21-CAT-01: The Mention catalog covers every unique Source segment in all 50 packet cases.
- H21-CAT-02: The Mention catalog records an empty Gold mention list for a segment with no Organization.
- H21-CAT-03: Each Gold mention records exact text, start position, and end position.
- H21-CAT-04: Each catalog segment records its case, fixture, paragraph, label, and source-text digest.
- H21-CAT-05: The evaluator rejects a Gold mention whose text differs from its recorded source range.
- H21-CAT-06: The evaluator rejects catalog drift before it invokes either Mention proposer.
- H21-CAT-07: The catalog uses the Organization definition from H2.
- H21-CAT-08: The evaluator reanchors a catalog segment after only its derived DocumentNode ID changes.
- H21-CAT-09: Reanchoring requires one fixture, case set, segment label, and source-text digest match.

### Mention proposer Port

- H21-PORT-01: The Application Layer defines a Port for one Source segment and one proposal batch.
- H21-PORT-02: Each Mention proposal records text, start position, end position, and tool score.
- H21-PORT-03: Each proposal batch records the proposer identity and elapsed milliseconds.
- H21-PORT-04: The Application Layer validates every proposal against the exact Source segment.
- H21-PORT-05: The Application Layer rejects the complete batch after any invalid proposal.
- H21-PORT-06: The Application Layer orders valid proposals by source position.
- H21-PORT-07: The Application Layer preserves distinct overlapping proposals.
- H21-PORT-08: The Application Layer rejects duplicate proposal spans.

### GLiNER Adapter

- H21-GLI-01: The Adapter uses `urchade/gliner_medium-v2.1`.
- H21-GLI-02: The Adapter pins revision `40ec419335d09393f298636f471328b722c6da9e`.
- H21-GLI-03: The Adapter uses the `organization` label and threshold `0.5`.
- H21-GLI-04: The Adapter uses CPU inference without quantization.
- H21-GLI-05: The Adapter maps each GLiNER result into a Mention proposal.
- H21-GLI-06: The Adapter fails when GLiNER returns a malformed result.
- H21-GLI-07: The Adapter loads GLiNER only when the caller constructs the Adapter.

### Qwen2.5 baseline

- H21-QWN-01: The evaluator uses the existing H2 Organization mention prompt.
- H21-QWN-02: The evaluator records the configured Model identity for each Qwen2.5 run.
- H21-QWN-03: The evaluator maps each Qwen2.5 name to every exact occurrence in its Source segment.
- H21-QWN-04: The evaluator rejects a Qwen2.5 name that does not occur in its Source segment.

### Comparison report

- H21-REP-01: The evaluator runs each Mention proposer three times.
- H21-REP-02: The evaluator records every proposal from every run.
- H21-REP-03: The evaluator reports micro and per-document precision, recall, and F1.
- H21-REP-04: The evaluator reports exact, truncated, expanded, crossing, and missing Boundary results.
- H21-REP-05: The evaluator reports per-segment latency plus p50, p95, and total latency.
- H21-REP-06: The evaluator reports exact-set and pairwise Jaccard stability.
- H21-REP-07: The evaluator records every false positive and false negative with Source segment identity.
- H21-REP-08: The evaluator reports `completed` regardless of which Mention proposer scores higher.
- H21-REP-09: The evaluator reports a typed blocked status for a missing fixture or unavailable proposer.

### Production isolation

- H21-ISO-01: The public ingestion Pipeline continues to use PHP-1 V3.
- H21-ISO-02: The evaluator writes no accepted Ledger state.
- H21-ISO-03: The evaluator does not select a production Mention proposer.

## 4. Proposed Architecture

```text
50-case packet + Mention catalog
                |
                v
          PHP-1 evaluator
           /           \
          v             v
 Qwen2.5 baseline   Mention proposer Port
                          |
                          v
                    GLiNER Adapter
           \             /
            v           v
       KoteKomi span validation
                |
                v
         Comparison report
```

The Application Layer owns the Mention proposer Port and source-span validation.

The GLiNER Adapter owns model loading and tool-shape mapping.

The evaluator owns corpus replay, metric calculation, and report assembly.

## 5. Key Interactions

```text
Operator       Evaluator       Qwen2.5       GLiNER       Report
   |               |              |             |            |
   | run           |              |             |            |
   |-------------->| validate     |             |            |
   |               | catalog      |             |            |
   |               |------------->| propose     |            |
   |               |<-------------| spans       |            |
   |               |--------------------------->| propose    |
   |               |<---------------------------| spans      |
   |               | validate and score                      |
   |               |---------------------------------------->|
   | report        |              |             |            |
   |<--------------|              |             |            |
```

## 6. Data Model

The repository adds one versioned JSON Mention catalog.

Each catalog segment contains these fields.

```text
case_ids
fixture_path
fixture_sha256
paragraph_node_id
source_segment_label
source_text_sha256
gold_mentions
```

Each Gold mention contains these fields.

```text
text
start
end
```

The repository adds Application DTOs for Mention proposer input, Mention proposals, and proposal batches.

The evaluator writes one disposable JSON report and one disposable plain-text review report.

The report does not become Ledger or Archive authority.

## 7. APIs / Interfaces

The local comparison command is:

```bash
uv run python scripts/verify_php1_span_proposers.py \
  [--config <config-path>] \
  --output <report-path> \
  --review-report <review-path>
```

The command returns zero after a completed comparison.

The command returns nonzero for a typed blocked result or a contract failure.

The GLiNER Adapter uses `gliner` version `0.2.28` through the workspace lock file.

## 8. Behavior & Domain Rules

The evaluator derives Source segments with the existing PHP-1 segmentation policy.

The evaluator retains the catalog DocumentNode ID as annotation provenance.

The evaluator uses the current DocumentNode ID after H21-CAT-09 produces one match.

The evaluator scores exact character spans.

The evaluator counts an unmatched proposal as a false positive.

The evaluator counts an unmatched Gold mention as a false negative.

The evaluator classifies a proper proposal subspan as truncated.

The evaluator classifies a proposal that contains the Gold mention as expanded.

The evaluator classifies another partial overlap as crossing.

The evaluator classifies a Gold mention without an overlapping proposal as missing.

The evaluator measures model load time separately from warm inference latency.

The evaluator excludes one unscored GLiNER warm-up call from latency measurements.

The evaluator treats a tool score as proposer metadata.

The evaluator does not convert a tool score into source confidence or evidence confidence.

The evaluator uses the Mention catalog only for evaluation.

## 9. Acceptance Criteria

- AC-H21-CAT-01: Tests prove the catalog covers every derived Source segment once.
- AC-H21-CAT-02: Tests prove source digest and exact-span drift block evaluation.
- AC-H21-CAT-03: Tests prove a derived DocumentNode ID change reanchors without source drift.
- AC-H21-PORT-01: Fake-Port tests prove valid spans pass in source order.
- AC-H21-PORT-02: Fake-Port tests prove invalid and duplicate spans reject the batch.
- AC-H21-GLI-01: Adapter tests prove pinned model, revision, label, threshold, and device use.
- AC-H21-GLI-02: Adapter tests prove valid mapping and malformed-result failures.
- AC-H21-QWN-01: Tests prove one proposed name maps to every exact occurrence.
- AC-H21-REP-01: Tests prove precision, recall, F1, and Boundary result calculations.
- AC-H21-REP-02: Tests prove latency and three-run stability calculations.
- AC-H21-REP-03: Tests prove the report exposes every false positive and false negative.
- AC-H21-ISO-01: Pipeline tests prove public ingestion retains PHP-1 V3.
- AC-H21-LOCAL-01: The three local fixtures produce one completed three-run comparison.
- AC-H21-LOCAL-02: The review report exposes source text, Gold mentions, and both proposer results.

## 10. Reference Implementations

- H2 corpus replay: `scripts/php1_diagnostic_support.py`.
- H2 report entry point: `scripts/verify_php1_h2.py`.
- Model span validation: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Lazy Adapter exports: `packages/adapters/src/kotekomi_adapters/__init__.py`.

## 11. Constraints and Halt Conditions

The implementer must not tune the GLiNER threshold against the Mention catalog.

The implementer must not use either proposer output to define a Gold mention.

The implementer must halt if the evaluator cannot distinguish model load time from inference latency.

The implementer must halt if the comparison changes production PHP-1 behavior.
