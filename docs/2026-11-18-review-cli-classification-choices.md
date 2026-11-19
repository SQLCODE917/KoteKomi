# Review CLI Classification Choices

## Context & Problem

An operator uses `review decide` to classify an ingested Event before recomposition.
An Assertion states an atomic meaning.
A ProposedChange holds a proposed record until separate review.
The CLI currently advertises `reported_claim`, `second_hand_report`, `anonymous_report`, and `unknown` as an attribution choice.
Those strings are absent from their Domain Core enums.
The CLI constructs the enums after it loads the review packet.
The planned change removes those invalid choices.

Primary end-to-end Flow:

1. The operator enters review decisions through the existing command.
2. The parser validates the declared classification choices.
3. Valid arguments reach the existing review workflow.
4. Invalid arguments produce a usage error before storage access.

The [Agile package](2026-11-18-review-cli-classification-agile-package.md) owns scope, iteration limits, and stop decisions.

## Goals

- Operators receive valid advertised classification choices.
- Operators receive an immediate usage error for unsupported spellings.
- Existing valid review arguments retain their meaning.

## Requirements

### Pipeline argument boundary

- RCR-01: The parser offers only `reported_observation` for `--assertion-type`.
- RCR-02: The parser offers only `direct_document` for `--attribution-basis`.
- RCR-03: The parser retains `primary`, `secondary`, `tertiary`, and `unknown` for `--source-authority`.
- RCR-04: The command rejects other values with parser exit code 2 before configuration or Ledger access.
- RCR-05: The command preserves valid identity, predicate, reviewer, run, and Event arguments.
- RCR-06: The CLI help and operator guide describe this restricted workflow.

## Proposed Architecture

The Pipeline parser owns command admission.
The Domain Core retains classification definitions.
The existing Application Layer owns review decisions and accepted prerequisite writes.

```text
Operator -> Pipeline parser -> Review workflow -> Application Layer -> Ledger
                 |
                 v
             Domain Core
```

## Key Interactions

```text
Operator       Parser        Review workflow
   | arguments    |                 |
   |------------->|                 |
   |              | valid arguments |
   |              |---------------->|
   | usage error  |                 |
   |<-------------| invalid values  |
```

## Data Model

The change adds no stored records.
Existing review records, ProposedChanges, and ProvenanceActivity records retain their contracts.

## APIs / Interfaces

Requirements RCR-01 through RCR-03 define the restricted command vocabulary.
The command does not map invalid spellings to different meanings.

## Behavior & Domain Rules

Requirement RCR-04 applies before any review packet is loaded.
Valid input follows the retained review path.
Separate Assertion acceptance remains required.
The Domain Core enums remain unchanged.

## Acceptance Criteria

- AC-01: Parser tests verify RCR-01 through RCR-03 and conversion of each offered value to its canonical enum.
- AC-02: Negative command tests verify RCR-04 for all four previously advertised invalid strings and arbitrary invalid input.
- AC-03: Tests guard configuration and review access with failure sentinels during invalid-input checks.
- AC-04: A valid command fixture verifies RCR-05 with `reported_observation`, `secondary`, and `direct_document`.
- AC-05: Help assertions and documentation review verify RCR-06.
- AC-06: Existing review journey regressions remain passing; this is regression evidence, not new semantic validation.

## Reference Implementations

- Parser and dispatch: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- CLI tests: `packages/pipelines/tests/test_cli.py`.
- Classification definitions: `packages/domain/src/kotekomi_domain/models.py`.
- Review behavior: `packages/application/src/kotekomi_application/event_construction_review.py`.
- Operator instructions: `docs/operator-ingestion.md`.

## Constraints and Halt Conditions

Follow the existing `implement-tdd` Harness status before implementation.
Stop when the Harness reports blocked.
This specification handoff permits no production edits, merge, remote-reference fabrication, or Harness modification before the gate clears.
Long-running verification follows the repository's human-started execution rule.
