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

Briefings use numbered citations in human-facing Markdown.

Briefing citation registries store Source IDs and EvidenceTarget IDs.

Default human-facing Briefing Markdown does not expose raw canonical Domain IDs.

Briefings label analytic inference.

## Checks

Run Briefing tests after each change.

Verify visible text.

Verify Source IDs through structured citation registry data.

Verify EvidenceTarget IDs through structured citation registry data.

Verify human-facing Markdown does not expose raw canonical Domain IDs.

Verify analytic inference labels.
