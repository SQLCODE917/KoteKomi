# TDD Harness Binding

## Context & Problem

A user writes a Technical Design Document and asks an implementation agent to implement it.

The user runs Harness commands from the KoteKomi repository root.

The user identifies the Technical Design Document with a local file path.

The local file path can be relative to the current working directory.

The Harness currently tracks task manifests, receipts, lifecycle gates, verification plans, check runs, and CI results.

The Harness does not yet identify the exact Technical Design Document that caused a task.

The user cannot compare Technical Design Documents unless the Harness links each implementation result to exact Technical Design Document content.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `TDD snapshot` for the exact bytes that the Harness stores after it reads the TDD path.

This TDD uses the term `TDD digest` for the SHA-256 digest of the TDD snapshot.

This TDD uses the term `TDD title` for the first heading in the TDD snapshot.

This TDD uses the term `task identifier` for the internal Harness identifier for one TDD digest.

This TDD uses the term `TDD binding` for the canonical record that links one TDD digest to one task identifier.

This TDD uses the term `TDD index` for the derived local lookup file for TDD bindings.

This TDD uses the term `TDD alias` for an additional TDD path that points to the same TDD digest.

Primary end-to-end Flow:

1. The user gives the Harness a TDD path.

2. The Harness reads the TDD path from the current working directory.

3. The Harness stores a TDD snapshot.

4. The Harness computes a TDD digest for the TDD snapshot.

5. The Harness looks up the TDD digest in the TDD index.

6. The Harness reuses the existing TDD binding when the TDD digest is already known.

7. The Harness derives a task identifier when the TDD digest is not known.

8. The Harness writes or updates the canonical TDD binding.

9. The Harness writes an immutable binding revision and an immutable receipt.

10. The Harness rebuilds or updates the TDD index.

## Goals

- The user can start Harness work with only a TDD path.

- The user can identify which Technical Design Document authorized a Harness task.

- The user can use multiple local paths for the same TDD content without creating duplicate tasks.

- The user can detect when a TDD path changed after the first binding.

- The operator can use a TDD binding as the first receipt in an implementation evidence chain.

- A later scorecard can attribute Harness metrics to exact TDD content.

## Requirements

TDD path boundary:

- TP-01: The TDD path reader accepts a local markdown file path.

- TP-02: The TDD path reader resolves a relative path from the current working directory.

- TP-03: The TDD path reader does not fetch network resources.

- TP-04: The TDD path reader stores the exact TDD snapshot that it reads.

- TP-05: The TDD path reader returns a blocked result when it cannot read the TDD path.

Task identity boundary:

- TI-01: The task identity resolver reads the TDD title from the first markdown heading when it exists.

- TI-02: The task identity resolver uses the TDD file name when the TDD title does not exist.

- TI-03: The task identity resolver creates a slug from the selected title or file name.

- TI-04: The task identity resolver appends a 12-hex-character digest suffix to the slug.

- TI-05: The task identity resolver creates a task identifier only for an unknown TDD digest.

- TI-06: The task identity resolver reuses the existing task identifier when the TDD digest is known.

- TI-07: The task identity resolver reports a blocked collision when a new TDD digest maps to an existing task identifier.

- TI-08: The task identity resolver exposes a test-only collision fixture for TI-07 tests.

TDD binding boundary:

- TB-01: The TDD binding writer computes the TDD digest from the TDD snapshot.

- TB-02: The TDD binding writer stores the primary TDD path.

- TB-03: The TDD binding writer stores all known TDD paths for the TDD digest.

- TB-04: The TDD binding writer stores the TDD digest.

- TB-05: The TDD binding writer stores the task identifier.

- TB-06: The TDD binding writer stores the canonical binding path.

- TB-07: The TDD binding writer stores the latest binding revision number.

- TB-08: The TDD binding writer returns a ready result when the same TDD path already has the same TDD digest.

- TB-09: The TDD binding writer returns a blocked result when the same TDD path already has a different TDD digest.

- TB-10: The TDD binding writer adds a TDD alias when a new TDD path has an existing TDD digest.

- TB-11: The TDD binding writer writes a new binding revision when it adds a TDD alias.

- TB-12: The TDD binding writer does not derive a new task identifier for a known TDD digest.

Receipt boundary:

- RB-01: The Harness writes one immutable receipt for each binding revision.

- RB-02: The receipt includes the TDD digest.

- RB-03: The receipt includes the task identifier.

- RB-04: The receipt includes the binding revision number.

- RB-05: The Harness does not overwrite an existing binding receipt.

Index boundary:

- IX-01: The TDD index maps each TDD path to one task identifier.

- IX-02: The TDD index maps each TDD digest to one task identifier.

- IX-03: The TDD index maps each task identifier to one canonical binding path.

- IX-04: The TDD index is derived local state.

- IX-05: The Harness rebuilds the TDD index by scanning canonical TDD bindings when the index is missing.

- IX-06: The Harness rebuilds the TDD index when the index conflicts with canonical TDD bindings.

- IX-07: Canonical TDD bindings win over stale TDD index entries.

CLI boundary:

- CLI-01: The CLI exposes a command that creates or reads a TDD binding from a TDD path.

- CLI-02: The CLI prints JSON output for the TDD binding result to stdout by default.

- CLI-03: The CLI returns a nonzero exit code for a blocked TDD binding result.

- CLI-04: The CLI accepts an optional output path for an operator report copy.

- CLI-05: The CLI does not require a receipt path.

- CLI-06: The normal documented command runs without optional output flags.

## Proposed Architecture

The TDD path reader owns local file access.

The task identity resolver owns deterministic task identifier creation for unknown TDD digests.

The TDD binding writer owns canonical binding records and immutable binding revisions.

The receipt writer owns immutable binding receipts.

The TDD index builder owns derived lookup state.

The CLI owns the operator boundary.

```text
+------------------+      +--------------------+      +-----------------+
| Operator         | ---> | CLI                | ---> | TDD path reader |
+------------------+      +--------------------+      +-----------------+
                                      |                         |
                                      v                         v
                            +--------------------+      +--------------+
                            | TDD index builder  | <--- | TDD snapshot |
                            +--------------------+      +--------------+
                                      |
                                      v
                            +--------------------+
                            | Task identity      |
                            | resolver           |
                            +--------------------+
                                      |
                                      v
                            +--------------------+
                            | TDD binding writer |
                            +--------------------+
                                      |
                                      v
                            +--------------------+
                            | Receipt writer     |
                            +--------------------+
```

## Key Interactions

Primary sequence:

```text
Operator       CLI          Path reader      Index builder    Binding writer    Receipt writer
   |            |                |                 |                  |                 |
   | bind TDD   |                |                 |                  |                 |
   |----------->|                |                 |                  |                 |
   |            | read path      |                 |                  |                 |
   |            |--------------->|                 |                  |                 |
   |            | snapshot       |                 |                  |                 |
   |            |<---------------|                 |                  |                 |
   |            | resolve digest |                 |                  |                 |
   |            |--------------------------------->|                  |                 |
   |            | binding facts  |                 |                  |                 |
   |            |<---------------------------------|                  |                 |
   |            | write binding  |                 |                  |                 |
   |            |--------------------------------------------------->|                 |
   |            | binding        |                 |                  |                 |
   |            |<---------------------------------------------------|                 |
   |            | write receipt  |                 |                  |                 |
   |            |-------------------------------------------------------------------->|
   |            | receipt        |                 |                  |                 |
   |            |<--------------------------------------------------------------------|
   | JSON       |                |                 |                  |                 |
   |<-----------|                |                 |                  |                 |
```

Alias sequence:

```text
Operator       CLI          Path reader      Index builder      Binding writer
   |            |                |                 |                    |
   | bind path  |                |                 |                    |
   |----------->|                |                 |                    |
   |            | read path      |                 |                    |
   |            |--------------->|                 |                    |
   |            | snapshot       |                 |                    |
   |            |<---------------|                 |                    |
   |            | known digest   |                 |                    |
   |            |--------------------------------->|                    |
   |            | existing task  |                 |                    |
   |            |<---------------------------------|                    |
   |            | add alias      |                 |                    |
   |            |---------------------------------------------------->|
   |            | new revision   |                 |                    |
   |            |<----------------------------------------------------|
   | ready JSON |                |                 |                    |
   |<-----------|                |                 |                    |
```

Drift sequence:

```text
Operator       CLI          Path reader      Index builder
   |            |                |                 |
   | bind path  |                |                 |
   |----------->|                |                 |
   |            | read path      |                 |
   |            |--------------->|                 |
   |            | snapshot       |                 |
   |            |<---------------|                 |
   |            | path conflict  |                 |
   |            |--------------------------------->|
   |            | blocked result |                 |
   |            |<---------------------------------|
   | blocked    |                |                 |
   |<-----------|                |                 |
```

## Data Model

The Harness will create one canonical TDD binding per TDD digest.

The canonical binding path is:

```text
<state-root>/experiments/<task-id>/spec/tdd-binding.json
```

The TDD snapshot path is:

```text
<state-root>/experiments/<task-id>/spec/tdd-snapshot.md
```

The binding revision directory is:

```text
<state-root>/experiments/<task-id>/spec/tdd-binding-revisions/
```

The binding receipt directory is:

```text
<state-root>/experiments/<task-id>/spec/receipts/
```

The TDD index path is:

```text
<state-root>/tdds/index.json
```

The current TDD binding record has these fields:

- `schema_version`

- `task_id`

- `primary_tdd_path`

- `tdd_paths`

- `tdd_snapshot_path`

- `tdd_sha256`

- `tdd_title`

- `latest_binding_revision`

- `latest_binding_revision_path`

- `latest_binding_receipt_path`

- `status`

- `diagnostics`

The binding revision record has the same fields as the current TDD binding record.

The binding revision file name uses this form:

```text
tdd-binding-<three-digit-revision>.json
```

The binding receipt file name uses this form:

```text
tdd-binding-<three-digit-revision>.receipt.json
```

The TDD index record has these fields:

- `schema_version`

- `by_tdd_path`

- `by_tdd_sha256`

- `by_task_id`

- `diagnostics`

The `tdd_paths` list contains unique normalized repository-relative paths.

The `tdd_paths` list is sorted lexicographically after the Harness adds any new path.

The `primary_tdd_path` value is the first path that created the canonical TDD binding.

The `primary_tdd_path` value appears in `tdd_paths`.

A TDD alias is permanent until a future explicit alias-removal command exists.

## APIs / Interfaces

The CLI contract is:

```text
kotekomi-agent tdd-bind <tdd-path> [--output <binding-report-json>]
```

The CLI prints the JSON result to stdout when `--output` is absent.

The `--output` file is an optional operator report copy.

The `--output` file does not define canonical Harness state.

The CLI writes canonical Harness state under the canonical binding path.

The CLI writes canonical receipts under the binding receipt directory.

The JSON result contract is:

```text
schema_version
status
task_id
requested_tdd_path
primary_tdd_path
tdd_paths
tdd_snapshot_path
tdd_sha256
tdd_title
canonical_binding_path
latest_binding_revision
latest_binding_revision_path
latest_binding_receipt_path
diagnostics
```

The blocked result uses `status = blocked`.

The ready result uses `status = ready`.

## Behavior & Domain Rules

The Harness treats the TDD snapshot as the source of identity.

The Harness treats the TDD digest as the stable TDD identity.

The Harness treats the TDD path string as location metadata.

The Harness derives the task identifier from the TDD title or TDD file name and a 12-hex-character digest suffix only when the TDD digest is unknown.

The Harness reuses the existing task identifier when the TDD digest is known.

The Harness allows the same TDD digest to bind to more than one TDD path.

The Harness blocks when one TDD path already has a different TDD digest.

The Harness blocks when a new TDD digest maps to an existing task identifier.

The Harness preserves the old TDD binding when a drift check blocks.

The Harness writes a new binding revision after each successful alias update.

The Harness writes a new immutable receipt after each binding revision.

The Harness records a diagnostic when the TDD path cannot be read.

The Harness records a diagnostic when the TDD digest conflicts with the existing TDD path binding.

The Harness records a diagnostic when the task identifier collides with a different TDD digest.

## Acceptance Criteria

- AC-TP-01: Acceptance tests prove the command reads a local markdown file.

- AC-TP-02: Acceptance tests prove the command resolves a relative path from the current working directory.

- AC-TP-03: Acceptance tests prove the command rejects network-style sources.

- AC-TP-04: Acceptance tests prove the command writes a TDD snapshot.

- AC-TP-05: Acceptance tests prove an unreadable TDD path returns blocked status.

- AC-TI-01: Unit tests prove the task identifier uses the first markdown heading for an unknown digest.

- AC-TI-02: Unit tests prove the task identifier uses the file name when no heading exists for an unknown digest.

- AC-TI-03: Unit tests prove the task identifier includes a slug.

- AC-TI-04: Unit tests prove the task identifier includes a 12-hex-character digest suffix.

- AC-TI-05: Unit tests prove equal TDD snapshot bytes reuse the same task identifier.

- AC-TI-06: Unit tests use the test-only collision fixture to prove task identifier collision returns blocked status.

- AC-TB-01: Unit tests prove equal TDD snapshot bytes produce equal TDD digests.

- AC-TB-02: Unit tests prove changed TDD snapshot bytes produce different TDD digests.

- AC-TB-03: Acceptance tests prove the binding record includes `primary_tdd_path`.

- AC-TB-04: Acceptance tests prove the binding record includes `tdd_paths`.

- AC-TB-05: Acceptance tests prove the binding record includes the task identifier.

- AC-TB-06: Acceptance tests prove conflicting TDD path binding returns blocked status.

- AC-TB-07: Acceptance tests prove repeated binding with the same path and digest returns ready status.

- AC-TB-08: Acceptance tests prove identical content at two paths produces one canonical TDD binding.

- AC-TB-09: Acceptance tests prove the second identical path becomes a TDD alias.

- AC-TB-10: Acceptance tests prove alias updates write a new binding revision.

- AC-RB-01: Acceptance tests prove each binding revision writes one immutable receipt through the receipt writer.

- AC-RB-02: Receipt tests prove each receipt includes the TDD digest.

- AC-RB-03: Receipt tests prove each receipt includes the task identifier.

- AC-RB-04: Receipt tests prove each receipt includes the binding revision number.

- AC-RB-05: Acceptance tests prove the receipt writer does not overwrite an existing binding receipt.

- AC-IX-01: Acceptance tests prove the TDD index maps TDD paths to task identifiers.

- AC-IX-02: Acceptance tests prove the TDD index maps TDD digests to task identifiers.

- AC-IX-03: Acceptance tests prove the TDD index maps task identifiers to canonical binding paths.

- AC-IX-04: Acceptance tests prove the Harness rebuilds a missing TDD index.

- AC-IX-05: Acceptance tests prove canonical TDD bindings win over stale TDD index entries.

- AC-CLI-01: CLI tests prove the command exists.

- AC-CLI-02: CLI tests prove the command prints JSON to stdout when `--output` is absent.

- AC-CLI-03: CLI tests prove blocked status returns a nonzero exit code.

- AC-CLI-04: CLI tests prove `--output` writes an operator report copy.

- AC-CLI-05: CLI tests prove the normal command does not require a receipt path.

- AC-CLI-06: CLI tests prove `kotekomi-agent tdd-bind <tdd-path>` runs as documented.

## Reference Implementations

- Receipt writing: follow `packages/devtools/src/kotekomi_devtools/receipt_writer.py`.

- Receipt status: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

- Manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.

## Constraints and Halt Conditions

The implementer must halt if the task manifest schema cannot reference a TDD binding by path and digest.

The implementer must halt if the task identifier collision fixture cannot be isolated from production behavior.
