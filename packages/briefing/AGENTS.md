# Briefing Agent Guidelines

## Required Reads

Read before editing `packages/briefing`:

1. `docs/agent/domain.md`
2. `docs/agent/pipelines.md`
3. `docs/agent/output-format.md`
4. `docs/agent/testing.md`

## Boundary

The Briefing package defines Briefing structure and rendering.

Briefings explain changed Ledger state since a previous Briefing.

Briefings cite Source IDs and EvidenceSpan IDs.

Briefings label analytic inference.

## Checks

Run Briefing tests after each change.

Verify visible text.

Verify Source IDs.

Verify EvidenceSpan IDs.

Verify analytic inference labels.
