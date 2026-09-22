# TDD: CEA-1.23 Nested Event Ownership Transfer

- Status: Implemented; mixed; independent review pending; production inactive
- Deliverable ID: `CEA-1.23`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.22 Nested Event Ownership Diagnostic](2026-09-21-competitive-attachment-nested-event-ownership.md)

## 1. Context & Problem

CEA-1.22 showed that Qwen can distinguish Nested Event content from Sibling Spillover.

The prompt author knew all five CEA-1.22 labels before the diagnostic ran.

All five cases came from one Document.

CEA-1.22 therefore established task representability rather than transfer.

**Transfer Case** means one exact Candidate and target Event from another Document.

**Ownership Label** means one blind `Y`, `N`, or `U` semantic judgment.

**Frozen Prompt** means the exact CEA-1.22 prompt bytes and digest.

**Original Gold** means the exact fragment-containment oracle from CEA-1.

Original Gold does not answer the Ownership Label question.

The Primary Flow is:

1. The runner validates the completed CEA-1.22 package and Frozen Prompt.
2. The Pipeline resolves twenty Transfer Cases against human-reviewed SourceSegments.
3. The Pipeline writes one blind ownership request without expected labels.
4. The reviewer supplies one Ownership Label and rationale for every case.
5. The runner validates the complete blind response before it invokes Qwen.
6. Qwen answers the same bounded question once for each Transfer Case.
7. The Pipeline compares Qwen answers with the sealed Ownership Labels.
8. The runner writes exact evidence and a second-opinion handoff.

The experiment creates no ProposedChange or accepted Ledger record.

The experiment does not activate production routing.

## 2. Goals

- An operator can review twenty cross-document Ownership Labels.
- An operator can inspect each exact Qwen input and raw output.
- An operator can measure positive and negative transfer separately.
- An operator can identify the first failed Transfer Case.
- An operator can send one self-contained evidence package for independent review.

## 3. Requirements

### Transfer catalog

- CEA123-CAT-01: The Pipeline resolves every SourceSegment from the reviewed held-out catalog.
- CEA123-CAT-02: The catalog uses two Documents that CEA-1.22 did not use.
- CEA123-CAT-03: The catalog contains twenty distinct SourceSegments.
- CEA123-CAT-04: Each Candidate occurs exactly once in its SourceSegment.
- CEA123-CAT-05: Each target Event occurs exactly once in its SourceSegment.
- CEA123-CAT-06: Each Contained Event occurs exactly once inside its Candidate.
- CEA123-CAT-07: The Pipeline constructs every source offset and identifier.
- CEA123-CAT-08: The catalog stores no Ownership Label.

### Blind review

- CEA123-REV-01: The request defines Passage, Candidate, target Event, and Contained Event.
- CEA123-REV-02: The request asks whether every substantive Candidate part belongs to the target Event.
- CEA123-REV-03: The request includes no Qwen answer or Original Gold label.
- CEA123-REV-04: The response supplies one `Y`, `N`, or `U` answer for every case.
- CEA123-REV-05: The response supplies one non-empty rationale for every case.
- CEA123-REV-06: The runner rejects missing, duplicate, malformed, or foreign decisions.
- CEA123-REV-07: The runner requires at least six `Y` and six `N` labels.

### Model task

- CEA123-MOD-01: The runner pins the exact CEA-1.22 prompt digest.
- CEA123-MOD-02: One model task asks one Ownership Label question.
- CEA123-MOD-03: The task shows the complete SourceSegment.
- CEA123-MOD-04: The task shows the exact Candidate and target Event.
- CEA123-MOD-05: The task shows every Contained Event in source order.
- CEA123-MOD-06: The model input contains no expected label or rationale.
- CEA123-MOD-07: Qwen returns exactly `Y`, `N`, or `U`.
- CEA123-MOD-08: The runtime preserves the exact input, raw output, and execution evidence.

### Evaluation

- CEA123-EVL-01: The evaluator scores each occurrence rather than each string identity.
- CEA123-EVL-02: The evaluator reports exact accuracy and class recall.
- CEA123-EVL-03: The evaluator reports invalid and unclear answers.
- CEA123-EVL-04: The evaluator reports results by Document and expected label.
- CEA123-EVL-05: `supported` requires at least eighteen correct answers.
- CEA123-EVL-06: `supported` requires at least `0.85` recall for `Y` and `N`.
- CEA123-EVL-07: `supported` requires zero invalid, failed, blocked, or unclear answers.
- CEA123-EVL-08: `mixed` requires at least fifteen correct complete answers.
- CEA123-EVL-09: Every other complete result is `falsified`.
- CEA123-EVL-10: One unresolved result makes the outcome `inconclusive`.

### Evidence package

- CEA123-PKG-01: The runner writes a typed catalog before blind review.
- CEA123-PKG-02: The runner preserves the exact reviewer response and digest.
- CEA123-PKG-03: The report shows exact input, expected answer, and actual answer.
- CEA123-PKG-04: The handoff distinguishes semantic labels from Original Gold.
- CEA123-PKG-05: The handoff states reviewer and Document limits.
- CEA123-PKG-06: The report records zero canonical writes.

## 4. Proposed Architecture

```text
reviewed SourceSegments
          |
          v
 exact Transfer Case catalog
          |
          +----> blind reviewer ----> sealed Ownership Labels
          |
          +----> Frozen Prompt -----> Qwen decisions
                                      |
                                      v
                              occurrence evaluator
```

The Application Layer owns Transfer Case, response, observation, and report contracts.

The Pipeline owns exact range construction, blind rendering, and evaluation.

The ModelRuntime Port owns Qwen execution evidence.

The disposable runner owns package composition.

## 5. Key Interactions

```text
Operator        Runner          Pipeline          Reviewer       Qwen
   |               |               |                 |             |
   | prepare       |               |                 |             |
   |-------------->| resolve cases |                 |             |
   |               |-------------->| render request  |             |
   |<--------------| request       |                 |             |
   | label         |               |---------------->|             |
   | run           | validate      |                 |             |
   |-------------->| response      |                 |             |
   |               |---------------------------------------------->|
   |               |<----------------------------------------------|
   |               |-------------->| evaluate        |             |
   |<--------------| report        |                 |             |
```

## 6. Data Model

`AttachmentNestedTransferSelector` identifies one source-exact test case.

`AttachmentNestedTransferCase` records resolved ranges and one model task.

`AttachmentNestedTransferCatalog` records the frozen twenty-case inventory.

`AttachmentNestedTransferDecision` records one blind Ownership Label.

`AttachmentNestedTransferSubmission` records one complete blind response.

`AttachmentNestedTransferObservation` records one Qwen execution.

`AttachmentNestedTransferEvaluation` compares one observation with one blind label.

`AttachmentNestedTransferReport` records the terminal outcome and metrics.

All records remain derived experiment evidence.

## 7. APIs / Interfaces

The `prepare` command accepts the completed CEA-1.22 root and one output root.

The `prepare` command writes the typed catalog and blind review request.

The reviewer writes one JSON response through standard output.

The `run` command accepts the prepared root, reviewer response, and runtime config.

The `run` command writes execution records, a report, a review, and a handoff.

## 8. Behavior & Domain Rules

- An Ownership Label describes semantic attachment rather than character containment.
- A `Y` label means every substantive Candidate part belongs to the target Event proposition.
- An `N` label means at least one substantive Candidate part belongs to a sibling proposition.
- A `U` label means the SourceSegment does not decide ownership.
- One `U` reviewer label remains valid Gold for this experiment.
- One `U` Qwen answer remains unresolved.
- KoteKomi constructs every offset and identifier from exact source text.
- The Pipeline preserves reviewer and Qwen evidence separately.

## 9. Acceptance Criteria

- CEA123-ACC-01: Tests prove every selector resolves to exact source characters.
- CEA123-ACC-02: Tests reject repeated or absent Candidate and Event strings.
- CEA123-ACC-03: Tests prove blind rendering excludes labels and model results.
- CEA123-ACC-04: Tests reject incomplete and foreign review responses.
- CEA123-ACC-05: Tests prove all four terminal outcomes.
- CEA123-ACC-06: Tests prove occurrence and class metrics.
- CEA123-ACC-07: Preparation reports twenty cases and two Documents.
- CEA123-ACC-08: Focused formatting, lint, typecheck, and tests pass.
- CEA123-ACC-09: The report records zero canonical writes.

## 10. Reference Implementations

- Exact task rendering: `competitive_attachment_nested_event_ownership.py`.
- Blind response validation: `competitive_attachment_unequal_range_blind_review.py`.
- Model execution evidence: `competitive_attachment_edge_filter_preview.py`.
- Source catalog: `organization-mention-held-out-gold-v1.json`.

## 11. Constraints and Halt Conditions

- Stop when the Frozen Prompt digest changes.
- Stop when one selector cannot resolve uniquely.
- Stop when the blind response contains fewer than six `Y` or six `N` labels.
- Stop when one expected label enters a model input.
- Stop before production integration.
