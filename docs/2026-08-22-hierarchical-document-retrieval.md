# DR-4: Hierarchical Document Retrieval

- Status: Accepted
- Program: `derived-retrieval`
- Deliverable ID: `DR-4`
- Depends on: `docs/2026-08-21-document-hybrid-activation.md`
- Program envelope: `docs/2026-07-11-derived-document-retrieval.md`
- Local conformance command: `uv run python scripts/verify_dr4_canonical.py`

## Context & Problem

DR-3 selects one or more small authoritative `DocumentNode` records through the document plane.
Each selected node already has authoritative parent links in its `DocumentRepresentationBundle`.
The existing `DocumentRetrievalUnit` records a readable `section_path` but not the node identities that define its structural ancestry.
Reviewers cannot inspect the complete structural position that made a derived unit searchable.

`ContextPlanner` already resolves heading ancestry from the authoritative bundle.
DR-4 makes the derived unit identity include the same authoritative lineage.
DR-4 keeps `ContextPlanner` as the only component that selects and packs model context.

**Glossary**

- A **direct parent** is the `DocumentNode` named by a searchable node's `parent_node_id`.
- An **ancestor chain** is the ordered tuple from the document-root node to the direct parent.
- A **heading ancestor** is an ancestor whose `node_type` is `heading`.
- A **parent body** is the original text of a non-heading ancestor.

### Primary end-to-end flow

1. The Application Layer loads an acceptable `DocumentRepresentationBundle`.
2. The Application Layer derives a `DocumentRetrievalUnit` for each searchable `DocumentNode`.
3. Each unit records its direct parent and complete ancestor chain in its deterministic identity.
4. The derived indexes publish retrieval representations that reference the new unit identities.
5. A retrieval query selects focal authoritative node IDs.
6. `ContextPlanner` resolves heading ancestors from the authoritative bundle and writes a `ContextManifest`.

## Goals

- A reviewer can inspect the direct parent and complete ancestor chain for each derived unit.
- A rebuilt index produces the same hierarchy-aware unit identities from the same representation.
- A selected focal node retains the headings that identify its document location.
- A `ContextManifest` contains original focus and heading text without automatic parent-body expansion.
- Existing exact, lexical, semantic, and hybrid query behavior remains available after index rebuild.

## Requirements

### Retrieval-unit requirements

- RU-01: `DocumentRetrievalUnit` uses `document_node_hierarchy_unit_v2` as its unit policy.
- RU-02: Each unit has exactly one focal `DocumentNode` ID.
- RU-03: Each unit records one required `parent_node_id`.
- RU-04: Each unit records required `ancestor_node_ids` from the document root through its direct parent.
- RU-05: `ancestor_node_ids` contains no duplicate ID and excludes the focal node ID.
- RU-06: The last `ancestor_node_ids` value equals `parent_node_id`.
- RU-07: The unit fingerprint includes `parent_node_id` and `ancestor_node_ids`.
- RU-08: The Application Layer derives the two hierarchy fields only from the accepted bundle.
- RU-09: A unit does not store copied parent or ancestor text.

### Index requirements

- IR-01: Exact, lexical, and semantic builds use the DR-4 unit policy.
- IR-02: A manifest with another unit policy fails as `retrieval_index_stale`.
- IR-03: A rebuild replaces only derived retrieval state.
- IR-04: A rebuild from the same accepted bundle produces the same unit IDs and manifest content fingerprints.

### Context requirements

- CT-01: Retrieval sends only selected focal `DocumentNode` IDs to `ContextPlanner`.
- CT-02: `ContextPlanner` reads parent links from the accepted `DocumentRepresentationBundle`.
- CT-03: `ContextPlanner` adds every heading ancestor as a required `ContextCandidate`.
- CT-04: `ContextPlanner` does not add the document root as a `ContextCandidate`.
- CT-05: `ContextPlanner` does not add a parent body solely because it is an ancestor.
- CT-06: `ContextPlanner` remains the only component that writes a `ContextManifest`.

### Canonical conformance requirements

- CC-01: The conformance script verifies the locked local fixture digest and page count.
- CC-02: The conformance script uses public `kotekomi` commands with a disposable Ledger and Archive.
- CC-03: The script ingests the fixture, builds the exact and lexical index, and queries `all lawful purposes`.
- CC-04: The script verifies the selected persisted unit's hierarchy against the accepted bundle.
- CC-05: The script verifies that the resulting manifest includes every heading ancestor of the focus node.
- CC-06: The script verifies that the resulting manifest excludes non-heading ancestor bodies and unrequired sibling nodes.
- CC-07: The script emits a JSON failure when the fixture is missing or differs from the lock.
- CC-08: The script creates no Harness task state, receipt, or lifecycle record.

## Proposed Architecture

The Application Layer derives hierarchy-aware units from authoritative document structure.
The SQLite Adapter stores those units only as derived index state.
`ContextPlanner` resolves and packs authoritative context.

```text
DocumentRepresentationBundle
        |
        v
DocumentRetrievalUnit
  parent_node_id
  ancestor_node_ids
        |
        v
derived document indexes
        |
        v
RetrievalHit
        |
        v
ContextPlanner
        |
        v
ContextManifest
```

## Key Interactions

```text
operator -> Pipeline: retrieval query
Pipeline -> Application Layer: query command
Application Layer -> SQLite Adapter: channel candidates
SQLite Adapter -> Application Layer: retrieval unit IDs
Application Layer -> ContextPlanner: focal node IDs
ContextPlanner -> accepted bundle: parent links and source text
ContextPlanner -> Pipeline: ContextManifest
```

## Data Model

`DocumentRetrievalUnit` adds `parent_node_id` and `ancestor_node_ids`.
The direct parent duplicates the final ancestor ID for direct inspection.
The ancestor chain includes the document root and excludes the focal node.
The unit policy changes from `document_node_unit_v1` to `document_node_hierarchy_unit_v2`.
The exact, lexical, and semantic representation types do not add hierarchy fields.
Their existing unit identity reference makes each new representation hierarchy-aware.
`RetrievalHit`, `AnalysisUnit`, and `ContextManifest` keep their current shapes.

## APIs / Interfaces

`document_retrieval_unit_fingerprint` accepts `parent_node_id` and `ancestor_node_ids`.
`DocumentRetrievalUnit` requires both fields.
The existing build and query commands keep their command-line interfaces.
The existing `RetrievalSelectionAnalysisUnitInput` keeps focal node IDs as its only retrieval input.

## Behavior & Domain Rules

The Application Layer excludes the document root from searchable units.
Each searchable unit therefore has a direct parent and a nonempty ancestor chain.
The Application Layer follows `parent_node_id` links until it reaches the document root.
The Application Layer fails rather than creating a unit when the bundle cannot provide that chain.
The accepted bundle already validates parent references and cycles before DR-4 builds a unit.

The Application Layer rejects a prior index manifest because it identifies the v1 unit policy.
The Application Layer rebuilds derived retrieval state from the accepted bundle.
The rebuild does not modify Archive bytes, accepted document records, or Ledger knowledge.

`ContextPlanner` treats focal nodes and heading ancestors as separate candidates.
`ContextPlanner` keeps heading ancestors required under the existing token-budget policy.
The planner does not use derived unit text or ancestry values as context evidence.

## Acceptance Criteria

- AC-RU-01: Domain tests prove unit validation and identity for a complete ancestor chain.
- AC-RU-02: Domain tests reject an empty, repeated, self-referential, or parent-mismatched chain.
- AC-RU-03: Application tests prove the builder records root-to-parent ancestry from a nested bundle.
- AC-IR-01: Adapter tests prove a v1 manifest fails as stale under DR-4.
- AC-IR-02: Adapter and Application tests prove exact, lexical, and semantic rebuilds retain deterministic identities.
- AC-CT-01: Application tests prove retrieval sends focal IDs without parent-body text.
- AC-CT-02: Context tests prove every heading ancestor is selected and the document root is excluded.
- AC-CT-03: Context tests prove a sibling and a non-heading parent body remain excluded.
- AC-CC-01: The direct local conformance script validates the locked PDF and DR-4 query path.
- AC-CC-02: Formatting, lint, type checks, focused tests, and the repository test suite pass.

## Reference Implementations

- Unit building: `packages/application/src/kotekomi_application/document_retrieval.py`.
- Hierarchy packing: `packages/application/src/kotekomi_application/context_planning.py`.
- Derived storage: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.
- Public retrieval command: `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

DR-4 does not add a retrieval channel, a retrieval plane, a reranker, or a prompt-building service.
DR-4 does not change document parsing or hierarchy repair.
DR-4 stops if an implementation requires synthetic text as source evidence.
DR-4 stops if `ContextPlanner` must accept derived unit text or derived ancestry as authority.
DR-4 uses ordinary repository checks and the local conformance script.
DR-4 does not use Harness task lifecycle or receipt functions.
