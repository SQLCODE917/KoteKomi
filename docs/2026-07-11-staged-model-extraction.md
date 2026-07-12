# TDD: Staged Model Extraction

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Evidence Targets](2026-07-11-replayable-evidence-targets.md), [Context Planning](2026-07-11-deterministic-context-planning.md)

## 1. Context and problem

The superseded whole-document proposal path asked one model invocation to discover ontology records, assign identifiers, extract claims, select evidence, and emit a proposal batch.

Long documents do not fit that path.

Combining semantic judgment with canonical bookkeeping made failures difficult to isolate, replay, or validate.

## 2. Goals

- Run one bounded semantic task per model invocation.
- Separate mention discovery, reference resolution, claim extraction, evidence grounding, and consolidation.
- Preserve exact inputs, raw outputs, parsed outputs, validation, and retries.
- Let the model abstain when text is ambiguous or unsupported.
- Keep canonical IDs, hashes, proposal construction, and ledger writes deterministic.
- Ensure only grounded, schema-valid candidate records reach `ProposedChange` review.
- Preserve disagreements and alternatives instead of forcing premature merging.

## 3. Non-goals and forbidden approaches

This TDD does not make model output authoritative or require a particular model family.

Forbidden:

- sending unbounded whole documents to the model;
- accepting model-provided canonical IDs, source IDs, evidence IDs, or record hashes;
- parsing malformed output by guessing what the model intended;
- allowing references to source nodes absent from the context manifest;
- creating proposals from partially valid batches;
- forcing a claim from every analysis unit;
- combining semantically distinct claims because their wording is similar;
- discarding raw output or failed attempts after a successful retry.

## 4. Requirements

1. A generic model-task port accepts a finalized task specification and context manifest.
2. Every invocation creates a unique `ModelRun` with deterministic task fingerprint and separately hashed output.
3. Model identity includes weights/file digest where available, runtime, tokenizer, prompt, schema, generation parameters, and hardware-sensitive determinism settings.
4. Raw response is archived before semantic parsing when a response exists.
5. Output is parsed against a strict, versioned schema with no extra fields.
6. Validation verifies all local references, manifest node references, evidence quotes, enum values, and task-specific constraints.
7. A failed output invalidates the whole task attempt; no partial record reaches proposal construction.
8. Retries create new runs and preserve prior runs, errors, and outputs.
9. Model-local labels are scoped to one run and mapped to application-owned candidate IDs.
10. Candidate claims must be atomic, standalone enough for review, attributed, temporally scoped where expressed, and explicit about modality/negation.
11. Evidence grounding is a separate task or deterministic validation stage and must complete before proposal construction.
12. Consolidation classifies relationships among bounded candidates without deleting originals.
13. Abstention and “no candidate” are valid typed outputs distinct from model failure.
14. The application constructs canonical domain records and `ProposedChange` objects deterministically from validated candidates.

## 5. Invariants

- One `ModelRun` references exactly one context manifest and one task/schema version.
- The task fingerprint commits to all deterministic inputs but is not the unique run ID.
- Distinct nondeterministic outputs from the same task fingerprint remain distinct runs.
- Every candidate field produced by a model traces to a run and raw response.
- Every cited node was visible in that run's manifest.
- No candidate claim becomes reviewable without replayable direct evidence.
- Model abstention creates coverage, not a fabricated empty proposal.
- Canonical IDs and proposal hashes are stable functions of validated application data, not model labels.
- Consolidation never mutates or erases its input candidates.

## 6. Proposed task pipeline

```text
AnalysisUnit + ContextManifest
        │
        ├── mention_extraction
        ├── reference_resolution
        ├── claim_extraction
        ├── evidence_grounding
        ├── within_document_consolidation
        └── canonical_proposal_mapping (deterministic application code)
```

Task types may be skipped when deterministic data already supplies the needed result, but the reason is recorded.

## 7. Data model and interfaces

```yaml
ExtractionTask:
  extraction_task_id:
  task_type:
  context_manifest_id:
  input_candidate_ids:
  prompt_id:
  schema_id:
  model_profile_id:
  task_fingerprint:

ModelRun:
  model_run_id:
  extraction_task_id:
  task_fingerprint:
  model_identity:
  runtime_identity:
  tokenizer_id:
  prompt_digest:
  schema_digest:
  generation_parameters:
  raw_output_artifact_id:
  output_digest:
  status: succeeded | abstained | invalid_output | runtime_failed | cancelled
  error_code:
  started_at:
  completed_at:

CandidateClaim:
  candidate_claim_id:
  originating_run_id:
  subject_reference:
  predicate:
  object_or_value:
  qualifiers:
  attribution:
  modality:
  negation:
  valid_time:
  reported_time:
  candidate_evidence_refs:

CandidateRelationship:
  left_candidate_id:
  right_candidate_id:
  classification: equivalent | compatible_distinct | contradicts | refines | unrelated | unresolved
  rationale_evidence_refs:
  originating_run_id:
```

Required port:

```python
run_model_task(task: ModelTaskRequest) -> ModelTaskResponse
```

The response contains model-local data only. Application use cases own archive, validation, candidate IDs, and proposal construction.

## 8. Task-specific behavior

### Mention extraction

Returns source-surface spans and coarse types. It does not resolve global canonical entities.

### Reference resolution

Links pronouns, roles, acronyms, and abbreviations only among visible candidate mentions/nodes. Ambiguous links remain unresolved with ranked alternatives when schema permits.

### Claim extraction

Selects claim-bearing content, disambiguates it using manifest context, and decomposes it into atomic candidates. Attribution, negation, modality, units, conditions, and time are not discarded.

### Evidence grounding

Returns exact source-node/span candidates for each claim. Deterministic evidence validation may reject them. A claim with no sufficient direct support is withheld from proposal construction.

### Consolidation

Operates on a bounded candidate set, such as one section or one source document. It records equivalence or contradiction judgments but keeps original claims and provenance.

## 9. Error and retry behavior

- Runtime crash/timeout: archive available diagnostics, mark run failed, create no candidates.
- Invalid JSON/schema: preserve raw output, mark invalid, create no candidates.
- Unknown local reference: fail validation for the run.
- Out-of-manifest node reference: fail validation as a grounding violation.
- Unsupported candidate: record rejected grounding; do not “repair” with model prose.
- Cancellation: produce a terminal cancelled attempt and no partial batch.
- Retry: create a new run; reuse the same manifest only if all pinned inputs remain valid.

## 10. Compatibility and delivery

- The staged task port replaces the superseded whole-document proposal contract.
- No whole-document proposal adapter remains in the production path.
- Fixtures recreate extraction behavior through staged tasks.
- Deterministic fake runtimes implement each task schema for tests.
- Local production runtimes use the same port and may vary model size without changing domain contracts.

## 11. Completion gates

### Correctness criteria

- Two runs with the same task fingerprint but different raw outputs receive distinct run IDs and retain both outputs.
- Malformed schema, unknown local IDs, out-of-manifest citations, unsupported evidence, and partial batches create no `ProposedChange` records.
- Canonical candidate/proposal IDs remain stable when model-local labels are renamed but validated semantics and evidence are unchanged.
- Every proposed claim has a successful extraction lineage and validated direct evidence target.
- Gold examples preserve attribution, negation, modality, quantities/units, and temporal qualifiers.
- Abstention is distinguishable from no-claim, invalid output, and runtime failure.
- Consolidation preserves contradictory and unresolved candidates rather than selecting one silently.

### Success criteria

- Long-document gold cases complete through bounded manifests and staged runs.
- A reviewer can navigate from a proposal through candidate stages, every model run, exact input manifest, raw output, and evidence.
- Injected failures at each task stage do not leak partial records downstream.
- Replaying deterministic fake runtimes yields byte-stable candidate/proposal output.
- Model quality meets the extraction and grounding thresholds in the evaluation TDD.

### Failure criteria

This deliverable is incomplete if:

- one model call still owns extraction, IDs, evidence, and proposal creation end to end;
- invalid output is partially salvaged into reviewable records;
- model-local identifiers enter canonical ledger identity;
- retries overwrite failed attempts;
- claims without direct support enter review as ordinary grounded proposals;
- abstention is reported as success with no coverage detail;
- source references not visible to the model can pass validation.

## 12. R1-D bounded PDF proof

The R1-D fixture uses the press-release priority paragraph as one `claim_extraction` task.

The fixture passes a ready `ContextManifest` to a deterministic task runtime.

The runtime returns model-local Organization, EvidenceTarget, and Assertion labels.

Application code archives the raw JSON before parsing it.

Application code records an immutable `ExtractionTask` and `ModelRun`.

Application code rejects candidates that cite nodes outside the manifest.

Application code maps valid local labels to canonical IDs and pending `ProposedChange` records.

The proof verifies that renamed local labels produce identical canonical IDs.

## 13. References

- Claimify staged claim extraction: https://aclanthology.org/2025.acl-long.348/
- KoteKomi application ports, proposal use case, and testing guidance

## 14. Halt conditions

Stop and revise when a task cannot be independently validated, when the runtime cannot preserve exact raw output and model identity, or when a required claim type cannot be represented without conflating source report and world-state assertion.
