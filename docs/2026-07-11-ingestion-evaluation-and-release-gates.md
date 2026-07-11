# TDD: Ingestion Evaluation and Release Gates

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** all ingestion-program child deliverables

## 1. Context and problem

Unit tests can prove that components accept inputs while the integrated system still loses pages, omits required context, invents claims, cites the wrong occurrence, inflates corroboration, or hides failed work. Completion needs a versioned gold corpus, measurable quality thresholds, end-to-end provenance assertions, and fault injection across every persistence boundary.

## 2. Goals

- Define a representative, redistributable gold corpus and labeled expected outcomes.
- Measure parsing, context, extraction, grounding, lineage, retrieval, coverage, and graph behavior separately.
- Establish non-waivable evidence and integrity gates.
- Test success, valid no-result, abstention, degradation, blocking, failure, cancellation, and recovery.
- Produce a signed/hashed release report tied to exact code, tools, models, policies, schemas, prompts, and corpus version.
- Prevent “works on fixtures” from being confused with provider or production readiness.

## 3. Non-goals and forbidden approaches

This TDD does not demand one model or parser implementation.

Forbidden:

- evaluating only end prose or proposal count;
- using the same model to create and judge all gold labels without human review;
- waiving evidence uniqueness, atomicity, deterministic integrity, or source-history preservation;
- hiding failed documents by removing them from the denominator;
- tuning thresholds on the held-out release set;
- claiming Reuters/AP production readiness from synthetic fixtures alone;
- accepting nondeterministic regressions without recording and bounding them.

## 4. Gold corpus requirements

The first release corpus SHALL contain at least:

- 12 distinct source documents;
- 150 labeled atomic source claims, including explicit no-claim regions;
- 25 claims requiring context outside the focus paragraph;
- 20 claims from tables, footnotes, captions, or structured metadata;
- 10 intentionally ambiguous/unsupported units where abstention or no-claim is expected;
- 4 source-version chains including update, correction, clarification, or withdrawal;
- 3 syndication/republication groups;
- 3 independent-control groups reporting similar facts without derivation;
- 100 labeled retrieval queries including exact and paraphrase cases.

Mandatory format/behavior classes:

- clean born-digital PDF;
- scanned and mixed PDF;
- multi-column and rotated PDF;
- repeated furniture;
- nested sections and lists;
- merged-header and cross-page tables;
- footnote and distant-definition dependencies;
- malformed/corrupt/encrypted PDF;
- NewsML-G2 or equivalent structured-news payload;
- AP-like and Reuters-like authorized/synthetic version chains;
- permitted semantic HTML article;
- exact duplicate, edited republication, partial quotation, and independent report pairs;
- negation, modality, attribution, quantities/units, and temporal-scope claims.

Gold labels SHALL identify source nodes/spans, required context, expected atomic claims, attribution/time/modality, lineage relation, analysis outcome, and acceptable alternatives where the source is genuinely ambiguous.

## 5. Evaluation layers and metrics

### Parsing and representation

- page/status coverage;
- logical reading-order accuracy;
- heading/list hierarchy accuracy;
- text-span and page-region validity;
- table cell/header/span accuracy;
- footnote/caption/reference-link accuracy;
- analyzability classification accuracy.

### Context planning

- required-context recall;
- required-context precision;
- budget compliance;
- manifest determinism;
- correct split/block classification.

### Claim extraction

- atomic claim precision and recall;
- attribution accuracy;
- negation/modality accuracy;
- temporal-scope accuracy;
- quantity/unit exactness;
- abstention/no-claim classification.

### Evidence grounding

- selector uniqueness and exactness;
- direct-support sufficiency;
- context-role completeness;
- table-header evidence completeness;
- replay success from archived artifacts.

### Lineage and retrieval

- false document-level merge count;
- missed known syndication count;
- independent-cluster correctness;
- exact-query rank;
- Recall@10;
- stale-index rejection.

### System integrity

- frozen-plan coverage reconciliation;
- idempotency and duplicate prevention;
- revision-history preservation;
- deterministic rebuild equivalence;
- recovery equivalence after injected failures;
- authoritative-state survival after derived-store deletion.

## 6. Initial release thresholds

These are minimums, not optimization targets:

| Measure | Gate |
|---|---:|
| Archived payload/hash integrity | 1.00 |
| Planned-unit terminal accounting | 1.00 |
| Valid evidence selector uniqueness | 1.00 |
| Historical evidence replay | 1.00 |
| Direct-evidence selector precision | 1.00 |
| Direct-support sufficiency | ≥ 0.95 |
| Required-context recall | ≥ 0.95 |
| Atomic claim precision | ≥ 0.90 |
| Atomic claim recall | ≥ 0.80 |
| Attribution accuracy | ≥ 0.95 |
| Negation/modality accuracy | ≥ 0.95 |
| Temporal-scope accuracy | ≥ 0.90 |
| Table interpretation-context completeness | ≥ 0.95 |
| Retrieval Recall@10 | ≥ 0.95 |
| Exact ID/quote rank-1 accuracy | 1.00 |
| False merge among independent controls | 0 |
| Revision/syndication independence inflation | 0 |
| Deterministic exact/lexical rebuild mismatches | 0 |
| Authoritative records lost after derived deletion | 0 |

Metrics use document- and claim-level bootstrap confidence intervals in the report. A threshold passes only when the measured point estimate passes and no observed hard-gate violation exists.

## 7. Hard non-waivable gates

A release fails immediately if any case shows:

- accepted evidence resolving to zero or multiple occurrences;
- accepted source-backed assertion without validated direct support;
- a generated artifact accepted as source evidence;
- missing page/unit/task coverage;
- silent source-version overwrite;
- partial model batch entering proposals;
- parser/model upgrade mutating historical evidence;
- false lineage merge among protected independent controls;
- rights/embargo policy bypass in tests;
- authoritative information loss after deleting derived stores;
- recovery producing duplicate accepted/proposed records;
- an atomicity violation that exposes half-committed archive/ledger state.

## 8. Fault-injection matrix

Tests SHALL inject failure or corruption at least at:

- raw blob write before/after metadata commit;
- ledger transaction before/after archive publication;
- parser startup, mid-document, and canonical serialization;
- OCR startup, selected-page failure, and corrupt output;
- malformed provider DTO and identity/version conflict;
- context tokenizer mismatch and runtime truncation;
- retrieval index partial build, stale manifest, and corrupt files;
- model timeout, cancellation, invalid schema, unknown local reference, and out-of-manifest citation;
- evidence validation disagreement;
- proposal-batch commit before/after boundary;
- process crash followed by recovery at each durable stage;
- derived graph build and atomic activation.

Each case specifies expected durable records, expected absence of records, run/coverage state, retry eligibility, and CLI/API status.

## 9. Test suites

```text
unit/
  domain invariants, canonical serialization, policies, selector validation
contract/
  archive, ledger, parser, OCR, provider, model, retrieval, graph adapters
corpus/
  format-specific gold representation and evidence cases
pipeline/
  staged extraction, coverage, recovery, lineage, derived rebuilds
end_to_end/
  capture → reviewable proposal → acceptance → search/graph explanation
fault_injection/
  matrix above
provider_smoke/
  entitlement-gated, read-only, no public snapshots
```

Every production adapter has the same contract suite as its fake/in-memory equivalent.

## 10. Release report

The generated report SHALL include:

- corpus version/digest and split identities;
- code revision and dependency lock digest;
- schema/migration versions;
- parser, OCR, tokenizer, model, prompt, and generation identities;
- context, coverage, lineage, retrieval, and graph policy IDs;
- every metric numerator, denominator, threshold, and confidence interval;
- all failures, abstentions, blocks, and excluded cases without denominator removal;
- fault-injection results;
- provider conformance/smoke-test status;
- deterministic rebuild digests;
- reviewer/sign-off identity and report digest.

A report is immutable once used for a release decision. A rerun creates a new report.

## 11. Provider-readiness rule

Synthetic fixtures certify provider-adapter logic only. Claiming production readiness for AP, Reuters, or another licensed provider additionally requires:

- project-authorized recorded payloads covering required version/status cases;
- adapter conformance pass over those payloads;
- a successful read-only live smoke test under valid entitlement;
- rights/embargo/export policy tests for the actual agreement;
- no licensed article body in public CI artifacts or logs.

A provider can remain “not certified” without blocking generic PDF/news capabilities, but product documentation must state that scope accurately.

## 12. Completion gates

### Correctness criteria

- Gold labels are independently reviewed and every case maps to archived fixture source locations.
- All metrics are computed from enumerated records with no hidden exclusions.
- Every hard gate and threshold is executable in CI or the entitlement-gated release environment.
- Fault-injection outcomes match expected durable-state and recovery contracts.
- Repeating the release suite with pinned deterministic components reproduces exact integrity/rebuild digests.
- Model-dependent variance is reported over a declared run count/seed policy and still meets thresholds.
- Test failures identify document, unit, task, candidate/assertion, and source evidence involved.

### Success criteria

- The full integrated release suite passes all non-waivable gates and numeric thresholds.
- A release report is generated, hashed, reviewed, and linked from the release artifact.
- At least one end-to-end case demonstrates each: long PDF dependency, table evidence, provider correction, abstention, interruption/recovery, syndication cluster, independent corroboration, retrieval replay, and graph explanation.
- Production provider claims are limited to adapters that satisfy the provider-readiness rule.
- Regression runs fail when seeded defects intentionally violate each hard invariant.

### Failure criteria

This deliverable is incomplete if:

- thresholds exist only in prose or require manual interpretation;
- test denominators omit failures, blocked cases, or no-claim regions;
- evidence exactness is sampled rather than checked exhaustively;
- fault tests inspect logs but not durable state;
- synthetic data is used to claim licensed-provider production readiness;
- release results cannot be tied to exact tools/models/policies/corpus;
- any hard gate can be waived while the system is called complete;
- an intentionally seeded invariant violation does not fail the suite.

## 13. Halt conditions

Stop release and revise the relevant child TDD when a hard gate fails, a threshold regression is statistically or operationally meaningful, a fixture's gold label is disputed, or production/provider behavior cannot be reproduced under the recorded test conditions.
