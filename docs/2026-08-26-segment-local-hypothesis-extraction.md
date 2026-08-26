# TDD: Segment-Local Hypothesis Extraction

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.2
- Depends on: PHP-1.1 Literal Output Hardening

## 1. Context & Problem

PHP-1.1 sends a whole Paragraph to one model task.

The local model often abstains when a Paragraph contains many relationships.

PHP-1.2 sends one SourceSegment to one model task.

### Terms

**Segment work item** means one deterministic AnalysisUnit for one SourceSegment.

### Primary end-to-end flow

1. ContextPlanner derives ordered SourceSegments from one authoritative Paragraph.
2. ContextPlanner persists one Segment work item for each SourceSegment.
3. The Pipeline sends the exact text of one SourceSegment to one model task.
4. The Application Layer verifies the returned claims against that SourceSegment.
5. The Pipeline creates pending ProposedChanges for verified claims within Paragraph capacity.

## 2. Goals

- A reviewer can inspect one model response against one exact SourceSegment.
- KoteKomi keeps direct Organization relationship extraction within PHP-1 scope.
- KoteKomi preserves a visible outcome for each SourceSegment.

## 3. Requirements

### ContextPlanner

- PHP12-PLAN-01: ContextPlanner derives Segment work items with `segment_local_hypothesis_v1`.
- PHP12-PLAN-02: Each Segment work item includes one parent Paragraph and one literal SourceSegment label in its deterministic identity.
- PHP12-PLAN-03: Each Segment ContextManifest renders only the exact selected SourceSegment.

### Pipeline

- PHP12-PIPE-01: The Pipeline pins `paragraph_hypothesis_segment_v1`.
- PHP12-PIPE-02: The Pipeline creates one ModelRun for each Segment work item.
- PHP12-PIPE-03: The Pipeline processes Segment work items in source order.

### Application Layer

- PHP12-VERIFY-01: The Application Layer keeps the PHP-1 text validator and exact mention checks.
- PHP12-VERIFY-02: The Application Layer reuses one EvidenceTarget for distinct claims from one SourceSegment.
- PHP12-VERIFY-03: The Application Layer keeps the existing PHP-1.1 eight-claim batch rule unchanged.

## 4. Proposed Architecture

```text
Paragraph
  -> SourceSegment
  -> Segment work item
  -> ContextManifest
  -> ModelRun
  -> pending ProposedChanges
```

ContextPlanner owns SourceSegment identity and ContextManifest rendering.

The Pipeline owns task order.

The Application Layer owns validation and pending record creation.

## 5. Key Interactions

```text
Pipeline -> ContextPlanner: derive Segment work items
Pipeline -> ModelTaskRuntime: one selected SourceSegment
ModelTaskRuntime -> Application Layer: text response
Application Layer -> Ledger: ModelRun and pending records
```

## 6. Data Model

AnalysisUnit adds an optional `source_segment_label`.

The label participates in AnalysisUnit identity and persisted payload integrity.

ContextManifest records the selected SourceSegment label.

PHP-1.2 creates no new accepted Domain Core record type.

## 7. APIs / Interfaces

The model response keeps the PHP-1 claim line contract.

```text
claim: s1 | <organization subject> | <relation label> | <organization object>
```

## 8. Behavior & Domain Rules

The model receives no Ledger identity or source coordinate.

## 9. Acceptance Criteria

- AC-PHP12-01: ContextPlanner tests prove one Segment work item per SourceSegment.
- AC-PHP12-02: ContextPlanner tests prove each Segment ContextManifest contains only its selected SourceSegment.
- AC-PHP12-03: Application tests prove separate claims from one SourceSegment share one EvidenceTarget.
- AC-PHP12-04: Pipeline tests prove source-order Segment work items and the unchanged PHP-1.1 batch rule.
- AC-PHP12-05: Local packet replay records every Segment outcome for all 50 rows.

## 10. Constraints and Halt Conditions

PHP-1.2 keeps direct Organization relationship extraction.

PHP-1.2 does not change the PHP-1.1 eight-claim batch rule.

The program evaluates the eight-claim design after PHP-1 produces reviewed corpus evidence.

PHP-1.2 does not add ontology types, cross-segment evidence, retries, or output repair.
