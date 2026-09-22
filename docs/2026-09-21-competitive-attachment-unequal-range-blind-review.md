# TDD: CEA-1.21 Unequal-Range Blind Review

- Status: Completed; mixed semantic outcome; response-format gate failed; production inactive
- Deliverable ID: `CEA-1.21`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)

## 1. Context & Problem

CEA-1.20 established Exact Self-Attachment across the complete `935`-edge inventory.

That route covers forty equal-range edges.

It leaves `895` unequal-range edges unresolved.

CEA-1.19 found eighteen unequal-range edges whose Candidate dependency root matches the Event head.

Its composed Structural Route selects thirteen edges and excludes five edges.

Existing labels cannot independently validate that policy.

Three selected edges depend on reviewed labels that differ from Original Gold.

The next experiment must collect semantic judgments without revealing either label source or route result.

**Blind Review Case** means one exact Candidate and Event pair rendered without Gold or route metadata.

**Structural Selection** means CEA-1.19 Head Alignment followed by complete Foreign Event exclusion.

**Unequal-Range Relation** identifies containment, reverse containment, partial overlap, or disjoint ranges.

The Primary Flow is:

1. The runner validates the completed CEA-1.19 and corrected CEA-1.20 packages.
2. The Pipeline selects all eighteen Head-Aligned unequal-range edges.
3. The Pipeline assigns opaque review case IDs.
4. The Pipeline writes a blind request without Gold or Structural Selection metadata.
5. A reviewer answers `Y`, `N`, or `U` for every case.
6. The runner validates the complete response without repair.
7. The Pipeline reveals the sealed policy and evaluates it against the blind judgments.
8. The runner writes a typed report and a second-opinion handoff.

The experiment invokes no Qwen task.

The experiment creates no ProposedChange or accepted Ledger record.

The experiment does not activate production routing.

## 2. Hypothesis

> Complete Foreign Event exclusion makes dependency-head routing safe for the eighteen Head-Aligned unequal-range edges.

`supported` requires every selected edge to receive blind answer `Y`.

`supported` also requires every excluded edge to receive blind answer `N`.

## 3. Goals

- A reviewer can judge every edge without seeing the existing labels.
- An operator can compare Structural Selection against one complete blind review.
- An operator can inspect every source, Candidate, Event, judgment, and policy result.
- An operator can distinguish safety failures from conservative exclusions.
- An operator can see results by exact range relation.

## 4. Requirements

### Evidence preparation

- CEA121-EVD-01: The runner validates every predecessor digest and fingerprint.
- CEA121-EVD-02: The Pipeline selects exactly the Head-Aligned unequal-range inventory.
- CEA121-EVD-03: The Pipeline preserves exact source characters and occurrence IDs.
- CEA121-EVD-04: The Pipeline assigns one stable opaque ID to each review case.
- CEA121-EVD-05: The catalog records Original, Reviewed, and Effective Gold for later comparison.
- CEA121-EVD-06: The blind request omits all Gold and route metadata.

### Blind review

- CEA121-REV-01: The request defines Event and Candidate before using those terms.
- CEA121-REV-02: The request asks one bounded attachment question.
- CEA121-REV-03: `Y` means the complete Candidate belongs to the Event proposition.
- CEA121-REV-04: `N` means some substantive Candidate content belongs elsewhere.
- CEA121-REV-05: `U` means the passage does not decide the attachment.
- CEA121-REV-06: The response supplies one answer and rationale for every opaque case ID.
- CEA121-REV-07: Invalid, missing, duplicate, or foreign decisions fail without repair.

### Evaluation

- CEA121-EVL-01: The evaluator reveals Structural Selection only after response validation.
- CEA121-EVL-02: The evaluator reports selected `Y`, `N`, and `U` counts.
- CEA121-EVL-03: The evaluator reports excluded `Y`, `N`, and `U` counts.
- CEA121-EVL-04: The evaluator reports agreement with Original, Reviewed, and Effective Gold.
- CEA121-EVL-05: The evaluator reports results by Unequal-Range Relation.
- CEA121-EVL-06: One selected `N` produces `falsified`.
- CEA121-EVL-07: One `U` produces `inconclusive` when no selected `N` exists.
- CEA121-EVL-08: One excluded `Y` produces `mixed` when no selected `N` or `U` exists.
- CEA121-EVL-09: Only selected `Y` and excluded `N` produce `supported`.

### Evidence package

- CEA121-PKG-01: The prepared package records catalog and request digests.
- CEA121-PKG-02: The final package records the exact reviewer response digest.
- CEA121-PKG-03: The readable comparison includes exact data in and data out.
- CEA121-PKG-04: The handoff states that one document and one reviewer cannot establish transfer.
- CEA121-PKG-05: The package records zero Qwen executions and zero canonical writes.

## 5. Architecture

```text
CEA-1.19 Head-Aligned cases
             |
             v
      unequal-range filter
             |
             v
   sealed evaluation catalog --------+
             |                        |
             v                        |
     blind review request             |
             |                        |
             v                        |
    complete Y/N/U response           |
             |                        |
             +------------------------+
                         |
                         v
              policy comparison report
```

The Application Layer owns catalog, response, and report contracts.

The Pipeline owns case derivation, blind rendering, and evaluation.

The disposable runner writes and validates the evidence package.

## 6. Data Model

`AttachmentUnequalRangeRelation` records the exact interval relation.

`AttachmentBlindReviewCase` records one sealed evaluation case.

`AttachmentBlindReviewCatalog` records the complete eighteen-case inventory.

`AttachmentBlindReviewDecision` records one reviewer answer and rationale.

`AttachmentBlindReviewSubmission` records one complete response.

`AttachmentBlindReviewEvaluation` records one revealed policy comparison.

`AttachmentBlindReviewReport` records the terminal result.

These records remain derived experiment evidence.

## 7. Interfaces

The `prepare` command accepts CEA-1.19 and CEA-1.20 roots.

The `prepare` command writes `catalog.json` and `blind-review-request.md`.

The reviewer writes `blind-review-response.json` through standard output.

The `evaluate` command accepts the prepared root and reviewer response.

The `evaluate` command writes `report.json`, `comparison-review.md`, and `second-opinion-handoff.md`.

## 8. Acceptance Criteria

- CEA121-ACC-01: Tests prove all four Unequal-Range Relations.
- CEA121-ACC-02: Tests prove blind rendering excludes Gold and policy fields.
- CEA121-ACC-03: Tests reject incomplete and duplicate responses.
- CEA121-ACC-04: Tests prove all four terminal outcomes.
- CEA121-ACC-05: Preparation reports exactly eighteen cases.
- CEA121-ACC-06: Preparation reports sixteen Candidate-contains-Event cases.
- CEA121-ACC-07: Preparation reports one Event-contains-Candidate case.
- CEA121-ACC-08: Preparation reports one partial-overlap case.
- CEA121-ACC-09: Evaluation reports zero model executions and zero canonical writes.

## 9. Constraints

- The blind request must not contain Gold labels.
- The blind request must not contain Structural Selection results.
- The reviewer command must disable Claude tools.
- The evaluator must not repair reviewer output.
- The result cannot activate production.
- The result cannot establish transfer beyond the frozen document.

## 12. Experimental Outcome

CEA-1.21 completed on September 21, 2026.

The blind request contained eighteen Head-Aligned unequal-range cases.

The request exposed no Gold or Structural Selection field.

The reviewer answered `Y` for all thirteen selected cases.

The reviewer answered `Y` for four of five excluded cases.

The reviewer answered `N` for the remaining excluded case.

The evaluator classified the registered semantic hypothesis as `mixed`.

The result confirms the positive Head-Aligned route on this inventory.

The result rejects complete Foreign Event exclusion as a semantic rule.

The four disputed Candidates contain a nested Event that serves as target Event content.

The accepted negative Candidate crosses from one Event into sibling Event content.

The reviewer returned one complete JSON object inside a Markdown code fence.

The operator preserved the raw response and removed only the fence.

The normalized JSON object matched the raw response body byte for byte.

The evaluator did not repair the response.

The manual normalization failed CEA121-REV-07 and the matching constraint.

The semantic judgments remain experiment evidence rather than production authority.

One Claude Opus review reproduced every count and agreed with all eighteen judgments.

Both semantic passes used the same model family.

The result cannot establish independent human agreement or cross-document transfer.

Production integration remains `not_activated`.
