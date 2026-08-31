# TDD: Organization Mention Boundary Reconciliation MVP

- Status: Accepted
- Program: [Organization Mention Reconciliation and Resolution Program](2026-08-28-organization-mention-reconciliation-program.md)
- Increment: ORG-R1
- Predecessor: ORG-R0 shared trace and held-out annotation foundation
- Scope: deterministic derived diagnostics only

## User story

As a reviewer, I can see why one literal Organization-mention boundary survived or remained ambiguous when Qwen2.5 and GLiNER propose different spans over the same authoritative text.

## Outcome

ORG-R1 turns source-valid `MentionCandidate` records into deterministic, reviewable boundary decisions.

It safely resolves only boundary conflicts whose answer follows from source characters and a named policy.

It preserves every unresolved candidate and emits `ambiguous` instead of choosing by score, proposer, input order, or span length.

ORG-R1 does not decide whether a source expression denotes an Organization, and it does not resolve an acronym or reference to an entity.

## Context

ORG-R0 established source-bound Qwen2.5 and GLiNER proposal traces plus an independently reviewed 50-paragraph held-out packet that was not used to tune current proposal behavior.

The H2.3 monotonic union preserves recall but deliberately retains overlapping candidates.

Those overlaps include safe syntactic cases, semantic alternatives, and true ambiguity.

One generic winner rule would mix those cases and silently discard evidence.

## Authority boundary

The accepted `DocumentRepresentationBundle` and its `SourceSegment` text remain authoritative.

`MentionProposalObservation`, `MentionCandidate`, boundary relations, boundary decisions, reconciled candidates, Gold catalogs, evaluation reports, and `ExtractionStageTrace` records are derived state.

No ORG-R1 record is accepted Ledger knowledge or authorizes a `ProposedChange`.

All input spans must match exact authoritative source characters before reconciliation.

Invalid coordinates, text drift, digest drift, duplicate candidate identities, or trace drift fail explicitly.

## Application contracts

### `MentionBoundaryRelation`

The relation between two half-open source intervals is exactly one of:

```text
equal
contains
contained_by
crossing
adjacent
disjoint
```

For `A` relative to `B`, `equal` means both boundaries match, `contains` means `A` strictly contains `B`, `contained_by` is its inverse, `crossing` means the intervals overlap without containment, `adjacent` means one ends exactly where the other begins, and `disjoint` means they neither overlap nor touch.

### `MentionBoundaryDecisionStatus`

```text
resolved
ambiguous
uncontested
```

`resolved` means a named source-literal rule selected a terminal expression from a conflict component.

`ambiguous` preserves the whole conflict component without a winner.

`uncontested` means a candidate has no overlapping competing boundary.

### `MentionBoundaryDecision`

Each decision records at least:

```text
id
source_segment_id
source_text_digest
status
rule_id
candidate_ids
selected_candidate_ids
preserved_candidate_ids
alias_evidence_candidate_ids
relations
diagnostics
```

Order is canonical.

An ambiguous decision has no selected candidate.

Every input candidate appears in exactly one decision and in `preserved_candidate_ids`.

### `ReconciledMentionCandidate`

A reconciled candidate records at least:

```text
id
source_segment_id
source_text_digest
text
start
end
source_candidate_ids
proposer_ids
decision_id
boundary_status
alias_evidence_candidate_ids
```

It identifies a terminal boundary decision but does not assert Organization qualification.

### `OrganizationBoundaryReconciliationResult`

The result records:

```text
policy_id
source_segment_id
source_text_digest
relations
decisions
reconciled_candidates
```

The policy identity is `organization_boundary_reconciliation_v1`.

Equivalent source boundaries produce identical decisions and selected boundaries regardless of input order, proposer order, scores, or model-run identities.

Proposer and model-run provenance remains preserved, so provenance-bearing output can differ when that evidence differs even though the decision cannot.

## Deterministic policy

The policy applies these rules in order.

### 1. Validate and merge equal source spans

Existing proposal fusion validates every observation against source characters and merges observations with equal spans.

Equal-span provenance is retained.

An input that bypasses this invariant fails rather than being silently repaired.

### 2. Recognize an exact parenthetical alias declaration

For an outer candidate whose complete text has exact source form `expanded name (ALIAS)`, the complete outer expression is selected when nested candidates correspond exactly to the expanded-name or alias substrings.

The nested alias is retained as alias evidence.

This rule does not resolve later uses of that alias to an entity.

Malformed, partial, or competing parenthetical structures remain ambiguous.

### 3. Remove only a terminal possessive suffix

When one candidate is exactly another candidate plus terminal ASCII `'s` or Unicode `’s`, the non-possessive candidate is selected.

No other punctuation, determiner, geographic qualifier, legal suffix, or lexical material is stripped in ORG-R1.

### 4. Preserve uncontested candidates

Non-overlapping and adjacent candidates remain separate `uncontested` candidates.

ORG-R1 does not fuse them into a phrase or suppress one because it is nearby.

### 5. Preserve unresolved overlap

Every remaining nested or crossing conflict is `ambiguous`.

All source-valid candidates remain inspectable and no reconciled winner is emitted for that component.

## Forbidden winner signals

The policy must not select a boundary because of a proposal score, proposer, model run, input order, observation count, longest span, shortest span, capitalization, or fixture-specific name.

## Gold catalog compiler

A deterministic compiler turns the reviewed Markdown packet into a machine-readable held-out catalog.

The catalog binds fixture and fixture SHA-256; representation and paragraph-node identity; exact paragraph text and SHA-256; V3 Source segment identity, exact authoritative text, traceable model-facing Source copy, and their digests; literal Gold expressions in both coordinate systems; repeated source occurrences; `resolved:` source components; reviewer notes; and packet bytes and SHA-256.

Literal allocation is deterministic:

1. exact source characters are mandatory;
2. accepted longer expressions reserve their source interval before shorter accepted expressions can use the same characters;
3. standalone occurrences use lexical boundaries when an expression starts or ends with a word character;
4. repeated expressions allocate remaining eligible occurrences in source order;
5. every requested occurrence resolves exactly once;
6. every selected literal span fits wholly inside one V3 Source segment.

The compiler fails on source drift, ambiguous allocation, missing expressions, excess requested occurrences, segment drift, development-Gold overlap, or malformed resolved components.

Resolved entries remain reference-resolution Gold and are excluded from ORG-R1 exact-boundary scoring.

The catalog contains exactly 50 reviewed paragraphs, 150 literal occurrences, five reference-resolution entries, and zero V3 Source segments shared with development Gold.

## Evaluation record

The evaluator consumes pinned proposer evidence and emits canonical JSON plus a human-readable report.

For every Source segment it records exact source and Gold offsets; Qwen prompt, rendered input, raw output, proposals, model, and `ModelRun`; GLiNER source, proposals, model, package version, threshold, and effective flat-span configuration; fused candidates; interval relations; conflict components; rules; terminal decisions; selected and ambiguous candidates; stage traces; and exact, partial, missed, and spurious outcomes.

Outcomes expose these diagnostic signals when applicable:

```text
qwen_exact_missing
gliner_exact_missing
both_proposers_missing
partial_candidate_available
exact_candidate_available
reconciliation_ambiguous
reconciliation_wrong_selection
source_or_gold_integrity_failure
qualification_pending
```

An uncontested singleton false positive is `qualification_pending`, not an ORG-R1 boundary failure, because semantic qualification belongs to ORG-R2.

## Development protocol

Freeze one three-repetition `php1_span_proposer_comparison_v1` report before changing reconciliation behavior.

Development uses the existing 164-segment Organization Gold catalog and frozen Qwen2.5 and GLiNER proposal evidence.

Reconciliation tuning must not rerun Qwen or change proposer prompts, models, thresholds, or parsing.

Classify failures as source or Gold integrity, proposer exact miss, partial candidate available, policy ambiguity, wrong deterministic selection, qualification pending, or implementation defect.

## Development acceptance gates

The development result is acceptable only when:

1. zero resolved Gold-overlapping conflict decisions select a wrong boundary;
2. at least one non-equal conflict is safely resolved by a named rule;
3. every unresolved conflict is `ambiguous` with no selected candidate;
4. candidate retention is 100 percent;
5. equal spans retain all proposer provenance;
6. input order, score, proposer, and model-run perturbations do not change decision status, rule, or selected boundaries;
7. pinned replay produces byte-identical canonical JSON;
8. no production Pipeline, prompt, model, threshold, ontology contract, or accepted Ledger state changes.

The zero-wrong gate applies to decisions the policy claims to resolve, not to universal recall.

## Held-out protocol

The held-out catalog is not used to design, tune, or debug ORG-R1.

After policy, implementation, tests, and development evidence are frozen, run the held-out evaluation once.

The held-out gate is zero wrong `resolved` boundary decisions.

If a policy decision fails, record the implementation as `not_selected` and preserve the result; do not tune against the same catalog.

A rerun is allowed only for a demonstrated infrastructure, source-integrity, catalog-compiler, or execution defect that did not expose policy outcomes before correction.

## Acceptance criteria

### AC-R1-01 — Interval algebra is total

Every valid pair receives one relation and inverse relations are correct.

### AC-R1-02 — Equal evidence is merged

Equal spans retain every proposer observation and produce one uncontested candidate.

### AC-R1-03 — Parenthetical aliases are safe

An exact declaration selects the complete expression and preserves nested alias evidence.

### AC-R1-04 — Possessive removal is narrow

Only terminal `'s` and `’s` conflicts select the non-possessive expression.

### AC-R1-05 — Adjacency does not imply identity

Adjacent and disjoint candidates remain separate and uncontested.

### AC-R1-06 — Ambiguity loses no evidence

Unrecognized nested and crossing conflicts retain every candidate and select no winner.

### AC-R1-07 — No hidden ranking policy

Scores, proposers, model runs, observation counts, and input order cannot change decision status, rule, or selected boundaries.

### AC-R1-08 — Invalid deterministic inputs fail

Invalid offsets, drift, duplicate identities, equal-span bypass, and tampered traces fail explicitly.

### AC-R1-09 — Gold compilation is exact

The reviewed packet compiles to exact offsets with locked counts and no development overlap.

### AC-R1-10 — Resolved references remain separate

The five context-dependent entries retain source components and do not enter boundary scores.

### AC-R1-11 — Diagnostics are complete

Canonical JSON and review output expose source, proposer, fusion, relation, rule, decision, Gold, score, and trace evidence without truncating model output.

### AC-R1-12 — Development gates pass

Frozen development replay meets every development gate.

### AC-R1-13 — Held-out is evaluated once

The frozen implementation receives one held-out evaluation and records the gate result.

### AC-R1-14 — Production remains unchanged

ORG-R1 adds no Adapter dependency, production selection, prompt change, ontology expansion, Ledger write, migration, or compatibility path.

## Required tests

Application tests cover interval relations and inverses; component grouping and ordering; equal provenance merge; ASCII and Unicode possessives; parenthetical aliases; adjacency; nested and crossing ambiguity; score/proposer/run/order independence; invalid offsets and drift; complete candidate preservation; and deterministic serialization.

Pipeline and script tests cover repeated and nested literal allocation; possessives; longer-expression reservation; V3 segment mapping; discontinuous resolved components; scoring exclusion; tampered proposal and trace evidence; complete reports; diagnostic classification; byte-identical replay; development gates; and one-run held-out enforcement.

## Verification

Run focused ORG-R1 Application and Pipeline tests, packet verification, machine catalog compilation, one frozen development replay, and one final held-out evaluation.

Then run applicable formatting, lint, Pyright, Application, Adapter, Pipeline, and repository checks from `docs/CHECK_PLAN.md`.

## Out of scope

Semantic qualification, ReFinED, acronym or reference resolution, prompt changes, proposer changes, ontology expansion, accepted Ledger writes, production selection, and compatibility code are out of scope.

## Stop condition

Stop after the deterministic policy, development replay, and one sealed held-out evaluation are recorded and verified.

Do not begin ORG-R2.

## Implementation result

The implementation was frozen at commit `7e0475715d39ccb072795acfa66d957575092bf1` before the held-out catalog was evaluated.

The development and one-time held-out evaluations selected `organization_boundary_reconciliation_v1` with zero wrong resolved decisions, complete candidate retention, no ambiguous winner, and safe non-equal conflict resolution.

The held-out pass safely resolved three unique exact parenthetical-alias conflicts and one unique terminal-possessive conflict.

The five context-dependent reference entries remained excluded from ORG-R1 scoring as designed.

Uncontested non-Gold selections remain `qualification_pending`; ORG-R1 did not reinterpret those semantic type decisions as boundary failures.

The compact immutable result and artifact digests are recorded in [Organization Boundary Reconciliation Result](organization-boundary-reconciliation-result-v1.json).
