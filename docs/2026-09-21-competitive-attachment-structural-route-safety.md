# TDD: CEA-1.19 Structural Route Safety Sweep

- Status: Implemented; supported on frozen evidence; production inactive
- Deliverable ID: `CEA-1.19`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.18 Dependency-Head Residual Routing](2026-09-21-competitive-attachment-dependency-head-routing.md)

## 1. Context & Problem

CEA-1.18 tested dependency-head routing on seventeen Residual Ownership cases.

The Structural Route answered `Y` when one Candidate Root equaled the Event Anchor.

CEA-1.18 ran after deterministic Foreign Event exclusion.

Its sealed inventory contained no Structural Route Gold-negative case.

Independent review applied head alignment to all `935` frozen CEA-1 edges.

The original CEA-1 oracle labeled eight of `58` Head-Aligned edges `N`.

Five of those eight Candidates contain a complete Foreign Event.

The Residual Ownership task contract excludes those five Candidates.

Human review later changed the other three exact edges from `N` to `Y`.

Those three Candidates contain structural punctuation or a conjunction at a boundary.

The original oracle and the later human-reviewed Gold therefore disagree on three exact edges.

### Terms

**Original Gold** means one occurrence-level answer from a finalized CEA-1 `oracle.json` file.

**Reviewed Gold** means one answer from the accepted CEA-1.17 Gold catalog.

**Effective Gold** means Reviewed Gold for an exact reviewed edge and Original Gold otherwise.

**Foreign Event** means another Event option whose complete source range lies inside the Candidate.

**Eligible Edge** means one Head-Aligned edge whose Candidate contains no Foreign Event.

**Structural Decision** means the deterministic `Y` answer assigned to an Eligible Edge.

### Hypothesis

> Foreign Event exclusion followed by exact dependency-head alignment will retain every
> Effective Gold-positive Head-Aligned edge and route no Effective Gold-negative edge to `Y`.

### Primary flow

1. The runner validates both finalized CEA-1 packages and the complete CEA-1.17 report.
2. The Pipeline enumerates every Candidate and Event pair in both CEA-1 matrices.
3. The Application Layer derives complete Candidate Root evidence from pinned Stanza tokens.
4. The Pipeline applies Reviewed Gold by exact Candidate and Event identity.
5. The Pipeline excludes every Candidate that contains a complete Foreign Event.
6. The Pipeline evaluates every remaining Head-Aligned edge against Effective Gold.

CEA-1.19 creates experiment evidence only.

## 2. Goals

- An operator can reconcile the eight old-oracle negatives without hidden policy choices.
- An operator can inspect every Head-Aligned edge and every Foreign Event exclusion.
- An operator can distinguish a boundary-label correction from a routing recovery.
- An operator can see whether the composed Structural Route has one observed false positive.
- The experiment invokes no model and changes no canonical state.

## 3. Requirements

### Evidence authority

- CEA119-EVD-01: The runner must validate both finalized CEA-1 evidence packages.
- CEA119-EVD-02: The runner must validate the complete CEA-1.17 report.
- CEA119-EVD-03: The runner must evaluate all `935` Candidate and Event pairs.
- CEA119-EVD-04: The runner must bind every direct input by SHA-256.
- CEA119-EVD-05: The Pipeline must map Reviewed Gold by exact Candidate and Event identity.
- CEA119-EVD-06: Reviewed Gold must override Original Gold for the same exact edge.
- CEA119-EVD-07: The report must identify every Original Gold and Reviewed Gold conflict.

### Dependency evidence

- CEA119-DEP-01: The Application Layer must reuse each pinned Stanza trace.
- CEA119-DEP-02: Each Candidate token inventory must contain every named linguistic token.
- CEA119-DEP-03: Each Candidate Root inventory must be complete for its Candidate tokens.
- CEA119-DEP-04: The Application Layer must map each Event Anchor by exact source range.
- CEA119-DEP-05: A Head-Aligned edge must have one Candidate Root equal to the Event Anchor.
- CEA119-DEP-06: Incomplete or invalid deterministic evidence must stop report construction.

### Eligibility

- CEA119-ELG-01: The Pipeline must find Foreign Events by complete source-range containment.
- CEA119-ELG-02: A Head-Aligned edge with one Foreign Event must be ineligible.
- CEA119-ELG-03: A Head-Aligned edge without a Foreign Event must be eligible.
- CEA119-ELG-04: Boundary punctuation and conjunctions must not determine eligibility.
- CEA119-ELG-05: Every ineligible edge must retain its exact Foreign Event IDs.

### Evaluation

- CEA119-EVL-01: The evaluator must apply Effective Gold after eligibility decisions exist.
- CEA119-EVL-02: The evaluator must report development and validation separately.
- CEA119-EVL-03: The evaluator must report all pair, Head-Aligned, and eligible counts.
- CEA119-EVL-04: The evaluator must report Original Gold counts before overrides.
- CEA119-EVL-05: The evaluator must report Effective Gold counts after overrides.
- CEA119-EVL-06: The evaluator must report eligible true positives and false positives.
- CEA119-EVL-07: The evaluator must report excluded positive and negative counts.
- CEA119-EVL-08: `supported` requires zero eligible Effective Gold-negative edges.
- CEA119-EVL-09: `supported` requires zero excluded Effective Gold-positive edges.
- CEA119-EVL-10: `falsified` requires one eligible Effective Gold-negative edge.
- CEA119-EVL-11: `mixed` requires zero eligible negatives and one excluded positive.

### Evidence package

- CEA119-PKG-01: The JSON report must use typed Application Layer DTOs.
- CEA119-PKG-02: The review must show each Head-Aligned edge with exact source text.
- CEA119-PKG-03: The review must show Candidate, Event, roots, and Foreign Events.
- CEA119-PKG-04: The review must show Original Gold, Reviewed Gold, and Effective Gold.
- CEA119-PKG-05: The handoff must state the bounded claim and its coverage limit.
- CEA119-PKG-06: The report must record zero model executions and canonical writes.

## 4. Proposed Architecture

```text
CEA-1 matrices + Stanza traces + two Gold authorities
                         |
                         v
              complete root derivation
                         |
                         v
                 head alignment
                         |
                         v
             Foreign Event exclusion
                         |
                         v
              Effective Gold evaluator
```

The Application Layer owns complete token and root evidence.

The Pipeline owns Gold precedence, eligibility, evaluation, and review rendering.

The disposable runner validates inputs and writes the evidence package.

## 5. Key Interactions

```text
Operator        Runner        Application Layer        Pipeline
   |               |                  |                   |
   | run           |                  |                   |
   |-------------->| validate inputs  |                   |
   |               |----------------->| derive roots      |
   |               |<-----------------| exact evidence    |
   |               |------------------------------------->| apply Gold + eligibility
   |               |<-------------------------------------| typed report
   |<--------------| report paths     |                   |
```

## 6. Data Model

`AttachmentStructuralSafetyCase` records one Head-Aligned edge and its evaluation.

`AttachmentStructuralSafetyPhase` records one complete phase summary.

`AttachmentStructuralSafetyReport` records the complete model-free result.

These Application Layer DTOs remain derived experiment evidence.

## 7. APIs / Interfaces

The runner accepts the CEA-1.17 root and both finalized CEA-1 roots.

The runner writes `report.json`, `comparison-review.md`, `second-opinion-handoff.md`, and `status.json`.

The runner exits zero after it writes complete valid evidence.

## 8. Behavior & Domain Rules

- Exact SourceSegment characters remain authoritative.
- Stanza supplies dependency observations.
- The Pipeline applies the later human-reviewed answer for an exact edge conflict.
- Foreign Event exclusion remains a prerequisite for the Structural Decision.
- Boundary punctuation remains part of source evidence.
- CEA-1.19 does not activate production routing.

## 9. Acceptance Criteria

- CEA119-ACC-01: Tests reject an incomplete Candidate Root inventory.
- CEA119-ACC-02: Tests prove Reviewed Gold overrides one exact Original Gold answer.
- CEA119-ACC-03: Tests prove Foreign Event exclusion uses complete Event ranges.
- CEA119-ACC-04: Tests prove each terminal outcome.
- CEA119-ACC-05: The experiment evaluates `935` exact edges.
- CEA119-ACC-06: The experiment reproduces `58` Head-Aligned edges.
- CEA119-ACC-07: The experiment reports three Gold conflicts.
- CEA119-ACC-08: The experiment reports five Foreign Event exclusions.
- CEA119-ACC-09: Focused formatting, lint, typecheck, and tests pass.
- CEA119-ACC-10: The report records zero model executions and canonical writes.

## 10. Reference Implementations

- Root evidence: `competitive_attachment_dependency_head_routing.py`.
- Foreign Event exclusion: `competitive_attachment_residual_ownership.py`.
- Matrix validation: `run_competitive_attachment_edge_filter_experiment.py`.
- Dependency relations: [Universal Dependencies](https://universaldependencies.org/u/dep/).

## 11. Constraints and Halt Conditions

- Stop when one exact Candidate and Event pair lacks Gold.
- Stop when Reviewed Gold maps to more than one exact edge.
- Stop when one Candidate or Event range changes.
- Stop when Gold enters dependency analysis.
- Stop when one action invokes a model runtime.
- Stop when one action writes canonical intelligence.
- Keep validation evidence frozen after this TDD starts.

## 12. Experimental Outcome

CEA-1.19 completed on September 21, 2026.

The experiment evaluated all `935` frozen Candidate and Event pairs.

It reproduced `58` Head-Aligned edges.

The Original Gold contained `50` positive edges and eight negative edges.

Reviewed Gold superseded three exact Original Gold answers.

The Effective Gold therefore contained `53` positive edges and five negative edges.

All five Effective Gold-negative Candidates contained a complete Foreign Event.

Foreign Event exclusion removed those five Candidates from the Structural Route.

All `53` eligible edges had Effective Gold answer `Y`.

The composed policy produced zero eligible false positives.

The composed policy excluded zero Effective Gold-positive edges.

The report classified the registered hypothesis as `supported`.

The experiment invoked zero models.

The experiment created zero ProposedChanges and zero accepted Ledger changes.

This result validates the composition on the frozen source and Gold inventory.

This result does not test unseen syntax, parser errors, or an independent document.

Independent review reproduced every digest, count, and route decision.

Independent review found that the report contract fixed two failure counts to zero.

CEA-1.20 changed both fields to non-negative integers.

The repaired contract can represent `supported`, `mixed`, and `falsified` reports.

The five frozen inventory counts remain literal experiment invariants.

Inventory drift invalidates the evidence package instead of changing its semantic outcome.

Independent review also separated the `935`-edge sweep from the reached evidence.

The Structural Route reached `58` Head-Aligned edges and selected `53` edges.

Three selected edges depend on Reviewed Gold that differs from Original Gold.

Original Gold therefore scores the selected edges as `50` positive and three negative.

The CEA-1.17 reviewed catalog contains three negative controls.

Head alignment abstains on all three reviewed negative controls.

The frozen inventory contains no eligible partial Foreign Event overlap.

The accepted CEA-1.19 claim is therefore narrower than the registered hypothesis.

On one frozen document, the composed policy selected `53` edges.

The selected edges contained zero Effective Gold negatives.

The composed policy abstained on all three CEA-1.17 reviewed negative controls.

Three selected edges rely on a boundary-label convention that Original Gold scores as negative.

CEA-1.20 scans the complete `935`-edge inventory for exact source-range equality.

It finds forty exact pairs and `895` unequal-range pairs.

Production integration remains `not_activated`.
