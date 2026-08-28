# TDD: PHP-1 Mention and Relationship Diagnosis

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H2
- Depends on: [Segment-Bound PHP-1 Evaluation](2026-08-27-php1-segment-bound-evaluation.md)

## 1. Context & Problem

PHP-1 currently asks one model task to find literal Organization mentions and direct relationships.

H1 showed that a prompt can improve one relationship shape and lose a demonstrated relationship.

The current target report records only the final relationship result.

The report cannot distinguish a missing Organization mention from a missed relationship.

The diagnostic therefore cannot identify the next bounded repair.

**Mention candidate** means one literal Organization string that the model proposes from one Source copy view.

**Candidate pair** means one unordered pair of distinct Mention candidates from one Source copy view.

**Pair judgment** means one model result for one Candidate pair that either proposes one direct
relationship or abstains.

**Mention result** means the validated ordered Mention candidates from one Source copy view.

**H2 target result** means the per-Expectation record that states mention, pair, and relationship
outcomes.

### Primary end-to-end flow

1. The packet diagnostic resolves an H0 Expectation to one authoritative Source segment.
2. The mention task returns literal Organization mentions from that Source segment.
3. KoteKomi validates the mentions and derives Candidate pairs.
4. The relationship task judges each Candidate pair against the same Source segment.
5. The existing verifier decides whether each proposed relationship is source-faithful.
6. The H2 report identifies the stage that matched or missed each Expectation.

## 2. Goals

- An operator sees whether each expected Organization appeared in the Mention result.
- An operator sees whether KoteKomi formed the expected Candidate pair.
- An operator sees whether the pair task abstained, failed validation, or produced a verified relationship.
- The Pipeline retains the stable V3 PHP-1 behavior while H2 evaluates this diagnostic path.

## 3. Requirements

### Mention task

- H2-MENTION-01: The diagnostic sends one Source copy view to one mention task.
- H2-MENTION-02: The mention task uses `paragraph_organization_mention_v1`.
- H2-MENTION-03: The mention task returns one line per distinct Organization name or one defined abstention.
- H2-MENTION-04: Each `mention:` line contains the Source segment label and one Organization string.
- H2-MENTION-05: The diagnostic accepts a Mention candidate only when its text occurs literally in the Source copy view.
- H2-MENTION-06: The diagnostic rejects an entire mention response with an unknown label, duplicate string, or malformed line.
- H2-MENTION-07: The diagnostic orders accepted Mention candidates by their first Source copy position.
- H2-MENTION-08: The diagnostic records the source-copy start and end position for each Mention candidate.

### Candidate pairs

- H2-PAIR-01: The diagnostic derives one Candidate pair for every unordered pair of Mention candidates.
- H2-PAIR-02: The diagnostic derives no Candidate pair across Source segments.
- H2-PAIR-03: The diagnostic records the complete bounded set of Candidate pairs.
- H2-PAIR-04: The diagnostic records zero Candidate pairs when the Mention result has fewer than two candidates.

### Pair judgment

- H2-JUDGE-01: The diagnostic sends one Source copy view and one Candidate pair to each pair task.
- H2-JUDGE-02: The pair task uses `paragraph_organization_pair_relation_v1`.
- H2-JUDGE-03: The pair task returns one existing PHP-1 `claim:` line or the existing PHP-1 abstention.
- H2-JUDGE-04: The pair task can state either direction of the Candidate pair.
- H2-JUDGE-05: The diagnostic sends each non-abstaining pair result through the existing PHP-1 validator and faithfulness verifier.
- H2-JUDGE-06: The diagnostic records the raw pair response, ModelRun identity, validation result, and verifier result.

### H2 report

- H2-REPORT-01: The H2 report includes one H2 target result for every resolved H0 Expectation.
- H2-REPORT-02: Each H2 target result records separate subject and object mention states.
- H2-REPORT-03: Each H2 target result records the Candidate pair state.
- H2-REPORT-04: Each H2 target result records the Pair judgment state.
- H2-REPORT-05: The H2 report records `matched` only after a verifier-accepted claim matches the Expectation pair in its declared direction.
- H2-REPORT-06: The H2 report records one explicit first failed state when an Expectation does not match.
- H2-REPORT-07: The H2 report records prompt, ContextManifest, and ModelRun provenance for every task.
- H2-REPORT-08: The H2 report records unexpected verifier-accepted claims separately from Target matches.

### Production isolation

- H2-ISO-01: The public automatic ingestion Pipeline continues to use `paragraph_hypothesis_segment_v3`.
- H2-ISO-02: H2 writes no ProposedChange, Assertion, Organization, or Relationship into a user Ledger.
- H2-ISO-03: The H2 command uses the packet diagnostic's disposable Ledger and Archive.

## 4. Proposed Architecture

```text
Authoritative Source segment
            |
            v
       Mention task
            |
            v
      Mention result
            |
            v
      Candidate pairs
            |
            v
        Pair tasks
            |
            v
Existing validator and verifier
            |
            v
        H2 report
```

The packet diagnostic owns task orchestration and H2 report assembly.

KoteKomi owns literal validation, position mapping, Candidate pair derivation, and Target matching.

The model owns Mention candidate proposals and Pair judgments.

The existing verifier owns source-faithfulness decisions.

## 5. Key Interactions

```text
Operator    Diagnostic     Model       Verifier       H2 report
   |             |           |             |              |
   | run H2      |           |             |              |
   |------------>| mention   |             |              |
   |             |---------->|             |              |
   |             | mentions  |             |              |
   |             |<----------|             |              |
   |             | pair task |             |              |
   |             |---------->|             |              |
   |             | claim     |             |              |
   |             |<----------|             |              |
   |             |------------------------>|              |
   |             | verified claim          |              |
   |             |<------------------------|              |
   |             |---------------------------------------->|
   | H2 result   |           |             |              |
   |<------------|           |             |              |
```

## 6. Data Model

The repository adds two versioned prompt files.

The repository adds a local `verify_php1_h2.py` command.

The command writes one disposable JSON report.

The command can render an existing H2 JSON report into one plain-text review file per H2 prompt.

Each review file names its prompt file.

Each review file records every resolved H0 Expectation as three groups: full Source segment, expected result, and actual result.

The renderer does not invoke a model or modify a Ledger.

```bash
uv run python scripts/verify_php1_h2.py \
  --input <report-path> \
  --mention-report <mention-review-path> \
  --pair-report <pair-review-path>
```

Each Mention result contains these fields.

```text
source_segment_label
source_copy_text
status
mention_candidates
prompt_id
prompt_digest
context_manifest_id
model_run_id
raw_output
```

Each Mention candidate contains these fields.

```text
organization_text
source_copy_start
source_copy_end
```

Each Pair judgment contains these fields.

```text
first_organization_text
second_organization_text
status
model_run_id
raw_output
verified_hypotheses
```

Each H2 target result contains these fields.

```text
expectation_id
subject_mention_state
object_mention_state
candidate_pair_state
pair_judgment_state
target_status
diagnostics
```

The diagnostic report remains derived local output.

## 7. APIs / Interfaces

The H2 command is:

```bash
uv run python scripts/verify_php1_h2.py [--config <config-path>] --output <report-path>
```

The command returns a nonzero exit status only for a fixture, configuration, or diagnostic contract failure.

The command returns zero after a completed report, including reports with missing Targets.

## 8. Behavior & Domain Rules

The mention task names only literal Organization strings from one Source copy view.

KoteKomi does not resolve pronouns, aliases, or generic descriptions in H2.

The pair task receives only candidates that passed literal mention validation.

The pair task abstains for coordinated participants in one shared action.

KoteKomi does not treat a pair task claim as a Target match before the existing verifier accepts it.

The diagnostic records `subject_mention_missing` before `object_mention_missing` when both expected
mentions are absent.

The diagnostic records `candidate_pair_missing` after both expected mentions are present and the
expected Candidate pair is absent.

The diagnostic records `pair_abstained`, `pair_invalid`, or `pair_unverified` after the expected
Candidate pair exists and the Pair judgment fails.

The diagnostic records `matched` after a verified claim matches the expected ordered pair.

H2 does not alter the eight-claim limit.

H2 does not add coreference, Entity resolution, Event records, new ontology types, or accepted Ledger
state.

## 9. Acceptance Criteria

- AC-H2-MENTION-01: Tests prove literal Mention candidates map to exact Source copy positions in source order.
- AC-H2-MENTION-02: Tests prove malformed, duplicate, unknown-label, and over-limit mention output fails as one rejected response.
- AC-H2-PAIR-01: Tests prove the diagnostic derives each unordered pair once and derives no cross-segment pair.
- AC-H2-JUDGE-01: Tests prove the pair task receives one Source copy view and only its Candidate pair.
- AC-H2-JUDGE-02: Tests prove the diagnostic records abstained, invalid, unverified, and verified Pair judgments.
- AC-H2-REPORT-01: Tests prove an H2 target result identifies each first failed state and a verified Target match.
- AC-H2-REPORT-02: Tests prove the report retains prompt, ContextManifest, ModelRun, and raw-output provenance.
- AC-H2-ISO-01: Pipeline tests prove public automatic ingestion retains the V3 prompt contract.
- AC-H2-ISO-02: Tests prove H2 writes no canonical records into a user Ledger.
- AC-H2-LOCAL-01: The three local packet fixtures produce one completed H2 report with one H2 target result for every resolved H0 Expectation.
- AC-H2-LOCAL-02: The renderer writes one prompt-named review file for mentions and pair judgments from one completed H2 report.

## 10. Reference Implementations

- Source segment resolution: `scripts/php1_diagnostic_support.py`.
- H0 Expectation report: `scripts/verify_php1_packet.py`.
- PHP-1 validation and verification: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Production prompt provenance: `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## 11. Constraints and Halt Conditions

H2 stops after it produces a stage-specific report for the existing H0 Expectation catalog.

The implementer must halt if the H2 report cannot distinguish a missing mention from an abstained Pair
judgment.

The implementer must halt if H2 requires a user Ledger write.
