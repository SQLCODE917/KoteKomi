# TDD: Paragraph Hypothesis Eight-Claim Evaluation

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.6
- Depends on: PHP-1.5

## 1. Context & Problem

PHP-1 limits one response to eight claim lines.

The limit is an initial safety decision.

The current packet report cannot distinguish a limit effect from an ineligible row or malformed model output.

PHP-1.6 measures the limit without changing production acceptance behavior.

### Terms

**Limit effect** means the number of otherwise parseable claim lines after the first eight source-ordered claim lines.

### Primary end-to-end flow

1. The diagnostic archives one raw model response.
2. The evaluator reads that raw response without publishing candidates.
3. The evaluator counts claim lines in source order.
4. The report records a limit effect only for provisional eligible rows.
5. An operator compares the count with other failure categories.

## 2. Goals

- An operator can measure whether the current limit suppresses candidate coverage.
- Production PHP-1 validation remains unchanged.
- The report does not treat malformed output as an eligible ninth claim.

## 3. Requirements

### Diagnostic evaluator

- PHP16-EVAL-01: The evaluator reads retained raw model output only.
- PHP16-EVAL-02: The evaluator records `not_applicable` for rows without a provisional `eligible` label.
- PHP16-EVAL-03: The evaluator records `not_measurable` for malformed or abstained output.
- PHP16-EVAL-04: The evaluator counts claim lines after the eighth only when all lines have the PHP-1 claim shape.
- PHP16-EVAL-05: The evaluator creates no Ledger record.

## 4. Proposed Architecture

```text
Raw model output
  -> diagnostic evaluator
  -> limit-effect record
  -> packet summary
```

The diagnostic evaluator owns measurement.

The Application Layer retains the production limit.

## 5. Key Interactions

```text
Diagnostic -> evaluator: raw output and provisional label
Evaluator -> diagnostic: limit-effect record
Diagnostic -> operator: aggregate counts
```

## 6. Data Model

The local diagnostic result adds one limit-effect record per row.

## 7. APIs / Interfaces

The evaluator returns `not_applicable`, `not_measurable`, or `measured`.

## 8. Behavior & Domain Rules

The evaluator does not alter a ModelRun or ProposedChange.

## 9. Acceptance Criteria

- AC-PHP16-01: Tests distinguish an eligible nine-line response from malformed text.
- AC-PHP16-02: Tests prove labels outside `eligible` return `not_applicable`.
- AC-PHP16-03: The 50-row replay reports all limit-effect states.

## 10. Constraints and Halt Conditions

PHP-1.6 does not change the eight-claim limit.
