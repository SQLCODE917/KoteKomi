# HP-6 Qualified Event Semantics Evaluation

- Feature: [HP-6 Qualified Event Semantics and Source Support](2026-09-02-qualified-event-semantics-source-support.md)
- Parent evaluation: [HP-5 Atomic Claim and Ontology Evaluation](2026-09-02-hp5-atomic-claim-evaluation.md)
- Gold catalog: [HP-6 Event Semantics Gold Catalog](hp6-event-semantics-gold-v1.json)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

## Evaluation operation

`scripts/verify_hp6_event_semantics.py` validates the retained HP-5 report and
invokes the public `extraction build-event-semantics` command twice for each of
its ten evaluated cases.

Each run retains the public command result, complete HybridEventSemanticsPreview,
semantic signature, every ModelRun ID, and every exact raw model output.

The Gold comparison covers seven human-reviewed events in five scenarios.

Unlisted parent events remain visible in the Preview but are not scored as
either mapped or unresolved.

## Observed results

The final two-pass evaluation produced 20 runs.

It reported zero Gold findings and zero stability findings.

Across both repetitions, the runs produced:

- 34 EventSemanticDraft records;
- 100 EventArgumentAssignmentDraft records;
- 56 explicit SemanticCoverageGap records;
- 252 SemanticStatement records;
- 252 SemanticSupportJudgment records; and
- 414 archived ModelRun records.

The seven reviewed events matched their expected frames, roles, target kinds,
exact source targets, qualifiers, and attribution in both repetitions.

The reviewed set includes change in intensity, authorization,
characterization, recommendation, causation, investment abandonment, and
classification.

All reviewed SemanticStatements were directly supported in both repetitions.

## Authority and traceability

Qwen selected only task-local governed frame and role meanings.

Separate bounded tasks selected each role target.

KoteKomi resolved every selected candidate, sibling event, or source literal to
authoritative source characters and constructed all IDs, ranges, digests,
EvidenceTargets, and validation attempts.

A second set of tasks judged deterministic SemanticStatements against the full
exact SourceSegment without receiving normalization rationale.

Every stage retained exact data in, parsed data out, the complete raw model
output digest, prompt and schema digests, and causal stage lineage.

Preview reload replayed every referenced EvidenceTarget against the accepted
DocumentRepresentationBundle.

The operation created no Event, Assertion, Relationship, or ProposedChange and
changed no accepted wiki intelligence.

## Visible limitations

Six runs were typed `blocked` because their HP-5 parents were blocked.

The other fourteen runs were typed `partial` because their parents, semantic
gaps, or unscored event interpretations remained incomplete.

The support pass produced 248 `directly_supported` and four
`partially_supported` judgments.

The two unique partial judgments were stable across repetitions:

- an `announced` event was normalized as authorization, while the support task
  correctly observed that an announcement alone does not establish
  authorization; and
- `the US` was assigned as a causation cause for `started the 2026 Iran war`,
  while the support task found only partial support for that role meaning.

The evaluator also preserved an invented `announcement` frame as raw model
output and excluded it with `unknown_event_frame` instead of crashing or
constructing governed semantics.

One unscored event remains a material HP-7 design warning.

An Amodei `said` event whose content reports uncertainty was normalized as a
recommendation, and its separate Qwen support tasks still returned direct
support.

Independent tasks prevent normalization rationale from leaking into support,
but they do not make two judgments from the same model statistically or
semantically independent.

HP-7 must not interpret a model support outcome as automatic truth or accepted
state.

It must preserve review as the authority boundary and define explicit admission
rules from the governed draft, its gaps, and its support evidence.

## Conclusion

HP-6 verifies the intended hybrid boundary for the reviewed event slice.

The model interprets bounded source meaning.

KoteKomi owns ontology identifiers, exact source mapping, typed construction,
validation, replay, and state authority.

Unsupported, partial, malformed, and out-of-profile results remain visible and
cannot silently enter the intelligence Ledger.
