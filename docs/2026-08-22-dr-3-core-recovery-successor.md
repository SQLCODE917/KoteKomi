# DR-3 Core Recovery Successor

## Context & Problem

The accepted DR-3 TDD defines normal hybrid document retrieval.
The original DR-3 candidate contains its completed implementation patch.
The original task cannot reach a normal feature-branch closeout because its historic run is blocked.
The repository now provides superseded-result tags for this recovery case.
This TDD delivers the unchanged DR-3 patch through a new feature branch.
This TDD then records the original blocked task as superseded evidence.

**Glossary**

- A **historical patch** is the non-receipt change from commit `5e63f47` through commit `c50e576`.
- A **successor task** is this task, which delivers the historical patch.
- A **superseded task** is a historic DR-3 task that the successor task replaces.

### Primary end-to-end flow

1. An operator starts this successor task from the current `main` branch.
2. The successor task applies the historical patch without changing its content.
3. The Harness verifies the successor candidate and records candidate CI evidence.
4. The Harness promotes the verified feature branch to `main`.
5. The Harness records successful main CI and deletes the successor feature branch.
6. The Harness records each superseded task as historical evidence after the successor completes.

## Goals

- Normal document retrieval uses exact, lexical, and semantic channels.
- A unique exact result retains precedence over other channels.
- A normal query returns authoritative DocumentNode IDs and a ContextManifest.
- The current `main` branch receives only the historical DR-3 implementation patch.
- Historic DR-3 work remains inspectable after the successor task completes.

## Requirements

### Successor delivery

- SD-01: The successor candidate has stable patch ID `8bcd4f449a707dac86725bc69d3b04d9dc156f83`.
- SD-02: The successor candidate changes only the paths listed in this task manifest.
- SD-03: The successor candidate does not change the accepted DR-3 TDD.
- SD-04: The successor candidate does not add DR-4 behavior.

### Hybrid retrieval

- HR-01: The successor delivers the behavior defined by `docs/2026-08-21-document-hybrid-activation.md`.
- HR-02: The normal build command builds exact, lexical, and semantic derived indexes.
- HR-03: The normal query command uses the DR-3 hybrid policy.
- HR-04: A unique exact result selects only the exact channel.
- HR-05: A non-unique exact result and a paraphrase consult exact, lexical, and semantic channels.
- HR-06: The Application Layer sends only selected authoritative DocumentNode IDs to ContextPlanner.

### Closeout

- CO-01: The Harness records successful candidate CI before it promotes the successor.
- CO-02: The Harness records successful main CI before it completes the successor task.
- CO-03: The Harness deletes the successor feature branch after successful main CI.
- CO-04: The Harness records the original DR-3 task and prior DR-3 successor as superseded after this task completes.
- CO-05: The Harness retains every historic result tag and publishes a superseded-result tag when a historic result tag records `abandoned`.

## Proposed Architecture

The existing Pipeline selects normal hybrid retrieval.
The existing Application Layer applies the exact guard and fusion policy.
The existing SQLite Adapter reads derived retrieval indexes.
The existing ContextPlanner creates the ContextManifest.
The Harness records delivery and historic replacement evidence.

```text
operator -> Pipeline -> Application Layer -> SQLite Adapter
                         |                    |
                         v                    v
                    ContextPlanner       derived indexes
                         |
                         v
                   ContextManifest

Harness -> successor branch -> main -> historic task records
```

## Key Interactions

```text
operator -> Pipeline: normal document query
Pipeline -> Application Layer: hybrid query
Application Layer -> SQLite Adapter: channel candidates
Application Layer -> ContextPlanner: DocumentNode IDs
ContextPlanner -> Pipeline: ContextManifest
Pipeline -> operator: query record
```

```text
operator -> Harness: complete successor task
Harness -> Git: promote verified feature branch
Git -> Harness: successful main CI evidence
Harness -> Git: delete successor branch
Harness -> Harness: publish superseded task evidence
```

## Data Model

The successor preserves the DR-3 RetrievalChannelObservation, RetrievalHit, and RetrievalQueryRecord contracts.
The successor creates no product record beyond those DR-3 contracts.
The Harness writes task result, cleanup, and superseded-result evidence outside the product Ledger.

## APIs / Interfaces

The successor preserves the DR-3 normal retrieval commands.
The successor preserves `--channel exact-lexical` and `--channel semantic` as diagnostic commands.
The Harness uses `close-superseded-task` to record each historic task after this task is complete.

## Behavior & Domain Rules

The successor blocks when its stable patch ID differs from SD-01.
The successor blocks when the locked canonical PDF or `semantic-validation-v1` profile is unavailable.
The successor blocks when candidate verification or main CI fails.
The Harness retains the original `result` tag when that tag records an abandoned result.
The Harness publishes a separate `superseded-result` tag for that historic task.
The Harness does not delete a historic feature branch until its superseded task result is recorded.

## Acceptance Criteria

- AC-SD-01: Git verification proves the successor stable patch ID equals SD-01.
- AC-HR-01: Domain and Application tests prove the exact guard and hybrid fusion behavior.
- AC-HR-02: Adapter tests prove the hybrid policy reads derived indexes.
- AC-HR-03: Pipeline and scenario tests prove normal, exact-lexical, and semantic command routing.
- AC-HR-04: The locked canonical scenario passes `test-ingest` and `test-query --suite dr-3-v1`.
- AC-HR-05: The canonical rebuild check preserves hybrid candidate order, selected node IDs, and ContextManifest identities.
- AC-CO-01: Harness evidence proves candidate CI, main CI, task result, and branch cleanup completed.
- AC-CO-02: Harness evidence proves both historic DR-3 tasks have superseded outcomes.
- AC-CO-03: Formatting, lint, type checks, and required repository tests pass.

## Reference Implementations

- Hybrid policy: `packages/application/src/kotekomi_application/document_retrieval.py`.
- Index queries: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.
- Scenario runner: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.
- Historic task closure: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.

## Constraints and Halt Conditions

The successor stops if it changes the accepted DR-3 behavior.
The successor stops if it needs a new retrieval plane or generated text.
The successor stops if it changes the locked canonical PDF.
