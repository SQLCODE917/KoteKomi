# TDD Harness Binding

## Context & Problem

A user writes a Technical Design Document and asks an implementation agent to implement it.

The user runs Harness commands from the KoteKomi repository root.

The user identifies the Technical Design Document with a local file path.

The local file path can be relative to the current working directory.

The Harness currently tracks task manifests, receipts, lifecycle gates, verification plans, check runs, and CI results.

The Harness does not yet identify the exact Technical Design Document that caused a task.

The user cannot compare Technical Design Documents unless the Harness links each implementation result to exact Technical Design Document content.

This TDD uses the term `TDD path` for the repository-relative local file path that identifies the Technical Design Document.

This TDD uses the term `requested TDD path` for the TDD path supplied to the current command.

This TDD uses the term `primary TDD path` for the first TDD path that created a canonical binding.

This TDD uses the term `TDD path alias` for any later TDD path that has the same TDD digest as the canonical binding.

This TDD uses the term `TDD paths` for the sorted set that contains the primary TDD path and all TDD path aliases.

This TDD uses the term `TDD snapshot` for the exact bytes that the Harness stores after it reads the TDD path.

This TDD uses the term `TDD digest` for the SHA-256 digest of the TDD snapshot.

This TDD uses the term `TDD title` for the first heading in the TDD snapshot.

This TDD uses the term `task identifier` for the internal Harness identifier for one TDD digest.

This TDD uses the term `TDD binding` for the current stored record that links one TDD digest to one task identifier.

This TDD uses the term `TDD binding revision` for an immutable historical copy of a TDD binding.

This TDD uses the term `TDD index` for the derived local lookup file that maps TDD paths, TDD digests, and task identifiers to canonical bindings.

Primary end-to-end Flow:

1. The user gives the Harness a TDD path.

2. The Harness reads the TDD path from the current working directory.

3. The Harness stores a TDD snapshot.

4. The Harness computes a TDD digest for the TDD snapshot.

5. The Harness looks up the TDD digest in the TDD index.

6. The Harness reuses the existing task identifier when the TDD digest is already known.

7. The Harness derives a task identifier only when the TDD digest is unknown.

8. The Harness writes or updates the TDD binding.

9. The Harness writes an immutable TDD binding revision and an immutable receipt.

10. The Harness updates the TDD index.

## Goals

- The user can start Harness work with only a TDD path.

- The user can identify which Technical Design Document authorized a Harness task.

- The Harness does not create duplicate tasks for identical TDD content.

- The user can detect when a TDD path changed after the first binding.

- The operator can use a TDD binding as the first evidence record in an implementation run.

- A later scorecard can attribute Harness metrics to exact TDD content.

## Requirements

TDD path boundary:

- TP-01: The TDD path reader accepts a local markdown file path.

- TP-02: The TDD path reader resolves a relative path from the current working directory.

- TP-03: The TDD path reader normalizes the TDD path to a repository-relative path.

- TP-04: The TDD path reader does not fetch network resources.

- TP-05: The TDD path reader stores the exact TDD snapshot that it reads.

- TP-06: The TDD path reader returns a blocked result when it cannot read the TDD path.

Task identity boundary:

- TI-01: The task identity resolver uses digest-first lookup.

- TI-02: The task identity resolver reuses the existing task identifier when the TDD digest is already known.

- TI-03: The task identity resolver reads the TDD title from the first markdown heading when the TDD digest is unknown and the heading exists.

- TI-04: The task identity resolver uses the TDD file name when the TDD digest is unknown and the TDD title does not exist.

- TI-05: The task identity resolver creates a slug from the selected title or file name.

- TI-06: The task identity resolver appends a 12-character lowercase hexadecimal digest suffix to the slug.

- TI-07: The task identity resolver uses the derived value as the task identifier for an unknown TDD digest.

- TI-08: The task identity resolver exposes a fixture-only collision resolver for tests.

- TI-09: The task identity resolver blocks when the candidate task identifier already belongs to a different TDD digest.

TDD binding boundary:

- TB-01: The TDD binding writer computes the TDD digest from the TDD snapshot.

- TB-02: The TDD binding writer stores the requested TDD path.

- TB-03: The TDD binding writer stores the primary TDD path.

- TB-04: The TDD binding writer stores TDD paths.

- TB-05: The TDD binding writer stores the TDD digest.

- TB-06: The TDD binding writer stores the task identifier.

- TB-07: The TDD binding writer returns blocked status when the same requested TDD path already maps to a different TDD digest.

- TB-08: The TDD binding writer returns ready status when the same requested TDD path already maps to the same TDD digest.

- TB-09: The TDD binding writer treats a new requested TDD path with a known TDD digest as a TDD path alias.

- TB-10: The TDD binding writer keeps the first-bound path as the primary TDD path.

- TB-11: The TDD binding writer keeps TDD paths unique.

- TB-12: The TDD binding writer sorts TDD paths lexicographically after each update.

- TB-13: The TDD binding writer keeps TDD path aliases permanent until a future explicit alias removal command exists.

Canonical storage boundary:

- CS-01: The Harness stores the current binding at `<state-root>/experiments/<task-id>/spec/tdd-binding.json`.

- CS-02: The Harness stores the TDD snapshot at `<state-root>/experiments/<task-id>/spec/tdd-snapshot.md`.

- CS-03: The Harness stores immutable binding revisions under `<state-root>/experiments/<task-id>/spec/tdd-binding-revisions/`.

- CS-04: The Harness stores immutable binding receipts under `<state-root>/experiments/<task-id>/spec/receipts/`.

- CS-05: The Harness stores the TDD index at `<state-root>/tdds/index.json`.

- CS-06: The Harness names binding revisions as `tdd-binding-<revision>.json` with a three-digit decimal revision.

- CS-07: The Harness names binding receipts as `tdd-binding-<revision>.receipt.json` with the same revision number.

- CS-08: The Harness updates `tdd-binding.json` as the current binding copy after each ready binding update.

- CS-09: The Harness never overwrites an existing binding revision.

- CS-10: The Harness never overwrites an existing binding receipt.

TDD index boundary:

- IX-01: The TDD index maps each TDD path to one task identifier.

- IX-02: The TDD index maps each TDD digest to one task identifier.

- IX-03: The TDD index maps each task identifier to one canonical binding path.

- IX-04: The Harness rebuilds the TDD index by scanning canonical bindings when the index is missing.

- IX-05: The Harness treats canonical bindings as source of truth when the index conflicts with canonical bindings.

- IX-06: The Harness updates the TDD index after each ready binding update.

Receipt boundary:

- RB-01: The Harness writes one immutable receipt for each TDD binding revision.

- RB-02: The receipt includes the TDD digest.

- RB-03: The receipt includes the task identifier.

- RB-04: The receipt includes the binding revision number.

- RB-05: The receipt includes the SHA-256 digest of the binding revision file.

CLI boundary:

- CLI-01: The CLI exposes a command that creates or reads a TDD binding from a TDD path.

- CLI-02: The CLI prints JSON to stdout by default.

- CLI-03: The CLI accepts an optional `--output` path that writes a JSON copy of the result.

- CLI-04: The CLI treats `--output` as an operator report and not as canonical state.

- CLI-05: The CLI returns a nonzero exit code for a blocked TDD binding result.

## Proposed Architecture

The TDD path reader owns local file access.

The task identity resolver owns deterministic task identifier creation.

The TDD binding writer owns TDD digest computation and TDD binding storage.

The TDD index writer owns derived local lookup state.

The receipt writer owns immutable TDD binding receipts.

The CLI owns the operator boundary.

```text
+------------------+      +--------------------+      +-----------------+
| Operator         | ---> | CLI                | ---> | TDD path reader |
+------------------+      +--------------------+      +-----------------+
                                      |                         |
                                      v                         v
                            +--------------------+      +--------------+
                            | Task identity      | <--- | TDD snapshot |
                            | resolver           |      +--------------+
                            +--------------------+
                                      |
                                      v
                            +--------------------+      +-------------+
                            | TDD binding writer | ---> | TDD index   |
                            +--------------------+      +-------------+
                                      |
                                      v
                            +--------------------+
                            | Receipt writer     |
                            +--------------------+
```

## Key Interactions

Primary sequence:

```text
Operator       CLI          Path reader      Identity resolver    Binding writer    Index writer    Receipt writer
   |            |                |                  |                   |               |              |
   | bind TDD   |                |                  |                   |               |              |
   |----------->|                |                  |                   |               |              |
   |            | read path      |                  |                   |               |              |
   |            |--------------->|                  |                   |               |              |
   |            | snapshot       |                  |                   |               |              |
   |            |<---------------|                  |                   |               |              |
   |            | resolve id     |                  |                   |               |              |
   |            |---------------------------------->|                   |               |              |
   |            | task id        |                  |                   |               |              |
   |            |<----------------------------------|                   |               |              |
   |            | write binding  |                  |                   |               |              |
   |            |----------------------------------------------------->|               |              |
   |            | binding        |                  |                   |               |              |
   |            |<-----------------------------------------------------|               |              |
   |            | update index   |                  |                   |               |              |
   |            |-------------------------------------------------------------------->|              |
   |            | write receipt  |                  |                   |               |              |
   |            |----------------------------------------------------------------------------------->|
   | JSON       |                |                  |                   |               |              |
   |<-----------|                |                  |                   |               |              |
```

Alias sequence:

```text
Operator       CLI          Path reader      Binding writer      Index writer      Receipt writer
   |            |                |                  |                   |               |
   | bind TDD   |                |                  |                   |               |
   |----------->|                |                  |                   |               |
   |            | read path      |                  |                   |               |
   |            |--------------->|                  |                   |               |
   |            | same digest    |                  |                   |               |
   |            |<---------------|                  |                   |               |
   |            | add alias      |                  |                   |               |
   |            |---------------------------------->|                   |               |
   |            | new revision   |                  |                   |               |
   |            |<----------------------------------|                   |               |
   |            | update index   |                  |                   |               |
   |            |----------------------------------------------------->|               |
   |            | write receipt  |                  |                   |               |
   |            |-------------------------------------------------------------------->|
   | ready JSON |                |                  |                   |               |
   |<-----------|                |                  |                   |               |
```

## Data Model

The Harness will create one current TDD binding record per task identifier.

The current TDD binding record has these fields:

- `schema_version`

- `task_id`

- `requested_tdd_path`

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

The immutable TDD binding revision has the same fields as the current TDD binding record.

The TDD index record has these fields:

- `schema_version`

- `paths`

- `digests`

- `tasks`

- `diagnostics`

The `paths` map uses TDD path keys and task identifier values.

The `digests` map uses TDD digest keys and task identifier values.

The `tasks` map uses task identifier keys and state-root-relative canonical binding path values.

The Harness will read TDD binding records by TDD path through the TDD index.

The Harness will read TDD binding records by TDD digest through the TDD index.

The Harness will read TDD binding records by task identifier through the TDD index.

## APIs / Interfaces

The CLI contract is:

```text
kotekomi-agent tdd-bind <tdd-path> [--output <binding-json>]
```

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
latest_binding_revision
latest_binding_revision_path
latest_binding_receipt_path
diagnostics
```

The blocked result uses `status = blocked`.

The ready result uses `status = ready`.

## Behavior & Domain Rules

The Harness treats the TDD snapshot as the source of identity.

The Harness resolves identity by TDD digest before it derives a task identifier.

The Harness treats the TDD path string as location metadata.

The Harness derives the task identifier only for an unknown TDD digest.

The Harness derives the task identifier from the TDD title or TDD file name and a 12-character digest suffix.

The first binding for a TDD digest wins the task identifier for that TDD digest.

The Harness treats identical TDD bytes at different paths as TDD path aliases.

The Harness blocks when one TDD path already maps to a different TDD digest.

The Harness blocks when a derived task identifier collides with a different TDD digest.

The Harness preserves the old TDD binding when a drift check blocks.

The Harness records a diagnostic when the TDD path cannot be read.

The Harness records a diagnostic when the TDD digest conflicts with the existing TDD path binding.

The Harness records a diagnostic when the task identifier collides with a different TDD digest.

## Acceptance Criteria

- AC-TP-01: Acceptance tests prove the command reads a local markdown file.

- AC-TP-02: Acceptance tests prove the command resolves a relative path from the current working directory.

- AC-TP-03: Acceptance tests prove the command normalizes a repository-relative TDD path.

- AC-TP-04: Acceptance tests prove the command rejects network-style sources.

- AC-TP-05: Acceptance tests prove the command writes a TDD snapshot.

- AC-TP-06: Acceptance tests prove an unreadable TDD path returns blocked status.

- AC-TI-01: Unit tests prove digest-first lookup reuses an existing task identifier.

- AC-TI-02: Unit tests prove the task identifier uses the first markdown heading for an unknown digest when it exists.

- AC-TI-03: Unit tests prove the task identifier uses the file name for an unknown digest when no heading exists.

- AC-TI-04: Unit tests prove the task identifier includes a slug.

- AC-TI-05: Unit tests prove the task identifier includes a 12-character digest suffix.

- AC-TI-06: Unit tests prove a fixture-only collision resolver can create a deterministic collision case.

- AC-TI-07: Unit tests prove task identifier collision with a different digest returns blocked status.

- AC-TB-01: Unit tests prove equal TDD snapshot bytes produce equal TDD digests.

- AC-TB-02: Unit tests prove changed TDD snapshot bytes produce different TDD digests.

- AC-TB-03: Acceptance tests prove the binding record includes the requested TDD path.

- AC-TB-04: Acceptance tests prove the binding record includes the primary TDD path.

- AC-TB-05: Acceptance tests prove the binding record includes sorted unique TDD paths.

- AC-TB-06: Acceptance tests prove the binding record includes the task identifier.

- AC-TB-07: Acceptance tests prove conflicting TDD path binding returns blocked status.

- AC-TB-08: Acceptance tests prove repeated binding with the same digest returns ready status.

- AC-TB-09: Acceptance tests prove identical heading-less files at different paths become aliases of the first binding.

- AC-CS-01: Acceptance tests prove the current binding exists at the canonical current binding path.

- AC-CS-02: Acceptance tests prove the TDD snapshot exists at the canonical snapshot path.

- AC-CS-03: Acceptance tests prove each ready binding update writes a new immutable binding revision.

- AC-CS-04: Acceptance tests prove each ready binding update writes a new immutable receipt.

- AC-CS-05: Acceptance tests prove old binding revisions are not overwritten.

- AC-CS-06: Acceptance tests prove old binding receipts are not overwritten.

- AC-IX-01: Acceptance tests prove the TDD index maps TDD paths to task identifiers.

- AC-IX-02: Acceptance tests prove the TDD index maps TDD digests to task identifiers.

- AC-IX-03: Acceptance tests prove the TDD index maps task identifiers to canonical binding paths.

- AC-IX-04: Acceptance tests prove the Harness rebuilds the TDD index when the index is missing.

- AC-RB-01: Receipt tests prove each binding revision has one immutable receipt.

- AC-RB-02: Receipt tests prove the receipt includes the TDD digest.

- AC-RB-03: Receipt tests prove the receipt includes the task identifier.

- AC-RB-04: Receipt tests prove the receipt includes the binding revision number.

- AC-CLI-01: CLI tests prove the command exists.

- AC-CLI-02: CLI tests prove the command prints JSON to stdout by default.

- AC-CLI-03: CLI tests prove optional `--output` writes a JSON copy.

- AC-CLI-04: CLI tests prove blocked status returns a nonzero exit code.

## Reference Implementations

- Receipt writing: follow `packages/devtools/src/kotekomi_devtools/receipt_writer.py`.

- Receipt status: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

- Manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.

## Constraints and Halt Conditions

The implementer must halt if the task manifest schema cannot reference a TDD binding by `tdd_path` and `tdd_sha256`.

The implementer must halt if the task identifier rule produces a real collision outside the fixture-only test seam.
