# Task Preflight and Protected-Oracle Locks

## Status

Document class: Leaf TDD

Design status: Accepted

Series: `docs/2026-07-14-terra-high-harness-series-plan.md`

Series leaf: H2

Planning baseline: `1e04a4a2a638203e8e6901e59bc3baf4cc7dba85`

Implementation profile: `terra-high-v1`

Prerequisite: `harness-01-task-manifest-contract`

## Context & Problem

H1 validates the shape and deterministic meaning of one Task Manifest.

H1 does not prove that the manifest belongs to the current Git state.

H1 does not lock the Leaf TDD, protected acceptance oracle, dependency receipts, or implementation scope.

H2 adds one read-only preflight command that determines whether a validated task can begin.

## Goals

- Add one deterministic `preflight-task` command.
- Require execution from the exact repository root.
- Derive the specification commit from Task Manifest history.
- Require `HEAD` to equal that specification commit.
- Require a clean worktree and index.
- Lock the Leaf TDD and every protected artifact to committed and current bytes.
- Validate reference paths at the specification commit.
- Reject allowed scopes that can modify protected paths.
- Reject allowed paths with symbolic-link ancestors.
- Require one unambiguous verified receipt for every dependency.
- Preserve H1 validation behavior and diagnostics unchanged.
- Emit one stable machine-readable result without repository mutation.

## Non-Goals & Forbidden Approaches

### Non-Goals

- H2 does not execute acceptance commands.
- H2 does not verify a Candidate Commit.
- H2 does not create a candidate Verification Receipt.
- H2 does not promote tasks into an Acceptance Registry.
- H2 does not run retained checks.
- H2 does not change Task Manifest V1.
- H2 does not change H1 validation behavior.
- H2 does not modify GitHub Actions.
- H2 does not write repository files.
- H2 does not stage files, switch branches, or change Git history.
- H2 does not select among several matching dependency receipts.
- H2 does not validate private provider credentials or live services.

### Forbidden Approaches

- Do not execute a shell command supplied by a Task Manifest.
- Do not execute any acceptance command during preflight.
- Do not infer the execution base from a branch name.
- Do not accept an uncommitted Task Manifest as ready.
- Do not accept a later unrelated `HEAD` as the execution base.
- Do not treat an ignored or untracked receipt as dependency authority.
- Do not select the newest matching receipt when several match.
- Do not follow symbolic links to satisfy a protected path.
- Do not modify the index, branch, `HEAD`, or worktree.
- Do not duplicate H1 schema validation.
- Do not add product-package dependencies.
- Do not edit protected specification records during implementation.

## Requirements

1. The CLI exposes `kotekomi-agent preflight-task PATH`.
2. `PATH` uses repository-relative POSIX exact-file syntax.
3. The command requires the current directory to be the physical Git repository root.
4. Stage 1 returns only invocation and repository-context diagnostics.
5. Stage 2 invokes the existing H1 Task Manifest validation contract.
6. Stage 2 returns H1 diagnostics unchanged.
7. Stage 2 prevents every Git readiness check when H1 validation fails.
8. Stage 3 evaluates every independent discoverable readiness violation.
9. Stage 3 derives the execution base from history for the Task Manifest path.
10. Stage 3 requires current `HEAD` to equal the execution base.
11. Stage 3 requires the worktree and index to be clean.
12. Stage 3 validates `baseline_revision` against the execution base.
13. Stage 3 locks the Leaf TDD to committed and current bytes.
14. Stage 3 locks every protected artifact to committed and current bytes.
15. Stage 3 validates exact-file and directory reference paths.
16. Stage 3 rejects allowed scopes that overlap implicit protected paths.
17. Stage 3 rejects allowed paths with existing symbolic-link components.
18. Stage 3 validates one verified tracked receipt for every dependency.
19. The command returns deterministic diagnostics and field order.
20. The command performs no repository write or Git mutation.
21. Expected not-ready results write no stderr text.
22. H1 protected acceptance remains green.
23. The H2 acceptance module skips only while `preflight-task --help` reports the subcommand absent.
24. Candidate verification requires the H2 command help and all H2 cases to run without skips.

## Invariants

- Task Manifest V1 remains the only manifest-shape authority.
- H1 validation output remains unchanged.
- The execution base is derived from Git history, not user input.
- The Task Manifest binds itself through its specification commit.
- The Leaf TDD and protected artifacts remain immutable during implementation.
- Ignored files do not make a task not ready.
- Staged, unstaged, and untracked non-ignored files make a task not ready.
- Reference files remain advisory unless also protected.
- Dependency authority comes only from tracked regular JSON files.
- Several matching dependency receipts remain an explicit failure.
- Preflight performs no writes.
- Preflight executes no Task Manifest command.
- Product packages remain independent from `kotekomi-devtools`.
- The bootstrap skip deactivates as soon as the H2 subcommand exists.
- A help failure other than the absent-subcommand response does not activate the bootstrap skip.

## Proposed Architecture

```text
kotekomi-agent preflight-task
             |
             v
Invocation and Repository Context
             |
             v
H1 Task Manifest Validator
             |
             v
Specification Commit Resolver
             |
       +-----+-----+
       |           |
       v           v
Artifact Locks   Scope and Receipt Checks
       |           |
       +-----+-----+
             |
             v
Stable Preflight Result
```

The CLI owns argument parsing and exit-code mapping.

The repository-context component validates the current Git root.

The H1 validator remains the only Task Manifest validation authority.

The specification resolver derives the execution-base revision from path history.

Artifact locks compare committed blobs and current regular files.

Scope checks prevent implementation access to protected records.

Receipt checks inspect tracked committed JSON receipts.

The result component orders diagnostics and emits compact JSON.

## Key Interactions

### Ready task

```text
User
  |
  | kotekomi-agent preflight-task .agent/tasks/task.toml
  v
CLI
  |
  | Stage 1 passes
  v
H1 Validator
  |
  | valid manifest
  v
Git and File Locks
  |
  | clean, exact specification HEAD, valid locks
  v
Dependency Receipts
  |
  | one leaf_verified receipt per dependency
  v
CLI
  |
  | ready JSON and exit 0
  v
User
```

### Invalid Task Manifest

```text
User
  |
  | preflight-task PATH
  v
Stage 1
  |
  | passes
  v
H1 Validator
  |
  | H1 diagnostics
  v
CLI
  |
  | not_ready JSON and exit 1
  |
  | no Stage 3 checks
  v
User
```

### Valid manifest with readiness failures

```text
User
  |
  | preflight-task PATH
  v
Stage 1 and H1
  |
  | pass
  v
Stage 3 Readiness
  |
  | all discoverable violations
  v
Stable Diagnostic Sort
  |
  | not_ready JSON and exit 1
  v
User
```

## Data Model

### Preflight result

The public result uses this field order:

```text
status
schema_version
task_id
manifest_sha256
manifest_file_sha256
execution_base_revision
diagnostics
```

`status` is `ready` or `not_ready`.

`schema_version` and `task_id` follow H1 parsed-identity rules.

`manifest_sha256` is H1 canonical parsed-manifest identity.

`manifest_file_sha256` is SHA-256 over exact readable Task Manifest bytes.

`execution_base_revision` is the resolved forty-character Git commit.

`diagnostics` contains ordered H1 or H2 diagnostics.

### Diagnostic

Every diagnostic uses this field order:

```text
code
location
rule
```

H1 diagnostics retain their existing code, location, and rule.

H2 diagnostics use the tables in this document.

### Implicit protected path set

The implicit protected set contains:

- the Task Manifest path supplied to `preflight-task`;
- `tdd_path`;
- every `protected_artifacts[].path`.

The Task Manifest does not need a self-referential digest.

Its specification commit binds its bytes.

## APIs / Interfaces

### Command

```text
kotekomi-agent preflight-task PATH
```

The command expects `PATH` to be relative to the exact repository root.

### Ready result

```json
{"status":"ready","schema_version":1,"task_id":"harness-02-task-preflight","manifest_sha256":"<64 lowercase hex>","manifest_file_sha256":"<64 lowercase hex>","execution_base_revision":"<40 lowercase hex>","diagnostics":[]}
```

### Not-ready result

```json
{"status":"not_ready","schema_version":1,"task_id":"harness-02-task-preflight","manifest_sha256":"<64 lowercase hex or null>","manifest_file_sha256":"<64 lowercase hex or null>","execution_base_revision":"<40 lowercase hex or null>","diagnostics":[{"code":"task_preflight.repository_violation","location":"/repository","rule":"clean_worktree"}]}
```

### Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | The task is ready |
| `1` | The task is not ready |
| `2` | CLI invocation is invalid |
| `70` | An unexpected internal failure occurred |

Expected not-ready results write one compact JSON object to stdout.

Expected not-ready results leave stderr empty.

CLI usage errors write usage text to stderr.

Unexpected internal failures write no stdout and one stable stderr line.

## Behavior & Domain Rules

### Manifest argument syntax

The supplied manifest argument:

- is nonempty;
- is not absolute;
- has no `.` segment;
- has no `..` segment;
- has no backslash;
- has no repeated slash;
- has no `~` prefix;
- has no `*`, `?`, `[`, or `]` wildcard;
- does not end with `/`.

Invalid repository-relative syntax uses rule `repository_relative_posix`.

A trailing slash uses rule `exact_file`.

Stage 1 does not read the manifest when the argument is invalid.

### Repository context

The command asks Git for the repository top level.

Failure to identify a repository uses rule `git_repository`.

The current physical directory must identify the same directory as the Git top level.

A repository subdirectory uses rule `repository_root`.

Stage 1 returns all discoverable Stage 1 diagnostics.

Stage 1 failure leaves every identity field null.

Stage 1 failure prevents H1 and Stage 3 execution.

### H1 validation stage

After Stage 1 passes, the command invokes `validate_task_manifest`.

A readable manifest always receives `manifest_file_sha256`.

A missing or unreadable manifest has a null raw-file digest.

If H1 returns invalid:

- `status` is `not_ready`;
- H1 diagnostics are returned unchanged;
- `schema_version` and `task_id` use H1 values;
- `manifest_sha256` is null;
- `execution_base_revision` is null;
- Stage 3 does not run.

A valid H1 result supplies the canonical `manifest_sha256`.

H2 can parse the already validated TOML for Stage 3 values.

### Execution-base revision

The execution-base revision is the newest commit reachable from current `HEAD` that changed the supplied Task Manifest path.

The search does not follow an earlier path across a rename.

A deletion commit counts as a commit that changed the path.

The Task Manifest must be a regular Git blob at the execution base.

The current Task Manifest path must be a regular non-symlink file.

Git modes `100644` and `100755` are regular files.

A symbolic link, Git link, tree, missing entry, or other mode fails `tracked_regular_file`.

Current `HEAD` must equal the execution-base revision.

Detached `HEAD` is valid when it equals that revision.

A named branch is not required.

### Baseline revision

`baseline_revision` must resolve to a Git commit.

The baseline commit must be an ancestor of the execution-base revision.

The normal baseline is an earlier commit.

The contract does not define or require a self-referential equality fixture.

A missing commit emits only `commit_exists`.

The ancestor check runs only when both commits resolve.

### Worktree state

The command treats staged, unstaged, and untracked non-ignored files as dirty.

Ignored files do not make the repository dirty.

A dirty repository emits one `clean_worktree` diagnostic.

The dirty-worktree result does not suppress other independent Stage 3 checks.

### Leaf TDD lock

`tdd_path` must be a regular Git blob at the execution base.

The current path must be a regular non-symlink file.

The committed blob SHA-256 must equal `tdd_sha256`.

The current file SHA-256 must equal `tdd_sha256`.

Failure of either regular-file prerequisite emits `tracked_regular_file`.

`digest_match` runs only when both regular-file prerequisites pass.

One digest diagnostic covers committed or current byte mismatch.

### Protected-artifact locks

Each protected artifact follows the Leaf TDD lock rules.

The diagnostic location uses the protected artifact index.

A regular-file failure uses the `path` location.

A byte mismatch uses the `sha256` location.

Digest comparison runs only when committed and current files are regular.

### Reference paths

An exact reference path must be:

- a regular Git blob at the execution base;
- a current regular non-symlink file;
- reachable without a symbolic-link ancestor.

A directory scope ending in `/` must:

- contain at least one regular tracked file under the prefix at the execution base;
- identify a current directory;
- have no symbolic-link component in the current path.

Reference paths are not digest-locked unless also protected.

One failed reference emits `tracked_file_or_nonempty_directory`.

### Protected overlap

Each allowed path is checked once against the complete implicit protected set.

An exact allowed file conflicts when it equals an implicit protected path.

An allowed directory scope conflicts when it contains an implicit protected path.

One allowed path emits at most one `protected_overlap` diagnostic.

### Allowed-path symbolic links

Every existing component below the repository root is inspected.

An allowed path fails when any existing component is a symbolic link.

The final implementation path can be absent.

Nonexistent trailing components are valid after all existing ancestors pass.

One allowed path emits at most one `symlink_ancestor` diagnostic.

### Dependency receipts

Dependency receipt authority uses committed files at the execution base.

H2 searches regular tracked `.json` files under `.agent/receipts/`.

The command parses committed blob bytes, not untracked or ignored files.

A receipt matches when top-level `task_id` equals the dependency ID.

Malformed JSON and non-object JSON do not match.

An unrelated receipt does not match.

Untracked receipts do not match.

Current receipt modifications and symbolic links do not override the committed blob.

Zero matches emits `leaf_verified_receipt`.

One match passes only when top-level `result` equals `leaf_verified`.

One non-verified match emits `leaf_verified_receipt`.

More than one match emits `unique_leaf_verified_receipt`.

Receipt filename and receipt kind do not determine authority.

### Discoverable Stage 3 diagnostics

Stage 3 returns every independent violation whose prerequisites resolve.

Checks that require an execution base run only after it resolves.

The ancestor check runs only after the baseline and execution-base commits resolve.

Digest checks run only after committed and current regular files resolve.

Dependency checks run only after the execution base resolves.

Dirty-state, scope-overlap, and current symlink checks remain independently discoverable.

### Diagnostic ordering

Diagnostics sort by:

1. `location`;
2. `code`;
3. `rule`.

The command returns exactly one diagnostic for each failing rule and location.

### Read-only behavior

The command performs no write.

The command does not modify the Git index.

The command does not switch branches.

The command does not move `HEAD`.

The command does not create or remove files.

The command does not execute acceptance commands.

## Diagnostic Contract

### Invocation and repository diagnostics

| Code | Location | Rule |
|---|---|---|
| `task_preflight.manifest_path_violation` | `/manifest_path` | `repository_relative_posix` |
| `task_preflight.manifest_path_violation` | `/manifest_path` | `exact_file` |
| `task_preflight.repository_violation` | `/repository` | `git_repository` |
| `task_preflight.repository_violation` | `/repository` | `repository_root` |
| `task_preflight.repository_violation` | `/repository` | `clean_worktree` |

### Manifest and revision diagnostics

| Code | Location | Rule |
|---|---|---|
| `task_preflight.manifest_violation` | `/manifest_path` | `tracked_regular_file` |
| `task_preflight.manifest_violation` | `/manifest_path` | `head_is_execution_base` |
| `task_preflight.revision_violation` | `/baseline_revision` | `commit_exists` |
| `task_preflight.revision_violation` | `/baseline_revision` | `ancestor_of_execution_base` |

### TDD and protected-artifact diagnostics

| Code | Location | Rule |
|---|---|---|
| `task_preflight.tdd_violation` | `/tdd_path` | `tracked_regular_file` |
| `task_preflight.tdd_violation` | `/tdd_sha256` | `digest_match` |
| `task_preflight.protected_artifact_violation` | `/protected_artifacts/{index}/path` | `tracked_regular_file` |
| `task_preflight.protected_artifact_violation` | `/protected_artifacts/{index}/sha256` | `digest_match` |

### Reference, scope, and dependency diagnostics

| Code | Location | Rule |
|---|---|---|
| `task_preflight.reference_violation` | `/reference_paths/{index}` | `tracked_file_or_nonempty_directory` |
| `task_preflight.scope_violation` | `/allowed_paths/{index}` | `protected_overlap` |
| `task_preflight.scope_violation` | `/allowed_paths/{index}` | `symlink_ancestor` |
| `task_preflight.dependency_violation` | `/depends_on/{index}` | `leaf_verified_receipt` |
| `task_preflight.dependency_violation` | `/depends_on/{index}` | `unique_leaf_verified_receipt` |

## Bootstrap Activation

The protected H2 acceptance module has one temporary module-wide skip condition.

The skip activates only when `kotekomi-agent preflight-task --help` returns the CLI absent-subcommand response.

The absent-subcommand response has exit code `2` and reports `preflight-task` as an invalid choice.

A missing CLI executable, a different help failure, or an implemented but broken command does not activate the skip.

The H2 specification commit therefore keeps the existing full repository suite green with exactly 52 skipped H2 cases.

Candidate verification first runs the protected `h2-cli` acceptance command.

The `h2-cli` command must exit `0`.

The candidate H2 suite must then report exactly 52 passed cases and zero skipped cases.

The implementation agent cannot satisfy H2 verification by leaving the bootstrap skip active.

## Acceptance Criteria

### Gate 1: specification integrity

- The H2 Task Manifest satisfies Task Manifest V1.
- The H2 Leaf TDD digest matches `tdd_sha256`.
- Every protected artifact digest matches the H2 Task Manifest.
- The H2 Task Manifest has an externally recorded bootstrap digest.
- H1 is represented by one tracked `leaf_verified` receipt.
- Before H2 implementation, the full suite reports exactly 52 skipped H2 cases.
- The bootstrap skip activates only for the absent-subcommand help response.

### Gate 2: command activation and ready result

- The protected `h2-cli` command exits `0`.
- `kotekomi-agent preflight-task --help` writes command usage without an invalid-choice error.
- A disposable ready repository exits `0`.
- Ready stdout matches the exact compact JSON contract.
- Ready stderr is empty.
- Two runs against unchanged state are byte-identical.
- `manifest_sha256` matches H1 canonical serialization.
- `manifest_file_sha256` matches exact manifest bytes.
- `execution_base_revision` equals the specification commit.
- Preflight changes no file, index entry, branch, or `HEAD`.

### Gate 3: Stage 1 failures

The protected suite proves:

- absolute manifest argument;
- `./` manifest argument;
- parent-traversal manifest argument;
- backslash manifest argument;
- repeated-slash manifest argument;
- `~` manifest argument;
- wildcard manifest argument;
- directory manifest argument;
- invocation outside a Git repository;
- invocation from a repository subdirectory;
- several simultaneous Stage 1 violations in stable order.

Each Stage 1 case returns only Stage 1 diagnostics.

Each Stage 1 case leaves identity fields null.

### Gate 4: H1 short circuit

- An H1 schema failure returns H1 diagnostics unchanged.
- An H1 schema failure returns no H2 Stage 3 diagnostic.
- A readable invalid manifest returns its raw-file digest.
- A readable invalid manifest has null canonical and execution-base identities.

### Gate 5: repository and revision readiness

The protected suite proves:

- staged dirty state;
- unstaged dirty state;
- untracked dirty state;
- an untracked current Task Manifest;
- a Task Manifest committed as a symbolic link;
- a regular committed Task Manifest replaced by a current symbolic link;
- a later unrelated `HEAD`;
- a missing baseline commit;
- an existing non-ancestor baseline commit.

Ignored files remain ready.

### Gate 6: TDD and protected locks

The protected suite proves for both TDD and protected artifact:

- missing committed path;
- untracked ignored current path;
- committed symbolic link;
- declared digest mismatch;
- current worktree byte mutation;
- current symbolic-link replacement.

A regular-file failure does not add a digest diagnostic.

### Gate 7: references and scope

The protected suite proves:

- missing exact reference;
- empty directory reference;
- exact reference committed as a symbolic link;
- directory reference with a current symbolic-link component;
- exact allowed-file overlap;
- allowed-directory overlap;
- allowed path with a symbolic-link ancestor;
- absent final allowed path with safe ancestors remains valid.

### Gate 8: dependency receipts

The protected suite proves:

- no matching receipt;
- malformed and unrelated receipts only;
- one untracked matching receipt;
- one matching failed committed receipt;
- a current verified edit that cannot override a failed committed receipt;
- a current symbolic link that cannot override a verified committed receipt;
- several matching receipts;
- one matching `leaf_verified` receipt.

Receipt selection uses committed blobs.

### Gate 9: combined violations

- Several independent Stage 3 failures return together.
- Diagnostics use exact locations and rules.
- Diagnostics use deterministic location, code, and rule ordering.
- Checks without resolved prerequisites do not create cascade diagnostics.

### Gate 10: package and regression checks

- Product packages import no `kotekomi_devtools` module.
- `kotekomi-devtools` imports no KoteKomi product package.
- H1 protected acceptance passes unchanged.
- H2 protected acceptance reports exactly 52 passed cases.
- H2 protected acceptance reports zero skipped cases.
- Devtools unit tests pass.
- Ruff passes.
- Pyright passes.
- The authoritative Linux full repository suite passes.

## Cross-Cutting Concerns

### Security

All Git commands use argument arrays.

The command invokes no shell.

Manifest acceptance arrays remain inert values.

Preflight does not follow symbolic links for authority.

### Determinism

Result and diagnostic field order is fixed.

Diagnostics have one sort order.

The result contains no clock, temporary path, process ID, or random value.

### Platform behavior

Disposable repository tests use Git and the local filesystem.

Symbolic-link cases require macOS or Linux behavior.

The authoritative full repository result remains Linux CI.

### Error handling

Expected not-ready states return exit `1`.

Usage errors return exit `2`.

Unexpected internal failures return exit `70`.

Expected failures emit no traceback.

## Reference Implementations

- `packages/devtools/src/kotekomi_devtools/task_manifest.py` owns H1 validation.
- `packages/devtools/src/kotekomi_devtools/cli.py` owns existing CLI dispatch.
- `.agent/schemas/task-manifest-v1.schema.json` owns Task Manifest V1 shape.
- `.agent/receipts/bootstrap/harness-01-task-manifest-contract-candidate-01.json` is the verified H1 prerequisite.
- `packages/devtools/tests/acceptance/test_task_manifest_contract.py` is the H1 regression oracle.
- `docs/agent/testing.md` defines repository test rules.

## Alternatives Considered

- A branch-name execution base was rejected because branches are mutable labels.
- A manifest-declared specification commit was rejected because it permits self-asserted authority.
- A manifest self-digest was rejected because it creates recursive identity.
- A baseline equal to its containing specification commit was rejected as a content-addressed self-reference.
- Selecting the newest dependency receipt was rejected until a registry defines active authority.
- Filesystem-only receipt discovery was rejected because untracked files are not durable authority.
- Running acceptance commands was deferred to candidate verification.
- Writing preflight receipts was deferred to a later leaf.
- Removing H2 tests from root discovery was rejected because it would weaken permanent acceptance.
- Allowing an unconditional bootstrap skip was rejected because a candidate could remain falsely green.

## Halt Conditions

No unresolved decision remains.

Stop implementation when H1 validation must change.

Stop implementation when preflight requires a repository write.

Stop implementation when a readiness check requires acceptance-command execution.

Stop implementation when dependency authority needs selection among several receipts.

Stop implementation when a protected acceptance case has more than one valid result.
