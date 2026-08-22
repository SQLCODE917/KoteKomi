# DR-3 Source-Ingest Diagnostic Channel

## Context & Problem

The DR-3 normal retrieval commands build and query hybrid exact, lexical, and semantic projections.
The normal commands require a configured semantic embedding profile.
The source-ingest PDF fixture test does not define an embedding profile.
The test verifies deposited-source ingestion and disposable exact and lexical retrieval.
The test does not verify hybrid retrieval.
The test currently calls unqualified retrieval commands.
Those calls now select the normal hybrid commands and fail with `hybrid_profile_unavailable`.

**Terms**

- **Diagnostic channel** means the existing `exact-lexical` retrieval channel.
- **Source-ingest fixture test** means `test_source_add_file_ingests_project_pdf_fixture`.

Primary end-to-end flow:

1. The source-ingest fixture test creates a PDF representation.
   The test uses its existing processing configuration.
2. The test calls the existing build command with the diagnostic channel.
3. The Pipeline builds the exact and lexical derived projection without an embedding request.
4. The test calls the existing query command with the diagnostic channel.
5. The test verifies the existing authoritative retrieval result.

## Goals

- Repository CI validates the source-ingest fixture without a semantic embedding service.
- DR-3 normal hybrid commands continue to require a configured semantic embedding profile.
- The source-ingest fixture test identifies the retrieval behavior that it validates.

## Requirements

### Source-ingest fixture test

- SIF-01: The source-ingest fixture test passes `--channel exact-lexical` to the build command.
- SIF-02: The source-ingest fixture test passes `--channel exact-lexical` to `retrieval query`.
- SIF-03: The source-ingest fixture test does not define an embedding profile.
  The source-ingest fixture test does not start an embedding service.

### Pipeline contract

- PC-01: The Pipeline retains the unqualified DR-3 build and query contract.
- PC-02: The Pipeline retains the existing exact-lexical diagnostic channel contract.

## Proposed Architecture

The fixture test owns channel selection for its diagnostic assertion.
The Pipeline owns the existing diagnostic channel behavior.

```text
source-ingest fixture test
          |
          v
Pipeline retrieval CLI --channel exact-lexical
          |
          v
exact and lexical derived projection
```

## Key Interactions

```text
fixture test -> Pipeline: build-document --channel exact-lexical
Pipeline -> projection: build exact and lexical records
fixture test -> Pipeline: query --channel exact-lexical
Pipeline -> fixture test: authoritative node result
```

## Data Model

This TDD creates no Domain Core records or schema.
The existing derived exact and lexical projection records remain disposable state.

## APIs / Interfaces

The fixture test uses the existing `--channel exact-lexical` CLI option.
This TDD changes no public CLI contract.

## Behavior & Domain Rules

The normal DR-3 commands require the configured semantic embedding profile.
The diagnostic channel does not require an embedding profile.
The source-ingest fixture test verifies PDF ingestion and exact and lexical retrieval.
The test uses the diagnostic channel for that scope.

## Acceptance Criteria

- AC-SIF-01: The source-ingest fixture test passes with its existing processing-only configuration.
- AC-SIF-02: The test command arguments include `--channel exact-lexical` for build and query.
- AC-PC-01: Existing DR-3 Pipeline tests prove unqualified commands pass the configured normal profile.
- AC-PC-02: Repository formatting, lint, type, and test checks pass.

## Reference Implementations

- Source-ingest fixture: `packages/pipelines/tests/test_source_add_file.py`.
- DR-3 Pipeline contract: `packages/pipelines/tests/test_document_retrieval.py`.
- Diagnostic channel dispatch: `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

The implementation stops if it needs to change the normal hybrid command behavior.
The implementation stops if it adds an embedding profile to the source-ingest fixture test.
The implementation stops if it adds a model dependency to the source-ingest fixture test.
