# TDD: CEA-1.2 Review-Claim Verification Diagnostic

- Status: Verified; selected review claims classified; production integration not activated
- Deliverable ID: `CEA-1.2`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1.1 Discrimination Experiment](2026-09-18-competitive-event-attachment-discrimination-experiment.md)
- Review under test: [`2nd-opinion-3.md`](../2nd-opinion-3.md)
- Development Gold: [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

CEA-1 improved competitive Event attachment on the frozen validation partition.
CEA-1.1 found persistent errors after prompt and example changes.
A second opinion attributes those errors to candidate segmentation, syntax, output ordering, and experiment design.
Several claims are testable against evidence that KoteKomi already preserved.
Several claims require new human labels or new model executions.
KoteKomi needs to distinguish those two groups before it changes the attachment architecture.

### Terms

**Review Claim** means one falsifiable statement selected from the second opinion.
**Claim Verdict** means `confirmed`, `partly_confirmed`, `falsified`, or `not_testable`.
**Range Relation** identifies how one Attachment Candidate range relates to one Event's Gold ranges.
**Nested Candidate Pair** means two candidates in one SourceSegment where one range contains the other.
**Segmentation Flip** means a Nested Candidate Pair has different Gold Attachment Sets.
**Syntax Observation** means one source-exact dependency path from an Event head to a Candidate head.
**Trigger-Containing Candidate** means one Candidate contains a strict subrange used by an Event expression.
**Unordered Counterfactual** means deterministic re-parsing of archived labels as a mathematical set.
**Handoff Summary** means the compact Markdown evidence supplied to a future reviewer.

### Hypothesis

> Frozen CEA evidence can verify the review's mechanical claims and isolate its unsupported causal claims without another model execution.

### Primary flow

1. The Pipeline validates the frozen CEA-1 and CEA-1.1 evidence chains.
2. KoteKomi derives Range Relations, Syntax Observations, and trigger-containment observations.
3. KoteKomi re-scores syntax-derived Attachment Edges against occurrence-level Gold.
4. KoteKomi re-parses archived invalid answers under an unordered counterfactual.
5. The Pipeline writes one typed report and one Handoff Summary.

CEA-1.2 produces derived experiment evidence only.

## 2. Goals

- An operator can see which review claims the frozen evidence confirms.
- An operator can inspect exact source ranges and dependency paths behind each verdict.
- An operator can compare syntax-derived and archived Qwen attachment metrics.
- An operator can distinguish format-only failures from semantic failures.
- A future reviewer receives one self-contained Handoff Summary.

## 3. Requirements

### Frozen evidence

- CEA12-EVD-01: The Pipeline must validate both CEA-1 phase roots before analysis.
- CEA12-EVD-02: The Pipeline must validate the CEA-1.1 run root before analysis.
- CEA12-EVD-03: The Pipeline must require 162 development and 179 validation candidates.
- CEA12-EVD-04: The Pipeline must require twenty Events in each phase.
- CEA12-EVD-05: The Pipeline must require the approved 24-case CEA-1.1 catalog.
- CEA12-EVD-06: The Pipeline must verify every stored digest that protects an input file.
- CEA12-EVD-07: The Pipeline must preserve development and validation as separate partitions.

### Range analysis

- CEA12-RNG-01: KoteKomi must classify each Candidate and Event pair by Range Relation.
- CEA12-RNG-02: Range Relation values must be `candidate_within_gold`, `gold_within_candidate`, `partial_overlap`, or `disjoint`.
- CEA12-RNG-03: KoteKomi must identify every Nested Candidate Pair with a Segmentation Flip.
- CEA12-RNG-04: The report must preserve both exact ranges, texts, and Attachment Sets for each flip.
- CEA12-RNG-05: One or more Segmentation Flips must confirm segmentation-dependent Gold labels.

### Trigger containment

- CEA12-TRG-01: KoteKomi must detect strict Event-expression subranges inside Candidates.
- CEA12-TRG-02: The report must count Trigger-Containing Candidates across all candidates.
- CEA12-TRG-03: The report must count Trigger-Containing Candidates among all Gold-`NONE` candidates.
- CEA12-TRG-04: The report must count them among the thirteen CEA-1 validation false positives.
- CEA12-TRG-05: The report must count them among the four CEA-1.1 Gold-`NONE` cases.
- CEA12-TRG-06: The report must preserve source-exact split proposals without changing Gold.
- CEA12-TRG-07: A strict majority confirms a claim that trigger containment catches most cases.
- CEA12-TRG-08: One through six covered cases produce `partly_confirmed` for that claim.
- CEA12-TRG-09: Zero covered cases produce `falsified` for that claim.

### Syntax analysis

- CEA12-SYN-01: KoteKomi must use the preserved Stanza analysis for each SourceSegment.
- CEA12-SYN-02: KoteKomi must anchor each Event by its exact head range.
- CEA12-SYN-03: KoteKomi must anchor each Candidate by one token whose head leaves its range.
- CEA12-SYN-04: KoteKomi must record an explicit gap when either anchor is absent or ambiguous.
- CEA12-SYN-05: Each Syntax Observation must preserve every directed dependency-path edge.
- CEA12-SYN-06: KoteKomi must classify paths through the frozen predicate-argument relation families.
- CEA12-SYN-07: Exact Event-expression Candidates must attach to their Event deterministically.
- CEA12-SYN-08: Other structurally supported paths must create syntax-derived experimental edges.
- CEA12-SYN-09: Syntax-derived edges must remain diagnostic evidence.
- CEA12-SYN-10: The report must score exact sets, edges, `NONE`, leakage, and exact Events.
- CEA12-SYN-11: The report must compare syntax metrics with archived CEA-1 Qwen metrics.
- CEA12-SYN-12: Four of four governing cases produce `confirmed` for governing-case recovery.
- CEA12-SYN-13: One through three recovered governing cases produce `partly_confirmed`.
- CEA12-SYN-14: Zero recovered governing cases produce `falsified`.
- CEA12-SYN-15: Syntax can replace Qwen only when validation meets every declared CEA-1 metric.

### Repeated occurrences

- CEA12-REP-01: The report must inspect the three CEA-1.1 repeated-text cases.
- CEA12-REP-02: Each case must preserve the Candidate range and linguistic token IDs.
- CEA12-REP-03: Each case must preserve its syntax-derived and Gold Attachment Sets.
- CEA12-REP-04: Three exact cases produce `confirmed` for deterministic occurrence routing.
- CEA12-REP-05: One or two exact cases produce `partly_confirmed`.
- CEA12-REP-06: Zero exact cases produce `falsified`.

### Archived output counterfactual

- CEA12-OUT-01: KoteKomi must inspect archived CEA-1.1 invalid outputs without changing them.
- CEA12-OUT-02: KoteKomi must accept distinct known labels in any order for the counterfactual.
- CEA12-OUT-03: KoteKomi must reject unknown labels, duplicate labels, and mixed `NONE` answers.
- CEA12-OUT-04: The report must retain the emitted order and canonicalized set separately.
- CEA12-OUT-05: Three semantically exact re-parses produce `confirmed` for format-only failure.
- CEA12-OUT-06: Fewer than three exact re-parses produce `partly_confirmed` or `falsified`.

### Experiment-design claims

- CEA12-DES-01: The report must record SourceSegment concentration in the 24-case catalog.
- CEA12-DES-02: The report must classify statistical significance and generalization as `not_testable`.
- CEA12-DES-03: The report must compare the maximum demonstrated answer cardinality by Prompt Arm.
- CEA12-DES-04: A lower revised maximum confirms the example-cardinality confound.
- CEA12-DES-05: The report must not infer causation from that confound.
- CEA12-DES-06: The claim that true model error is below 65 of 179 must be `not_testable`.
- CEA12-DES-07: The proposed 85 percent syntax threshold must remain unvalidated.

### Evidence and safety

- CEA12-SAF-01: The diagnostic must execute zero model tasks.
- CEA12-SAF-02: The diagnostic must create zero ProposedChanges.
- CEA12-SAF-03: The diagnostic must create zero accepted Ledger writes.
- CEA12-SAF-04: Equal inputs must produce byte-identical JSON and Markdown outputs.
- CEA12-SAF-05: The manifest must bind every input, policy, TDD, and output digest.
- CEA12-SAF-06: The Pipeline must fail on missing, changed, or malformed evidence.
- CEA12-SAF-07: CEA-1.2 must not activate production behavior.

## 4. Proposed Architecture

```text
frozen CEA evidence
        |
        v
strict evidence validator
        |
        v
range + syntax + output analyzers
        |
        v
occurrence-level evaluator
        |
        v
typed report + Handoff Summary
```

The Application Layer owns derived observation and verdict contracts.
The Pipeline owns evidence loading, evaluation, and report rendering.
The existing model evidence remains immutable.
The Domain Core receives no new record.

## 5. Key Interactions

```text
Operator          Pipeline              KoteKomi
   |                 |                     |
   | verify claims   |                     |
   |---------------->| validate evidence   |
   |                 |-------------------->|
   |                 | derive observations |
   |                 |-------------------->|
   |                 | score claims        |
   |                 |<--------------------|
   | paths + summary |                     |
   |<----------------|                     |
```

## 6. Data Model

CEA-1.2 adds Application DTOs for Range Relations, Syntax Observations, Review Claims, and reports.
The DTOs represent derived diagnostic evidence.
The Pipeline stores validated JSON and Markdown files under one run root.
CEA-1.2 adds no Ledger table and no Domain Core record.

## 7. APIs / Interfaces

The CEA runner gains one `verify-review-findings` command.
The command accepts development, validation, CEA-1.1, Gold, and output paths.
The command requires an absent or empty output root.
The command prints every output path and one terminal status.

The run root contains these files:

- `report.json` contains complete typed observations and verdicts.
- `review.md` contains exact data-in and data-out for repository review.
- `summary.json` contains bounded machine-readable findings.
- `second-opinion-summary.md` contains the future handoff.
- `manifest.json` binds input and output digests.
- `status.json` records terminal completion.

## 8. Behavior & Domain Rules

KoteKomi treats syntax as structural evidence rather than semantic authority.
KoteKomi keeps Range Relation analysis separate from semantic attachment judgment.
KoteKomi preserves every repeated occurrence by source range and token identity.
KoteKomi preserves archived output bytes before it applies the counterfactual parser.
KoteKomi marks claims `not_testable` when the frozen evidence cannot decide them.
KoteKomi reports syntax regressions even when syntax improves one selected subset.

## 9. Acceptance Criteria

- AC-CEA12-EVD: Tests reject changed digests, wrong partition counts, and missing evidence.
- AC-CEA12-RNG: Tests prove all Range Relations and at least one real Segmentation Flip.
- AC-CEA12-TRG: Tests reproduce all four declared trigger-containment populations.
- AC-CEA12-SYN: Tests preserve exact anchors, paths, gaps, metrics, and governing verdicts.
- AC-CEA12-REP: Tests preserve and score all three repeated-text occurrences.
- AC-CEA12-OUT: Tests distinguish unordered format failures from semantic failures.
- AC-CEA12-DES: Tests preserve concentration and cardinality evidence without causal inflation.
- AC-CEA12-SAF: Tests prove zero model calls, zero canonical writes, and stable replay.
- AC-CEA12-HND: Tests require every Handoff Summary section and referenced digest.
- AC-CEA12-REG: Existing CEA-1 and CEA-1.1 focused tests pass unchanged.
- AC-CEA12-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Exact occurrence contracts: follow `competitive_event_attachment.py`.
- Dependency paths: follow `event_entity_predicate_arguments.py`.
- Experiment evidence: follow `competitive_attachment_discrimination.py`.
- Operator runner: follow `run_competitive_event_attachment_experiment.py`.

## 11. Constraints and Halt Conditions

Stop when a frozen input digest does not match its manifest.
Stop when development and validation candidate counts differ from 162 and 179.
Stop when the CEA-1.1 catalog differs from 24 approved cases.
Stop when one source range does not replay exact authoritative characters.
Stop when a Syntax Observation silently loses an anchor or path gap.
Stop when the diagnostic would execute Qwen2.5 or another model.
Stop when the diagnostic would change Gold or production behavior.
Stop after CEA-1.2 writes its terminal evidence package.

## 12. Verification Result

CEA-1.2 completed its model-free replay on 2026-09-18.

The replay validated 162 development Candidates and 179 validation Candidates.
The replay validated twenty Events in each phase.
The replay validated all ten CEA-1.1 condition reports and their archived executions.
The replay executed zero model tasks.
The replay created zero ProposedChanges and zero accepted Ledger writes.

The diagnostic found 184 Segmentation Flips among 438 strict Nested Candidate Pairs.
This result confirms that the containment oracle depends on Candidate segmentation.

Trigger containment covered four of thirteen validation false-`NONE` cases.
It covered three of four CEA-1.1 challenge `NONE` cases.
The frozen evidence therefore supports trigger containment as a useful bounded detector.
It does not confirm the stronger claim that trigger containment explains most validation false-`NONE` cases.

The syntax route exactly recovered two of four governing-context cases.
On validation, syntax matched or exceeded archived Qwen on three of eleven declared gates.
It improved character recall, `NONE` accuracy, and qualification recall.
It regressed exact Attachment Set accuracy, edge precision, edge recall, entity recall, Sibling-Event Leakage, and exact Event count.
The result falsifies syntax as a replacement for Qwen under the frozen policy.

The syntax route exactly recovered zero of three repeated-text cases.
Exact occurrence identity remains necessary, but the frozen dependency policy does not solve attachment for these cases.

The unordered parser recovered the label sets from all three archived `E2,E1` outputs.
None of those three label sets matched Gold after KoteKomi mapped the labels to Event occurrences.
The result falsifies the claim that those failures were format-only.

The control Prompt demonstrated a maximum answer cardinality of four.
The examples Prompt demonstrated a maximum answer cardinality of two.
This result confirms a cardinality confound without assigning it causal effect.

The 24-case CEA-1.1 catalog draws fourteen Candidates from one SourceSegment.
CEA-1.2 classifies statistical significance and independent generalization as `not_testable`.
It also classifies the proposed 85 percent syntax threshold and a lower true model-error count as `not_testable`.

The terminal result fingerprint is `65c622e0fd5a5a01aadd197ab02471698361bce91ec9819cb92c8085e6a5beb0`.
The durable local Handoff Summary is `/private/tmp/kotekomi-cea12-review-verification-20260918-sealed-v3/second-opinion-summary.md`.

Final repository verification completed on 2026-09-18.
Formatting, lint, and type checking passed.
The focused CEA verification suite passed 41 tests.
The full repository suite passed 1,666 tests and skipped one test in 345.03 seconds.
The full-suite log is `/private/tmp/kotekomi-cea12-full-checks-20260918.log` and its JUnit report is `/private/tmp/kotekomi-cea12-full-checks-20260918.xml`.
