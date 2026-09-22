# TDD: CEA-1.20 Exact Event Self-Attachment

## 1. Context & Problem

CEA-1.19 tested a Structural Route across `935` Candidate and Event pairs.

The Structural Route reached `58` Head-Aligned pairs.

Independent review found that CEA-1.20 initially searched only those `58` pairs.

Exact source-range equality does not depend on dependency-head alignment.

The complete `935`-edge inventory must therefore define the evidence boundary.

**Exact Self-Attachment** means a Candidate and Target Event have identical source ranges.

**Unequal-Range Edge** means a Candidate and Target Event have different source ranges.

**Original Gold** means the occurrence-level answer in the frozen CEA-1 oracle.

**Reviewed Negative Control** means one CEA-1.17 case with reviewed Gold answer `N`.

The Primary Flow is:

1. The runner validates the completed CEA-1.17 and CEA-1.19 packages.
2. The runner loads the complete frozen matrices, oracles, and source inputs.
3. The Pipeline scans every Candidate and Event pair for exact range equality.
4. The Pipeline evaluates Exact Self-Attachment against Original Gold.
5. The Pipeline confirms that the route abstains on every Reviewed Negative Control.
6. The runner writes a typed report, a review, and an independent-review handoff.

The experiment invokes no model.

The experiment creates no ProposedChange or accepted Ledger record.

The experiment does not activate production routing.

## 2. Goals

- An operator can see the complete denominator for exact self-attachment.
- An operator can see every Exact Self-Attachment decision with exact source text.
- An operator can see the Original Gold result without Reviewed Gold substitution.
- An operator can see whether every Reviewed Negative Control remains outside the route.
- A failed CEA-1.19 semantic policy can produce a typed terminal report.
- An independent reviewer can reproduce every reported count from pinned files.

## 3. Requirements

### CEA-1.19 measurement repair

- CEA120-MSR-01: The CEA-1.19 report accepts any non-negative eligible-negative count.
- CEA120-MSR-02: The CEA-1.19 report accepts any non-negative excluded-positive count.
- CEA120-MSR-03: The CEA-1.19 report derives its outcome from those observed counts.
- CEA120-MSR-04: A positive eligible-negative count produces `falsified`.
- CEA120-MSR-05: A zero eligible-negative count and positive excluded-positive count produce `mixed`.
- CEA120-MSR-06: Frozen inventory counts remain fail-fast experiment invariants.

### Evidence validation

- CEA120-EVD-01: The runner validates every CEA-1.17 and CEA-1.19 input digest.
- CEA120-EVD-02: The runner requires both completed independent reviews.
- CEA120-EVD-03: The Pipeline uses all `935` frozen Candidate and Event pairs.
- CEA120-EVD-04: The Pipeline uses Original Gold for Exact Self-Attachment evaluation.
- CEA120-EVD-05: The Pipeline identifies Reviewed Negative Controls from CEA-1.17 evidence.
- CEA120-EVD-06: Gold remains outside every route decision.
- CEA120-EVD-07: The Head-Aligned inventory remains a cross-check rather than a filter.

### Exact route

- CEA120-RTE-01: Exact range equality assigns `Y`.
- CEA120-RTE-02: Unequal ranges receive no answer.
- CEA120-RTE-03: The Pipeline preserves Candidate and Event occurrence identity.
- CEA120-RTE-04: The Pipeline reports every exact pair from the complete inventory.
- CEA120-RTE-05: The Pipeline reports the unequal-range remainder as a count.

### Evaluation

- CEA120-EVL-01: The evaluator reports complete-inventory counts by phase.
- CEA120-EVL-02: The evaluator reports Original Gold positives and negatives for exact pairs.
- CEA120-EVL-03: The evaluator reports Reviewed Gold conflicts for exact pairs.
- CEA120-EVL-04: The evaluator reports each Reviewed Negative Control and its route result.
- CEA120-EVL-05: `supported` requires zero Exact Self-Attachment Original Gold negatives.
- CEA120-EVL-06: `supported` requires every Reviewed Negative Control to remain unrouted.
- CEA120-EVL-07: `falsified` requires one Exact Self-Attachment Original Gold negative.
- CEA120-EVL-08: `mixed` requires zero Exact Self-Attachment negatives.
- CEA120-EVL-09: `mixed` requires one routed Reviewed Negative Control.

### Evidence package

- CEA120-PKG-01: The report records all input paths and SHA-256 digests.
- CEA120-PKG-02: The review shows exact source, Candidate, Event, and Original Gold.
- CEA120-PKG-03: The review reports the unequal-range remainder without classifying it.
- CEA120-PKG-04: The handoff derives every reported count from the typed report.
- CEA120-PKG-05: The handoff states that exact equality does not validate unequal ranges.
- CEA120-PKG-06: The handoff identifies the route as an oracle consistency check.
- CEA120-PKG-07: The package records zero model executions and zero canonical writes.

## 4. Proposed Architecture

```text
complete CEA-1 matrices + oracle + source inputs
                         |
                         v
              exact source-range test
                    +----+----+
                    |         |
                    v         v
              equal range   unequal range
                    |         |
                    v         v
                   `Y`     no decision
                    |
                    v
             Original Gold check
                    |
                    v
          occurrence-level typed report
```

The Application Layer owns route records and report validation.

The Pipeline owns evidence selection, exact-range testing, evaluation, and review rendering.

The disposable runner validates files and writes the evidence package.

## 5. Key Interactions

```text
Operator        Runner        Application Layer        Pipeline
   |               |                  |                   |
   | run           |                  |                   |
   |-------------->| validate files   |                   |
   |               |------------------------------------->| scan all edges
   |               |                  |<------------------| typed inputs
   |               |                  |------------------>| typed report
   |               |<-------------------------------------| review text
   |<--------------| paths and outcome|                   |
```

## 6. Data Model

`AttachmentExactSelfCase` records one equal-range Candidate and Event pair.

`AttachmentSelfRoutingPhase` records one complete phase denominator and its exact cases.

`AttachmentReviewedNegativeControl` records one CEA-1.17 reviewed negative.

`AttachmentSelfRoutingReport` records the complete model-free result.

These records remain derived experiment evidence.

## 7. APIs / Interfaces

The runner accepts one CEA-1.17 root and one CEA-1.19 root.

The runner obtains the frozen matrices, oracles, and source inputs through CEA-1.19 evidence references.

The runner writes `report.json`, `comparison-review.md`, and `second-opinion-handoff.md`.

The runner writes `status.json`.

The runner exits zero after it writes a complete typed result.

## 8. Behavior & Domain Rules

- Exact SourceSegment characters remain authoritative.
- Exact Self-Attachment uses source-range equality only.
- Original Gold evaluates Exact Self-Attachment.
- Reviewed Gold remains visible but cannot change that evaluation.
- The route assigns no answer to unequal-range edges.
- Frozen inventory drift invalidates the evidence package.
- Semantic failure remains a constructible typed outcome.
- The experiment invokes no model.
- The experiment leaves production integration `not_activated`.

## 9. Acceptance Criteria

- CEA120-ACC-01: Tests construct all three CEA-1.19 semantic outcomes.
- CEA120-ACC-02: Tests reject CEA-1.19 frozen inventory drift.
- CEA120-ACC-03: Tests prove exact equality over a complete matrix.
- CEA120-ACC-04: Tests prove unequal ranges remain unanswered.
- CEA120-ACC-05: Tests prove Original Gold remains the exact-route evaluator.
- CEA120-ACC-06: Tests prove one exact-route negative produces `falsified`.
- CEA120-ACC-07: Tests prove one routed Reviewed Negative Control prevents `supported`.
- CEA120-ACC-08: The experiment reports all `935` Candidate and Event pairs.
- CEA120-ACC-09: The experiment reports forty Exact Self-Attachment pairs.
- CEA120-ACC-10: The experiment reports zero Exact Self-Attachment Original Gold negatives.
- CEA120-ACC-11: The experiment reports `895` unequal-range edges.
- CEA120-ACC-12: The experiment reports three unrouted Reviewed Negative Controls.
- CEA120-ACC-13: The experiment records zero model executions and zero canonical writes.

## 10. Reference Implementations

- CEA-1.19 contracts: `competitive_attachment_structural_route_safety.py`.
- CEA-1.19 Pipeline: `competitive_attachment_structural_route_safety.py`.
- CEA-1.17 reviewed Gold: `competitive_attachment_residual_transfer.py`.
- Evidence runner: `run_competitive_attachment_exact_self_routing.py`.

## 11. Constraints and Halt Conditions

- Stop when one matrix lacks complete oracle coverage.
- Stop when one exact pair lacks authoritative source text.
- Stop when the complete inventory disagrees with the CEA-1.19 denominator.
- Stop when one experiment path invokes a model.
- Stop when one result creates a ProposedChange or accepted Ledger record.

## Experimental Outcome

CEA-1.20 completed on September 21, 2026.

The corrected experiment evaluated all `935` frozen Candidate and Event pairs.

Forty pairs had identical Candidate and Event ranges.

All forty Exact Self-Attachment pairs had Original Gold answer `Y`.

Twenty Exact Self-Attachment pairs occurred in each phase.

The remaining `895` edges had unequal ranges.

All forty exact pairs also appeared in the Head-Aligned subset.

The `18` remaining Head-Aligned pairs had unequal ranges.

All three Original Gold and Reviewed Gold conflicts occurred in that unequal-range subset.

The CEA-1.17 catalog supplied three reviewed negative controls.

The Exact Self-Attachment route selected none of those controls.

The report classified the registered hypothesis as `supported`.

The route retires only the easiest `40` of `935` edges.

The experiment invoked zero models.

The experiment created zero ProposedChanges and zero accepted Ledger changes.

Production integration remains `not_activated`.

The next experiment must evaluate the `18` Head-Aligned unequal-range pairs against blind review.
