# TDD: PHP-1 Organization Mention Qualification

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H2.2
- Depends on: [Specialized Organization Span Proposer Evaluation](2026-08-27-php1-specialized-organization-span-proposer-evaluation.md)

## 1. Context & Problem

H2.1 shows that Qwen2.5 produces more precise Organization spans than GLiNER.

H2.1 also shows that GLiNER overlaps more Gold mentions than Qwen2.5.

Neither proposer alone supplies the accuracy and coverage that PHP-1 needs.

PHP-1 must treat both outputs as fallible proposals.

PHP-1 must qualify a proposal before it creates a Candidate pair.

**Proposal observation** means one source span that one Mention proposer returns.

**Mention candidate** means one source span with one or more Proposal observations.

**Qualification judgment** means one bounded model result for one Mention candidate.

**Validated Organization mention** means one exact source span that passed a Qualification judgment.

**Organization identity candidate** means one derived group of Validated Organization mentions.

**Alias declaration** means one validated expression that binds an expanded name to an initialism.

### Primary end-to-end flow

1. Qwen2.5 and GLiNER produce Proposal observations for one Source segment.
2. The Application Layer validates each Proposal observation against authoritative source characters.
3. The Application Layer combines observations with the same source span into one Mention candidate.
4. Qwen2.5 judges each Mention candidate against the Organization definition.
5. The Application Layer resolves the returned literal expression to exact source positions.
6. The Application Layer groups explicit document-local aliases into Organization identity candidates.
7. The diagnostic derives Candidate pairs only from Validated Organization mentions.

## 2. Goals

- An operator sees which proposer found each Mention candidate.
- An operator sees why each Mention candidate became validated, rejected, or invalid.
- An operator sees exact source positions that KoteKomi resolved after each model judgment.
- An operator sees explicit expanded-name and initialism aliases grouped within one Document.
- An operator can compare qualified mention quality with the H2.1 proposer baselines.
- A later TDD can select the qualified path without changing Ledger authority.

## 3. Requirements

### Proposal fusion

- H22-FUSE-01: The Application Layer accepts only Proposal observations that match source characters.
- H22-FUSE-02: The Application Layer combines observations with equal start and end positions.
- H22-FUSE-03: A Mention candidate retains every distinct proposer identity and its metadata.
- H22-FUSE-04: The Application Layer preserves Proposal observations with overlapping unequal spans.
- H22-FUSE-05: The Application Layer assigns a deterministic identity to each Mention candidate.
- H22-FUSE-06: The Application Layer orders Mention candidates by source position.

### Qualification task

- H22-JUDGE-01: The diagnostic sends one Source segment and one Mention candidate to each task.
- H22-JUDGE-02: The task uses `paragraph_organization_qualification_v1`.
- H22-JUDGE-03: The task returns one `organization:` line or one defined `reject:` line.
- H22-JUDGE-04: An `organization:` line contains one complete literal Organization expression.
- H22-JUDGE-05: The task returns no source position or internal identifier.
- H22-JUDGE-06: The diagnostic records the raw result and ModelRun provenance.

### Exact source resolution

- H22-SPAN-01: The Application Layer resolves the returned expression against the Source segment.
- H22-SPAN-02: The resolved expression contains the original Mention candidate span.
- H22-SPAN-03: The Application Layer creates one Validated Organization mention after one unique match.
- H22-SPAN-04: The Application Layer records a `rejected` result after a valid `reject:` result.
- H22-SPAN-05: The Application Layer records an `invalid` result for malformed or ambiguous output.
- H22-SPAN-06: Equal final spans become one Validated Organization mention with combined provenance.

### Document-local aliases

- H22-ALIAS-01: The Application Layer groups equal validated names within one representation.
- H22-ALIAS-02: The Application Layer recognizes an explicit parenthetical initialism.
- H22-ALIAS-03: The initialism must match the significant words of the expanded source name.
- H22-ALIAS-04: A leading geographic abbreviation does not contribute to the initialism.
- H22-ALIAS-05: The expanded name becomes the preferred name.
- H22-ALIAS-06: A later validated initialism in the same representation joins the same identity.
- H22-ALIAS-07: A conflicting initialism receives `alias_ambiguous` and joins no expanded identity.
- H22-ALIAS-08: The Application Layer does not resolve aliases across representations.

### Candidate pairs

- H22-PAIR-01: The diagnostic derives pairs only from Validated Organization mentions.
- H22-PAIR-02: The diagnostic derives pairs only within one Source segment.
- H22-PAIR-03: The diagnostic derives no pair between aliases of one Organization identity candidate.
- H22-PAIR-04: The relationship task receives source-local literal names from the selected mentions.

### Evaluation

- H22-EVAL-01: The diagnostic runs three production-equivalent repetitions.
- H22-EVAL-02: The report compares each qualified run with its Qwen2.5 H2.1 run.
- H22-EVAL-03: The report records candidate, qualified, alias, pair, latency, and stability results.
- H22-EVAL-04: The report records `selected` only when every quality gate passes.
- H22-EVAL-05: The report records `not_selected` after a complete run that fails a quality gate.
- H22-EVAL-06: A selected run preserves every exact Qwen2.5 true positive.
- H22-EVAL-07: A selected run matches or exceeds Qwen2.5 exact-span precision.
- H22-EVAL-08: A selected run exceeds Qwen2.5 exact-span recall.
- H22-EVAL-09: A selected run resolves the reviewed NIST alias case.
- H22-EVAL-10: A selected run preserves each mandatory H2 Candidate pair.

### Production isolation

- H22-ISO-01: The public ingestion Pipeline continues to use PHP-1 V3.
- H22-ISO-02: The diagnostic writes no accepted record into a user Ledger.
- H22-ISO-03: A proposer or Qualification judgment creates no accepted Ledger record.

## 4. Proposed Architecture

```text
Authoritative Source segments
             |
             v
      Qwen2.5 + GLiNER
             |
             v
       Proposal fusion
             |
             v
    Qualification tasks
             |
             v
  Exact source resolution
             |
             v
  Alias groups + Candidate pairs
             |
             v
        H2.2 report
```

The Mention proposer Adapters own tool-specific Proposal observations.

The Application Layer owns source validation, fusion, exact resolution, aliases, and pairs.

The model owns only the semantic Qualification judgment.

The diagnostic owns corpus orchestration and report assembly.

## 5. Key Interactions

```text
Diagnostic   Proposers   Application   Model   Report
    |            |            |          |       |
    |----------->| propose    |          |       |
    |<-----------| spans      |          |       |
    |------------------------>| validate |       |
    |                         |          |       |
    |----------------------------------->| judge |
    |<-----------------------------------|       |
    |------------------------>| resolve  |       |
    |------------------------>| aliases  |       |
    |------------------------>| pairs    |       |
    |------------------------------------------->|
```

## 6. Data Model

H2.2 adds Application Layer DTOs for these derived values.

```text
ProposalObservation
MentionCandidate
QualificationJudgment
ValidatedOrganizationMention
AliasDecision
OrganizationIdentityCandidate
QualifiedOrganizationPair
```

Each DTO retains its source or producer identity.

The DTOs do not become Domain Core records.

The diagnostic stores these DTO values only in its disposable report.

## 7. APIs / Interfaces

The local command is:

```bash
uv run python scripts/verify_php1_mention_qualification.py \
  [--config <config-path>] \
  [--comparison-input <h2.1-report-path>] \
  [--qualification-input <qualification-checkpoint-path>] \
  [--qualification-checkpoint <checkpoint-path>] \
  --output <report-path> \
  --review-report <review-path>
```

The command validates and reuses a completed H2.1 report when the operator supplies it.

The command writes a qualification checkpoint after each complete repetition.

The command validates and reuses a completed qualification checkpoint when the operator supplies it.

The command returns zero after `selected` or `not_selected`.

The command returns nonzero after a typed blocked result or contract failure.

The Qualification output contract is:

```text
organization: <complete literal Organization expression>
```

or:

```text
reject: not an organization
```

## 8. Behavior & Domain Rules

The task uses the Organization definition in `docs/agent/domain.md`.

KoteKomi supplies authoritative text and owns every source position.

The model does not create Organization identities, aliases, Candidate pairs, or Ledger records.

An initialism match ignores punctuation and defined function words.

An initialism match can ignore one leading dotted or uppercase geographic abbreviation.

The alias resolver does not merge similar names without an explicit Alias declaration.

An Organization identity candidate remains derived evaluation state.

The diagnostic retains every failed judgment as review evidence.

## 9. Acceptance Criteria

- AC-H22-FUSE-01: Tests prove equal spans combine and unequal overlaps remain distinct.
- AC-H22-FUSE-02: Tests prove source mismatch fails before Qualification.
- AC-H22-JUDGE-01: Tests prove each task receives one Source segment and one candidate.
- AC-H22-JUDGE-02: Tests prove accepted, rejected, malformed, and unavailable model outcomes.
- AC-H22-SPAN-01: Tests prove a partial proposal resolves to one complete source expression.
- AC-H22-SPAN-02: Tests prove a non-overlapping or ambiguous expression is invalid.
- AC-H22-ALIAS-01: Tests prove the NIST declaration and later NIST mention share one identity.
- AC-H22-ALIAS-02: Tests prove a conflicting initialism remains separate and auditable.
- AC-H22-PAIR-01: Tests prove rejected candidates and same-identity aliases create no pair.
- AC-H22-EVAL-01: Tests prove every quality gate contributes to selection status.
- AC-H22-EVAL-02: Tests prove the report exposes all candidate and ModelRun provenance.
- AC-H22-ISO-01: Pipeline tests prove public ingestion retains PHP-1 V3.
- AC-H22-LOCAL-01: The three local fixtures produce one complete three-run report.

## 10. Reference Implementations

- Mention proposer Port: `packages/application/src/kotekomi_application/organization_mention_proposer.py`.
- ModelRun boundary: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- H2.1 scoring: `scripts/php1_span_proposer_evaluation.py`.
- Corpus orchestration: `scripts/php1_diagnostic_support.py`.

## 11. Constraints and Halt Conditions

The implementer must not tune GLiNER against the Gold mention catalog.

The implementer must not use proposer output as Gold mention data.

The implementer must not add a canonical alias record in H2.2.

The implementer must retain PHP-1 V3 when the report records `not_selected`.

## 12. Observed Result

The three local fixtures produced a complete three-run report.

Each repetition produced the same quality counts and selection outcome.

The qualified path increased exact-span recall from `0.695402` to `0.844828` and F1 from `0.778135`
to `0.809917`.

The qualified path reduced exact-span precision from `0.883212` to `0.777778` and did not preserve
every exact Qwen2.5 true positive.

The reviewed NIST alias resolved, and the mandatory Anthropic-Palantir Candidate pair remained
present in every repetition.

The result is `not_selected`.

PHP-1 V3 remains the production path.
