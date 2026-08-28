# TDD: PHP-1 Organization Mention Input and Benchmark Integrity

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H2.2.2
- Depends on: [Organization Semantics and Annotation Alignment](2026-08-28-php1-organization-semantics-and-annotation-alignment.md)

## 1. Context & Problem

H2.2.1 aligns the expected Organization spans with one Mention policy.

The current evaluator still loses coordinate provenance when it normalizes whitespace.

The mention output parser rejects a valid segment with more than twelve names.

The evaluator also sends citation-only Source segments to the model.

The relationship catalog lists selected targets instead of all eligible relations in its scored segments.

These defects can create false errors and false success claims.

**Source copy** means the deterministic model-facing text derived from one authoritative Source segment.

**Source copy map** means the boundary mapping from Source copy positions to authoritative positions.

**Model eligibility** means `model_eligible` or `not_applicable_nonlexical` for one Source segment.

**Complete relation subset** means every PHP-1 eligible ordered relation in the selected target Source segments.

**Corrected baseline** means three repeated Qwen2.5 and GLiNER runs against the human-reviewed Mention Gold.

### Primary end-to-end flow

1. The evaluator derives one Source copy and Source copy map from each authoritative Source segment.
2. The evaluator skips only Source segments that contain no lexical content.
3. Qwen2.5 and GLiNER propose names without a repository-owned mention-count cap.
4. KoteKomi validates copy spans and resolves authoritative spans.
5. The evaluator scores mentions against the aligned catalog.
6. The evaluator scores relation judgments against the Complete relation subset.

## 2. Goals

- An operator can trace each scored proposal to exact authoritative characters.
- A high-cardinality Source segment can return every distinct name.
- Citation-only Source segments produce explicit non-applicable results without model calls.
- An operator sees relation precision only where the benchmark is complete.
- H2.3 starts from a reproducible corrected baseline.

## 3. Requirements

### Source copy boundary

- H222-COPY-01: The Application Layer derives one Source copy from authoritative text.
- H222-COPY-02: The Source copy map contains one authoritative boundary for each Source copy boundary.
- H222-COPY-03: The Source copy map preserves every non-whitespace character.
- H222-COPY-04: The Source copy map maps collapsed whitespace to its complete authoritative range.
- H222-COPY-05: KoteKomi rejects a Source copy map whose text or digest does not match its source.
- H222-COPY-06: Each validated proposal records copy and authoritative coordinates.

### Model eligibility

- H222-ELG-01: The evaluator classifies citation-only and ellipsis-only segments as `not_applicable_nonlexical`.
- H222-ELG-02: The evaluator classifies every other non-empty Source segment as `model_eligible`.
- H222-ELG-03: The evaluator invokes no model for `not_applicable_nonlexical`.
- H222-ELG-04: The report retains every non-applicable Source segment.

### Mention output

- H222-MEN-01: The mention contract has no repository-owned line-count limit.
- H222-MEN-02: The parser validates every returned line through the existing literal contract.
- H222-MEN-03: The existing eight-hypothesis limit remains unchanged.
- H222-MEN-04: A repeated distinct name still maps to every exact Source copy occurrence.

### Complete relation subset

- H222-REL-01: The catalog identifies each selected Source segment as relation-complete.
- H222-REL-02: The catalog records every PHP-1 eligible ordered relation in those Source segments.
- H222-REL-03: Each relation records literal subject, relation, and object expressions.
- H222-REL-04: Target matching requires subject direction, relation meaning, object direction, and verifier acceptance.
- H222-REL-05: The evaluator calls a verified relation unexpected only inside the Complete relation subset.
- H222-REL-06: The evaluator treats a reversed relation as a different relation.

### Corrected baseline

- H222-BAS-01: The baseline runs Qwen2.5 and GLiNER three times on all model-eligible segments.
- H222-BAS-02: The baseline records mention precision, recall, F1, latency, and stability.
- H222-BAS-03: The baseline runs Qwen2.5 relation judgments on the Complete relation subset.
- H222-BAS-04: The baseline records target coverage and all unexpected accepted relations in that subset.
- H222-BAS-05: The repository stores a compact baseline summary and full-report digest.
- H222-BAS-06: Full candidate and model outputs remain disposable local reports.

## 4. Proposed Architecture

```text
Authoritative Source segment
          |
          v
 Source copy + map ----> Model eligibility
          |                    |
          | model_eligible     | nonlexical result
          v                    v
   Qwen2.5 + GLiNER       Baseline report
          |
          v
 Span and relation scoring
          |
          v
 Corrected baseline report
```

The Application Layer owns Source copy derivation and coordinate resolution.

The evaluator owns Model eligibility and benchmark scoring.

The catalog owns the Complete relation subset.

## 5. Key Interactions

```text
Evaluator     Application      Model       Catalog       Report
    |              |             |            |            |
    | source text  |             |            |            |
    |------------->| copy + map  |            |            |
    |<-------------|             |            |            |
    | classify     |             |            |            |
    |--------------------------->| propose    |            |
    |<---------------------------|            |            |
    |-------------->| resolve    |            |            |
    |---------------------------------------->| compare    |
    |----------------------------------------------------->|
```

## 6. Data Model

The Application Layer adds a derived Source copy record.

The record contains Source copy text, authoritative text digest, and boundary positions.

The proposal report records copy start, copy end, authoritative start, and authoritative end.

The relation catalog adds a Complete relation subset and literal relation expressions.

The compact baseline summary records policy, Gold catalog, prompt, model, and full-report digests.

The model digest binds the complete available model identity snapshot.

It does not claim a byte-level weights digest when the runtime does not expose one.

## 7. APIs / Interfaces

The source copy boundary resolves a half-open copy range into one half-open authoritative range.

The corrected baseline command writes one full JSON report and one compact JSON summary.

The command returns a typed blocked result when a fixture, model, or catalog is unavailable.

## 8. Behavior & Domain Rules

Whitespace normalization remains a derived model-input transformation.

Source copy positions do not replace authoritative positions.

The evaluator counts non-applicable Source segments in corpus coverage but not model quality denominators.

The evaluator keeps harmless source whitespace unchanged in authoritative text.

The evaluator blocks when selected prose differs semantically from the reviewed Source segment.

The evaluator does not compare text from two parser tools.

The evaluator excludes coordinated participants in one shared action from ordered PHP-1 relations.

Those participants require the later Event-frame slice rather than an invented direction.

## 9. Acceptance Criteria

- AC-H222-COPY-01: Tests prove spaces, newlines, and tabs map back to exact authoritative ranges.
- AC-H222-COPY-02: Tests prove drifted text, digest, and boundaries reject before scoring.
- AC-H222-ELG-01: Tests prove citation and ellipsis controls skip all model calls.
- AC-H222-MEN-01: Tests prove fourteen distinct names parse and score.
- AC-H222-MEN-02: Tests prove the eight-hypothesis limit remains unchanged.
- AC-H222-REL-01: Catalog tests prove all selected Source segments declare complete coverage.
- AC-H222-REL-02: Tests prove direction and relation meaning contribute to Target matching.
- AC-H222-REL-03: Tests prove unexpected relations are evaluated only in complete segments.
- AC-H222-BAS-01: Three local runs produce one completed corrected baseline.
- AC-H222-BAS-02: The compact summary matches the full report digest.
- AC-H222-ISO-01: Pipeline tests prove public ingestion retains PHP-1 V3.

## 10. Reference Implementations

- Source copy rendering: `packages/application/src/kotekomi_application/context_planning.py`.
- Mention parser: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Mention scoring: `scripts/php1_span_proposer_evaluation.py`.
- Relation scoring: `scripts/php1_diagnostic_support.py`.

## 11. Constraints and Halt Conditions

H2.2.2 does not change PDF parsing.

H2.2.2 does not add coreference or Event extraction.

H2.2.2 does not select a production proposer.

## 12. Observed Result

The Source copy map preserves model-facing and authoritative coordinates for every scored proposal.

The current Gold contains 164 Source segments and 209 exact Mention occurrences.

The evaluator classifies 140 segments as model-eligible and 24 as `not_applicable_nonlexical`.

The evaluator invokes no model for a nonlexical segment.

The human review supersedes the earlier 177-Mention corrected baseline.

Every new corrected baseline must bind the current Gold digest before model execution.

The complete current-ontology relation subset contains 15 ordered relations in 9 Source segments.
