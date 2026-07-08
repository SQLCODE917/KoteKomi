# Application Layer Agent Guidelines

## Required Reads

Read before editing `packages/application`:

1. `docs/agent/architecture.md`
2. `docs/agent/domain.md`
3. `docs/agent/testing.md`

## Boundary

The Application Layer implements use cases.

The Application Layer defines Ports.

The Application Layer depends on the Domain Core.

The Application Layer does not depend on specific tools.

## Checks

Run Application Layer tests after each change.

Use fake Ports for Application Layer tests.

Do not import Adapter implementations.
