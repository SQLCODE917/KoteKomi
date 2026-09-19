# TDD: Competitive Event Attachment MVP

- Status: Verified; hypothesis supported; production integration not activated
- Deliverable ID: `CEA-1`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Parent evidence:
  [Source-Grounded Proposition Scope Experiment](2026-09-17-source-grounded-proposition-scope-experiment.md)
- Development Gold:
  [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

KoteKomi has exact source-grounded Events and exact Fragment Candidates.
The current proposition experiment asks Qwen2.5 whether one candidate belongs to one Event.
That independent question conceals sibling Events in the same SourceSegment.
The best prompt reconstructed only two of twenty development Events exactly.
The same run accepted 57 Gold-overreaching candidates and rejected 70 Gold-compatible candidates.
Its 379 candidate rows represent 162 source occurrences across six development SourceSegments.
The approved Gold also contains exact fragments that belong to several Events.
The MVP tests whether one competitive decision improves this boundary.

### Terms

**Competing Event Set** means every reviewed Gold source-grounded Event in one SourceSegment.
**Attachment Candidate** means one exact source occurrence considered against a Competing Event Set.
**Attachment Edge** means one derived link between exact candidate and Event occurrences.
**Attachment Set** means every Event linked to one Attachment Candidate.
**Gold Attachment Set** means the Attachment Set derived from approved Proposition Gold.
**Sibling-Event Leakage** means a false Attachment Edge to a sibling Event.
**Protected Recall** covers entity, qualification, and proposition character recall.
**Task-Local Event Label** means `E1` through `En` within one model task.
**Non-Whitespace Character Set** means the source positions whose characters are not Unicode whitespace.

### Hypothesis

> Presenting all co-occurring Events together will reduce sibling-Event leakage and improve exact proposition reconstruction without losing entity or qualification recall.

### Primary flow

1. The Pipeline groups approved Events and existing Fragment Candidates by SourceSegment.
2. KoteKomi builds one deduplicated candidate-by-Event matrix and proves Gold coverage.
3. The Pipeline reconstructs prompt-v3 and runs a small competitive diagnostic.
4. Qwen2.5 selects zero, one, or several Task-Local Event Labels for each candidate.
5. KoteKomi maps labels to Event occurrences and compares development and frozen validation results.

This MVP produces derived experiment evidence only.

## 2. Goals

- An operator can inspect one exact candidate against every competing Event.
- An operator can distinguish missing candidates from incorrect attachment judgments.
- The experiment can represent a fragment shared by several Events.
- The experiment measures occurrence errors before identity summaries.
- The experiment compares competitive attachment with the archived independent baseline.
- The experiment reaches one reproducible `supported`, `mixed`, or `falsified` result.

## 3. Requirements

### Authority and scope

- CEA-AUT-01: KoteKomi reads source text from the accepted DocumentRepresentationBundle.
- CEA-AUT-02: Every candidate and Event range must replay exactly against its SourceSegment.
- CEA-AUT-03: Repeated equal text at different ranges must remain separate occurrences.
- CEA-AUT-04: Gold must supply evaluation labels only.
- CEA-AUT-05: Model-visible case data contains source text and Task-Local Event Labels only.
- CEA-AUT-06: The experiment must create zero ProposedChanges and zero accepted Ledger writes.
- CEA-AUT-07: The experiment must not assign a semantic role or governed Event type.

### Oracle and baseline

- CEA-ORB-01: The Pipeline must group Gold Events by phase and SourceSegment digest.
- CEA-ORB-02: The Pipeline must union Fragment Candidates across each Competing Event Set.
- CEA-ORB-03: Equal ranges must produce one candidate with all reasons and parent IDs.
- CEA-ORB-04: Distinct equal-text ranges must remain distinct candidates.
- CEA-ORB-05: A Gold set contains each Event whose Gold scope contains the candidate's source characters.
- CEA-ORB-06: A candidate with an empty Gold Attachment Set must receive the Gold result `NONE`.
- CEA-ORB-07: Compatible candidates must cover every Gold fragment's source characters.
- CEA-ORB-08: The preflight must report uncovered fragments before any model execution.
- CEA-ORB-09: The baseline must include the existing deterministic Event-expression attachment.
- CEA-ORB-10: Each archived prompt-v3 `Y` answer must produce one Attachment Edge.
- CEA-ORB-11: The baseline must preserve archived `N`, `U`, malformed, failed, and missing outcomes.
- CEA-ORB-12: The baseline must validate its catalog, prompt, input, result, and runtime digests.
- CEA-ORB-13: The preflight must report every inventory and edge count.

### Competitive task

- CEA-TASK-01: One model task must contain one candidate and its complete Competing Event Set.
- CEA-TASK-02: KoteKomi must order Event options by exact expression range and stable Event identity.
- CEA-TASK-03: KoteKomi must assign Task-Local Event Labels in that order.
- CEA-TASK-04: One exact SourceSegment copy must mark the candidate occurrence.
- CEA-TASK-05: Each Event option must mark that Event occurrence and the same Candidate occurrence in one exact SourceSegment copy when their ranges are disjoint or nested.
- CEA-TASK-05A: Crossing Candidate and Event ranges must use separate exact Candidate and Event views under the same Event option rather than corrupting or duplicating source text.
- CEA-TASK-06: Separate marked copies must distinguish repeated candidate and Event expressions.
- CEA-TASK-07: Qwen2.5 must return `NONE`, `UNCLEAR`, or labels such as `E1,E3`.
- CEA-TASK-08: A multi-Event answer must use the supplied Event order and contain each label once.
- CEA-TASK-08A: A label means the Candidate as a whole belongs to that Event's source meaning.
- CEA-TASK-08B: `NONE` means the candidate belongs to no listed Event.
- CEA-TASK-08C: `UNCLEAR` means the SourceSegment does not decide the Attachment Set.
- CEA-TASK-09: Surrounding ASCII whitespace must remain non-semantic transport framing.
- CEA-TASK-10: KoteKomi must archive the unmodified raw model output.
- CEA-TASK-11: KoteKomi must reject unknown, duplicate, reordered, mixed, or explanatory output.
- CEA-TASK-12: One failed or invalid task must leave only that candidate unresolved.
- CEA-TASK-13: KoteKomi must attach an exact Event expression to its own Event deterministically.
- CEA-TASK-14: KoteKomi must expose each omitted deterministic attachment.
- CEA-TASK-15: KoteKomi must map each valid model label to its supplied Event occurrence.
- CEA-TASK-16: KoteKomi must construct every decision, Attachment Edge, digest, and trace.
- CEA-TASK-17: The runtime must count the completely formatted input before execution.
- CEA-TASK-18: An oversized task must produce `context_budget_blocked` without truncation.

### Diagnostic gate

- CEA-DIA-01: The diagnostic catalog must use approved development Gold only.
- CEA-DIA-02: The catalog must contain one candidate expected to attach to one of five Events.
- CEA-DIA-03: The catalog must contain one subject shared by coordinated Events.
- CEA-DIA-04: The catalog must contain one temporal expression shared by several Events.
- CEA-DIA-05: The catalog must contain one attribution source.
- CEA-DIA-06: The catalog must contain one clausal complement.
- CEA-DIA-07: The catalog must contain one `NONE` candidate.
- CEA-DIA-08: The catalog must contain one candidate with a multi-Event Gold Attachment Set.
- CEA-DIA-09: Each case must retain complete data-in, data-out, Gold, evaluation, and timing evidence.
- CEA-DIA-10: Every valid diagnostic output must satisfy the finite-answer contract.
- CEA-DIA-11: The multi-Event case must retain every expected Event label.
- CEA-DIA-12: Human review must approve label clarity and occurrence distinction.
- CEA-DIA-13: Diagnostic approval must bind the invariant execution contract, not phase-local Event labels.

### Development and validation

- CEA-RUN-01: Development must contain the existing twenty development Events in six SourceSegments.
- CEA-RUN-02: Development must execute three repetitions under one pinned runtime profile.
- CEA-RUN-03: Development can change the prompt, rendering, answer syntax, or candidate policy.
- CEA-RUN-04: The Pipeline must freeze those four inputs and their digests before validation.
- CEA-RUN-05: Validation must contain the existing twenty validation Events.
- CEA-RUN-06: Validation must execute once after the freeze.
- CEA-RUN-07: Validation results must not change the prompt or policy inside CEA-1.
- CEA-RUN-08: Every repetition must retain complete data-in, data-out, mapping, lineage, and timing.
- CEA-RUN-09: The three development result fingerprints must match for a `supported` result.
- CEA-RUN-10: The report must identify validation as a transfer check.

### Evaluation

- CEA-EVL-01: Exact-set accuracy must compare predicted and Gold sets per candidate occurrence.
- CEA-EVL-02: Edge precision, recall, and F1 must score candidate-to-Event occurrence pairs.
- CEA-EVL-03: Sibling-Event Leakage must count false edges outside each nonempty Gold set.
- CEA-EVL-04: Shared-fragment recall must score Gold edges from candidates attached to several Events.
- CEA-EVL-05: `NONE` correctness must score exact empty-set predictions.
- CEA-EVL-06: The evaluator must separate `UNCLEAR`, malformed, failed, and unresolved rates.
- CEA-EVL-07: Entity-occurrence retention must use the existing reviewed entity occurrences.
- CEA-EVL-08: Qualification-fragment retention must use the existing reviewed qualification labels.
- CEA-EVL-09: Character precision, recall, and F1 must compare reconstructed Event scopes with Gold.
- CEA-EVL-10: Exact complete-Event count must require equal Non-Whitespace Character Sets.
- CEA-EVL-11: The report must include calls, tokens, latency, and result fingerprints.
- CEA-EVL-12: Identity-level summaries must follow occurrence-level metrics and cannot replace them.
- CEA-EVL-13: Every metric must use the same candidate inventory as the prompt-v3 baseline.
- CEA-EVL-14: An unresolved candidate cannot count as an exact Attachment Set match.

### Outcome

- CEA-OUT-01: A completed final report must record exactly `supported`, `mixed`, or `falsified`.
- CEA-OUT-02: `supported` requires every acceptance gate in this TDD.
- CEA-OUT-03: `falsified` requires accuracy not to rise and leakage not to fall in both phases.
- CEA-OUT-04: Every other valid completed result must record `mixed`.
- CEA-OUT-05: An incomplete or invalid execution must have no experimental outcome.
- CEA-OUT-06: No CEA-1 outcome can activate production behavior.

## 4. Proposed Architecture

```text
SourceSegment + Events + existing Fragment Candidates
                         |
                         v
              Candidate Matrix Builder
                         |
              +----------+----------+
              |                     |
              v                     v
      prompt-v3 baseline      Qwen competitive task
              |                     |
              +----------+----------+
                         v
               deterministic mapper
                         |
                         v
          proposition reconstruction + evaluator
```

The Application Layer owns grouping, task construction, mapping, and reconstruction.
The existing ModelRuntime Port owns Qwen2.5 execution evidence.
The Pipeline owns phase orchestration, Gold comparison, and result classification.
The Domain Core receives no new record.

## 5. Key Interactions

```text
Operator       Pipeline       Application Layer       Qwen2.5       Evaluator
   |              |                  |                    |              |
   | prepare      |                  |                    |              |
   |------------->| build matrix     |                    |              |
   |              |----------------->| validate ranges    |              |
   |              |<-----------------| matrix + baseline  |              |
   |              | preflight Gold ------------------------------->     |
   | diagnostic   |                  |                    |              |
   |------------->| one candidate    |                    |              |
   |              |----------------->| render task        |              |
   |              |                  |------------------->|              |
   |              |                  | labels             |              |
   |              |                  |<-------------------|              |
   |              |<-----------------| map decision       |              |
   | run phase    | repeat candidates and preserve evidence              |
   |------------->|----------------------------------------------------->|
   | report paths |<-----------------------------------------------------|
```

## 6. Data Model

`CompetitiveAttachmentCandidate` records one exact range, text, proposal reasons, and parent evidence.
`CompetitiveAttachmentEventOption` records one Task-Local Event Label and exact Event occurrence.
`CompetitiveAttachmentGoldDecision` records one candidate's Gold Attachment Set for evaluation only.
`CompetitiveAttachmentDecision` records deterministic edges, raw output, parsed labels, mapped edges, and status.
`CompetitiveAttachmentMatrix` records one SourceSegment, its candidates, Event options, decisions, and digests.
`CompetitiveAttachmentCaseEvaluation` records one candidate's baseline, competitive result, Gold result, and errors.
`CompetitiveAttachmentPhaseReport` records one phase's metrics, execution counts, fingerprints, and outcome inputs.
These types are Application Layer DTOs.
The Pipeline serializes validated DTOs as derived experiment evidence.

## 7. APIs / Interfaces

The runner must expose `prepare`, `diagnose`, `run`, `finalize`, and `compare`.
`prepare` must create the matrix, oracle, baseline, preflight, and immutable manifest.
`diagnose` must execute only the frozen diagnostic catalog.
`run` must execute one named phase and repetition from an immutable manifest.
`finalize` must reject missing, duplicate, changed, or invalid candidate results.
`compare` must produce baseline deltas, phase metrics, and the final experimental outcome.
Each operation must write schema-versioned JSON and a human-readable review file.
Each output must identify every input, prompt, runtime, model, and parent digest.

## 8. Behavior & Domain Rules

KoteKomi must order candidates by source start, source end, and exact text.
KoteKomi must order Event options by expression start, expression end, and stable Event identity.
KoteKomi must union deterministic and valid model Attachment Edges without deleting either lineage.
`NONE` must map to an empty model-proposed Attachment Set.
`UNCLEAR` must leave the candidate unresolved.
An invalid output must leave the candidate unresolved and preserve the raw output.
A shared candidate must retain every distinct positive Attachment Edge.
Candidate deduplication must preserve every source reason and parent record.
Proposition reconstruction must union selected candidate character ranges per Event.
Proposition reconstruction must preserve separated source ranges as separated fragments.
The evaluator must read approved Gold directly rather than a normalized paraphrase.
The validation manifest must freeze before validation output exists.
The experiment must retain the current production path unchanged.

## 9. Acceptance Criteria

- AC-CEA-AUT-01: Tests reject changed source text, ranges, Event bindings, and catalog digests.
- AC-CEA-AUT-02: Tests prove repeated equal strings remain separate occurrences.
- AC-CEA-AUT-03: Reports prove zero ProposedChanges and zero accepted Ledger writes.
- AC-CEA-ORB-01: Preflight reproduces forty Gold Events across nineteen SourceSegments.
- AC-CEA-ORB-02: Preflight proves complete Gold fragment coverage before model execution.
- AC-CEA-ORB-03: A fixture reconstructs the prompt-v3 baseline from archived finite answers.
- AC-CEA-ORB-04: Baseline reconstruction preserves every unresolved and invalid disposition.
- AC-CEA-TASK-01: Fake-Port tests preserve all competing Event options in one model input.
- AC-CEA-TASK-02: Parser tests accept ordered single-label and multi-label answers.
- AC-CEA-TASK-03: Parser tests accept `NONE` and `UNCLEAR` and reject mixed answers.
- AC-CEA-TASK-04: Mapping tests prove Task-Local Event Labels cannot escape their task.
- AC-CEA-TASK-05: Tests prove deterministic own-Event attachment survives a model omission.
- AC-CEA-TASK-06: Tests prove token preflight blocks an oversized task without truncation.
- AC-CEA-DIA-01: The diagnostic review covers all seven required failure classes.
- AC-CEA-DIA-02: The diagnostic retains its expected multi-Event set without malformed output.
- AC-CEA-DIA-03: Tests prove one approved execution contract accepts different phase-local finite label sets.
- AC-CEA-RUN-01: Three development repetitions produce equal result fingerprints.
- AC-CEA-RUN-02: One frozen validation repetition uses the exact development contract digests.
- AC-CEA-EVL-01: Evaluator fixtures detect occurrence swaps that identity summaries hide.
- AC-CEA-EVL-02: Evaluator fixtures detect sibling leakage and shared-fragment loss.
- AC-CEA-EVL-03: Reports include every metric in CEA-EVL-01 through CEA-EVL-14.
- AC-CEA-OUT-01: A result classifier produces exactly one valid completed outcome.
- AC-CEA-OUT-02: A `supported` result has 100% exact source validity and complete Gold coverage.
- AC-CEA-OUT-03: A `supported` result has zero silent drops and zero canonical writes.
- AC-CEA-OUT-04: A `supported` result strictly improves exact attachment-set accuracy in both phases.
- AC-CEA-OUT-05: A `supported` result reduces Sibling-Event Leakage in both phases.
- AC-CEA-OUT-06: A `supported` result does not reduce Protected Recall in either phase.
- AC-CEA-OUT-07: A `supported` result has stable development fingerprints under the pinned runtime.
- AC-CEA-PLAN: `docs/CHECK_PLAN.md` records deterministic and model-backed verification commands.
- AC-CEA-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Candidate construction: follow `source_grounded_proposition_scope.py`.
- Gold preflight: follow `source_grounded_proposition_stage_local.py`.
- Model execution: follow `source_grounded_proposition_preview.py`.
- Experiment orchestration: follow `run_source_grounded_proposition_scope_experiment.py`.
- Stage evidence: follow `extraction_stage_trace.py`.

## 11. Constraints and Halt Conditions

The Pipeline must halt before model execution when Gold coverage is incomplete.
The Pipeline must halt before development when the diagnostic review is not approved.
The Pipeline must halt before validation until the development contract digests are frozen.
The Pipeline must preserve a validation failure instead of tuning against it inside CEA-1.
The implementation must not add a semantic role vocabulary.
The implementation must not add a new specialist dependency.
The implementation must not change production ingestion.
The implementation must not create a ProposedChange or accepted Ledger record.

## 12. Implementation Evidence

The Application Layer now owns strict competitive-candidate, Event-option, Attachment Edge, decision, matrix, evaluation, metrics, and phase-report DTOs.
The bounded model task exposes only exact source copies and Task-Local Event Labels.
KoteKomi validates the finite answer, maps labels to exact Event occurrences, retains deterministic Event-expression edges, and archives raw execution evidence.
The Pipeline now reconstructs and validates the prompt-v3 baseline, derives the Gold oracle, proves candidate coverage, executes the seven-case diagnostic gate, runs frozen repetitions, and classifies only completed development-plus-validation evidence.
The experiment runner uses an ephemeral Ledger implementation that rejects accepted-state writes.
Production ingestion remains unchanged.

The 2026-09-18 deterministic development preflight reproduced:

- twenty development Events;
- six development SourceSegments;
- 162 deduplicated exact candidate occurrences;
- 96 candidates shared by multiple Gold Events;
- twelve `NONE` candidates;
- complete Gold fragment coverage;
- source validity `1.0`;
- all seven required diagnostic categories.

The seven-case diagnostic produced six exact Attachment Sets.
All seven outputs satisfied the finite-answer contract.
The required multi-Event case retained its complete Attachment Set.
The human approved the diagnostic under reviewer identity `DSerbarinov`.

Diagnostic approval version two binds the invariant execution contract.
Each phase continues to pin its own concrete finite label-schema set.
This distinction prevents different valid Event-label inventories from invalidating one approved task contract.

Three development repetitions each executed 162 model tasks.
All three repetitions produced semantic result fingerprint `366c8ed6c55ca78551652696cdd5bfc7f5c1bb79cb79e476d03d3622cef2e0f0`.
Development exact Attachment Set accuracy rose from `0.104938` to `0.530864`.
Development Sibling-Event Leakage fell from 49 edges to 39 edges.
Development entity recall rose from `0.857143` to `0.968254`.
Development qualification recall rose from `0.575758` to `0.727273`.
Development character F1 rose from `0.714411` to `0.735253`.
Development character precision fell from `0.648509` to `0.626200`.
Development exact complete-Event count fell from two to one.
These regressions remain visible even though the defined Protected Recall gates passed.

The frozen validation repetition executed 179 model tasks across thirteen SourceSegments.
Validation exact Attachment Set accuracy rose from `0.424581` to `0.636872`.
Validation Sibling-Event Leakage fell from twelve edges to ten edges.
Validation entity recall rose from `0.943396` to `1.0`.
Validation qualification recall rose from `0.485714` to `0.685714`.
Validation character precision rose from `0.839656` to `0.886157`.
Validation character recall rose from `0.819466` to `0.894275`.
Validation character F1 rose from `0.829438` to `0.890198`.
Validation exact complete-Event count rose from one to seven.

Validation corrected 53 baseline errors and regressed fifteen baseline successes.
Sixty-five of 179 candidate occurrences retained a nonexact Attachment Set.
Those errors comprise seventeen complete omissions, 25 partial under-attachments, thirteen false-positive `NONE` cases, five over-attachments, and five wrong-set substitutions.
Validation `NONE` correctness remained eight of 21 candidates.
Validation shared-fragment recall remained seventy of 106 Gold edges.

Both phases retained source validity `1.0` and Gold coverage `1.0`.
Both phases produced zero invalid outputs, zero silent drops, and zero canonical writes.
The final comparison classified CEA-1 as `supported` under every defined acceptance gate.
Production integration remains `not_activated`.

Repository closure passed formatting, lint, typecheck, and the cumulative test suite.
The cumulative suite passed 1,639 tests and skipped one test on 2026-09-18.

The approved execution-contract digest is `decb4b692ec1a607bd85bf853a329e108d6325bbd95dd9a5780b6985ee4c054a`.
The validation report digest is `42edef22c8240bf74d7110b18ef4b382f1ebee3d25b1b7ce49742f657feb69b4`.
The final comparison digest is `e8faefb24b2ce331d5018665a25bfbad75c6015dce5f77b4414ddc75b43f0b90`.
