# Intelligence Pipeline Improvement Agile Package

- Status: In progress
- Program ID: `intelligence-pipeline-improvement`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Predecessor: [Ingestion to Reviewed Assertion](2026-11-04-ingestion-to-reviewed-assertion-agile-package.md)
- First deliverable: IPI-01, Agree the passages and success measures
- Next deliverable: IPI-01 human approval of the proposed manifest
- Baseline revision: `7dc9a44`
- Implementation branch: `feature/ipi-intelligence-pipeline-improvement`
- Opening commit: `3ab08be`

## User Outcome and Strategic Shift

An operator obtains more source-faithful proposed Assertions, or obtains the same results with less review effort.
The operator uses normal ingestion, supported review commands, and source-linked replay.
Human review still controls accepted Ledger state.

> We have made real engineering progress, but too little of it has translated into a working intelligence pipeline.

This package funds improvements to that Pipeline.
Measurement helps choose and verify those improvements.
Measurement infrastructure, additional experiments, and test counts cannot substitute for a visible capability gain.

IRA demonstrated one real-source journey from ingestion through review to a proposed Assertion visible in replay.
Its recorded run contains 167 Events, one composed outcome, and 166 holds on `assertion_inputs_unavailable`.
Those counts measure workflow coverage.
They do not measure correctness, because the other Events were not independently assessed.
The run also contains proposals from the ingestion proposal plan, separate from reviewed recomposition.
Counts in this package follow the construction review's Assertion ID and resulting ProposedChange.

The package addresses the next limitation: the demonstrated workflow requires review, and its completeness and effort remain unmeasured across several passages.
The package does not restart the R16-R18 prompt-experiment sequence.

## Scope and Terms

An Assertion is an atomic statement with subject, predicate, object, qualifiers, classifications, and evidence.
A ProposedChange requires review before it changes accepted Ledger state.
A successful result here remains a proposed Assertion with a pending ProposedChange.
Independent assessment of that result does not itself accept the Assertion.

The following are proposed measurement definitions for this package, not new Domain Core types.

- A reference statement is one atomic meaning that a human reviewer identifies from the complete passage and its context.
- A complete result preserves that statement's participants, relation, essential complements, polarity, modality, attribution, and required time or place meaning.
- A usable result is a complete result with valid identity decisions, replayable evidence, a pending Assertion proposal, and linked content visible in replay.
- Active review time is time spent inspecting evidence, deciding, correcting, recovering from errors, and verifying replay.
- Waiting time is time spent waiting for ingestion, models, or commands rather than reviewing.
- A development passage can inform implementation choices.
- A reserved passage remains unavailable to the implementing agent until the implementation is fixed for final evaluation.

Semantic completeness concerns what the Source asserts, not independent truth of that assertion.
An atomic Assertion need not reproduce every adjacent sentence.
A reviewer specifies which context can be omitted without changing the reference statement's meaning.
An unsupported statement remains an explicit hold and contributes no usable result.

## Bounded Population

IPI-01 proposes 12 passages from at least two real Documents in the target intelligence domain.
A human reviewer approves six development passages and six reserved passages before baseline measurement.
The reviewer selects passages before seeing whether the current selector or composer can complete them.
The previous IRA case can serve as a regression but cannot count among the reserved passages.

Each partition contains at least two straightforward statements and two statements with meaning-bearing qualifiers or complements.
The reviewer identifies every in-scope reference statement in each selected passage.
The manifest fixes source digests, context, reference statements, and partition membership.
The reviewer records why each statement belongs in scope.
Representation limitations remain visible failures within that scope rather than reasons to replace a passage.
Changing the population or rubric requires explicit review and a new baseline.

The reviewer keeps reserved text and expected content outside the implementing agent's working context.
An evaluation operator runs the baseline and final workflow on those passages in separate disposable roots.
The operator measures development passages before implementation and keeps reserved comparisons until the final implementation is fixed.
A test copied from the development case is a regression, not independent evaluation.
If the agent has already inspected a proposed reserved passage, the reviewer replaces it before measurement.

## Primary Operator Flow

1. A reviewer agrees the passages, reference statements, and scoring rubric without consulting generated Assertions.
2. An operator ingests the Documents and attempts each statement through the existing review workflow.
3. The operator records usable results, failures, active review time, waiting time, and corrections.
4. The implementing agent compares bottlenecks across the entire ingestion and review path.
5. The agent ships one bounded production improvement and checks its development results.
6. An independent reviewer assesses the fixed implementation on reserved passages through the same workflow.

Accepted identity prerequisites use the existing validated acceptance path.
Each comparison starts from an equivalent fresh state, including the same declared pre-existing identities.
The operator creates required new prerequisites through review in both conditions.
The final run cannot inherit approvals or proposals from the baseline.
Corrections use supported operator commands; manually seeded outcomes and edited derived JSON do not count as usable results.

## Success Measures and Decision Gates

Let `N` be the number of reference statements fixed for a partition.
Let `C` be the number with a usable result after the bounded operator attempt.
Each reference statement contributes at most one to `C`, regardless of duplicate proposals.
A missed Event, unavailable candidate, unsupported composition, or unfinished review contributes zero.
The report lists extra, duplicate, and incorrect proposals separately.
Unknown timing cannot count as zero or satisfy the effort route.

The operator allows at most five active minutes per reference statement in each condition.
The operator records incomplete attempts at that limit instead of silently abandoning them.
A human can approve a different limit only before baseline measurement.

Let `A` be total active review seconds across all attempts, including failed attempts and recovery.
Compare the following measures separately for development and reserved passages.

| Measure | Definition | Decision it controls |
| --- | --- | --- |
| Usable coverage | `C / N`, with the fixed reference denominator | Whether production produces more complete intelligence |
| Review cost | `A / C`, undefined when `C = 0` | Whether effort falls without excluding unsuccessful attempts |
| Active effort | `A`, plus per-statement times and corrections | Which operator step deserves implementation work |
| Time to usable result | Active time plus waiting time, with timed-out attempts listed | Whether saved effort hides a new operational delay |
| Safety and fidelity | Per-statement semantic assessment, evidence replay, identity and approval checks | Whether a numerical gain is admissible |
| Stage losses | Reference statements lost at paragraph discovery, mentions/grounding, Events, selection, composition, review, proposal persistence, or replay | Where the next change belongs |

### Proposed numerical acceptance target

IPI-01 confirms these targets with the human before any baseline run.
The package succeeds only if production behavior changes and the reserved comparison meets either route:

- Capability route: at least two additional reference statements produce usable results, and review cost does not increase.
- Effort route: usable coverage does not fall, at least three reference statements produce usable results, and review cost falls by at least 25 percent.

If baseline `C = 0`, only the capability route applies.
For that case, final `C` must be at least two and total active effort must not exceed the baseline attempt budget.
The undefined baseline review cost does not become zero or an invented ratio.

Both routes require zero loss of a previously usable reference statement in the paired comparison.
Both routes require evidence replay, explicit review, and correct proposed-versus-accepted state for every counted result.
Any new semantic defect or unsafe state transition must be fixed before completion.
The report includes per-statement results so aggregate gains cannot hide regressions.
Waiting time, model calls, and runtime failures are reported alongside the primary measures.
A final waiting-time increase above 20 percent requires explicit operator acceptance before completion.

These targets are local acceptance decisions, not statistical proof of general reliability.
The report states sample size, operator identity, task order, prior familiarity, and timing uncertainty.
The operator alternates baseline-first and final-first order across reserved passages to reduce practice effects.
The operator uses blinded implementation labels where practical and discloses any unblinded comparison.

## Rules That Keep Work Directed at the Pipeline

### Compare stages before choosing a change

IPI-02 records a short table covering every stage in the Stage losses measure.
For each observed bottleneck, record affected reference IDs, evidence, operator cost, proposed correction, estimated effort, and dependencies.
Unknown impact stays unknown until one bounded inspection resolves it.
The table includes at least three candidate corrections from different stages when the evidence contains them.
If fewer exist, record the evidence rather than invent alternatives.

Choose the smallest feasible correction with the greatest evidenced improvement in usable coverage or review cost.
Favor changes that can complete a real operator journey over changes that improve an intermediate score alone.
Explain why the chosen correction outranks the next two feasible alternatives.
An upstream missed Event competes with a slow review command; neither disappears because the agent is currently editing composition.
A short inspection of a competing bottleneck does not require building its implementation.

### Bound setup and local attempts

The initial measurement setup is one deliverable with one small manifest and one result format.
Use existing typed observability, review records, composition outcomes, and replay summaries first.
A spreadsheet or Markdown table suffices for human timing and assessment.
Any new persisted machine-readable boundary needs an Application Layer DTO and validation.
A new dashboard, scoring framework, experiment registry, or generic evaluation engine is outside this package.

Plan no more than one working day of agent effort for initial measurement setup.
Reaching that limit triggers a concrete review of the missing measurement, not another instrumentation increment.
Existing correctness checks remain mandatory even when that limit is reached.

The package permits at most two production improvement cycles after the baseline.
Each cycle names a user-visible outcome, affected reference IDs, a production change, and its stop condition before work starts.
At most one bounded diagnostic experiment can precede that cycle's implementation.
Its possible outcomes must select an implementation decision; an inconclusive outcome triggers the next feasible correction from the table.

A cycle permits one implementation and one corrective attempt against its failing development cases.
If neither improves usable coverage or review cost, stop that approach and compare other stages again.
Test repairs and report refinements do not reset this limit.
A safety defect must still be corrected or the change reverted.
An unsuccessful change is reverted unless the human explicitly accepts a separate demonstrated benefit.

### Reconsider priorities after every cycle

Update the bottleneck table after each production change.
Compare at least one feasible correction outside the stage just changed before continuing there.
A second cycle in the same stage requires evidence that it still outranks those alternatives.
The agent cannot justify continuation merely by citing code already written or an almost-passing case.

Fix the implementation revision before revealing reserved passages or per-case results.
Use the reserved partition once for this package's acceptance comparison.
After exposure, those passages become development material for future work.
If the final comparison misses the target, record the outcome as Target not met.
Do not rename a hold as success, lower the bar, or start a new nearby experiment automatically.
A successor needs a human decision informed by the remaining bottleneck table.

## Deliverable Tracker

Each implementation deliverable requires a focused accepted TDD before it changes a boundary.
This package defines priorities and acceptance policy; it does not preselect a schema, model, or semantic extension.
Each production change ships and reverts independently.

| ID | Deliverable | Depends on | Status | Evidence |
| --- | --- | --- | --- | --- |
| IPI-01 | Agree passages, reference meanings, and attempt budget | None | Planned | Human-approved manifest and rubric |
| IPI-02 | Measure the existing workflow and compare stage bottlenecks | IPI-01 | Planned | Baseline, timings, stage table, ranked correction |
| IPI-03 | Ship the highest-value production correction | IPI-02 | Planned | Failing-first regression and normal operator journey |
| IPI-04 | Reassess priorities and deliver a second correction only if required | IPI-03 | Planned | Updated stage table and bounded production result |
| IPI-05 | Evaluate reserved passages and reconcile the package | IPI-03; IPI-04 decision | Planned | Independent assessment, measures, operator confirmation |

### IPI-01: Agree passages and reference meanings

- [ ] A: The reviewer fixes the 12 passages, partitions, context, and all in-scope reference statements.
- [ ] B: The reviewer approves completeness criteria, targets, attempt budget, and admissible omissions before baseline execution.
- [ ] C: Reserved content remains outside implementation context; source material is retrievable for the evaluation operator.
- [ ] D: The manifest includes missed and unsupported constructions without filtering by current output.

### IPI-02: Establish a baseline and choose work

- [ ] A: The operator records baseline counts and effort with fixed denominators and explicit missing measurements.
- [ ] B: The stage table covers discovery through replay and identifies the first blocking stage per failed reference statement.
- [ ] C: The agent ranks competing corrections across stages and selects a visible production outcome.
- [ ] D: Measurement remains within the setup limit and reuses retained contracts.

### IPI-03: Deliver the first improvement

- [ ] A: A focused TDD specifies the selected user outcome and boundary changes.
- [ ] B: Tests reproduce the defect or lock in existing behavior before a refactor.
- [ ] C: The normal ingestion/review/replay path demonstrates the improvement without seeded accepted state or expected outputs.
- [ ] D: Development results report changed usable coverage and review cost, plus semantic and safety regressions.
- [ ] E: The agent updates priorities across the full Pipeline before selecting further work.

### IPI-04: Decide whether another correction earns its place

- [ ] A: The agent compares the measured result with the proposed target and remaining cross-stage opportunities.
- [ ] B: The agent completes a second bounded correction, or records why final evaluation is now the best next action.
- [ ] C: Each continued attempt obeys the cycle limit; an exhausted approach ends with a reversion or an explicit retained-benefit decision.

A decision to skip the second correction can complete IPI-04.
It cannot count as an additional capability gain.

### IPI-05: Verify a product gain

- [ ] A: The operator runs fixed baseline and final revisions against reserved passages in separate fresh roots.
- [ ] B: A human independent of implementation assesses complete meanings and evidence against the predeclared rubric.
- [ ] C: One numerical success route passes with all fidelity, safety, and non-regression gates.
- [ ] D: The operator confirms linked proposed Assertions and remaining holds in replay.
- [ ] E: The report joins construction reviews to their Assertion proposals and lists every reference outcome.
- [ ] F: Operator instructions, CHECK_PLAN, tracker, and revision-specific checks match the delivered behavior.

## Ownership and Preservation

Application Layer use cases continue to own semantic decisions, review transitions, and transaction intent.
Adapters validate, load, and persist through declared Ports.
Pipelines compose the retained use cases; CLI and Textual expose their outcomes.
The Domain Core remains the owner of accepted-state invariants.

The package retains evidence replay, atomic acceptance, idempotent retry, explicit holds, and pending Assertion proposals.
A reviewer makes identity and classification decisions; convenience improvements cannot silently accept them.
Reusing a reviewed decision requires its explicit scope to cover the current identity, occurrence, or Source.
Historical evidence and operator runs remain read-only.
Portable captured fixtures exercise the real path and state their origin; invented parses remain construction tests only.
Semantic extensions require a focused TDD and counterexamples before implementation.
A new model or broad prompt search requires an explicit scope revision.

## Verification, Reporting, and Completion

Use the [CHECK_PLAN](CHECK_PLAN.md) for retained IRA, R20, replay, persistence, and whole-tree checks.
Each implementation TDD adds its exact commands and deterministic completion probe before the work runs.
Human-started live operations specify command, durable paths, completion probe, and success criteria.
The implementing agent does not poll those runs or write the operator's accepted Ledger records.
The agent continues independent authorized work while a human review is pending.
It does not treat elapsed time as approval.

The completion report names baseline and final revisions, manifest revision, reviewer, operator, fresh roots, and measurement limitations.
It reports `N`, `C`, `A`, review cost, waiting time, stage losses, incorrect proposals, and remaining work for each partition.
It distinguishes automatic draft quality from the final result after human corrections.
It names the production behavior responsible for the measured gain.

Complete requires IPI-05-C and the other acceptance checks.
Passing tests, better diagnostics, or a report with no product gain leaves the package incomplete.
After the allowed cycles or a failed reserved comparison, record Target not met and request a scope decision.
A truthful unsuccessful conclusion ends the measurement loop; it does not manufacture completion.

The next-work recommendation compares remaining addressable bottlenecks across the Pipeline.
It names the highest-value feasible correction and why continued work in the last edited component is or is not justified.
This package establishes bounded improvement evidence, not general extraction reliability or whole-package held-out validation.
