# Competitive Event Attachment Program

- Status: CEA-1.23 mixed; CEA-1.24 transport recalibrated with execution pending; production inactive
- Program ID: `competitive-event-attachment`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Predecessor evidence:
  [Source-Grounded Proposition Scope Experiment](2026-09-17-source-grounded-proposition-scope-experiment.md)
- First deliverable:
  [CEA-1 Competitive Event Attachment MVP](2026-09-18-competitive-event-attachment-mvp.md)
- Development Gold:
  [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## Context and problem

KoteKomi identifies exact Event expressions in an authoritative SourceSegment.
KoteKomi also proposes exact source fragments that can complete each Event proposition.
The current experiment judges each Event and fragment pair independently.
That task hides the other Events in the same SourceSegment from Qwen2.5.
Qwen2.5 can therefore attach one fragment to several sibling Events without comparing them.
The best independent task passed only two of twenty development Events exactly.
It produced 57 accepted Gold-overreaching candidates and 70 rejected Gold-compatible candidates.
The approved Gold contains 40 Events across 19 SourceSegments.
Eleven SourceSegments contain multiple Events, with up to five Events in one SourceSegment.
The Gold contains 187 distinct exact fragment ranges.
Forty-two exact fragment ranges belong to more than one Event.
The next experiment must therefore compare sibling Events and permit multi-Event attachment.

### Terms

**Competing Event Set** means every source-grounded Event under review in one SourceSegment.
**Attachment Candidate** means one exact source occurrence considered against that set.
**Attachment Edge** means one derived link between exact candidate and Event occurrences.
**Attachment Set** means every Event that receives an Attachment Edge from one Attachment Candidate.
**Gold Attachment Set** means the Attachment Set derived from approved Proposition Gold.
**Sibling-Event Leakage** means a false edge to an Event outside the Gold Attachment Set.
**Task-Local Event Label** means one temporary label that identifies an Event within one model task.
**Competitive Event Attachment** means this program's bounded attachment task.
Researchers study similar work as predicate-argument attachment.
They also study it as semantic role argument identification and event argument extraction.

### Program statement

```text
authoritative SourceSegment
        +
source-grounded Events
        +
exact Attachment Candidates
        |
        v
one candidate against all competing Events
        |
        v
occurrence-specific multi-label Attachment Set
        |
        v
source-grounded proposition assembly
        |
        v
later Semantic Argument Assignment
```

## User outcome

A reviewer receives Event propositions whose exact source fragments attach to the correct Event occurrences.

The reviewer can inspect every competing Event, candidate, model answer, mapping, and result.

KoteKomi preserves shared fragments when one exact occurrence contributes to several Event propositions.

The first deliverable produces experimental evidence only.

## Invariable decisions

### Authority

The accepted DocumentRepresentationBundle remains authoritative for source characters.

The Ledger remains authoritative for accepted intelligence and review history.

Every Attachment Candidate maps to one exact half-open range in one authoritative SourceSegment.

Repeated equal text at different ranges remains distinct.

Every source-grounded Event retains its exact EventMention and EvidenceTargets.

Gold supplies evaluation labels only.

Gold cannot select production candidates or enter a model task.

### Competitive attachment

One model task shows all Events that compete for one Attachment Candidate.

One Attachment Candidate can attach to zero, one, or several Events.

An Attachment Edge identifies exact candidate and Event occurrences.

An identity-level summary remains secondary to occurrence-level evidence.

An Event expression attaches to its own Event deterministically.

Qwen2.5 can propose additional Attachment Edges for that occurrence.

### Task allocation

KoteKomi selects exact source ranges and constructs the Competing Event Set.

KoteKomi assigns Task-Local Event Labels in deterministic source order.

Qwen2.5 selects Task-Local Event Labels or returns `NONE` or `UNCLEAR`.

Qwen2.5 receives source text and Task-Local Event Labels instead of canonical identifiers.

KoteKomi maps every valid label to its supplied Event occurrence.

KoteKomi creates every derived record, digest, source reference, and trace.

Specialist observations remain candidate evidence rather than source authority.

### Scope

Competitive Event Attachment decides fragment membership only.

It does not assign an agent, patient, instrument, location, time, or other semantic role.

It does not normalize source wording into a governed Event type.

It does not decide whether an Event proposition is true outside the Source report.

It does not create a ProposedChange or accepted Ledger record.

### Evaluation

The evaluator scores exact Attachment Candidate occurrences and Event occurrences.

The evaluator reports identity-level summaries only after occurrence-level metrics.

The evaluator cannot merge repeated occurrences before scoring.

The evaluator separates candidate coverage from attachment judgment.

The evaluator preserves `NONE`, `UNCLEAR`, malformed, failed, and missing outcomes.

The evaluator compares the competitive task with the archived prompt-v3 independent baseline.

### Production safety

Production ingestion retains its current behavior throughout the experimental deliverables.

A later cutover TDD must select and integrate a production contract.

The cutover TDD must delete the superseded independent attachment path in the same change.

## Research basis

[TabEAE](https://aclanthology.org/2023.acl-long.701/) processes co-occurring Events together.

[EventGraph](https://aclanthology.org/2022.case-1.2/) models triggers and arguments jointly.

[PAIE](https://aclanthology.org/2022.acl-long.466/) selects spans through joint assignment.

[Universal Dependencies analysis](https://aclanthology.org/2021.law-1.5/) recovers many argument links from syntax.
It also identifies cases that require semantic judgment.

[PropSegmEnt](https://aclanthology.org/2023.findings-acl.565/) separates propositions within one sentence.

[MinIE](https://aclanthology.org/D17-1278/) preserves qualifications around a bare extraction.

These sources justify joint competition and separate qualification handling.

They do not authorize model output as source evidence or accepted Ledger state.

## Proposed architecture

```text
SourceSegment + source-grounded Events
                  |
                  v
       exact Candidate Matrix Builder
                  |
                  v
       bounded Qwen competitive task
                  |
                  v
      deterministic Attachment Mapper
                  |
                  v
     proposition reconstruction + evaluator
```

The Application Layer owns grouping, Task-Local Event Labels, mapping, and reconstruction.

The existing ModelRuntime Port owns bounded Qwen2.5 execution evidence.

The Pipeline owns experiment orchestration, Gold comparison, and phase reports.

The Domain Core receives no new record until a later production TDD requires one.

## Incremental delivery

CEA-1 has completed empirical verification.

CEA-1.1 has completed empirical verification with a `mixed` outcome.

CEA-1.2 has completed model-free verification of the selected second-opinion claims.

CEA-1.3 has completed its model-free bounded hybrid selection diagnostic with a `supported` outcome.

CEA-1.3 passed the full repository suite with `1677` tests passed and one test skipped.

CEA-1.4 tested two bounded Prompt Arms on one concentrated diagnostic catalog.

The perfection gate rejected both Prompt Arms before aggregate evaluation.

CEA-1.5 tests whether runtime probability evidence makes the same filter calibratable.

Its first live attempt produced no semantic calibration result: an unsafe request for twenty token alternatives exceeded the installed LM Studio MLX backend maximum of ten, and the backend crashed on the following request. The corrected contract requests ten, rejects larger values before generation transport, preserves failed attempts, and still requires a fresh live diagnostic before any aggregate replay.

Later deliverables define a user story, precondition, and postcondition only.

### CEA-1 — Competitive Event Attachment MVP

**User story:** An operator can compare one candidate with every competing Event.

**Precondition:** Approved Proposition Gold and archived prompt-v3 development evidence exist.

**Postcondition:** Development and frozen validation classify the hypothesis.

**TDD:** [Competitive Event Attachment MVP](2026-09-18-competitive-event-attachment-mvp.md)

### CEA-1.1 — Competitive attachment discrimination experiment

**User story:** An operator can identify why attachment sets remain wrong and test two bounded task-contract corrections.

**Precondition:** CEA-1 preserves complete occurrence evidence for its 65 nonexact validation candidates.

**Postcondition:** A reviewed audit and development-only ablation classify the corrections as `supported`, `mixed`, or `falsified`.

**TDD:** [Competitive Event Attachment Discrimination Experiment](2026-09-18-competitive-event-attachment-discrimination-experiment.md)

### CEA-1.2 — Review-claim verification diagnostic

**User story:** An operator can verify which second-opinion claims follow from frozen CEA evidence.

**Precondition:** CEA-1 and CEA-1.1 preserve complete occurrence and model-output evidence.

**Postcondition:** A model-free report classifies each selected claim and produces a handoff summary.

**TDD:** [CEA-1.2 Review-Claim Verification Diagnostic](2026-09-18-competitive-event-attachment-review-verification.md)

### CEA-1.3 — Bounded hybrid selection diagnostic

**User story:** An operator can determine whether boundary-normalized Gold and bounded syntax safely complement archived Qwen attachment decisions.

**Precondition:** CEA-1 and CEA-1.2 preserve complete occurrence, syntax, and model-output evidence.

**Postcondition:** A model-free policy sweep classifies one preregistered hybrid selection policy and preserves a self-contained handoff package.

**TDD:** [CEA-1.3 Bounded Hybrid Selection Diagnostic](2026-09-18-competitive-event-attachment-bounded-hybrid-selection.md)

### CEA-1.4 — High-recall competitive edge filter

**User story:** An operator can inspect whether one bounded semantic decision retains or rejects each proposed Candidate-to-Event edge.

**Precondition:** CEA-1.3 preserves exact Qwen and syntax edge pools and their occurrence-level ceilings.

**Postcondition:** Development selects one filtered Pool Arm and frozen validation classifies the edge-filter hypothesis.

**TDD:** [CEA-1.4 High-Recall Competitive Edge Filter](2026-09-19-competitive-attachment-edge-filter.md)

### CEA-1.5 — Calibrated competitive edge filter

**User story:** An operator can determine whether one frozen threshold separates useful and harmful Pool Edges.

**Precondition:** CEA-1.4 preserves exact V8 and V9 prompts, tasks, executions, and Maximum Pool evidence.

**Postcondition:** A safety and break-even diagnostic either stops or authorizes one frozen aggregate replay.

**TDD:** [CEA-1.5 Calibrated Competitive Edge Filter](2026-09-19-competitive-attachment-edge-filter-calibration.md)

### CEA-1.6 — Attachment measurement authority

**User story:** An operator can test one proposed rejection rule against authoritative occurrence-level Attachment Gold.

**Precondition:** CEA-1.5 preserves both Prompt Arms, complete probability evidence, Maximum Pools, and normalized Gold inputs.

**Postcondition:** KoteKomi records whether the rule is safe, preserves every counterexample, and binds one independently reviewed evidence package.

**TDD:** [CEA-1.6 Attachment Measurement Authority](2026-09-20-competitive-attachment-measurement-authority.md)

### CEA-1.7 — Attachment task definition diagnostic

**User story:** An operator can determine which bounded semantic task resolves one observed attachment mechanism without erasing valid intelligence.

**Precondition:** CEA-1.6 establishes authoritative measurement and a diagnostic catalog with positive and negative controls.

**Postcondition:** One task contract is selected for a later aggregate replay, or the experiment records that none is safe.

**TDD:** [CEA-1.7 Residual Attachment Ownership Diagnostic](2026-09-20-competitive-attachment-residual-ownership.md)

### CEA-1.8 — Demonstration cue ablation

**User story:** An operator can identify whether one prompt cue caused the constant answer.

**Precondition:** CEA-1.7 preserves ten exact tasks and twenty stable `N` answers.

**Postcondition:** One prompt-only ablation classifies the Cue Effect without changing production.

**TDD:**
[CEA-1.8 Demonstration Cue Ablation](2026-09-20-competitive-attachment-demonstration-cue-ablation.md)

### CEA-1.9 — Explicit Candidate Remainder experiment

**User story:** An operator can compare implicit Candidate judgment with explicit Candidate Remainder judgment.

**Precondition:** CEA-1.8 preserves ten exact tasks, corrected Residual Ownership Gold, and complete cue-arm Probability Evidence.

**Postcondition:** A paired development diagnostic classifies whether explicit Candidate Remainder rendering improves selective semantic judgment.

**TDD:**
[CEA-1.9 Explicit Candidate Remainder Experiment](2026-09-20-competitive-attachment-candidate-remainder.md)

### CEA-1.10 — Finite answer format isolation

**User story:** An operator can distinguish answer-format imitation from semantic judgment changes.

**Precondition:** CEA-1.9 preserves ten paired tasks and twenty first-token probability records.

**Postcondition:** A one-factor prompt experiment measures strict output validity, answer-label pressure, and finite-label stability.

**TDD:**
[CEA-1.10 Finite Answer Format Isolation](2026-09-20-competitive-attachment-finite-answer-format.md)

### CEA-1.11 — Single-token answer termination

**User story:** An operator receives exact finite answers without accepting or repairing explanatory model text.

**Precondition:** CEA-1.10 preserves ten Bare Arm first-token decisions and shows that every Bare execution starts with `Y` or `N`.

**Postcondition:** Two identical one-token repetitions establish whether deterministic generation bounds preserve the archived first-token decisions and produce strict valid outputs.

**Outcome:** Inconclusive.

LM Studio returned twenty completed responses without an output item at a one-token request limit.

KoteKomi preserved all failed ModelRuns and correctly rejected the missing output text.

Every ready ModelInputAdmission retained the expected model identity.

A direct runtime probe found one emitted token at a two-token request limit.

**TDD:**
[CEA-1.11 Single-Token Answer Termination](2026-09-20-competitive-attachment-single-token-termination.md)

### CEA-1.12 — Runtime-calibrated budget-bounded output

**User story:** An operator can verify exact finite answers under the smallest functioning runtime limit.

**Precondition:** CEA-1.11 preserves twenty empty-output failures and a bounded output-limit probe.

**Postcondition:** Two identical repetitions classify whether a two-token request yields one exact answer token without changing its first-token distribution.

**Outcome:** Supported as a budget-bound output mechanism.

The result does not establish model-chosen termination.

Under the pinned runtime, the two-token request constrained observed output to the finite answer token.

**TDD:**
[CEA-1.12 Runtime-Calibrated Budget-Bounded Output](2026-09-20-competitive-attachment-runtime-calibrated-termination.md)

### CEA-1.13 — Part-wise residual ownership

**User story:** An operator can determine whether each exact Candidate Remainder part belongs to one Target Event fact.

**Precondition:** CEA-1.12 preserves a stable budget-bound finite-answer mechanism for the ten sealed Residual Ownership cases.

**Postcondition:** KoteKomi compares whole-Candidate and part-wise judgments under one declared runtime contract and preserves exact data-in and data-out evidence.

**TDD:**
[CEA-1.13 Part-Wise Residual Ownership](2026-09-20-competitive-attachment-partwise-residual-ownership.md)

### CEA-1.14 — Candidate marker boundary ablation

**User story:** An operator can determine whether model-visible Candidate marker boundaries cause stable Whole Arm errors.

**Precondition:** CEA-1.13 preserves ten exact Whole Arm tasks, two stable answers per task, and a completed independent review.

**Postcondition:** Two source-preserving marker variants classify the boundary hypothesis without changing the authoritative Candidate occurrence.

**TDD:**
[CEA-1.14 Candidate Marker Boundary Ablation](2026-09-21-competitive-attachment-candidate-marker-boundary-ablation.md)

### CEA-1.15 — Remainder enumeration isolation

**User story:** An operator can determine whether CEA-1.14 recovered one case because the Candidate marker moved or because one explicitly enumerated Remainder part disappeared.

**Precondition:** CEA-1.14 preserves the exact recovered case, the harder leading-`that` control, and two stable observations per relevant arm.

**Postcondition:** One four-call probe holds both Authoritative Candidate markers fixed while deterministically changing only the explicit Remainder enumeration.

**TDD:**
[CEA-1.15 Remainder Enumeration Isolation](2026-09-21-competitive-attachment-remainder-enumeration-isolation.md)

### CEA-1.16 — Remainder cardinality ablation

**User story:** An operator can determine whether the CEA-1.15 recovery depends on presenting one Remainder part rather than two.

**Precondition:** CEA-1.15 preserves a stable recovered answer with an unchanged Candidate marker and one explicitly enumerated Remainder part.

**Postcondition:** One fresh judgment changes only the boundary between two adjacent Remainder parts while preserving every model-visible source character.

**TDD:**
[CEA-1.16 Remainder Cardinality Ablation](2026-09-21-competitive-attachment-remainder-cardinality-ablation.md)

### CEA-1.17 — Residual Ownership transfer calibration

**User story:** An operator can determine whether the strongest source-exact Residual Ownership rendering and a development-frozen score threshold transfer beyond the ten development cases.

**Precondition:** CEA-1.13 preserves complete Whole executions, CEA-1.15 preserves the two leading-`that` filtered executions, and CEA-1.16 demonstrates that presentation changes materially affect score even without changing the answer.

**Postcondition:** KoteKomi calibrates on sealed development evidence and evaluates the frozen policy twice on all seven eligible validation cases without changing production.

**TDD:**
[CEA-1.17 Residual Ownership Transfer Calibration](2026-09-21-competitive-attachment-residual-transfer-calibration.md)

### CEA-1.18 — Dependency-head Residual routing

**User story:** An operator can route exact-head Residual Edges without asking Qwen a semantic question that syntax already answers.

**Precondition:** CEA-1.17 preserves ten development cases and seven validation cases with pinned Stanza traces and two frozen semantic answers per case.

**Postcondition:** KoteKomi separates Head-Aligned Residuals from Semantic Residuals and evaluates the bounded routing policy without a model call.

**TDD:**
[CEA-1.18 Dependency-Head Residual Routing](2026-09-21-competitive-attachment-dependency-head-routing.md)

### CEA-2 — Qualification attachment

**User story:** A reviewer sees each qualification attached to the correct Event.

**Precondition:** CEA-1.4 establishes an occurrence-stable attachment contract.

**Postcondition:** Each qualification receives occurrence-level attachment evidence.

### CEA-3 — Specialist prior comparison

**User story:** An operator knows whether a specialist prior improves Qwen2.5 judgments.

**Precondition:** CEA-1 supplies one frozen competitive task and error taxonomy.

**Postcondition:** Qwen, specialist, and combined paths have comparable evidence.

### CEA-4 — Deterministic proposition assembly

**User story:** A reviewer sees one complete source-grounded proposition for each Event.

**Precondition:** Selected attachment and qualification policies pass their reviewed gates.

**Postcondition:** KoteKomi assembles exact fragments and preserves every decision and gap.

### CEA-5 — Independent held-out evaluation

**User story:** An operator can measure transfer beyond the source material used during development.

**Precondition:** CEA-4 freezes the candidate, attachment, and assembly contracts.

**Postcondition:** A separate corpus measures occurrence quality and lineage completeness.

### CEA-6 — Production cutover

**User story:** A reviewer receives complete Event propositions through normal ingestion.

**Precondition:** The selected path passes CEA-5 and preserves all earlier source-valid behavior.

**Postcondition:** Production uses one attachment path, and KoteKomi deletes the superseded path.

Semantic Argument Assignment starts after this program produces complete propositions.

## CEA-1 outcome

CEA-1 classified its hypothesis as `supported` on 2026-09-18.

Three development repetitions produced one stable semantic result fingerprint.

The frozen validation phase improved exact Attachment Set accuracy from `0.424581` to `0.636872`.

Validation Sibling-Event Leakage fell from twelve edges to ten edges.

Validation entity recall rose from `0.943396` to `1.0`.

Validation qualification recall rose from `0.485714` to `0.685714`.

Validation character F1 rose from `0.829438` to `0.890198`.

The experiment retained source validity `1.0`, Gold coverage `1.0`, and zero canonical writes.

The result establishes competitive visibility as a better attachment architecture than independent judgments.

The result does not establish production readiness.

Sixty-five of 179 validation candidates still had a nonexact Attachment Set.

The remaining errors included seventeen complete omissions and thirteen false-positive `NONE` cases.

Shared-fragment recall remained `0.660377`.

A later TDD must use these occurrence-level errors without changing CEA-1's frozen result.

CEA-1.1 consumes the validation result as diagnostic evidence.

CEA-1.1 cannot use that validation partition as fresh transfer evidence.

CEA-1.1 tests task wording and example balance on development candidates only.

## CEA-1.1 outcome

CEA-1.1 classified its hypothesis as `mixed` on 2026-09-18.

Ten conditions executed 240 Qwen2.5 tasks over the approved 24-candidate development catalog.
Every condition retained source validity `1.0`, complete Gold coverage, zero ProposedChanges, and zero accepted Ledger writes.
The repeated combined conditions were semantically stable.

The combined Prompt Arm reduced Hamming Loss in both Event Orders and did not increase Sibling-Event Leakage.
It did not improve exact Attachment Set accuracy or mean Jaccard Similarity in both orders.
It increased Order-Sensitive Candidates from seven to eight and regressed protected recall in source order.
The scope-only arm produced the best individual reversed-order result but regressed in source order.
The examples-only arm did not establish its proposed mechanism.

The experiment therefore rejects wording and example tuning as a sufficient production correction.
Governing context, shared-fragment attachment, repeated occurrences, Gold-`NONE` discrimination, and Event-order sensitivity remain open.
Production integration remains `not_activated`.

The CEA-1.1 comparison digest is `6f09dd6bb92ec7e8eb775495300914df61e9210243a144db82ead2caa88a71fa`.

## CEA-1.2 outcome

CEA-1.2 completed its model-free diagnostic on 2026-09-18.

It confirmed that Candidate segmentation changes Gold Attachment Sets.
It found 184 Segmentation Flips among 438 strict Nested Candidate Pairs.

Trigger containment covered four of thirteen validation false-`NONE` cases.
It covered three of four CEA-1.1 challenge `NONE` cases.
Trigger containment is useful but does not explain most validation false attachments.

The frozen syntax route recovered two of four governing-context cases exactly.
It matched or exceeded Qwen on three of eleven validation gates.
It did not satisfy the replacement contract.

The syntax route recovered zero of three repeated-text cases exactly.
All three unordered `E2,E1` outputs remained semantically wrong after set parsing.
Those failures were not format-only.

The examples Prompt lowered the demonstrated maximum answer cardinality from four to two.
The experiment confirms this confound without assigning it causal effect.

The diagnostic classifies significance, independent transfer, the proposed syntax threshold, and a lower true model-error count as `not_testable` from frozen evidence.
It executed zero model tasks and changed no canonical state.
Production integration remains `not_activated`.

## CEA-1.3 outcome

CEA-1.3 classified its preregistered hypothesis as `supported` on 2026-09-19.

Boundary Normalization changed exactly three Gold Attachment Sets.
The changes removed one leading delimiter from each of two Candidates and terminal numeric citation markers from one Candidate.
The authoritative Candidate ranges and source evidence remained unchanged.

The primary policy was archived competitive Qwen union path-length-one syntax plus Governed Complement Scope.
Development exact Attachment Set accuracy rose from `0.530864` to `0.537037`.
Validation exact Attachment Set accuracy rose from `0.642458` to `0.681564`.

Development entity recall remained `0.968254`.
Development qualification recall rose from `0.727273` to `0.757576`.
Development shared-fragment recall rose from `0.736111` to `0.819444`.
Development character recall rose from `0.890297` to `0.897123`.

Validation entity recall remained `1.0`.
Validation qualification recall rose from `0.685714` to `0.828571`.
Validation shared-fragment recall rose from `0.660377` to `0.735849`.
Validation character recall rose from `0.894275` to `0.951908`.

The syntax route rescued twenty-two of sixty-four Qwen false-negative development edges and fourteen of fifty validation edges.
Rescue precision was `0.666667` in development and `0.7` in validation.

The same union also exposed a precision tradeoff.
Development edge precision fell from `0.778195` to `0.765886`, and Sibling-Event Leakage rose from forty-one to fifty-two.
Validation edge precision fell from `0.848958` to `0.834906`, and Sibling-Event Leakage rose from eleven to seventeen.
The `supported` result therefore verifies complementarity under the declared exact-set and protected-recall endpoint.
It does not authorize the primary union as a production policy.

Head-aware trigger containment achieved Gold-`NONE` precision `0.642857` and recall `0.3`.
It remains a diagnostic flag rather than a gate.

All three repeated-text cases preserved exact occurrence identity.
Only one of three had a semantically exact primary-policy Attachment Set.
This corrects the earlier conflation of occurrence routing with semantic over-attachment.

Both complete model-free replays produced byte-identical reports, reviews, summaries, handoffs, statuses, and manifests.
The diagnostic executed zero model tasks and changed no canonical state.
Production integration remains `not_activated`.

## CEA-1.4 outcome

CEA-1.4 rejected both Prompt Arms at its mandatory diagnostic on 2026-09-19.

The first diagnostic used sixteen tasks from one concentrated catalog.
Both repetitions produced thirteen of sixteen Gold-exact decisions.
The catalog concentration prevented approval.

The corrected catalog covered all six development SourceSegments.
It contained eight Gold-positive edges and eight Gold-negative edges.
It preserved one mixed Candidate pair and two shared entity edges.

The first corrected prompt produced thirteen of sixteen Gold-exact decisions twice.
It failed one mixed Candidate edge, one temporal edge, and one cross-sentence occurrence edge.

The second corrected prompt produced thirteen of sixteen Gold-exact decisions twice.
It corrected the mixed Candidate edge and the cross-sentence occurrence edge.
It retained the temporal error.
It introduced one reference-supported entity error and one attribution error.

Every execution returned valid finite output.
Both repetitions produced stable semantic decisions.
The prompt revision exchanged error classes without improving exact accuracy.

The sixteen-of-sixteen diagnostic gate blocked human approval.
The Pipeline did not execute the 490-edge development or 257-edge validation replays.
The registered aggregate Edge Filter hypothesis therefore remains untested.
The experiment created no ProposedChange and changed no accepted Ledger state.
Production integration remains `not_activated`.

The preserved V8 and V9 error swaps can reflect one decision-boundary change.
CEA-1.5 tests this calibration hypothesis before KoteKomi adds routed semantic tasks.

## CEA-1.13 outcome

CEA-1.13 completed its paired Whole Arm and Part Arm experiment on September 20, 2026.

The Whole Arm answered seven of ten cases correctly.

The Part Arm answered three of ten cases correctly.

The Part Arm recovered one Whole Arm error and regressed five correct Whole Arm answers.

All fifty-four executions returned stable strict finite answers.

The stored report classified the result as `mixed` under overlapping outcome rules.

The independent review reconciled all ten cases and identified that taxonomy defect.

The reviewed outcome is `falsified` because Candidate accuracy fell from seven to three.

The result falsifies the exact Part prompt and Aggregate design.

The result does not authorize production integration.

CEA-1.14 isolates Candidate marker placement while retaining the stable Whole task.

## CEA-1.14 outcome

CEA-1.14 completed its paired Structural Trim and Introducer Trim experiment on September 21, 2026.

Its typed report returned `supported` after Candidate accuracy increased from seven to eight of ten cases.

All forty outputs were strict, all repetitions were stable, and no correct case regressed.

Independent review reproduced the report and found no Gold leakage, source-range error, prompt drift, runtime drift, or canonical write.

The review also showed that the experiment had only three distinct Introducer perturbations.

The one recovery coincided with both a moved Candidate marker and a reduction from two enumerated Remainder parts to one.

The fresh Structural control was reported but was not an accuracy gate in the outcome function.

No Gold-`N` case received the Introducer perturbation.

The procedural report remains `supported`, while the causal mechanism remains `inconclusive`.

CEA-1.15 keeps the Candidate marker fixed and changes only the exact Remainder enumeration in the two relevant cases.

## CEA-1.15 outcome

CEA-1.15 completed on September 21, 2026.

All four outputs were strict finite answers, both cases were repetition-stable, and no canonical state changed.

The recovered FedRAMP case remained `Y/Y` while its Authoritative Candidate marker still included `that`.

The hard control remained `N/N` after the same leading token was removed from its explicitly displayed prefix Remainder.

The stored evaluator returned `supported` and `part_inventory_sufficient` under the accepted TDD.

Independent review and local digest reconciliation confirmed the execution evidence but rejected the broad mechanism wording.

The experiment proves that moving the Candidate marker was not necessary for the recovered case.

It does not distinguish removal of an explicitly listed function word from reduction of the Remainder inventory from two parts to one.

Only one of the two Gold-`Y` cases passed, so stability must not be presented as correctness.

CEA-1.16 preserves all model-visible characters and changes only one Remainder boundary to test the cardinality explanation directly.

## CEA-1.16 outcome

CEA-1.16 completed on September 21, 2026.

The two-part Split view returned strict `Y` with a finite-label Attachment Score of `0.461143908412929`.

The registered hypothesis was `falsified` because the answer did not change to `N`.

The one-part CEA-1.15 control scored `5.186837124947065`.

The `4.725693216534136`-nat loss establishes that cardinality remains a material model-input factor even though it was not individually necessary for this answer.

No CEA-1.16 result authorizes a production rendering policy.

CEA-1.17 evaluates the strongest bounded rendering over its full eligible development and validation inventory rather than continuing one-case binary ablations.

## CEA-1.17 outcome

CEA-1.17 completed on September 21, 2026.

The frozen threshold improved development accuracy from eight of ten to nine of ten.

It changed zero validation decisions.

Validation accuracy remained five of seven in both repetitions.

All fourteen validation executions were strict and repetition-stable.

The result is `mixed` under the accepted TDD.

The validation score ranked leading Candidate text instead of Residual Ownership reliably.

Production integration remains `not_activated`.

CEA-1.18 tests dependency-head routing on the same sealed cases without another model call.

## CEA-1.18 outcome

CEA-1.18 completed on September 21, 2026.

The model-free router identified eleven Head-Aligned Residuals and six Semantic Residuals.

The Structural Route retained every Head-Aligned Residual as `Y`.

The Semantic Route preserved the frozen CEA-1.17 threshold answer.

Development accuracy remained nine of ten.

Validation accuracy improved from five of seven to seven of seven.

The router recovered both CEA-1.17 validation false negatives without a regression.

The sealed inventory contains no Head-Aligned Gold-negative case.

Production integration remains `not_activated` until independent review and counterexample coverage.

Independent review reproduced the narrow result and then swept all `935` frozen CEA-1 edges.

The sweep found `58` Head-Aligned edges and eight negatives under the original CEA-1 oracle.

Five of those negatives contain a complete Foreign Event.

The CEA-1.17 task contract already excludes those five edges.

Later human-reviewed Gold changed the remaining three exact edges to `Y`.

CEA-1.19 tests that composed policy over the complete frozen inventory.

## CEA-1.19 scope

CEA-1.19 applies explicit Gold precedence before it evaluates the composed Structural Route.

It retains boundary punctuation as source evidence.

It excludes a Candidate when the Candidate contains a complete Foreign Event.

It assigns deterministic `Y` only after Foreign Event exclusion and exact head alignment.

It invokes no model and cannot activate production routing.

## CEA-1.19 outcome

CEA-1.19 completed on September 21, 2026.

It evaluated all `935` frozen Candidate and Event pairs.

It reproduced `58` Head-Aligned edges.

Reviewed Gold corrected three exact boundary cases from `N` to `Y`.

Five remaining Effective Gold-negative edges contained a complete Foreign Event.

The existing Foreign Event exclusion removed all five negative edges.

All `53` eligible Head-Aligned edges had Effective Gold answer `Y`.

The composed policy excluded no Effective Gold-positive edge.

The report classified the bounded hypothesis as `supported`.

Independent review reproduced the implementation and every reported count.

Independent review found that only `58` of `935` edges reached the Head-Aligned class.

Independent review found that three selected edges depend on disputed Gold overrides.

Independent review found no eligible partial Foreign Event overlap.

The CEA-1.19 report contract also prevented typed failure reports.

CEA-1.20 repairs the report contract and isolates exact self-attachment.

Production integration remains `not_activated`.

## CEA-1.20 outcome

CEA-1.20 completed on September 21, 2026.

It scanned all `935` frozen Candidate and Event pairs.

It found forty Exact Self-Attachment pairs and `895` unequal-range pairs.

All forty exact pairs had Original Gold answer `Y`.

All forty exact pairs also occurred in the Head-Aligned subset.

The other eighteen Head-Aligned pairs had unequal ranges.

That unequal-range subset contained all three disputed Gold overrides.

The Pipeline assigned no answer to unequal-range edges.

The exact route abstained on all three CEA-1.17 reviewed negative controls.

The report classified the bounded hypothesis as `supported`.

The result establishes exact Event self-attachment as an oracle consistency check.

The result covers only forty of `935` edges.

The result does not establish unequal-range attachment.

Production integration remains `not_activated` pending independent transfer evidence.

## CEA-1.21 outcome

CEA-1.21 collected blind semantic judgments for eighteen Head-Aligned unequal-range edges.

The review request omitted Original Gold, Reviewed Gold, Effective Gold, and Structural Selection.

The reviewer answered `Y` for all thirteen selected edges.

The reviewer answered `Y` for four of five excluded edges.

The reviewer answered `N` for one excluded edge that crossed into sibling Event content.

The evaluator classified the registered semantic hypothesis as `mixed`.

The result confirms the Head-Aligned positive route on this inventory.

The result rejects complete Foreign Event exclusion as a semantic rule.

The reviewer wrapped the complete JSON object in a Markdown fence.

The operator preserved the raw response and removed only that fence.

The semantic result remains useful, but the response-format gate failed.

One same-model second pass reproduced the package and agreed with all judgments.

CEA-1.22 tests a bounded nested Event ownership question on the five exclusions.

## CEA-1.22 plan

CEA-1.22 will show Qwen one Head-Aligned Candidate, one target Event, and each contained Event.

Qwen will decide whether all Candidate content remains inside the target Event proposition.

KoteKomi will preserve the CEA-1.21 blind answers as experiment-only evaluation labels.

The diagnostic will run twice under one pinned runtime contract.

The diagnostic cannot establish transfer or activate production.

## CEA-1.22 outcome

CEA-1.22 completed on September 21, 2026.

Qwen matched all five CEA-1.21 blind semantic decisions in two deterministic repetitions.

The result supports the bounded Nested Event ownership task on known cases.

The result does not establish transfer because the prompt author knew every evaluation label.

Three Original Gold disagreements came only from coordinating words or punctuation.

One Original Gold disagreement concerned a substantive nested Event clause.

The Original Gold labels remain valid measurements of exact fragment containment.

They do not serve as direct human judgments of Nested Event ownership.

CEA-1.23 freezes the CEA-1.22 prompt before blind cross-document labeling.

Production integration remains `not_activated`.

## CEA-1.23 plan

CEA-1.23 freezes the exact CEA-1.22 prompt bytes.

It selects twenty unique SourceSegments from two other Documents.

Each case contains one Candidate, one target Event, and at least one Contained Event.

A blind reviewer labels every case before Qwen executes.

Qwen answers the same bounded ownership question once per case.

The evaluator reports occurrence accuracy, class recall, runtime failures, and Document slices.

The experiment cannot activate production.

## CEA-1.23 outcome

CEA-1.23 completed on September 22, 2026.

The blind reviewer labeled twelve cases `Y` and eight cases `N` before Qwen executed.

Qwen2.5-14B answered sixteen of twenty cases correctly.

Accuracy was `0.8`.

`Y` recall was `0.75`.

`N` recall was `0.875`.

Every execution returned one valid finite answer.

The model produced no blocked, failed, invalid, or unclear result.

Three false-negative answers rejected valid modifier or reported-content ownership.

One false-positive answer retained a coordinated sibling Event.

The result is `mixed` under the accepted TDD.

The experiment establishes cross-document task transfer.

The experiment does not establish production reliability.

Production integration remains `not_activated`.

CEA-1.24 first corrects a discovered context-construction confound.

It then compares two local language models under model-specific output transport allowances.

## CEA-1.24 plan

CEA-1.24 will replay all twenty cases with Qwen2.5-14B under Exact Source Context before it runs Qwen3-14B.

Exact Source Context renders the already-selected SourceSegment as one complete focus node instead of applying sentence segmentation to the synthetic experiment paragraph.

The Historical Baseline remains the original CEA-1.23 evidence.

The Comparator Baseline is the corrected twenty-case Qwen2.5 replay.

Historical-to-Comparator transitions measure the context correction.

Comparator-to-Challenger transitions measure the model swap.

The Comparator retains the proven two-token output allowance.

The Challenger uses a sixteen-token output allowance.

The Challenger allowance follows a bounded Qwen3 response-shape probe.

That probe produced no visible text at two tokens and one exact answer at sixteen tokens.

A byte-exact confirmation reproduced one exact answer with the unchanged failed input.

The evaluator requires one exact answer token from either model.

The primary model artifact uses `Q6_K` quantization.

The operator may use `Q5_K_M` only after the Q6 memory estimate or load attempt fails its declared host-safety gate.

The runner will verify the loaded model architecture, parameter count, quantization, model size, instance identifier, and context length through LM Studio model metadata.

The runner will preserve the exact CEA-1.23 semantic prompt and blind labels.

The Qwen3 renderer will append `/no_think` after the complete model-visible task.

The evaluator will report both transition series, class recall, latency, exact input parity, and exact model identity.

The experiment cannot activate production.

## CEA-1.24 outcome

CEA-1.24 completed on September 22, 2026.

The corrected Qwen2.5 Comparator answered sixteen of twenty cases correctly.

The Qwen3 Challenger answered fifteen of twenty cases correctly.

Qwen3 achieved perfect `Y` recall and `0.375` `N` recall by emitted answer.

All twenty Challenger executions returned one valid finite answer token.

The two models disagreed on nine cases.

Qwen3 corrected four Comparator errors and introduced five regressions.

The registered model-swap hypothesis was `falsified`.

Independent review found a stronger class signal in Qwen3's first-token probabilities.

The review found a broad interval that preserves at least `0.85` calibration recall per class.

The evidence does not establish transfer because the same twenty cases exposed that interval.

CEA-1.25 freezes one threshold before it executes on approved Gold Fragment Cases.

Production integration remains `not_activated`.

## CEA-1.25 plan

CEA-1.25 will derive one Frozen Threshold from the sealed CEA-1.24 Qwen3 executions.

It will derive eighty balanced cases from approved Source-Grounded Proposition Gold.

The Transfer Set will cover all forty Gold Events and all nineteen SourceSegments.

Qwen3 will answer the unchanged ownership question under the same prompt and model artifact.

The runtime will request twenty first-position alternatives to reduce score censoring.

The evaluator will compare emitted answers with threshold decisions on the same executions.

The evaluator will report class recall, balanced accuracy, MCC, corrections, and regressions.

The experiment cannot activate production.

## Program completion

The program completes when production constructs an inspectable proposition from Attachment Edges.

The production path must preserve exact source evidence and complete execution lineage.

The production path must retain unresolved attachment decisions as explicit gaps.

The program does not require an exhaustive semantic role ontology.

## Stop conditions

Stop when one model task requires canonical identifiers or source offsets.

Stop when candidate construction cannot cover an approved Gold fragment.

Stop when one repeated occurrence cannot remain distinct through evaluation.

Stop when an identity-level score hides an occurrence-level error.

Stop when a deliverable assigns semantic roles before attachment passes.

Stop when an experimental result creates a ProposedChange or accepted Ledger record.

Stop when validation results influence the same TDD's prompt or candidate policy.
