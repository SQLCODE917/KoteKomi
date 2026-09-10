# TDD: Monotonic Role Completion

- Status: Superseded by HSQ-7
- Deliverable ID: HSQ-2
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [HSQ-1 Governed Event Coverage](2026-09-06-governed-event-coverage.md)
- Superseded by: [HSQ-7 Bounded Semantic Task Allocation](2026-09-08-bounded-semantic-task-allocation.md)

## Context & Problem

The current HP-6 flow validates normalization role targets and then discards them.

Separate role tasks can replace valid targets with unrelated source spans.

**AssignmentOrigin** means the stage that supplied one selected role target.

### Primary end-to-end flow

1. Qwen proposes one normalized frame and role set.
2. KoteKomi validates each proposed role target.
3. KoteKomi preserves each valid target.
4. Qwen completes only missing or invalid roles.
5. KoteKomi constructs one event from the combined monotonic role set.

## Goals

- A reviewer sees valid normalization assignments preserved.
- A reviewer can identify the origin of every role assignment.
- The Pipeline avoids redundant role-completion work.

## Requirements

### Domain Core

- MRC-DOM-01: `AssignmentOrigin` contains `normalization` and `role_completion`.
- MRC-DOM-02: Each EventArgumentAssignmentDraft records one AssignmentOrigin.

### Application Layer

- MRC-APP-01: The Application Layer validates normalization assignments before completion.
- MRC-APP-02: The Application Layer preserves each valid normalization assignment.
- MRC-APP-03: The Application Layer calls role completion only for a missing or invalid role.
- MRC-APP-04: Role completion cannot overwrite a valid normalization assignment.
- MRC-APP-05: The Application Layer retains rejected completion output in stage evidence.

## Proposed Architecture

```text
normalization assignments
        |
        v
source validation ---- invalid or missing roles ----> role completion
        |                                                |
        +---------------- monotonic union ----------------+
                              |
                              v
                    EventSemanticDraft
```

## Key Interactions

```text
Application -> KoteKomi validator: normalization target
validator -> Application: valid or invalid
Application -> Qwen: each missing or invalid role
Qwen -> Application: completed target or absent
Application -> Domain Core: complete monotonic role set
```

## Data Model

`EventArgumentAssignmentDraft.assignment_origin` records the selected stage.

The assignment identity includes AssignmentOrigin.

## Behavior & Domain Rules

- MRC-RUL-01: A selected normalization assignment has precedence over completion output.
- MRC-RUL-02: An unresolved required role creates a typed coverage gap.
- MRC-RUL-03: An unresolved optional role remains absent.

## Acceptance Criteria

- AC-MRC-APP-01: A complete valid normalization result causes zero role-completion calls.
- AC-MRC-APP-02: An invalid target causes one bounded completion sequence for that role.
- AC-MRC-APP-03: A conflicting completion target cannot replace a valid target.
- AC-MRC-DOM-01: Canonical serialization preserves every AssignmentOrigin.
- AC-MRC-RUL-01: Existing HP-6 Gold events retain every adjudicated role.

## Reference Implementations

- Role validation: follow `packages/application/src/kotekomi_application/hybrid_event_semantics_preview.py`.
- Stage traces: follow `packages/application/src/kotekomi_application/extraction_stage_trace.py`.
