# TDD: Hybrid Document Orchestration

- Status: Implemented and verified
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Deliverable ID: HP-8
- Depends on: [HP-7 ProposedChange Integration](2026-09-03-hybrid-proposed-change-integration.md)
- Replaces: the CIR-2 paragraph-hypothesis path inside `kotekomi ingest`
- Evaluation: [HP-8 Document Orchestration Evaluation](2026-09-03-hp8-document-orchestration-evaluation.md)

## Context & Problem

HP-1 through HP-7 transform one authoritative paragraph into pending ProposedChanges.

Each stage retains exact inputs, outputs, lineage, and terminal diagnostics.

The public ingestion command still runs the superseded CIR-2 paragraph-hypothesis path.

A user cannot run the Hybrid Pipeline over one complete ingested document.

A long document run also needs durable paragraph checkpoints and explicit coverage.

**Hybrid Pipeline Policy** means the pinned HP-1 through HP-7 configuration for one representation.

**Paragraph Work** means one planned paragraph and its Hybrid Pipeline Policy fingerprint.

**Paragraph Receipt** means one immutable terminal record for one Paragraph Work item.

**Document Coverage Report** means one immutable reconciliation of all planned Paragraph Receipts.

**Accounted gap** means a persisted non-complete stage result or terminal stop. A later stage may
still produce a safe usable subset, including an HP-7 proposal plan, while the Paragraph Receipt
retains the earlier gap.

### Primary end-to-end flow

1. A user deposits one supported file with `kotekomi ingest`.
2. The Pipeline captures one authoritative DocumentRepresentationBundle.
3. The Application Layer plans every paragraph in reading order under one Hybrid Pipeline Policy.
4. The Application Layer reuses or runs HP-1 through HP-7 for each paragraph.
5. The Application Layer reconciles every Paragraph Receipt into one Document Coverage Report.
6. HP-9 reconciles document-local Actor and Organization candidates.
7. One Ledger transaction publishes the reconciled proposals and closes the IngestionChangeSet.

## Goals

- One ingestion produces one reviewable IngestionChangeSet for the complete paragraph scope.
- A retry reuses completed Paragraph Receipts without rerunning models.
- The user sees bounded progress and one terminal extraction summary.
- The user can inspect exact HP-1 through HP-7 inputs and outputs for every paragraph.
- A terminal model or specialized-model gap remains visible without corrupting wiki state.

## Requirements

### Document scope

- HDO-SCP-01: The Application Layer selects every paragraph DocumentNode.
- HDO-SCP-02: The Application Layer orders Paragraph Work by node order and node ID.
- HDO-SCP-03: The Application Layer excludes every non-paragraph DocumentNode.
- HDO-SCP-04: The Hybrid Pipeline Policy records selected and excluded node counts.
- HDO-SCP-05: The Application Layer freezes the complete AnalysisPlan before model work.
- HDO-SCP-06: The Hybrid Pipeline Policy pins the representation and AnalysisPlan identities.

### Policy identity

- HDO-POL-01: The Hybrid Pipeline Policy pins every prompt digest.
- HDO-POL-02: The Hybrid Pipeline Policy pins every model-output schema digest.
- HDO-POL-03: The Hybrid Pipeline Policy pins the model identity and generation settings.
- HDO-POL-04: The Hybrid Pipeline Policy pins the GLiNER identity and configuration.
- HDO-POL-05: The Hybrid Pipeline Policy pins the ReFinED identity and configuration.
- HDO-POL-06: The Hybrid Pipeline Policy pins the ontology profile identity and digest.
- HDO-POL-07: KoteKomi derives each Paragraph Work fingerprint from the policy and source node.
- HDO-POL-08: A changed pinned input creates different Paragraph Work.

### Paragraph execution

- HDO-EXE-01: The Application Layer validates a reusable Paragraph Receipt before adapter startup.
- HDO-EXE-02: A valid reusable Paragraph Receipt prevents every model call for its paragraph.
- HDO-EXE-03: A missing Paragraph Receipt starts the paragraph at HP-1.
- HDO-EXE-04: A complete or partial HP-1 Preview advances to HP-2.
- HDO-EXE-05: A blocked HP-1 Preview creates an accounted gap and stops that paragraph.
- HDO-EXE-06: HP-2 runs deterministically from the HP-1 Preview.
- HDO-EXE-07: HP-3 records ReFinED output or one explicit ReFinED gap.
- HDO-EXE-08: An HP-3 gap remains advisory when HP-4 can continue.
- HDO-EXE-09: HP-4 through HP-6 preserve their existing terminal contracts.
- HDO-EXE-10: A replayable HP-6 Preview advances to one immutable HP-7 Plan.
- HDO-EXE-11: Paragraph execution does not publish ProposedChanges.
- HDO-EXE-12: The Pipeline initializes each required Adapter only after the first cache miss.

### Paragraph checkpoints

- HDO-CHK-01: The Archive stores one Paragraph Receipt at a content-derived path.
- HDO-CHK-02: The Paragraph Receipt identifies all seven stage dispositions in stage order.
- HDO-CHK-03: Each stage disposition is `created`, `reused`, or `not_run`.
- HDO-CHK-04: Each executed stage records its output identity, digest, and terminal status.
- HDO-CHK-05: Each `not_run` stage records the prior terminal reason.
- HDO-CHK-06: The Paragraph Receipt records all HP-7 ProposedChange IDs.
- HDO-CHK-07: Receipt reload replays canonical stage bytes and authoritative source bindings.
- HDO-CHK-08: Missing, corrupt, stale, or conflicting receipt evidence stops closure.
- HDO-CHK-09: The Archive reuses byte-identical Paragraph Receipts.

### Coverage and closure

- HDO-COV-01: The Application Layer requires one Paragraph Receipt per Paragraph Work item.
- HDO-COV-02: The Document Coverage Report records complete and gap paragraph counts.
- HDO-COV-03: A persisted terminal gap counts as accounted coverage.
- HDO-COV-04: Missing or invalid evidence counts as unaccounted coverage.
- HDO-COV-05: Unaccounted coverage prevents an IngestionChangeSet.
- HDO-COV-06: Zero selected paragraphs produces complete empty coverage.
- HDO-COV-07: Complete coverage yields AnalysisRun state `complete`.
- HDO-COV-08: Accounted gaps yield AnalysisRun state `complete_with_gaps`.
- HDO-COV-09: The Archive stores the canonical Document Coverage Report.
- HDO-COV-10: The Document Coverage Report pins every Paragraph Receipt digest.
- HDO-COV-11: The IngestionChangeSet pins the Document Coverage Report digest.
- HDO-COV-12: The IngestionChangeSet contains only ProposedChange IDs from the HP-9 Document Proposal Plan.
- HDO-COV-13: One Ledger transaction stores the AnalysisRun scope and pending proposals.
- HDO-COV-14: The same transaction stores the IngestionChangeSet and completes the IngestionRun.
- HDO-COV-15: A closure failure rolls back all new records from HDO-COV-13 and HDO-COV-14.
- HDO-COV-16: A retry preserves every existing ProposedChange review status.
- HDO-COV-17: A fully reused document records IngestionChangeSet origin `reused`.

### Public operation

- HDO-CLI-01: `kotekomi ingest` runs HP-8 after authoritative capture.
- HDO-CLI-02: `kotekomi ingest` no longer runs the CIR-2 paragraph-hypothesis policy.
- HDO-CLI-03: Text output reports paragraph progress without canonical record IDs.
- HDO-CLI-04: Text output reports proposal, complete paragraph, and gap paragraph counts.
- HDO-CLI-05: A closed run with accounted gaps exits zero.
- HDO-CLI-06: Missing evidence or an unhandled failure exits one with a safe message.

## Proposed Architecture

```text
User CLI -> Ingestion Pipeline -> HP-1..HP-7 use cases
                 |                      |
                 v                      v
            Application Layer <---- Archive checkpoints
                 |
                 v
          one Ledger transaction
```

The Pipeline owns configuration, progress output, and Adapter lifetime.

The Application Layer owns scope, replay, progression, coverage, and closure decisions.

The existing HP-1 through HP-7 use cases own their bounded stage decisions.

The Local Archive Adapter stores immutable policy, receipt, and report bytes.

The SQLite Adapter persists the existing AnalysisRun, ProposedChange, and IngestionChangeSet records.

## Key Interactions

```text
User   Pipeline   Application   Models   Archive   Ledger
 | ingest  |           |          |         |        |
 |-------->| capture authoritative Source ---------->|
 |         |---------->| plan     |         |------->|
 |         |---------->| receipt? |<--------|        |
 |         |           | run stages-------->|        |
 |         |           |---------->|         |------>|
 |         |           | checkpoint--------->|        |
 |         |---------->| reconcile|         |        |
 |         |           | close transaction---------->|
 |<--------| progress and summary |         |        |
```

## Data Model

`HybridPipelinePolicyManifest` is an immutable Application Layer DTO in the Archive.

`HybridParagraphStageRecord` is one stage disposition inside a Paragraph Receipt.

`HybridParagraphReceipt` is an immutable Application Layer DTO in the Archive.

`HybridDocumentCoverageRecord` reconciles one Paragraph Work item with one Paragraph Receipt.

`HybridDocumentCoverageReport` is an immutable Application Layer DTO in the Archive.

`AnalysisRun` remains the canonical Ledger record for one complete planned scope.

HP-8 adds `complete_with_gaps` to `AnalysisRunState`.

`IngestionChangeSet` remains the canonical closed set of pending ProposedChanges.

HP-8 adds no accepted Actor, Organization, Event, Assertion, or Relationship.

## APIs / Interfaces

The public command remains:

```text
kotekomi ingest <PATH> --url <HTTPS_URL>
```

The Application Layer exposes explicit planning, paragraph execution, replay, coverage, and closure results.

The Archive Port reads and writes policy manifests, Paragraph Receipts, and Document Coverage Reports.

The Ledger Port atomically closes one HP-8 document run.

## Behavior & Domain Rules

The Pipeline runs Paragraph Work sequentially in reading order.

One paragraph failure cannot remove a prior Paragraph Receipt.

One model failure becomes a typed stage result under existing HP stage rules.

An unexpected exception leaves the IngestionRun in an error state and retains completed receipts.

The next ingestion of identical bytes and policy reuses those receipts.

HP-8 does not change prompts, model schemas, ontology semantics, or HP-7 admission.

Reviewer approval remains the only path from ProposedChange to accepted intelligence.

HP-8 submits paragraph HP-7 Plans only through the HP-9 reconciliation contract.

Historical CIR-2 records remain readable Ledger history.

## Acceptance Criteria

- AC-HDO-01: Application tests prove exact paragraph scope and ordering.
- AC-HDO-02: Contract tests prove each pinned policy input changes the work fingerprint.
- AC-HDO-03: Application tests prove the complete HP stage progression matrix.
- AC-HDO-04: Archive tests prove immutable storage, replay, reuse, and corruption rejection.
- AC-HDO-05: Application tests prove complete, gap, missing, and empty coverage.
- AC-HDO-06: Adapter tests prove atomic closure rollback and review-status preservation.
- AC-HDO-07: Pipeline tests prove lazy Adapter startup and zero calls on full reuse.
- AC-HDO-08: Pipeline tests prove progress, summaries, safe failures, and CIR-2 removal.
- AC-HDO-09: A two-paragraph fixture proves exact data in and data out for HP-1 through HP-8.
- AC-HDO-10: The canonical PDF run accounts for every authoritative paragraph.
- AC-HDO-11: The canonical PDF run uses configured Qwen2.5, GLiNER, and ReFinED Adapters.
- AC-HDO-12: The canonical report retains the seven reviewed events and known false event lineage.
- AC-HDO-13: The canonical report retains the parent Gold rejection for the known false event and proves current ingestion creates no accepted intelligence.
- AC-HDO-14: A repeated canonical ingest makes zero model and specialized-model calls.
- AC-HDO-15: Formatting, Ruff, Pyright, focused tests, and the full test suite pass.

## Reference Implementations

- Paragraph stages: follow `packages/application/src/kotekomi_application/hybrid_*_preview.py`.
- Proposal planning: follow `packages/application/src/kotekomi_application/hybrid_proposed_changes.py`.
- Immutable files: follow `packages/adapters/src/kotekomi_adapters/local_archive.py`.
- Run scope: follow `packages/application/src/kotekomi_application/analysis_coverage.py`.
- User ingestion: follow `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

Stop if HP-8 requires a new semantic model task.

Stop if HP-8 needs a new accepted intelligence record.

Stop if a terminal gap cannot preserve replayable stage evidence.

Stop if retry requires an unpinned latest-record lookup.
