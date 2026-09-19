# Competitive Event Attachment Program

- Status: CEA-1 supported; CEA-1.1 mixed; CEA-1.2 verified; CEA-1.3 closed; CEA-1.4 falsified at diagnostic; production inactive
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

CEA-1.4 tested one bounded semantic filter over one high-recall edge pool.

No CEA-1.1 Prompt Arm passed the production safety gates.

The next deliverable must route each edge to one bounded decision type.

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

CEA-1.4 classified its generic Edge Filter hypothesis as `falsified` on 2026-09-19.

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

The mandatory diagnostic gate blocked human approval.
The Pipeline did not execute full development or validation.
The experiment created no ProposedChange and changed no accepted Ledger state.
Production integration remains `not_activated`.

The next deliverable must separate four decision types.
KoteKomi must use ReferenceDecisions for reference-supported participation.
KoteKomi must route attribution scope to a bounded attribution task.
KoteKomi must route temporal scope to a bounded temporal task.
KoteKomi must route mixed Candidate scope to an atomicity task.

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
