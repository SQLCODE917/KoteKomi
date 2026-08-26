# TDD: Paragraph Hypothesis Provisional Eligibility Labels

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.4
- Depends on: PHP-1.3

## 1. Context & Problem

The 50-row packet contains direct relationships and intentional PHP-1 controls.

The current report counts every abstention alike.

An operator cannot tell whether a model missed an in-scope relation or correctly abstained from an out-of-scope paragraph.

PHP-1.4 gives each packet row one provisional eligibility label.

### Terms

**Provisional eligibility label** means an agent-authored, reviewable classification of one packet row for the current PHP-1 organization-to-organization task.

### Primary end-to-end flow

1. An agent reads one authoritative packet row.
2. The agent assigns one provisional eligibility label.
3. The packet parser exposes that label to the diagnostic.
4. The diagnostic reports outcomes grouped by label.
5. A reviewer can confirm or revise the label outside the runtime path.

## 2. Goals

- An operator can separate expected abstention from a direct extraction miss.
- The report retains the original case class and expected semantic work.
- The runtime remains independent from the packet annotations.

## 3. Requirements

### Evaluation packet

- PHP14-PACKET-01: Each of the 50 rows records one provisional eligibility label.
- PHP14-PACKET-02: The packet uses only `eligible`, `out_of_scope`, `needs_coreference`, `needs_multi_segment`, or `control`.
- PHP14-PACKET-03: Each row records one concise label reason.

### Packet diagnostic

- PHP14-DIAG-01: The parser rejects a row without a known label.
- PHP14-DIAG-02: The result preserves each row label and reason.
- PHP14-DIAG-03: The summary groups terminal outcomes by label.

## 4. Proposed Architecture

```text
Packet row
  -> provisional eligibility label
  -> packet parser
  -> local diagnostic
  -> outcome by label
```

The evaluation packet owns the provisional label.

The diagnostic owns parsing and aggregation.

## 5. Key Interactions

```text
Agent -> Evaluation packet: label one row
Packet parser -> Diagnostic: labeled case
Diagnostic -> Operator: grouped outcome report
```

## 6. Data Model

The packet and local JSON diagnostic add label and reason fields.

PHP-1.4 creates no Ledger records.

## 7. APIs / Interfaces

The packet parser exposes a non-empty label and reason in `Php1DiagnosticCase.metadata`.

## 8. Behavior & Domain Rules

The label does not select runtime behavior.

The label does not accept or reject a ProposedChange.

## 9. Acceptance Criteria

- AC-PHP14-01: Parser tests reject an unknown or missing label.
- AC-PHP14-02: Parser tests load exactly 50 uniquely labeled rows.
- AC-PHP14-03: Summary tests group outcomes by provisional label.
- AC-PHP14-04: The 50-row replay preserves each label and label reason.

## 10. Constraints and Halt Conditions

PHP-1.4 adds no ontology type or model prompt change.

The labels remain provisional until independent corpus review.
