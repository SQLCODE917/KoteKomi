# TDD: CEA-1.22 Nested Event Ownership Diagnostic

- Status: Completed; bounded hypothesis supported; transfer unproven; production inactive
- Deliverable ID: `CEA-1.22`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.21 Unequal-Range Blind Review](2026-09-21-competitive-attachment-unequal-range-blind-review.md)

## 1. Context & Problem

CEA-1.21 reviewed eighteen Head-Aligned unequal-range Attachment Edges.

The Structural Route selected thirteen edges and excluded five edges.

The blind reviewer accepted all thirteen selected edges.

The blind reviewer also accepted four excluded edges.

Those four Candidates contain another Event inside target Event content.

The blind reviewer rejected one Candidate that crosses into sibling Event content.

Complete Foreign Event exclusion therefore removes valid proposition content.

**Contained Event** means another complete Event expression inside one Candidate range.

**Nested Event** means a Contained Event that serves as target Event content or detail.

**Sibling Spillover** means Candidate content that belongs to a separate sibling proposition.

**Ownership Decision** means one `Y`, `N`, or `U` answer for the complete Candidate.

The Primary Flow is:

1. The runner validates the CEA-1.21 package and its completed review.
2. The Pipeline derives the five excluded cases without changing any source range.
3. The Pipeline renders one bounded semantic task for each case.
4. Qwen returns one `Y`, `N`, or `U` answer for each task.
5. KoteKomi maps every answer to the exact Candidate and target Event.
6. The Pipeline compares two repetitions with the blind semantic labels.

The diagnostic invokes no production Pipeline.

The diagnostic creates no ProposedChange or accepted Ledger record.

## 2. Hypothesis

> A bounded Qwen task can distinguish Nested Events from Sibling Spillover across the five
> CEA-1.21 exclusions without changing source spans.

## 3. Goals

- An operator can inspect each exact model input and raw output.
- An operator can distinguish a Nested Event from Sibling Spillover.
- An operator can inspect answer stability across two repetitions.
- An operator can identify the first failed case without a complete ingestion.

## 4. Requirements

### Evidence preparation

- CEA122-EVD-01: The runner validates every CEA-1.21 input and output digest.
- CEA122-EVD-02: The Pipeline derives exactly five structurally excluded cases.
- CEA122-EVD-03: The cases contain four blind `Y` labels and one blind `N` label.
- CEA122-EVD-04: Each case preserves exact SourceSegment, Candidate, and Event ranges.
- CEA122-EVD-05: Each case names every complete Contained Event.
- CEA122-EVD-06: Gold labels do not enter a model task.

### Model task

- CEA122-MOD-01: One task asks one Ownership Decision question.
- CEA122-MOD-02: The task shows the complete authoritative passage.
- CEA122-MOD-03: The task shows the exact Candidate text.
- CEA122-MOD-04: The task shows the exact target Event text.
- CEA122-MOD-05: The task shows every Contained Event in source order.
- CEA122-MOD-06: The task uses no canonical ID or source offset.
- CEA122-MOD-07: The prompt defines each task term before use.
- CEA122-MOD-08: Qwen returns exactly `Y`, `N`, or `U`.
- CEA122-MOD-09: The runtime preserves complete execution evidence.

### Evaluation

- CEA122-EVL-01: The runner executes each task twice under one runtime contract.
- CEA122-EVL-02: The evaluator reports each answer beside the blind label.
- CEA122-EVL-03: The evaluator reports invalid, failed, blocked, and unclear results.
- CEA122-EVL-04: The evaluator reports semantic stability by exact case.
- CEA122-EVL-05: `supported` requires ten correct and complete decisions.
- CEA122-EVL-06: `mixed` requires a stable correct `N` and at least six correct positive decisions.
- CEA122-EVL-07: `falsified` applies when Qwen accepts the Sibling Spillover case.
- CEA122-EVL-08: `inconclusive` applies to one unstable or unresolved case.

### Evidence package

- CEA122-PKG-01: The runner writes one typed preflight before model execution.
- CEA122-PKG-02: The runner writes one typed execution record per task and repetition.
- CEA122-PKG-03: The review shows exact input, raw output, expected answer, and actual answer.
- CEA122-PKG-04: The handoff states the same-document and same-model limits.
- CEA122-PKG-05: The report records zero ProposedChanges and accepted Ledger writes.

## 5. Proposed Architecture

```text
CEA-1.21 excluded cases
            |
            v
 exact Contained Event catalog
            |
            v
 bounded Qwen ownership task
            |
            v
 deterministic answer mapping
            |
            v
 two-repetition evaluator
```

The Application Layer owns task rendering and experiment DTOs.

The existing ModelRuntime Port owns Qwen execution evidence.

The Pipeline owns evidence derivation, evaluation, and report rendering.

## 6. Key Interactions

```text
Operator        Runner        Application Layer        ModelRuntime
   |               |                  |                    |
   | run           |                  |                    |
   |-------------->| validate inputs  |                    |
   |               |----------------->| render task        |
   |               |                  |------------------->| answer Y/N/U
   |               |                  |<-------------------| raw output
   |               |<-----------------| typed decision     |
   |<--------------| report and handoff                    |
```

## 7. Data Model

`AttachmentNestedEventCase` records one exact diagnostic case.

`AttachmentNestedEventObservation` records one model execution result.

`AttachmentNestedEventEvaluation` records two answers and one expected answer.

`AttachmentNestedEventReport` records the terminal diagnostic outcome.

These records remain Application Layer experiment DTOs.

## 8. APIs / Interfaces

The runner accepts one complete CEA-1.21 run root and one explicit config path.

The runner writes preflight, report, review, handoff, and status files.

The task input contains Passage, Candidate, Target Event, and Contained Events fields.

## 9. Behavior & Domain Rules

- A Contained Event can remain part of a target Event proposition.
- A Candidate receives `Y` when every substantive part belongs to the target Event.
- A Candidate receives `N` when one substantive part belongs to a sibling proposition.
- A `U`, invalid output, blocked task, or failed task remains unresolved.
- KoteKomi creates every identifier and evidence reference.
- The diagnostic preserves the CEA-1.21 blind labels without rewriting prior evidence.
- The diagnostic leaves production routing inactive.

## 10. Acceptance Criteria

- CEA122-ACC-01: Tests prove the renderer omits Gold, IDs, and offsets.
- CEA122-ACC-02: Tests prove one and multiple Contained Event inputs.
- CEA122-ACC-03: Tests prove all four terminal outcomes.
- CEA122-ACC-04: Tests reject incomplete and duplicate observations.
- CEA122-ACC-05: Preflight reports five cases with the required label balance.
- CEA122-ACC-06: Focused formatting, lint, typecheck, and tests pass.
- CEA122-ACC-07: The report records zero canonical writes.

## 11. Reference Implementations

- Model execution: `competitive_attachment_edge_filter_preview.py`.
- Task records: `competitive_attachment_edge_filter.py`.
- Evidence derivation: `competitive_attachment_unequal_range_blind_review.py`.
- Dependency evidence: Universal Dependencies.

## 12. Constraints and Halt Conditions

- Stop when a prepared case changes one authoritative source range.
- Stop when one Contained Event is absent from the task.
- Stop when Gold enters one model input.
- Stop when the runtime identity differs between repetitions.
- Stop before validation transfer or production integration.

## 13. Experimental Outcome

CEA-1.22 completed on September 21, 2026.

Qwen returned ten complete decisions for five exact cases across two repetitions.

Qwen matched the CEA-1.21 blind semantic decisions in all ten executions.

The diagnostic recorded four correct `Y` cases and one correct `N` case per repetition.

The diagnostic created no ProposedChange or accepted Ledger record.

The evaluator classified the registered bounded hypothesis as `supported`.

The repeated deterministic executions establish runtime reproducibility.

They do not establish semantic robustness under changed generation settings.

The five cases came from one Document, three sentences, and four distinct Candidate ranges.

The prompt author knew all five blind decisions before this diagnostic ran.

The result therefore establishes task representability on known cases rather than transfer.

The Original Gold `N` labels answer a different mechanical containment question.

That oracle requires every non-whitespace Candidate character to occur inside reviewed fragments.

Three semantic `Y` disagreements arise only from `and`, `but`, or `, but` outside those fragments.

One semantic `Y` disagreement concerns a substantive nested `tied` clause.

The remaining semantic `N` case agrees with Original Gold and contains sibling spillover.

CEA-1.23 will freeze the prompt and test blind labels from other Documents.

Production integration remains `not_activated`.
