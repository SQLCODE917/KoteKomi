# Adapter Agent Guidelines

## Required Reads

Read before editing `packages/adapters`:

1. `docs/agent/adapters.md`
2. `docs/agent/architecture.md`
3. `docs/agent/testing.md`

## Boundary

Adapters implement Application Layer Ports.

Adapters map tool-native shapes into Application Layer DTOs or Domain Core objects.

Adapters validate external input before passing it inward.

Adapters translate, persist, and load records.

Adapters do not decide Domain meaning, status transitions, review outcomes, or repair policy.

## Checks

Run Adapter tests with fixtures.

Do not pass tool-native shapes across the Application Layer boundary.
