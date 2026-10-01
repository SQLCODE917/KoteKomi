# TDD: Parser-Constituent Candidate Filter

- Status: Accepted
- Deliverable ID: `R7`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Selection Label and Capture](2026-09-30-selection-label-and-capture.md)
- Depends on: [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md)

## 1. Context & Problem

R6 renders one finite selection task per Event over the Event's syntax-attached candidates.

run-003 measured 1,152 Candidate labels across 53 Events.

The pools over-offer non-content candidates.

Function-word candidates form 16.1 percent of the labels.

Citation and number artifacts form 5.5 percent of the labels.

The Event's own trigger head forms 4.6 percent of the labels.

The Boundary gaps are zero, so coverage is not the problem.

The problem is precision: large pools drive over-selection.

Event AHE-008 offers 57 candidates and the model selects 47 of them.

Event AHE-033 rejects because the runner offered its own trigger head as a selectable candidate.

R7 adds five deterministic Candidate filters that shrink the pool before the selection task renders.

The filters never change the candidate inventory the Boundary-gap detector reads.

### Terms

**Candidate filter** means one deterministic removal rule applied in a fixed order.

**Selectable candidate** means one syntax-attached candidate that survives every Candidate filter.

**Selectable candidate list** means one Event's Selectable candidates in source order.

**Function-word part of speech** means one of ADP, AUX, CCONJ, DET, PART, and SCONJ.

**Artifact part of speech** means one of NUM, PUNCT, and SYM.

**Content token** means one dependency token whose part of speech is neither a Function-word nor an Artifact part of speech.

**Trailing punctuation** means one of the characters `.` `,` `;` `:` `!` `?`.

**Segment-core span** means the full source segment content span R6 adds for boundary coverage.

The terms Event trigger head, Syntax-attached candidate, Event frame, Boundary gap, and Residual review keep the meanings the Calibrated Residual Ownership TDD defines.

The terms Candidate label and Selection Score keep the meanings the Selection Label and Capture TDD defines.

### Primary flow

1. The runner re-derives the R3-A constituent pool and applies the R1 dependency-path router, unchanged.
2. The Application Layer derives one Selectable candidate list per Event by applying every Candidate filter in fixed order.
3. The runner renders one selection task per Event over the Selectable candidate list only.
4. The runner captures Token Probability Evidence and computes the Selection Score, unchanged.
5. The router sends uncertain selections to residual review, unchanged.
6. The Boundary-gap detector still reads the full inventory, so the filters never change Boundary Fidelity.

## 2. Goals

- Operators observe one selection task whose Candidate labels name only content-bearing, non-redundant, trigger-free candidates.
- Operators observe the Event's own trigger head never offered as a selectable candidate.
- Operators observe zero Boundary gaps after filtering.
- Operators observe the parser and the scorer still agree on every selection task.

## 3. Requirements

### Selectable candidate derivation

- R7-SEL-01: The Application Layer returns the syntax-attached candidates in source order minus every candidate a filter removes.
- R7-SEL-02: The derivation reads no Gold and invokes no model.
- R7-SEL-03: The derivation applies the filters in the fixed order trigger, core, function-word, artifact, dedup, nested.

### Filters

- R7-TRG-01: The trigger filter removes the candidate whose exact span equals the Event frame trigger span.
- R7-COR-01: The core filter removes the Segment-core span candidate.
- R7-FNC-01: The function-word filter removes a candidate whose every dependency token has a Function-word part of speech.
- R7-ART-01: The artifact filter removes a candidate whose every dependency token has an Artifact part of speech.
- R7-DED-01: The dedup filter strips leading and trailing whitespace and one or more Trailing punctuation characters from each candidate's displayed surface.
- R7-DED-02: The dedup filter drops a candidate whose stripped surface is empty.
- R7-DED-03: The dedup filter keeps one candidate per distinct stripped surface text; the earliest candidate by source offset survives.
- R7-NST-01: The nested filter removes a candidate when a surviving candidate strictly contains its token set and adds only Function-word or Artifact tokens.

### Rendering

- R7-RND-01: The renderer names one Candidate label per Selectable candidate in source order and no label for a removed candidate.
- R7-RND-02: The renderer sends no candidate boundary, unchanged from R6.

### Non-regression

- R7-INV-01: The Candidate filters never change the inventory the Boundary-gap detector reads.
- R7-INV-02: Every rendered candidate stays a syntax-attached candidate, unchanged from R6.
- R7-INV-03: An Event whose Selectable candidate list is empty goes to residual review and is not rendered as a zero-candidate task.

## 4. Proposed Architecture

```text
Runner
  -> Application Layer Candidate filters : syntax-attached -> Selectable candidate list
  -> render_event_frame_selection_task   : Candidate labels over the Selectable list only
  -> local model                         : one finite subset or NONE
  -> Selection Score + router            : accepted selection or residual review
  -> Boundary-gap detector               : full inventory, unchanged
```

The Candidate filters live in the Application Layer with the selection-task surface.

They sit between the R1 dependency-path router and the selection renderer.

They never touch the candidate inventory builder or the Boundary-gap detector.

## 5. Key Interactions

```text
Runner           -> Application Layer : attached candidates + tokens + trigger span
Application Layer -> filters          : trigger, core, function-word, artifact, dedup, nested
filters          -> Application Layer : Selectable candidate list
Runner           -> renderer          : Candidate labels over the Selectable list
renderer         -> local model       : one finite subset or NONE
local model      -> router            : Selection Score, threshold decision
```

## 6. Data Model

R7 creates no new stored record.

The Selectable candidate list reuses the Parser Constituent record, unchanged.

Each Candidate filter is a predicate over the Parser Constituent's token list, its exact span, and the dependency tokens' part-of-speech values.

The dedup filter's stripped surface is a display-only derivation; it never changes the Parser Constituent's exact span.

## 7. APIs / Interfaces

The Application Layer exposes one entry point for the Selectable candidate derivation.

It maps the syntax-attached candidate list, the dependency tokens, and the Event trigger head span to one ordered Selectable candidate list.

The selection renderer accepts the Selectable candidate list and renders Candidate labels over it.

No Adapter or Domain port changes in this deliverable.

## 8. Behavior & Domain Rules

A Candidate filter removes a candidate; it never rewrites a candidate span or text.

The trigger, core, function-word, and artifact filters commute; the dedup and nested filters run after them.

A candidate whose every token is a Function-word part of speech is never selectable.

A candidate whose every token is an Artifact part of speech is never selectable.

The nested filter keeps the containing candidate and removes the contained candidate only when the containing candidate adds non-content tokens.

An Event with no Selectable candidate is a residual-review Event, never an accepted selection.

## 9. Acceptance Criteria

- AC-R7-TRG-01: Tests prove the trigger filter removes the candidate equal to the Event frame trigger span.
- AC-R7-COR-01: Tests prove the core filter removes the Segment-core span candidate.
- AC-R7-FNC-01: Tests prove the function-word filter removes an ADP-, AUX-, CCONJ-, DET-, PART-, and SCONJ-only candidate.
- AC-R7-FNC-02: Tests prove the function-word filter keeps a candidate with at least one Content token.
- AC-R7-ART-01: Tests prove the artifact filter removes a NUM-, PUNCT-, and SYM-only candidate.
- AC-R7-ART-02: Tests prove the artifact filter keeps a mixed candidate with one Content token.
- AC-R7-DED-01: Tests prove the dedup filter strips leading and trailing whitespace and trailing punctuation.
- AC-R7-DED-02: Tests prove the dedup filter drops an empty-surface candidate.
- AC-R7-DED-03: Tests prove the dedup filter keeps the earliest candidate when two candidates share a stripped surface.
- AC-R7-NST-01: Tests prove the nested filter removes a strict-subset candidate whose superset adds only Function-word or Artifact tokens.
- AC-R7-NST-02: Tests prove the nested filter keeps a strict-subset candidate when the superset adds a Content token.
- AC-R7-SEL-01: Tests prove the Selectable list is a source-ordered subsequence of the syntax-attached candidates.
- AC-R7-SEL-02: Tests prove the derivation reads no Gold and invokes no model.
- AC-R7-RND-01: Tests prove the renderer names one label per Selectable candidate and no label for a removed candidate.
- AC-R7-INV-01: Tests prove the filters do not change the inventory the Boundary-gap detector reads.
- AC-R7-INV-02: Tests prove parser and scorer label-set parity holds on a filtered selection task.
- AC-R7-INV-03: Tests prove an empty Selectable list routes the Event to residual review and is not rendered.
- AC-R7-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Candidate inventory builder: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`build_constituent_candidate_inventory`).
- Dependency token model: `packages/application/src/kotekomi_application/event_entity_connections.py` (`EventEntityLinguisticToken`).
- Attachment and rendering surface: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py` (`attached_constituents`, `render_event_frame_selection_task`).
- Legacy renderer: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`render_constituent_selection_task`).
- Application tests: `packages/application/tests/test_parser_constituent_candidate_generation.py`, `packages/application/tests/test_calibrated_residual_ownership.py`.
- Runner: `scripts/run_calibrated_residual_ownership.py`.

## 11. Constraints and Halt Conditions

- Do not change the candidate inventory builder. The filters run on the syntax-attached candidates, never on the inventory the Boundary-gap detector reads.
- Keep the `C1..C<n>` Candidate labels and the finite answer parser unchanged.
- The nested filter keeps the containing candidate; do not invert that direction without a new TDD.
- Stop when a fresh run shows any nonzero Boundary gap after the filters.
- Stop when a rendered selection task still names a Function-word, Artifact, or trigger-head candidate.
- Stop when the parser and scorer label-set parity check reports any mismatch.