# Pipeline Agent Guidelines

## Required Reads

Read before editing `packages/pipelines`:

1. `docs/agent/pipelines.md`
2. `docs/agent/architecture.md`
3. `docs/agent/domain.md`
4. `docs/agent/testing.md`

## Boundary

Pipelines expose user-visible workflows.

Pipelines compose Application Layer use cases.

Pipelines write canonical state through the Application Layer.

Pipelines open Ledger transactions around Application Layer use cases.

Pipelines keep canonical state in the Ledger and Archive.

## Checks

Run Pipeline fixture tests after each change.

Verify ProvenanceActivity records for state changes.

Verify model output creates ProposedChange records before accepted state.
