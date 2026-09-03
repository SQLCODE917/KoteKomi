# HP-7 ProposedChange Integration Evaluation

- Feature: [HP-7 Hybrid ProposedChange Integration](2026-09-03-hybrid-proposed-change-integration.md)
- Parent evaluation: [HP-6 Qualified Event Semantics Evaluation](2026-09-02-hp6-qualified-event-semantics-evaluation.md)
- Gold catalog: [HP-7 Proposal Admission Gold Catalog](hp7-proposal-admission-gold-v1.json)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`

## Evaluation operation

`scripts/verify_hp7_proposed_changes.py` copies the retained HP-6 Ledger and Archive into an isolated workspace.

It replays the first retained HP-6 run for each reviewed case, constructs HP-7 Plans without a model call, submits every Plan twice, captures an existing review packet, and applies the Gold review outcome through the existing review use cases.

The output retains the exact HP-6 event, gaps, statements, and support judgments given to admission; the admission decision; every proposed JSON body; the review packet; and the final review outcome.

## Observed results

The evaluation processed eight reviewed events with zero findings.

Seven previously reviewed HP-6 Gold events were admitted to review and approved.

The Amodei `said` event was also admitted because its governed shape was complete and each separate support task returned `directly_supported`.

The reviewer rejected it because the source reports uncertainty and a conditional policy assessment, not a recommendation.

No accepted Event was created for that rejected proposal, and every event-owned Assertion proposal was rejected with it.

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

The retained false recommendation is a model interpretation error.

Strict HP-7 admission is not designed to relitigate that semantic judgment, so admitting it is not a policy failure.

The review boundary worked as designed and prevented the error from becoming accepted wiki state.

The shared-entity collision found during the first replay was an implementation error.

It was not hidden or assigned to model quality; deterministic reference validation blocked the whole batch until the mapping was corrected.

The reviewed source text and current event ontology were sufficient for all eight review decisions, so this bounded run found no data or ontology blocker.

## Conclusion

HP-7 establishes the intended authority transition:

```text
HP-6 derived semantics
    -> deterministic HybridProposalPlan
    -> pending ProposedChanges
    -> explicit human review
    -> accepted Ledger records or retained rejection
```

Model evidence can now reach review without becoming truth by accident.
