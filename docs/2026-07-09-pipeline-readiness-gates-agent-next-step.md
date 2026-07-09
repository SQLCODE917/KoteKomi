# Pipeline Readiness Gates and Agent Next Step

## 1. Context & Problem

Pipeline Readiness is a derived summary of the next safe Pipeline command.
Agent Next Step is the machine-readable command recommendation from Pipeline Readiness.
KoteKomi exposes review readiness and agent JSON for review commands.
KoteKomi does not yet expose one Pipeline-level state that agents can query before proceeding.

## 2. Goals

- Let agents ask KoteKomi for the next Pipeline command.
- Report commands that are blocked by pending review.
- Report safe commands from current Ledger state.
- Reuse Review Readiness instead of duplicating review policy.
- Expose Pipeline Readiness as text and JSON.
- Keep the feature read-only.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not block existing commands.
- This TDD does not add a scheduler.
- This TDD does not run the next command.
- This TDD does not persist graph projection metadata.
- This TDD does not add Ledger tables.
- This TDD does not add Domain Core records.

Forbidden approaches:

- Agents must not parse human CLI text to choose the next command.
- The Pipeline must not assemble state by parsing command output.
- The orchestration layer must not mutate Ledger state.
- The orchestration layer must not approve or reject ProposedChange records.
- The orchestration layer must not claim graph projection freshness.
- The orchestration layer must not hide review blockers.

## 4. Requirements

- `pipeline status` must report the current stage.
- `pipeline status` must report the next command.
- `pipeline status` must report safe commands.
- `pipeline status` must report blocked commands.
- `pipeline status` must include Review Readiness fields.
- `pipeline status` must include canonical record counts.
- `pipeline status --format json` must emit JSON.
- `pipeline next` must report the next command and reason.
- `pipeline next --format json` must emit JSON.
- JSON output must use primitive JSON values, arrays, and objects.
- JSON output must serialize enums as strings.
- Pipeline Readiness must fail fast on malformed matching ProposedChange records.

## 5. Invariants

- Pipeline Readiness is derived from Ledger state.
- Pipeline Readiness does not become canonical Ledger state.
- Pipeline Readiness does not change accepted Ledger records.
- Pipeline Readiness does not change ProposedChange review status.
- ProposedChange remains the gate before accepted Ledger state.
- The Application Layer owns stage selection.
- The Pipeline renders Application Layer DTOs.

## 6. Proposed Architecture

The Pipeline exposes `pipeline status` and `pipeline next`.
The Application Layer builds Pipeline Readiness from Ledger records and Review Readiness.
The Application Layer serializes Pipeline DTOs to JSON-compatible objects.
The LedgerRepository Port loads canonical records and ProposedChange records.
The SQLite Adapter persists and loads records without orchestration decisions.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| pipeline command |       | readiness DTOs      |
+------------------+       +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Review Readiness    |
                           | pending review gate |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | LedgerRepository    |
                           | Ledger records      |
                           +---------------------+
```

## 7. Key Interactions

### Agent Reads Pipeline Status

```text
Agent -> Pipeline: pipeline status --format json
Pipeline -> Application Layer: get Pipeline Status
Application Layer -> Review Readiness: get review gate
Application Layer -> LedgerRepository: count accepted records
Application Layer -> Pipeline: PipelineStatus
Pipeline -> Agent: JSON object
```

### Agent Reads Next Step

```text
Agent -> Pipeline: pipeline next --format json
Pipeline -> Application Layer: get Pipeline Next Step
Application Layer -> Application Layer: derive next step from status
Application Layer -> Pipeline: PipelineNextStep
Pipeline -> Agent: JSON object
```

### Human Reads Pipeline Status

```text
User -> Pipeline: pipeline status
Pipeline -> Application Layer: get Pipeline Status
Application Layer -> Pipeline: PipelineStatus
Pipeline -> User: text summary
```

## 8. Data Model

`PipelineStatus` summarizes current Ledger readiness.

```text
PipelineStatus
- stage
- next_command
- safe_commands
- blocked_commands
- blockers
- review_required
- pending_count
- missing_reference_count
- source_count
- document_count
- accepted_assertion_count
- relationship_count
- outcome_count
- argument_edge_count
- briefing_count
- candidate_document_ids
```

`PipelineNextStep` presents one recommended action.

```text
PipelineNextStep
- command
- reason
- stage
- requires_human_review
- blocked
- blockers
```

`PipelineBlocker` describes one blocked command.

```text
PipelineBlocker
- command
- reason
- blocker_type
- blocker_id
```

## 9. APIs / Interfaces

The Application Layer adds `get_pipeline_status`.
The Application Layer adds `get_pipeline_next`.
The Application Layer adds `pipeline_status_to_json`.
The Application Layer adds `pipeline_next_to_json`.

`PipelineStatusInput` has no required fields.

The Pipeline adds these commands:

```text
kotekomi pipeline status
kotekomi pipeline status --format json
kotekomi pipeline next
kotekomi pipeline next --format json
```

## 10. Behavior & Domain Rules

Stage selection uses this order:

1. `review_required` when pending ProposedChange records exist.
2. `ready_for_source_ingest` when no Source records exist.
3. `ready_for_assertion_proposal` when Documents exist and no accepted Assertions exist.
4. `ready_for_briefing` when accepted analytic Assertions or ArgumentEdges exist after the latest Briefing.
5. `briefing_current` when a Briefing exists and no newer accepted record exists.
6. `ready_for_graph_mining` when accepted Assertions, Relationships, and Outcomes exist.
7. `ready_for_graph_projection` when accepted Assertions exist.

`review_required` blocks graph projection, graph mining, and Briefing generation.
`ready_for_source_ingest` recommends `kotekomi source add-file <path>`.
`ready_for_assertion_proposal` recommends `kotekomi source propose-assertions`.
`ready_for_graph_projection` recommends `kotekomi graph project`.
`ready_for_graph_mining` recommends `kotekomi graph mine`.
`ready_for_briefing` recommends `kotekomi briefing generate --title <title>`.
`briefing_current` has no next command.

Graph projection is derived and not persisted.
Pipeline Readiness does not report graph projection freshness.

Example:

```text
The Ledger has pending ProposedChange records.
stage = review_required
next_command = kotekomi review list
```

Example:

```text
The Ledger has a Source and Document but no accepted Assertions.
stage = ready_for_assertion_proposal
candidate_document_ids contains the Document ID.
```

Example:

```text
The Ledger has accepted analytic records and no Briefing.
stage = ready_for_briefing
next_command = kotekomi briefing generate --title <title>
```

## 11. Acceptance Criteria

- Application tests prove an empty Ledger returns `ready_for_source_ingest`.
- Application tests prove a Document without accepted Assertions returns `ready_for_assertion_proposal`.
- Application tests prove pending ProposedChange records return `review_required`.
- Application tests prove review blockers appear in Pipeline blockers.
- Application tests prove accepted initial records return graph readiness.
- Application tests prove accepted mined analytic records return Briefing readiness.
- Application tests prove a current Briefing returns `briefing_current`.
- Application tests prove JSON serializers emit structured objects.
- Pipeline tests prove fixture `pipeline status --format json` changes across ingest, proposal, review, mining, and Briefing generation.
- `docs/CHECK_PLAN.md` includes Pipeline Readiness checks.

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
- `docs/2026-07-09-review-readiness-agent-state.md`

## 14. Alternatives Considered

- Enforce gates now: rejected because this slice is read-only.
- Use Review Readiness alone: rejected because agents need a Pipeline-level next command.
- Persist pipeline state: rejected because the Ledger already stores canonical inputs.
- Track graph projection freshness now: rejected because graph projection metadata is not persisted.

## 15. Halt Conditions

- Halt if Pipeline Readiness requires Adapter imports in the Application Layer.
- Halt if JSON output requires parsing rendered text.
- Halt if the command mutates Ledger state.
- Halt if stage selection hides pending review blockers.
