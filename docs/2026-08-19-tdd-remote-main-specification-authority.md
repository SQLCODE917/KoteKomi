# TDD Remote Main Specification Authority

## Context & Problem

An implementation agent starts a Harness run from a repository worktree.

The Feature Branch Default TDD requires that worktree to check out clean local `main`.

That rule makes the run depend on the caller worktree instead of canonical remote state.

This TDD defines `origin/main` as the specification authority for Task Manifest V2 runs.

The **specification commit** is the `origin/main` commit that contains the Task Manifest.

The **remote manifest** is the Task Manifest blob at the specification commit.

Primary end-to-end flow:

1. The agent requests `implement-tdd` from any repository worktree.
2. The Harness fetches and resolves the specification commit from `origin/main`.
3. The Harness validates the remote manifest against the TDD binding.
4. The Harness records the specification commit and remote manifest digest.
5. The Harness creates `feature/<task-id>` at the specification commit.

## Goals

- An agent can start a V2 run without checking out local `main`.
- A run records one immutable remote specification commit.
- A later main update does not change an active run specification.
- The Harness rejects a remote manifest that conflicts with the TDD binding.

## Requirements

### Specification authority

- SA-01: This TDD supersedes SR-02 through SR-06 of the Feature Branch Default TDD.
- SA-02: `implement-tdd` fetches `origin/main` before it creates new specification evidence.
- SA-03: The Harness resolves the fetched `origin/main` commit as the specification commit.
- SA-04: The Harness reads the remote manifest from the specification commit.
- SA-05: The Harness validates remote manifest bytes through Task Manifest validation.
- SA-06: The Harness compares remote manifest task ID, TDD path, and TDD digest with TDD binding evidence.
- SA-07: The Harness records the specification commit and SHA-256 of remote manifest bytes.
- SA-08: The Harness does not read a local Task Manifest to establish specification evidence.
- SA-09: The Harness accepts a detached, feature-branch, or dirty caller worktree.
- SA-10: The Harness blocks before V2 specification, manifest, or feature-branch evidence when remote specification validation fails.

### Snapshot reuse

- SRU-01: The Harness reuses valid persisted specification evidence without reading current `origin/main`.
- SRU-02: The Harness blocks when the indexed state copy digest conflicts with persisted specification evidence.
- SRU-03: A later `origin/main` commit does not change persisted specification evidence.

### Remote manifest evidence

- RME-01: A V2 run writes exact remote manifest bytes to state before it indexes manifest evidence.
- RME-02: The V2 remote manifest path is `spec/task-manifest.toml` with path scope `state`.
- RME-03: The evidence catalog validates the V2 state copy as Task Manifest TOML.
- RME-04: V1 historical runs retain repository-scoped Task Manifest evidence.
- RME-05: V2 uses evidence key `(spec, task_manifest, manifest)` with the RME-02 state path.
- RME-06: The evidence catalog dispatches Task Manifest validation by the manifest schema version.

### Remote failures

- RF-01: Missing origin, failed fetch, unresolved origin main, absent remote manifest, invalid remote manifest, and binding mismatch return exit code `2`.
- RF-02: The Harness emits diagnostic code `workflow.remote_specification_invalid` for each RF-01 result.

### Feature branch

- FB-01: The feature branch producer creates local and origin feature refs at the specification commit.
- FB-02: The feature branch producer retains existing feature-ref conflict behavior.
- FB-03: The feature branch producer does not switch the caller worktree.

## Proposed Architecture

The implementation workflow owns remote specification selection.

The Task Manifest validator owns remote manifest validation.

The feature branch producer owns feature refs.

```text
Agent worktree -> Implementation workflow -> origin/main commit
                                           -> remote manifest
                                           -> feature/<task-id>
```

## Key Interactions

```text
Agent -> Harness: implement-tdd
Harness -> origin: fetch main
Harness -> origin/main: read manifest blob
Harness -> Evidence catalog: write specification evidence
Harness -> origin: push feature branch
```

## Data Model

The existing specification record remains the canonical record.

The V2 remote manifest state copy is the canonical Task Manifest evidence.

The record stores the specification commit and remote manifest SHA-256 digest.

## APIs / Interfaces

`kotekomi-agent implement-tdd <tdd-path>` keeps its existing interface.

## Behavior & Domain Rules

The Harness binds a new run to the fetched specification commit.

The Harness uses that persisted commit after `origin/main` advances.

The Harness reads the remote manifest for each unpersisted specification attempt.

## Acceptance Criteria

- AC-SA-01: Disposable repository tests prove detached, feature, and dirty worktrees create the same specification evidence.
- AC-SA-02: Tests prove specification evidence uses remote main bytes and revision.
- AC-SA-03: Tests prove absent origin, absent main, invalid remote manifests, and binding mismatches block without evidence.
- AC-SRU-01: Tests prove a later main update retains the original specification record and feature ref.
- AC-FB-01: Tests prove feature-ref conflicts and non-force creation retain current behavior.

## Reference Implementations

- Workflow state: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.
- Feature refs: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

## Constraints and Halt Conditions

The implementation does not add a local-main fallback path.

The implementation does not change V1 historical behavior.
