# HP-7 ProposedChange Integration Evaluation

- Status: Historical evaluation; execution path superseded by [HSQ-6](2026-09-07-source-bound-governed-event-extraction.md)

- Feature: [HP-7 Hybrid ProposedChange Integration](2026-09-03-hybrid-proposed-change-integration.md)
- Parent evaluation: [HP-6 Qualified Event Semantics Evaluation](2026-09-02-hp6-qualified-event-semantics-evaluation.md)
- Gold catalog: [HP-7 Proposal Admission Gold Catalog](hp7-proposal-admission-gold-v1.json)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`

## Evaluation operation

The retired HP-7 evaluator copied the retained legacy HP-6 Ledger and Archive into an isolated workspace.

HSQ-6 replaces that retained-report path with canonical source-to-Candidate-Wiki evaluation over current previews.

It replays the first retained HP-6 run for each reviewed case.

It constructs HP-7 Plans without a model call and submits every Plan twice.

It captures a review packet and applies the Gold review outcome only for proposed events.

It verifies that excluded Gold semantics are absent or held, create no `ProposedChange`, and require
no review action.

The output retains the exact HP-6 evidence given to admission.

The output also retains each decision, proposed body, review packet, and applicable review outcome.

## Corrective acceptance contract

The Hybrid Semantic Quality Program supersedes the original false-event expectation.

Seven approved Gold events must reach review as proposed events.

Those seven proposed events must pass their Gold review actions.

The Gold-rejected Amodei `said` recommendation must be excluded.

The forbidden recommendation may be absent upstream or terminate as held when observed.

It must create no `ProposedChange`, review packet, or accepted Event.

Every second submission reproduced the same Plan and proposal identities and returned `reused`.

## Integrity and traceability

Each candidate Event and Assertion retains exact replayable source evidence and its HP-1 through HP-6 identities.

Source-specific Actor and Organization proposals retain mention and reference lineage instead of event-specific lineage.

This distinction allows multiple events to share one typed entity proposal without creating conflicting bodies for one record identity.

The evaluator exposed that conflict in its first run; the Application mapping was corrected and a focused multi-event regression test now protects the rule.

HP-7 never invokes Qwen2.5, GLiNER, or ReFinED.

It deterministically maps already retained evidence into pending records.

Only the existing review use case creates accepted Ledger intelligence and review ProvenanceActivities.

## Finding ownership

The retained false recommendation exposed an incomplete semantic-admission policy and an
under-specified Gold locator.

The corrected policy must contain that error before the review boundary.

The evaluator reports a proposed false event as a policy or implementation failure.

The shared-entity collision found during the first replay was an implementation error.

It was not hidden or assigned to model quality; deterministic reference validation blocked the whole batch until the mapping was corrected.

The reviewed source text and current event ontology were sufficient for the seven review decisions
and one excluded semantic, so this bounded run found no data or ontology blocker.

## Conclusion

HP-7 now verifies both branches of the intended authority transition:

```text
HP-6 derived semantics -> deterministic HybridProposalPlan
    -> proposed -> pending ProposedChanges -> explicit human review
    -> excluded -> absent or held          -> no ProposedChange -> no review action
```

Model evidence can now reach review without becoming truth by accident.
