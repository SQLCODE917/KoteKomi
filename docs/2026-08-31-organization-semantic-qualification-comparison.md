# TDD: Organization Semantic Qualification Comparison

- Status: Accepted
- Program: [Organization Mention Reconciliation and Resolution Program](2026-08-28-organization-mention-reconciliation-program.md)
- Increment: ORG-R2
- Predecessor: [ORG-R1 Organization Mention Boundary Reconciliation](2026-08-31-organization-mention-boundary-reconciliation.md)
- Scope: derived diagnostic evidence only

## Context & Problem

ORG-R1 preserves source-valid Organization candidates and records deterministic boundary decisions.

ORG-R1 does not decide whether one candidate denotes an Organization in its source context.

The existing H2.2 task can return a different source expression from its input candidate.

That behavior mixes semantic qualification with boundary repair.

ORG-R2 must compare semantic systems while it holds the ORG-R1 boundary constant.

### Terms

A `Qualification Candidate` is one source-valid candidate that ORG-R1 preserved.

A `Qualification Judgment` states whether that exact candidate denotes an Organization.

A `Qualification Execution` is one producer attempt to judge one Qualification Candidate.

A `Qualification Bundle` is a tracked set of normalized ORG-R2 evaluation records.

An `Eligible Candidate` has an exact Gold boundary or no overlap with a Gold boundary.

A `Boundary Case` overlaps a Gold boundary without matching it exactly.

### User outcome

A reviewer can compare Qwen2.5 and ReFinED judgments for the same literal candidate.

The reviewer can trace each judgment through ORG-R1 to exact authoritative source characters.

The reviewer can inspect complete data in and data out for every error or disagreement.

### Primary flow

1. The evaluator rebuilds Qualification Candidates from frozen ORG-R1 evidence.
2. The evaluator sends each exact candidate and Source segment to Qwen2.5 and ReFinED.
3. The Application Layer validates each producer result and constructs a Qualification Judgment.
4. The evaluator scores eligible judgments against the reviewed Gold catalog.
5. The evaluator writes a normalized Qualification Bundle and a failure review.
6. The evaluator records development and sealed held-out results without changing production behavior.

## Goals

- Compare two independent semantic approaches on identical ORG-R1 candidates.
- Preserve complete source, boundary, producer, execution, and decision lineage.
- Separate semantic errors from boundary errors and runtime failures.
- Measure quality, abstention, latency, and stability without selecting a production path.
- Retain directly inspectable evaluation evidence in Git.

## Requirements

### Candidate catalog

- CC-01: The evaluator derives every Qualification Candidate from an ORG-R1 preserved candidate.
- CC-02: The catalog binds the ORG-R1 policy, freeze commit, report digest, and decision identity.
- CC-03: The catalog stores exact source text, source digest, candidate text, and half-open offsets.
- CC-04: The catalog includes candidates from resolved, uncontested, and ambiguous decisions.
- CC-05: The evaluator rejects candidate, source, decision, or digest drift.
- CC-06: Three frozen ORG-R1 repetitions must contain equivalent candidate boundaries.

### Application Layer

- AQ-01: The Application Layer defines `organization`, `not_organization`, and `ambiguous`.
- AQ-02: The Application Layer constructs each Qualification Judgment from one exact candidate.
- AQ-03: A Qualification Judgment cannot change candidate text or offsets.
- AQ-04: The Application Layer keeps semantic judgment separate from execution status.
- AQ-05: Each judgment references its producer evidence and terminal stage trace.
- AQ-06: Producer scores remain diagnostics and do not become truth confidence.

### Qwen2.5 producer

- QW-01: Qwen2.5 receives one Qualification Candidate per bounded model task.
- QW-02: Qwen2.5 receives the exact Source segment used by the candidate.
- QW-03: The task accepts exactly `organization`, `not_organization`, or `ambiguous`.
- QW-04: The evaluator records the prompt, rendered input, raw output, `ModelRun`, and timing.
- QW-05: Invalid model output produces `invalid_output` and no semantic judgment.

### ReFinED producer

- RF-01: The ReFinED Port accepts exact source text and caller-supplied candidate spans.
- RF-02: The ReFinED Adapter uses the official predetermined-span inference mode.
- RF-03: The Adapter returns project-owned DTOs instead of ReFinED objects.
- RF-04: The Adapter records the model, entity set, package revision, resources, and timing.
- RF-05: The Adapter preserves linked entity, top-k entity, fine type, coarse type, and score evidence.
- RF-06: The Adapter rejects missing, duplicate, reordered, or source-drifted span results.
- RF-07: The worker uses an isolated Python environment and an explicit executable path.
- RF-08: The evaluation runs without network access after resource setup.
- RF-09: Worker or resource failure produces a typed blocked evaluation result.

### ReFinED mapping

- RM-01: `ORG` coarse mention evidence maps to `organization`.
- RM-02: Explicit non-ORG coarse mention evidence maps to `not_organization`.
- RM-03: Missing, unknown, or conflicting coarse mention evidence maps to `ambiguous`.
- RM-04: The mapping records its policy identity with every decision.
- RM-05: A ReFinED entity link does not become a KoteKomi Organization identity.

### Gold scoring

- GS-01: An exact Gold span has expected judgment `organization`.
- GS-02: A candidate disjoint from all Gold spans has expected judgment `not_organization`.
- GS-03: A non-exact Gold overlap is a Boundary Case.
- GS-04: The evaluator excludes Boundary Cases from semantic precision and recall.
- GS-05: The evaluator reports Boundary Cases with their ORG-R1 decision and overlap relation.
- GS-06: Resolved reference entries remain outside ORG-R2 Gold scoring.

### Evidence retention

- ER-01: The evaluator writes development and held-out Qualification Bundles under `docs/evaluations/org-r2/`.
- ER-02: Each bundle contains a manifest, inputs, executions, decisions, traces, metrics, and review records.
- ER-03: The bundle stores each canonical shared source and prompt payload once and references it by
  content identity; derived human review records may render a copy for direct inspection.
- ER-04: The bundle preserves complete observable producer output without truncation.
- ER-05: The manifest records every file path, SHA-256 digest, and record count.
- ER-06: A resumed run accepts only an identical manifest and fills only missing executions.
- ER-07: A resumed run rejects a conflicting execution for an existing execution identity.
- ER-08: The held-out bundle refuses overwrite after its first complete evaluation.
- ER-09: A compact result record binds both complete bundle manifests by SHA-256 and resolves their
  ORG-R1 report, catalog, and reconciliation digests to the frozen ORG-R1 result commit.

### Failure review

- FR-01: The evaluator emits one review record for every wrong, ambiguous, invalid, or disagreeing result.
- FR-02: A review record includes complete source, candidate, expected result, producer input, and producer output references.
- FR-03: The reviewer assigns one or more fixed root-cause hypotheses or `unresolved`.
- FR-04: The reviewer assigns one or more fixed semantic case tags or `other`.
- FR-05: The evaluator does not infer a root cause from aggregate metrics.

## Proposed Architecture

```text
Frozen ORG-R1 evidence
        |
        v
Application candidate catalog
        |
        +--------------------+
        |                    |
        v                    v
Qwen ModelRuntime       ReFinED Port
        |                    |
        +---------+----------+
                  |
                  v
Application judgments
                  |
                  v
Pipeline evaluator
                  |
                  v
Tracked Qualification Bundle
```

The Application Layer owns candidate validation, judgment mapping, and scoring rules.

The Qwen path uses the existing `ContextPlanner`, `ModelRuntime`, and `ModelRun` contracts.

The ReFinED Adapter translates the isolated worker protocol into Application DTOs.

The Pipeline evaluator orchestrates the comparison and writes derived diagnostic files.

No ORG-R2 component writes accepted Ledger state.

## Key Interactions

```text
Evaluator          Application       Qwen          ReFinED        Bundle
    |                    |              |              |              |
    | rebuild catalog    |              |              |              |
    |------------------->|              |              |              |
    | validated inputs   |              |              |              |
    |<-------------------|              |              |              |
    |                    | run candidate|              |              |
    |                    |------------->|              |              |
    |                    | raw result   |              |              |
    |                    |<-------------|              |              |
    |                    | run same span|              |              |
    |                    |---------------------------->|              |
    |                    | type evidence              |              |
    |                    |<----------------------------|              |
    |                    | construct judgments         |              |
    |                    |--------------|              |              |
    | judgments + traces |              |              |              |
    |<-------------------|              |              |              |
    | write normalized evidence                         |              |
    |--------------------------------------------------------------->|
```

## Data Model

### `QualificationCandidate`

```text
id
source_segment_id
source_text_sha256
text
start
end
boundary_decision_id
boundary_status
boundary_rule_id
source_candidate_ids
proposer_ids
```

### `OrganizationQualificationDecision`

```text
id
candidate_id
producer_id
judgment
execution_status
evidence_record_id
execution_record_ids
terminal_trace_id
mapping_policy_id
diagnostics
```

### `ContextualOrganizationTypeEvidence`

```text
candidate_id
returned_text
start
end
coarse_type
coarse_mention_type
predicted_entity
entity_linking_score
top_k_entities
predicted_entity_types
failed_class_check
```

### Qualification Bundle

```text
manifest.json
inputs.jsonl
prompt.json
qwen-inputs.jsonl
refined-runtime.json
refined-batches.jsonl
executions-qwen.jsonl
executions-refined.jsonl
decisions.jsonl
traces.jsonl
metrics.json
review.jsonl
review.md
attempts-qwen.jsonl (only when a pre-inference Qwen attempt fails)
attempts-refined-pre-freeze.jsonl (only when a worker changes before policy freeze)
attempts-refined-pre-freeze-runtime.json (only when a worker changes before policy freeze)
refined-blocked.json (only when an isolated worker attempt blocks)
```

All bundle records use deterministic canonical JSON encoding.

Execution timing and non-deterministic output remain evidence and can change between runs.

If an unsealed run reaches the model boundary with an invalid execution profile, the failed
attempts are retained separately before the corrected executions begin. They remain part of the
sealed bundle and are never scored as semantic judgments.

## APIs / Interfaces

The Application Layer defines a `ContextualOrganizationTypePort`.

The Port accepts one source text plus an ordered tuple of Qualification Candidates.

The Port returns one evidence record for every input candidate.

The worker protocol uses one strict JSON request and one strict JSON response per batch.

The Adapter validates the response through Application DTOs before it returns.

The evaluation command requires explicit development or held-out phase and output directory.

The command supports resume for an incomplete development bundle.

The command never resumes or overwrites a completed held-out bundle.

## Behavior & Domain Rules

The Qwen and ReFinED producers receive identical candidate IDs, source text, and offsets.

The Qwen prompt can explain the KoteKomi Organization policy.

The ReFinED mapping uses only returned type evidence.

The evaluator preserves producer outputs separately.

The evaluator does not fuse producer judgments in ORG-R2.

An `ambiguous` judgment is a valid semantic abstention.

An invalid output is not an `ambiguous` judgment.

The evaluator reports organization precision, recall, and F1.

The evaluator also reports specificity, exact accuracy, decisive accuracy, coverage, ambiguity,
invalid output, availability, latency, and exact-label stability.

For exact-Gold and disjoint-Gold executions, `organization` is the positive class and
`not_organization` is the negative class. Precision, recall, F1, and specificity use only decisive
labels. Exact accuracy counts `ambiguous` as an incorrect completed judgment; decisive accuracy
excludes it. Coverage is decisive completed judgments divided by all completed eligible judgments.
Runtime availability counts completed and invalid-output responses, while valid-output rate counts
only completed semantic judgments. Exact-label stability requires all three repetitions to complete
with the same label. Latency reports nearest-rank median and p95 alongside minimum and maximum.

The evaluator applies these root-cause hypothesis values:

```text
model_capability
input_context
prompt_contract
specialized_model_scope
architecture
ontology
implementation
gold_or_source_data
unresolved
```

The evaluator applies these semantic case tags:

```text
country_as_government
supranational_body
media_outlet
initiative_or_project
event
product
job_title_or_role
generic_class
citation_only
other
```

The reviewer, not the evaluator, assigns root-cause hypotheses and semantic case tags.

## Acceptance Criteria

- AC-CC-01: Catalog tests prove every ORG-R1 preserved candidate appears exactly once.
- AC-CC-02: Catalog tests reject source, offset, digest, policy, decision, and repetition drift.
- AC-AQ-01: Application tests prove all three judgments and separate execution statuses.
- AC-AQ-02: Application tests prove no qualification result can change a candidate boundary.
- AC-QW-01: Fake-runtime tests prove exact prompt, source, candidate, raw output, and `ModelRun` retention.
- AC-QW-02: Negative tests prove malformed output becomes `invalid_output`.
- AC-RF-01: Adapter tests prove exact predetermined-span request and complete response mapping.
- AC-RF-02: Negative Adapter tests reject missing, duplicate, reordered, and drifted spans.
- AC-RF-03: A real worker smoke test processes caller-provided spans offline after setup.
- AC-RM-01: Mapping tests prove ORG, non-ORG, and unknown type behavior.
- AC-GS-01: Scoring tests prove exact, disjoint, and overlap eligibility rules.
- AC-ER-01: Bundle tests prove canonical records, file digests, resume, conflict, and held-out sealing.
- AC-ER-02: Trace tests prove each qualification trace reaches one ORG-R1 boundary decision.
- AC-FR-01: Report tests prove every failure and disagreement receives complete review evidence.
- AC-EV-01: Development evaluation runs both producers three times on identical candidates.
- AC-EV-02: Held-out evaluation runs once after the implementation and policies are frozen.
- AC-EV-03: Both complete bundles and the compact result remain tracked in Git.
- AC-EV-04: ORG-R2 leaves production selection and accepted Ledger state unchanged.

## Reference Implementations

- Boundary lineage: `organization_mention_boundary_reconciliation.py`.
- Shared traces: `extraction_stage_trace.py`.
- Qwen execution evidence: `php1_diagnostic_support.py`.
- Adapter Port shape: `organization_mention_proposer.py`.
- ReFinED predetermined spans: `Refined.process_text(text, spans=...)` in ReFinED V1.

## Constraints and Halt Conditions

ORG-R2 does not implement entity identity or reference resolution.

ORG-R2 does not alter the Organization ontology.

ORG-R2 does not select or fuse a production qualification path.

The implementation must not patch or fork ReFinED to make the experiment pass.

The evaluator stops when the pinned worker cannot execute the official predetermined-span mode.

The evaluator stops when held-out Gold influenced prompt, mapping, or policy changes.

The evaluator stops when any producer receives different source characters or candidate boundaries.

## Implementation result

ORG-R2 ran both producers three times over identical ORG-R1 candidates and retained complete
development and held-out Qualification Bundles.

The held-out evaluation contained 222 unique candidates and 666 executions per producer. Qwen2.5
reached 0.505682 exact accuracy, 0.613636 coverage, 0.824074 decisive accuracy, and 0.941441
exact-label stability. ReFinED reached 0.513228 exact accuracy, 0.587302 coverage, 0.873874
decisive accuracy, and 1.0 exact-label stability.

Both systems had high positive-class recall but weak negative specificity. Qwen2.5 also produced 39
invalid held-out outputs, all preserved without repair or semantic judgment. The review evidence shows
that unresolved acronyms, generic references, and source-local institutional readings remain major
inputs to later ORG-R3 and ORG-R4 work.

ORG-R2 did not fuse the producers, select a production path, change accepted Ledger state, or alter
the Organization ontology. The compact immutable outcome is recorded in [Organization Semantic
Qualification Result](organization-semantic-qualification-result-v1.json).
