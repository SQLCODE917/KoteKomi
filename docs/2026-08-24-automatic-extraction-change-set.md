# CIR-2: Automatic Extraction and Change Set

The [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
replaces this TDD's paragraph-hypothesis path inside `kotekomi ingest`.

Existing CIR-2 Ledger records remain read-only historical evidence.

- Status: Accepted
- Program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Deliverable ID: CIR-2
- Depends on: [CIR-1 User Ingestion Run MVP](2026-08-24-user-ingestion-run-mvp.md)

## 1. Context & Problem

CIR-1 archives a deposited file and records a captured IngestionRun.

The user cannot yet see a complete, reviewable set of proposed knowledge from that file.

An **IngestionChangeSet** is an immutable closed set of pending ProposedChanges selected by one AnalysisRun with complete coverage for one IngestionRun.

An **automatic extraction policy** is the named policy that selects document nodes, context limits, the staged claim schema, and model execution settings.

An **EvidenceCandidate** is one model-selectable, whole-node projection of authoritative source text in a ready ContextManifest.

The candidate is derived state and records its stable local identifier, DocumentNode, TextView, exact character range, and source regions.

### Primary end-to-end flow

1. The user runs `kotekomi ingest <path> --url <URL>`.
2. The Pipeline archives and represents the deposited file through the CIR-1 path.
3. The Application Layer freezes every paragraph and table-caption analysis unit.
4. The ContextPlanner renders each focus node with an `evidence_candidate` identifier and persists the complete candidate catalogue in the ContextManifest.
5. The Application Layer runs bounded claim extraction for every required unit.
6. The Application Layer resolves every selected candidate identifier into an exact authoritative EvidenceTarget.
7. The Application Layer reconciles coverage and closes one IngestionChangeSet.
8. The Pipeline records `[CAPTURED]` and prints the extraction summary.

## 2. Goals

- The user receives a complete proposed knowledge set without internal identifiers.
- Every ProposedChange retains model, context, and EvidenceTarget lineage.
- The model interprets source text but never authors source identifiers, quotations, offsets, or regions.
- A valid no-claim result remains distinguishable from a failed model task.
- KoteKomi preserves captured source records when automatic extraction fails.
- Repeated identical ingestion reuses complete pinned analysis without duplicate pending knowledge.

## 3. Requirements

### User CLI Pipeline

- C2-CLI-01: `kotekomi ingest` runs automatic extraction after accepted source capture.
- C2-CLI-02: The command prints the CIR-1 result row followed by one extraction summary on success.
- C2-CLI-03: The summary reports proposed-change count and required-unit completion count.
- C2-CLI-04: Default output contains no canonical Domain ID.
- C2-CLI-05: A model failure writes one safe error and returns exit code `1`.

### Automatic extraction

- C2-EXT-01: Superseded by [CIR-2.1](2026-08-25-cir-2-1-typed-assertion-object-mvp.md),
  which defines the current pinned automatic-extraction prompt and schema contract.
- C2-EXT-02: The policy plans every paragraph, table-caption, and list-item node.
- C2-EXT-03: The policy groups at most four focus nodes in one AnalysisUnit.
- C2-EXT-04: Every required unit uses the existing ContextPlanner and staged claim schema.
- C2-EXT-05: The Application Layer records one ModelRun attempt for each executed unit.
- C2-EXT-06: The Application Layer closes a set only after complete, unblocked required coverage.
- C2-EXT-07: An abstention, no-proposal result, or representation with no policy-selected nodes counts as completed coverage.
- C2-EXT-08: A runtime failure, invalid output, or required context block prevents set closure.
- C2-EXT-09: A ready `focus_node_evidence_v1` ContextManifest contains exactly one `evidence_01`, `evidence_02`, and so on EvidenceCandidate for each selected focus node in rendered order.
- C2-EXT-10: The rendered model input labels every EvidenceCandidate, omits authoritative DocumentNode IDs, and does not require the model to return a DocumentNode ID, source quotation, character offset, TextView ID, or region ID.
- C2-EXT-11: The model selects an EvidenceCandidate only by its local identifier, and the Application Layer derives the resulting whole-node EvidenceTarget from the persisted candidate catalogue.
- C2-EXT-12: An unknown, duplicate, absent, or malformed EvidenceCandidate selection becomes `INVALID_OUTPUT` after raw-output archival and produces no ProposedChange.
- C2-EXT-13: The Application Layer assigns deterministic assertion local identifiers in model-output order; the model does not author an assertion identifier that has no task-local reference use.

### IngestionChangeSet

- C2-SET-01: The Domain Core defines immutable IngestionChangeSet records.
- C2-SET-02: A set names its IngestionRun, selected AnalysisRun, representation, coverage report digest, and ordered distinct ProposedChange IDs.
- C2-SET-03: A set records `executed` or `reused` analysis origin.
- C2-SET-04: The SQLite Adapter validates every referenced record before it stores a set.
- C2-SET-05: The Adapter stores set closure atomically with captured IngestionRun completion.
- C2-SET-06: A set contains no accepted Assertion or Relationship.

### Runtime configuration

- C2-RUN-01: The default named runtime profile is `lm-studio`.
- C2-RUN-02: The default profile uses `http://127.0.0.1:1234/v1`, `qwen2.5-14b-instruct`, a 16,384-token context, and a 2,048-token output cap.
- C2-RUN-03: `kotekomi init` writes the active LM Studio profile and commented llama-server and Ollama alternatives.
- C2-RUN-04: The LM Studio Adapter validates `/v1/models` and runs one strict `/v1/responses` task.
- C2-RUN-05: The Adapter rejects malformed, mismatched-model, and incomplete responses.
- C2-RUN-06: A model task timeout is a total wall-clock deadline. Streaming activity cannot extend it; expired tasks discard partial output and become `RUNTIME_FAILED` without an implicit retry.
- C2-RUN-07: The Application Layer records its measured elapsed duration and configured deadline on every ModelRun; the LM Studio Adapter records first SSE response-event latency when available.
- C2-RUN-08: `kotekomi model runs --format json` exposes safe, read-only execution diagnostics without prompts, raw output, or source text.

## 4. Proposed Architecture

```text
User CLI
  |
  v
Ingestion orchestration use case
  |                    |
  v                    v
Source capture      AnalysisRun and coverage
  |                    |
  v                    v
Archive + Ledger <- ContextManifest EvidenceCandidates <- LM Studio ModelTaskRuntime
                         |
                         v
                  IngestionChangeSet
```

The Pipeline composes the User CLI.

The Application Layer owns planning, extraction completion, reuse selection, and set closure.

The LM Studio Adapter translates HTTP responses into the ModelTaskRuntime Port.

The SQLite Adapter stores records and validates cross-record references.

## 5. Key Interactions

```text
User -> Pipeline: ingest path and URL
Pipeline -> Source capture: archive and represent
Pipeline -> Extraction use case: analyze representation
Extraction use case -> Model runtime: bounded staged task
Extraction use case -> Ledger: coverage and pending ProposedChanges
Extraction use case -> Ledger: close IngestionChangeSet
Pipeline -> IngestionRun use case: complete as captured
Pipeline -> User: result row and summary
```

## 6. Data Model

```text
IngestionChangeSet
    id
    ingestion_run_id
    analysis_run_id
    representation_id
    coverage_report_digest
    proposed_change_ids
    analysis_origin
    closed_at
    change_set_digest
```

```text
EvidenceCandidate
    id
    node_id
    text_view_id
    start_char
    end_char
    source_region_ids
```

EvidenceCandidates are persisted inside the immutable ContextManifest integrity payload.

`focus_node_evidence_v1` creates candidates only for selected focus nodes.

The candidate identifiers are local to one ContextManifest and are ordered as `evidence_01`, `evidence_02`, and so on.

The Application Layer derives the digest from every stored field except the record ID and closure timestamp.

The set can contain zero ProposedChange IDs.

An IngestionRun completed by CIR-2 records its AnalysisRun and IngestionChangeSet internally.

## 7. APIs / Interfaces

The existing ingest command remains:

```text
kotekomi ingest <path> --url <SOURCE_URL>
```

The diagnostic command is:

```text
kotekomi model runs --format json
```

It reports ModelRun identity, terminal status, application-measured elapsed time,
configured deadline, optional first-response-event latency, and token counts. It
does not expose prompt content, raw model output, or extracted source text.

A successful CIR-2 command prints:

```text
<display_filename>\t[CAPTURED]\t<UTC_YYYY-MM-DDTHH:MM>
Extraction: <proposal_count> proposed changes; <complete_units>/<required_units> units complete
```

The Application Layer exposes explicit inputs and results for automatic extraction and set closure.

The ModelTaskRuntime Port remains the only model boundary.

## 8. Behavior & Domain Rules

The Pipeline keeps an IngestionRun running until source capture and automatic extraction reach a terminal result.

The Pipeline records an error after successful capture when model work cannot complete.

The error preserves Source, Document, representation, and model lineage already stored.

The Pipeline closes an empty set after complete no-proposal or abstained coverage.

The Application Layer reuses analysis only when the representation, plan, prompt, schema, validator, and execution specification match exactly. AnalysisRun scope records are immutable; complete coverage is attested by the coverage report digest sealed into the change set rather than by mutating the published run record.

The extraction schema contains `evidence_candidate_id` instead of model-authored source selectors.

The Application Layer validates the identifier against the exact persisted ContextManifest catalogue and derives its EvidenceTarget from authoritative source state.

The model does not provide text, offsets, node IDs, TextView IDs, or region IDs for accepted evidence.

The reused set records the prior AnalysisRun and `reused` origin.

The Application Layer creates no CandidateKnowledgeView in CIR-2.

## 9. Acceptance Criteria

- AC-C2-01: Domain tests reject duplicate IDs, missing references, mutable digests, and invalid origins.
- AC-C2-02: Application tests prove full-scope successful extraction closes one set.
- AC-C2-03: Application tests prove valid abstention and no-proposal results close an empty set.
- AC-C2-04: Application tests prove failed or blocked required work closes no set and ends the run as error.
- AC-C2-05: Application tests prove identical completed analysis is reused without a second model call.
- AC-C2-06: SQLite tests prove restart-safe record persistence and atomic closure.
- AC-C2-07: Adapter tests prove strict LM Studio request and response behavior.
- AC-C2-07A: Adapter and Application tests prove a streaming task cannot extend its wall-clock deadline and produces no partial ProposedChange on expiry.
- AC-C2-07B: Domain, Application, Adapter, and CLI tests prove every ModelRun persists application-owned timing diagnostics and exposes only safe fields through `kotekomi model runs`.
- AC-C2-07C: Application tests prove that a selected EvidenceCandidate produces a whole-node authoritative EvidenceTarget without model-authored text or source coordinates.
- AC-C2-07D: Application tests prove that an unknown, duplicate, or injected source selector is archived as invalid output without a ProposalChange.
- AC-C2-08: CLI tests prove default configuration, safe failures, result summaries, and identifier-free output.
- AC-C2-09: The local Anthropic--DoD PDF ingestion proves complete coverage, source-grounded pending proposals, and no accepted intelligence writes.

## 10. Reference Implementations

- Bounded extraction: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Coverage reconciliation: `packages/application/src/kotekomi_application/analysis_coverage.py`.
- Ingestion history: `packages/application/src/kotekomi_application/ingestion_runs.py`.
- LM Studio HTTP validation: `packages/adapters/src/kotekomi_adapters/lm_studio_embeddings.py`.
- Model-run diagnostics: `packages/application/src/kotekomi_application/model_run_logging.py`.
