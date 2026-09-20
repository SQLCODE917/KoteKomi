# TDD: CEA-1.4 High-Recall Competitive Edge Filter

- Status: Mandatory diagnostic rejected; aggregate hypothesis untested; production inactive
- Deliverable ID: `CEA-1.4`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1.3 Bounded Hybrid Selection Diagnostic](2026-09-18-competitive-event-attachment-bounded-hybrid-selection.md)
- Development Gold: [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

CEA-1.3 proved that bounded syntax can recover correct Attachment Edges that competitive Qwen2.5 misses.
CEA-1.3 also proved that a monotonic union retains false Qwen2.5 edges.
The `path_unbounded_plus_complement` pool has a Gold-dependent per-edge exact-set ceiling of `0.925926` in development and `0.905028` in validation.
The current primary pool has ceilings of `0.777778` and `0.804469`.
The larger pool therefore contains useful intelligence that the current union cannot select safely.
KoteKomi does not yet have a bounded semantic filter that can accept or reject one proposed Candidate-to-Event edge.

### Terms

**Pool Edge** means one occurrence-specific Candidate-to-Event edge proposed by competitive Qwen2.5, one syntax policy, or both.
**Maximum Pool** means the union of competitive Qwen2.5 edges and `path_unbounded_plus_complement` syntax edges.
**Pool Arm** means the subset of Maximum Pool edges available under one declared syntax policy.
**Target Edge** means the one Pool Edge that Qwen2.5 judges in one task.
**Sibling Event** means another Event occurrence in the same Competing Event Set.
**Edge Filter Decision** means `Y`, `N`, or `U` for one Target Edge.
**Filtered Attachment Set** means every Event whose Target Edge has a `Y` decision for one Attachment Candidate.
**Pool Gap** means a Candidate for which no Pool Edge exists.
**Unresolved Candidate** means a Candidate with a `U`, invalid, blocked, or failed Edge Filter Decision.

### Hypothesis

> A bounded Qwen2.5 filter over a high-recall occurrence-specific edge pool will improve exact Attachment Set accuracy and edge precision while preserving protected recall.

### Primary flow

1. KoteKomi validates sealed CEA-1 through CEA-1.3 evidence.
2. KoteKomi constructs the Maximum Pool without Gold.
3. Qwen2.5 judges one Target Edge while every Sibling Event remains visible.
4. KoteKomi maps `Y`, `N`, and `U` to typed occurrence-specific decisions.
5. KoteKomi derives and compares filtered Pool Arms.
6. KoteKomi writes a complete experimental evidence package.

CEA-1.4 produces experimental evidence only.

## 2. Goals

- An operator can inspect why each proposed edge was retained, rejected, or left unresolved.
- An operator can compare lower-noise and higher-recall pools without repeated model tasks.
- An operator can see whether Qwen2.5 removes false sibling attachments without losing source-supported intelligence.
- An operator can distinguish evidenced `NONE` from a Pool Gap.
- A future reviewer receives exact data in, raw model output, mapped decisions, metrics, and lineage.

## 3. Requirements

### Frozen evidence

- CEA14-EVD-01: The Pipeline must validate finalized CEA-1 development and validation evidence.
- CEA14-EVD-02: The Pipeline must validate the sealed CEA-1.2 evidence chain.
- CEA14-EVD-03: The Pipeline must validate the sealed CEA-1.3 evidence chain.
- CEA14-EVD-04: The Pipeline must require 162 development Candidates and 179 validation Candidates.
- CEA14-EVD-05: The Pipeline must preserve the approved forty-Event phase split.
- CEA14-EVD-06: The Pipeline must reject changed source, Candidate, Event, prompt, runtime, or predecessor digests.
- CEA14-EVD-07: Gold must not create a Pool Edge or enter a model task.

### Pool construction

- CEA14-POL-01: KoteKomi must construct Pool Edges from archived competitive Qwen2.5 decisions and frozen syntax observations.
- CEA14-POL-02: The Maximum Pool must use `path_unbounded_plus_complement` syntax.
- CEA14-POL-03: The Maximum Pool must contain exactly 490 development edges and 257 validation edges.
- CEA14-POL-04: Each Pool Edge must identify exact Candidate and Event occurrences.
- CEA14-POL-05: Each Pool Edge must preserve whether Qwen2.5, syntax, or both proposed it.
- CEA14-POL-06: Proposal origins must not enter the model task.
- CEA14-POL-07: KoteKomi must derive `path_1_plus_complement`, `path_3_plus_complement`, and `path_unbounded_plus_complement` Pool Arms from the same Maximum Pool decisions.
- CEA14-POL-08: A narrower Pool Arm must be a subset of every wider declared Pool Arm.
- CEA14-POL-09: A Pool Gap must remain explicit.

### Model task

- CEA14-MOD-01: One model task must judge one Target Edge.
- CEA14-MOD-02: The task must contain the exact authoritative SourceSegment.
- CEA14-MOD-03: The task must mark the exact Candidate occurrence.
- CEA14-MOD-04: The task must mark the Target Event occurrence.
- CEA14-MOD-05: The task must show every Sibling Event with a task-local label.
- CEA14-MOD-06: The task must omit canonical IDs, source offsets, Gold labels, proposal origins, and KoteKomi implementation terms.
- CEA14-MOD-07: Qwen2.5 must return exactly `Y`, `N`, or `U`.
- CEA14-MOD-08: The prompt must define every task term before it uses that term.
- CEA14-MOD-09: The prompt examples must not copy a Gold source passage.
- CEA14-MOD-10: The runtime must preserve the complete logical input, raw output, receipt, admission decision, and execution diagnostics.

### Deterministic mapping

- CEA14-MAP-01: `Y` must retain the Target Edge.
- CEA14-MAP-02: `N` must reject the Target Edge without deleting its proposal evidence.
- CEA14-MAP-03: `U` must create an unresolved Edge Filter Decision.
- CEA14-MAP-04: Invalid, blocked, or failed model output must create an unresolved Edge Filter Decision.
- CEA14-MAP-05: A Candidate with one or more Pool Edges and only `N` decisions must produce an evidenced empty Filtered Attachment Set.
- CEA14-MAP-06: A Pool Gap must not become an evidenced empty Filtered Attachment Set.
- CEA14-MAP-07: Any unresolved edge must make its Candidate unresolved for exact-set scoring.
- CEA14-MAP-08: KoteKomi must create every identifier, mapping, trace, and metric.

### Development selection

- CEA14-SEL-01: The diagnostic catalog must contain sixteen development Pool Edges.
- CEA14-SEL-02: The catalog must cover Qwen false positives, syntax-only true and false edges, shared fragments, Gold-`NONE`, repeated occurrences, attribution, time, and long dependency paths.
- CEA14-SEL-02A: The catalog must cover all six development SourceSegments represented in the Maximum Pool.
- CEA14-SEL-02B: The catalog must contain eight Gold-positive edges and eight Gold-negative edges.
- CEA14-SEL-02C: The catalog must include one shared entity occurrence that belongs to multiple Events.
- CEA14-SEL-02D: The catalog must include both proposed edges for one Gold-empty Candidate that mixes Sibling Events.
- CEA14-SEL-03: The diagnostic must execute twice under one pinned prompt and runtime contract.
- CEA14-SEL-04: Human approval must bind the catalog, prompt, runtime, both diagnostic results, and review.
- CEA14-SEL-04A: Human approval requires all sixteen diagnostic decisions to match Gold in both repetitions.
- CEA14-SEL-05: The full development run may reuse one diagnostic result only when the complete task fingerprint matches.
- CEA14-SEL-06: KoteKomi must evaluate all three filtered Pool Arms from one Maximum Pool decision set.
- CEA14-SEL-07: Development Gold must select the arm with the highest exact Attachment Set accuracy.
- CEA14-SEL-08: A tie must prefer higher edge F1, then lower Sibling-Event Leakage, then the narrower Pool Arm.
- CEA14-SEL-09: The selected arm, prompt, runtime, parser, and mapping rules must become frozen before validation.

### Validation

- CEA14-VAL-01: Validation must execute the frozen contract once.
- CEA14-VAL-02: Validation results must not change the same TDD's prompt, pool, parser, selection rule, or mapping.
- CEA14-VAL-03: The report must label validation as diagnostic rather than independent transfer evidence.
- CEA14-VAL-04: A fresh held-out corpus must remain unused until CEA-4 freezes complete proposition assembly.

### Metrics and outcome

- CEA14-MET-01: Each Pool Arm must report exact-set count and accuracy.
- CEA14-MET-02: Each Pool Arm must report occurrence-level edge precision, recall, and F1.
- CEA14-MET-03: Each Pool Arm must report Sibling-Event Leakage and Gold-`NONE` accuracy.
- CEA14-MET-04: Each Pool Arm must report entity, qualification, shared-fragment, and character recall.
- CEA14-MET-05: Each Pool Arm must report unresolved, invalid, blocked, failed, and Pool Gap counts.
- CEA14-MET-06: The report must compare raw pools, filtered pools, competitive Qwen2.5, and the CEA-1.3 primary policy.
- CEA14-MET-07: The report must preserve Gold-dependent Oracle Ceilings as non-deployable context.
- CEA14-OUT-01: The result must be `supported`, `mixed`, or `falsified`.
- CEA14-OUT-02: `supported` requires strict exact-set and edge-precision gains in both phases.
- CEA14-OUT-03: `supported` requires lower Sibling-Event Leakage in both phases.
- CEA14-OUT-04: `supported` requires no regression in entity, qualification, shared-fragment, character, or Gold-`NONE` recall.
- CEA14-OUT-05: `supported` requires zero invalid outputs, zero silent drops, and complete lineage.
- CEA14-OUT-06: `mixed` applies when only some gates or one phase improves.
- CEA14-OUT-07: `falsified` applies when the filter provides no safe gain.
- CEA14-OUT-08: Every outcome must leave production integration inactive.

### Evidence package

- CEA14-PKG-01: The runner must support prepare, diagnose, approve, run, freeze, validate, and finalize actions.
- CEA14-PKG-02: The runner must preserve one canonical JSON record for every task and decision.
- CEA14-PKG-03: The runner must write exact human-readable diagnostic and phase reviews.
- CEA14-PKG-04: The runner must write a development freeze receipt before validation.
- CEA14-PKG-05: The runner must write a summary, second-opinion handoff, manifest, and terminal status.
- CEA14-PKG-06: The manifest must bind every input, prompt, runtime contract, output, and result fingerprint.
- CEA14-PKG-07: The runner must write terminal status only after all evidence validates.

## 4. Proposed Architecture

```text
sealed Qwen and syntax evidence
              |
              v
 deterministic Maximum Pool
              |
              v
 bounded Qwen2.5 Edge Filter
              |
              v
 deterministic Pool Arms
              |
              v
 occurrence-level evaluator
              |
              v
 experimental evidence package
```

The Application Layer owns Pool Edge contracts, model-task construction, output mapping, and Candidate status.
The existing ModelRuntime Port owns Qwen2.5 execution and ModelRun evidence.
The Pipeline owns sealed-evidence validation, Pool Arm derivation, metrics, selection, and reports.
The disposable runner composes the experiment phases.
The Domain Core receives no new record.

## 5. Key Interactions

### Diagnostic and development

```text
Operator        Runner        Application        ModelRuntime        Pipeline
   |               |               |                  |                 |
   | prepare       |               |                  |                 |
   |-------------->| validate pool |                  |                 |
   |               |-------------->|                  |                 |
   | diagnose      | build task    |                  |                 |
   |-------------->|-------------->| execute Y/N/U    |                 |
   |               |               |----------------->|                 |
   |               |               | archive receipt  |                 |
   | review/approve|<--------------|                  |                 |
   | run dev       | reuse exact task or execute      |                 |
   |-------------->|--------------------------------->|                 |
   | freeze        |----------------------------------------------->    |
   |               |                    select arm and bind contract    |
```

### Validation failure

```text
frozen task -> model output -> strict parser
                                | valid Y/N/U -> typed decision
                                | invalid     -> unresolved decision
runtime failure ------------------------------> unresolved decision
unresolved decision --------------------------> no exact-set credit
```

## 6. Data Model

CEA-1.4 adds Application DTOs only.

The DTO family includes `AttachmentPoolEdge`, `AttachmentEdgeFilterTask`, `AttachmentEdgeFilterDecision`, `FilteredAttachmentSet`, `AttachmentEdgeFilterPhaseReport`, `AttachmentEdgeFilterManifest`, and `AttachmentEdgeFilterStatus`.

Every DTO uses strict validation, canonical ordering, source-exact ranges, and deterministic fingerprints.

The Archive preserves task-local inputs, raw model output, ModelRun evidence, and stage traces.

No CEA-1.4 DTO is an accepted Ledger record.

## 7. APIs / Interfaces

The model task has this logical shape:

```text
Passage: <authoritative source with exact Candidate marking>
Target Event: <one task-local label and exact Event marking>
Other Events: <every sibling label and exact expression>
Answer: Y | N | U
```

The runner exposes these actions:

```text
prepare
diagnose
approve-diagnostic
run-development
freeze-development
run-validation
finalize
```

Every long-running action writes a durable log and machine-readable status file.

## 8. Behavior & Domain Rules

- The SourceSegment remains authoritative for every character.
- Pool construction uses proposer evidence instead of Gold.
- Gold may select a development Pool Arm and score results.
- Gold never enters a model task.
- One model decision applies to one exact Target Edge.
- A `Y` decision requires the whole meaningful Candidate to belong to the Target Event.
- A Candidate that imports meaning from a Sibling Event receives `N` for the Target Edge.
- Leading punctuation, trailing punctuation, and source citation markers do not change Candidate meaning.
- All Sibling Events remain visible to preserve competitive context.
- One Maximum Pool decision can serve every narrower Pool Arm.
- A negative decision can suppress an experimental Qwen edge without deleting its provenance.
- An unresolved decision remains visible and cannot become a negative decision.
- A Pool Gap remains different from evidenced `NONE`.
- Validation cannot tune the same contract.
- CEA-1.4 cannot create a ProposedChange or accepted Ledger state.

## 9. Acceptance

- CEA14-ACC-01: Focused tests verify exact Maximum Pool and nested Pool Arm inventories.
- CEA14-ACC-02: Focused tests verify task input contains source-exact Candidate, Target Event, and Sibling Events without canonical identifiers.
- CEA14-ACC-03: Focused tests verify strict `Y`, `N`, and `U` parsing and mapping.
- CEA14-ACC-04: Focused tests verify Pool Gap, evidenced `NONE`, unresolved, and mixed Candidate states.
- CEA14-ACC-05: Focused tests verify proposal provenance survives a negative decision.
- CEA14-ACC-06: Focused tests verify deterministic Pool Arm selection and freeze enforcement.
- CEA14-ACC-07: Focused tests verify occurrence-level metrics and protected recall gates.
- CEA14-ACC-08: Focused tests reject evidence, prompt, runtime, approval, and manifest drift.
- CEA14-ACC-09: The diagnostic writes two complete and stable evidence sets before approval.
- CEA14-ACC-09A: The diagnostic summary reports Gold-exact counts and blocks approval after any semantic mismatch.
- CEA14-ACC-10: Development and validation preserve every model task and decision.
- CEA14-ACC-11: The final package records zero ProposedChanges, zero accepted writes, and inactive production integration.
- CEA14-ACC-12: Formatting, lint, typecheck, focused tests, and the full repository suite pass.

## 10. Implementation State

The Application DTOs, bounded model use case, deterministic Pipeline evaluator, resumable experiment runner, prompt, focused tests, and Check Plan entry are implemented.

The model-free sealed-evidence preflight passes with 162 development Candidates, 179 validation Candidates, 490 development Maximum Pool Edges, 257 validation Maximum Pool Edges, sixteen diagnostic tasks, and no Gold in any model task.

The first two-repetition live diagnostic completed with 32 valid and stable model executions.
Gold comparison found thirteen correct decisions and three repeatable semantic errors.
Two errors retained one over-broad Candidate that mixed the `partnered` and `offered` Events.
One error omitted the shared `Palantir` entity from the `offered` Event.
The first catalog also selected fifteen of sixteen tasks from one SourceSegment.
That diagnostic is rejected and remains preserved under its original run root.

The first corrected prompt required the whole meaningful Candidate to belong to the Target Event.
The corrected catalog covered all six development SourceSegments, balanced eight positive and eight negative edges, and included a shared entity case.
Its two clean repetitions were stable at thirteen of sixteen Gold-exact decisions.
It fixed the original paired Candidate's `partnered` decision and the shared `Palantir` decision, but retained three distinct over-attachments: a Candidate spanning matrix and relative-clause material, matrix-clause time applied to an embedded nominal Event, and an equal-name occurrence imported from the preceding sentence.

A model-free check over all 490 development and 257 validation Maximum-Pool edges rejected a universal deterministic shortcut.
Target-Event containment inside a Candidate was Gold-positive for 26 of 42 development edges and 25 of 29 validation edges.
Temporal Candidates were also legitimately shared across coordinated and inherited verbal Events.
The Maximum Pool contained only one different-sentence edge, so that observation is insufficient for a universal hard rejection rule.

The second corrected prompt preserved the task and finite output contract.
It added generic contrasts for mixed Candidates, embedded Event time, and equal-name occurrences.
Both clean repetitions again produced thirteen of sixteen Gold-exact decisions.
The prompt corrected the mixed Candidate and equal-name occurrence errors.
It retained the embedded Event time error.
It also rejected one reference-supported entity and one attribution predicate incorrectly.

The diagnostic therefore rejects both Prompt Arms under its sixteen-of-sixteen gate.
Prompt tuning exchanged two false-positive edges for two false-negative edges.
The Pipeline did not execute full development or validation after this result.
The aggregate Edge Filter hypothesis remains untested.
CEA-1.5 tests whether one probability threshold explains the Prompt Arm error exchange.

Production integration remains `not_activated`.

## 11. References

- [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- [CEA-1.3 Bounded Hybrid Selection Diagnostic](2026-09-18-competitive-event-attachment-bounded-hybrid-selection.md)
- [`2nd-opinion-4.md`](../2nd-opinion-4.md)
- [TabEAE](https://aclanthology.org/2023.acl-long.701/)
- [Universal Dependencies analysis for relation extraction](https://aclanthology.org/2021.law-1.5/)

## 12. Constraints and Risks

- The current validation partition cannot establish independent transfer.
- The Maximum Pool can still omit a correct edge.
- Qwen2.5 can repeat the semantic errors that created the original edges.
- Per-edge calls increase local runtime cost.
- The experiment cannot establish production readiness.
- A fresh held-out corpus remains reserved for CEA-5.
