# DR-3 Exact-Lexical Diagnostic CLI

## Context & Problem

DR-3 retains exact and lexical retrieval as a diagnostic channel.
The Pipeline implements the exact-lexical branch.
The public CLI accepts only `semantic` as a channel value.
The source-ingest PDF fixture cannot select its intended diagnostic channel.

**Terms**

- **Diagnostic channel** means `exact-lexical`.
- **Normal command** means a retrieval command without `--channel`.

Primary end-to-end flow:

1. An operator supplies `--channel exact-lexical` to a document build or query command.
2. The CLI validates the diagnostic channel value.
3. The Pipeline calls its existing exact and lexical branch.
4. The Pipeline returns authoritative retrieval output without an embedding request.

## Goals

- Operators can select the retained exact and lexical diagnostic channel.
- The source-ingest fixture validates its stated retrieval scope without an embedding service.
- Unqualified DR-3 commands retain hybrid retrieval behavior.

## Requirements

### CLI

- CLI-01: `retrieval build-document --channel exact-lexical` is valid.
- CLI-02: `retrieval query --channel exact-lexical` is valid.
- CLI-03: The CLI rejects `--embedding-profile` unless the channel is `semantic`.

### Pipeline

- PL-01: The diagnostic channel builds exact and lexical derived projections.
- PL-02: The diagnostic channel queries exact and lexical derived projections.
- PL-03: The diagnostic channel does not request an embedding.
- PL-04: A normal command retains the configured hybrid profile requirement.

### Source-ingest fixture test

- SIF-01: The source-ingest fixture test uses the diagnostic channel for build and query.
- SIF-02: The fixture test keeps its processing-only configuration.

## Proposed Architecture

The CLI validates channel selection.
The existing Pipeline branch owns diagnostic retrieval behavior.

```text
operator or fixture test
          |
          v
Pipeline CLI --channel exact-lexical
          |
          v
existing exact and lexical branch
```

## Key Interactions

```text
operator -> Pipeline CLI: retrieval command with exact-lexical
Pipeline CLI -> exact and lexical branch: diagnostic command
exact and lexical branch -> operator: authoritative retrieval output
```

## Data Model

This TDD creates no Domain Core record or schema.
The existing exact and lexical projections remain derived state.

## APIs / Interfaces

The CLI adds `exact-lexical` to the accepted `--channel` values.
The CLI keeps `semantic` as the only channel that accepts `--embedding-profile`.

## Behavior & Domain Rules

The diagnostic channel does not require an embedding profile.
The normal command requires its configured semantic embedding profile.
The Pipeline does not change exact guard, lexical ranking, or hybrid fusion behavior.

## Acceptance Criteria

- AC-CLI-01: Pipeline tests prove build and query accept the diagnostic channel.
- AC-CLI-02: Pipeline tests prove the diagnostic channel passes no embedding profile.
- AC-CLI-03: Pipeline tests prove an embedding profile with the diagnostic channel fails.
- AC-PL-01: The source-ingest PDF fixture test passes with the diagnostic channel.
- AC-PL-02: Existing DR-3 normal-profile tests pass.
- AC-PL-03: Repository formatting, lint, type, and test checks pass.

## Reference Implementations

- CLI dispatch: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Normal profile tests: `packages/pipelines/tests/test_document_retrieval.py`.
- Source-ingest fixture: `packages/pipelines/tests/test_source_add_file.py`.

## Constraints and Halt Conditions

The implementation stops if it changes the normal hybrid command behavior.
The implementation stops if it changes exact guard, lexical ranking, or hybrid fusion behavior.
The implementation stops if it adds an embedding profile to the source-ingest fixture.
