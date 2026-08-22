# DR-3 Integrated Recovery Successor

## Context & Problem

DR-3 normal retrieval requires a configured hybrid embedding profile.
The source-ingest fixture uses a retrieval build as a processing-only check.
The historical DR-3 diagnostic CLI patch selects the exact-lexical channel for that fixture.
The historical hybrid patch cannot pass repository CI without the diagnostic CLI patch.
This TDD delivers both completed patches through one feature branch.

**Glossary**

- The **hybrid patch** has stable patch ID `8bcd4f449a707dac86725bc69d3b04d9dc156f83`.
- The **diagnostic patch** has stable patch ID `0f9c1d95e053fedeb0a68b9b49adf9b9b4cd141e`.
- The **integrated patch** is the ordered combination of the hybrid patch and diagnostic patch.

### Primary end-to-end flow

1. An operator starts this task from clean current `main`.
2. The task applies the hybrid patch and then the diagnostic patch.
3. The Harness verifies the candidate and records candidate CI.
4. The Harness promotes the verified feature branch after candidate CI succeeds.
5. The Harness records main CI and deletes the feature branch after main CI succeeds.
6. The Harness records the two historic DR-3 branch-bearing tasks as superseded evidence.

## Goals

- Normal document retrieval provides exact, lexical, and semantic results.
- The processing-only source-ingest fixture uses exact-lexical retrieval.
- Repository CI passes for the combined DR-3 behavior.
- Historic DR-3 work remains reviewable after normal closeout.

## Requirements

### Delivery

- DL-01: The candidate contains the hybrid patch before the diagnostic patch.
- DL-02: The candidate preserves both stable patch IDs from the glossary.
- DL-03: The candidate changes only paths listed in this task manifest.
- DL-04: The candidate does not add DR-4 behavior.

### Retrieval

- RT-01: The candidate implements the accepted DR-3 hybrid policy.
- RT-02: A unique exact result consults only the exact channel.
- RT-03: A non-unique exact result and a paraphrase consult exact, lexical, and semantic channels.
- RT-04: ContextPlanner receives only selected authoritative DocumentNode IDs.

### Diagnostic command

- DC-01: The CLI accepts `--channel exact-lexical` for document build and query commands.
- DC-02: The exact-lexical command does not require an embedding profile.
- DC-03: The source-ingest fixture uses the exact-lexical command.
- DC-04: An unqualified document command retains hybrid behavior.

### Closeout

- CO-01: Candidate CI succeeds before promotion.
- CO-02: Main CI succeeds before feature-branch cleanup.
- CO-03: The Harness records the original DR-3 task and prior DR-3 successor as superseded.

## Proposed Architecture

The Pipeline selects normal or diagnostic retrieval behavior.
The Application Layer owns hybrid selection.
The SQLite Adapter reads derived indexes.
ContextPlanner creates the ContextManifest.

```text
operator -> Pipeline -> Application Layer -> SQLite Adapter
                         |                    |
                         v                    v
                    ContextPlanner       derived indexes
                         |
                         v
                   ContextManifest
```

## Key Interactions

```text
operator -> Pipeline: normal document query
Pipeline -> Application Layer: hybrid query
Application Layer -> SQLite Adapter: channel candidates
Application Layer -> ContextPlanner: DocumentNode IDs
ContextPlanner -> Pipeline: ContextManifest
```

```text
fixture -> Pipeline: exact-lexical build
Pipeline -> exact-lexical branch: diagnostic command
exact-lexical branch -> fixture: derived index result
```

## Data Model

The task preserves the accepted DR-3 retrieval records.
The diagnostic command creates no new Domain Core record.

## APIs / Interfaces

The normal retrieval commands use the hybrid policy.
The diagnostic retrieval commands accept `exact-lexical`.
The semantic diagnostic command continues to require an embedding profile.

## Behavior & Domain Rules

The task blocks when either stable patch differs from its glossary identity.
The task blocks when the locked PDF or the pinned semantic profile is unavailable.
The normal command requires its configured hybrid profile.
The exact-lexical command does not request embeddings.

## Acceptance Criteria

- AC-DL-01: Git verification proves the candidate preserves both stable patches in order.
- AC-RT-01: Domain, Application, Adapter, Pipeline, and scenario tests prove DR-3 behavior.
- AC-DC-01: Pipeline tests prove diagnostic channel routing and source-ingest fixture behavior.
- AC-RT-02: The locked PDF passes `test-ingest` and `test-query --suite dr-3-v1`.
- AC-RT-03: The canonical rebuild check preserves hybrid candidate order, selected nodes, and ContextManifest identities.
- AC-CO-01: Harness evidence proves candidate CI, main CI, task result, and cleanup completed.
- AC-CO-02: Harness evidence proves the two historic DR-3 tasks are superseded.

## Reference Implementations

- Hybrid policy: `packages/application/src/kotekomi_application/document_retrieval.py`.
- CLI routing: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Scenario runner: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.

## Constraints and Halt Conditions

The task stops if it changes accepted DR-3 behavior beyond the two historical patches.
The task stops if it changes the locked canonical PDF.
