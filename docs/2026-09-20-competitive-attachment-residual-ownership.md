# TDD: CEA-1.7 Residual Attachment Ownership Diagnostic

- Status: Accepted; implementation in progress; production inactive
- Deliverable ID: `CEA-1.7`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1.6 Attachment Measurement Authority](2026-09-20-competitive-attachment-measurement-authority.md)

## 1. Context & Problem

CEA-1.6 proved that target containment alone is an unsafe Attachment rejection rule.

The CEA-1.6 audit contains 31 Pool Edges whose Candidate properly contains its Target Event.

Fourteen Gold-negative Pool Edges also contain a complete Other Event expression.

No Gold-positive Pool Edge has that observed shape.

The remaining 17 Pool Edges include 12 Gold-positive Edges and five Gold-negative Edges.

Exact ranges can identify the first shape without semantic judgment.

Exact ranges cannot decide whether the remaining Candidate text belongs to the Target Event.

CEA-1.7 tests one bounded semantic task for those remaining Pool Edges.

### Terms

**Containment Edge** means a Pool Edge whose Candidate properly contains its Target Event range.

**Foreign Event** means an Other Event whose complete range occurs inside the Candidate.

**Deterministic Mixed Edge** means a Containment Edge that contains a Foreign Event.

**Residual Edge** means a Containment Edge that contains no Foreign Event.

**Candidate Remainder** means the exact Candidate characters before and after its Target Event.

**Residual Ownership** means every meaningful part of the Candidate Remainder describes the fact centered on the Target Event.

### Hypothesis

> A bounded Residual Ownership task can distinguish valid and invalid Residual Edges without losing a Gold-positive Attachment.

### Primary flow

1. KoteKomi reconstructs authoritative Attachment Gold and the 31 Containment Edges.
2. KoteKomi identifies 14 Deterministic Mixed Edges and 17 Residual Edges from exact ranges.
3. KoteKomi sends each development Residual Edge to Qwen twice.
4. Qwen returns one `Y`, `N`, or `U` Residual Ownership judgment.
5. KoteKomi records exact input, raw output, mapping, expected answer, and evaluation.
6. KoteKomi writes a self-contained second-opinion handoff for human-run Claude review.

CEA-1.7 creates no canonical intelligence.

## 2. Goals

- An operator can inspect whether one narrow semantic task resolves Residual Ownership.
- An operator can distinguish deterministic Foreign Event detection from semantic ownership judgment.
- An operator can compare two Qwen repetitions for every development Residual Edge.
- A reviewer can inspect exact data-in and data-out for every incorrect or unstable judgment.
- A future experiment can reuse the frozen validation Residual Edges without changing this prompt.

## 3. Requirements

### Deterministic selection

- CEA17-SEL-01: KoteKomi must derive Containment Edges from exact Candidate and Target Event ranges.
- CEA17-SEL-02: KoteKomi must derive Foreign Events from exact Other Event ranges.
- CEA17-SEL-03: KoteKomi must identify 12 development Deterministic Mixed Edges.
- CEA17-SEL-04: KoteKomi must identify ten development Residual Edges.
- CEA17-SEL-05: KoteKomi must identify two validation Deterministic Mixed Edges.
- CEA17-SEL-06: KoteKomi must identify seven validation Residual Edges.
- CEA17-SEL-07: Selection must not read Attachment Gold.

### Bounded semantic task

- CEA17-MOD-01: The prompt must define Candidate, Target Event, Other Events, and Residual Ownership.
- CEA17-MOD-02: The prompt must ask whether all meaningful Candidate Remainder text belongs to the Target Event fact.
- CEA17-MOD-03: Qwen must return exactly `Y`, `N`, or `U`.
- CEA17-MOD-04: Qwen must not create identifiers, ranges, Domain Core records, or classifications.
- CEA17-MOD-05: KoteKomi must invoke Qwen only for Residual Edges.
- CEA17-MOD-06: KoteKomi must preserve the complete logical input and raw output for each judgment.

### Evaluation

- CEA17-EVL-01: Attachment Gold must remain outside every model input.
- CEA17-EVL-02: KoteKomi must score each answer at the occurrence level.
- CEA17-EVL-03: KoteKomi must report positive retention, negative rejection, accuracy, invalid output, and repetition stability.
- CEA17-EVL-04: `supported` requires ten correct development answers in both repetitions.
- CEA17-EVL-05: `supported` requires identical semantic answers across both repetitions.
- CEA17-EVL-06: Any Gold-positive `N`, `U`, invalid output, or failed execution must prevent `supported`.
- CEA17-EVL-07: Validation evidence must remain prepared and unexecuted during the development diagnostic.

### Evidence package

- CEA17-PKG-01: The runner must preserve the sealed CEA-1.6 and CEA-1.5 input digests.
- CEA17-PKG-02: The runner must write typed preflight, task, execution, report, review, and status files.
- CEA17-PKG-03: The review must show exact source, Candidate, Target Event, Candidate Remainder, expected answer, and both actual answers.
- CEA17-PKG-04: The handoff must state the hypothesis, method, prompt, metrics, failures, and review questions.
- CEA17-PKG-05: The runner must report the exact handoff and expected Claude review paths.
- CEA17-PKG-06: The human must invoke Claude through standard input and standard output.
- CEA17-PKG-07: The package must report zero ProposedChanges and zero accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.6 measurement
             |
             v
 exact containment selection
        /              \
       v                v
Foreign Event       Residual Edge
deterministic       bounded Qwen task
       \                /
        v              v
      occurrence-level evaluation
                 |
                 v
       review + Claude handoff
```

The Application Layer owns task and result DTOs.

The Pipeline owns exact selection and occurrence-level evaluation.

The existing Model Runtime owns the bounded Qwen execution.

The disposable runner owns experiment orchestration and file output.

The human owns the Claude invocation.

## 5. Key Interactions

```text
Human             Runner             KoteKomi             Qwen
  | prepare          |                  |                    |
  |----------------->| exact selection  |                    |
  |                  |----------------->|                    |
  |                  | preflight        |                    |
  | run development  |                  |                    |
  |----------------->| two repetitions  |                    |
  |                  |----------------->| Y / N / U          |
  |                  |<---------------------------------------|
  |                  | evaluate + write handoff              |
  | Claude handoff   |                  |                    |
```

## 6. Data Model

CEA-1.7 adds Application Layer DTOs for one Residual Edge case, one observation, one case evaluation, one phase report, and one status.

These DTOs are experimental evidence.

CEA-1.7 adds no Ledger schema and no accepted record.

## 7. APIs / Interfaces

The runner `prepare` action accepts one configuration file, CEA-1.5 root, CEA-1.6 root, and output root.

The runner `run-development` action accepts one configuration file and one prepared output root.

The runner prints the exact second-opinion handoff path and expected Claude review path.

The human invokes Claude with this command shape:

```text
claude -p --model opus --effort high --add-dir RUN_ROOT < HANDOFF > REVIEW
```

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- Deterministic Mixed Edge detection remains experimental.
- Residual Ownership is an Attachment decision rather than a semantic role.
- Other Events remain visible to Qwen as context.
- Qwen supplies only one local semantic answer.
- KoteKomi creates every identifier, range, trace, mapping, metric, and file.
- The validation partition is descriptive evidence because prior reviews inspected its Gold.
- Production integration remains inactive.

## 9. Acceptance Criteria

- CEA17-ACC-01: Unit tests prove exact Containment Edge and Foreign Event selection.
- CEA17-ACC-02: Unit tests prove Residual Edge selection does not read Gold.
- CEA17-ACC-03: Unit tests prove task rendering contains exact source characters and no canonical identifiers.
- CEA17-ACC-04: Unit tests prove occurrence-level scoring and all terminal outcomes.
- CEA17-ACC-05: Pipeline tests reproduce the 12/10 and 2/7 deterministic partitions.
- CEA17-ACC-06: Runner tests prove exact data-in/data-out review rendering.
- CEA17-ACC-07: Focused formatting, lint, typecheck, and tests pass.
- CEA17-ACC-08: The human-run development diagnostic writes two complete repetitions.
- CEA17-ACC-09: The handoff reports zero ProposedChanges and zero accepted writes.

## 10. Reference Implementations

- Model execution: `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_preview.py`
- Exact task records: `packages/application/src/kotekomi_application/competitive_attachment_edge_filter.py`
- Sealed evidence loading: `scripts/run_competitive_attachment_measurement_authority.py`
- Occurrence-level Gold: `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_measurement_authority.py`

## 11. Constraints and Halt Conditions

- Stop when any exact range differs from its SourceSegment characters.
- Stop when the 12/10 or 2/7 deterministic partition changes.
- Stop when any model input contains Attachment Gold.
- Stop when one execution omits its ModelRun or ExtractionStageTrace.
- Stop when an action would write ProposedChanges or accepted Ledger state.
- Stop before validation when development does not satisfy its declared gate.
