# TDD: Live-Source Walking Skeleton

- **Status:** Proposed
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Source Capture and Document Versioning](2026-07-11-source-capture-and-document-versioning.md), [Versioned Document Representations](2026-07-11-versioned-document-representations.md), and [Derived Document Retrieval](2026-07-11-derived-document-retrieval.md)

## 1. Context & Problem

KoteKomi currently ingests local files and recorded structured-news payloads through separate workflows.

KoteKomi does not yet expose one walking skeleton from a permitted live HTML URL to searchable, replayable source material.

The test article is [Anthropic–United States Department of Defense dispute](https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute).

The command reads the article body from one JSON-LD Article Object in the initial HTTP HTML response.

The command preserves the complete HTTP response as an immutable raw capture.

The command creates a versioned `DocumentRepresentation` from the captured HTML.

The representation applies the pinned `jsonld_article_body_v1` extraction policy.

The lexical index searches original representation node text.

The `SourceProjection` is a disposable, schema-valid JSON view of one representation.

The `SourceProjection` gives operators a review surface and gives agents a typed object.

The source capture, representation, and retrieval TDDs define the underlying authority contracts.

### Terms

**Live HTML Article** means one permitted URL whose initial successful response contains one unambiguous JSON-LD Article Object.

**JSON-LD Article Object** means one JSON-LD object with type `Article` or `NewsArticle` and a non-empty string `articleBody` field.

**Source Fetch Result** means the validated Application Layer DTO returned by the `SourceFetcher` Port.

**Source Projection** means the disposable JSON object that describes one `Source`, one `Document`, and one representation.

**Lexical Index** means the SQLite FTS5 derived index for pinned representations.

### Primary end-to-end flow

1. A user runs `source add-url` with the test article URL.
2. The Pipeline asks the `SourceFetcher` Port for the initial HTML response.
3. The Application Layer archives the response and resolves immutable `Source` and `Document` records.
4. The HTML Representation Adapter reads the archived response, selects one JSON-LD Article Object, and commits a versioned representation.
5. The SQLite FTS5 Adapter indexes representation nodes.
6. The Application Layer writes a deterministic `SourceProjection` and returns its archive reference.

The command reports created or reused canonical and derived objects.

## 2. Goals

- A user ingests the test article through one command without preparing a local source file.
- The workflow preserves exact response bytes and creates one replayable representation.
- FTS5 returns original `DocumentNode` identifiers and exact node text.
- The workflow writes byte-stable JSON for pinned inputs and policies.
- Repeated responses reuse identities and changed responses create new immutable documents.
- The workflow reports an explicit failure when the response has no unambiguous JSON-LD Article Object.
- Agents consume typed search hits and JSON without parsing Markdown.
- Derived-state deletion leaves canonical source, document, and representation records unchanged.

## 3. Requirements

### User Pipeline

- LS-PIPE-01: The Pipeline exposes `source add-url --url <URL>` as the walking-skeleton entry point.
- LS-PIPE-02: The Pipeline accepts exactly one absolute `http` or `https` URL and returns machine-readable JSON with `--format json`.
- LS-PIPE-03: The Pipeline reports typed `blocked`, `failed`, `created`, and `reused` outcomes.
- LS-PIPE-04: The Pipeline writes canonical records through the Application Layer and returns all output IDs and archive references.

### SourceFetcher Port and Adapter

- LS-FETCH-01: The `SourceFetcher` Port returns response bytes, requested URI, final URI, status, media type, redirect chain, and safe response metadata.
- LS-FETCH-02: The Adapter sends one ordinary HTTP GET request and does not execute JavaScript or call the MediaWiki API.
- LS-FETCH-03: The Adapter accepts only a final 2xx `text/html` response of at most 10 MiB.
- LS-FETCH-04: The Adapter records redirects and the HTML canonical link without replacing requested URL identity.
- LS-FETCH-05: The Adapter removes authorization, cookie, and `Set-Cookie` values from safe metadata.
- LS-FETCH-06: The Adapter returns typed failures for transport, response, size, and access-challenge errors.
- LS-FETCH-07: The Adapter does not bypass access controls and normalizes the requested URI deterministically.

### Capture Use Case

- LS-CAP-01: The Application Layer stores the response bytes in a `RawBlob` before downstream derived state.
- LS-CAP-02: The Application Layer resolves `Source` identity from the normalized requested URI.
- LS-CAP-03: The Application Layer resolves `Document` identity from the `Source`, raw digest, and generic HTML version policy.
- LS-CAP-04: The Application Layer uses the raw SHA-256 digest as the generic HTML provider version.
- LS-CAP-05: The Application Layer uses normalized URI plus raw digest as this workflow's idempotent capture identity.
- LS-CAP-06: The same identity reuses the existing capture and document; a changed digest creates a new document and update relation.
- LS-CAP-07: `SourceCapture` records URI, response metadata, retrieval method, capture time, and rights profile.
- LS-CAP-08: A representation failure preserves the committed raw capture.

### HTML Representation Adapter

- LS-REP-01: The Adapter reads the archived `RawBlob` and does not fetch the URL during representation creation.
- LS-REP-02: The Adapter records parser name, version, configuration digest, code revision, input digest, and output digest.
- LS-REP-03: The Adapter applies only the pinned `jsonld_article_body_v1` policy in this slice.
- LS-REP-04: The policy selects exactly one JSON-LD Article Object from the captured HTML.
- LS-REP-05: The policy returns `jsonld_article_body_missing` when no JSON-LD Article Object has a non-empty `articleBody` field.
- LS-REP-06: The policy returns `jsonld_article_body_ambiguous` when multiple JSON-LD Article Objects have a non-empty `articleBody` field.
- LS-REP-07: The Adapter creates one logical `TextView` and ordered nodes from the selected `articleBody` value.
- LS-REP-08: The Adapter records a replayable `EvidenceTarget` for every indexed node.
- LS-REP-09: The Adapter commits the validated bundle atomically and creates a new representation for parser or policy changes.
- LS-REP-10: Unchanged pinned inputs create the same representation digest.

### Lexical Index

- LS-FTS-01: The Lexical Index stores original logical node text and deterministic title and section metadata.
- LS-FTS-02: The Lexical Index excludes empty and generated text and inserts nodes in stable representation order.
- LS-FTS-03: The Lexical Index manifest records representation IDs, representation digests, preprocessing policy, software identity, and output digest.
- LS-FTS-04: The search Port accepts a query pinned to one manifest and returns representation ID, node ID, exact text, section path, method, score, and rank.
- LS-FTS-05: The search Port returns original node text, uses stable ID tie-breaking, and rejects missing, corrupt, or stale manifests.
- LS-FTS-06: The Lexical Index remains rebuildable from committed representations.

### Source Projection

- LS-PROJ-01: The Application Layer builds the `SourceProjection` from validated source, document, representation, node, selector, and index-manifest records.
- LS-PROJ-02: The projection includes source identity, URIs, capture ID, document ID, representation ID, parser lineage, and representation digest.
- LS-PROJ-03: The projection includes ordered sections and nodes with IDs, types, section paths, exact text, and selector references.
- LS-PROJ-04: The projection includes the Lexical Index manifest ID and representation digest.
- LS-PROJ-05: The projection uses a versioned schema and canonical JSON serialization.
- LS-PROJ-06: The writer validates references, content-addresses the derived Archive object, and reuses identical content.
- LS-PROJ-07: The writer writes no accepted Ledger records or generated prose.

## 4. Proposed Architecture

The `LiveHtmlIngestUseCase` owns workflow decisions and transaction intent.

The SourceFetcher, capture, representation, FTS5, and derived Archive components own their respective tool boundaries.

```text
source add-url Pipeline
          │
          ▼
LiveHtmlIngestUseCase ───────► SourceFetcher Adapter
          │                              │
          │                              ▼
          │                       Source Fetch Result
          ▼                              │
Capture and Representation Use Cases ◄──┘
          │
          ├──────────────► Ledger + authoritative Archive
          ├──────────────► SQLite FTS5 Adapter
          └──────────────► Derived Archive Adapter
                                      │
                                      ▼
                              SourceProjection JSON
```

The Domain Core defines existing source, document, representation, node, and selector records.

The Application Layer defines Ports, Adapters implement HTTP, FTS5, and Archive behavior, and the Pipeline formats results.

The Domain Core imports no HTTP, HTML, FTS5, or JSON rendering code.

## 5. Key Interactions

```text
User        Pipeline       Fetcher       Application       Ledger/Archive       FTS5       Projection
 │              │             │              │                    │                │             │
 │ add-url      │             │              │                    │                │             │
 │─────────────►│             │              │                    │                │             │
 │              │ fetch URL   │              │                    │                │             │
 │              │────────────►│              │                    │                │             │
 │              │             │ result       │                    │                │             │
 │              │◄────────────│              │                    │                │             │
 │              │ ingest      │              │                    │                │             │
 │              │──────────────────────────►│                    │                │             │
 │              │             │              │ archive and commit │                │             │
 │              │             │              │───────────────────►│                │             │
 │              │             │              │ build index        │                │             │
 │              │             │              │────────────────────────────────────►│             │
 │              │             │              │ build projection   │                │             │
 │              │             │              │──────────────────────────────────────────────►│
 │              │ result      │              │                    │                │             │
 │◄─────────────│             │              │                    │                │             │
```

The Pipeline stops after a typed fetch failure, while the Application Layer preserves captures on representation failure.

The Application Layer publishes the index manifest before the projection reference and publishes neither on index failure.

## 6. Data Model

The Ledger already stores the canonical source, capture, document, revision, and representation records.

The Archive already stores immutable raw source bytes.

This TDD adds the following derived DTOs and records.

```yaml
SourceFetchResult:
  requested_uri:
  final_uri:
  status:
  media_type:
  redirect_chain:
  response_metadata:
  payload:

LexicalIndexManifest:
  manifest_id:
  representation_ids:
  representation_digests:
  preprocessing_policy_id:
  software_identity:
  output_digest:

SourceProjection:
  projection_version:
  projection_id:
  source_id:
  capture_id:
  document_id:
  representation_id:
  requested_uri:
  final_uri:
  title:
  parser_lineage:
  representation_digest:
  sections:
  nodes:
  lexical_index_manifest_id:

SourceProjectionNode:
  node_id:
  node_type:
  section_path:
  text:
  source_selector_id:
```

`SourceFetchResult` exists only at the SourceFetcher Port boundary.

The derived manifest and projection remain rebuildable, and the projection schema validates every node reference against the pinned representation.

The projection does not become an alternate source of truth for article text.

## 7. APIs / Interfaces

The SourceFetcher Port returns one `SourceFetchResult` or one typed failure.

The lexical search Port returns validated `RetrievalHit` DTOs pinned to one manifest.

The projection writer accepts validated records and returns one derived Archive object reference.

The Pipeline returns all IDs and archive references, uses non-zero exits for blocked or failed outcomes, and omits article body text from logs.

The implementation adds `schemas/source_projection.schema.json`, a derived Archive Port, and the single-representation lexical path.

## 8. Behavior & Domain Rules

### Same response

The Application Layer computes one SHA-256 digest over the received HTML bytes.

The same normalized URI and byte digest resolve the same canonical and derived identities and return `reused`.

### Changed response

The same normalized URI with a different byte digest keeps the existing `Source` and creates a new `Document`.

The new `Document` receives an update relation and new representation, index manifest, and projection.

The prior document, representation, index manifest, and projection remain readable.

### Parser change

A parser or representation-policy change creates a new representation while the prior representation remains pinned to its original lineage.

### Failure and rebuild

The Application Layer preserves raw captures on representation failure and publishes no index or projection for a blocked representation.

The Application Layer rejects stale or corrupt indexes before search, and deleting derived state leaves canonical records unchanged.

Rebuilding from archived input reproduces the same derived digests under pinned policies.

### Explicit scope

This TDD creates no concept pages, wiki pages, Assertions, ProposedChanges, graph projections, semantic indexes, embeddings, summaries, rerankers, or Briefings.

This TDD adds no browser rendering, MediaWiki API access, or provider-specific Wikipedia logic.

## 9. Acceptance Criteria

### Primary workflow

- AC-LS-PIPE-01: A fixture-backed command test uses a fake SourceFetcher and returns one valid projection reference.
- AC-LS-PIPE-02: A live smoke test verifies the test URL returns 2xx HTML with one unambiguous JSON-LD Article Object, the expected title, a representation, and one FTS hit.
- AC-LS-FETCH-01: Adapter tests cover success, redirects, response rejection, size, metadata filtering, and access challenges.
- AC-LS-CAP-01: Capture tests verify stable Source identity, raw SHA-256 storage, immutable Document creation, and replay.
- AC-LS-REP-01: Representation tests verify JSON-LD selection, article-body nodes, logical text, order, EvidenceTargets, lineage, digest, and atomic publication.
- AC-LS-REP-02: A fixture with no qualifying `articleBody` returns `jsonld_article_body_missing`, preserves the raw capture, and publishes no representation or derived output.
- AC-LS-REP-03: A fixture with multiple qualifying `articleBody` values returns `jsonld_article_body_ambiguous`, preserves the raw capture, and publishes no representation or derived output.
- AC-LS-FTS-01: FTS tests verify a known phrase returns original representation and node IDs with exact text.
- AC-LS-PROJ-01: Projection tests validate the schema and every node and selector reference.

### Determinism and revision

- AC-LS-DET-01: Identical responses produce identical canonical IDs, representation digest, index digest, projection bytes, and projection digest.
- AC-LS-DET-02: A one-byte response change preserves Source identity, creates a new Document and representation, and preserves the earlier revision.
- AC-LS-DET-03: A parser-policy change creates a new representation, and derived-state rebuild reproduces pinned output.

### Failure, authority, and safety

- AC-LS-FAIL-01: Fetch failure creates no canonical or derived records, while representation failure preserves the raw capture and creates no derived output.
- AC-LS-FAIL-02: Stale or corrupt index and projection references fail before successful publication or search.
- AC-LS-FAIL-03: Tests prove that no model, graph, embedding, Briefing, or accepted Ledger write runs in this workflow.
- AC-LS-DOC-01: Deterministic tests use recorded or synthetic rights-safe responses, and logs omit article body text by default.

## 10. Reference Implementations

- Immutable capture identity: follow `packages/application/src/kotekomi_application/source_capture.py`.
- Representation identity: follow `packages/application/src/kotekomi_application/representation_identity.py`.
- Structured article mapping: follow `packages/adapters/src/kotekomi_adapters/structured_news.py`.
- Representation persistence: follow `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.
- Raw Archive storage: follow `packages/adapters/src/kotekomi_adapters/local_archive.py`.
- Pipeline fixtures: follow `packages/pipelines/tests/test_source_add_news.py`.
- Retrieval contract: follow `docs/2026-07-11-derived-document-retrieval.md`.

## 11. Constraints and Halt Conditions

- Halt if the test URL lacks one unambiguous JSON-LD Article Object with a non-empty `articleBody` field.
- Halt if selected indexed nodes lack replayable `EvidenceTarget` records.
- Halt if browser rendering or MediaWiki API access becomes necessary.
- Halt if implementation introduces a second canonical record for article text or source identity.
- A later HTML extraction strategy requires a separate TDD and a separate policy identity.
- Halt if implementation adds concepts, graph traversal, semantic search, model synthesis, or Briefing generation.
- Halt if deterministic CI requires live network bytes.
