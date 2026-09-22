# TDD: CEA-1.18 Dependency-Head Residual Routing

- Status: Implemented; supported on sealed evidence; production inactive
- Deliverable ID: `CEA-1.18`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.17 Residual Ownership Transfer
  Calibration](2026-09-21-competitive-attachment-residual-transfer-calibration.md)

## 1. Context & Problem

CEA-1.17 tested seventeen Residual Ownership cases.

The frozen threshold produced nine correct development decisions.

The frozen threshold produced five correct validation decisions.

The threshold changed zero validation decisions.

Candidate boundary shape separated the validation scores more strongly than Residual Ownership did.

The phrase `agreements with the Trump administration` scored about `8.90`.

The phrase `an agreement with the AI Safety Institute` scored about `-9.84`.

Both phrases use the Event noun as the syntactic head of the Candidate.

KoteKomi already stores one pinned Stanza dependency tree for each SourceSegment.

KoteKomi can identify the syntactic head without another model call.

### Terms

**Candidate Root** means one non-punctuation Candidate token.

Its dependency head leaves the Candidate.

**Event Anchor** means the Stanza token at the exact Target Event head range.

**Head-Aligned Residual** means a Residual Edge with one Candidate Root equal to its Event Anchor.

**Semantic Residual** means a Residual Edge that is not a Head-Aligned Residual.

**Structural Route** means a positive experimental decision for a Head-Aligned Residual.

**Semantic Route** means the frozen CEA-1.17 threshold decision for a Semantic Residual.

### Hypothesis

> Dependency-head routing will preserve nine of ten development decisions and recover all seven
> validation decisions without changing one Gold-negative decision.

### Primary flow

1. The runner validates the complete CEA-1.17 package and independent review.
2. The Application Layer maps each Candidate and Target Event to pinned Stanza tokens.
3. The Pipeline classifies each case as Head-Aligned Residual or Semantic Residual.
4. The Pipeline assigns the Structural Route or frozen Semantic Route.
5. The Pipeline compares every routed decision with Gold at the exact occurrence.
6. The runner writes one JSON report, one review, and one Claude handoff.

CEA-1.18 creates experimental evidence only.

## 2. Goals

- An operator can inspect every Candidate Root and Event Anchor.
- An operator can distinguish structural routing from Qwen semantic judgment.
- An operator can compare the routed result with the frozen CEA-1.17 result.
- An operator can see the missing Gold-negative Head-Aligned coverage.
- The diagnostic executes no model task and changes no canonical state.

## 3. Requirements

### Input evidence

- CEA118-EVD-01: The runner must validate the complete CEA-1.17 report.
- CEA118-EVD-02: The runner must require the completed CEA-1.17 Claude review.
- CEA118-EVD-03: The runner must reuse all ten development and seven validation cases.
- CEA118-EVD-04: The runner must validate both finalized CEA-1 source packages.
- CEA118-EVD-05: The runner must bind every direct input by SHA-256.
- CEA118-EVD-06: Gold must remain outside dependency analysis.

### Dependency analysis

- CEA118-DEP-01: The Application Layer must reuse each pinned Stanza trace.
- CEA118-DEP-02: The Application Layer must map the Event Anchor by exact source range.
- CEA118-DEP-03: The Application Layer must derive Candidate Roots from Candidate token IDs.
- CEA118-DEP-04: Dependency analysis must preserve exact token text and ranges.
- CEA118-DEP-05: A Head-Aligned Residual must have exactly one Candidate Root.
- CEA118-DEP-06: That Candidate Root must equal the Event Anchor token.
- CEA118-DEP-07: Zero or multiple Candidate Roots must produce a Semantic Residual.
- CEA118-DEP-08: The diagnostic must preserve every dependency gap.

### Routing

- CEA118-RTE-01: The Pipeline must assign the Structural Route to each Head-Aligned Residual.
- CEA118-RTE-02: The Structural Route must produce experimental answer `Y`.
- CEA118-RTE-03: The Pipeline must assign the Semantic Route to every other case.
- CEA118-RTE-04: The Semantic Route must preserve both frozen CEA-1.17 threshold answers.
- CEA118-RTE-05: The Pipeline must preserve each route origin with its answer.
- CEA118-RTE-06: The diagnostic must run after deterministic Foreign Event exclusion.

### Evaluation

- CEA118-EVL-01: The evaluator must apply Gold after every route decision exists.
- CEA118-EVL-02: The evaluator must score development and validation separately.
- CEA118-EVL-03: The evaluator must report baseline and routed accuracy.
- CEA118-EVL-04: The evaluator must report every recovery and regression.
- CEA118-EVL-05: The evaluator must report Head-Aligned Gold-positive and Gold-negative counts.
- CEA118-EVL-06: The evaluator must report Semantic Residual Gold counts.
- CEA118-EVL-07: The evaluator must report the projected Qwen call reduction.
- CEA118-EVL-08: `supported` requires nine correct development cases.
- CEA118-EVL-09: `supported` requires seven correct validation cases.
- CEA118-EVL-10: `supported` requires every Gold-negative case to remain `N`.
- CEA118-EVL-11: `mixed` requires a validation gain with one failed quality gate.
- CEA118-EVL-12: `falsified` requires one Structural Route false positive or no validation gain.
- CEA118-EVL-13: The runner must stop before report construction when dependency evidence is incomplete or invalid.

### Evidence package

- CEA118-PKG-01: The JSON report must use typed Application Layer DTOs.
- CEA118-PKG-02: The review must show exact source, Candidate, Event, and Gold answer.
- CEA118-PKG-03: The review must show Candidate Roots, Event Anchor, and dependency path.
- CEA118-PKG-04: The review must show the baseline answer, route, and routed answer.
- CEA118-PKG-05: The review and handoff must derive Head-Aligned Gold-negative coverage from the typed phase records.
- CEA118-PKG-06: The package must report zero model executions and canonical writes.

## 4. Proposed Architecture

```text
CEA-1.17 cases + pinned Stanza traces
                  |
                  v
      existing dependency analyzer
                  |
          +-------+-------+
          |               |
          v               v
    Head-Aligned       Semantic
    Structural Route   frozen Qwen route
          |               |
          +-------+-------+
                  v
       occurrence-level evaluator
```

The Application Layer owns exact token mapping and typed evidence.

The Pipeline owns routing, Gold evaluation, and review rendering.

The disposable runner validates inputs and writes the evidence package.

## 5. Key Interactions

```text
Operator        Runner        Application Layer        Pipeline
   |               |                  |                   |
   | run           |                  |                   |
   |-------------->| validate inputs  |                   |
   |               |----------------->| map exact heads   |
   |               |<-----------------| observations      |
   |               |------------------------------------->| route + evaluate
   |               |<-------------------------------------| typed report
   |<--------------| report paths     |                   |
```

## 6. Data Model

`AttachmentSyntaxObservation` remains the dependency evidence contract.

`AttachmentHeadRoutingCase` records one route and its occurrence-level evaluation.

`AttachmentHeadRoutingPhase` records one phase summary.

`AttachmentHeadRoutingReport` records the complete model-free result.

These records remain derived experiment evidence.

## 7. APIs / Interfaces

The runner accepts the CEA-1.17 root and both finalized CEA-1 roots.

The runner writes `report.json`, `review.md`, `second-opinion-handoff.md`, and `status.json`.

The runner exits zero after it writes complete valid evidence.

## 8. Behavior & Domain Rules

- Exact SourceSegment characters remain authoritative.
- Stanza supplies dependency observations but does not decide Gold correctness.
- KoteKomi creates every route decision and evaluation.
- The Structural Route remains bounded to the seventeen sealed Residual Edges.
- The review reports the observed Head-Aligned Gold-negative count as a coverage measure.
- CEA-1.18 does not activate production routing.

## 9. Acceptance Criteria

- CEA118-ACC-01: Tests prove exact Candidate Root and Event Anchor mapping.
- CEA118-ACC-02: Tests prove all route branches and terminal outcomes.
- CEA118-ACC-03: The diagnostic produces eleven Head-Aligned Residuals.
- CEA118-ACC-04: All eleven Head-Aligned Residuals have Gold answer `Y`.
- CEA118-ACC-05: The diagnostic produces six Semantic Residuals.
- CEA118-ACC-06: The Semantic Residuals contain three `Y` and three `N` Gold answers.
- CEA118-ACC-07: Routed accuracy is nine of ten in development.
- CEA118-ACC-08: Routed accuracy is seven of seven in validation.
- CEA118-ACC-09: Focused formatting, lint, typecheck, and tests pass.
- CEA118-ACC-10: The report records zero model executions and canonical writes.

## 10. Reference Implementations

- Dependency mapping: `competitive_attachment_review_verification.py`.
- Frozen decisions: `competitive_attachment_residual_transfer.py`.
- Runner evidence validation: `run_competitive_attachment_residual_transfer.py`.
- Dependency relations: [Universal Dependencies](https://universaldependencies.org/u/dep/).
- Stanza token heads:
  [Stanza dependency parsing](https://stanfordnlp.github.io/stanza/depparse.html).

## 11. Constraints and Halt Conditions

- Stop when one case lacks exact Stanza evidence.
- Stop when one Candidate or Event range changes.
- Stop when Gold enters dependency analysis.
- Stop when one Structural Route maps a Gold-negative case to `Y`.
- Stop when an action would invoke a model runtime.
- Stop when an action would write canonical intelligence.

## 12. Experimental Outcome

CEA-1.18 completed on September 21, 2026.

The report classified the registered hypothesis as `supported`.

Seven development cases and four validation cases used the Structural Route.

All eleven Head-Aligned Residuals had Gold answer `Y`.

Three development cases and three validation cases used the Semantic Route.

Those six cases contained three Gold-positive and three Gold-negative answers.

Development accuracy remained nine of ten in both repetitions.

Validation accuracy improved from five of seven to seven of seven in both repetitions.

The Structural Route recovered `hiring` and `agreement` without a regression.

The Semantic Route retained the one unresolved development miss for `held discussions`.

The diagnostic projected eleven fewer Qwen calls across the seventeen cases.

The projected call reduction was about `64.7%`.

The diagnostic executed zero model tasks.

The diagnostic created zero ProposedChanges and zero accepted Ledger changes.

The sealed CEA-1.17 evidence contains zero Head-Aligned Gold-negative cases.

Independent review then applied head alignment to all `935` edges in the frozen CEA-1 matrices.

That sweep found `58` Head-Aligned edges under the original CEA-1 oracle.

The original oracle labeled `50` of those edges `Y` and eight edges `N`.

Five of the eight `N` edges contain a complete Foreign Event.

The CEA-1.17 task contract already excludes those five edges before dependency-head routing.

The later human-reviewed CEA-1.17 Gold changed the other three exact edges from `N` to `Y`.

Those three Candidates start or end with structural punctuation or a conjunction.

The review's proposed punctuation veto would therefore preserve an older Gold artifact.

The independent review correctly found that the standalone head-alignment rule is unsafe.

CEA-1.18 did not test the standalone rule.

CEA118-RTE-06 places the rule after deterministic Foreign Event exclusion.

The review also found that the Markdown renderer printed a literal zero for negative coverage.

The implementation now derives that value from the typed phase records.

The implementation now binds every Candidate Root to the complete Candidate token inventory.

Invalid or incomplete deterministic dependency evidence now stops report construction.

CEA-1.19 will test the composed policy across all frozen edges with explicit Gold precedence.

Production integration remains blocked until that test and held-out counterexample coverage pass.
