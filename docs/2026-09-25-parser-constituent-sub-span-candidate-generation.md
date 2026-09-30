# TDD: Parser-Constituent Sub-Span Candidate Generation

- Status: Accepted
- Deliverable ID: `R3-A`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Depends on: [R3 Parser-Constituent Candidate Generation](2026-09-25-parser-constituent-candidate-generation.md)
- Supersedes: candidate granularity of R3 requirements `R3-CST-02` and `R3-CST-03`

## 1. Context & Problem

The R3 runner derives one Constituent Candidate Inventory per Event from the pinned Stanza dependency tree.

R3 emits mostly one clause-level contiguous token group per sentence, the Detached-clause groups, and the Event trigger.

The corrected Attachment Gold stores word-level and phrase-level Attachment Candidates.

Most corrected Gold fragments equal one dependency token or one syntactic phrase, not one whole clause.

The run-001 Constituent Pool Ceiling measures `0.1628` on development and `0.1887` on validation.

The Constituent Pool Ceiling is the best exact-set Attachment Gold score a perfect selector can reach.

A ceiling that low makes most false negatives structurally unreachable, not selection errors.

R3-A adds Sub-span candidates so word-level and phrase-level Gold fragments enter the pool.

The selection renderer, selection parser, scoring, and report stay exactly as R3 defines them.

### Terms

**Dependency token** means one `EventEntityLinguisticToken` in the pinned Stanza dependency tree.

**Dependency subtree** means one head dependency token plus every dependency token reachable from it by child edges within one sentence.

**Detached clause** means one subtree whose root dependency relation is one of `acl`, `acl:relcl`, `advcl`, or `parataxis`.

**Token sub-span** means the exact source range of one dependency token.

**Head phrase projection** means the contiguous source range from the leftmost to the rightmost dependency token in one dependency subtree after every Detached clause is removed and the remaining tokens split into contiguous token groups at non-whitespace source gaps.

**Sub-span candidate** means a Parser Constituent whose range is one Token sub-span or one Head phrase projection.

**Parser Constituent**, **Constituent Candidate Inventory**, **Constituent Pool Ceiling**, **Corrected Attachment Gold**, **Gold Attachment Set**, **Event trigger**, and **Held-out partition** keep the R3 meaning.

### Primary flow

1. The runner binds the frozen Proposition Gold, trigger Gold, connection Gold, and pinned Stanza runtime by SHA-256.
2. The runner re-derives the Corrected Attachment Gold with the R2 splitter.
3. The Application Layer derives one Token sub-span per dependency token per Event.
4. The Application Layer derives one Head phrase projection per dependency head that governs a dependent, per Event.
5. The Application Layer adds every Sub-span candidate to the R3 clause-level inventory and removes duplicate exact spans.
6. The Application Layer measures Boundary Fidelity and the Constituent Pool Ceiling against the corrected Gold.
7. The runner renders, runs, and scores one finite selection task per Event exactly as R3 does.
8. The report lists every corrected Gold fragment the enrichment still misses.

## 2. Goals

- The Constituent Pool Ceiling reaches at least `0.90` on both partitions.
- The inventory includes every dependency token as one standalone candidate.
- The inventory includes one phrase candidate per dependency head that governs a dependent.
- An operator can read every corrected Gold fragment the enrichment still misses.
- The inventory adds at most two Sub-span candidates per dependency token.
- The selection renderer, selection parser, scoring, and report stay unchanged from R3.

## 3. Requirements

### Sub-span derivation

The inventory builder owns these requirements.

- R3A-CSP-01: The inventory builder derives one Token sub-span per dependency token in the Event SourceSegment.
- R3A-CSP-02: The inventory builder derives one Head phrase projection per dependency token that governs at least one dependent.
- R3A-CSP-03: The inventory builder derives every Sub-span candidate from the pinned Stanza dependency tree.
- R3A-CSP-04: Every Sub-span candidate is source-exact.
- R3A-CSP-05: Every Sub-span candidate is a clause-local contiguous token group.
- R3A-CSP-06: A Head phrase projection never crosses a Detached clause boundary.
- R3A-CSP-07: The inventory builder reads no corrected Gold while deriving Sub-span candidates.
- R3A-CSP-08: The inventory builder invents no source characters.

### Inventory composition

The inventory builder owns these requirements.

- R3A-INV-01: The enriched inventory keeps the R3 clause-level Parser Constituents and the Event trigger.
- R3A-INV-02: The enriched inventory adds every Sub-span candidate and removes duplicate exact spans.
- R3A-INV-03: The enriched inventory keeps source order and exact-span distinctness.
- R3A-INV-04: The enriched inventory adds at most two Sub-span candidates per dependency token.
- R3A-INV-05: Equal inputs produce a byte-identical enriched inventory.

### Boundary fidelity

The report owns these requirements.

- R3A-FID-01: The report classifies each corrected Gold fragment as covered or missed by exact span.
- R3A-FID-02: The report computes the Constituent Pool Ceiling per partition.
- R3A-FID-03: The Constituent Pool Ceiling reaches at least `0.90` on both partitions.
- R3A-FID-04: The report lists every corrected Gold fragment the enriched inventory still misses.
- R3A-FID-05: The report labels each missed fragment as neither a Token sub-span nor a Head phrase projection.

### Selection and report reuse

The selection renderer, selection parser, and report keep these requirements from R3.

- R3A-SEL-01: The selection renderer names every inventory constituent by one stable label.
- R3A-SEL-02: The selection parser accepts a finite label subset or the exact NONE token.
- R3A-SEL-03: The selection renderer sends no candidate boundary to the model.
- R3A-SCR-01: The report maps each Selected Constituent Set onto the corrected Gold Attachment Set.
- R3A-SAF-01: Model output never enters accepted state.
- R3A-SAF-02: The runner creates zero ProposedChanges and zero accepted Ledger writes.

## 4. Proposed Architecture

```text
frozen Proposition Gold + trigger Gold + connection Gold
                      |
                      +--> re-derived Corrected Attachment Gold (R2 splitter)
                      |
                      v
         pinned Stanza dependency tree
                      |
                      +--> R3 clause-level Parser Constituents  (kept)
                      +--> Token sub-span per dependency token
                      +--> Head phrase projection per governing head
                      |              |
                      v              v
         Constituent Candidate Inventory per Event (deduplicated, ordered)
                      |
                      +--> Boundary Fidelity census (vs corrected Gold)
                      |
                      v
         finite selection tasks (unchanged from R3)
                      |
                      +--> local model Constituent Selection
                      |
                      v
         selection census + JSON report + Markdown review
```

## 5. Key Interactions

```text
Runner       -> R2 splitter         : re-derive Corrected Attachment Gold
Application  -> Stanza tree         : derive Token sub-spans and Head phrase projections
Application  -> inventory builder   : merge, deduplicate, and order Sub-span candidates
Application  -> Boundary Fidelity   : classify Gold fragments as covered or missed
Application  -> selection renderer  : name every constituent by one stable label
Runner       -> local model         : run one Constituent Selection per Event (unchanged)
Application  -> selection parser    : parse one finite subset or NONE (unchanged)
Application  -> report              : score selections and record the ceiling
```

## 6. Data Model

`ParserConstituent` keeps its R3 shape and adds no field.

`ConstituentCandidateInventory` keeps its R3 shape.

The Constituent Pool Ceiling stays a derived coverage ratio over the enriched inventory.

No new record type appears.

## 7. APIs / Interfaces

The inventory builder accepts one Event, its dependency tokens, its source text, and its Event expression.

The inventory builder returns one enriched `ConstituentCandidateInventory`.

The selection renderer, selection parser, scoring functions, and report keep the R3 interfaces.

## 8. Behavior & Domain Rules

The parser, not the model, draws every Sub-span boundary.

A Token sub-span is one dependency token exact range.

A Head phrase projection is one dependency subtree contiguous range after Detached clause removal.

A corrected Gold fragment is covered only by an exact equal span.

The Constituent Pool Ceiling stays a diagnostic bound, not a selection.

An invalid model answer still produces rejection or quarantine, never accepted state.

The held-out partition stays reserved and unread.

## 9. Acceptance Criteria

- AC-R3A-CSP-01: Tests prove one Token sub-span exists per dependency token.
- AC-R3A-CSP-02: Tests prove one Head phrase projection exists per governing dependency token.
- AC-R3A-CSP-03: Tests prove every Sub-span candidate derives from the pinned tree.
- AC-R3A-CSP-04: Tests prove every Sub-span candidate is source-exact.
- AC-R3A-CSP-05: Tests prove every Sub-span candidate is clause-local and contiguous.
- AC-R3A-CSP-06: Tests prove a Head phrase projection never crosses a Detached clause.
- AC-R3A-CSP-07: Tests prove the builder reads no Gold.
- AC-R3A-CSP-08: Tests prove the inventory invents no source characters.
- AC-R3A-INV-01: Tests prove the R3 clause-level constituents and trigger survive enrichment.
- AC-R3A-INV-02: Tests prove Sub-span candidates deduplicate by exact span.
- AC-R3A-INV-03: Tests prove the enriched inventory keeps source order and distinctness.
- AC-R3A-INV-04: Tests prove growth stays at most two Sub-span candidates per token.
- AC-R3A-INV-05: Equal inputs produce a byte-identical enriched inventory.
- AC-R3A-FID-01: The offline fixture E2E report classifies every corrected Gold fragment covered or missed.
- AC-R3A-FID-02: The offline fixture E2E report recomputes the Constituent Pool Ceiling per partition.
- AC-R3A-FID-03: The offline fixture E2E ceiling reaches at least `0.90` on both partitions.
- AC-R3A-FID-04: The offline fixture E2E report lists every still-missed corrected Gold fragment.
- AC-R3A-FID-05: The offline fixture E2E report labels each missed fragment as neither a Token sub-span nor a Head phrase projection.
- AC-R3A-SEL-01: Tests prove the selection renderer still names one label per constituent and sends no boundary.
- AC-R3A-SEL-02: Tests prove the selection parser still accepts only a finite subset or NONE.
- AC-R3A-SCR-01: Tests prove the selection census still maps selected spans onto the corrected Gold Attachment Set.
- AC-R3A-SAF-01: The report records zero canonical writes and zero ProposedChanges.
- AC-R3A-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Clause-local derivation: `packages/application/src/kotekomi_application/source_grounded_proposition_scope.py` (`_clause_local_constituents`).
- R3 candidate builder: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`_clause_local_constituent_spans`, `build_constituent_candidate_inventory`).
- Dependency token model: `packages/application/src/kotekomi_application/event_entity_connections.py` (`EventEntityLinguisticToken`).
- Detached-clause relation set: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`_DETACHED_CLAUSE_RELATIONS`).
- Application tests: `packages/application/tests/test_parser_constituent_candidate_generation.py`.
- Pipeline tests: `packages/pipelines/tests/test_parser_constituent_candidate_generation.py`.
- Runner: `scripts/run_parser_constituent_candidate_generation.py`.
- Config: `docs/r3-parser-constituent-run-config.toml`.

## 11. Constraints and Halt Conditions

- Stop when the enriched inventory reads the corrected Gold to choose a Sub-span candidate.
- Stop when a Sub-span candidate cannot materialize to exact source characters.
- Stop when the offline fixture E2E ceiling stays below `0.90` on either partition; record the missed-fragment taxonomy for a follow-up TDD.
- Stop when the enriched inventory must invent source characters.
- Do not change the selection renderer, selection parser, scoring, or report in this TDD.
- Defer the answer-adherence recovery to a separate TDD; this TDD does not loosen the finite answer parser.