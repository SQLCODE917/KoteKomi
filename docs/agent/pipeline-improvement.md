# Pipeline Improvement

## Purpose and Scope

Build a working intelligence Pipeline through bounded production improvements.
Measurement selects and verifies that work.
Additional reports, experiments, and tests do not substitute for usable intelligence.

Apply this policy to capability work, Pipeline changes, experiments, and Agile packages.
Use the existing package tracker or task record for decisions and evidence.
This policy requires no new service, dashboard, registry, or evaluation framework.
It governs agent work; the master design and accepted contracts continue to govern Domain meaning.
Preserve existing package targets and declared approval gates.
Apply these rules to new work and remaining decisions without rewriting historical evidence.

An Assertion states one atomic meaning with its participants, relation, qualifiers, classifications, and evidence.
Assess completeness against a reviewed source meaning, including essential complements, polarity, modality, attribution, and time or place.
An inspectable proposed Assertion remains distinct from accepted Ledger intelligence.
Evidence that a Source asserts a statement does not establish that the statement is independently true.

## Choose and Deliver Work

1. Name the operator action, current failure, and required visible result.
   For semantic work, identify a source statement and its complete expected meaning before judging output.
   For maintenance, name the failure or cost and the product path it affects.
2. Locate the first blocking stage using existing typed observability and retained records.
   Record a suspected cause as a hypothesis until a focused check establishes it.
3. Compare feasible corrections across stages before selecting an approach.
   Consider affected statements, expected user benefit, effort, risk, dependencies, and confidence in the evidence.
   Compare alternatives outside the last edited component when the observed failures provide them.
   Explain the selection briefly; do not invent precise benefit estimates or alternatives without evidence.
4. Implement the smallest independently shippable correction that advances the intended operator workflow.
   Name its affected cases, expected production behavior, and stop condition before starting.
   Write a focused TDD when a boundary changes.
   Use the retained production entry points and existing review requirements.
5. Verify the implementation and assess the complete result separately.
   Trace source content through evidence, the proposed record, persistence, and presentation where those boundaries apply.
   Keep failures visible by source statement or Event.
6. Reassess priorities after each production cycle.
   Continue in the same stage only when current evidence ranks it above feasible alternatives elsewhere.
   Code already written and an almost-passing case are not evidence of user benefit.

The first blocking stage is an investigation starting point, not an automatic priority or a proven cause.
For example, absent selected roles do not alone establish a grounding defect.
A large loss count does not establish that a proposed correction will recover those losses.
Choose the smallest useful path to the operator result rather than maximizing an intermediate score.

## Evidence and Claims

State observations, hypotheses, and demonstrated causes separately.
Name the tested revision, inputs, assessed population, and limitations beside a result.

| Evidence | Permitted conclusion |
| --- | --- |
| Engineering tests pass | The tested contracts hold |
| Event discovered | The Pipeline identified a possible happening |
| Proposition composed | Current structural rules accepted that proposition |
| Complete meaning and evidence assessed | That particular result satisfies the declared semantic rubric |
| Development cases improve | The change helps those assessed development cases |
| Reserved cases improve | The comparison provides transfer evidence within that assessed set |
| Human effort measured under a fixed protocol | That protocol permits an operator-effort comparison |

Structural acceptance cannot establish semantic completeness.
Counterfactual counts identify mechanisms and opportunities; they do not establish correct, complete Assertions without assessment.
Distinct live runs can differ in model outputs and machine load.
Equal model-call counts do not prove equal outputs or explain a timing difference.
Use captured-input replay to isolate deterministic behavior changes when a causal claim requires it.
Finite case evidence does not establish general extraction reliability.

## Verification and Measurement Scale

Use the cheapest existing evidence that can reject or establish the intended claim.
Reuse captured source inputs and parses for deterministic selection and composition changes.
Verify that a capture passes the production boundary validators before relying on it.
Run fresh ingestion when the changed boundary or acceptance claim requires fresh execution.
Do not repeat a full ingestion solely to regenerate unchanged intermediate inputs.
Follow [Long-Running Operations](long-running-operations.md) for authorized live runs and expensive checks.

A bounded bug fix needs a failing regression and verification through its affected product boundary.
A behavior-preserving refactor needs characterization tests and the same behavior after the change.
Neither automatically needs a new corpus, timed study, or reserved partition.
A claim of lower operator effort requires measured effort under a declared protocol.
A claim of transfer requires cases unavailable to implementation decisions.
Declare broader capability targets, denominators, and assessment rules before implementation or measurement as the package requires.

Use existing Ledger and Archive records before adding instrumentation.
Keep a manual timing or assessment table when it suffices.
A missing metric warrants only the smallest addition needed for the declared decision.
The package states a setup budget before instrumentation starts.
Reaching that budget requires a decision about the missing evidence, not an automatic instrumentation increment.

## Iteration Limits and Autonomy

A production cycle tests one user-visible improvement hypothesis through implementation and assessment.
It is not an individual edit, test run, or debugging step.
Capability packages default to at most two production cycles unless their approved scope specifies another limit.
Each cycle permits one bounded diagnostic experiment, one implementation approach, and one corrective attempt against its target cases.
Ordinary debugging to satisfy the selected contract remains authorized within that approach.
Focused regression and cause-isolation checks are verification, not separate production experiments.
Repeated probes that seek a new improvement hypothesis consume the diagnostic budget regardless of their label.
Renaming an experiment, repairing tests, or refining a report does not reset a consumed cycle.

Before an experiment, name the implementation decision each possible result will change.
Specify the next implementation action for an inconclusive result.
If every result leads only to more investigation, revise or omit the experiment.
After an unsuccessful corrective attempt, stop that approach and compare feasible corrections across stages again.
Resolve a safety defect or revert its change even when the cycle budget is exhausted.
Do not start another cycle after the package limit without an explicit scope decision.

Continue routine implementation, fixture authoring, wiring, and verification within the authorized scope.
Module count, missing test fixtures, and an ordinary failed attempt are implementation work, not approval blockers.
Preserve reviewable work and continue independent authorized tasks while a human decision is pending.
Human gates declared by the package must precede the work they govern.
An autonomy instruction does not authorize bypassing those gates or approving meanings on the human's behalf.
Escalate a concrete unavailable capability, an unapproved semantic extension, or a decision outside accepted scope.
Present the evidence and the smallest concrete decision needed.

## Assessment Integrity

Agree reference meanings from complete source context rather than generated results.
Fix in-scope statements, admissible omissions, denominators, and targets before the comparison they govern.
Retain missed Events, unsupported statements, and unfinished attempts in the declared population.
Account for unsuccessful effort and waiting under the approved protocol.
Unknown effort is unmeasured, not zero.

Record who performed each assessment and which tasks an agent assisted or performed.
Agent execution time cannot replace human active-review time.
Disclose changes in reviewer, protocol, population, or implementation order before interpreting the result.
Preserve completed measurements and their provenance when a human delegates later work.
Do not combine incompatible measurements into an acceptance claim.

Keep reserved content and expected meanings outside the implementing agent's context until the declared evaluation.
After exposure or evaluation, those cases can inform development but cannot remain fresh independent evidence.
Do not tune against reserved failures and claim the same evaluation as independent validation.
Reviewed expected meanings are not regenerated from changed implementation output.
Join construction reviews to their Assertion proposals rather than counting unrelated ingestion proposals as reviewed results.
Assessment of a proposed Assertion does not accept it into the Ledger.

## Completion and Retention

Report these three decisions separately.

| Decision | Required evidence |
| --- | --- |
| Implementation verified | Applicable tests, formatting, lint, typecheck, and contract checks pass |
| Capability demonstrated | The intended operator behavior works on named cases with assessed meaning and evidence |
| Package target met | The declared package acceptance gates pass on the declared population |

Engineering completion alone does not complete a capability package.
Maintenance work can finish against its declared engineering and operational requirements without claiming extraction gains.
Use the existing tracker to distinguish implementation progress from the package result.
When the allowed evaluation ends below target, close the evaluation as `Target not met` and request a scope decision.
Do not mark the capability package `Complete`, lower its target, or automatically start a successor experiment.

A verified partial improvement can be retained through normal review even when the package misses its target.
Name its demonstrated benefit and limitations separately from package success.
Revert an unsafe change if its required invariants cannot be restored.
Revert an unsuccessful change unless review explicitly accepts another demonstrated benefit.
Closeout ends the local loop; it does not require discarding useful, safe work.

The next-work recommendation compares remaining addressable failures across the Pipeline.
It states why the proposed correction outranks alternatives and what remains unknown.
It does not default to another extension of the component last edited.
