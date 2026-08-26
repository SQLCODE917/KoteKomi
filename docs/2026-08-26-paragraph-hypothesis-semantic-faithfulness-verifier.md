# TDD: Paragraph Hypothesis Semantic Faithfulness Verifier

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.7
- Depends on: PHP-1.6

## 1. Context & Problem

PHP-1 validates that subject and object strings occur in the selected SourceSegment.

That check cannot determine whether the stated relation faithfully represents the source sentence.

PHP-1.7 adds a separate model task that judges each deterministically grounded Atomic hypothesis before KoteKomi creates pending ProposedChanges.

### Terms

**Faithfulness verdict** means one `accept` or `reject` decision about whether a proposed relation follows directly from one exact SourceSegment.

### Primary end-to-end flow

1. The extraction task returns a deterministically grounded Atomic hypothesis.
2. KoteKomi sends the exact SourceSegment and the hypothesis text to a verifier task.
3. The verifier returns one Faithfulness verdict.
4. KoteKomi archives and validates that verdict.
5. KoteKomi creates a pending ProposedChange only for an accepted verdict.

## 2. Goals

- A reviewer can inspect an independent semantic decision for every pending PHP-1 hypothesis.
- KoteKomi rejects unsupported relation wording before review.
- Raw extraction output and raw verifier output remain auditable.

## 3. Requirements

### Application Layer

- PHP17-VERIFY-01: The Application Layer runs the faithfulness verifier after deterministic grounding succeeds.
- PHP17-VERIFY-02: The verifier receives one exact SourceSegment and one hypothesis sentence.
- PHP17-VERIFY-03: The verifier returns exactly `accept` or `reject` and one non-empty reason.
- PHP17-VERIFY-04: The Application Layer archives verifier output before parsing it.
- PHP17-VERIFY-05: The Application Layer records a failed or malformed verifier task as a visible ModelRun outcome.
- PHP17-VERIFY-06: The Application Layer creates a pending ProposedChange only when the verifier accepts the hypothesis.

### Pipeline

- PHP17-PIPE-01: The Pipeline pins a verifier prompt and its digest.
- PHP17-PIPE-02: The Pipeline records the verifier ModelRun identity with the originating extraction ModelRun.

## 4. Proposed Architecture

```text
Atomic hypothesis
  -> deterministic grounding
  -> faithfulness verifier
  -> verified hypothesis
  -> pending ProposedChange
```

The Application Layer owns task ordering and publication gating.

The ModelTaskRuntime returns untrusted verifier text.

## 5. Key Interactions

```text
Application Layer -> ModelTaskRuntime: source sentence and hypothesis
ModelTaskRuntime -> Application Layer: verdict text
Application Layer -> Ledger: verifier ModelRun and eligible ProposedChanges
```

## 6. Data Model

The existing ModelRun records each verifier task.

The extraction ModelRun outcome records the accepted and rejected hypothesis counts.

PHP-1.7 creates no accepted Assertion.

## 7. APIs / Interfaces

The verifier response uses this text contract.

```text
verdict: accept
reason: exact direct relationship
```

## 8. Behavior & Domain Rules

The verifier cannot create record identifiers or accepted state.

KoteKomi treats a verifier failure as a rejected candidate.

## 9. Acceptance Criteria

- AC-PHP17-01: Application tests prove an accepted verdict creates a pending ProposedChange.
- AC-PHP17-02: Application tests prove a rejected verdict creates no pending ProposedChange.
- AC-PHP17-03: Application tests prove malformed verifier text creates no pending ProposedChange.
- AC-PHP17-04: Adapter and Pipeline tests prove raw verifier output persists and pins its prompt.
- AC-PHP17-05: The 50-row replay reports verifier verdicts for every deterministically grounded eligible hypothesis.

## 10. Constraints and Halt Conditions

PHP-1.7 does not accept Ledger state from any model output.

PHP-1.7 does not add a predicate vocabulary or ontology type.
