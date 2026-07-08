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

## Checks

Run Adapter tests with fixtures.

Do not pass tool-native shapes across the Application Layer boundary.
