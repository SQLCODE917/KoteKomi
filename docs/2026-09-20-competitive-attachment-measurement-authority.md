# TDD: CEA-1.6 Attachment Measurement Authority

- Status: Accepted; implementation in progress; production inactive
- Deliverable ID: `CEA-1.6`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1.5 Calibrated Competitive Edge Filter](2026-09-19-competitive-attachment-edge-filter-calibration.md)
- Development Gold: [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

CEA-1.5 found stable score rankings but no safe threshold for V8 or V9.
Its first outcome vocabulary called that result `ranking_failure`.
That name conflated unstable ranking with stable scores that were not separable.

An independent reviewer proposed a deterministic target-containment rejection rule.
The reviewer evaluated the rule against a fragment-containment proxy for Attachment Gold.
The proxy matched the sixteen diagnostic labels.
The proxy did not match KoteKomi's normalized occurrence-level Attachment Gold over the full pools.

KoteKomi needs one authoritative measurement path before it tests another semantic task.

### Terms

**Attachment Gold** means the reviewed `CompetitiveAttachmentGoldDecision` Event set after the three approved CEA-1.3 normalization changes.

**R1-strict** means a rule that rejects a Pool Edge when its Candidate properly contains its Target Event range.

**Gold-positive loss** means an Attachment Gold Event that R1-strict rejects.

**Diagnostic Control** means one occurrence-specific Pool Edge selected to expose one rule's positive or negative behavior.

**Second-Opinion Review** means the exact Markdown that the human obtains from Claude through standard input and standard output.

### Hypothesis

> Official normalized Attachment Gold will show that R1-strict removes valid attachments that the sixteen-case diagnostic did not expose.

### Primary flow

1. KoteKomi validates the sealed CEA-1.5 inputs and reconstructs Attachment Gold through the declared Pipeline function.
2. KoteKomi applies R1-strict to every development and validation Pool Edge.
3. KoteKomi records every rule decision and compares it with Attachment Gold.
4. KoteKomi writes Diagnostic Controls and a self-contained second-opinion handoff.
5. The human sends the handoff to Claude and KoteKomi binds the returned review to the experiment package.

CEA-1.6 uses no model execution for the attachment experiment.
CEA-1.6 produces no canonical intelligence.

## 2. Goals

- An operator can distinguish unstable ranking from stable non-separability.
- An operator can audit one deterministic rejection rule against every occurrence-level Pool Edge.
- A reviewer can see every valid attachment that the rule would delete.
- A future diagnostic cannot treat target containment as a safe rejection signal without positive controls.
- A second-opinion reviewer receives a self-contained and digest-bound evidence package.

## 3. Requirements

### Evidence authority

- CEA16-EVD-01: The Pipeline must validate the sealed CEA-1.5 run metadata, pools, tasks, and source roots.
- CEA16-EVD-02: The Pipeline must reconstruct Attachment Gold from `CompetitiveAttachmentGoldDecision` records.
- CEA16-EVD-03: The Pipeline must apply only the three reviewed CEA-1.3 normalization changes.
- CEA16-EVD-04: The Pipeline must require 490 development and 257 validation Pool Edges.
- CEA16-EVD-05: The Pipeline must reject a foreign Candidate, Event, source range, digest, or phase.
- CEA16-EVD-06: Fragment containment must not create or replace an Attachment Gold decision.

### Calibration outcome

- CEA16-CAL-01: `ranking_unstable` must identify changed cross-class score ordering across repetitions.
- CEA16-CAL-02: `not_separable` must identify stable ordering with no safe threshold.
- CEA16-CAL-03: `inconclusive` must identify a safe threshold that does not clear the break-even gate.
- CEA16-CAL-04: `calibratable` must identify a threshold that clears every declared gate.
- CEA16-CAL-05: The Application Layer must not expose `ranking_failure`.
- CEA16-CAL-06: The preserved V8 and V9 evidence must resolve to `not_separable` without model execution.

### R1-strict audit

- CEA16-AUD-01: KoteKomi must evaluate R1-strict from exact Candidate and Target Event ranges.
- CEA16-AUD-02: Each decision must preserve the Pool Edge, Candidate, Target Event, source text, expected answer, and rule answer.
- CEA16-AUD-03: The development report must contain 22 rule firings, 15 Gold-negative removals, and 7 Gold-positive losses.
- CEA16-AUD-04: The validation report must contain 9 rule firings, 4 Gold-negative removals, and 5 Gold-positive losses.
- CEA16-AUD-05: The combined report must contain 31 rule firings, 19 Gold-negative removals, and 12 Gold-positive losses.
- CEA16-AUD-06: Any Gold-positive loss must make the rule outcome `unsafe`.
- CEA16-AUD-07: A rule decision must not delete its Pool Edge evidence.

### Diagnostic controls

- CEA16-CTL-01: The Pipeline must preserve the sealed CEA-1.5 diagnostic catalog unchanged.
- CEA16-CTL-02: The Pipeline must write a successor control catalog from development Gold only.
- CEA16-CTL-03: The successor catalog must include the mixed Palantir and AWS Candidate as a Gold-negative control.
- CEA16-CTL-04: The successor catalog must include at least two Gold-positive target-containing Candidates.
- CEA16-CTL-05: Each control must preserve exact Candidate and Target Event ranges.

### Evidence package

- CEA16-PKG-01: The runner must expose `run`, `record-second-opinion`, and `finalize` actions.
- CEA16-PKG-02: `run` must write the audit report, human review, controls, handoff, manifest, and status.
- CEA16-PKG-03: The handoff must state the hypothesis, method, authoritative Gold path, scorecard, exact counterexamples, and review questions.
- CEA16-PKG-04: The handoff must include all twelve Gold-positive losses.
- CEA16-PKG-05: KoteKomi must report the exact handoff path and expected review path without creating or invoking an executable Claude launcher.
- CEA16-PKG-06: The human must invoke Claude with the handoff on standard input and the review on standard output.
- CEA16-PKG-07: `record-second-opinion` must require the human-reported Claude exit code and reject any value other than zero.
- CEA16-PKG-08: `record-second-opinion` must bind a successful non-empty review to its input digest.
- CEA16-PKG-09: `finalize` must require an evidence-backed verification for each material review claim.
- CEA16-PKG-10: The terminal manifest must bind every input and output digest.
- CEA16-PKG-11: Every action must report zero ProposedChanges and zero accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.5 evidence
          |
          v
official Attachment Gold
          |
          v
  R1-strict decisions
          |
          v
audit report + controls + handoff
          |
          v
human-run Claude review
          |
          v
verified terminal package
```

The Application Layer owns the audit DTOs.
The Pipeline owns Attachment Gold reconstruction, rule evaluation, controls, and reports.
The disposable runner owns orchestration and evidence packaging.
The human owns the external Claude invocation.

## 5. Key Interactions

```text
Agent             Runner             Pipeline             Human
  | run              |                  |                   |
  |----------------->| validate + audit |                   |
  |                  |----------------->|                   |
  |                  | report + handoff |                   |
  |                  |<-----------------|                   |
  |                  | handoff + review paths              |
  |                  |------------------------------------->|
  |                  |                  | Claude via stdin  |
  |                  |                  | review via stdout |
  | record review    |<-------------------------------------|
  |----------------->| digest review    |                   |
  | verify + finalize|                  |                   |
```

## 6. Data Model

CEA-1.6 adds Application Layer DTOs for one R1-strict decision, one phase report, one complete audit report, one Diagnostic Control, one second-opinion receipt, one review-claim verification, one manifest, and one status.

These DTOs are experimental evidence rather than Domain Core records.

CEA-1.6 adds no Ledger schema and no accepted record.

## 7. APIs / Interfaces

The runner `run` action accepts one CEA-1.5 run root and one output root.

The runner `record-second-opinion` action accepts one output root and one human-reported exit code.

The runner `finalize` action accepts one output root and one structured claim-verification file.

The agent gives the human an exact one-line command with this shape:

```text
claude -p --model opus --effort high --add-dir RUN_ROOT
  < second-opinion-handoff.md
  > claude-opus-review.md
```

KoteKomi does not create or execute that command. After the human reports the terminal exit code, `record-second-opinion --reported-exit-code 0` binds the handoff and review digests. A nonzero reported exit code is rejected.

## 8. Behavior & Domain Rules

- Attachment Gold is the evaluation authority.
- R1-strict is an experiment subject rather than an admission policy.
- Validation use remains disclosed because the prior reviewer inspected validation Gold.
- V8 remains the cleaner baseline.
- V9 remains preserved development-tuned evidence.
- CEA-1.6 does not change prompts, Pool Edges, Candidates, Events, or Gold.
- CEA-1.6 does not execute Qwen, ingestion, or Wiki projection.
- CEA-1.6 does not activate production behavior.

## 9. Acceptance Criteria

- CEA16-ACC-01: Unit tests prove all four calibration outcome states.
- CEA16-ACC-02: Unit tests prove Attachment Gold comes from reviewed occurrence-level decisions.
- CEA16-ACC-03: Pipeline tests reproduce every exact R1-strict count.
- CEA16-ACC-04: Pipeline tests preserve all twelve Gold-positive losses.
- CEA16-ACC-05: Pipeline tests reject foreign and digest-drifted evidence.
- CEA16-ACC-06: Runner tests verify the complete handoff, reported review path, absence of an executable Claude launcher, and human-reported exit-code contract.
- CEA16-ACC-07: Runner tests verify review receipt and claim-verification closure.
- CEA16-ACC-08: The model-free experiment completes with `unsafe` as the R1-strict outcome.
- CEA16-ACC-09: The full repository suite passes.
- CEA16-ACC-10: The terminal package reports zero ProposedChanges and zero accepted writes.

## 10. Reference Implementations

- Gold reconstruction: `scripts/run_competitive_attachment_edge_filter_experiment.py`
- Calibration outcome: `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_edge_filter_calibration.py`
- Evidence packaging: `scripts/run_competitive_attachment_edge_filter_calibration.py`

## 11. Constraints and Halt Conditions

- Stop when reconstructed Gold does not match the sealed candidate inventory.
- Stop when an exact count differs from CEA16-AUD-03 through CEA16-AUD-05.
- Stop when the sealed CEA-1.5 diagnostic catalog changes.
- Stop when the second-opinion review is empty or Claude exits unsuccessfully.
- Stop when claim verification omits a material review claim.
- Stop when any action would write canonical intelligence.
