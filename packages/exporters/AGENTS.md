# Exporter Agent Guidelines

## Required Reads

Read before editing `packages/exporters`:

1. `docs/agent/domain.md`
2. `docs/agent/adapters.md`
3. `docs/agent/testing.md`

## Boundary

Exporters write derived files from Ledger records.

Exporters do not own canonical state.

Exporters do not change accepted records.

## Expected Export Formats

Initial export formats:

- JSONL
- GraphML
- Mermaid
- JSON-LD
- Schema.org

## Checks

Run Exporter tests after each change.

Verify exported records preserve canonical IDs.

Verify exports can be regenerated from the Ledger.
