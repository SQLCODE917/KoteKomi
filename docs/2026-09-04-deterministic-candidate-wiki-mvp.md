# TDD: Deterministic Candidate Wiki MVP

- Status: Accepted
- Program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Deliverable ID: CIR-4
- Depends on: [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Supersedes: [CIR-3 Candidate Knowledge View](2026-08-25-cir-3-candidate-knowledge-view.md)

## 1. Context & Problem

HP-8 creates one closed `IngestionChangeSet` from a complete document run.

The change set can contain pending `Actor`, `Organization`, `Event`, and `Assertion` records.

The review CLI presents each `ProposedChange` separately.

The user cannot inspect those records as one connected knowledge view.

KoteKomi does not yet generate a Wiki projection.

CIR-4 will generate a deterministic Candidate Wiki for one selected ingestion.

The Candidate Wiki will contain source-backed pages and explicit review state.

The Candidate Wiki will remain disposable derived state.

### Terms

**CandidateKnowledgeView** means an Application Layer read model for one closed change set.

The CandidateKnowledgeView combines accepted reference records with reviewable candidate records.

**Candidate record** means one valid pending record from a `ProposedChange`.

**Candidate Wiki** means the complete Markdown page set for one CandidateKnowledgeView.

**WikiPageInput** means the typed records and citations that determine one Wiki page.

**Wiki page input fingerprint** means the digest of one WikiPageInput and the renderer policy.

**WikiEvidenceReference** means one replayable source selector for displayed Wiki content.

It contains an `EvidenceTarget` or the exact evidence selector inside one `ProposedChange`.

**WikiCitationRegistry** maps citation numbers to WikiEvidenceReferences.

**WikiBuildManifest** means the complete machine-readable record of one Candidate Wiki build.

**Active Wiki link** means the `review/wiki` symlink to one complete build directory.

### Primary end-to-end flow

1. The user selects one captured ingestion by exact filename.
2. The Application Layer resolves its closed change set into one CandidateKnowledgeView.
3. The Application Layer creates every WikiPageInput and the WikiCitationRegistry.
4. The Wiki renderer creates deterministic Markdown from the typed page inputs.
5. The Archive Adapter atomically publishes the complete build under `review/wiki/`.
6. The CLI prints the relative Candidate Wiki path.

## 2. Goals

- A user can inspect one complete candidate ingestion with ordinary Markdown tools.
- Every displayed claim identifies its accepted or pending review state.
- Every source-backed claim resolves to exact authoritative evidence.
- Rebuilding the same Candidate Wiki produces byte-identical files.
- Candidate Wiki generation changes no accepted intelligence.

## 3. Requirements

### Ingestion selection

- CW-SEL-01: The CLI accepts one exact filename basename.
- CW-SEL-02: The CLI uses the program's common ingestion selector for duplicate filenames.
- CW-SEL-03: The selector accepts an `IngestionRun` only when it names a closed change set.
- CW-SEL-04: The selector rejects an ingestion without a closed change set.
- CW-SEL-05: The CLI requires no canonical Domain ID from the user.

### CandidateKnowledgeView

- CW-VIEW-01: The Application Layer creates the CandidateKnowledgeView without a Ledger write.
- CW-VIEW-02: The view identifies one `IngestionRun` and its `IngestionChangeSet`.
- CW-VIEW-03: The view validates the change-set digest before it reads any proposal body.
- CW-VIEW-04: The view reads only the ProposedChanges named by the change set.
- CW-VIEW-05: The view parses every included proposal through its declared Domain Core record.
- CW-VIEW-06: The view supports `Actor`, `Organization`, `Event`, and `Assertion` proposals.
- CW-VIEW-06A: The view parses a pending Assertion as a `ProposedAssertion`.
- CW-VIEW-06B: The view parses embedded proposal evidence as a WikiEvidenceReference.
- CW-VIEW-07: A pending proposal contributes its proposed record as a Candidate record.
- CW-VIEW-08: An approved proposal contributes its accepted Ledger record.
- CW-VIEW-09: An edited proposal contributes its accepted Ledger record.
- CW-VIEW-10: A rejected proposal contributes no intelligence record.
- CW-VIEW-11: The view records excluded rejected proposals in its summary.
- CW-VIEW-12: The view includes accepted records that an included record references.
- CW-VIEW-13: The view includes each referenced `Source`, `Document`, and `EvidenceTarget`.
- CW-VIEW-14: The view fails when a required accepted or candidate reference is absent.
- CW-VIEW-15: The view fails when a proposal declares an unsupported record type.
- CW-VIEW-16: The view orders records by record type and record ID.
- CW-VIEW-17: The snapshot digest covers each proposal ID, review status, and source payload.
- CW-VIEW-18: The snapshot digest covers each accepted reference record.
- CW-VIEW-19: The snapshot digest covers the change-set digest and view policy ID.
- CW-VIEW-20: Domain defaults do not change the digest of a pending proposal source payload.

### Page planning

- CW-PLAN-01: The Application Layer creates one home page.
- CW-PLAN-02: The Application Layer creates one page for the selected Document.
- CW-PLAN-03: The Application Layer creates one page per included Actor.
- CW-PLAN-04: The Application Layer creates one page per included Organization.
- CW-PLAN-05: The Application Layer creates one page per included Event.
- CW-PLAN-05A: The Application Layer creates pages for included accepted Entity and Place references.
- CW-PLAN-06: The subject page displays every included Assertion.
- CW-PLAN-07: An entity-object page displays an inbound link for each Assertion.
- CW-PLAN-08: The Document page links every record with a WikiEvidenceReference.
- CW-PLAN-09: Every included record appears in at least one WikiPageInput.
- CW-PLAN-10: The planner derives page labels from typed record names.
- CW-PLAN-11: The planner creates filesystem-safe paths under typed directories.
- CW-PLAN-12: The planner resolves equal paths with a deterministic digest suffix.
- CW-PLAN-13: The planner orders pages by page type, case-folded label, and path.
- CW-PLAN-14: Each WikiPageInput records accepted or pending state for each record.
- CW-PLAN-15: Each page fingerprint covers its typed source payloads and citations.
- CW-PLAN-16: Each page input fingerprint covers the renderer policy ID.

### Citations

- CW-CIT-01: The Application Layer creates one citation per displayed WikiEvidenceReference.
- CW-CIT-01A: An included Actor, Organization, or Event uses its proposal evidence.
- CW-CIT-01B: A displayed Assertion uses its persisted EvidenceTargets.
- CW-CIT-02: Each citation names one Source, Document, representation, and exact text range.
- CW-CIT-03: Each citation records the exact evidence text and source location.
- CW-CIT-04: The planner assigns citation numbers in deterministic evidence order.
- CW-CIT-05: Markdown pages use citation numbers instead of canonical Domain IDs.
- CW-CIT-06: The registry identifies an EvidenceTarget or its source ProposedChange.
- CW-CIT-07: Citation validation replays exact text against the authoritative representation.
- CW-CIT-08: Failed citation replay stops the complete build.

### Deterministic rendering

- CW-REN-01: The Wiki renderer accepts only validated WikiPageInput records.
- CW-REN-02: The Wiki renderer makes no model-runtime call.
- CW-REN-03: The renderer labels the complete Wiki as an unpublished Candidate Wiki.
- CW-REN-04: The renderer labels every candidate record as pending review.
- CW-REN-05: The renderer labels every accepted record as accepted.
- CW-REN-06: The renderer uses the canonical predicate for each accepted Assertion.
- CW-REN-06A: The renderer labels a pending ProposedAssertion relation label as proposed.
- CW-REN-06B: The renderer renders each typed subject and object through its page label.
- CW-REN-07: The renderer preserves literal object values without semantic rewriting.
- CW-REN-08: The renderer links typed record references to their planned pages.
- CW-REN-09: The renderer emits no raw canonical Domain ID in Markdown.
- CW-REN-10: The renderer produces byte-identical Markdown for equal WikiPageInput records.

### Build publication

- CW-BLD-01: The Archive Adapter stages one build under `review/wiki-builds/`.
- CW-BLD-02: The staged build contains every planned Markdown page.
- CW-BLD-03: The staged build contains `citations.json` and `manifest.json`.
- CW-BLD-04: The WikiBuildManifest identifies the candidate snapshot digest.
- CW-BLD-05: The manifest records every Markdown and citation file digest.
- CW-BLD-06: The manifest records included and excluded counts by record type and review state.
- CW-BLD-07: The manifest does not record its own path or digest.
- CW-BLD-08: The build ID derives from canonical manifest fields without the build ID.
- CW-BLD-09: Build files contain no build time or host-specific absolute path.
- CW-BLD-10: The build validator rejects an absent, extra, or changed staged file.
- CW-BLD-11: The Adapter promotes a valid stage to an immutable build directory.
- CW-BLD-12: The Adapter atomically replaces the Active Wiki link after promotion.
- CW-BLD-13: A failed build leaves the prior Active Wiki link unchanged.
- CW-BLD-14: The build does not create or modify `wiki/`.
- CW-BLD-15: Equal inputs reuse an equivalent build directory and file bytes.

### Public operation

- CW-CLI-01: `kotekomi wiki build <filename> --candidate` runs CIR-4.
- CW-CLI-02: The command reads Ledger and Archive paths from KoteKomi configuration.
- CW-CLI-03: A successful command prints `review/wiki/` and exits zero.
- CW-CLI-04: A validation or publication failure prints a safe explanation and exits one.
- CW-CLI-05: The command does not change `IngestionRun` status.
- CW-CLI-06: The command does not create an active review.
- CW-CLI-07: The command does not create a ProvenanceActivity.

## 4. Proposed Architecture

```text
User CLI
   |
   v
Candidate Wiki use case -----> Ledger + Archive records
   |
   v
WikiPageInput + citations
   |
   v
Markdown renderer
   |
   v
Candidate Wiki Archive Port -----> review/wiki/
                                 -> review/wiki-builds/<build-id>/
```

The Application Layer owns CandidateKnowledgeView resolution and page planning.

The Wiki exporter owns deterministic Markdown rendering.

The Archive Adapter owns staging, validation, immutable builds, and Active Wiki link replacement.

The Pipeline owns configuration, filename selection, and user output.

The Domain Core keeps existing intelligence and evidence contracts.

## 5. Key Interactions

```text
User       Pipeline       Application       Renderer       Archive
 | build      |                |                |              |
 |----------->| select run     |                |              |
 |            |--------------->| resolve view   |              |
 |            |                | plan pages     |              |
 |            |                |--------------->| render       |
 |            |                |<---------------| files        |
 |            |                |------------------------------>|
 |            |                |                 validate/publish
 |<-----------| review/wiki/   |                |              |
```

## 6. Data Model

`CandidateKnowledgeView` is an immutable Application Layer DTO.

It records these fields:

```text
view_policy_id
ingestion_run_id
ingestion_change_set_id
change_set_digest
candidate_snapshot_digest
records
excluded_proposal_counts
```

Each view record contains its record type, typed record, review state, and source proposal ID.

`WikiPageInput` is an immutable Application Layer DTO.

It records these fields:

```text
relative_path
page_kind
display_label
records
citation_numbers
input_fingerprint
```

`WikiEvidenceReference` records these fields:

```text
citation_number
reference_kind
source_id
document_id
representation_id
text_view_id
start_char
end_char
exact_text
prefix_text
suffix_text
node_ids
page_numbers
evidence_target_id
evidence_validation_attempt_id
proposed_change_id
```

`reference_kind` is `evidence_target` or `proposal_evidence`.

Exactly one evidence target ID or proposal ID identifies the reference origin.

`WikiCitationRegistry` is a structured derived file stored beside the Markdown pages.

`WikiBuildManifest` is a structured derived file stored beside the Markdown pages.

The manifest records the view policy, snapshot digest, renderer policy, file entries, and counts.

The manifest records the selected ingestion and change-set IDs for machine inspection.

Each file entry records a relative path, page input fingerprint, and content digest.

The build has this shape:

```text
review/wiki-builds/<build-id>/
    index.md
    documents/<page>.md
    entities/<page>.md
    actors/<page>.md
    organizations/<page>.md
    places/<page>.md
    events/<page>.md
    citations.json
    manifest.json

review/wiki -> wiki-builds/<build-id>/
```

The Archive stores immutable build directories under `review/wiki-builds/`.

The Active Wiki link exposes the selected build at `review/wiki/`.

CIR-4 adds no Domain Core record and requires no Ledger migration.

## 7. APIs / Interfaces

The public command is:

```text
kotekomi wiki build <filename> --candidate
```

The Application Layer exposes explicit view, plan, validation, and build result DTOs.

The Ledger Port loads the selected run, change set, proposals, and referenced records.

The Candidate Wiki Archive Port stages and publishes one complete build.

The Wiki renderer receives no Ledger repository or Archive path.

The implementation adds the existing `packages/exporters` directory as a workspace package.

## 8. Behavior & Domain Rules

The Candidate Wiki represents one selected ingestion at one observed review state.

A later review decision changes the candidate snapshot digest.

The next build atomically changes the Active Wiki link after complete build validation.

Pending records remain pending in every page and structured file.

Approved and edited records enter the Wiki only through accepted Ledger records.

Rejected records remain auditable through manifest counts and Ledger history.

The Candidate Wiki does not determine review outcomes.

The Candidate Wiki does not become evidence for an Assertion.

The Candidate Wiki does not change accepted intelligence.

## 9. Acceptance Criteria

- AC-CW-01: Application tests prove mixed statuses under CW-VIEW-07 through CW-VIEW-11.
- AC-CW-02: Application tests prove reference closure under CW-VIEW-12 through CW-VIEW-15.
- AC-CW-03: Application tests prove equal inputs produce equal snapshot and page fingerprints.
- AC-CW-04: Page tests prove complete inclusion under CW-PLAN-01 through CW-PLAN-09.
- AC-CW-05: Citation tests prove replay and resolution under CW-CIT-01 through CW-CIT-08.
- AC-CW-06: Exporter tests prove visible state, links, literal preservation, and no raw IDs.
- AC-CW-07: Adapter tests prove complete staging, atomic replacement, and failure preservation.
- AC-CW-08: Pipeline tests prove filename selection, output, exit codes, and zero model calls.
- AC-CW-09: Pipeline tests prove the command changes no Ledger record or published Wiki file.
- AC-CW-10: Rebuild tests prove byte-identical Markdown, citations, and manifest files.
- AC-CW-11: The canonical PDF build produces linked Document, Actor, Organization, and Event pages.
- AC-CW-12: Manual review confirms each displayed claim matches its cited source text.
- AC-CW-13: Formatting, Ruff, Pyright, focused tests, and the full test suite pass.

## 10. Reference Implementations

- Ingestion selection: follow `packages/application/src/kotekomi_application/ingestion_runs.py`.
- Review-state loading: follow `kotekomi_application/review_queue_packet.py`.
- Proposal parsing: follow `kotekomi_application/proposed_change_review.py`.
- Evidence replay: follow `kotekomi_application/evidence_targets.py`.
- Markdown rendering: follow `packages/briefing/src/kotekomi_briefing/markdown.py`.
- Atomic files: follow `packages/adapters/src/kotekomi_adapters/local_archive.py`.

## 11. Constraints and Halt Conditions

Stop if the renderer needs a model judgment to produce a page.

Stop if a page cannot distinguish accepted records from pending records.

Stop if a displayed claim cannot resolve to authoritative evidence.

Stop if the build requires a pending record to enter accepted Ledger state.

Stop if one invalid record would be silently omitted from the Candidate Wiki.
