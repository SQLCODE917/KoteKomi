# DR-3 Combined Recovery Delivery

## Context & Problem

The historic DR-3 hybrid patch and diagnostic patch overlap in CLI option declarations.
The overlap prevents their individual stable patch IDs from surviving one resolved delivery branch.
The resolved combined candidate defines the intended DR-3 delivery tree.
This TDD delivers that candidate through the Harness feature-branch flow.

**Glossary**

- The **combined patch** has stable patch ID `3e630f06b12dfddd5953672e25b9e3300a472159`.
- The **normal command** is a retrieval command without `--channel`.
- The **diagnostic command** is a retrieval command with `--channel exact-lexical`.

### Primary end-to-end flow

1. An operator starts the task from clean current `main`.
2. The task applies the combined patch to its feature branch.
3. The Harness verifies the candidate and records candidate CI.
4. The Harness promotes the verified branch after candidate CI succeeds.
5. The Harness records main CI and completes the task.
6. The Harness records the historic DR-3 branch-bearing tasks as superseded.

## Goals

- A normal retrieval command uses exact, lexical, and semantic channels.
- A diagnostic command uses exact and lexical retrieval without embeddings.
- The source-ingest fixture uses the diagnostic command.
- Repository and canonical DR-3 acceptance pass.

## Requirements

### Delivery

- DL-01: The candidate has the combined patch identity from the glossary.
- DL-02: The candidate changes only paths in the task manifest.
- DL-03: The candidate does not add DR-4 behavior.

### Retrieval

- RT-01: A normal command builds exact, lexical, and semantic derived indexes.
- RT-02: A normal query applies the accepted DR-3 hybrid policy.
- RT-03: A unique exact result consults only the exact channel.
- RT-04: A non-unique exact result and a paraphrase consult all three channels.
- RT-05: ContextPlanner receives only selected authoritative DocumentNode IDs.

### Diagnostic command

- DC-01: The CLI accepts `exact-lexical` for document build and query commands.
- DC-02: The diagnostic command does not request an embedding profile.
- DC-03: The source-ingest fixture invokes the diagnostic command for its retrieval build and query.
- DC-04: The normal command retains hybrid behavior.

### Closeout

- CO-01: Candidate CI succeeds before promotion.
- CO-02: Main CI succeeds before task completion.
- CO-03: The Harness records the original DR-3 task and earlier closeout task as superseded.

## Proposed Architecture

The Pipeline selects normal or diagnostic retrieval.
The Application Layer selects hybrid candidates.
The SQLite Adapter reads derived indexes.
ContextPlanner builds the ContextManifest.

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

## Data Model

The task preserves the accepted DR-3 retrieval records.
The diagnostic command creates no Domain Core record.

## APIs / Interfaces

The normal retrieval commands use the hybrid policy.
The diagnostic retrieval commands accept `exact-lexical`.
The semantic diagnostic command continues to require an embedding profile.

## Behavior & Domain Rules

The task blocks when the candidate patch differs from DL-01.
The task blocks when the locked PDF or pinned semantic profile is unavailable.
The normal command requires its configured embedding profile.
The diagnostic command does not request embeddings.

## Acceptance Criteria

- AC-DL-01: Git verification proves the candidate patch matches DL-01.
- AC-RT-01: Domain, Application, Adapter, Pipeline, and scenario tests prove DR-3 behavior.
- AC-DC-01: Pipeline tests prove diagnostic routing and source-ingest fixture behavior.
- AC-RT-02: The locked PDF passes `test-ingest` and `test-query --suite dr-3-v1`.
- AC-RT-03: The canonical rebuild check preserves candidate order, selected nodes, and ContextManifest identities.
- AC-CO-01: Harness evidence proves candidate CI, main CI, task result, and cleanup.
- AC-CO-02: Harness evidence proves the historic DR-3 tasks are superseded.

## Reference Implementations

- Hybrid policy: `packages/application/src/kotekomi_application/document_retrieval.py`.
- CLI routing: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Scenario runner: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.

## Constraints and Halt Conditions

The task stops if it changes behavior beyond the combined patch.
The task stops if it changes the locked canonical PDF.
