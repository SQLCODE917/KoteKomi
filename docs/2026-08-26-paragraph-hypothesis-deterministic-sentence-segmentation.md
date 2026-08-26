# TDD: Paragraph Hypothesis Deterministic Sentence Segmentation

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.3
- Depends on: [PHP-1.2 Segment-Local Hypothesis Extraction](2026-08-26-segment-local-hypothesis-extraction.md)

## 1. Context & Problem

PHP-1.2 treats punctuation followed by whitespace as a sentence boundary.

That rule splits authoritative prose at initials such as `U.S.`.

The split removes relationship context before the model reads the SourceSegment.

PHP-1.3 derives complete sentences with a versioned deterministic policy.

### Terms

**Sentence span** means a contiguous range that a sentence segmenter identifies inside one Paragraph.

### Primary end-to-end flow

1. ContextPlanner reads one authoritative Paragraph.
2. ContextPlanner derives ordered sentence spans with `paragraph_segment_v2`.
3. ContextPlanner creates one Segment work item for each sentence span.
4. The Pipeline renders one exact sentence span for one model task.
5. The Application Layer verifies returned source mentions against that sentence span.

## 2. Goals

- A SourceSegment preserves abbreviations and citations inside its original sentence.
- SourceSegments remain exact and reconstruct the authoritative Paragraph.
- A stored work item identifies the segmentation policy that created it.

## 3. Requirements

### ContextPlanner

- PHP13-SEG-01: ContextPlanner defines `paragraph_segment_v2`.
- PHP13-SEG-02: ContextPlanner derives its spans with PySBD English sentence boundaries.
- PHP13-SEG-03: ContextPlanner preserves every source character, including whitespace.
- PHP13-SEG-04: ContextPlanner assigns labels in source order.
- PHP13-SEG-05: ContextPlanner uses `paragraph_segment_v2` for `segment_local_hypothesis_v1` work items.

### Application Layer

- PHP13-VERIFY-01: The Application Layer accepts both stored PHP-1 segment policies.
- PHP13-VERIFY-02: The Application Layer validates each claim against the policy pinned by its ContextManifest.

## 4. Proposed Architecture

```text
Paragraph
  -> paragraph_segment_v2
  -> SourceSegment
  -> Segment work item
  -> ContextManifest
  -> ModelRun
```

ContextPlanner owns segmentation and work-item identity.

The Application Layer owns source-grounding validation.

## 5. Key Interactions

```text
Pipeline -> ContextPlanner: plan paragraph work
ContextPlanner -> Pipeline: exact sentence work item
Pipeline -> ModelTaskRuntime: one sentence span
ModelTaskRuntime -> Application Layer: hypothesis text
```

## 6. Data Model

ContextManifest records `paragraph_segment_v2` when it renders a PHP-1.3 work item.

PHP-1.3 creates no new Domain Core record type.

## 7. APIs / Interfaces

`paragraph_source_segments` accepts a versioned segment policy identifier.

## 8. Behavior & Domain Rules

KoteKomi retains `paragraph_segment_v1` only to verify already persisted work.

New segment-local work uses `paragraph_segment_v2`.

## 9. Acceptance Criteria

- AC-PHP13-01: A ContextPlanner test proves `U.S.` stays inside one sentence span.
- AC-PHP13-02: A ContextPlanner test proves sentence spans concatenate to their input Paragraph.
- AC-PHP13-03: A planning test proves new segment-local work uses `paragraph_segment_v2`.
- AC-PHP13-04: Application and Pipeline tests prove v2 manifests validate and ground claims.
- AC-PHP13-05: The 50-row packet diagnostic records all rows with v2 spans.

## 10. Reference Implementations

- Segment and manifest logic: `packages/application/src/kotekomi_application/context_planning.py`.
- Hypothesis validation: `packages/application/src/kotekomi_application/staged_model_extraction.py`.

## 11. Constraints and Halt Conditions

PHP-1.3 does not alter the eight-claim rule.

PHP-1.3 does not repair model output.
