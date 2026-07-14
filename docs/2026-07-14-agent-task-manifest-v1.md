# Task Manifest Contract and Validation

## Status

Document class: Leaf TDD

Design status: Accepted

Series: `docs/2026-07-14-terra-high-harness-series-plan.md`

Series leaf: H1

Planning baseline: `e597b49f3929838d303e96347d7137e3f16a69d8`

Implementation profile: `terra-high-v1`

## Context & Problem

KoteKomi has no machine-readable execution boundary for an implementation task.

A coding agent can currently infer scope, change acceptance files, and report completion without independent proof.

The accepted Terra-high harness series requires one immutable task contract before implementation begins.

H1 defines Task Manifest V1 and one validation command.

## Goals

- Define one versioned Task Manifest contract.
- Validate Task Manifest TOML against one protected JSON Schema.
- Reject malformed manifests with stable machine-readable diagnostics.
- Reject unsafe or ambiguous repository paths.
- Reject arbitrary shell command strings.
- Produce one deterministic canonical manifest digest.
- Integrate `kotekomi-devtools` into the root workspace.
- Keep the harness independent from every KoteKomi product package.

## Non-Goals & Forbidden Approaches

### Non-Goals

- H1 does not inspect Git history or revisions.
- H1 does not verify file existence or file digests.
- H1 does not execute acceptance commands.
- H1 does not verify a Candidate Commit.
- H1 does not create a Verification Receipt.
- H1 does not update an Acceptance Registry.
- H1 does not integrate the harness into GitHub Actions.
- H1 does not define Series Manifest behavior.
- H1 does not collect experiment metrics.
- H1 does not change a KoteKomi product contract.

### Forbidden Approaches

- Do not accept YAML manifests.
- Do not accept unversioned manifests.
- Do not accept an external model name in place of `terra-high-v1`.
- Do not accept arbitrary shell command strings.
- Do not invoke a shell to validate a manifest.
- Do not import a KoteKomi product package.
- Do not copy the protected JSON Schema into a second authoritative location.
- Do not inspect the filesystem records named inside a manifest.
- Do not silently ignore unknown fields.
- Do not emit a traceback for expected invalid input.
- Do not normalize or reorder arrays before digest generation.
- Do not edit the protected specification files during implementation.

## Requirements

1. The repository contains a workspace package named `kotekomi-devtools`.
2. The package exposes the `kotekomi-agent` console command.
3. The command accepts `validate-task PATH`.
4. The command reads UTF-8 TOML from `PATH`.
5. The command validates parsed values against `.agent/schemas/task-manifest-v1.schema.json`.
6. The command runs from the repository root.
7. The command rejects every unknown object field.
8. The command applies semantic and repository-path validation only after schema validation succeeds.
9. The command returns all schema violations found in one schema-validation pass.
10. The command returns all semantic and path violations found in one post-schema validation pass.
11. The command sorts diagnostics deterministically.
12. The command emits one compact JSON object followed by one newline.
13. The command emits no stderr text for an expected invalid manifest.
14. The command computes a canonical SHA-256 digest only for a valid manifest.
15. The root workspace discovers the package command and all package tests.
16. Root Ruff and Pyright checks include the package source and tests.
17. The package declares no dependency on a KoteKomi product package.

## Invariants

- Task Manifest V1 has one JSON Schema authority.
- Manifest validation performs no repository write.
- Manifest validation executes no manifest command.
- Manifest validation performs no Git operation.
- Manifest validation does not resolve symlinks.
- Manifest validation does not inspect referenced file existence.
- Equivalent TOML formatting produces the same digest.
- Array order remains part of the digest.
- Expected invalid input produces no traceback.
- Product packages remain independent from `kotekomi-devtools`.
- `kotekomi-devtools` remains independent from product packages.

## Proposed Architecture

```text
kotekomi-agent CLI
        |
        v
TOML Loader
        |
        v
JSON Schema Validator
        |
        +----------> Stable Diagnostics
        |
        v
Repository Path Validator
        |
        +----------> Stable Diagnostics
        |
        v
Canonical JSON Digest
        |
        v
Validation Result JSON
```

The CLI owns argument parsing and exit-code mapping.

The TOML Loader reads one UTF-8 file and returns parsed project-owned values.

The JSON Schema Validator applies the protected Task Manifest V1 schema.

The Repository Path Validator applies semantic path rules that JSON Schema cannot express.

The Canonical JSON Digest component produces the manifest identity.

The Stable Diagnostics component orders and serializes validation results.

## Key Interactions

### Valid manifest

```text
User
  |
  | kotekomi-agent validate-task PATH
  v
CLI
  |
  | read UTF-8 TOML
  v
TOML Loader
  |
  | parsed object
  v
Schema Validator
  |
  | no violations
  v
Path Validator
  |
  | no violations
  v
Canonical Digest
  |
  | SHA-256
  v
CLI
  |
  | valid JSON result and exit 0
  v
User
```

### Invalid manifest

```text
User
  |
  | kotekomi-agent validate-task PATH
  v
CLI
  |
  | parsed object
  v
Schema Validator or Path Validator
  |
  | ordered diagnostics
  v
CLI
  |
  | invalid JSON result and exit 1
  v
User
```

### Missing or malformed file

```text
User
  |
  | kotekomi-agent validate-task PATH
  v
CLI
  |
  +---- missing or unreadable ----> file diagnostic
  |
  +---- malformed TOML -----------> parse diagnostic
                                      |
                                      v
                         invalid JSON result and exit 1
```

## Data Model

### Task Manifest V1

Task Manifest V1 requires these top-level fields.

| Field | Shape | Rule |
|---|---|---|
| `schema_version` | integer | Exactly `1` |
| `task_id` | identifier | Lowercase kebab case |
| `title` | nonempty string | Human-readable task title |
| `status` | string | Exactly `ready_for_terra_high` |
| `series_id` | identifier | Lowercase kebab case |
| `task_class` | enum | One supported task class |
| `model_profile` | string | Exactly `terra-high-v1` |
| `baseline_revision` | string | Forty lowercase hexadecimal characters |
| `tdd_path` | repository file path | Exact Leaf TDD path |
| `tdd_sha256` | string | Sixty-four lowercase hexadecimal characters |
| `goal` | nonempty string | One dominant outcome |
| `depends_on` | identifier array | Unique dependency IDs |
| `allowed_paths` | repository path array | At least one unique path |
| `reference_paths` | repository path array | Unique paths |
| `protected_artifacts` | object array | At least one protected file |
| `acceptance` | command array | At least one required command |
| `readiness` | object | Complete readiness declaration |
| `budget` | object | Positive soft limits |
| `stop_conditions` | string array | At least one unique condition |

### Identifiers

These fields use the same identifier pattern:

```text
[a-z0-9]+(-[a-z0-9]+)*
```

The rule applies to task IDs, series IDs, dependency IDs, acceptance IDs, and contract-family IDs.

Identifiers reject spaces, underscores, uppercase letters, leading hyphens, trailing hyphens, and consecutive hyphens.

### Task classes

Task Manifest V1 accepts these task classes:

```text
schema-contract
pure-behavior
move-only-refactor
adapter-contract
orchestration
wiring
repository-tooling
documentation-contract
```

### Protected artifact

Each protected artifact contains:

| Field | Shape |
|---|---|
| `path` | exact repository file path |
| `sha256` | sixty-four lowercase hexadecimal characters |
| `kind` | protected artifact kind |

Allowed kinds are:

```text
leaf-tdd
task-manifest
json-schema
acceptance-test
fixture
golden
agent-instructions
```

The Task Manifest does not list itself as a protected artifact.

H2 will bind the Task Manifest to the specification commit without a self-referential digest.

Protected artifact paths must be unique within `protected_artifacts`.

### Acceptance command

Each acceptance command contains:

| Field | Shape |
|---|---|
| `id` | unique identifier |
| `argv` | nonempty string array |
| `timeout_seconds` | positive integer |
| `profile` | execution-profile enum |

Allowed profiles are:

```text
portable-local
authoritative-linux
private-conformance
```

Every acceptance command is required.

Task Manifest V1 has no optional-command flag.

Acceptance IDs must be unique within `acceptance`.

A duplicate acceptance ID returns `task_manifest.semantic_violation`.

### Readiness record

The readiness record requires:

```text
dominant_outcome
contract_family
public_entry_point
authority
scope_policy
side_effect_boundary
failure_policy
negative_proof
legacy_disposition
unresolved_decisions
```

Every text field is nonempty.

`unresolved_decisions` must be an empty array.

### Budget record

The budget record requires:

```text
maximum_production_files
maximum_test_files
maximum_production_diff_lines
```

Every value is a positive integer.

H1 validates budget shape only.

H1 does not inspect a Git diff.

## APIs / Interfaces

### Command

```text
kotekomi-agent validate-task PATH
```

The command expects the current working directory to be the KoteKomi repository root.

The command reads the authoritative schema at:

```text
.agent/schemas/task-manifest-v1.schema.json
```

### Valid result

A valid result uses this field order:

```text
status
schema_version
task_id
manifest_sha256
diagnostics
```

The compact JSON result has this shape:

```json
{"status":"valid","schema_version":1,"task_id":"harness-01-task-manifest-contract","manifest_sha256":"<64 lowercase hex characters>","diagnostics":[]}
```

### Invalid result

An invalid result uses the same top-level field order.

The compact JSON result has this shape:

```json
{"status":"invalid","schema_version":null,"task_id":null,"manifest_sha256":null,"diagnostics":[{"code":"task_manifest.schema_violation","location":"/task_id","rule":"pattern"}]}
```

A diagnostic uses this field order:

```text
code
location
rule
```

### Diagnostic codes

Task Manifest V1 defines these codes:

```text
task_manifest.file_not_found
task_manifest.file_unreadable
task_manifest.toml_parse_error
task_manifest.schema_violation
task_manifest.semantic_violation
task_manifest.path_violation
```

### Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | The manifest is valid |
| `1` | The manifest file is missing, unreadable, malformed, or invalid |
| `2` | The CLI invocation is invalid |
| `70` | An unexpected internal failure occurred |

Expected invalid manifests write their JSON result to stdout.

Expected invalid manifests leave stderr empty.

CLI usage errors write usage information to stderr.

An unexpected internal failure writes no stdout.

An unexpected internal failure writes one stable stderr line without a traceback.

## Behavior & Domain Rules

### Schema-validation order

The command parses TOML before schema validation.

A TOML parse failure returns only `task_manifest.toml_parse_error`.

The command runs post-schema validation only when schema validation returns no violations.

Post-schema validation runs semantic uniqueness checks and repository-path checks.

Post-schema validation returns every semantic and path violation from that pass.

The command computes a manifest digest only when every validation stage succeeds.

### Parsed identity fields

An invalid result includes `schema_version` only when the parsed value is exactly integer `1`.

An invalid result includes `task_id` only when the parsed value is a string matching the identifier pattern.

Every other case emits `null` for that identity field.

### File diagnostic rules

A missing path returns `task_manifest.file_not_found` with rule `exists`.

A directory, permission failure, or other read failure returns `task_manifest.file_unreadable` with rule `readable`.

Invalid UTF-8 returns `task_manifest.file_unreadable` with rule `utf8`.

File diagnostics use the root location.

### Schema diagnostic locations

Schema diagnostic locations use RFC 6901 JSON Pointer strings.

The root location is the empty string.

A value violation identifies the violating value.

A `required` violation identifies the containing object.

An `additionalProperties` violation identifies the containing object.

The diagnostic `rule` is the JSON Schema keyword that failed.

### Path rules

Every manifest path uses repository-relative POSIX syntax.

A valid path:

- is nonempty;
- is not absolute;
- has no `.` segment;
- has no `..` segment;
- has no backslash;
- has no repeated slash;
- has no `~` prefix;
- has no `*`, `?`, `[`, or `]` wildcard character.

A directory scope ends with `/`.

An exact-file path does not end with `/`.

`tdd_path` is an exact-file path.

Each protected artifact path is an exact-file path.

Allowed and reference paths can identify exact files or directory scopes.

Duplicate detection applies within `allowed_paths` and `reference_paths`.

Protected artifact paths must be unique within `protected_artifacts`.

Acceptance IDs must be unique within `acceptance`.

The same path can appear in different roles.

Path validation does not check whether a path exists.

### Path diagnostic rules

Post-schema diagnostics use these `rule` values:

```text
repository_relative_posix
exact_file
unique_path
unique_identifier
```

`unique_identifier` applies to duplicate acceptance IDs.

The diagnostic location identifies the exact field or array item.

For duplicate collection entries, the location identifies every duplicate after the first occurrence.

A duplicate acceptance ID uses this diagnostic shape:

```json
{"code":"task_manifest.semantic_violation","location":"/acceptance/1/id","rule":"unique_identifier"}
```

### Canonical manifest digest

The command computes the canonical digest after complete validation.

The command:

1. Uses the parsed TOML value.
2. Preserves array order.
3. Sorts object keys recursively.
4. Serializes compact UTF-8 JSON.
5. Uses `,` and `:` without surrounding whitespace.
6. Emits non-ASCII characters directly.
7. Performs no Unicode normalization.
8. Appends no newline to the digested bytes.
9. Computes SHA-256 over those bytes.

Equivalent TOML whitespace, comments, quote styles, and table formatting produce the same digest.

Changing array order changes the digest.

### Diagnostic ordering

Diagnostics sort by:

1. `location`;
2. `code`;
3. `rule`.

The command returns every violation from the schema stage or the combined post-schema stage.

### JSON output

The command writes one compact JSON object.

The command uses the public field order defined in this TDD.

The command does not escape non-ASCII text unless JSON syntax requires it.

The command writes exactly one trailing newline.

## Acceptance Criteria

### Gate 1: protected contract assets

- The protected JSON Schema is valid Draft 2020-12 JSON Schema.
- The canonical valid fixture satisfies the protected schema.
- The equivalent-format fixture parses to the same value.
- The reordered-array fixture parses to a different value.
- Every protected file digest matches the Task Manifest.
- The Task Manifest itself has an externally recorded bootstrap digest.

### Gate 2: package integration

- `uv sync --all-packages --frozen` succeeds after lockfile generation.
- `uv run kotekomi-agent validate-task <valid fixture>` invokes the package command.
- `uv run pytest packages/devtools/tests/acceptance/test_task_manifest_contract.py` discovers the protected acceptance suite.
- `uv run pytest` discovers the devtools tests from the repository root.
- `uv run ruff check` includes the devtools package.
- `uv run pyright` includes the devtools package.

### Gate 3: valid manifests

- The canonical valid fixture exits `0`.
- Valid stdout matches the compact JSON contract.
- Valid stderr is empty.
- The equivalent-format fixture returns the same digest.
- The reordered-array fixture returns a different digest.
- Every valid digest contains sixty-four lowercase hexadecimal characters.

### Gate 4: schema failures

The protected acceptance suite proves these cases:

- missing required field;
- unknown top-level field;
- unknown nested field;
- invalid task ID;
- invalid baseline revision;
- invalid digest;
- empty acceptance argument vector;
- shell command string;
- invalid acceptance profile;
- nonempty unresolved-decision list;
- multiple schema errors in stable order;
- schema failure prevents post-schema path diagnostics.

Each case exits `1`.

Each case writes one invalid JSON result to stdout.

Each case leaves stderr empty.

### Gate 5: semantic and path failures

The protected acceptance suite proves these cases:

- absolute path;
- parent traversal;
- backslash path;
- `./` path prefix;
- repeated slash;
- `~` path prefix;
- wildcard path;
- trailing slash on `tdd_path`;
- duplicate allowed path;
- duplicate reference path;
- duplicate protected artifact path;
- protected directory path;
- duplicate acceptance ID;
- multiple path failures in stable order.

Each case exits `1`.

Path cases return `task_manifest.path_violation`.

The duplicate acceptance ID returns `task_manifest.semantic_violation`.

Each case identifies the exact invalid location and semantic rule.

### Gate 6: file and CLI failures

- A missing manifest returns `task_manifest.file_not_found` with rule `exists`.
- A directory or other read failure returns `task_manifest.file_unreadable` with rule `readable`.
- Invalid UTF-8 returns `task_manifest.file_unreadable` with rule `utf8`.
- Malformed TOML returns `task_manifest.toml_parse_error` with rule `toml`.
- Expected file failures emit no traceback.
- Expected file failures leave stderr empty.
- Invalid CLI invocation exits `2`.
- Invalid CLI invocation writes usage information to stderr.
- Invalid CLI invocation writes no stdout.

### Gate 7: package boundary and execution isolation

- Devtools source imports no product package.
- Devtools runtime dependencies include no product package.
- Product packages import no devtools package.
- The root workspace contains `packages/devtools`.
- The root development dependency group installs `kotekomi-devtools` from the workspace.
- Root Pytest configuration discovers devtools tests and source.
- Root Pyright configuration includes devtools tests and source.
- The harness performs no repository write during validation.
- The harness executes no manifest command during validation.

### Gate 8: repository verification

Portable local checks:

```text
uv run pytest packages/devtools/tests/acceptance/test_task_manifest_contract.py
uv run ruff check
uv run pyright
```

Authoritative Linux checks:

```text
uv run python scripts/generate_schemas.py
git diff --exit-code -- schemas
uv run ruff check
uv run pyright
uv run pytest
```

The first Candidate Commit passes every portable check without a human rebrief.

The authoritative Linux profile passes on the exact Candidate Commit.

## Cross-Cutting Concerns

### Security

The CLI treats manifest commands as inert argument arrays.

The CLI does not execute a shell.

The CLI does not resolve or access manifest paths during H1 validation.

### Determinism

Canonical serialization fixes object-key order and JSON separators.

The digest preserves array order.

Diagnostics have a fixed sort order.

JSON output has a fixed field order.

### Platform behavior

The H1 acceptance suite is platform-independent.

The full repository suite remains authoritative on Linux.

H1 does not change platform-sensitive PDF goldens.

### Error handling

Expected invalid input returns exit `1` without a traceback.

Unreadable files use rule `readable`.

Invalid UTF-8 files use rule `utf8`.

Usage errors return exit `2`.

Unexpected internal failures return exit `70`.

## Reference Implementations

- `pyproject.toml` defines workspace and root quality-tool integration.
- `packages/domain/pyproject.toml` shows the package build layout.
- `docs/agent/testing.md` defines test-boundary rules.
- `docs/agent/documentation-style.md` defines contract-document style.
- `.agent/schemas/task-manifest-v1.schema.json` is the protected schema authority.
- Python `tomllib` is the TOML parser.
- `jsonschema` Draft 2020-12 validation is the schema-validation mechanism.

## Alternatives Considered

- YAML was rejected because TOML is already native to the Python 3.12 toolchain.
- Shell command strings were rejected because they create quoting and injection ambiguity.
- External Codex model names were rejected because CLI names can change independently from project process profiles.
- A self-digest inside the Task Manifest was rejected because it creates a recursive identity problem.
- Duplicate schemas were rejected because they create authority drift.
- Filesystem existence checks were deferred to H2 because H1 validates contract shape only.
- Git revision checks were deferred to H2 because H1 performs no Git inspection.

## Halt Conditions

No unresolved decision remains.

Stop implementation when the protected schema and this TDD conflict.

Stop implementation when a required behavior needs Git inspection.

Stop implementation when a required behavior needs command execution.

Stop implementation when the package would need a KoteKomi product dependency.

Stop implementation when a protected acceptance case has more than one valid output.
