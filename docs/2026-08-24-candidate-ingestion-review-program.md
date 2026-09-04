# Candidate Ingestion Review Program

- Status: Accepted
- Program ID: `candidate-ingestion-review`
- Repository baseline: `main` at `e901698`
- Prerequisite: [Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- Prerequisite: [Deposited-Source Walking Skeleton](2026-08-13-live-source-walking-skeleton.md)
- Prerequisite: [Derived Retrieval Program](2026-07-11-derived-document-retrieval.md)
- Prerequisite: [Derived Projection Readiness](2026-08-23-derived-projection-readiness.md)
- First child deliverable: [CIR-1 User Ingestion Run MVP](2026-08-24-user-ingestion-run-mvp.md)
- Current extraction program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Current Wiki deliverable: [CIR-4 Deterministic Candidate Wiki MVP](2026-09-04-deterministic-candidate-wiki-mvp.md)

## Context and problem

KoteKomi preserves Sources, Documents, evidence, accepted intelligence, and review history.

KoteKomi also builds disposable projections such as a Wiki projection and a Briefing.

The current operator CLI exposes canonical identifiers and individual pipeline stages.

Existing ProcessingAttempt and AnalysisRun records identify narrower internal work.

No existing record identifies one user ingestion across capture, analysis, review, and publication.

A local user needs a smaller CLI that treats KoteKomi as one black box.

The local user knows deposited file paths, Source URLs, filenames, and generated Markdown paths.

The local user must not need Source IDs, Document IDs, representation IDs, or ProposedChange IDs.

Model output cannot enter accepted Ledger state before review.

Item-by-item review cannot show the combined effect of one document on all projections.

The user needs a complete candidate view before the user publishes or discards one ingestion.

This program adds that review loop in independently shippable child TDDs.

Each child TDD must leave one working user outcome.

Future child TDDs must not be written in full before prior implementation evidence exists.

## Program statement

KoteKomi must let a local user review one document as one candidate knowledge change.

KoteKomi must project the candidate change without changing accepted intelligence.

KoteKomi must publish or discard the complete candidate change through one explicit decision.

```text
deposited file
    -> permanent Source, Document, evidence, and ProposedChanges
    -> candidate knowledge view
    -> candidate Wiki, retrieval, chat, and Briefing projections
    -> publish or discard
    -> clean review workspace
```

The accepted Ledger state remains authoritative.

The Wiki projection, retrieval indexes, chat answers, and Briefings remain disposable.

## Glossary

**User CLI** means the black-box command surface defined by this program.

**Operator CLI** means the existing low-level commands that expose internal workflow controls.

**IngestionRun** means one admitted execution of `kotekomi ingest`.

**IngestionChangeSet** means the closed set of ProposedChanges created by one IngestionRun.

**PublishedKnowledgeRevision** means one immutable digest of accepted knowledge.

**CandidateKnowledgeView** means one PublishedKnowledgeRevision plus one IngestionChangeSet.

**Candidate snapshot digest** means the digest that identifies one CandidateKnowledgeView.

**ReviewWorkspace** means the Archive paths that hold candidate projections for one active review.

**Published projection** means a disposable projection built from accepted Ledger knowledge.

**Candidate projection** means a disposable projection built from one CandidateKnowledgeView.

**Wiki projection** means a complete Markdown wiki generated from one knowledge view.

**Wiki page input fingerprint** means the digest of canonical inputs that determine one Wiki page.

**Active review** means the one IngestionRun whose status is `review`.

## Goals

1. A user can ingest a deposited document with one path and one attribution URL.
2. A user can inspect all admitted ingestion attempts without internal identifiers.
3. KoteKomi can create a complete candidate knowledge view without accepted Ledger writes.
4. A user can inspect candidate Wiki pages with ordinary Markdown tools.
5. A user can identify Wiki pages affected by one ingestion.
6. A user can test the candidate view through retrieval, chat, and a Daily Briefing.
7. A user can publish every ProposedChange from one ingestion as one decision.
8. A user can discard every ProposedChange from one ingestion as one decision.
9. Every decision preserves source capture, model, evidence, proposal, and review provenance.
10. Every projection can be deleted and rebuilt from the Ledger and Archive.

## Non-goals

This program does not implement natural-language command interpretation.

This program does not fetch the supplied Source URL.

This program does not expose individual ProposedChange editing through the User CLI.

This program does not support more than one active review.

This program does not implement general branch creation, rebasing, or merging.

This program does not make generated Wiki Markdown canonical.

This program does not add incremental Wiki mutation commands.

This program does not delete rejected evidence or review history.

This program does not define a destructive purge operation.

This program does not define multi-user authorization.

This program does not make generated chat answers accepted intelligence.

## User CLI contract

The User CLI adds these commands over the program increments.

```text
kotekomi ingest <path> --url <SOURCE_URL>

kotekomi ingestions list

kotekomi ingestions changes <filename>

kotekomi briefing create

kotekomi wiki build <filename> --candidate

kotekomi wiki chat

kotekomi ingestions publish <filename>

kotekomi ingestions discard <filename> --reason <text>
```

The User CLI reads Ledger, Archive, model, and reviewer settings from KoteKomi configuration.

The User CLI accepts the existing global `--config` option.

The User CLI does not require Ledger or Archive paths on each command.

The User CLI writes machine-consumable result rows and paths to stdout.

The User CLI writes prompts and explanatory errors to stderr.

The User CLI reads an ambiguity selection from stdin.

The User CLI uses exit code `0` when the requested operation succeeds.

The User CLI uses exit code `1` when a valid operation cannot complete.

The User CLI uses exit code `2` for command syntax or invalid interactive selection.

The User CLI renders timestamps in UTC with `YYYY-MM-DDTHH:MM`.

The User CLI does not add a table header.

The User CLI separates list fields with one tab.

The User CLI does not paginate ingestion history.

The User CLI does not print canonical Domain IDs in default output.

The Operator CLI remains available for diagnostics and direct contract testing.

The User CLI calls Application Layer use cases directly.

The User CLI does not invoke the Operator CLI as a subprocess.

## Ingestion status contract

The program uses these persisted IngestionRun status values.

| Stored status | User output | Meaning |
|---|---|---|
| `running` | `[RUNNING]` | KoteKomi admitted the run and has no terminal result. |
| `captured` | `[CAPTURED]` | Source capture and representation are durable. |
| `review` | `[REVIEW]` | The candidate view and required review projections are ready. |
| `published` | `[PUBLISHED]` | KoteKomi accepted the change set and published its projections. |
| `discarded` | `[DISCARDED]` | KoteKomi rejected the set and kept published knowledge. |
| `error` | `[ERROR]` | The run cannot continue without a new user command. |

CIR-1 uses `running`, `captured`, and `error`.

CIR-5 supersedes normal successful completion at `captured` with completion at `review`.

Earlier increments use `captured` until every required review projection is ready.

Later recovery work can use `captured` to describe durable progress before review readiness.

The list timestamp identifies the IngestionRun start time.

A later review decision does not change the displayed timestamp.

## User stories

### US-CIR-01 - Ingest a deposited document

As a local user, I want to supply a deposited file path and Source URL.

I want KoteKomi to own every internal identity and pipeline choice.

```text
kotekomi ingest raw/document-1.pdf \
  --url https://example.com/document-1.pdf
```

The Source URL supplies attribution and stable Source identity.

KoteKomi does not request the Source URL.

A successful complete-program result prints one row.

```text
document-1.pdf	[REVIEW]	2026-08-24T05:01
```

Acceptance criteria:

- AC-US-01-01: The command accepts a supported deposited file and one absolute HTTPS URL.
- AC-US-01-02: The command archives the supplied bytes before model work starts.
- AC-US-01-03: The command creates one IngestionRun for each admitted execution.
- AC-US-01-04: The command exposes no canonical Domain ID.
- AC-US-01-05: The command performs no network request for the Source URL.
- AC-US-01-06: The command reaches `[REVIEW]` only after candidate readiness succeeds.

### US-CIR-02 - List ingestion history

As a local user, I want a latest-first history of admitted ingestion attempts.

```text
kotekomi ingestions list
```

Example output:

```text
document-1.pdf	[REVIEW]	2026-08-24T05:01
document-0.pdf	[ERROR]	2026-08-22T18:10
document-1.pdf	[DISCARDED]	2026-08-21T14:32
```

Acceptance criteria:

- AC-US-02-01: The command prints every IngestionRun in descending start-time order.
- AC-US-02-02: The command prints filename, status, and start timestamp.
- AC-US-02-03: The command prints one tab between fields.
- AC-US-02-04: The command prints no header and no canonical Domain ID.
- AC-US-02-05: An empty history produces empty stdout and exit code `0`.

### US-CIR-03 - Receive an automatic candidate view

As a local user, I want KoteKomi to produce a complete candidate view without guidance.

I want the candidate view to include accepted knowledge and the new ProposedChanges.

I want published knowledge to remain unchanged while I review the candidate view.

Acceptance criteria:

- AC-US-03-01: One successful ingestion creates one closed IngestionChangeSet.
- AC-US-03-02: One CandidateKnowledgeView names one base PublishedKnowledgeRevision.
- AC-US-03-03: Every candidate projection records one candidate snapshot digest.
- AC-US-03-04: Candidate construction creates no accepted Assertion or Relationship.
- AC-US-03-05: KoteKomi admits at most one active review.
- AC-US-03-06: A changed base revision makes the candidate view stale and unpublishable.

### US-CIR-04 - Walk the candidate Wiki

As a local user, I want a complete candidate Wiki in ordinary Markdown.

I want to open that Wiki with Obsidian or another userspace tool.

The ReviewWorkspace uses this stable path relative to the Archive root.

```text
review/wiki/
```

The published Wiki uses this stable path relative to the Archive root.

```text
wiki/
```

Acceptance criteria:

- AC-US-04-01: The candidate Wiki contains a coherent complete page set.
- AC-US-04-02: Candidate pages visibly identify their unpublished review state.
- AC-US-04-03: Candidate page metadata identifies the review state without Domain IDs.
- AC-US-04-04: Candidate generation leaves the published Wiki unchanged.
- AC-US-04-05: A failed candidate build leaves no half-built candidate Wiki visible.

### US-CIR-05 - List Wiki pages affected by one ingestion

As a local user, I want to identify the candidate Wiki pages affected by one filename.

```text
kotekomi ingestions changes document-1.pdf
```

When one filename matches several runs, KoteKomi prompts on stderr.

```text
Multiple ingestions match filename `document-1.pdf`, choose one to continue:

1. document-1.pdf	[REVIEW]	2026-08-24T05:01
2. document-1.pdf	[DISCARDED]	2026-08-21T14:32
>
```

The selected command writes only relative page paths to stdout.

```text
Anthropic–United_States_Department_of_Defense_dispute.md
Donald_Trump.md
Anthropic.md
```

Acceptance criteria:

- AC-US-05-01: The command matches the exact filename basename.
- AC-US-05-02: One match continues without a prompt.
- AC-US-05-03: Multiple matches use a latest-first numbered selection.
- AC-US-05-04: Selection numbers exist only for the current prompt.
- AC-US-05-05: Zero matches fail without a fuzzy filename guess.
- AC-US-05-06: The result includes candidate pages whose page inputs changed.
- AC-US-05-07: The command sorts pages by distinct inbound candidate Wiki pages.
- AC-US-05-08: The command breaks equal hub counts by relative path.
- AC-US-05-09: The command uses page input fingerprints instead of prose differences.
- AC-US-05-10: The command prints no canonical Domain ID.
- AC-US-05-11: Published and discarded runs use their retained candidate page manifest.
- AC-US-05-12: Captured and error runs fail because no candidate page manifest exists.

### US-CIR-06 - Test the candidate Wiki through chat

As a local user, I want to ask questions against the same candidate view.

```text
kotekomi wiki chat
```

The command uses the active CandidateKnowledgeView when an active review exists.

The command uses the current PublishedKnowledgeRevision otherwise.

Acceptance criteria:

- AC-US-06-01: The chat session states whether it uses candidate or published knowledge.
- AC-US-06-02: Every answer receipt records the selected knowledge-view digest.
- AC-US-06-03: Candidate chat uses the candidate retrieval and graph projections.
- AC-US-06-04: Chat answers cite accepted or proposed evidence records.
- AC-US-06-05: Chat creates no accepted intelligence.

### US-CIR-07 - Generate a Daily Briefing preview

As a local user, I want a Daily Briefing from the active knowledge view.

```text
kotekomi briefing create
```

A candidate result prints one relative path.

```text
review/briefings/daily_briefing_2026-08-24T0524.md
```

A published result prints one relative path.

```text
briefings/daily_briefing_2026-08-24T0524.md
```

Acceptance criteria:

- AC-US-07-01: The command uses the active candidate view when one exists.
- AC-US-07-02: The command uses the published view when no active review exists.
- AC-US-07-03: A candidate Briefing visibly identifies its unpublished state.
- AC-US-07-04: A candidate Briefing does not enter published Briefing ancestry.
- AC-US-07-05: The command prints only the generated relative path.
- AC-US-07-06: Publication regenerates a reviewed candidate Briefing from accepted state.

### US-CIR-08 - Publish one ingestion

As a local user, I want to publish the complete ingestion after holistic review.

```text
kotekomi ingestions publish document-1.pdf
```

A successful result prints the selected ingestion row.

```text
document-1.pdf	[PUBLISHED]	2026-08-24T05:01
```

Acceptance criteria:

- AC-US-08-01: The command accepts only an IngestionRun in `[REVIEW]`.
- AC-US-08-02: The command requires the configured local reviewer identity.
- AC-US-08-03: The command verifies the base PublishedKnowledgeRevision is current.
- AC-US-08-04: The command validates the complete IngestionChangeSet before accepted writes.
- AC-US-08-05: The command accepts every ProposedChange or accepts none.
- AC-US-08-06: Each accepted record references review provenance.
- AC-US-08-07: KoteKomi regenerates published projections from accepted state.
- AC-US-08-08: KoteKomi removes the ReviewWorkspace after publication completes.
- AC-US-08-09: A successful command leaves no active review.
- AC-US-08-10: Duplicate filenames use the common interactive selector.

### US-CIR-09 - Discard one ingestion

As a local user, I want to discard the complete ingestion after holistic review.

```text
kotekomi ingestions discard document-1.pdf \
  --reason "Contract values were extracted incorrectly"
```

A successful result prints the selected ingestion row.

```text
document-1.pdf	[DISCARDED]	2026-08-24T05:01
```

Acceptance criteria:

- AC-US-09-01: The command accepts only an IngestionRun in `[REVIEW]`.
- AC-US-09-02: The command records the configured reviewer, timestamp, and reason.
- AC-US-09-03: The command rejects every pending ProposedChange in the change set.
- AC-US-09-04: The command creates no accepted intelligence record.
- AC-US-09-05: The command leaves the PublishedKnowledgeRevision unchanged.
- AC-US-09-06: The command leaves the published Wiki unchanged.
- AC-US-09-07: The command removes the ReviewWorkspace.
- AC-US-09-08: A successful command leaves no active review.
- AC-US-09-09: Duplicate filenames use the common interactive selector.

### US-CIR-10 - Preserve audit history and future correction paths

As a local user, I want publish and discard decisions to remain auditable.

I want future corrections to change canonical knowledge instead of generated Markdown.

Acceptance criteria:

- AC-US-10-01: Publish and discard retain Source and Document records.
- AC-US-10-02: Publish and discard retain evidence, model runs, and coverage records.
- AC-US-10-03: Publish and discard retain ProposedChanges and their decision status.
- AC-US-10-04: A rejected ProposedChange remains replayable.
- AC-US-10-05: A future correction can create a human-authored ProposedChange.
- AC-US-10-06: A correction can supersede an Assertion without rewriting its history.
- AC-US-10-07: A correction triggers full projection regeneration.
- AC-US-10-08: No correction command edits Wiki Markdown as canonical state.

## Durable invariants

### Authority

The Ledger and Archive remain canonical.

Accepted Ledger records define published intelligence.

Source captures, model runs, evidence, and ProposedChanges remain permanent audit records.

A CandidateKnowledgeView grants no accepted status to ProposedChanges.

A Wiki projection never becomes authoritative.

A Briefing never becomes authoritative.

A chat answer never becomes authoritative.

### One candidate state

KoteKomi has one current PublishedKnowledgeRevision.

KoteKomi has zero or one active CandidateKnowledgeView.

One active CandidateKnowledgeView belongs to one IngestionRun.

One active CandidateKnowledgeView contains one closed IngestionChangeSet.

The change set contains every ProposedChange produced by the admitted ingestion.

Every proposed reference resolves against the base revision or the same change set.

KoteKomi freezes the change set before it builds review projections.

A rerun that changes the proposal set creates a new IngestionRun and change set.

A second ingestion cannot enter candidate creation while an active review exists.
The ingest command reports the active filename and requires publish or discard first.

### View consistency

Every candidate projection records the same candidate snapshot digest.

Every candidate projection records the same base PublishedKnowledgeRevision.

Every candidate projection records the same IngestionChangeSet.

The candidate snapshot digest covers the base revision, frozen change set, and view policy.

A candidate query rejects a projection with a different digest.

A publish command rejects a stale candidate view.

### Whole-ingestion decision

The user publishes or discards one complete IngestionChangeSet.

Publish changes every pending ProposedChange in the set through one decision.

Discard changes every pending ProposedChange in the set through one decision.

A partial decision is an error.

Individual edit and decision workflows remain outside this program.

### Projection lifecycle

KoteKomi builds each Wiki as a complete projection.

KoteKomi does not mutate individual Wiki pages as canonical operations.

KoteKomi publishes a projection only after the complete build passes validation.

KoteKomi preserves the last known-good published projection during a failed build.

KoteKomi removes candidate projections after publish or discard.
KoteKomi retains candidate build and page-change manifests after cleanup.

KoteKomi can delete and rebuild every projection from canonical state.

### Change attribution

A Wiki page manifest records one input fingerprint for each page.

The input fingerprint depends on canonical records and the renderer contract.

The input fingerprint does not depend only on generated Markdown bytes.

An ingestion affects a page when its candidate input fingerprint differs from its base fingerprint.

The page manifest records the distinct inbound page count from the candidate Wiki.

### Human-facing identity

The User CLI resolves ingestions through exact filenames and interactive selection.
The changes, publish, and discard commands use the same filename selector.

The User CLI keeps canonical IDs inside Application Layer results and audit records.

The User CLI uses relative generated paths for userspace tools.

The User CLI never asks the user to copy a canonical ID between commands.

### Future human corrections

A human correction enters the same proposal and review architecture.

A correction of a model misread keeps the original Document as evidence.

The review provenance identifies the human who corrected the interpretation.

New human knowledge uses an explicit human-authored Source or contribution record.

A successor Assertion preserves the prior Assertion and names its predecessor.

## Target architecture

```text
Local user
    |
    v
User CLI Pipeline
    |
    v
Ingestion and review use cases
    |
    +---------------------> Ledger + Archive
    |                         accepted knowledge
    |                         audit records
    |
    v
CandidateKnowledgeView
    |
    +----------+-----------+-----------+-----------+
    |          |           |           |
    v          v           v           v
Wiki       Retrieval     Briefing     Chat
projector  projectors    generator    session
    |          |           |           |
    +----------+-----------+-----------+
               |
               v
        ReviewWorkspace
               |
        publish or discard
               |
               v
     published projections or cleanup
```

The Application Layer owns IngestionRun transitions.

The Application Layer owns IngestionChangeSet closure.

The Application Layer owns CandidateKnowledgeView selection.

The Application Layer owns publish and discard transaction intent.

Adapters store records and generated files.

Pipelines expose the User CLI.

Projectors consume one explicit knowledge view.

## Target end-to-end flow

```text
published revision S0
    |
    | kotekomi ingest
    v
IngestionRun R1
    |
    +-> archived Document and evidence
    +-> model runs and coverage
    +-> ProposedChanges
    |
    v
IngestionChangeSet C1
    |
    v
candidate view V1 = S0 + C1
    |
    +-> review/wiki/
    +-> candidate retrieval projections
    +-> review/briefings/
    +-> candidate chat
    |
    +------ publish ------> accepted revision S1 ------> wiki/ and briefings/
    |
    +------ discard ------> accepted revision S0 ------> existing projections
```

## Agile delivery map

Each child deliverable is independently shippable and independently revertible.

Only one child TDD must be active for implementation at one time.

### CIR-1 - User Ingestion Run MVP

Working result:

A user runs `kotekomi ingest <path> --url <URL>` through the User CLI.

KoteKomi archives and represents the deposited file through existing use cases.

KoteKomi records one durable IngestionRun for each admitted attempt.

The command ends in `[CAPTURED]` or `[ERROR]`.

A user lists all attempts with `kotekomi ingestions list`.

This slice establishes user-facing identity, history, output, and retry contracts.

User stories:

- US-CIR-01.
- US-CIR-02.

Document:

[CIR-1 User Ingestion Run MVP](2026-08-24-user-ingestion-run-mvp.md)

### CIR-2 - Automatic Extraction and Change Set

Working result:

The ingest command continues from accepted representation through bounded model work.

KoteKomi records coverage, ProposedChanges, and one closed IngestionChangeSet.

KoteKomi allows at most one open IngestionChangeSet.

A successful run remains `[CAPTURED]` until review projections exist.

User stories:

- US-CIR-01.
- US-CIR-03.
- US-CIR-10.

Detailed TDD:

[CIR-2 Automatic Extraction and Change Set](2026-08-24-automatic-extraction-change-set.md)

### CIR-3 - Candidate Knowledge View

Status:

The original CIR-3 design is superseded.

HP-7 expanded the candidate record set to Actors, Organizations, Events, and Assertions.

HP-8 established the complete document-scoped IngestionChangeSet.

CIR-4 now owns the first bounded CandidateKnowledgeView as part of a visible Wiki result.

User stories:

- US-CIR-03.
- US-CIR-06.
- US-CIR-07.

Detailed TDD:

[CIR-3 Candidate Knowledge View](2026-08-25-cir-3-candidate-knowledge-view.md)

### CIR-4 - Wiki Projection MVP

Working result:

KoteKomi generates a complete deterministic Candidate Wiki for one closed ingestion.

The Candidate Wiki combines referenced accepted records with pending candidate records.

The Wiki projector records page input fingerprints, citations, and a complete build manifest.

The user can open `review/wiki/` with ordinary Markdown tools.

The command leaves accepted intelligence, published Wiki files, and ingestion status unchanged.

User stories:

- US-CIR-04.
- US-CIR-10.

Detailed TDD:

[CIR-4 Deterministic Candidate Wiki MVP](2026-09-04-deterministic-candidate-wiki-mvp.md)

### CIR-5 - Candidate Wiki and Change Inspection

Working result:

KoteKomi promotes one built CandidateKnowledgeView into the active review lifecycle.

The published Wiki remains unchanged.

A successful candidate build changes the run to `[REVIEW]`.

The user runs `kotekomi ingestions changes <filename>`.

The command returns affected page paths in deterministic hub order.

User stories:

- US-CIR-04.
- US-CIR-05.

Detailed TDD:

Write after CIR-4 implementation evidence exists.

### CIR-6 - Whole-Ingestion Publish and Discard

Working result:

The user publishes or discards one complete IngestionChangeSet.

Publish accepts all changes and rebuilds the published Wiki.

Discard preserves accepted knowledge and the published Wiki.

Both decisions remove the ReviewWorkspace.

User stories:

- US-CIR-08.
- US-CIR-09.
- US-CIR-10.

Detailed TDD:

Write after CIR-5 implementation evidence exists.

### CIR-7 - Candidate Daily Briefing

Working result:

`kotekomi briefing create` uses the active CandidateKnowledgeView by default.

The command returns one candidate or published Markdown path.

Publish regenerates a reviewed candidate Briefing from accepted state.

User stories:

- US-CIR-07.
- US-CIR-10.

Detailed TDD:

Write after CIR-6 implementation evidence exists.

### CIR-8 - Candidate Wiki Chat

Working result:

`kotekomi wiki chat` uses the active CandidateKnowledgeView by default.

Answer receipts identify the view and retrieval manifests.

Chat creates no accepted intelligence.

User stories:

- US-CIR-06.
- US-CIR-10.

Detailed TDD:

Write after CIR-7 implementation evidence exists.

### CIR-9 - Publication Safety and Program Closeout

Working result:

KoteKomi detects stale candidate views and incomplete projection builds.

KoteKomi preserves the last known-good published projection.

KoteKomi reconciles interrupted publish and cleanup operations.

The canonical scenario proves discard, reingest, publish, rebuild, Briefing, and chat paths.

User stories:

- US-CIR-01 through US-CIR-10.

Detailed TDD:

Write after CIR-8 implementation evidence exists.

## Future TDD links

This section becomes the stable index for child TDDs.

| Deliverable | Title | TDD |
|---|---|---|
| CIR-1 | User Ingestion Run MVP | [CIR-1 TDD](2026-08-24-user-ingestion-run-mvp.md) |
| CIR-2 | Automatic Extraction and Change Set | [CIR-2 TDD](2026-08-24-automatic-extraction-change-set.md) |
| CIR-3 | Candidate Knowledge View | Superseded by the CIR-4 read model. |
| CIR-4 | Deterministic Candidate Wiki MVP | [CIR-4 TDD](2026-09-04-deterministic-candidate-wiki-mvp.md) |
| CIR-5 | Candidate Wiki and Change Inspection | Add link after CIR-4 evidence exists. |
| CIR-6 | Whole-Ingestion Publish and Discard | Add link after CIR-5 evidence exists. |
| CIR-7 | Candidate Daily Briefing | Add link after CIR-6 evidence exists. |
| CIR-8 | Candidate Wiki Chat | Add link after CIR-7 evidence exists. |
| CIR-9 | Publication Safety and Program Closeout | Add link after CIR-8 evidence exists. |

A child TDD can split when repository evidence triggers the TDD sizing gate.

A split child TDD must retain the parent deliverable ID with a decimal suffix.

## Program acceptance criteria

### User boundary

- AC-PROG-UI-01: No User CLI workflow requires a canonical Domain ID.
- AC-PROG-UI-02: User CLI list output remains valid tab-separated text.
- AC-PROG-UI-03: Prompts and explanations do not contaminate result stdout.
- AC-PROG-UI-04: Exact filename selection resolves duplicate filename history.
- AC-PROG-UI-05: Generated results use relative paths that userspace tools can open.

### Authority boundary

- AC-PROG-AUTH-01: Model output reaches accepted state only through review.
- AC-PROG-AUTH-02: Candidate projection creation changes no accepted record.
- AC-PROG-AUTH-03: Discard changes no accepted intelligence record.
- AC-PROG-AUTH-04: Publish accepts the complete change set or accepts none.
- AC-PROG-AUTH-05: Rejected ProposedChanges remain in the Ledger.
- AC-PROG-AUTH-06: Every accepted change references review provenance.

### View boundary

- AC-PROG-VIEW-01: All candidate projections share one candidate snapshot digest.
- AC-PROG-VIEW-02: A stale candidate view cannot be published.
- AC-PROG-VIEW-03: KoteKomi allows at most one active review.
- AC-PROG-VIEW-04: Candidate pages visibly identify their review state.
- AC-PROG-VIEW-05: Candidate chat states its selected view.

### Projection boundary

- AC-PROG-PROJ-01: A failed candidate build does not change the published Wiki.
- AC-PROG-PROJ-02: A failed published build preserves the last known-good Wiki.
- AC-PROG-PROJ-03: Publish rebuilds generated files from accepted Ledger state.
- AC-PROG-PROJ-04: Discard removes candidate files.
- AC-PROG-PROJ-05: Deleted projections rebuild to equivalent manifests and content.
- AC-PROG-PROJ-06: Page change detection uses canonical input fingerprints.

### Audit boundary

- AC-PROG-AUDIT-01: Every admitted ingestion attempt has one IngestionRun.
- AC-PROG-AUDIT-02: Retries create new IngestionRuns and reuse canonical records when valid.
- AC-PROG-AUDIT-03: Publish and discard preserve Source and Document records.
- AC-PROG-AUDIT-04: Publish and discard preserve model and evidence records.
- AC-PROG-AUDIT-05: Every review decision records reviewer, time, and reason or decision basis.
- AC-PROG-AUDIT-06: Historical projections identify their source knowledge revision.

## Testing and validation

### Test layers

Domain Core tests verify record validation and allowed status transitions.

Application tests use fake Ports to verify decisions and transaction intent.

Adapter tests verify SQLite and Archive contracts with disposable fixtures.

Pipeline tests run the User CLI against disposable Ledger and Archive paths.

Projection tests compare manifests, page inputs, generated paths, and visible state labels.

Briefing tests verify visible preview labels and structured citation registries.

Chat tests verify view selection, evidence resolution, and answer receipts.

### Deterministic model boundary

Ordinary CI uses a deterministic model-runtime fixture.

The fixture emits schema-valid ProposedChanges and explicit invalid cases.

CI does not depend on exact prose from a live model.

CI treats accepted records, evidence links, manifests, and status transitions as the oracle.

A local model smoke test can supplement the deterministic suite.

A local model smoke test cannot replace the deterministic suite.

### Canonical scenario

Every child TDD uses this deposited PDF scenario.

```text
scenario_id: anthropic-dod-dispute-v1
local fixture: raw/Anthropic-United_States_Department_of_Defense_dispute.pdf
source URL: https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute
```

The local fixture remains untracked.

The committed scenario contract preserves the expected digest and page count.

A verifier rejects a missing fixture.

A verifier rejects a digest or page-count mismatch.

The scenario never fetches or regenerates the Source URL.

The Source URL supplies identity and attribution only.

### Increment validation

Each child TDD adds one direct conformance script.

The script name uses `scripts/verify_cir<N>_canonical.py`.

Each child TDD adds one immutable suite identity.

The suite identity uses `cir-<N>-v1`.

Each child suite reruns every implemented prior CIR suite.

A correction creates a new suite version.

A correction does not rewrite a closed suite.

### CIR-1 closeout

CIR-1 must prove:

```text
clean Ledger and Archive
    -> User CLI ingest
    -> durable Source, Document, and representation
    -> durable IngestionRun
    -> User CLI ingestion history
```

The closeout must repeat the same file and URL.

The closeout must prove two IngestionRuns and reused canonical records.

The closeout must include one typed failed attempt.

### Complete-program closeout

The final cumulative scenario uses two clean-workspace tracks.

Track A proves discard.

```text
ingest
    -> [REVIEW]
    -> candidate Wiki
    -> changed-page list
    -> candidate Daily Briefing
    -> candidate chat
    -> discard
    -> unchanged accepted revision
    -> unchanged published Wiki
    -> empty ReviewWorkspace
```

Track B proves publish.

```text
ingest
    -> [REVIEW]
    -> candidate Wiki
    -> changed-page list
    -> candidate Daily Briefing
    -> candidate chat
    -> publish
    -> new accepted revision
    -> regenerated published Wiki
    -> regenerated published Briefing
    -> empty ReviewWorkspace
```

The final suite deletes derived projections and rebuilds them.

The final suite compares the rebuilt projection manifests and page input fingerprints.

The final suite verifies default user output contains no canonical Domain ID.

The final suite runs without network access.

### Manual validation

A human closeout uses the locked PDF in `raw/`.

The human opens `review/wiki/` in Obsidian or another Markdown reader.

The human follows links from the changed pages.

The human creates and reads a candidate Daily Briefing.

The human uses the candidate chat session.

The human runs discard once in a clean workspace.

The human reruns ingestion and runs publish in another clean workspace.

The human confirms `review/` is absent after both decisions.

### Check plan

Every child TDD updates `docs/CHECK_PLAN.md`.

The check plan records the exact unit, contract, integration, and canonical commands.

A missing local canonical fixture produces a visible failure.

A missing fixture does not count as a passing or skipped closeout.

## Contract ownership and change control

This program owns the User CLI command names and default output shapes.

This program owns IngestionRun lifecycle terms.

This program owns the one-active-review rule.

This program owns CandidateKnowledgeView consistency rules.

This program owns whole-ingestion publish and discard semantics.

This program owns ReviewWorkspace path semantics.

Child TDDs own the smallest contracts required by their working result.

A later child TDD can extend an earlier status transition explicitly.

A later child TDD cannot rewrite historical IngestionRuns or decisions.

A later child TDD cannot make a projection authoritative.

A later child TDD cannot expose canonical Domain IDs as required user input.

The program envelope changes only when a durable invariant or delivery boundary changes.
