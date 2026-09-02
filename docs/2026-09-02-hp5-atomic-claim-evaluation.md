# HP-5 Atomic Claim and Ontology Evaluation

- Feature: [HP-5 Hybrid Atomic Claims and Ontology Validation](2026-09-02-hybrid-atomic-claims-ontology-validation.md)
- Parent evaluation: [HP-4 Event Frame Evaluation](2026-09-02-hp4-event-frame-evaluation.md)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Scope: the same 12 reviewed HP-4 development cases

## Evaluation operation

`scripts/verify_hp5_atomic_claims.py` consumes the retained HP-4 evaluation
report. It invokes the public `extraction build-atomic-claims` command twice
for every available HP-4 Preview. The report retains the complete HP-4 input,
HP-5 output, exact EvidenceTarget and validation-attempt records, both public
command results, and finding ownership.

The evaluator snapshots Event, Assertion, Relationship, and ProposedChange
records before and after the run. EvidenceTarget and EvidenceValidationAttempt
records are deliberately excluded from that snapshot because HP-5 is required
to persist them as canonical evidence records.

## Observed results

All 12 reviewed cases appear in the report.

Two cases had no HP-4 Preview because they had already stopped at HP-1. The
evaluator records them as `upstream_unavailable`; it does not invent an HP-5
result.

The remaining ten cases produced:

- 21 EventSubjectDraft records;
- 128 AtomicClaimDraft records;
- 21 OntologyValidationReport records;
- 14 full-SourceSegment EvidenceTargets;
- 73 explicit ontology findings; and
- ten byte-identical second HP-5 replays.

The 128 claims comprise 43 `has_argument`, 21 `has_event_type`, 21
`has_modality`, 21 `has_polarity`, 14 `has_time`, and 8 `according_to` atoms.
No evaluated frame contained an accepted HP-4 place qualifier.

The Event, Assertion, Relationship, and ProposedChange snapshot remained empty
and byte-identical. HP-5 therefore created evidence records but no accepted or
proposed intelligence.

## Ontology findings

All 21 reports were nonconformant under the deliberately small
`hybrid_event_core_v1` slice. This is not a source-truth failure score.

The exact findings were:

- 21 `unmapped_event_type` findings;
- 37 `unmapped_argument_role` findings; and
- 15 `attribution_support_missing` findings.

The HP-4 model proposed labels such as `disinvestment`, `announcement`,
`investor`, and `target_of_disinvestment`. HP-5 preserved those labels exactly.
It did not map them to `event`, `actor`, `participant`, or `object` by spelling,
case, or meaning.

Six of 43 argument labels matched the small core role set exactly. None of the
21 open event labels matched the core label `event`. The result demonstrates
that HP-5 is a lossless conformance boundary and label inventory. It does not
demonstrate that the initial core slice is a useful governed event vocabulary.
That vocabulary remains later work.

## Truthfulness and traceability

Every AtomicClaimDraft references one EvidenceTarget and one successful
EvidenceValidationAttempt. Each target selects the full authoritative
SourceSegment in the accepted logical TextView and retains its paragraph node
and PDF region lineage. Reload replayed every selector against the pinned
DocumentRepresentationBundle.

For HP4-AD-08, HP-4 separated the clause into a causal frame around `caused`
and a disinvestment frame around `abandon`. HP-5 preserved both subjects. The
disinvestment subject has separate argument atoms for 1789 Capital and
Anthropic, plus event type, polarity, modality, and source-attribution atoms.
Its one EvidenceTarget is the exact source sentence. The open labels remain
visible as findings instead of being accepted as governed ontology terms.

For HP4-AD-01, broad and overlapping HP-4 triggers remained broad and
overlapping in HP-5. HP-5 did not merge them or claim that they were correct.
That is the intended authority boundary: atomization is faithful to its parent,
while source-support judgment remains HP-6 work.

## Stage ownership

The evaluator classified all 73 findings without changing them:

- 58 belong to HP-4 open event or role proposals; and
- 15 belong to the missing HP-4 candidate-attribution support contract.

No claim was observed with a wrong source segment, missing frame field,
invented value, changed open label, or unreplayable EvidenceTarget. Those would
be HP-5 implementation defects.

Semantically questionable frames remain upstream HP-4 evidence. HP-5 faithfully
atomizes them, and the ontology report remains orthogonal to whether their
claims are supported by source prose.

## Conclusions

HP-5 validates the intended division of work:

- HP-4 performs fallible event and role interpretation.
- HP-5 deterministically constructs atomic records and evidence selectors.
- The ontology slice performs exact conformance only.
- Unknown labels and contract gaps remain explicit.
- No derived interpretation becomes accepted Ledger intelligence.

The next bounded slice can judge each atom against its EvidenceTarget without
depending on ontology conformance and without reconstructing source offsets.
