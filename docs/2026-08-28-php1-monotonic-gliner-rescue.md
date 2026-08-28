# TDD: PHP-1 Monotonic GLiNER Rescue

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H2.3
- Depends on: [Organization Mention Input and Benchmark Integrity](2026-08-28-php1-organization-mention-input-and-benchmark-integrity.md)

## 1. Context & Problem

The corrected baseline measures Qwen2.5 and GLiNER against one aligned benchmark.

Qwen2.5 has demonstrated high-precision mentions that later stages must retain.

GLiNER can propose additional source-valid spans that Qwen2.5 missed.

H2.2 sent every combined proposal through another semantic qualification task.

That task removed demonstrated Qwen2.5 true positives and did not select a production path.

**Baseline candidate** means one source-valid Qwen2.5 proposal from the corrected baseline.

**Rescue candidate** means one additional source-valid GLiNER proposal.

**Candidate group** means source-local expressions grouped only by exact text or an explicit parenthetical alias declaration.

**Monotonic rescue run** means a run that retains every baseline observation and adds Rescue candidates.

### Primary end-to-end flow

1. The evaluator validates the corrected baseline and its input digests.
2. The evaluator retains every Baseline candidate and baseline pair result.
3. The evaluator adds source-valid GLiNER spans and deterministic alias provenance.
4. The evaluator creates only new pairs that contain a Rescue candidate group.
5. Qwen2.5 judges those new pairs in the Complete relation subset.
6. The evaluator compares end-to-end mention and relation results with the corrected baseline.

## 2. Goals

- An operator sees whether GLiNER adds useful coverage without erasing Qwen2.5 behavior.
- An operator sees every added span, excluded overlap, and resulting new pair.
- An operator sees end-to-end relation gains instead of mention recall alone.
- A later TDD receives evidence for or against production adoption.

## 3. Requirements

### Baseline binding

- H23-BIND-01: The evaluator accepts one completed corrected baseline.
- H23-BIND-02: The evaluator validates policy, catalog, prompt, model, and source digests.
- H23-BIND-03: The evaluator rejects a partial or drifted baseline.

### Monotonic fusion

- H23-FUSE-01: The evaluator retains every Baseline candidate with its original provenance.
- H23-FUSE-02: The evaluator adds each source-valid GLiNER span absent from the baseline.
- H23-FUSE-03: An exact duplicate adds GLiNER provenance to the Baseline candidate.
- H23-FUSE-04: Unequal overlapping spans remain separate and visible.
- H23-FUSE-05: An explicit parenthetical initialism shares one Candidate group.
- H23-FUSE-06: The evaluator performs no per-candidate semantic qualification model call.
- H23-FUSE-07: Source-valid candidates do not become validated Organizations or accepted Ledger state.
- H23-FUSE-08: The evaluator excludes overlapping Candidate groups from pair generation and records the reason.

### Incremental pair judgments

- H23-PAIR-01: The evaluator reuses every baseline pair result without another model call.
- H23-PAIR-02: The evaluator creates new pairs only when one group contains a Rescue candidate.
- H23-PAIR-03: The evaluator runs new pair judgments only in the Complete relation subset.
- H23-PAIR-04: The evaluator retains each model result and verifier result.
- H23-PAIR-05: The evaluator records authoritative input and complete observable output for every stage.

### Comparison

- H23-CMP-01: The evaluator runs three production-equivalent repetitions.
- H23-CMP-02: Each repetition retains every Baseline candidate and pair result.
- H23-CMP-03: Each repetition retains every baseline Target match.
- H23-CMP-04: Each repetition improves exact Mention recall.
- H23-CMP-05: Each repetition matches at least one additional relation target.
- H23-CMP-06: No repetition accepts a relation outside the Complete relation subset catalog.
- H23-CMP-07: The report records raw Mention precision, pair growth, and latency as diagnostics.
- H23-CMP-08: Every invoked model task reaches one terminal result.

### Production isolation

- H23-ISO-01: The public ingestion Pipeline continues to use PHP-1 V3.
- H23-ISO-02: The evaluator writes no accepted Ledger state.
- H23-ISO-03: The evaluator records `selected_for_followup` only when every comparison gate passes.
- H23-ISO-04: Selection authorizes a later production-adoption TDD.

## 4. Proposed Architecture

```text
Corrected baseline + GLiNER proposals
                 |
                 v
          Monotonic fusion
            /          \
           v            v
 Reused baseline pairs  New candidate pairs
           \            /
            v          v
       Relation comparison
                 |
                 v
          H2.3 experiment report
```

The evaluator owns baseline binding, monotonic fusion, and comparison.

The Application Layer owns source-span validation and alias grouping.

The existing pair task and verifier own new relation judgments.

## 5. Key Interactions

```text
Operator      Evaluator       Baseline       GLiNER       Qwen2.5
   |              |               |             |             |
   | run H2.3     |               |             |             |
   |------------->| validate      |             |             |
   |              |-------------->|             |             |
   |              | retain        |             |             |
   |              |---------------------------->| spans       |
   |              | fuse and derive new pairs                 |
   |              |------------------------------------------>|
   |              |<------------------------------------------|
   | report       |               |             |             |
   |<-------------|               |             |             |
```

## 6. Data Model

The H2.3 report records Baseline inputs, GLiNER inputs, Mention candidates, Candidate groups, pair exclusions, and Candidate pairs.

The H2.3 report records the exact corrected-baseline full-report digest.

The report records reused pair results separately from new pair results.

The report records each comparison gate and one selection status.

The report remains disposable derived state.

The report records raw model output, ModelRun identity, prompt digest, and verified hypotheses for each relation judgment.

## 7. APIs / Interfaces

The local H2.3 command accepts a corrected baseline report.

The command writes one full JSON report, one compact summary, and one review report.

The command returns zero after a complete selected or not-selected experiment.

The command returns nonzero after a typed blocked result or contract failure.

## 8. Behavior & Domain Rules

The evaluator treats proposer scores as diagnostic metadata.

The evaluator does not convert proposer scores into evidence confidence.

The evaluator does not remove a Baseline candidate because GLiNER disagrees.

The evaluator does not treat an overlap as an alias without a literal alias declaration.

The evaluator does not generate a relationship Candidate pair between overlapping source spans.

Source-span validation proves only that a proposer copied authoritative characters.

Source-span validation does not prove that the copied expression denotes an Organization.

The evaluator compares relations only where the catalog declares complete coverage.

## 9. Acceptance Criteria

- AC-H23-BIND-01: Tests prove drifted baseline inputs block before fusion.
- AC-H23-FUSE-01: Tests prove all Baseline candidates survive fusion.
- AC-H23-FUSE-02: Tests prove exact duplicates add provenance and unequal overlaps remain visible but unpaired.
- AC-H23-FUSE-03: Tests prove parenthetical aliases share one identity.
- AC-H23-PAIR-01: Tests prove baseline pair results are reused without model calls.
- AC-H23-PAIR-02: Tests prove only pairs with a Rescue candidate group invoke the model.
- AC-H23-CMP-01: Tests prove each comparison gate contributes to selection status.
- AC-H23-CMP-02: Three local runs produce one complete comparison.
- AC-H23-ISO-01: Pipeline tests prove public ingestion retains PHP-1 V3.
- AC-H23-REP-01: Tests prove the review report exposes source, Gold, proposer, fusion, exclusion, and relation task records.

## 10. Reference Implementations

- Source span validation: `packages/application/src/kotekomi_application/organization_mention_proposer.py`.
- Alias grouping: `packages/application/src/kotekomi_application/organization_mention_qualification.py`.
- H2 pair judgment: `scripts/php1_diagnostic_support.py`.
- H2.1 scoring: `scripts/php1_span_proposer_evaluation.py`.

## 11. Constraints and Halt Conditions

H2.3 remains a diagnostic experiment.

H2.3 does not add accepted Organization, Assertion, or Relationship records.

H2.3 does not promote a source-valid candidate to a validated Organization.

H2.3 does not change the eight-hypothesis PHP-1 limit.

## 12. Observed Result

The human-reviewed Gold replay contains 209 exact Mentions across 164 Source segments.

The raw Qwen and GLiNER union reached exact Mention recall `0.851675`.

The same union reached precision `0.631206` and F1 `0.725051`.

The union recovered 40 Qwen misses and added 81 false positives.

Most false positives came from overlapping boundaries, generic references, unresolved acronyms, and Place-versus-government ambiguity.

This result confirms complementary GLiNER coverage but rejects raw union as a production path.

PHP-1 V3 remains the production path.

The next bounded work must reconcile boundaries, qualify entity type, and resolve references before production adoption.
