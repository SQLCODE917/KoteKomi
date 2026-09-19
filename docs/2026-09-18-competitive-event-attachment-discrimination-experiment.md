# TDD: Competitive Event Attachment Discrimination Experiment

- Status: Verified; mixed outcome; production integration not activated
- Deliverable ID: `CEA-1.1`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1 Competitive Event Attachment MVP](2026-09-18-competitive-event-attachment-mvp.md)
- Development Gold: [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)
- Review evidence: [CEA-1.1 Discrimination Experiment Review Handoff](2026-09-18-competitive-event-attachment-discrimination-review-handoff.md)

## 1. Context & Problem

CEA-1 gave Qwen2.5 one Attachment Candidate and every competing Event.
That change improved validation exact Attachment Set accuracy from `0.424581` to `0.636872`.
It also increased entity, qualification, and proposition character recall.
Sixty-five of 179 validation candidates still had a nonexact Attachment Set.
CEA-1 examples showed only prefix-shaped nonempty answers.
The CEA-1 task also described Event argumenthood more clearly than complete proposition membership.
CEA-1.1 tests those two possible causes without changing production ingestion.

### Terms

**Failure Shape** identifies the exact set difference between Gold and predicted Event occurrences.
**Failure Observation** records a deterministic property that can explain a Failure Shape.
**Mechanism Label** records a reviewer's explanation for one nonexact Attachment Set.
**Prompt Arm** identifies one fixed combination of instruction wording and examples.
**Event Order** identifies source order or reversed source order in one model task.
**Order-Sensitive Candidate** produces different canonical Event IDs under the two Event Orders.
**Non-Prefix Gold Set** omits `E1` or skips one lower Event label.
**Jaccard Similarity** measures the intersection divided by the union of two Attachment Sets.
**Hamming Loss** measures incorrect candidate-to-Event cells divided by all scored cells.

### Hypothesis

> Lossless proposition wording and counterbalanced examples improve exact Attachment Sets and reduce position-linked errors without reducing protected recall.

### Primary flow

1. The Pipeline audits every nonexact CEA-1 validation candidate.
2. KoteKomi selects 24 development candidates through one deterministic policy.
3. The operator approves the candidate catalog and four Prompt Arms.
4. Qwen2.5 judges each candidate under two Event Orders.
5. KoteKomi maps task labels to canonical Event occurrences and compares the Prompt Arms.

CEA-1.1 produces experiment evidence only.

## 2. Goals

- An operator can inspect every remaining CEA-1 validation error.
- An operator can distinguish set shape from a reviewed semantic explanation.
- An operator can measure whether task wording or examples cause attachment errors.
- An operator can detect answers that change when Event labels change position.
- The experiment produces one reproducible `supported`, `mixed`, or `falsified` result.

## 3. Requirements

### Frozen evidence

- CEA11-EVD-01: The Pipeline must validate the CEA-1 report, matrices, oracle, inputs, and execution records.
- CEA11-EVD-02: The Pipeline must identify exactly 65 nonexact validation candidates.
- CEA11-EVD-03: The Pipeline must reproduce the five recorded Failure Shape counts.
- CEA11-EVD-04: The Pipeline must preserve exact source, Candidate, Events, model input, and raw output.
- CEA11-EVD-05: The Pipeline must preserve Gold, baseline, and competitive Attachment Sets.
- CEA11-EVD-06: The Pipeline must keep CEA-1 evidence immutable.

### Failure audit

- CEA11-AUD-01: KoteKomi must assign one deterministic Failure Shape to each error.
- CEA11-AUD-02: KoteKomi must record missing and extra Event occurrences separately.
- CEA11-AUD-03: KoteKomi must record candidate reasons and overlapping Gold requirements.
- CEA11-AUD-04: KoteKomi must detect shared Gold, repeated text, Gold prefixes, and prediction prefixes.
- CEA11-AUD-05: The review packet must permit several ordered Mechanism Labels and one rationale.
- CEA11-AUD-06: The Mechanism Labels must be `scope_wording`, `position_bias`, `shared_fragment`, `repeated_occurrence`, `none_overselection`, `genuine_ambiguity`, `gold_or_candidate_issue`, or `other`.
- CEA11-AUD-07: A Mechanism Label must remain review evidence rather than accepted Ledger state.

### Development catalog

- CEA11-CAT-01: The catalog must contain 24 unique development candidate occurrences.
- CEA11-CAT-02: The selector must consider six Non-Prefix Gold Sets first.
- CEA11-CAT-03: The selector must next consider four nonexact `governing_context` candidates.
- CEA11-CAT-04: The selector must next consider four shared-fragment under-attachments.
- CEA11-CAT-05: The selector must next consider four Gold-`NONE` false positives.
- CEA11-CAT-06: The selector must next consider three repeated-text occurrences.
- CEA11-CAT-07: The selector must next consider three CEA-1 exact controls.
- CEA11-CAT-08: The selector must deduplicate after each category.
- CEA11-CAT-09: The selector must fill vacant slots with nonexact candidates in source order.
- CEA11-CAT-10: The model task catalog must contain no validation candidate.

### Prompt Arms

- CEA11-PRM-01: The `control` arm must use the exact CEA-1 prompt.
- CEA11-PRM-02: The `scope` arm must change only the proposition-membership instruction.
- CEA11-PRM-03: The `examples` arm must change only the examples.
- CEA11-PRM-04: The `combined` arm must contain both declared changes.
- CEA11-PRM-05: The new instruction must ask whether removal loses source-stated Event meaning.
- CEA11-PRM-06: The instruction must include attribution, modality, negation, purpose, comparison, time, and location.
- CEA11-PRM-07: The examples must include `E2`, `E1,E3`, and `E2,E4` answers.
- CEA11-PRM-08: The examples must use fictional text that does not copy Gold text.
- CEA11-PRM-09: Every Prompt Arm must retain the CEA-1 finite output contract.
- CEA11-PRM-10: The operator must approve the catalog and Prompt Arm digests before model execution.

### Paired Event Order

- CEA11-ORD-01: Each Prompt Arm must run in source and reversed Event Order.
- CEA11-ORD-02: KoteKomi must assign contiguous task labels after it orders Events.
- CEA11-ORD-03: KoteKomi must map each returned label to its supplied Event occurrence.
- CEA11-ORD-04: KoteKomi must map results back to canonical Event IDs before evaluation.
- CEA11-ORD-05: Reversed ordering must not change Candidate or Event source ranges.
- CEA11-ORD-06: The first pass must execute 192 model tasks.
- CEA11-ORD-07: A second `combined` pass must execute 48 model tasks.

### Evaluation

- CEA11-EVL-01: Exact Attachment Set accuracy remains the primary acceptance metric.
- CEA11-EVL-02: Empty Gold and empty prediction must have Jaccard Similarity `1.0`.
- CEA11-EVL-03: Hamming Loss must score every candidate-to-Event cell.
- CEA11-EVL-04: The report must count under-, over-, substitution-, omission-, and Gold-`NONE` errors.
- CEA11-EVL-05: The report must count Order-Sensitive Candidates after canonical mapping.
- CEA11-EVL-06: The report must measure Non-Prefix Gold Set accuracy.
- CEA11-EVL-07: The report must measure `governing_context` Gold-edge recall.
- CEA11-EVL-08: The report must preserve shared-fragment, `NONE`, entity, and qualification recall.
- CEA11-EVL-09: The report must preserve calls, tokens, latency, prompt digests, and fingerprints.
- CEA11-EVL-10: The report must preserve invalid, blocked, failed, and unresolved outcomes.

### Outcome and safety

- CEA11-OUT-01: The comparison must record `supported`, `mixed`, or `falsified`.
- CEA11-OUT-02: `supported` requires the combined arm to improve exact accuracy and Jaccard in both Event Orders.
- CEA11-OUT-03: `supported` requires the combined arm to lower Hamming Loss in both Event Orders.
- CEA11-OUT-04: `supported` requires lower order sensitivity and no higher sibling leakage.
- CEA11-OUT-05: `supported` requires no regression in protected recall or `NONE` accuracy.
- CEA11-OUT-06: `supported` requires stable repeated `combined` fingerprints.
- CEA11-OUT-07: `falsified` requires neither changed factor to improve its declared mechanism metric.
- CEA11-OUT-08: Every other complete result must be `mixed`.
- CEA11-OUT-09: Every run must preserve source validity `1.0` and Gold coverage `1.0`.
- CEA11-OUT-10: Every run must create zero ProposedChanges and zero accepted Ledger writes.
- CEA11-OUT-11: CEA-1.1 must not activate production behavior.

## 4. Proposed Architecture

```text
frozen CEA-1 evidence
        |
        v
failure audit + 24-case selector
        |
        v
four Prompt Arms x two Event Orders
        |
        v
canonical Event mapping + evaluator
        |
        v
review packet + experiment outcome
```

The Application Layer owns strict experiment DTOs and canonical Event mapping.
The existing bounded model use case owns Qwen2.5 execution.
The Pipeline owns evidence loading, selection, reporting, and comparison.
The Domain Core receives no new record.

## 5. Key Interactions

```text
Operator        Pipeline          KoteKomi          Qwen2.5
   |               |                 |                 |
   | prepare       |                 |                 |
   |-------------->| audit + select  |                 |
   |               |---------------->|                 |
   | review packet |                 |                 |
   |<--------------|                 |                 |
   | approve       |                 |                 |
   |-------------->| render labels   |                 |
   |               |---------------->| bounded task    |
   |               |                 |---------------->|
   |               |                 | finite answer   |
   |               |                 |<----------------|
   |               | map + evaluate  |                 |
   | result        |<----------------|                 |
   |<--------------|                 |                 |
```

## 6. Data Model

CEA-1.1 adds Application DTOs for the audit, Prompt Arm run, metrics, and comparison.
These DTOs represent derived experiment evidence.
The Pipeline stores validated JSON and Markdown copies under the run root.
CEA-1.1 does not add Ledger tables or Domain Core records.

## 7. APIs / Interfaces

The CEA runner gains commands to prepare, approve, run, and compare CEA-1.1.
The execution command gains an optional Event Order and prompt identity.
The default values preserve the exact CEA-1 execution contract.
The runner prints every output path and one terminal status.

## 8. Behavior & Domain Rules

The Pipeline treats validation as consumed diagnostic evidence after it builds the audit.
The Pipeline uses development candidates for every new model task.
The Pipeline maps task-local labels before it compares Event occurrences.
The Pipeline preserves CEA-1 output instead of rewriting it.
The Pipeline records incomplete model work as an explicit terminal outcome.

## 9. Acceptance Criteria

- AC-CEA11-EVD: Tests reproduce all 65 errors and the five Failure Shape counts.
- AC-CEA11-AUD: Tests preserve complete data-in, data-out, set differences, and review fields.
- AC-CEA11-CAT: Tests select 24 unique development candidates with no validation leakage.
- AC-CEA11-PRM: Tests prove each Prompt Arm changes only its declared factor.
- AC-CEA11-ORD: Tests map reversed labels to the same canonical Event occurrences.
- AC-CEA11-EVL: Tests verify Jaccard, Hamming, prefix, order, and protected-recall metrics.
- AC-CEA11-OUT: Tests cover `supported`, `mixed`, and `falsified` classifications.
- AC-CEA11-SAFE: Fake Ledger tests prove zero canonical writes.
- AC-CEA11-REG: Existing CEA-1 tests pass without fixture changes.
- AC-CEA11-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Exact occurrence contracts: follow `competitive_event_attachment.py`.
- Model execution: follow `competitive_event_attachment_preview.py`.
- Experiment reports: follow `competitive_event_attachment_stage_local.py`.
- Operator runner: follow `run_competitive_event_attachment_experiment.py`.

## 11. Constraints and Halt Conditions

Stop before model execution when the audit does not reproduce CEA-1 counts.
Stop before model execution when the catalog or Prompt Arms lack operator approval.
Stop when any model task contains a validation candidate.
Stop when reversed order changes authoritative source ranges.
Stop when one Prompt Arm changes an undeclared factor.
Stop when a result writes a ProposedChange or accepted Ledger record.
Stop after CEA-1.1 records its experimental outcome.

## 12. Implementation Evidence

The Application Layer owns strict failure-audit, catalog, condition-report, and comparison DTOs.
The existing bounded model use case now accepts one pinned Prompt ID and Event Order.
KoteKomi relabels ordered Events before model execution.
KoteKomi maps returned labels to canonical Event occurrences before evaluation.
Execution records bind source input, raw output, Prompt ID, prompt digest, Event Order, and runtime contract.
The Pipeline computes exact-set, Jaccard, Hamming, edge, recall, leakage, and Failure Shape metrics.
The Pipeline records every incomplete model status separately.
The comparison supports `supported`, `mixed`, and `falsified` outcomes.
Production integration remains `not_activated`.

The deterministic preflight consumed the preserved CEA-1 evidence.
It reproduced all 65 nonexact validation candidates.
It reproduced seventeen omissions and 25 under-attachments.
It reproduced thirteen Gold-`NONE` false positives.
It reproduced five over-attachments and five substitutions.
It selected 24 unique development candidates.
The catalog contains six Non-Prefix Gold cases.
It also contains four governing, four shared, four `NONE`, three repeated-text, and three exact-control cases.
The four Prompt Arms pass factor-isolation validation.
Focused formatting, lint, typecheck, and unit tests pass.

The operator approved the catalog and Prompt Arms under reviewer identity `DSerbarinov`.
The approval digest is `784ec392275a63a13d3233a5bf0877ebf0afe7bcb357eb0c8cb825ec1ed231af`.
The catalog digest is `47e13a7cee16b35e8a6222854305a3da6033010a909733716dc655746ba98640`.

The Qwen2.5 replay completed ten conditions and 240 model executions.
Every condition retained source validity `1.0` and Gold coverage `1.0`.
The replay produced zero ProposedChanges and zero accepted Ledger writes.
It produced three invalid finite answers, zero model failures, and zero context-budget blocks.
The repeated combined-arm conditions produced identical semantic results.

The control arm measured exact Attachment Set accuracy `0.416667` in both Event Orders.
Its mean Jaccard Similarity was `0.597222` in source order and `0.569444` in reversed order.
Its Hamming Loss was `0.314286` in source order and `0.271429` in reversed order.

The combined arm measured exact Attachment Set accuracy `0.416667` in source order and `0.458333` in reversed order.
Its mean Jaccard Similarity was `0.520833` in source order and `0.590278` in reversed order.
Its Hamming Loss was `0.300000` in source order and `0.257143` in reversed order.
The combined arm therefore reduced Hamming Loss in both orders but did not improve exact accuracy or Jaccard in both orders.
It increased Order-Sensitive Candidates from seven to eight.
It did not increase Sibling-Event Leakage and preserved `NONE` accuracy.
It did not preserve protected entity and qualification recall in source order.

The scope-only reversed-order condition was the best individual condition, with exact accuracy `0.541667`, mean Jaccard Similarity `0.673611`, and Hamming Loss `0.228571`.
The same Prompt Arm fell to exact accuracy `0.416667`, mean Jaccard Similarity `0.534722`, and Hamming Loss `0.328571` in source order.
Neither the scope factor nor the example factor therefore produced an order-stable improvement.
No Prompt Arm solved any of the four governing-context cases.
The examples did not improve the already strong Non-Prefix Gold cases.
Gold-`NONE`, repeated-text, shared-fragment, and governing-context errors remained substantial.

The comparison classified CEA-1.1 as `mixed`.
Its safety gates failed, so no tested Prompt Arm is eligible for production integration.
The comparison digest is `6f09dd6bb92ec7e8eb775495300914df61e9210243a144db82ead2caa88a71fa`.
Production integration remains `not_activated`.

The result falsifies prompt wording and example balance as sufficient corrections.
It preserves evidence that the remaining blocker is occurrence-sensitive attachment under competing Event order, especially governing context, shared fragments, repeated text, and `NONE` discrimination.
The next bounded experiment must test a different task decomposition rather than tune these Prompt Arms further.

Repository closure passed formatting, lint, typecheck, and the cumulative test suite.
The cumulative suite passed 1,639 tests and skipped one test on 2026-09-18.
