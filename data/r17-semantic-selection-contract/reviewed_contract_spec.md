# TDD: Semantic Selection Contract

- Status: Proposed
- Deliverable ID: `R17`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Corrective Re-Selection Execution](2026-10-06-corrective-reselection-execution.md)
- Depends on: [Decontextualization Composition](2026-09-28-decontextualization-composition.md), [Parser-Constituent Sub-Span Candidate Generation](2026-09-25-parser-constituent-sub-span-candidate-generation.md), [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md), [Selection-Failure Slot Routing](2026-10-01-selection-failure-slot-routing.md), [Residual Composition-Hold Routing](2026-10-01-residual-composition-hold-routing.md)

## 1. Context & Problem

R15 prepared one corrective re-selection task per residual Event.
R16 executed both tasks and produced grammatically valid answers.
R16 did not establish useful semantic selection and closed neither residual.
The original selection instruction and the R15 corrective instruction both specify answer format only.
The original instruction reads `Return a comma-separated subset of the Candidate labels, or NONE.`
The R15 `label_only` instruction demands only candidate labels.
The R15 `best_choice` instruction demands one candidate label or one exact `NONE`.
No deliverable defines which relationship to the marked Event makes a Candidate eligible.
The Selection Score measures emitted-answer likelihood, and grammar checks answer format; neither establishes semantic correctness.
Exact-set agreement measures agreement with existing references, whose semantic and boundary policies must therefore be explicit before it means anything.
`AHE-022` held on `subject_unavailable`, which reflects missing entity-resolution inputs and does not measure selection quality.
`AHE-051` returned `NONE` for `[45] The April order is not final.` Its Candidate pool contains no separate `not` constituent, while R4 derives polarity from selected fragments.
R17 therefore writes the semantic-selection policy down, as a versioned, human-reviewed record the implementation validates.
An operator can request agent-authored drafts for human review; drafts are not acceptance evidence.
R17 pins the four decisions — eligibility, the complete selected set, `NONE` justification, and independent acceptance signals — and the review-and-freeze procedure that binds each expected selected set to its source, pool, and policy.
R17 keeps model discrimination and ranking experiments out of scope until the contract freezes.

### Terms

**Semantic selection** means whether the observed selected set is correct and complete for every required role the Candidate pool can represent, measured by the eligibility and the complete-selected-set rules. A required role the pool cannot represent is out of scope for semantic selection and is reported only by boundary coverage.
**Semantic policy** means the human-authored, human-reviewed record that states the eligibility rule, the complete-selected-set rules, the `NONE` rule, and the signal rules this contract validates.
**Eligible candidate** means one Candidate that supplies content one role in the proposition centered on the marked Event requires.
**Candidate availability** means one Candidate the syntax attachment places in a task pool.
**Representable role** means a required role whose content has at least one Candidate in the Candidate pool.
**Boundary-coverage gap** means a required role with no Candidate whose span covers the role's expected source range.
**Selected constituent set** keeps the R3 and R4 meaning.
**NONE** means the answer token that names no eligible Candidate.
**Answer grammar** means whether a response conforms to the strict response grammar of its route, as R16 defines it — not whether the permissive R3 parser can recover a selection from it.
**Route** keeps the R16 `ResidualClosureRoute` meaning: `label_only_reselection` or `best_choice_reselection`; the route selects which strict grammar judges an observed answer.
**Acceptance signal** means one independently testable observation this contract defines.
**Reference policy record** means one frozen Event, one frozen Candidate pool, and one human-reviewed expected selected set with an eligibility explanation and review evidence.
**Observed answer** means one frozen parsed selection answer — the candidate labels a source emitted — kept distinct from the reference policy record.
**Expected source range** means one source span a role requires, recorded independently of the Candidate pool so a missing candidate is detected.
**Policy author** and **Policy reviewer** name the human roles that write and approve each reference policy record; neither is the coding agent.
**Semantic selection contract** means the versioned record that pins the four decisions and the five signals.
**Composition readiness** means whether the reference selected set carries the entity references and the polarity, modality, and attribution inputs construction needs; it evaluates the reference selected set, independent of the observed answer.
**Document artifact** means a non-propositional marker the Source embeds, such as a section label or a citation marker.
**Held-out partition** keeps the R1 meaning.
The terms Candidate, Candidate label, Candidate pool, Constituent Selection Task, and Event frame keep the meanings the Parser-Constituent Sub-Span Candidate Generation and Calibrated Residual Ownership TDDs define.

### Primary flow

1. The policy author writes each reference policy record; the policy reviewer approves it; the reviewer's evidence and content digests are recorded.
2. The operator freezes the versioned semantic selection contract, binding the version number and content digests to the policy records, the renderer, the scoring rules, and the thresholds.
3. The Application Layer renders each Constituent Selection Task from the contract eligibility rule, the frozen Event frame, and the frozen Candidate pool.
4. The Application Layer loads each observed answer separately from its reference policy record.
5. The Application Layer applies the five independent acceptance signals to each (reference policy record, observed answer) pair.
6. The Application Layer seals one report with the contract version, the policy records, the observed answers, and the signal results, with zero model executions and zero canonical writes.

## 2. Goals

- Operators observe one versioned, digest-bound semantic selection contract whose policy is human-authored and human-reviewed.
- Operators observe one task rendering that names the eligibility rule in the instruction.
- Operators observe one deterministic reference policy-record set, each with a human-reviewed expected selected set and review evidence.
- Operators observe five independent acceptance signals with legal values and explicit not-applicable conditions, never one merged selection score.
- Operators observe zero model executions, zero canonical writes, and zero ProposedChanges.

## 3. Requirements

### Contract versioning and freezing

- R17-VER-01: The semantic selection contract carries one monotonic version number.
- R17-VER-02: A change to any of the four decisions below increments the version.
- R17-VER-03: The contract binds its version to the content digests of the policy records, the renderer, the scoring rules, and the thresholds, so a record whose content changes without a version bump is detected.
- R17-VER-04: Each frozen policy record is bound by its source digest, its Candidate-pool digest, and its policy-body digest, not by version number alone.

### Decision 1: Eligibility

- R17-ELG-01: A Candidate is eligible when it is one source-exact constituent that supplies content one role requires.
- R17-ELG-02: Eligibility is role-anchored: a role is eligible only when the Event's proposition requires that role's content.
- R17-ELG-03: The selectable roles are a closed set — subject, object, time, place, polarity, and modality — each defined against the trigger head's dependents (R4-ROL-01/02, R4-POL-01, R4-MOD-01).
- R17-ELG-04: The reporting carrier is not a selectable role and never belongs in the selected set. Attribution enters composition through the deterministic R4 split (`split_trigger_scope`, R4-ATR-01), as a separate input independent of the selection answer.
- R17-ELG-05: Syntax attachment establishes candidate availability, never semantic eligibility.
- R17-ELG-06: Eligibility does not depend on whether an Actor or Organization entity reference has been resolved.
- R17-ELG-07: Polarity and modality stay selectable roles consistent with R4 deriving them from selected fragments; when a pool cannot represent a required marker, the boundary-coverage signal records the gap and names a required follow-up change.
- R17-ELG-08: Each selectable role carries one worked example in the policy record.

### Decision 2: Complete selected set

- R17-SET-01: The selected set contains exactly one eligible Candidate per required role the Candidate pool can represent, except that one role may require multiple Candidates for coordination. A required role with no representable content is reported by boundary coverage, not by this rule.
- R17-SET-02: When two or more overlapping Candidates supply one role's content, the canonical selection boundary is the narrowest source-exact span containing the role's argument head and all content the role requires, and no content a different role requires.
- R17-SET-03: Redundancy is relative to the canonical selection boundary (R17-SET-02): a Candidate is redundant when it adds no required content beyond the canonical selection — it names no distinct required role and narrows no content the role still requires. Selecting a redundant Candidate next to the canonical Candidate is rejected. A Candidate that is itself the canonical boundary is not redundant merely because a larger Candidate contains it.
- R17-SET-04: The selected set preserves separate source occurrences even when their text matches.
- R17-SET-05: A select-all answer fails when the pool contains ineligible or redundant Candidates, and passes only when the pool contains exactly the required constituents and nothing else.

### Decision 3: NONE justification

- R17-NONE-01: A justified NONE means the task is complete and valid and no eligible Candidate exists.
- R17-NONE-02: Justified NONE differs from a missing Candidate boundary (a boundary-coverage gap).
- R17-NONE-03: Justified NONE differs from an unresolved trigger.
- R17-NONE-04: Justified NONE differs from malformed output.
- R17-NONE-05: Justified NONE differs from unsupported input.
- R17-NONE-06: An observed NONE is an abstention; the abstention-correctness signal judges it against the expected eligible set and never assumes justification.
- R17-NONE-07: The policy record states the full treatment of the negated adjectival predicate `not final` in `AHE-051` (see R17-DEC-051).

### Decision 4: Independent acceptance signals

- R17-SIG-01: Answer grammar — `valid` or `invalid` — establishes that the response conforms to the strict response grammar of its route, reusing the R16 strict parsers (`parse_label_only_reselection_answer` for `label_only_reselection`, `parse_best_choice_reselection_answer` for `best_choice_reselection`) rather than the permissive R3 parser. Strictly invalid forms include lower-case or foreign labels, duplicate labels, empty comma elements, a `NONE` mixed with a label, Markdown fences, explanations, internal newlines, and any other non-grammar character. Under `label_only_reselection` only Candidate labels are accepted and `NONE` rejects; under `best_choice_reselection` exactly one Candidate label or the exact token `NONE` is accepted.
- R17-SIG-02: Semantic selection — `met`, `unmet`, or `not_applicable` — establishes that the observed selected set is correct and complete for every required role the Candidate pool can represent. `not_applicable` only when the strict-parse result is `rejected` (strictly malformed, even if the permissive parser could recover a selection).
- R17-SIG-03: Boundary coverage — `met` or `gap` — compares each expected source range against the Candidate pool; `met` when a Candidate's span covers (contains) the expected range, `gap` when no Candidate covers it. It is bound to the source and pool, not to the observed answer, so it stays measurable after malformed output. A policy record with no expected source ranges is `met`.
- R17-SIG-04: Abstention correctness — `justified`, `unjustified`, or `not_applicable` — judges an observed NONE against the expected eligible set. `not_applicable` for any answer that is not NONE.
- R17-SIG-05: Composition readiness — `ready`, `not_ready`, or `not_applicable` — evaluates the reference selected set (not the observed answer) against the frozen composition inputs: whether the human-reviewed selected content carries the entity references and the polarity, modality, and attribution inputs construction needs. `not_applicable` when the reference set or composition inputs are absent.
- R17-SIG-06: The applicability matrix fixes each signal's legal values and its `not_applicable` condition. Malformed output makes answer grammar `invalid`; it never suppresses boundary coverage (bound to source and pool) nor composition readiness (bound to the reference selected set).

| Signal | Legal values | `not_applicable` when |
| --- | --- | --- |
| Answer grammar | `valid`, `invalid` | never — always computed |
| Semantic selection | `met`, `unmet`, `not_applicable` | the strict-parse result is `rejected` (strictly malformed output) |
| Boundary coverage | `met`, `gap` | never — source- and pool-bound |
| Abstention correctness | `justified`, `unjustified`, `not_applicable` | the answer is not `NONE` |
| Composition readiness | `ready`, `not_ready`, `not_applicable` | the reference selected set or composition inputs are absent |

### Pinned policy: `AHE-051` `not final`

- R17-DEC-051-01: The frame is supported and valid: the trigger is `final`, the passage is a well-formed source sentence, and the proposition is "The April order is not final."
- R17-DEC-051-02: The eligible constituent set is the subject role `The April order` (C3). The citation artifacts `[45]` (C1) and `45` (C2) are document artifacts, not eligible content, and `order` (C4) is redundant relative to the canonical subject boundary because it adds no required content beyond C3.
- R17-DEC-051-03: Polarity is `negated`, but the required `not` occurrence is not representable in the Candidate pool; the boundary-coverage signal therefore records a gap for the polarity role.
- R17-DEC-051-04: Correct selection alone does not make `AHE-051` composition-ready: composition readiness stays `not_ready` until the polarity gap is closed by a required follow-up change.
- R17-DEC-051-05: The observed `NONE` is an unjustified abstention because the expected eligible set is non-empty.
- R17-DEC-051-06: The required follow-up change is recorded — either expand the pool to include the `not` constituent or source polarity deterministically from the dependency tree — and routed out of this deliverable.
- R17-DEC-051-07: The five signals for the observed `NONE` answer are: answer grammar `valid`, semantic selection `unmet`, boundary coverage `gap`, abstention correctness `unjustified`, composition readiness `not_ready`.
- R17-DEC-051-08: The five signals for a constructed answer selecting `C3` are: answer grammar `valid`, semantic selection `met`, boundary coverage `gap`, abstention correctness `not_applicable`, composition readiness `not_ready`. Correct selection leaves the case `not_ready` because the `not` polarity content is absent from the pool.

### Pinned policy: `AHE-022` `viewed`

- R17-DEC-022-01: The frame is supported and valid; the trigger is `viewed`.
- R17-DEC-022-02: The eligible set requires a subject role and an object role; the exact object boundary among the 35 candidates is authored and reviewed in the policy record, not chosen by the evaluator.
- R17-DEC-022-03: The observed select-all answer fails semantic selection because the pool contains Candidates redundant relative to the canonical role boundaries and ineligible sub-constituents.
- R17-DEC-022-04: Composition readiness is `not_ready` for `AHE-022` because the reference selected set's subject role lacks a resolved entity reference (`subject_unavailable`); readiness evaluates the reference set, so the incorrect select-all answer does not drive this value.

### Review and freeze procedure

- R17-REV-01: The policy author writes each expected selected set and eligibility explanation; the policy reviewer approves it; neither role is performed by the coding agent.
- R17-REV-02: Each policy record stores author identity, reviewer identity, review date and commit, and the source, pool, and policy-body digests, so the review evidence binds the answer to its source, pool, and policy.
- R17-REV-03: The runner loads policy records and observed answers from frozen files; it never generates an expected answer.
- R17-REV-04: A policy record becomes acceptance evidence only after its review evidence and digests are present and its content matches the frozen contract version.
- R17-REV-05: At an operator's explicit request, a coding agent can draft policy records with its draft-author identity and empty human approval fields.
  A human policy author adopts or edits those decisions, and a human policy reviewer approves the resulting policy-body digest before the record becomes acceptance evidence.
  The record preserves the agent's draft authorship after human adoption.

## 4. Proposed Architecture

```text
versioned, digest-bound semantic selection contract
      |
      +--> task renderer -------------------------> Constituent Selection Task
      |        instruction = eligibility rule
      |        body = frozen Event frame + Candidate pool
      |
      +--> reference policy records --------------> human-reviewed expected selected set
      |        author + reviewer + review evidence + digests
      |        expected source ranges (independent of pool)
      |
      +--> observed answers ----------------------> raw response + reused parsed form (model or constructed)
      |
      v
deterministic signal evaluator (contract, policy record, observed answer)
      |-- answer grammar           valid | invalid
      |-- semantic selection       met | unmet | not_applicable
      |-- boundary coverage        met | gap
      |-- abstention correctness   justified | unjustified | not_applicable
      |-- composition readiness    ready | not_ready | not_applicable
      |
      v
frozen report (zero model executions, zero canonical writes)
```

## 5. Key Interactions

The policy author and reviewer finalize each reference policy record before the contract freezes.
The renderer writes the eligibility rule into the task instruction and keeps the Event frame and the Candidate pool unchanged.
The signal evaluator reads a reference policy record and a separate observed answer, never the expected set evaluated against itself.
The boundary-coverage evaluator compares each expected source range against the Candidate pool and records a gap when no Candidate covers it, independent of the observed answer.
The evaluator parses each observed raw response once, through the R16 strict parser for the response's route (reusing the shared `ConstituentSelectionAnswer` DTO), and that strict-parse result drives the answer-grammar, semantic-selection, and abstention-correctness signals.
Composition readiness evaluates the reference selected set, never the observed answer, so it diagnoses the case independent of selection correctness.
The evaluator computes the five signals independently and never merges them into one score.
The runner seals one report that names the contract version, the policy records, the observed answers, and the signal results.

## 6. Data Model

`SemanticSelectionContract` stores the version, the eligibility rule, the complete-selected-set rules, the NONE rule, the canonical-boundary rules, the five signal definitions, and the content digests that freeze it.
`ReferencePolicyRecord` stores the Event ID, the source digest, the Candidate-pool digest, the human-reviewed expected selected set, the eligibility explanation, the expected source ranges, the author and reviewer identities, the review evidence, and the policy-body digest.
`ObservedAnswer` stores the Event ID, the route (`label_only_reselection` or `best_choice_reselection`), the raw response text and its digest, the reused `ConstituentSelectionAnswer` (status `selected`, `none`, or `rejected`; `rejected` is the strict parser's encoding of a response that fails the route's grammar), and the source-run artifact handle and digest. Its validator parses the raw response through the R16 strict parser for the route (`parse_corrective_reselection_answer`) against the task's `constituent_labels` and requires the stored parsed form to match. The permissive R3 parser is not used for the grammar, so an empty-element or duplicate-label response that R3 would repair still parses as `rejected`. The validator also binds the stored route to the Event's frozen task route and fails fast when they mismatch, so an observed answer never chooses whichever grammar accepts it.
Historical diagnostic tasks retain their frozen R15 routes.
Supplemental constructed cases bind their routes in a separate task manifest and never claim historical R15 provenance.
`Frozen inputs` — the source text, the Candidate pool (`ConstituentCandidateInventory`), the Event frame, and the composition inputs (Gold, Stanza, dependency tree) — are located by Event ID through the same frozen, digest-bound loaders R3 and R4 use; the policy record's digests verify supplied content, they do not locate it.
`SemanticSelectionSignalResult` stores one signal name, one legal value, and one explanation per (policy record, observed answer) pair.

## 7. APIs / Interfaces

- `render_selection_task(contract, event_frame, pool)` returns one Constituent Selection Task whose instruction names the eligibility rule.
- `load_reference_policy_records(contract)` returns the frozen, digest-bound policy-record set; it fails fast when any record lacks its author, reviewer, review evidence, or any digest.
- `load_observed_answers(contract)` returns the frozen observed answers as raw-response records with their reused parsed forms, kept separate from the policy records.
- `evaluate_selection(contract, policy_record, observed_answer)` parses the raw response once through the R16 strict parser for the route, then returns one signal result set applied independently.
- `check_boundary_coverage(contract, policy_record)` compares each expected source range against the Candidate pool and returns `met` when a Candidate's span covers the range, or `gap` when none covers it.
- `seal_semantic_selection_report(contract, policy_records, observed_answers, signal_results)` returns one sealed report with a result fingerprint and zero writes.

## 8. Behavior & Domain Rules

The semantic selection contract is the source of truth for eligibility, completeness, NONE justification, and the five signals.
The expected selected set is a policy record, never derived from an answer; the observed answer is a separate deterministic input.
Semantic selection and composition readiness never share one score.
The renderer never reuses a format-only instruction; it always appends the eligibility rule.
The evaluator never derives eligibility from an answer's grammatical validity.
Answer grammar is strict and route-dispatched: the evaluator reuses the R16 strict parsers, never the permissive R3 parser, so a response whose route grammar fails is `rejected` even when the R3 parser could recover a selection.
The observed answer's route must equal its frozen task's route; a mismatch fails fast at the boundary and is never re-judged under the other grammar.
Composition readiness evaluates the reference selected set, never the observed answer.
The evaluator obtains the source, the Candidate pool, the Event frame, and the composition inputs through the frozen R3/R4 loaders addressed by Event ID; digests verify, they do not locate.
Boundary coverage never reuses the Candidate pool as its own expectation; expected source ranges are independent.
A missing required marker is a recorded gap and a named follow-up change, never silently treated as affirmed.
The reference policy records never tune against the held-out partition.
Model discrimination and ranking experiments follow only after this contract freezes.

## 9. Acceptance Criteria

- AC-R17-VER-01: Tests prove the contract version is monotonic and changes when any of the four decisions changes.
- AC-R17-VER-02: Tests prove a policy record whose content changes without a version bump fails the digest check.
- AC-R17-ELG-01: Tests prove a syntactically attached Candidate is available but not eligible until it satisfies the role rules.
- AC-R17-ELG-02: Tests prove eligibility stays unchanged when the Actor or Organization entity reference is removed.
- AC-R17-ELG-03: Tests prove the reporting carrier never appears in the selected set and enters composition through the R4 split.
- AC-R17-SET-01: Tests prove nested Candidates naming one role reduce to the narrowest source-exact canonical boundary.
- AC-R17-SET-02: Tests prove a select-everything answer fails when the pool contains ineligible or redundant Candidates, and passes when the pool contains exactly the required constituents.
- AC-R17-SET-03: Tests prove two matching-text occurrences stay distinct when they are separate source occurrences.
- AC-R17-NONE-01: Tests prove a justified NONE differs from malformed output, a missing boundary, an unresolved trigger, and unsupported input.
- AC-R17-NONE-02: Tests prove `AHE-051` pins the supported frame, the eligible set `{C3}`, the polarity boundary gap, the follow-up change, and the unjustified-abstention judgment (R17-DEC-051).
- AC-R17-NONE-03: Tests prove an observed NONE is judged by the abstention-correctness signal against the expected eligible set.
- AC-R17-NONE-04: Tests prove the `AHE-051` five-signal profiles from R17-DEC-051-07 and R17-DEC-051-08: observed `NONE` is `valid`/`unmet`/`gap`/`unjustified`/`not_ready`, and a constructed `C3` answer is `valid`/`met`/`gap`/`not_applicable`/`not_ready`.
- AC-R17-SIG-01: Tests prove removing entity references changes composition readiness from `ready` to `not_ready` in a case that was initially ready, while the semantic-selection judgment stays unchanged.
- AC-R17-SIG-02: Tests prove each of the five signals computes independently with no merged score.
- AC-R17-SIG-03: Tests prove malformed output sets answer grammar to `invalid` and semantic selection and abstention correctness to `not_applicable`, while boundary coverage and composition readiness remain computed.
- AC-R17-SIG-04: Tests prove a required source range with no covering Candidate records a boundary-coverage gap, and a range contained in a larger Candidate records `met`.
- AC-R17-SIG-05: Tests prove the applicability matrix holds: malformed output leaves boundary coverage and composition readiness computed, and composition readiness follows the reference selected set, not the observed answer.
- AC-R17-SIG-06: Tests prove the grammar signal reuses the R16 strict parsers, not the permissive R3 parser: raw responses `,C3,,`, `C3,C3`, and `,NONE,` are grammar `invalid` and parse `rejected`, while the shared `ConstituentSelectionAnswer` DTO is retained with no parallel answer type.
- AC-R17-SIG-07: Tests prove the route binding fails fast: an observed answer whose route differs from its frozen task's route is rejected at the boundary and is never re-judged under the other grammar.
- AC-R17-SIG-08: Tests prove the fixtures preserve route limits: a `label_only` happy-path answer carries multiple comma-separated labels (with `NONE` rejected), and a `best_choice` happy-path answer carries exactly one label or the exact token `NONE`.
- AC-R17-REF-01: Tests prove the policy-record set covers the two diagnostic regression cases plus one case per selectable role and one justified-NONE case.
- AC-R17-REF-02: Tests prove every policy record carries author identity, reviewer identity, review evidence, and the source, pool, and policy-body digests.
- AC-R17-REF-03: Tests prove the evaluator never evaluates an expected set against itself; each evaluation pairs a policy record with a distinct observed answer.
- AC-R17-REF-04: Tests prove an agent-authored draft cannot become acceptance evidence without recorded human adoption and human review of its policy-body digest (R17-REV-05).
- AC-R17-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Composition rules: `packages/application/src/kotekomi_application/decontextualization_composition.py`.
- Selection DTOs: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (the shared `ConstituentSelectionAnswer` DTO).
- Strict grammar parsers: `packages/application/src/kotekomi_application/corrective_reselection_execution.py` (`parse_label_only_reselection_answer`, `parse_best_choice_reselection_answer`, `parse_corrective_reselection_answer`).
- Original task renderer: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py`.
- Selection-failure slots: `packages/application/src/kotekomi_application/selection_failure_slot_routing.py`.
- Composition-hold dispositions: `packages/application/src/kotekomi_application/residual_composition_hold_routing.py`.
- New module: `packages/application/src/kotekomi_application/semantic_selection_contract.py`.
- Policy records (drafts require human adoption and review): `data/r17-semantic-selection-contract/reference_policy_records.json`.
- Draft policy review: `docs/2026-10-07-semantic-selection-policy-review.md`.
- Observed answers (frozen): `data/r17-semantic-selection-contract/observed_answers.json`.
- Tests: `packages/application/tests/test_semantic_selection_contract.py`.
- Runner: `scripts/run_semantic_selection_contract.py`.

## 11. Constraints and Halt Conditions

R17 keeps the R3 parser, the R4 composer, the R15 closure routes, and the R16 execution runner unchanged.
The Application Layer invokes no model and reads no held-out partition Gold.
The coding agent drafts expected selections and eligibility explanations only at an operator's explicit request under R17-REV-05.
The coding agent never supplies human adoption, human review, or approval evidence.
The runner writes no canonical state and no ProposedChanges.
Halt when the contract version drifts from the renderer, the policy records, the scoring rules, or the thresholds.
Halt when a policy record lacks its author, reviewer, review evidence, or any digest.
Halt when the evaluator receives no separate observed answer.
Halt when an observed answer's route differs from its frozen task's route.
Halt when any signal merges into one score.
Model discrimination and ranking experiments stay outside this deliverable.

## 12. Execution & Experimentation Directive

- Implement the versioned, digest-bound contract, the renderer, the policy-record loader, the observed-answer loader, the boundary-coverage check, and the five-signal evaluator.
- Freeze the human-authored policy records together with the contract, the renderer, the scoring rules, and the thresholds in one version.
- Evaluate once, recording the observed-answer signal results in the Run Record.
- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R17 has not run.
