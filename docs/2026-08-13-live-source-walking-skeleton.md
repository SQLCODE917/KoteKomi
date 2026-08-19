# TDD: Deposited-Source Walking Skeleton

- **Status:** Proposed
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Source Capture and Document Versioning](2026-07-11-source-capture-and-document-versioning.md) and [Versioned Document Representations](2026-07-11-versioned-document-representations.md)

## 1. Context & Problem

KoteKomi accepts local Markdown and text files through `source add-file`.
KoteKomi does not accept a deposited PDF through that command.
KoteKomi has a PDF representation path, but no Pipeline composes it with authoritative Source capture.

A user can acquire a Wikipedia article with a browser.
The user selects Wikipedia's **Download as PDF** option and places the result in `raw/`.
The user supplies the article URL to KoteKomi without giving KoteKomi network authority.

**Deposited source** means a PDF, Markdown, or text file that a user placed on the local filesystem.

**Source URL** means the absolute HTTPS URL that identifies the external Source represented by a deposited source.

**Staging folder** means the project-root `raw/` folder that holds user-provided input before KoteKomi archives it.

### Primary end-to-end flow

1. A user places a Wikipedia PDF in `raw/`.
2. The user runs `source add-file <path> --source-url <URL>`.
3. The Pipeline validates the file and Source URL.
4. The Application Layer archives the exact bytes and commits the canonical Source and Document.
5. The Application Layer creates a representation that matches the file type.
6. The command returns the canonical identifiers and the representation outcome.

## 2. Goals

- A user can archive and represent a browser-downloaded Wikipedia PDF with one command.
- A user can archive and represent deposited Markdown and text files with the same command.
- KoteKomi preserves the exact input bytes before it creates a representation.
- A user can identify the external Source without granting KoteKomi network access.
- A failed PDF representation leaves the canonical capture available for review and retry.

## 3. Requirements

### Staging folder

- LS-STAGE-01: The repository ignores the project-root `raw/` folder.
- LS-STAGE-02: The Pipeline accepts a file path outside `raw/`.
- LS-STAGE-03: The Archive, not the staging folder, stores accepted raw bytes.

### Pipeline

- LS-PIPE-01: The Pipeline exposes `source add-file <path> --source-url <URL>`.
- LS-PIPE-02: The Pipeline accepts `.pdf`, `.md`, and `.txt` suffixes.
- LS-PIPE-03: The Pipeline requires one absolute HTTPS Source URL.
- LS-PIPE-04: The Pipeline returns JSON when the user passes `--format json`.
- LS-PIPE-05: The Pipeline returns one of `created`, `reused`, `blocked`, or `failed`.
- LS-PIPE-06: The Pipeline does not request the Source URL.

### Deposited source use case

- LS-CAP-01: The Application Layer validates the Source URL before it writes canonical state.
- LS-CAP-02: The Application Layer uses the normalized Source URL as the stable Source identity key.
- LS-CAP-03: The Application Layer uses the exact file bytes to compute the RawBlob and Document identities.
- LS-CAP-04: The Application Layer archives exact file bytes before it invokes a representation parser.
- LS-CAP-05: The Application Layer records the local file path and Source URL in capture provenance.
- LS-CAP-06: Identical Source URL and file bytes reuse the existing Source and Document.
- LS-CAP-07: Changed bytes at one Source URL create a new Document under the existing Source.

### Representation selection

- LS-REP-01: The Application Layer creates the existing local-file representation for `.md` and `.txt` files.
- LS-REP-02: The Application Layer invokes the existing PDF use case for `.pdf` files.
- LS-REP-03: The PDF use case reads the archived bytes associated with the captured Document.
- LS-REP-04: A PDF blocker leaves the Source, RawBlob, SourceCapture, and Document committed.
- LS-REP-05: The command reports PDF blockers without logging document text.

## 4. Proposed Architecture

The Pipeline validates command input and opens the Ledger transaction.
The deposited-source use case owns Source identity and capture decisions.
The PDF use case owns PDF representation decisions.
The Archive and SQLite adapters store canonical records.

```text
User
  |
  v
source add-file Pipeline
  |
  v
DepositedSourceUseCase ----> Archive + Ledger
  |                                |
  |                                v
  +---- local-file representation / PDF use case
```

The Domain Core defines the existing canonical records.
The Application Layer defines the use cases.
The adapters implement archive, Ledger, and PDF parser Ports.

## 5. Key Interactions

```text
User          Pipeline       Application       Archive and Ledger       PDF parser
 |                |                |                    |                    |
 | add-file      |                |                    |                    |
 |--------------->|                |                    |                    |
 |                | validate input |                    |                    |
 |                |--------------->|                    |                    |
 |                |                | archive and commit |                    |
 |                |                |------------------->|                    |
 |                |                | parse PDF bytes    |                    |
 |                |                |---------------------------------------->|
 |                | result         |                    |                    |
 |<---------------|<---------------|                    |                    |
```

## 6. Data Model

This TDD adds no Domain Core record type.

The workflow uses existing Source, RawBlob, SourceCapture, Document,
DocumentRepresentation, ProvenanceActivity, and PDF page-accounting records.

The Source canonical identity key equals the normalized Source URL.

The SourceCapture requested URI and canonical URI equal the normalized Source URL.

The SourceCapture retrieval method equals `user_deposited_file`.

The SourceCapture request metadata records the local file path and original filename.

## 7. APIs / Interfaces

`source add-file` adds the required `--source-url` option.

`source add-file` adds an optional `--format json` option with `text` as the default.

The JSON result contains `status`, `source_id`, `document_id`, `raw_path`,
`representation_id`, `provenance_activity_id`, and `blocking_reasons`.

`representation_id` and `provenance_activity_id` are null for a blocked PDF.

The Application Layer exposes explicit input and outcome DTOs for the deposited-source use case.

## 8. Behavior & Domain Rules

The Pipeline rejects a missing file, unsupported suffix, or invalid Source URL before it opens a Ledger transaction.

The Pipeline accepts only `https` Source URLs with a host.

The Application Layer normalizes the Source URL with the existing URI normalization rule.

The Application Layer creates a new Document when bytes change at an existing Source URL.

The Application Layer does not use a staging path as a Source identity key.

The Application Layer does not fetch the Source URL.

The Application Layer does not create FTS indexes, SourceProjection records, embeddings, Assertions, ProposedChanges, graph state, or Briefings.

## 9. Acceptance Criteria

- AC-LS-STAGE-01: Git ignores the project-root `raw/` folder.
- AC-LS-PIPE-01: Pipeline tests ingest project-owned PDF, Markdown, and text fixtures with a Source URL.
- AC-LS-PIPE-02: Pipeline tests reject a missing Source URL, non-HTTPS URL, missing file, and unsupported suffix.
- AC-LS-PIPE-03: Pipeline JSON tests return each required field and never perform a network request.
- AC-LS-CAP-01: Application tests prove the Source URL supplies stable Source identity and capture URI fields.
- AC-LS-CAP-02: Application tests prove the Archive receives exact bytes before representation parsing.
- AC-LS-CAP-03: Application tests prove identical bytes reuse canonical records and changed bytes create a Document revision.
- AC-LS-REP-01: PDF integration tests prove the parser receives captured PDF bytes and commits its representation.
- AC-LS-REP-02: A blocked PDF test proves capture records remain committed and reports typed blockers.
- AC-LS-REP-03: Markdown and text tests retain deterministic local-file representation behavior.
- AC-LS-MANUAL-01: The documented local command ingests `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf` with its Wikipedia Source URL.

## 10. Reference Implementations

- Source identity and immutable capture: `packages/application/src/kotekomi_application/source_capture.py`.
- Local text representation: `packages/application/src/kotekomi_application/source_file_ingest.py`.
- PDF representation: `packages/application/src/kotekomi_application/pdf_ingest.py`.
- PDF parser: `packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py`.
- Pipeline configuration and transactions: `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## 11. Constraints and Halt Conditions

- Halt if the implementation requires an HTTP client, browser automation, or MediaWiki API access.
- Halt if a parser reads a staging file after the Application Layer archives the canonical bytes.
- Halt if the implementation uses the local path as the Source identity key.
- Halt if the implementation adds derived retrieval or intelligence state to this TDD.
- CI uses only project-owned fixtures.
