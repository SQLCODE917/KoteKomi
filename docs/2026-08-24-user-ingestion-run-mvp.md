# CIR-1: User Ingestion Run MVP

- Status: Accepted
- Program: `candidate-ingestion-review`
- Deliverable ID: `CIR-1`
- Repository baseline: `main` at `e901698`
- Program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Depends on: [Deposited-Source Walking Skeleton](2026-08-13-live-source-walking-skeleton.md)
- Canonical suite: `cir-1-v1`

## 1. Context & Problem

KoteKomi already archives and represents a deposited PDF, Markdown file, or text file.

The existing `source add-file` Pipeline requires a file path and Source URL.

That command prints Source, Document, representation, and ProvenanceActivity identifiers.

The command does not create a durable record for each user attempt.

A failed attempt can disappear before the user can list or select it.

Repeated attempts against one filename cannot be distinguished through user-known values.

Later candidate review work needs one durable identity for each admitted ingestion attempt.

Existing ProcessingAttempt records identify one processor task after Document identity exists.

Existing AnalysisRun records identify analysis over an accepted representation.

Neither record spans the complete user command before Source capture.

This MVP adds that identity before it adds model extraction or candidate projections.

**Admitted ingestion** means a parsed command with a filename after configuration and Ledger open.

**IngestionRun** means one durable record for one admitted ingestion.

**Display filename** means the basename of the requested file path.

**Requested Source URL** means the exact URL string supplied by the user.

**Normalized Source URL** means the existing normalized absolute HTTPS Source URL.

### Primary end-to-end flow

1. The user runs `kotekomi ingest <path> --url <URL>`.
2. The Pipeline creates one `running` IngestionRun before file and URL validation.
3. The Pipeline calls the existing deposited-source Application use cases.
4. The existing use cases archive exact bytes and create or reuse the representation.
5. The Pipeline records `captured` or `error` as the terminal MVP status.
6. The user runs `kotekomi ingestions list` and sees every IngestionRun.

```text
user path and URL
    -> running IngestionRun
    -> existing Source capture and representation
    -> captured or error IngestionRun
    -> latest-first user history
```

CIR-1 deliberately stops at `captured`.

CIR-2 will extend successful ingestion through model work and candidate creation.

The User CLI setup path is `kotekomi init`.

The command creates user-local configuration and initializes the Ledger and Archive.

## 2. Goals

- A user can archive and represent one deposited file without supplying an internal identifier.
- A user can see one durable history row for each admitted ingestion.
- A retry creates a new IngestionRun while existing canonical identity rules remain unchanged.
- A failed attempt remains visible with a safe typed failure.
- Default User CLI output remains suitable for ordinary shell tools.
- Later TDDs can attach candidate state and decisions to one stable IngestionRun.

## Non-goals

CIR-1 does not run bounded model extraction.

CIR-1 does not create ProposedChanges.

CIR-1 does not create an IngestionChangeSet.

CIR-1 does not create a CandidateKnowledgeView.

CIR-1 does not generate a Wiki projection.

CIR-1 does not generate a Briefing.

CIR-1 does not publish or discard an ingestion.

CIR-1 does not resolve duplicate filenames interactively.

CIR-1 does not reconcile an interrupted `running` IngestionRun.

CIR-1 does not remove or rename the Operator CLI command `source add-file`.

## Contract ownership

CIR-1 owns these contracts.

```text
candidate_review.ingestion_run.v1
candidate_review.user_ingest_cli.v1
candidate_review.ingestion_history_cli.v1
candidate_review.ingestion_status_display.v1
```

CIR-1 consumes these contracts.

```text
deposited Source capture
stable Source identity from normalized Source URL
immutable Document identity from exact bytes
versioned Document representation
Archive exact-byte storage
SQLite Ledger transactions
```

CIR-1 extends no accepted intelligence contract.

## 3. Requirements

### User CLI Pipeline

- C1-CLI-01: The Pipeline exposes `kotekomi ingest <path> --url <URL>`.
- C1-CLI-02: The Pipeline exposes `kotekomi ingestions list`.
- C1-CLI-03: The ingest command accepts `.pdf`, `.md`, and `.txt` suffixes.
- C1-CLI-04: The ingest command reads Ledger and Archive paths from configuration.
- C1-CLI-04A: The Pipeline exposes `kotekomi init` for first-run user configuration and storage.
- C1-CLI-04B: Configuration lookup uses explicit `--config`, `./kotekomi.toml`, then the XDG-style user config.
- C1-CLI-04C: Missing configuration prints an exact setup remedy and creates no IngestionRun.
- C1-CLI-04D: The list command loads storage configuration without deriving a BuildIdentity.
- C1-CLI-05: The ingest command performs no request to the Source URL.
- C1-CLI-06: A captured run writes one ingestion row to stdout.
- C1-CLI-07: An error run writes no result row to stdout.
- C1-CLI-08: An error run writes one safe explanation to stderr.
- C1-CLI-09: A captured run returns exit code `0`.
- C1-CLI-10: An error run returns exit code `1`.
- C1-CLI-11: Invalid command syntax returns exit code `2`.
- C1-CLI-12: Invalid command syntax creates no IngestionRun.
- C1-CLI-13: Default output contains no canonical Domain ID.
- C1-CLI-14: The User CLI calls Application Layer use cases directly.
- C1-CLI-15: The User CLI does not invoke `source add-file` as a subprocess.

### IngestionRun Application use cases

- C1-RUN-01: The Domain Core defines the IngestionRun record.
- C1-RUN-02: One admitted ingestion creates one new IngestionRun.
- C1-RUN-03: A new IngestionRun starts with status `running`.
- C1-RUN-04: The start use case stores the requested path and requested Source URL.
- C1-RUN-05: The start use case derives and stores the display filename.
- C1-RUN-06: The start use case stores one UTC start timestamp.
- C1-RUN-07: The Pipeline starts the run before file existence, suffix, and URL validation.
- C1-RUN-08: A successful representation changes `running` to `captured`.
- C1-RUN-09: An expected operation failure changes `running` to `error`.
- C1-RUN-10: A terminal transition stores one UTC completion timestamp.
- C1-RUN-11: A terminal IngestionRun cannot return to `running`.
- C1-RUN-12: A captured run stores the normalized Source URL.
- C1-RUN-13: A captured run links the Source, Document, representation, and provenance activity.
- C1-RUN-14: An error run stores a failure stage and failure code.
- C1-RUN-15: An error run can store canonical links created before the failure.
- C1-RUN-16: A safe failure message contains no document text.
- C1-RUN-17: Repeating one path and URL creates another IngestionRun.
- C1-RUN-18: IngestionRun creation changes no accepted intelligence record.
- C1-RUN-19: Terminal transition uses the persisted `running` state as a precondition.
- C1-RUN-20: A conflicting second terminal transition fails explicitly.

### Deposited-source composition

- C1-CAP-01: The Pipeline uses the existing Source URL normalization rule.
- C1-CAP-02: The Pipeline uses the existing deposited-source capture use cases.
- C1-CAP-03: The Pipeline archives exact file bytes before representation parsing.
- C1-CAP-04: Identical Source URL and bytes reuse the existing Source and Document.
- C1-CAP-05: Changed bytes at one Source URL create a new Document revision.
- C1-CAP-06: A successful run stores the resulting representation identity internally.
- C1-CAP-07: A PDF blocker changes the IngestionRun to `error`.
- C1-CAP-08: A PDF blocker preserves committed Source capture records.
- C1-CAP-09: A missing file changes the IngestionRun to `error`.
- C1-CAP-10: An unsupported suffix changes the IngestionRun to `error`.
- C1-CAP-11: An invalid Source URL changes the IngestionRun to `error`.
- C1-CAP-12: Deposited-source outcomes remain independently testable through existing use cases.

### IngestionRun Port and Adapter

- C1-STORE-01: The Application Layer defines an IngestionRun repository Port.
- C1-STORE-02: The Port creates one `running` record atomically.
- C1-STORE-03: The Port applies one guarded terminal transition atomically.
- C1-STORE-04: The Port loads one IngestionRun by internal identity.
- C1-STORE-05: The Port lists every IngestionRun.
- C1-STORE-06: The SQLite Adapter persists every IngestionRun field.
- C1-STORE-07: The SQLite Adapter preserves UTC timestamp precision.
- C1-STORE-08: The SQLite Adapter orders history by start timestamp descending.
- C1-STORE-09: The SQLite Adapter breaks equal start times by internal identity.
- C1-STORE-10: Ledger initialization creates the IngestionRun storage.
- C1-STORE-11: IngestionRun storage remains outside accepted record iteration.
- C1-STORE-12: Derived projectors do not consume IngestionRun records as intelligence.

### History presentation

- C1-HIST-01: The list command prints every IngestionRun.
- C1-HIST-02: The list command prints no header.
- C1-HIST-03: Each row contains display filename, status, and start timestamp.
- C1-HIST-04: Each row uses one tab between fields.
- C1-HIST-05: The timestamp format is `YYYY-MM-DDTHH:MM`.
- C1-HIST-06: The timestamp represents UTC.
- C1-HIST-07: The list command preserves repository order.
- C1-HIST-08: The list command does not paginate.
- C1-HIST-09: The list command prints empty stdout when no runs exist.
- C1-HIST-10: The list command returns exit code `0` for an empty history.
- C1-HIST-11: The list command renders `running` as `[RUNNING]`.
- C1-HIST-12: The list command renders `captured` as `[CAPTURED]`.
- C1-HIST-13: The list command renders `error` as `[ERROR]`.
- C1-HIST-14: The list command prints no requested path or Source URL.
- C1-HIST-15: The list command prints no canonical Domain ID.

## 4. Proposed Architecture

The User CLI Pipeline owns command parsing and stream presentation.

The Application Layer owns IngestionRun creation and status transitions.

The existing deposited-source use cases own Source capture and representation decisions.

The IngestionRun repository Port owns persisted workflow history access.

The SQLite Adapter stores IngestionRun records in the Ledger.

The Archive and Ledger Adapters preserve existing Source and Document behavior.

```text
User
  |
  v
User CLI Pipeline
  |
  +------> IngestionRun use cases ------> IngestionRun repository
  |                                             |
  |                                             v
  |                                          SQLite
  |
  +------> Deposited-source use cases
                |
                +------> Archive + Ledger
                |
                +------> PDF parser
```

The Pipeline uses separate Application write units for run start and run completion.

The deposited-source write unit retains its existing transaction behavior.

A failure after run start cannot erase the IngestionRun start record.

A representation blocker cannot erase a committed Source capture.

### Configuration and BuildIdentity

`kotekomi init` creates `~/.config/kotekomi/kotekomi.toml` by default.

`XDG_CONFIG_HOME` replaces the default configuration root.

The default Ledger and Archive live below `~/.local/share/kotekomi`.

`XDG_DATA_HOME` replaces the default data root.

An explicit `--config` path uses sibling `data/kotekomi.db` and `data/archive` paths by default.

The generated configuration records the Ledger path, Archive path, and representation policy version.

The Pipeline derives package version, Git revision, and code digest from the executing Git checkout.

The code digest covers project metadata and every package source file.

The Pipeline fails before admission when it cannot derive that identity.

The list command does not derive an identity because it does not create authoritative processing state.

## 5. Key Interactions

### Captured ingestion

```text
User -> User CLI: ingest path and URL
User CLI -> Run use case: create running IngestionRun
Run use case -> Ledger: persist running IngestionRun
User CLI -> Source use case: capture and represent deposited file
Source use case -> Archive and Ledger: commit canonical results
User CLI -> Run use case: complete IngestionRun as captured
Run use case -> Ledger: persist guarded terminal transition
User CLI -> User: print captured row
```

### Failed ingestion

```text
User -> User CLI: ingest path and URL
User CLI -> Run use case: create running IngestionRun
Run use case -> Ledger: persist running IngestionRun
User CLI -> Source use case: attempt capture or representation
Source use case -> User CLI: return typed failure
User CLI -> Run use case: complete IngestionRun as error
Run use case -> Ledger: persist guarded terminal transition
User CLI -> User: print safe error to stderr
```

## 6. Data Model

CIR-1 adds one Domain Core record.

```text
IngestionRun
    ingestion_run_id
    requested_path
    display_filename
    requested_source_url
    normalized_source_url?
    status
    started_at
    completed_at?
    source_id?
    document_id?
    representation_id?
    provenance_activity_id?
    failure_stage?
    failure_code?
    safe_failure_message?
```

The `status` vocabulary for CIR-1 is:

```text
running
captured
error
```

A `running` record has no completion timestamp.

A `running` record has no failure fields.

A `captured` record has one completion timestamp.

A `captured` record has all four canonical links.

A `captured` record has one normalized Source URL.

A `captured` record has no failure fields.

An `error` record has one completion timestamp.

An `error` record has one failure stage and one failure code.

An `error` record can contain canonical links from committed earlier stages.

An `error` record can omit the normalized Source URL when URL validation failed.

An IngestionRun is a canonical workflow audit record.

An IngestionRun is not an accepted Assertion, Relationship, Outcome, or ProposedChange.

Projectors do not treat an IngestionRun as knowledge.

The repository reads history by descending `started_at`.

The repository uses internal identity as the deterministic tie-breaker.

## 7. APIs / Interfaces

### User CLI

The ingest command is:

```text
kotekomi ingest <path> --url <SOURCE_URL>
```

The setup command is:

```text
kotekomi init
```

The history command is:

```text
kotekomi ingestions list
```

The captured output row is:

```text
<display_filename>\t[CAPTURED]\t<UTC_YYYY-MM-DDTHH:MM>
```

The history row is:

```text
<display_filename>\t[<DISPLAY_STATUS>]\t<UTC_YYYY-MM-DDTHH:MM>
```

The ingest command writes the captured row to stdout only after terminal persistence succeeds.

The ingest command writes a safe error explanation to stderr after error persistence succeeds.

The list command writes only history rows to stdout.

### Application Layer

The Application Layer exposes explicit DTOs for these operations.

```text
start one IngestionRun
complete one IngestionRun as captured
complete one IngestionRun as error
list IngestionRuns
```

The start input carries the requested path and requested Source URL.

The start use case obtains its timestamp from the injected UTC clock.

The captured input carries the normalized Source URL and canonical result links.

The error input carries the failure stage, failure code, and safe failure message.

Each terminal use case obtains its completion timestamp from the injected UTC clock.

The list result carries already ordered IngestionRun records.

The DTOs carry canonical identities only inside Application and Adapter boundaries.

### Failure vocabulary

CIR-1 defines at least these failure codes.

```text
file_not_found
unsupported_file_type
source_url_invalid
archive_initialization_failed
source_capture_failed
document_representation_blocked
document_representation_failed
ingestion_run_transition_conflict
```

The failure stage vocabulary is:

```text
admission
source_validation
archive
source_capture
document_representation
run_persistence
```

Expected user failures do not produce an uncaught traceback.

## 8. Behavior & Domain Rules

### Admission

Argparse rejects a missing path or missing `--url` before admission.

The Pipeline rejects a requested path without a display filename before admission.

A syntax or path-shape rejection creates no IngestionRun.

The Pipeline loads configuration before admission.

A configuration or Ledger-open failure creates no IngestionRun.

The Pipeline admits the command after configuration and Ledger access succeed.

The Pipeline starts the IngestionRun before it reads the requested file.

### Capture result

The Pipeline maps a created or reused acceptable representation to `captured`.

The Pipeline maps a blocked PDF representation to `error`.

The Pipeline maps a failed representation to `error`.

The Pipeline maps a validation failure to `error`.

The Pipeline preserves partial canonical links returned by a committed capture stage.

### Retry identity

Every admitted command creates a new IngestionRun.

Canonical Source and Document identity remain content and URL based.

The IngestionRun identity does not replace Source or Document identity.

Two runs can link to the same Source, Document, representation, and provenance activity.

A changed file can link a later run to a new Document revision.

### Terminal transition

Only a persisted `running` record can enter a terminal state.

A terminal transition compares the expected current status.

An identical repeated terminal request returns the persisted terminal record.

A conflicting terminal request fails with `ingestion_run_transition_conflict`.

### Interrupted run

A command crash can leave an IngestionRun in `running`.

The list command displays that run as `[RUNNING]`.

CIR-1 performs no automatic timeout or reconciliation.

CIR-9 will define interrupted-run reconciliation.

### Stream behavior

The ingest success path writes one row to stdout.

The ingest failure path writes no row to stdout.

The ingest failure path writes one explanation to stderr.

The list command writes only rows to stdout.

Default output contains no requested URL, requested path, or canonical Domain ID.

### Timestamp behavior

The Application Layer receives an injected UTC clock.

The start use case stores the full clock precision.

The list presenter truncates the displayed value to minutes.

The presenter does not round the displayed value.

The repository sorts by full stored precision.

### Existing Operator CLI

The existing `source add-file` command remains available.

The new User CLI does not parse the text output of `source add-file`.

The new User CLI and Operator CLI share Application Layer capture use cases.

## 9. Acceptance Criteria

### Domain Core

- AC-C1-RUN-01: Domain tests accept each valid CIR-1 IngestionRun state.
- AC-C1-RUN-02: Domain tests reject invalid timestamp and status combinations.
- AC-C1-RUN-03: Domain tests reject missing captured canonical links.
- AC-C1-RUN-04: Domain tests reject missing error stage or code.
- AC-C1-RUN-05: Domain tests accept partial canonical links on an error record.
- AC-C1-RUN-06: Domain tests reject a transition from one terminal status to another.

### Application Layer

- AC-C1-APP-01: Fake-Port tests prove start creates one `running` record.
- AC-C1-APP-02: Fake-Port tests prove captured completion stores every result link.
- AC-C1-APP-03: Fake-Port tests prove error completion stores a safe typed failure.
- AC-C1-APP-04: Fake-Port tests prove a conflicting terminal transition fails.
- AC-C1-APP-05: Fake-Port tests prove each retry creates a new IngestionRun.
- AC-C1-APP-06: Fake-Port tests prove history order passes through unchanged.
- AC-C1-APP-07: Application tests prove no IngestionRun operation writes accepted intelligence.

### SQLite Adapter

- AC-C1-STORE-01: Migration tests create IngestionRun storage in a clean Ledger.
- AC-C1-STORE-02: Adapter tests round-trip every IngestionRun field.
- AC-C1-STORE-03: Adapter tests apply guarded terminal transitions atomically.
- AC-C1-STORE-04: Adapter tests reject a conflicting terminal transition.
- AC-C1-STORE-05: Adapter tests order runs by full UTC start time descending.
- AC-C1-STORE-06: Adapter tests apply the internal identity tie-breaker.
- AC-C1-STORE-07: Accepted-record iteration excludes IngestionRun rows.
- AC-C1-STORE-08: Existing Ledger initialization and migration tests remain green.

### User CLI Pipeline

- AC-C1-CLI-01: CLI tests prove the exact `ingest` command shape.
- AC-C1-CLI-02: CLI tests prove the exact `ingestions list` command shape.
- AC-C1-CLI-03: CLI tests ingest project-owned PDF, Markdown, and text fixtures.
- AC-C1-CLI-04: CLI tests prove a captured command writes one exact stdout row.
- AC-C1-CLI-05: CLI tests prove a failed command writes empty stdout.
- AC-C1-CLI-06: CLI tests prove a failed command writes a safe stderr explanation.
- AC-C1-CLI-07: CLI tests prove syntax failure creates no IngestionRun.
- AC-C1-CLI-08: CLI tests prove missing file, invalid URL, and suffix failures persist.
- AC-C1-CLI-09: CLI tests prove a PDF blocker persists as `[ERROR]`.
- AC-C1-CLI-10: CLI tests prove the Source URL is never requested.
- AC-C1-CLI-11: CLI tests prove default output contains no canonical Domain ID.
- AC-C1-CLI-12: CLI tests prove the list has no header and uses one tab.
- AC-C1-CLI-13: CLI tests prove empty history returns `0` with empty stdout.
- AC-C1-CLI-14: CLI tests prove two same-file attempts produce two rows.
- AC-C1-CLI-15: CLI tests prove same bytes reuse canonical Source and Document records.
- AC-C1-CLI-16: CLI tests prove list order uses full start-time precision.
- AC-C1-CLI-17: CLI tests prove `kotekomi init` creates the XDG-style configuration and storage.
- AC-C1-CLI-18: CLI tests prove setup does not overwrite an existing configuration.
- AC-C1-CLI-19: CLI tests prove a missing configuration names `kotekomi init` as the remedy.
- AC-C1-CLI-20: CLI tests prove history loading does not require BuildIdentity derivation.

### Regression

- AC-C1-REG-01: Existing `source add-file` tests remain green.
- AC-C1-REG-02: Existing deposited PDF capture tests remain green.
- AC-C1-REG-03: Existing Markdown and text capture tests remain green.
- AC-C1-REG-04: Existing Source revision tests remain green.
- AC-C1-REG-05: Existing derived projection tests ignore IngestionRun records.

### Canonical local validation

The canonical verifier is:

```text
scripts/verify_cir1_canonical.py
```

The verifier uses:

```text
raw/Anthropic–United_States_Department_of_Defense_dispute.pdf
https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute
```

The verifier performs these checks.

1. The verifier rejects a missing or mismatched locked PDF.
2. The verifier initializes a clean disposable Ledger and Archive.
3. The verifier runs the User CLI ingest command.
4. The verifier proves one `[CAPTURED]` row exists.
5. The verifier repeats the same file and URL.
6. The verifier proves two IngestionRuns exist.
7. The verifier proves both runs link to reused canonical records.
8. The verifier runs one valid command with a missing file.
9. The verifier proves one `[ERROR]` row exists.
10. The verifier runs `kotekomi ingestions list`.
11. The verifier proves latest-first order and exact field shape.
12. The verifier proves default output contains no canonical Domain ID.
13. The verifier proves the scenario made no network request.

A missing local PDF fails closeout visibly.

A missing local PDF does not count as a skipped or passing run.

The implementation adds the exact commands to `docs/CHECK_PLAN.md`.

## 10. Reference Implementations

- User CLI parser and stream patterns: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Deposited-source use case: `packages/application/src/kotekomi_application/source_file_ingest.py`.
- PDF representation behavior: `packages/application/src/kotekomi_application/pdf_ingest.py`.
- Domain record patterns: `packages/domain/src/kotekomi_domain/models.py`.
- Application Port patterns: `packages/application/src/kotekomi_application/ports.py`.
- SQLite repository patterns: `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.
- SQLite schema migrations: `packages/adapters/src/kotekomi_adapters/migrations/`.
- Archive behavior: `packages/adapters/src/kotekomi_adapters/local_archive.py`.
- Existing CLI fixture tests: `packages/pipelines/tests/test_source_add_file.py`.
- Existing shared CLI tests: `packages/pipelines/tests/test_cli.py`.
- Deposited-source contract: `docs/2026-08-13-live-source-walking-skeleton.md`.
- Testing rules: `docs/agent/testing.md`.

## 11. Constraints and Halt Conditions

Stop if the implementation requires a model runtime.

Stop if the implementation creates ProposedChanges.

Stop if the implementation creates candidate or published Wiki files.

Stop if the User CLI requires a canonical Domain ID.

Stop if the User CLI shells out to the Operator CLI.

Stop if one IngestionRun is reused for several admitted commands.

Stop if IngestionRun identity replaces Source or Document identity.

Stop if IngestionRun becomes an alias for ProcessingAttempt or AnalysisRun.

Stop if a failed attempt disappears from history.

Stop if the Source URL is requested.

Stop if a PDF blocker rolls back committed Source capture records.

Stop if IngestionRun rows enter accepted-record iteration.

Stop if a projector treats IngestionRun rows as intelligence.

Stop if normal user output includes document text or canonical Domain IDs.

Stop if the change adds compatibility aliases for the User CLI command names.

Stop if the implementation changes the existing capture identity rules.
