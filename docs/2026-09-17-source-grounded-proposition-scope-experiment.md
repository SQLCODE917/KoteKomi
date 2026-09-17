# Source-Grounded Proposition Scope Experiment

- Status: Marker-free hypothesis falsified; proposition boundary not accepted
- Parent: [Event-Entity Measurement Integrity](2026-09-17-event-entity-measurement-integrity.md)
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)

## 1. Context & Problem

KoteKomi currently asks whether one entity belongs to one Event.

That question omits the proposition that gives the Event its complete source meaning.

The omission exposes Qwen to every entity in a SourceSegment.

The omission also makes attribution, negation, modality, purpose, comparison, and time easy to lose.

For example, the Source may state that Sacks attributed a regulatory strategy to Anthropic.

The proposition must retain `Sacks stated` with the attributed content.

The proposition cannot reduce that Source report to world truth about Anthropic.

**Proposition Fragment** means one ordered exact source range that contributes to one Event meaning.

**Source-Grounded Proposition Scope** means the complete ordered fragment set for one Event.

**Fragment Candidate** means one exact range that deterministic linguistic analysis offers for review.

**Candidate Gap** means deterministic evidence cannot represent one reviewed Proposition Fragment.

### Primary Flow

1. KoteKomi loads one approved source-grounded Event and its exact SourceSegment.
2. KoteKomi derives Fragment Candidates from pinned linguistic and entity evidence.
3. The Pipeline proves that the candidates can cover every reviewed Gold fragment.
4. KoteKomi retains the Event expression without model judgment.
5. Qwen judges one remaining Fragment Candidate with `Y`, `N`, or `U`.
6. KoteKomi maps each answer to the exact candidate and merges included ranges.
7. The Pipeline compares the Source-Grounded Proposition Scope with reviewed Gold.
8. The corrected Event-entity evaluator measures the scoped candidate inventory.

This experiment writes derived evidence only.

## 2. Goals

- An operator can inspect the exact source fragments that define each Event proposition.
- Event propositions preserve source attribution and qualification.
- Qwen answers one semantic membership question without constructing records or source ranges.
- KoteKomi measures candidate generation separately from model judgment.
- Held-out proposition scope reduces irrelevant entity candidates without losing expected entities.

## 3. Requirements

### Gold Contract

- SGP-G01: Proposition Gold binds approved Connection Gold and Trigger Gold by digest.
- SGP-G02: Proposition Gold contains twenty development and twenty validation Events.
- SGP-G03: Each Gold Event records ordered, non-overlapping exact Proposition Fragments.
- SGP-G04: Each Gold fragment replays byte-for-byte against its SourceSegment.
- SGP-G05: Gold preserves attribution, negation, modality, purpose, comparison, and time.
- SGP-G06: A human approves Proposition Gold before scored model execution.
- SGP-G07: The evaluator reads Gold fragments directly from Proposition Gold.

### Candidate Construction

- SGP-C01: KoteKomi consumes the existing Event trigger and pinned linguistic evidence.
- SGP-C02: KoteKomi validates every linguistic token against authoritative characters.
- SGP-C03: KoteKomi always proposes the exact Event expression.
- SGP-C04: KoteKomi proposes same-sentence exact entity occurrences.
- SGP-C05: KoteKomi proposes exact predicate-dependent subtrees.
- SGP-C06: KoteKomi proposes exact governing context outside the Event complement.
- SGP-C07: Governing context includes an attribution source and reporting predicate.
- SGP-C08: Candidate construction preserves coordination, control, and relative-clause evidence.
- SGP-C09: KoteKomi combines equal ranges and preserves every proposal reason.
- SGP-C10: KoteKomi records a Candidate Gap when candidates cannot cover one Gold fragment.
- SGP-C11: KoteKomi retains every broad syntax-backed candidate when it adds a clause-local candidate.

### Model Judgment

- SGP-M01: Qwen receives the complete authoritative SourceSegment.
- SGP-M02: Qwen receives one marked Event expression.
- SGP-M03: Qwen receives one marked Fragment Candidate.
- SGP-M04: Qwen receives no source offset or KoteKomi identifier.
- SGP-M05: Qwen's semantic payload is exactly `Y`, `N`, or `U`; surrounding ASCII whitespace is
  non-semantic transport framing and the unmodified raw output remains archived.
- SGP-M06: `Y` means the fragment must remain to preserve the Event's complete source meaning.
- SGP-M07: `N` means the fragment belongs only to another proposition or incidental context.
- SGP-M08: `U` means the SourceSegment does not decide fragment membership.
- SGP-M09: One failed judgment leaves only that Fragment Candidate unresolved.

The marker-free v6 diagnostic does not change SGP-M02 or SGP-M03.

It tests a replacement input contract before production integration.

### Deterministic Scope

- SGP-S01: KoteKomi includes the Event expression deterministically.
- SGP-S02: KoteKomi maps each model answer to its supplied candidate.
- SGP-S03: KoteKomi merges included overlapping ranges.
- SGP-S04: KoteKomi preserves separated ranges as ordered Proposition Fragments.
- SGP-S05: Every merged fragment records its contributing candidate IDs.
- SGP-S06: A Source-Grounded Proposition Scope identifies its Event and SourceSegment digest.
- SGP-S07: The scope records `complete` only when every candidate has a terminal decision.
- SGP-S08: The scope contains no normalized paraphrase or entity role.

### Evaluation

- SGP-E01: Preflight reports Gold fragment coverage before model execution.
- SGP-E02: The report separates candidate-generation gaps from judgment errors.
- SGP-E03: The report measures exact fragment precision, recall, and character coverage.
- SGP-E04: The report measures required qualification-fragment recall.
- SGP-E05: The report measures expected entity occurrence retention.
- SGP-E06: The report replays scoped entities through corrected occurrence measurement.
- SGP-E07: Development uses three repetitions.
- SGP-E08: Validation uses one frozen held-out repetition.
- SGP-E09: Every report contains exact input, raw output, parsed answer, and mapped decision.
- SGP-E10: The experiment records zero ProposedChanges and zero accepted Ledger writes.

## 4. Proposed Architecture

```text
SourceSegment + Event + linguistic evidence
                    |
                    v
       Deterministic Candidate Builder
                    |
          +---------+---------+
          |                   |
          v                   v
   Gold Preflight       Fragment Candidates
                              |
                              v
                      Qwen Y / N / U
                              |
                              v
                  Deterministic Scope Builder
                              |
                              v
              Source-Grounded Proposition Scope
                              |
                              v
                      Pipeline Evaluator
```

The Application Layer owns candidate and scope construction.

The Pipeline owns Gold comparison and experiment reports.

The existing model runtime records bounded executions.

The Domain Core receives no new record.

## 5. Key Interactions

```text
Operator        Pipeline        Application Layer        Qwen
   |               |                    |                  |
   | run phase     |                    |                  |
   |-------------->| load Event         |                  |
   |               |------------------->| build candidates |
   |               |<-------------------|                  |
   |               | preflight Gold     |                  |
   |               |------------------->| one candidate    |
   |               |                    |----------------->|
   |               |                    | Y / N / U        |
   |               |                    |<-----------------|
   |               |<-------------------| build scope      |
   | report paths  | evaluate and write |                  |
   |<--------------|                    |                  |
```

## 6. Data Model

`PropositionFragmentCandidate` records one exact proposed source range and its proposal reasons.

`PropositionFragmentDecision` records one deterministic or model disposition.

`SourceGroundedPropositionFragment` records one selected merged exact range.

`SourceGroundedPropositionScope` records the ordered fragments for one Event.

`PropositionScopeCaseEvaluation` records one Event's Gold comparison.

`PropositionScopePhaseReport` records one complete development or validation result.

These records remain derived experiment evidence.

## 7. APIs / Interfaces

The candidate builder accepts source text, one Event trigger, one Event, linguistic evidence, and
Event-entity candidates.

The model task accepts one Fragment Candidate and returns one finite answer.

The scope builder accepts the complete candidate and decision inventories.

The Pipeline runner writes typed execution, report, review, and manifest files.

## 8. Behavior & Domain Rules

The Source-Grounded Proposition Scope preserves complete source meaning.

Attribution remains part of an attributed Event proposition.

Negation and modality remain part of the proposition they qualify.

Temporal language remains source text without temporal normalization.

One Source-Grounded Proposition Scope can contain multiple exact fragments.

Candidate overlap is evidence fusion, not duplicate meaning.

The required Event-expression candidate is the only candidate that may occupy Event-expression
characters. A separately judged Fragment Candidate must be disjoint from the Event expression.
Structurally broad linguistic proposals that only partially overlap the Event expression are not
independently markable claims and must not be routed to the model. Exact duplicate ranges instead
fuse their proposal reasons into the required Event-expression candidate.

A prepared run pins the complete candidate-inventory digest. Interrupted Event outputs are reusable
only when their exact prepared input, candidate inventory, result digest, and zero accepted-state
writes validate against the refreshed run.

Classification under a governed Event vocabulary remains optional enrichment.

Semantic Argument Assignment starts after this experiment passes.

## 9. Acceptance Criteria

- AC-SGP-G01: Catalog tests prove exact 20/20 approved parent bindings.
- AC-SGP-G02: Catalog tests reject missing, overlapping, reordered, or changed fragments.
- AC-SGP-C01: Application tests cover attribution, coordination, control, and relative clauses.
- AC-SGP-C02: Application tests reject changed token and source digests.
- AC-SGP-M01: Parser tests accept one exact `Y`, `N`, or `U` semantic payload with optional
  surrounding ASCII whitespace, reject all additional semantic content, and preserve raw output.
- AC-SGP-M02: Fake-Port tests preserve exact model input and raw output lineage.
- AC-SGP-S01: Scope tests prove deterministic inclusion and exact range merging.
- AC-SGP-S02: Scope tests preserve discontinuous fragments and unresolved decisions.
- AC-SGP-E01: Preflight covers every reviewed Gold fragment before model execution.
- AC-SGP-E02: Development and validation retain every required qualification fragment.
- AC-SGP-E03: Scoped evaluation retains every expected entity occurrence.
- AC-SGP-E04: Validation occurrence recall does not regress from the corrected baseline.
- AC-SGP-E05: Validation false positives decrease from the corrected baseline.
- AC-SGP-E06: Three development result fingerprints match.
- AC-SGP-E07: Reports record zero canonical writes.
- AC-SGP-E08: Interrupted-run reuse validates exact input, candidate, digest, and write invariants.
- AC-SGP-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

## 10. Reference Implementations

- Exact linguistic evidence: follow `event_entity_predicate_arguments.py`.
- Bounded model execution: follow `event_entity_connection_preview.py`.
- Gold evaluation: follow `event_entity_connection_stage_local.py`.

## 11. Constraints and Halt Conditions

The Pipeline halts before model execution until a human approves Proposition Gold.

The Pipeline halts when candidate preflight cannot cover one required Gold fragment.

This TDD does not assign entity roles.

This TDD does not create a normalized CompleteProposition.

The next role TDD remains undefined until this experiment passes review.

## 12. Current Evidence and Required Human Boundary

The Application Layer now constructs exact Fragment Candidates, asks one finite `Y`, `N`, or `U`
question per non-Event candidate, preserves exact data-in/data-out traces, and constructs one typed
SourceGroundedPropositionScope without a normalized paraphrase or semantic role.

The attributed fixture preserves `Sacks stated` with `Anthropic was running a strategy` rather than
turning the attributed content into unqualified world truth.

The Pipeline now validates parent Gold, checks candidate coverage before model execution, scores
exact source characters, measures qualification and expected-entity retention, and writes typed
phase evidence with zero canonical writes.

The proposed 20/20 catalog is
[`hsq-source-grounded-proposition-gold-v1.json`](hsq-source-grounded-proposition-gold-v1.json).

The human-readable review is
[`hsq-source-grounded-proposition-gold-review-v1.md`](hsq-source-grounded-proposition-gold-review-v1.md).

The first development preflight observed 344 candidates over twenty Events and correctly halted
before model execution because the catalog was not approved.

Subsequent inspection found that thirty-eight Events still used the generator's sentence-wide
placeholder despite the catalog's earlier approved label.

That label did not establish a valid reviewed oracle and has been replaced with a proposed status.

The revised catalog now contains source-bounded fragments for all forty Events.

The preflight now distinguishes candidates whose meaningful characters are wholly inside Gold from
candidates that necessarily import non-Gold meaning.

An overreaching deterministic Event expression blocks execution because Qwen cannot trim a required
candidate.

The first exact selectable-character replay exposed eleven genuine candidate gaps: seven in
development and four in validation.

Clause-local constituent construction retained every original broad syntax-backed candidate while
adding narrower candidates around subordinate clauses, detached relative clauses, and citation
markers.

The first approved deterministic preflight observed 381 development candidates and 256 validation
candidates with zero missing Gold fragments and zero blocking deterministic candidates.

The human approved the revised forty-Event oracle on 2026-09-17.

Scored model execution is now authorized.

The preceding implementation baseline completed formatting, lint, typecheck, and the cumulative
repository suite on 2026-09-17 with `1596` tests passing and `1` skipped.

The first development repetition completed ten Events before TGE-019 exposed two structurally broad
Stanza candidates that began inside the required Event expression and continued into neighboring
propositions. Such a range cannot be marked as a separate candidate without crossing the Event
markers, and it was Gold-overreaching in this case.

The candidate builder now requires every separately judged candidate to be disjoint from the Event
expression. A deterministic refresh revalidated the exact prepared input, candidate inventory,
result digest, and zero accepted-state writes for each of the ten completed Events before retaining
their records. The refreshed preflight contains 379 development candidates and 252 validation
candidates, including 359 and 232 model-routed candidates respectively, with zero missing Gold
fragments and zero blockers.

The revised Gold, clause-local correction, overlap invariant, finite-answer framing contract, and
refresh validation pass focused formatting, lint, typecheck, and thirty-two proposition tests.

The revised change still requires cumulative repository verification.

Development repetition one completed 359 model executions in 437,895 milliseconds with zero
accepted Ledger writes. The original validator accepted only ten outputs and classified 349 as
invalid even though every rejected raw output was exactly `Y` or `N` followed by two line-feed
characters. That result measured output framing rather than proposition quality.

The finite-answer contract is now version two. It treats surrounding ASCII whitespace as
non-semantic framing while still rejecting additional tokens, explanations, or multiple answers.
The exact raw bytes remain in the ModelRun and ExtractionStageTrace, so normalization is visible and
auditable rather than destructive.

A deterministic counterfactual over the 359 archived raw outputs produced 218 `Y`, 141 `N`, and no
`U` answers. Under the corrected framing contract it would yield 0.890297 character recall,
0.568316 precision, 0.693769 F1, 0.909091 qualification recall, 0.893617 expected-entity recall, and
two exact Event passes out of twenty. This is diagnostic evidence rather than a replacement scored
run because the original ModelRun records correctly retain their version-one `invalid_output`
status.

The counterfactual falsifies output framing as the only problem. Once framing is corrected, the next
measured failure is semantic over-selection: 86 Gold-overreaching candidates received `Y`, while 55
Gold-compatible candidates received `N`. A fresh version-two replay must follow a bounded review of
those errors rather than repeating the unchanged task blindly.

Prompt v2 replaces undefined internal phrases such as `marked source fragment`, `marked event
expression`, `SourceSegment`, and `proposition` with ordinary task-local definitions of `Event` and
`Candidate`. It retains the removal test, explicitly distinguishes coordinated neighboring actions,
and adds one generic contrastive example. The prompt-only hypothesis is that clearer task language
will reduce over-selection without reducing reviewed qualification or entity retention.

The prompt-v2 development repetition uses the same approved twenty Events, candidate inventory,
model, generation settings, and Gold evaluation. Its comparison baseline is the deterministic
whitespace-normalized prompt-v1 diagnostic: 0.568316 precision, 0.890297 recall, 0.693769 F1,
0.909091 qualification recall, 0.893617 entity recall, and two exact Event passes.

Prompt v2 completed all 359 model judgments under the corrected finite-answer contract. It produced
0.595019 precision, 0.757192 recall, 0.666381 F1, 0.636364 qualification recall, 0.808511 entity
recall, and two exact Event passes. It reduced accepted Gold-overreaching candidates from 86 to 65,
but increased rejected Gold-compatible candidates from 55 to 68. The clearer prompt therefore
improved candidate-level discrimination while losing too much high-value proposition content; its
prompt-only acceptance hypothesis is falsified.

Prompt v3 preserves the ordinary-language Event and Candidate definitions, finite `Y`/`N`/`U`
contract, removal test, and generic contrastive example. It removes the additional candidate-boundary
explanation, enumerated positive categories, and detailed neighboring-context exclusions. A fresh
development repetition holds the approved twenty Events, 379 candidates, 359 model-routed
candidates, model, seed, runtime profile, and Gold catalog constant. Its bounded hypothesis is that
the shorter instructions improve proposition scope over prompt v2 without reducing entity or
qualification recall.

Prompt v3 completed all 359 model judgments with zero invalid outputs and zero accepted Ledger
writes. Compared with prompt v2, precision increased from 0.595019 to 0.648509, recall from 0.757192
to 0.795222, F1 from 0.666381 to 0.714411, and entity recall from 0.808511 to 0.851064. False-positive
characters fell from 1,057 to 884 while true-positive characters increased from 1,553 to 1,631.
The shorter prompt therefore supports the hypothesis that the removed explanatory material impaired
this model's proposition judgments.

The improvement is incomplete. Qualification recall fell from 0.636364 to 0.575758, exact Event
passes remained two of twenty, and prompt v3 still accepted 57 Gold-overreaching candidates while
rejecting 70 Gold-compatible candidates. The prompt is the leading measured variant, but the
proposition boundary remains unaccepted. The result supports separating qualification attachment
from general fragment membership rather than restoring more global prompt prose.

Prompt v4 makes each retained example use the same `<source>`, `<event>`, and `<candidate>` markers
as the real task, presents exactly one Candidate, and supplies exactly one answer. It also removes
the prompt-v3 `Alex` subject-positive example and `Plan A` neighboring-object negative example, and
moves the output instruction before the examples. The resulting replay therefore holds the twenty
Events, candidate inventory, model, seed, runtime profile, and Gold catalog constant, but does not
isolate marker consistency as its only prompt variable.

Prompt v4 completed all 359 model judgments with zero invalid outputs and zero accepted Ledger
writes. It produced 285 `N`, 73 `Y`, and one `U` answer. Compared with prompt v3, 127 prior `Y`
answers became `N`, including 91 Gold-compatible candidates. Precision fell from 0.648509 to
0.595592, recall from 0.795222 to 0.527060, F1 from 0.714411 to 0.559234, entity recall from 0.851064
to 0.446809, qualification recall from 0.575758 to 0.303030, and exact Event passes from two to zero.
Prompt v4 is rejected.

The result does not show that inference-shaped tagged examples are harmful because the example
semantics and instruction order changed at the same time. A valid marker-consistency experiment must
preserve all four prompt-v3 judgments and their order, express each as one independently tagged
input/output example, and leave the final output instruction after the examples.

Prompt v5 is that clean marker-consistency experiment. Relative to prompt v3, it preserves every
instruction, the four judgments in their original `Alex → Y`, `Plan B → Y`, `criticized → N`,
`Plan A → N` order, and the final output instruction after the examples. Its sole intended change is
that each judgment is represented as a separate input/output example using the same `<source>`,
`<event>`, and `<candidate>` markers as the runtime task. The replay again pins the same twenty
Events, 379 candidates, 359 model-routed candidates, model, seed, runtime profile, and Gold catalog.

Prompt v5 completed all 359 model judgments with zero invalid outputs and zero accepted Ledger
writes. It produced 251 `N` and 108 `Y` answers. Compared with prompt v3, 84 prior `Y` answers became
`N`, including 54 Gold-compatible candidates, while only 18 prior `N` answers became `Y`. Candidate
correctness fell from 232 of 359 to 210 of 359. Precision fell from 0.648509 to 0.613497, recall from
0.795222 to 0.633837, F1 from 0.714411 to 0.623501, entity recall from 0.851064 to 0.617021,
qualification recall from 0.575758 to 0.363636, and exact Event passes from two to zero. Prompt v5 is
rejected.

The clean comparison falsifies the marker-consistency hypothesis for this model and task. Repeating
the complete tagged sentence for each answer shifted Qwen toward rejection and performed worse than
the compact four-judgment mapping over one shared example sentence. Prompt v3 remains the leading
measured prompt. Its qualification weakness should be addressed as a separately bounded attachment
task rather than by expanding or restyling the general membership examples again.

Prompt v6 tests a different hypothesis.

The inline `<source>`, `<event>`, and `<candidate>` markers may impair Qwen's reasoning over the
runtime passage itself.

KoteKomi now has a marker-free diagnostic renderer.

It supplies the authoritative text unchanged under `Passage:`.

It supplies the exact Event and Candidate literals as separate fields.

It sends no identifier or source offset to Qwen.

The renderer permits model execution only when the Event and Candidate literals each occur exactly
once in the SourceSegment.

A repeated literal produces the typed `occurrence_ambiguous` result.

KoteKomi does not guess which repeated occurrence the field denotes.

The deterministic v6 preflight retained all 359 development model candidates.

It admitted 295 candidates to the paired marker-free replay.

It excluded 64 repeated-literal candidates with an explicit reason and no model execution.

The evaluator compares v3 and v6 only over the identical 295-candidate subset.

It preserves exact baseline input, marker-free input, raw output, parsed answer, trace identity, and
Gold compatibility for every candidate.

The v6 diagnostic cannot activate production integration.

A favorable result would justify designing occurrence-aware marker-free input for the excluded 64
candidates.

An unfavorable result would falsify inline runtime markers as the primary remaining quality cause.

The v6 replay completed 295 model executions with zero invalid outputs.

The replay excluded 64 repeated-literal candidates as `occurrence_ambiguous`.

The replay made zero accepted Ledger changes.

The paired v3 baseline classified 189 of 295 eligible candidates correctly.

The marker-free input classified 187 of 295 eligible candidates correctly.

Accuracy changed from 0.640678 to 0.633898.

Precision increased from 0.678082 to 0.907692.

Recall fell from 0.626582 to 0.383117.

F1 fell from 0.651316 to 0.538813.

Marker-free input corrected 43 prior false-positive `Y` answers to `N`.

It also changed 51 prior true-positive `Y` answers to false-negative `N` answers.

It recovered 11 prior false-negative `N` answers as `Y`.

It introduced two new false-positive `Y` answers and seven unresolved `U` answers.

The result falsifies inline runtime markers as the primary remaining quality cause.

The marker-free representation shifted Qwen toward rejection and lost source meaning overall.

The plain literal fields also could not identify 64 repeated occurrences.

KoteKomi will retain occurrence-aware inline marking for this boundary.

KoteKomi will not activate the marker-free input in production.

Prompt v3 remains the leading measured prompt for the current general membership task.
