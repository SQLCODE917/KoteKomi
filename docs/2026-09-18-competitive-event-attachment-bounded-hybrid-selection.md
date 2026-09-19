# TDD: CEA-1.3 Bounded Hybrid Selection Diagnostic

- Status: Verified; hypothesis supported; production integration not activated
- Deliverable ID: `CEA-1.3`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1.2 Review-Claim Verification Diagnostic](2026-09-18-competitive-event-attachment-review-verification.md)
- Development Gold: [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

CEA-1 established that competitive Event visibility improves fragment attachment over independent Event judgments.
CEA-1.1 established that the tested prompt and example changes do not provide a safe production correction.
CEA-1.2 established that unbounded dependency closure over-attaches Candidates and that several review claims were too strong.
A review of the CEA-1.2 evidence identified three narrower questions that frozen evidence can answer without another model execution.
First, punctuation and terminal citation markers can change the containment-derived Gold Attachment Set even when the underlying words are unchanged.
Second, short dependency paths may provide useful high-precision rescue evidence even though unbounded closure does not replace Qwen.
Third, Qwen and bounded syntax may make complementary errors that a conservative hybrid policy can exploit.
KoteKomi needs one model-free diagnostic that corrects the comparison boundary and tests those mechanisms without changing production ingestion.

### Terms

**Authoritative Range** means the exact half-open Candidate range preserved from the authoritative SourceSegment.
**Comparison Range** means a derived half-open range used only to compare that Candidate with Gold fragments.
**Boundary Normalization** means the deterministic derivation of a Comparison Range from an Authoritative Range.
**Syntax Path Limit** means the maximum number of dependency edges admitted by one experimental syntax policy.
**Governed Complement Scope** means one bounded rule that connects an Event head to a Candidate inside one directly governed `obj`, `ccomp`, or `xcomp` subtree.
**Syntax Selection** means the Attachment Set selected by one Syntax Path Limit and optional Governed Complement Scope.
**Union Selection** means the union of archived competitive-Qwen and Syntax Selection edges.
**Intersection Selection** means the intersection of archived competitive-Qwen and Syntax Selection edges.
**Rescue Edge** means one Gold edge recovered by Syntax Selection that archived competitive Qwen missed.
**Oracle Ceiling** means an explicitly labelled upper bound that chooses the better archived source after consulting Gold.
**Foreign Trigger** means an Event head contained in a Candidate whose Candidate anchor is not that Event head.
**Occurrence Identity Preservation** means repeated equal strings remain distinct by exact range and linguistic token identity.
**Semantic Attachment Exactness** means a Candidate's selected Event occurrences exactly equal its Gold Attachment Set.

### Hypothesis

> Boundary-normalized Gold comparison plus archived competitive Qwen union bounded high-precision syntax will improve exact Attachment Set accuracy in both frozen phases without reducing protected recall.

### Primary flow

1. The Pipeline validates the sealed CEA-1 and CEA-1.2 evidence chains.
2. KoteKomi derives one Comparison Range for every authoritative Attachment Candidate.
3. KoteKomi re-derives Gold Attachment Sets and archived model metrics against Comparison Ranges.
4. KoteKomi sweeps bounded syntax and hybrid selection policies over frozen Syntax Observations.
5. KoteKomi evaluates one preregistered primary policy and writes a complete diagnostic package.

CEA-1.3 produces derived experiment evidence only.

## 2. Goals

- An operator can distinguish source authority from comparison normalization.
- An operator can see exactly which Candidate labels change under normalization.
- An operator can compare path lengths one through four and unbounded closure.
- An operator can see whether Governed Complement Scope adds useful edges without recursive propagation.
- An operator can measure Qwen and syntax complementarity before another architecture experiment.
- An operator can inspect occurrence-level inputs, outputs, gaps, and metrics for every policy.
- A future reviewer receives one self-contained handoff document.

## 3. Requirements

### Frozen evidence

- CEA13-EVD-01: The Pipeline must validate the finalized CEA-1 development and validation roots.
- CEA13-EVD-02: The Pipeline must validate the sealed CEA-1.2 report and output digest chain.
- CEA13-EVD-03: The Pipeline must require 162 development and 179 validation Candidates.
- CEA13-EVD-04: The Pipeline must require twenty Gold Events in each phase.
- CEA13-EVD-05: The Pipeline must preserve development and validation as separate frozen phases.
- CEA13-EVD-06: The Pipeline must verify every data-bearing predecessor input digest before analysis.
- CEA13-EVD-07: Historical implementation and TDD digests must remain preserved as receipts even when their mutable repository paths have since changed.
- CEA13-EVD-08: The diagnostic must execute zero model tasks.
- CEA13-EVD-09: The diagnostic must write zero ProposedChanges and zero accepted Ledger records.

### Boundary normalization

- CEA13-NRM-01: The Authoritative Range and its exact text must remain unchanged.
- CEA13-NRM-02: Boundary Normalization must trim leading whitespace.
- CEA13-NRM-03: Boundary Normalization must trim leading comma, semicolon, or colon delimiters and adjacent whitespace.
- CEA13-NRM-04: Boundary Normalization must trim terminal repeated numeric citation markers such as `[11][12]` and adjacent whitespace.
- CEA13-NRM-05: Boundary Normalization must preserve periods, quotes, apostrophes, hyphens, parentheses, and internal punctuation.
- CEA13-NRM-06: Boundary Normalization must preserve an ordered list of applied operations.
- CEA13-NRM-07: An empty Comparison Range must produce an explicit typed diagnostic gap.
- CEA13-NRM-08: Gold containment must use non-whitespace characters from the Comparison Range.
- CEA13-NRM-09: Candidate generation, model input, source evidence, and accepted Gold must not use the Comparison Range.
- CEA13-NRM-10: The current frozen inventory must produce exactly three changed Gold Attachment Sets.
- CEA13-NRM-11: Every changed label must preserve the before and after ranges, texts, and Attachment Sets.

### Syntax policy sweep

- CEA13-SYN-01: The diagnostic must reuse CEA-1.2 Syntax Observations without reparsing source text.
- CEA13-SYN-02: The diagnostic must evaluate maximum dependency path lengths one, two, three, four, and unbounded.
- CEA13-SYN-03: An exact Event-expression Candidate must remain attached to its own Event under every policy.
- CEA13-SYN-04: A bounded path policy must admit a structurally supported observation only when its edge count is within the limit.
- CEA13-SYN-05: A diagnostic gap must never create a syntax edge.
- CEA13-SYN-06: The diagnostic must evaluate every path limit with and without Governed Complement Scope.

### Governed Complement Scope

- CEA13-CMP-01: Candidate and Event anchors must exist in the same sentence.
- CEA13-CMP-02: The first dependency edge from the Event head must point toward one dependent with base relation `obj`, `ccomp`, or `xcomp`.
- CEA13-CMP-03: Every remaining dependency edge must continue from governor to dependent inside that one complement subtree.
- CEA13-CMP-04: The rule must not traverse from a complement into a sibling Event subtree.
- CEA13-CMP-05: The rule must not recursively propagate one Event's scope to another Event.
- CEA13-CMP-06: Every admitted complement edge must preserve its full directed dependency path.

### Hybrid selection

- CEA13-HYB-01: The diagnostic must re-score the archived prompt-v3 independent baseline under normalized Gold.
- CEA13-HYB-02: The diagnostic must re-score archived competitive Qwen under normalized Gold.
- CEA13-HYB-03: Each syntax policy must produce its own occurrence-specific Attachment Sets.
- CEA13-HYB-04: Each syntax policy must produce Union Selection and Intersection Selection with archived competitive Qwen.
- CEA13-HYB-05: The diagnostic must count Rescue Edges and their Gold precision.
- CEA13-HYB-06: The diagnostic must report how many archived-Qwen false-negative edges each syntax policy covers.
- CEA13-HYB-07: The diagnostic must report a whole-source Oracle Ceiling between Qwen and syntax.
- CEA13-HYB-08: The diagnostic must report a per-edge Oracle Ceiling between Qwen and syntax.
- CEA13-HYB-09: Oracle Ceilings must be labelled non-deployable because they consult Gold.
- CEA13-HYB-10: The preregistered primary policy must be archived competitive Qwen union path-length-one syntax plus Governed Complement Scope.
- CEA13-HYB-11: The primary endpoint must be exact Attachment Set accuracy.

### Metrics

- CEA13-MET-01: Every policy must report exact Attachment Set count and accuracy.
- CEA13-MET-02: Every policy must report occurrence-level edge precision, recall, and F1.
- CEA13-MET-03: Every policy must report Sibling-Event Leakage.
- CEA13-MET-04: Every policy must report shared-fragment recall and Gold-`NONE` accuracy.
- CEA13-MET-05: Every policy must report entity and qualification recall.
- CEA13-MET-06: Every policy must report character precision, recall, and F1.
- CEA13-MET-07: Every policy must report exact complete-Event count.
- CEA13-MET-08: Every policy must report anchor-gap count.
- CEA13-MET-09: Metrics must use Candidate and Event occurrences rather than identity-only summaries.

### Head-aware trigger diagnostic

- CEA13-TRG-01: KoteKomi must compare each contained Event head with the Candidate anchor.
- CEA13-TRG-02: A contained Event is foreign only when its head differs from the Candidate anchor.
- CEA13-TRG-03: Missing or ambiguous anchors must produce explicit gaps.
- CEA13-TRG-04: The diagnostic must report precision and recall against normalized Gold-`NONE` labels.
- CEA13-TRG-05: CEA-1.3 must not split or rewrite Candidates.

### Repeated occurrences

- CEA13-OCC-01: The diagnostic must preserve exact range and token identities for all three reviewed repeated-text cases.
- CEA13-OCC-02: The diagnostic must score Occurrence Identity Preservation separately from Semantic Attachment Exactness.
- CEA13-OCC-03: An over-attached correct occurrence must not be reported as an occurrence-identity failure.

### Outcome and safety

- CEA13-OUT-01: The result must be `supported`, `mixed`, or `falsified`.
- CEA13-OUT-02: `supported` requires the primary policy to improve exact Attachment Set accuracy in both phases.
- CEA13-OUT-03: `supported` also requires no regression in entity, qualification, shared-fragment, and character recall in either phase.
- CEA13-OUT-04: `mixed` applies when only one phase improves or an Oracle Ceiling establishes unused headroom without a safe two-phase improvement.
- CEA13-OUT-05: `falsified` applies when neither phase improves and no Oracle Ceiling establishes useful headroom.
- CEA13-OUT-06: The report must state that validation remains diagnostic because the corpus and Gold informed earlier development.
- CEA13-OUT-07: The diagnostic must not change Domain Core, a public CLI, a model prompt, a model runtime, or production ingestion.
- CEA13-OUT-08: The diagnostic must not activate a production integration regardless of outcome.

### Evidence package

- CEA13-PKG-01: The runner must expose a `verify-selection-policy` subcommand.
- CEA13-PKG-02: The runner must write `report.json`.
- CEA13-PKG-03: The runner must write `review.md` with exact data in and data out.
- CEA13-PKG-04: The runner must write `summary.json`.
- CEA13-PKG-05: The runner must write `handoff.md`.
- CEA13-PKG-06: The runner must write `manifest.json` that binds every input and output digest.
- CEA13-PKG-07: The runner must write `status.json` only after all output validation succeeds.
- CEA13-PKG-08: Replaying byte-identical evidence must reproduce the same semantic result fingerprint.

## 4. Proposed Architecture

```text
sealed CEA-1 Candidate matrices and Qwen decisions
                    +
sealed CEA-1.2 Syntax Observations
                    +
approved Proposition Gold
                    |
                    v
        deterministic Boundary Normalizer
                    |
                    v
          normalized comparison oracle
                    |
                    v
   bounded syntax and complement-policy sweep
                    |
                    v
 Qwen / syntax / union / intersection comparison
                    |
                    v
       occurrence-level diagnostic package
```

The Application Layer defines strict experiment DTOs and narrow deterministic policy functions.
The Pipeline validates evidence, reconstructs Attachment Sets, calculates metrics, and renders reports.
The disposable runner composes those stable functions.
No Adapter or Domain Core change is required.

## 5. Key Interactions

### Boundary normalization

1. KoteKomi validates the Candidate against authoritative SourceSegment characters.
2. KoteKomi derives the Comparison Range and records every boundary operation.
3. KoteKomi derives normalized Gold containment without mutating either source or Gold records.
4. KoteKomi reports every label changed by normalization.

### Policy sweep

1. KoteKomi loads each frozen Candidate-to-Event Syntax Observation.
2. KoteKomi applies one declared path limit and complement-rule setting.
3. KoteKomi maps admitted observations into occurrence-specific Attachment Sets.
4. KoteKomi calculates syntax, union, intersection, and Oracle Ceiling metrics.
5. KoteKomi evaluates the preregistered primary policy independently of the best observed variant.

## 6. Data Model

CEA-1.3 adds Application DTOs only.

The DTO family includes `AttachmentComparisonRange`, `AttachmentNormalizationChange`, `AttachmentSyntaxPolicy`, `AttachmentPolicyPhaseResult`, `AttachmentSelectionPolicyReport`, `AttachmentSelectionPolicyManifest`, and `AttachmentSelectionPolicyStatus`.

Every DTO uses strict validation, canonical ordering, and deterministic fingerprints.

The report preserves authoritative ranges, comparison ranges, policy identities, Attachment Sets, metrics, and gaps.

No CEA-1.3 DTO is a canonical Ledger record.

## 7. APIs / Interfaces

```text
normalize_attachment_comparison_range(...)
select_attachment_edges(...)
build_attachment_selection_policy_report(...)
render_attachment_selection_policy_review(...)
render_attachment_selection_policy_handoff(...)
```

```text
uv run python scripts/run_competitive_attachment_selection_experiment.py \
  verify-selection-policy \
  --development-run-root <finalized-cea1-development-root> \
  --validation-run-root <finalized-cea1-validation-root> \
  --review-run-root <sealed-cea12-root> \
  --gold docs/hsq-source-grounded-proposition-gold-v1.json \
  --output-root <empty-output-root>
```

The command performs no network access and no model execution.

## 8. Behavior & Domain Rules

- Source authority always refers to the Authoritative Range rather than the Comparison Range.
- Boundary Normalization changes only evaluation containment semantics.
- Exact equal text at different source ranges remains different evidence.
- Syntax can add experimental evidence but cannot erase an archived Qwen edge.
- Intersection is diagnostic and cannot silently suppress either source's evidence.
- The primary policy remains fixed even when another swept variant scores better.
- Gold may evaluate a policy but may not select production edges.
- A model-free improvement does not authorize production integration.
- Invalid sealed evidence fails fast instead of being repaired.

## 9. Acceptance

- CEA13-ACC-01: Focused tests cover every normalization operation and forbidden trim.
- CEA13-ACC-02: Focused tests prove exactly three frozen Gold labels change.
- CEA13-ACC-03: Focused tests cover all ten syntax-policy variants.
- CEA13-ACC-04: Focused tests prove Governed Complement Scope cannot cross a sibling subtree.
- CEA13-ACC-05: Focused tests verify union, intersection, rescue, and Oracle Ceiling calculations.
- CEA13-ACC-06: Focused tests verify head-aware trigger gaps and repeated-occurrence separation.
- CEA13-ACC-07: The model-free replay writes and validates the complete evidence package.
- CEA13-ACC-08: A second byte-identical replay produces the same semantic result fingerprint.
- CEA13-ACC-09: Formatting, lint, typecheck, and the applicable test suite pass.
- CEA13-ACC-10: The final report records zero model tasks, zero ProposedChanges, zero accepted Ledger writes, and `not_activated` production integration.

## 10. References

- [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- [CEA-1 Competitive Event Attachment MVP](2026-09-18-competitive-event-attachment-mvp.md)
- [CEA-1.1 Discrimination Experiment](2026-09-18-competitive-event-attachment-discrimination-experiment.md)
- [CEA-1.2 Review-Claim Verification Diagnostic](2026-09-18-competitive-event-attachment-review-verification.md)
- [`2nd-opinion-3.md`](../2nd-opinion-3.md)
- [Universal Dependencies](https://universaldependencies.org/)
- [Universal Dependencies analysis for relation extraction](https://aclanthology.org/2021.law-1.5/)
- [PropSegmEnt](https://aclanthology.org/2023.findings-acl.565/)

## 11. Constraints and Risks

- The experiment reuses one corpus and cannot establish independent transfer.
- Dependency parses remain fallible specialist observations.
- The Oracle Ceilings describe available headroom rather than deployable policies.
- A path-length sweep can reveal a useful operating point without proving a universal linguistic rule.
- Model comparison remains deferred until the deterministic evidence has been exhausted.
