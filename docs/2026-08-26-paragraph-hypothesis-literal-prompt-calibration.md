# TDD: Paragraph Hypothesis Literal Prompt Calibration

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.5
- Depends on: PHP-1.4

## 1. Context & Problem

PHP-1.3 rejects malformed line shapes and ungrounded source mentions.

Those checks protect the Ledger.

Several local-model results fail because the prompt does not demonstrate the literal output contract sufficiently.

PHP-1.5 pins a new prompt that teaches the exact response shape without adding output repair.

### Terms

**Literal example** means a prompt example whose claim fields are copied exactly from its displayed SourceSegment.

### Primary end-to-end flow

1. The Pipeline renders one exact sentence span.
2. The Pipeline adds the pinned calibration prompt.
3. The model returns a claim line or abstention.
4. The Application Layer applies the unchanged literal validator.
5. The diagnostic retains raw output and terminal status.

## 2. Goals

- A model receives positive and negative examples of eligible relationships.
- A model receives one literal-copy example.
- The validator remains the final boundary.

## 3. Requirements

### Pipeline prompt

- PHP15-PROMPT-01: The Pipeline pins `paragraph_hypothesis_segment_v2`.
- PHP15-PROMPT-02: The prompt includes one literal eligible claim example.
- PHP15-PROMPT-03: The prompt includes one abstention example for a non-relationship sentence.
- PHP15-PROMPT-04: The prompt requires named organization mentions copied from the selected source span.
- PHP15-PROMPT-05: The prompt requires one literal source-segment label.

### Application Layer

- PHP15-VERIFY-01: The Application Layer keeps `paragraph_hypothesis_text_v1` unchanged.
- PHP15-VERIFY-02: The Application Layer archives every raw response before validation.

## 4. Proposed Architecture

```text
Pinned prompt
  -> exact SourceSegment
  -> model text
  -> unchanged validator
  -> ModelRun and pending ProposedChanges
```

The Pipeline owns prompt selection.

The Application Layer owns validation and pending record creation.

## 5. Key Interactions

```text
Pipeline -> ModelTaskRuntime: calibrated prompt and source text
ModelTaskRuntime -> Application Layer: raw text
Application Layer -> Ledger: terminal ModelRun
```

## 6. Data Model

ContextManifest and ModelRun pin the v2 prompt identifier and digest.

## 7. APIs / Interfaces

The model response remains the PHP-1 text contract.

## 8. Behavior & Domain Rules

KoteKomi does not repair a near-match output.

KoteKomi records every failed output as an invalid ModelRun.

## 9. Acceptance Criteria

- AC-PHP15-01: Pipeline tests prove the v2 prompt and digest are pinned.
- AC-PHP15-02: Application tests prove existing malformed-output rejection remains unchanged.
- AC-PHP15-03: The 50-row replay records literal-output failure counts for eligible rows.

## 10. Constraints and Halt Conditions

PHP-1.5 does not change the ontology or the eight-claim rule.
