# TDD: Segment-Bound PHP-1 Evaluation

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H0
- Depends on: [PHP-1 Reliability and Evaluation](2026-08-26-php1-reliability-and-evaluation.md)

## 1. Context & Problem

PHP-1 runs one model task for one authoritative Source segment.

The current packet diagnostic reports one result for each paragraph case.

The diagnostic marks a paragraph case complete when any Source segment produces a verified hypothesis.

The diagnostic does not determine whether that hypothesis matches the case's expected direct relationship.

The packet also uses one paragraph for several case IDs.

The current diagnostic cannot measure target coverage.

**Expectation** means one target direct Organization relationship in one Source segment.

**Expectation catalog** means the versioned structured list of Expectations for the annotation packet.

**Target match** means one verifier-accepted hypothesis with the Expectation's Source segment and Organization pair.

**Unexpected hypothesis** means one verifier-accepted hypothesis that has no Target match.

### Primary end-to-end flow

1. The operator runs the PHP-1 packet diagnostic.
2. The diagnostic resolves each Expectation to one Paragraph and one Source segment.
3. The diagnostic runs PHP-1 for the resolved Source segment.
4. The diagnostic compares each verifier-accepted hypothesis to the Expectation catalog.
5. The diagnostic writes one target result and one unexpected-hypothesis result where applicable.

## 2. Goals

- An operator sees whether PHP-1 matched every eligible direct Organization relationship target.
- An operator sees each unresolved Expectation as an explicit diagnostic result.
- An operator sees no cross-segment credit for a target.
- An operator sees each unexpected verifier-accepted hypothesis.
- The existing paragraph report remains available for historical comparison.

## 3. Requirements

### Expectation catalog

- H0-CATALOG-01: The repository stores one versioned Expectation catalog for the PHP-1 packet.
- H0-CATALOG-02: Each Expectation declares one unique expectation ID.
- H0-CATALOG-03: Each Expectation declares one or more existing eligible packet case IDs.
- H0-CATALOG-04: Each Expectation declares one source fixture path.
- H0-CATALOG-05: Each Expectation declares one paragraph anchor and one Source segment anchor.
- H0-CATALOG-06: Each Expectation declares one literal subject and one literal object in source order.
- H0-CATALOG-07: Each Expectation declares one relationship shape for operator reporting.
- H0-CATALOG-08: The catalog contains only PHP-1 eligible direct Organization relationship targets.
- H0-CATALOG-09: The catalog rejects duplicate expectation IDs.
- H0-CATALOG-10: The catalog rejects duplicate target identities.

### Expectation resolution

- H0-RESOLVE-01: The diagnostic resolves each paragraph anchor to exactly one paragraph DocumentNode.
- H0-RESOLVE-02: The diagnostic derives Source segments through the current PHP-1 Source segment policy.
- H0-RESOLVE-03: The diagnostic resolves each Source segment anchor to exactly one derived Source segment.
- H0-RESOLVE-04: The diagnostic records `unresolved` if an anchor resolves zero or many times.
- H0-RESOLVE-05: The diagnostic stops resolution after an `unresolved` result.

### Target matching

- H0-MATCH-01: The diagnostic compares an Expectation only to hypotheses from its resolved Source segment.
- H0-MATCH-02: The diagnostic requires exact Source copy subject and object text in the declared order.
- H0-MATCH-03: The diagnostic counts only verifier-accepted hypotheses as Target matches.
- H0-MATCH-04: The diagnostic records `matched` when at least one Target match exists.
- H0-MATCH-05: The diagnostic records `missing` after a successful Source segment run finds no Target match.
- H0-MATCH-06: The diagnostic records `blocked` when the Source segment run has no completed model result.
- H0-MATCH-07: The diagnostic records each nonmatching verifier-accepted hypothesis as an Unexpected hypothesis.

### Report

- H0-REPORT-01: The diagnostic preserves the existing paragraph report.
- H0-REPORT-02: The diagnostic writes a separate target report.
- H0-REPORT-03: The target report lists each Expectation once.
- H0-REPORT-04: The target report lists each Unexpected hypothesis once.
- H0-REPORT-05: The target report groups results by relationship shape.
- H0-REPORT-06: The target report records each PHP-1 prompt, schema, and execution-spec digest.

## 4. Proposed Architecture

```text
Annotation packet + Expectation catalog
                |
                v
        Packet diagnostic
          |            |
          v            v
Source segment run   Target matcher
          |            |
          +-----+------+
                v
          Target report
```

The Expectation catalog owns reviewed PHP-1 target definitions.

The packet diagnostic owns Expectation resolution and model execution.

The target matcher owns Target match and Unexpected hypothesis decisions.

The target report owns operator-visible result records.

## 5. Key Interactions

```text
Operator      Packet diagnostic      PHP-1       Target matcher
   |                  |                 |               |
   | run diagnostic   |                 |               |
   |----------------->| resolve target  |               |
   |                  |---------------->|               |
   |                  | verified result |               |
   |                  |<----------------|               |
   |                  |-------------------------------->|
   |                  | target report   |               |
   |<-----------------|                 |               |
```

## 6. Data Model

The Expectation catalog is the JSON file `docs/php1-evaluation-expectations-v1.json`.

The catalog root is:

```json
{
  "schema_version": "php1_evaluation_expectations_v1",
  "expectations": []
}
```

Each Expectation has these fields.

```text
expectation_id
case_ids
fixture_path
paragraph_anchor
source_segment_anchor
subject_text
object_text
relationship_shape
```

`case_ids` is a non-empty ordered list of existing eligible packet case IDs.

The target identity is the fixture path, Source segment anchor, subject text, and object text.

The target report has these fields for each Expectation.

```text
expectation_id
resolution_status
target_status
matched_model_run_ids
matched_proposed_change_ids
prompt_digest
schema_digest
execution_spec_digest
diagnostics
```

The target report has these fields for each Unexpected hypothesis.

```text
source_fixture_path
paragraph_node_id
source_segment_label
subject_text
relation_text
object_text
model_run_id
proposed_change_ids
```

`relationship_shape` describes a review category.

`relationship_shape` does not select a canonical predicate or determine a Target match.

H0 catalogs only direct relations whose ordered subject and object are literal named Organizations in
one current PHP-1 Source segment. Countries, people, pronouns, Events, and multi-segment claims
remain outside this baseline.

The existing faithfulness verifier determines semantic faithfulness for PHP-1.

## 7. APIs / Interfaces

The packet diagnostic accepts the Expectation catalog as a repository-owned input.

The packet diagnostic writes the target report in the existing local diagnostic output.

The target report contains one `target_results` collection and one `unexpected_hypotheses` collection.

The existing paragraph result fields remain unchanged.

## 8. Behavior & Domain Rules

The diagnostic resolves anchors against the reloaded authoritative DocumentRepresentationBundle.

The diagnostic uses the Source copy view for subject and object matching.

The diagnostic uses the authoritative Source segment for EvidenceTarget provenance.

The diagnostic creates no Ledger record from an Expectation.

The diagnostic creates no ProposedChange from an Expectation.

The diagnostic does not treat `unresolved` or `blocked` as `missing`.

The diagnostic records each case association without using a case ID as a Target match key.

The diagnostic preserves multiple Expectations with different Organization pairs in one Source segment.

The diagnostic preserves one Target match result when several packet cases refer to the same Expectation.

## 9. Acceptance Criteria

- AC-H0-01: Catalog tests reject missing fields and duplicate Expectation identities.
- AC-H0-02: Diagnostic tests resolve one paragraph anchor and one Source segment anchor exactly once.
- AC-H0-03: Diagnostic tests record `unresolved` without fallback if either anchor resolves zero or many times.
- AC-H0-04: Target matcher tests reject a verifier-accepted hypothesis from another Source segment.
- AC-H0-05: Target matcher tests reject reversed subject and object text.
- AC-H0-06: Target matcher tests record `matched`, `missing`, and `blocked` results.
- AC-H0-07: Target matcher tests record each nonmatching verifier-accepted hypothesis as unexpected.
- AC-H0-08: Diagnostic tests preserve the legacy paragraph report and add the target report.
- AC-H0-09: The local packet replay writes a deduplicated target report for every catalog Expectation.

## 10. Reference Implementations

- Packet parsing: `scripts/verify_php1_packet.py`.
- Isolated packet replay: `scripts/php1_diagnostic_support.py`.
- Source segment derivation: `packages/application/src/kotekomi_application/context_planning.py`.
- Faithfulness verification: `packages/application/src/kotekomi_application/staged_model_extraction.py`.

## 11. Constraints and Halt Conditions

H0 does not change the PHP-1 prompt.

H0 does not change the PHP-1 model runtime.

H0 does not change the eight-claim limit.

H0 does not classify a source mention as an Organization.

H0 stops when the target report establishes a replayable baseline for later PHP-1 TDDs.
