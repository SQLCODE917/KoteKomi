# Review Readiness and Agent State

## 1. Context & Problem

Review Readiness is a derived state summary for pending ProposedChange records.
Agent State is the machine-readable form of Review Queue, Review Packet, and readiness outputs.
KoteKomi can show human-readable review queues and packets.
KoteKomi does not yet expose structured review state that agents can consume without parsing text.

## 2. Goals

- Let agents detect when ProposedChange review blocks downstream Pipeline steps.
- Expose Review Queue and Review Packet objects as JSON.
- Expose Review Readiness as JSON and text.
- Count pending ProposedChange records by record type.
- Count pending and missing references across matching pending ProposedChange records.
- Keep human text output as the default CLI format.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not block graph projection commands.
- This TDD does not block Briefing generation commands.
- This TDD does not add a scheduler or workflow engine.
- This TDD does not add Ledger tables.
- This TDD does not add Domain Core records.
- This TDD does not add review automation.

Forbidden approaches:

- Agents must not parse human CLI text to determine readiness.
- The Pipeline must not assemble readiness by parsing printed Review Packets.
- The readiness command must not change ProposedChange review status.
- The readiness command must not repair malformed ProposedChange records.
- The JSON output must not include Markdown-only structures.
- The JSON output must not require a downstream caller to infer enum names from display text.

## 4. Requirements

- `review status` must inspect pending ProposedChange records by default.
- `review status` must accept record type, Source ID, and Document ID filters.
- `review status` must report `review_required`.
- `review status` must report `pending_count`.
- `review status` must report pending counts by record type.
- `review status` must report `pending_reference_count`.
- `review status` must report `missing_reference_count`.
- `review status` must report `can_project_graph`.
- `review status` must report `can_generate_briefing`.
- `review status` must report `next_recommended_command`.
- `review status` must fail fast on malformed matching ProposedChange records.
- `review list --format json` must emit JSON.
- `review show --format json` must emit JSON.
- JSON output must use primitive JSON values, arrays, and objects.
- JSON output must serialize enums as strings.
- JSON output must serialize datetimes as ISO 8601 strings.

## 5. Invariants

- ProposedChange remains the gate before accepted Ledger state.
- Review readiness is derived from the Ledger.
- Review readiness does not become canonical Ledger state.
- Review readiness does not change accepted Ledger records.
- Review readiness does not approve, reject, or edit ProposedChange records.
- Domain Core records and Application Layer DTOs remain boundary contracts.
- Deterministic invalid ProposedChange shape fails fast.

## 6. Proposed Architecture

The Pipeline exposes text and JSON review commands.
The Application Layer builds Review Readiness from Review Queue and Review Packet DTOs.
The Application Layer serializes review DTOs to JSON-compatible objects.
The LedgerRepository Port loads ProposedChange records and referenced records.
The SQLite Adapter persists and loads records without readiness decisions.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| review commands  |       | review state DTOs   |
+------------------+       +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | LedgerRepository    |
                           | Ledger records      |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | SQLite Adapter      |
                           | persistence only    |
                           +---------------------+
```

## 7. Key Interactions

### Agent Reads Readiness

```text
Agent -> Pipeline: review status --format json
Pipeline -> Application Layer: get Review Readiness
Application Layer -> LedgerRepository: list ProposedChange records
Application Layer -> Application Layer: inspect matching Review Packets
Application Layer -> Pipeline: ReviewReadinessStatus
Pipeline -> Agent: JSON object
```

### Agent Reads Queue

```text
Agent -> Pipeline: review list --format json
Pipeline -> Application Layer: list Review Queue
Application Layer -> Pipeline: ReviewQueueResult
Pipeline -> Agent: JSON object
```

### Agent Reads Packet

```text
Agent -> Pipeline: review show --format json
Pipeline -> Application Layer: get Review Packet
Application Layer -> Pipeline: ReviewPacket
Pipeline -> Agent: JSON object
```

## 8. Data Model

`ReviewReadinessStatus` summarizes matching pending ProposedChange records.

```text
ReviewReadinessStatus
- review_required
- pending_count
- pending_record_type_counts
- pending_reference_count
- missing_reference_count
- can_project_graph
- can_generate_briefing
- next_recommended_command
- blockers
```

`ReviewReadinessBlocker` identifies one unresolved dependency.

```text
ReviewReadinessBlocker
- proposed_change_id
- record_type
- stable_label
- referenced_type
- referenced_id
- resolution_status
```

## 9. APIs / Interfaces

The Application Layer adds `get_review_readiness`.
The Application Layer adds `review_queue_result_to_json`.
The Application Layer adds `review_packet_to_json`.
The Application Layer adds `review_readiness_to_json`.

`ReviewReadinessInput` contains:

- `record_type`
- `source_id`
- `document_id`

The Pipeline adds:

```text
kotekomi review status
kotekomi review status --format json
kotekomi review list --format json
kotekomi review show --format json
```

## 10. Behavior & Domain Rules

`review_required` is `true` when at least one matching ProposedChange is pending.
`can_project_graph` is `false` when `review_required` is `true`.
`can_generate_briefing` is `false` when `review_required` is `true`.
`next_recommended_command` is `kotekomi review next` when review is required.
`next_recommended_command` is `kotekomi graph project` when no review is required.

Readiness counts `pending` references separately from `missing` references.
Pending references identify dependency order work.
Missing references identify invalid or incomplete proposed state.
Both appear in `blockers`.

Example:

```text
The Ledger has 16 pending ProposedChange records.
review_required = true
can_project_graph = false
next_recommended_command = kotekomi review next
```

Example:

```text
The Ledger has no pending ProposedChange records.
review_required = false
can_generate_briefing = true
next_recommended_command = kotekomi graph project
```

Example:

```text
An Assertion proposal references a missing EvidenceSpan.
missing_reference_count = 1
The missing EvidenceSpan appears in blockers.
```

## 11. Acceptance Criteria

- Application tests prove readiness reports review required when pending ProposedChange records exist.
- Application tests prove readiness reports graph and Briefing readiness when no pending records exist.
- Application tests prove readiness counts pending references.
- Application tests prove readiness counts missing references.
- Application tests prove readiness filters by record type, Source ID, and Document ID.
- Application tests prove queue JSON uses structured objects.
- Application tests prove packet JSON uses structured objects.
- Application tests prove readiness JSON uses structured objects.
- Application tests prove malformed ProposedChange records fail fast.
- Pipeline tests prove fixture `review status` reports 16 pending ProposedChange records before review.
- Pipeline tests prove fixture `review list --format json` parses as JSON.
- Pipeline tests prove fixture `review show --format json` parses as JSON.
- Pipeline tests prove fixture `review status` reports no review required after review completes.
- `docs/CHECK_PLAN.md` includes Review Readiness checks.

## 12. Cross-Cutting Concerns

JSON output is the agent contract.
Text output is for humans.
Both outputs derive from the same Application Layer DTOs.

The command reads local Ledger state only.
The command does not fetch network content.

## 13. Reference Implementations

- `packages/application/src/kotekomi_application/review_queue_packet.py`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`
- `packages/pipelines/tests/test_review_queue_packet.py`
- `docs/2026-07-09-review-queue-and-review-packet.md`

## 14. Alternatives Considered

- Text-only status: rejected because agents would parse human output.
- Persist readiness state: rejected because readiness derives from Ledger records.
- Block downstream commands now: rejected because observability is the smaller contract.
- Add one JSON mode for all commands later: rejected because agents need review state now.

## 15. Halt Conditions

- Halt if JSON output requires parsing rendered text.
- Halt if readiness requires Adapter imports in the Application Layer.
- Halt if malformed deterministic state is silently skipped.
- Halt if readiness mutates review status or accepted Ledger state.
