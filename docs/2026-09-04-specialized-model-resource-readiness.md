# TDD: Specialized Model Resource Readiness

## Context & Problem

A KoteKomi user expects an installed local system to ingest documents without Internet access.

The Hybrid Pipeline uses GLiNER to propose mention spans.

The Hybrid Pipeline uses ReFinED to propose external entity identities.

GLiNER currently asks Hugging Face for its model during normal ingestion.

ReFinED currently requires manually configured Python and model-resource paths.

These behaviors make local readiness implicit and make ingestion depend on machine-specific setup.

**Model Resource** means one pinned local dependency that a specialized-model Adapter requires.

**Resource Installation** means one validated local copy of a Model Resource and its runtime files.

**Resource Root** means the shared user directory that contains Resource Installations.

**Resource Readiness** means the typed result of validating one Resource Installation locally.

The primary flow is:

1. The user initializes KoteKomi without downloading Model Resources.
2. The user runs one explicit install command while network access is available.
3. KoteKomi installs and validates the pinned GLiNER and ReFinED resources.
4. A later ingestion validates both Resource Installations without network access.
5. The Hybrid Pipeline runs GLiNER and ReFinED only from those local resources.

## Goals

- A user can install every required specialized Model Resource with one command.
- A user can inspect Model Resource readiness without network access.
- A prepared KoteKomi installation can ingest a document without Internet access.
- A readiness failure identifies the failed Model Resource and its corrective command.
- Every specialized-model result retains the exact Resource Installation identity.

## Requirements

### Application Layer

- SMR-APP-01: The Application Layer defines the supported Model Resource identifiers.
- SMR-APP-02: The supported identifiers are `gliner_mention_proposer_v1` and `refined_wikipedia_v1`.
- SMR-APP-03: The Application Layer defines `ready`, `missing`, `incomplete`, and `identity_mismatch` readiness statuses.
- SMR-APP-04: One Resource Readiness names its Model Resource, status, root, expected identity, observed identity, and diagnostics.
- SMR-APP-05: The aggregate readiness result orders GLiNER before ReFinED.
- SMR-APP-06: The aggregate readiness result is ready only when both Resource Readiness values are ready.
- SMR-APP-07: The Application Layer defines the inspection and installation Ports.

### Configuration Pipeline

- SMR-CFG-01: The generated user configuration contains one `[model_resources]` table.
- SMR-CFG-02: The table contains only a `root` path.
- SMR-CFG-03: The default Resource Root is `<XDG_DATA_HOME>/kotekomi/model-resources`.
- SMR-CFG-04: An explicit configuration can select another absolute or configuration-relative Resource Root.
- SMR-CFG-05: ReFinED timeout configuration does not select its executable or resource directory.
- SMR-CFG-06: KoteKomi derives ReFinED executable and resource paths from the Resource Installation.

### Model Resource CLI

- SMR-CLI-01: `kotekomi model resources status` inspects every supported Model Resource.
- SMR-CLI-02: The status command performs no network request.
- SMR-CLI-03: The status command supports text and JSON output.
- SMR-CLI-04: `kotekomi model resources install` installs both supported Model Resources by default.
- SMR-CLI-05: Repeatable `--resource gliner` and `--resource refined` options select resources.
- SMR-CLI-06: An install command reuses a ready Resource Installation without network access.
- SMR-CLI-07: An install command requires `--repair` before it replaces an invalid Resource Installation.
- SMR-CLI-08: The install command publishes a Resource Installation only after local validation succeeds.
- SMR-CLI-09: The text output supplies the exact corrective command for every non-ready resource.
- SMR-CLI-10: `kotekomi init` reports the status command and performs no Model Resource download.
- SMR-CLI-11: A successful targeted install exits successfully while still reporting aggregate readiness.

### GLiNER Adapter

- SMR-GLI-01: The GLiNER Resource Installation pins GLiNER package version `0.2.28`.
- SMR-GLI-02: The installation pins `urchade/gliner_medium-v2.1` at revision `40ec419335d09393f298636f471328b722c6da9e`.
- SMR-GLI-03: The installation pins `microsoft/deberta-v3-base` at revision `8ccc9b6f36199bec6961081d44eb72fb3f7353f3`.
- SMR-GLI-04: The installation contains only the required model and tokenizer files.
- SMR-GLI-05: A tracked lock records each required relative path and SHA-256 digest.
- SMR-GLI-06: The installer downloads both pinned repositories into one staged local model directory.
- SMR-GLI-07: The installer runs one local smoke inference before it publishes the installation.
- SMR-GLI-08: The runtime loader uses the local model directory and `local_files_only=true`.
- SMR-GLI-09: The runtime loader never calls `snapshot_download`.

### ReFinED Adapter

- SMR-REF-01: The ReFinED Resource Installation contains a Python 3.10 virtual environment.
- SMR-REF-02: The installer synchronizes `tools/refined-worker/requirements.txt` into that environment.
- SMR-REF-03: The requirements file pins the ReFinED package revision and every dependency version.
- SMR-REF-04: The installer downloads ReFinED resources only through the existing setup worker.
- SMR-REF-05: The installer validates the tracked ReFinED resource-tree digest and smoke spans.
- SMR-REF-06: The Resource Installation manifest binds the requirements digest and resource-tree digest.
- SMR-REF-07: Normal ReFinED workers set `download_files=false`.
- SMR-REF-08: The Pipeline selects the managed virtual environment and resource directory.

### Ingestion Pipeline

- SMR-ING-01: The ingestion Pipeline inspects both Model Resources before it starts an IngestionRun.
- SMR-ING-02: A non-ready resource returns `model_resources_not_ready` and a nonzero exit status.
- SMR-ING-03: A readiness failure creates no IngestionRun, Archive object, or Ledger record.
- SMR-ING-04: The failure output includes each non-ready Resource Readiness diagnostic.
- SMR-ING-05: The failure output includes `kotekomi model resources install` or its repair form.
- SMR-ING-06: A successful preflight allows the existing Hybrid Pipeline outcome rules to apply.
- SMR-ING-07: A runtime failure after successful preflight remains a recorded Pipeline failure or gap.
- SMR-ING-08: Model Resource manifests and existing model identities provide execution provenance.

## Proposed Architecture

```text
User
  |
  v
Model Resource CLI
  |
  v
Application readiness use case
  |
  +----------------------+----------------------+
  |                                             |
  v                                             v
GLiNER Resource Adapter                  ReFinED Resource Adapter
  |                                             |
  +----------------------+----------------------+
                         |
                         v
              Shared Resource Root
                         |
                         v
                Hybrid Pipeline preflight
```

The Application Layer owns Model Resource identifiers, statuses, aggregation, and Port contracts.

The GLiNER Adapter owns GLiNER downloads, file validation, and local model loading.

The ReFinED Adapter owns its isolated environment, resource setup, and file validation.

The Pipeline owns CLI composition, configuration, and ingestion preflight.

## Key Interactions

```text
User          CLI          Application        Adapters        Resource Root
 |             |                |                |                 |
 | install     |                |                |                 |
 |------------>| install all    |                |                 |
 |             |--------------->| install        |                 |
 |             |                |--------------->| stage/download  |
 |             |                |                |---------------->|
 |             |                |                | validate/publish|
 |             |<---------------| ready          |                 |
 | ready       |                |                |                 |
 |<------------|                |                |                 |
 |             |                |                |                 |
 | ingest      |                |                |                 |
 |------------>| inspect all    |                |                 |
 |             |--------------->| inspect        |                 |
 |             |                |--------------->| read only       |
 |             |                |<---------------| readiness       |
 |             |<---------------| aggregate      |                 |
 |             | run Pipeline from local resources                |
 |<------------| result         |                |                 |
```

## Data Model

KoteKomi stores no Model Resource in the Ledger or Archive.

Each Resource Installation stores one canonical JSON manifest under its managed directory.

The GLiNER manifest records its resource identifier, package version, repository revisions, file digests, and smoke result.

The ReFinED manifest records its resource identifier, Python version, requirements digest, resource-tree digest, and smoke result.

The Resource Root is untracked machine-local state.

## APIs / Interfaces

The Resource Inspection Port accepts a Model Resource identifier and Resource Root.

The Resource Inspection Port returns one Resource Readiness.

The Resource Installation Port accepts a Model Resource identifier, Resource Root, and repair flag.

The Resource Installation Port returns the Resource Readiness of the published installation.

The JSON status result contains `schema_version`, `status`, `resource_root`, and `resources`.

The aggregate `status` value is `ready` or `not_ready`.

## Behavior & Domain Rules

The installer uses a sibling staging directory for every new installation.

An interrupted or failed staging directory never counts as ready.

The installer reuses a ready installation.

The installer rejects an invalid published installation unless the user supplies `--repair`.

The installer removes the invalid installation only after the replacement passes validation.

The status and ingestion commands never repair local resources.

The install command is the only KoteKomi command that accesses model distribution services.

The GLiNER model and its tokenizer form one Resource Installation.

A missing runtime counts as not ready during preflight.

A failure that occurs after a successful preflight remains observable through existing Hybrid Pipeline records.

## Acceptance Criteria

- AC-SMR-APP-01: Application tests prove the identifiers, statuses, ordering, and aggregate readiness rules.
- AC-SMR-CFG-01: Configuration tests prove the default root, explicit root, relative root, and unknown-key rejection.
- AC-SMR-CLI-01: CLI tests prove install selection, reuse, repair, text output, and JSON output.
- AC-SMR-CLI-02: CLI tests prove `init` performs no resource installation.
- AC-SMR-GLI-01: Adapter tests prove every GLiNER lock file and digest.
- AC-SMR-GLI-02: Adapter tests prove the pinned tokenizer is part of the local model directory.
- AC-SMR-GLI-03: A network trap proves GLiNER inference uses local files only.
- AC-SMR-REF-01: Adapter tests prove environment, requirements, resource digest, and smoke validation.
- AC-SMR-REF-02: Worker tests prove every normal ReFinED request disables downloads.
- AC-SMR-ING-01: Pipeline tests prove preflight failure precedes every canonical write.
- AC-SMR-ING-02: Pipeline tests prove ready resources preserve existing partial and blocked runtime outcomes.
- AC-SMR-ING-03: A canonical offline ingestion produces no Hugging Face download output.
- AC-SMR-ING-04: Formatting, lint, type checking, and focused tests pass.

## Reference Implementations

- GLiNER Adapter: follow `packages/adapters/src/kotekomi_adapters/gliner_organization_mention_proposer.py`.
- ReFinED worker: follow `scripts/refined_entity_linking_worker.py`.
- Configuration: follow `packages/pipelines/src/kotekomi_pipelines/config.py`.
- CLI results: follow `packages/pipelines/src/kotekomi_pipelines/model_runtime.py`.

## Constraints and Halt Conditions

This TDD supersedes HP-3 requirements HGC-01 and HGC-02 for executable and resource paths.

The existing ReFinED timeout remains configurable.

This TDD does not manage LM Studio, Qwen, or embedding models.

Halt if normal ingestion requires network access after successful installation.

Halt if a Model Resource must become authoritative Ledger state.
