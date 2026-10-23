# TDD: Production Closure of AHE-022 and AHE-051

- Status: Proposed
- Deliverable ID: `R19`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Semantic Instruction Discrimination Experiment](2026-10-15-semantic-instruction-discrimination-experiment.md)
- Depends on: [Semantic Selection Contract](2026-10-07-semantic-selection-contract.md), [Decontextualization Composition](2026-09-28-decontextualization-composition.md), [Corrective Re-Selection Execution](2026-10-06-corrective-reselection-execution.md)
- Replaces prior premises: [Event-Entity Connection Second Opinion](2026-09-16-event-entity-connection-second-opinion.md)

## 1. Context & Problem

R17 freezes one human-adopted Reference selected set per residual Event and the five acceptance signals that score each observed answer. R18 measures model re-selection under a semantic instruction and finds no measured improvement.

The operator keeps the completeness bar for the two open residuals, `AHE-022` and `AHE-051`: they must close through the actual Pipeline. `AHE-004` is already closed by R12 through R14. A typed blocked or partial outcome is useful failure reporting, but it does not satisfy the closure bar.

R19 is production closure of `AHE-022` and `AHE-051`: production-generated selection that satisfies the reviewed semantic policy, entity references resolved by a declared source-grounded provider, and a composed Assertion whose arguments, polarity, modality, and attribution are preserved and inspectable with exact source spans.

### AHE-022

The Event is `viewed`; its Reference selected set is `{C1, C3}` - `C1 Sacks` (subject) and `C3 Amodei's decision` (object). Polarity `affirmed`; attribution `source_narrator`.

Two separate problems remain:

1. **Semantic selection is still incorrect.** The archived production answer selects every candidate, `C1..C35`, instead of `{C1, C3}`. R18's instruction change produces no measured improvement. The extra selected candidates are a selection defect, not a composition defect.
2. **A required entity reference is missing.** The composer's subject role resolves only an Actor or Organization reference, and no reviewed reference for `Sacks` reaches the composer, so it holds on `subject_unavailable`. That reference is a composition input supplied by the declared Event-Entity Connection provider; it is not necessarily missing from the constituent pool, and adding a reference does not fix the over-selection nor, by itself, prove production entity resolution.

### AHE-051

The sentence is `[45] The April order is not final.`; its Reference selected set is `{C3}` - `C3 The April order` (subject). Polarity `negated`; modality `actual`; attribution `source_narrator`.

Four separate problems remain:

1. **Semantic selection is still incorrect.** The archived production answer is `NONE`, which the R17 policy marks unjustified because `{C3}` is non-empty.
2. **Polarity is lost.** Stanza labels `not` as `advmod`; the composer derives polarity from the `neg` dependency relation only, so it records `affirmed` instead of `negated`.
3. **A required entity reference is missing.** The subject `The April order` is neither an Actor nor an Organization, so no reviewed reference reaches the composer. Fixing the `not` boundary alone does not fix the unjustified `NONE` nor the missing subject reference.
4. **The proposition is a copular predicate adjective with no ordinary object.** The Event trigger head is `final`, an adjective with a `cop` dependent `is` and no `obj`/`iobj`/`obl` dependent. The Domain Core Assertion requires exactly one object entity or value, so `subject_value` alone does not settle how "is not final" is expressed. R19 pins a copular decomposition (§5, `REQ-ASS-02`).

### Corrected premises

1. **AHE-901-909 are no longer untouched evaluation cases.** R17 defined their expected answers and R18 executed both variants. They are development and regression cases. Independent validation requires a genuinely untouched held-out partition; R19 does not consume it.
2. **AHE-022 has two separate problems.** Semantic selection and the missing entity reference are distinct; the reference is a composition input, not a fix for selection.
3. **Polarity and modality already exist in the composer.** `DecontextualizedProposition` carries both, and R4 derives them from dependency evidence. R19 preserves and validates that data through the production path; it does not require selected fragments to supply them.
4. **`centralized_identity_resolution.py` is not a general entity resolver.** It links a vague activity mention to a later concrete mention through an existing reference or explicit supersession; it cannot manufacture `AHE-022`'s missing subject identity. The entity-reference provider is the Event-Entity Connection.
5. **No general Event-class role system.** R19 supports the two required roles for the supported frames and reuses the existing `DecontextualizationRoleKind`; it does not build a general Event-class role declaration.

### Accepted selection does not equal correct Assertions

The 50 Events reached accepted selection; that records accepted selections, not 50 correct, complete Assertions. R19 preserves those accepted-selection guarantees and measures composition separately. Closing the two development residuals advances the package contract; it does not replace the independent held-out validation requirement - a held-out run with zero boundary gaps and zero fabricated roles.

## 2. Terms

- **Residual Event**, **Reference selected set**, **Constituent Selection Task**, **Constituent Selection Answer**, and **Candidate label** keep the R15, R16, and R17 meanings.
- **Semantic policy** and **acceptance signal** keep the R17 meanings: eligibility, complete-selected-set, `NONE` justification, and the five signals.
- **Deterministic selector** means the model-free operation that derives each required role from the trigger-head dependents, reduces each role to its canonical boundary through the role-boundary policy, and selects one eligible Candidate per realized role; it produces a `ConstituentSelectionAnswer`.
- **Required role** means the span-carrying content role subject or object that the selector realizes and selects. Polarity and modality are composition signals the composer derives from trigger-head dependents; the selector does not select Candidates for them. Time and place are not R19 roles.
- **Canonical boundary** keeps the R17 meaning: the narrowest source-exact span containing the role's argument head and every token the role-boundary policy names as required content, and no token a different role requires. The selector derives the boundary from the role-boundary policy, never from a reviewed expected source range. A Candidate equal to the canonical boundary is not redundant because a larger Candidate contains it.
- **Argument head** means the unique trigger-head dependent whose dependency relation realizes the role (`nsubj`/`nsubj:pass` for subject; `obj`/`iobj` for object). A role realized by `conj` coordination has one argument head per conjunct, reached by walking each `conj` dependent of the first conjunct.
- **Role-boundary policy** means one reviewed, Event-independent rule set that names the required-content dependency relations and the content-optional dependency relations. The selector applies this one rule set to every role of every Event; it never consults a reviewed expected source range.
- **Required-content relation** means a dependency relation the role-boundary policy names as part of the role's required content.
- **Content-optional relation** means a dependency relation the role-boundary policy names as outside the role's required content.
- **Unsupported time/place content** means a trigger-head `obl` dependent that the Event expresses but that R19 cannot carry as a subject or object. It is never reported as an object boundary gap or an object role; the composition holds with the typed reason `unsupported_time_place`.
- **Unsupported coordination** means a role realized by a `conj` coordination whose conjuncts produce more than one content span for the role's single slot. The composer holds with the typed reason `unsupported_coordination` and emits no Assertion instead of dropping a conjunct.
- **Eligible Candidate** means one Candidate that supplies the role's canonical-boundary content for one argument head; selection is by reduction to the canonical boundary, never by longest span.
- **Entity-reference provider** means the `EventEntityReferenceProvider` Port. The Event-Entity Connection implements it from its reviewed accepted references and returns accepted `DecontextualizationEntityRef` records with source-exact, ordered, non-empty occurrences, plus reviewed exclusions that positively establish a span as outside the Actor/Organization kinds.
- **Subject value** means a source-exact subject fragment resolved to `subject_value` only on positive evidence — a reviewed exclusion naming the span as outside the Actor/Organization kinds. The absence of an entity reference alone never authorizes a value; an unresolved name such as `Sacks` stays unresolved.
- **Copular predicate-adjective proposition** means a proposition whose trigger head is an adjective with a `cop` dependent and no `obj`/`iobj`/`obl` dependent; its relation is the copula and its object value is the predicate adjective.
- **Completed composition** means the composer returns status `PROPOSITION` with subject, relation, object when present, polarity, modality, and attribution, and no hold reason.
- **Inspectable Assertion** means one Domain Core `Assertion` record — `status` `proposed`, `epistemic_scope` `source_report` — that rerenders the content triple with exact supporting source spans. It is emitted only as a sealed-report inspection payload: it is never persisted in the Ledger, never wrapped into a `ProposedChange`, and never passed to any submitter.
- **Composition readiness** keeps the R17 meaning: whether the selected set carries the entity references and the polarity, modality, and attribution inputs construction needs.
- **Untouched held-out partition** keeps the R1 meaning.

## 3. Primary flow

The coordinating use case lives in the Application Layer: `deterministic_residual_composition_completion.py`. It composes the deterministic selector, the `EventEntityReferenceProvider` Port, the deterministic composer, and the inspectable Assertion constructor. The Event-Entity Connection stage (`packages/pipelines/src/kotekomi_pipelines/event_entity_connection_stage_local.py`: `load_connection_gold_catalog`, `ConnectionGoldEntity` accepted occurrences, and `ConnectionGoldExcludedExpression` exclusions) implements the `EventEntityReferenceProvider` Port. The composer stays deterministic: it receives validated `DecontextualizationEntityRef` records as arguments and never calls the Port, the Gold, or any external service. R19 achieves closure through the R4 composition workflow — the Application Layer use case, the Pipeline entry point, and the thin runner — with ingestion integration still pending.

1. The Pipeline entry point (`packages/pipelines/src/kotekomi_pipelines/deterministic_residual_composition_completion.py`) binds the frozen R3-A inventory, the pinned Stanza dependency tokens, the trigger Gold, and the connection Gold by SHA-256, then calls the Application Layer use case.
2. The deterministic selector locates the trigger head and enumerates its direct dependents.
3. The deterministic selector assigns each required role to its argument head, reduces each role to its canonical boundary with the role-boundary policy (`nsubj`/`nsubj:pass` for subject; `obj`/`iobj` for object), and selects one Candidate per realized role, one per conjunct for coordination.
4. The deterministic selector returns one `ConstituentSelectionAnswer` per Event. The R17 evaluator scores the two residual answers `semantic_selection = met`.
5. The Application Layer use case calls the `EventEntityReferenceProvider` Port (implemented by the Event-Entity Connection) for the validated references and exclusions, then hands them to the composer. An accepted Actor or Organization occurrence resolves to a `DecontextualizationEntityRef`; a reviewed exclusion resolves the subject to a `subject_value`; neither leaves the subject as `subject_unavailable`.
6. The deterministic composer consumes the production selection, the pinned dependency tokens, and the validated references; it records an `advmod` `not` or `n't` token as `negated`, and it decomposes a copular predicate-adjective Event into the copula relation and the predicate-adjective object value.
7. The constructor rerenders each completed proposition as one inspectable `Assertion` (`status` `proposed`, `epistemic_scope` `source_report`, never persisted, never a `ProposedChange`) with exact supporting source spans.
8. The Pipeline entry point seals one report: per-Event selection signals, the composition result, the Assertion spans, and a fingerprint, with zero model executions, zero canonical writes, and zero ProposedChanges.

R19 is deterministic: no model execution, no canonical write, no ProposedChange.

## 4. Goals

- The two residuals close through the actual production path, not through posted expectations.
- Production-generated selections satisfy the reviewed semantic policy.
- Required entity references come from a declared, source-grounded provider.
- Composition preserves required arguments, polarity, modality, and attribution.
- The resulting Assertion is inspectable with exact supporting source spans.
- Ready regression cases keep their composed subject, object, polarity, modality, and attribution.
- No Event-ID special case, injected reference answer, or fabricated identity satisfies closure.

## 5. Requirements

### Selection mechanism
- REQ-SEL-01: The deterministic selector derives each required role from the trigger-head dependents only; it never reads a model answer and never substitutes the frozen Reference set. Coordination traversal of a `conj` descendant of one argument head is part of that role, not a separate role source.
- REQ-SEL-02: For each realized role the selector picks the unique argument head dependent, enumerates the Candidate pool constituents that contain the head token and exclude the trigger head token, and reduces them to the canonical boundary with the role-boundary policy. Selection is by this reduction, never by longest span.
- REQ-SEL-03: When two distinct constituents both cover the canonical boundary losslessly, the selector prefers the one whose span equals the boundary; when two different spans remain tie-equivalent, the role is unsupported and the selector reports a boundary gap instead of guessing.
- REQ-SEL-04: When one role is realized by a `conj` coordination, the role requires one Candidate per conjunct; each conjunct reduces to its own canonical boundary, and the selected set contains every conjunct constituent. Otherwise a role selects exactly one Candidate.
- REQ-SEL-05: An unsupported role — no Candidate covering the canonical boundary, or a non-coordination multi-head ambiguity — reports `boundary_coverage = gap` and blocks composition; it never fabricates a Candidate.
- REQ-SEL-06: The production selection is `{C1, C3}` for `AHE-022` and `{C3}` for `AHE-051`; each scores `semantic_selection = met`.
- REQ-SEL-07: The five R17 acceptance signals stay independent and unchanged.

### Canonical-boundary policy
- REQ-BND-01: The selector derives every canonical boundary from one reviewed, Event-independent role-boundary policy. It never reads a reviewed `expected_source_range` or `canonical_candidate_label` to produce a selection.
- REQ-BND-02: The role-boundary policy names these required-content relations: `det`; `nmod:poss` plus the possessive `case` dependent of that possessor; `amod`; `flat`; and `compound` whose dependent token has `part_of_speech` `PROPN`. This keeps the possessor `Amodei's` in `Amodei's decision`, the proper noun `April` in `The April order`, and the proper noun `Mira` in `Mira Chen`.
- REQ-BND-03: The role-boundary policy names these content-optional relations: `case` on any token other than a required possessor; `mark`; `acl`; `advmod`; `aux`; `cop`; `neg`; `punct`; `nmod` that is not `nmod:poss`; and `compound` whose dependent token is not `PROPN`. This removes the common-noun title `President` from `President Mira Chen`.
- REQ-BND-04: When a dependent of the argument head carries a dependency relation outside the required-content and content-optional lists, the role is unsupported and the selector reports a boundary gap instead of guessing.
- REQ-BND-05: When `conj` coordination realizes one role, the selector walks every `conj` dependent (and its `cc`) of the first conjunct and derives one canonical boundary per conjunct. Each conjunct selects one Candidate.

### Subject representation
- REQ-SUB-01: The Domain Core `Assertion` and `ProposedAssertion` records gain `subject_value`; one subject is an entity or a value, never both.
- REQ-SUB-02: The composer `DecontextualizedRole` subject carries `entity_ref` or `subject_value`, never both.
- REQ-SUB-03: A subject resolves to `subject_value` only on positive evidence from a reviewed exclusion naming that span as outside the Actor/Organization kinds; the absence of an entity reference alone never authorizes a value.
- REQ-SUB-04: `AHE-051`'s subject resolves to the `subject_value` `The April order` on a reviewed exclusion; the resolver never misclassifies it as an Actor or an Organization.
- REQ-SUB-05: An unresolved subject name with neither an accepted reference nor a reviewed exclusion (for example an Actor such as `Sacks` when no accepted Actor reference exists) holds with `subject_unavailable`; it is never converted into a value.

### Entity reference boundary
- REQ-ENT-01: The Application Layer defines the `EventEntityReferenceProvider` Port; the composer receives references only through this Port.
- REQ-ENT-02: The Event-Entity Connection implements the Port. The Adapter maps each `ConnectionGoldEntity` accepted occurrence to a `DecontextualizationEntityRef` and each `ConnectionGoldExcludedExpression` to a reviewed exclusion; every occurrence is source-exact, ordered, and non-empty.
- REQ-ENT-03: A missing reviewed reference blocks composition with `subject_unavailable`; the provider never fabricates a reference.
- REQ-ENT-04: The Application Layer use case — not the composer — calls the Port and passes the validated references into the composer; the composer performs no reference lookup itself.
- REQ-ENT-05: The reviewed exclusion that authorizes a `subject_value` names the span with a `non_entity_value` contextual kind. R19 extends `ConnectionGoldExcludedExpression` (or the Port's exclusion DTO) with that kind. One `subject_value` requires exactly one such reviewed exclusion.

### Composition
- REQ-CMP-01: The composer preserves subject, object when present, polarity, modality, and attribution through the production path.
- REQ-CMP-02: An `advmod` token with lowercase lemma `not` or `n't` records `negated`; the existing `neg` relation also records `negated`.
- REQ-CMP-03: The modal-lemma mapping producing `modality` is unchanged and validated.
- REQ-CMP-04: A copular predicate-adjective Event (trigger head with a `cop` dependent and no `obj`/`iobj`/`obl` dependent) composes the copula token as the relation and the predicate-adjective span as an `object_value`; nothing is invented.
- REQ-CMP-05: A trigger-head `obl` dependent that realizes time or place content the Event expresses, but that R19 cannot carry as a subject or object, causes the composer to hold with the typed reason `unsupported_time_place` and emit no Assertion. It is never reported as an object boundary gap, because time and place are not object roles.
- REQ-CMP-06: When one role (subject or object) is realized by a coordination whose conjuncts produce more than one content span for the role's single slot, the composer holds with the typed reason `unsupported_coordination` and emits no Assertion; it never drops a conjunct. Supporting multiple subjects or objects for one Event remains outside R19.

### Assertion
- REQ-ASS-01: The inspectable Assertion carries exact supporting source spans for subject, object, and relation.
- REQ-ASS-02: For `AHE-051` the inspectable Assertion is source-exact and non-invented: `subject_value` `The April order` (`[5, 20)`), `predicate` `is` (the copula, `[21, 23)`), `object_value` `final` (the predicate adjective, `[28, 33)`), and `qualifiers` carrying the polarity `negated` from the `advmod` `not` (`[24, 27)`).
- REQ-ASS-03: The constructor preserves polarity and modality on the inspectable Assertion.
- REQ-ASS-04: The inspectable output is a Domain Core `Assertion` (`status` `proposed`, `epistemic_scope` `source_report`), not a `ProposedAssertion` and not a `ProposedChange`; it is never persisted and never submitted.

### Regression and validation
- REQ-REG-01: The frozen R17 historical evaluation is reproducible against its frozen implementation revision, not against the changed composer. R19 neither edits the frozen R17 result files nor their checksums, and it does not re-run the R17 evaluator against the changed composer expecting the frozen signals. Frozen R17 file preservation is historical reproducibility, not regression protection for the changed code.
- REQ-REG-02: The changed-composer production result is a separate record from the frozen R17 historical evaluation and never overwrites it.
- REQ-REG-03: The untouched held-out partition is neither read nor consumed.
- REQ-REG-04: The new selector and composer run on `AHE-901` through `AHE-909` and produce the explicit per-Event expected outcomes in the regression table below.
- REQ-REG-05: The five ready cases `AHE-901`, `AHE-903`, `AHE-905`, `AHE-906`, and `AHE-907` compose as propositions with the same subject, object, polarity, modality, and attribution as the R17 current-composer probe.
- REQ-REG-06: R19 verifies, as a recorded observation and not as regression protection, that the frozen R17 evaluator scores the changed composer's `AHE-903` selected set `{C1, C4}` as `semantic_selection = unmet` (R17 expects `{C1, C2, C3, C4}`). The composed proposition still preserves the R17 content. R19 presents this as an intentional selection-policy difference, never as unchanged selection correctness.

| Event | R19 selector selected set | R19 composition outcome | Intentional divergence |
| --- | --- | --- | --- |
| AHE-901 | C1, C2 | proposition: subject `Mira`, object `Tomas`, `affirmed`, `actual`, `source_narrator` | none (ready) |
| AHE-902 | C1 (subject only) | held `unsupported_time_place` (unrepresented `obl` time/place content) | time and place are not R19 roles |
| AHE-903 | C1, C4 | proposition: subject `Mira`, object `the agreement`, `negated`, `hypothetical`, `source_narrator` | polarity and modality derived in composition, not selected; frozen R17 evaluator returns `semantic_selection = unmet` against `{C1, C2, C3, C4}` |
| AHE-904 | C1, C2, C3 | held `unsupported_coordination` (one subject slot, two subject conjuncts); no Assertion | multiple-subject support is outside R19 |
| AHE-905 | C3, C4 | proposition: subject `Tomas`, object `the agreement`, `targeted` attribution | none (ready) |
| AHE-906 | C4, C6 | proposition: subject `Mira Chen`, object `the agreement`, `source_narrator` | none (ready) |
| AHE-907 | C1, C2 | proposition: subject `Mira`, object `Mira`, `source_narrator` | none (ready) |
| AHE-908 | NONE | held `selection_empty` | none (stays not_ready) |
| AHE-909 | C1, C2 | held `subject_unavailable` | none (stays not_ready) |

## 6. Acceptance Criteria

- AC-R19-SEL-01: Tests prove the deterministic selector returns `{C1, C3}` for `AHE-022` and `{C3}` for `AHE-051`.
- AC-R19-SEL-02: Tests prove both production selections score `semantic_selection = met`.
- AC-R19-SEL-03: Tests prove the frozen Reference set is never substituted as the production answer.
- AC-R19-SEL-04: Tests prove the canonical-boundary reduction — not longest span — is what selects each Candidate, on both residuals and a constructed overlapping-candidate case where the longest span is not the canonical boundary.
- AC-R19-SEL-05: Tests prove tie and coordination handling: a coordination selects one Candidate per conjunct, and an unterminated tie or unsupported single-head ambiguity reports a boundary gap instead of guessing.
- AC-R19-BND-01: Tests prove the selector derives each canonical boundary from the role-boundary policy and never from a reviewed `expected_source_range` or `canonical_candidate_label`.
- AC-R19-BND-02: Tests prove the policy retains the required content and removes the optional content on `Amodei's decision`, `The April order`, and `President Mira Chen` exactly as REQ-BND-02 and REQ-BND-03 name.
- AC-R19-BND-03: Tests prove an argument-head dependent carrying an unlisted dependency relation reports a boundary gap instead of guessing.
- AC-R19-SUB-01: Tests prove `AHE-051`'s subject resolves to the `subject_value` `The April order` and never to an Actor or an Organization.
- AC-R19-SUB-02: Tests prove the Domain Core `Assertion` accepts exactly one subject entity or one subject value.
- AC-R19-SUB-03: Tests prove the absence of an entity reference alone never resolves a subject to a value, and an unresolved name (for example `Sacks` with no accepted Actor reference) holds with `subject_unavailable`.
- AC-R19-ENT-01: Tests prove an entity reference resolves only through the `EventEntityReferenceProvider` Port and never through an injected answer or a fabricated identity.
- AC-R19-ENT-02: Tests prove every resolved occurrence is source-exact, ordered, and non-empty; a missing reviewed reference holds with `subject_unavailable`.
- AC-R19-ENT-03: Tests prove the Application Layer use case calls the Port and passes validated references into the composer, and the composer performs no reference lookup itself.
- AC-R19-POL-01: Tests prove an `advmod` `not` token records `negated`; the `neg` relation still records `negated`.
- AC-R19-MOD-01: Tests prove modal lemmas map to their modality and no modal records `actual`.
- AC-R19-CMP-01: Tests prove both residuals complete composition with subject, relation, object when present, polarity, modality, and attribution, and no hold reason.
- AC-R19-CMP-02: Tests prove the copular predicate-adjective case composes the copula as the relation and the predicate adjective as the `object_value` without inventing content.
- AC-R19-CMP-03: Tests prove `AHE-904` holds with `unsupported_coordination`, emits no Assertion, and drops no conjunct.
- AC-R19-CMP-04: Tests prove `AHE-902` holds with `unsupported_time_place` and is never reported as an object boundary gap.
- AC-R19-ASS-01: Tests prove the inspectable Assertion carries exact supporting source spans.
- AC-R19-ASS-02: Tests prove the `AHE-051` Assertion is `subject_value` `The April order`, `predicate` `is`, `object_value` `final`, `qualifiers` polarity `negated`, with no invented subject, object, or predicate content.
- AC-R19-ASS-03: Tests prove the inspectable output is a `status` `proposed` / `epistemic_scope` `source_report` Domain Core `Assertion`, not a `ProposedAssertion` and not a `ProposedChange`, and it is never persisted or submitted.
- AC-R19-CLS-01: Tests prove `AHE-022` and `AHE-051` each complete selection, composition, and Assertion construction through the production path; a typed hold does not count as closure.
- AC-R19-REG-01: Tests prove the frozen R17 result files and their checksums are unmodified, and the frozen evaluation is reproducible against its frozen revision. Frozen R17 file preservation is historical reproducibility, not regression protection for the changed code.
- AC-R19-REG-02: Tests prove the new selector and composer produce, for each of `AHE-901` through `AHE-909`, the explicit selected set and composition outcome in the §5 regression table, including the intentional divergences it names.
- AC-R19-REG-03: Tests prove the five ready cases `AHE-901`, `AHE-903`, `AHE-905`, `AHE-906`, and `AHE-907` still compose as propositions with the same subject, object, polarity, modality, and attribution as the R17 current-composer probe, and that the changed-composer production result never overwrites the frozen record.
- AC-R19-REG-04: Tests prove the frozen R17 evaluator scores the changed composer's `AHE-903` selected set `{C1, C4}` as `semantic_selection = unmet`, while its composed proposition still matches the preserved content in the table.
- AC-R19-REP-01: Tests prove the report records zero model executions, zero canonical writes, and zero ProposedChanges, plus one fingerprint.
- AC-R19-HALT-01: Tests prove a selection, entity, or composition gap halts with a typed blocked or partial outcome instead of closing.
- AC-R19-ALL: Focused formatting, lint, typecheck, and tests pass.

## 7. Reference Implementations

- Composer and polarity/modality/attribution derivation: `packages/application/src/kotekomi_application/decontextualization_composition.py` (`build_decontextualized_proposition`, `DecontextualizedProposition`, `DecontextualizationRole`, `DecontextualizationRoleKind`, `_modality`). `DecontextualizationHoldReason` gains `unsupported_time_place` and `unsupported_coordination`.
- Deterministic selector (canonical-boundary reduction, tie, coordination, unsupported): new `packages/application/src/kotekomi_application/source_grounded_selection.py`.
- Entity-reference provider Port: `packages/application/src/kotekomi_application/event_entity_reference_provider.py`.
- Event-Entity Connection Adapter (implements the Port): `packages/pipelines/src/kotekomi_pipelines/event_entity_connection_stage_local.py` (`ConnectionGoldEntity`, `ConnectionGoldExcludedExpression`, `ConnectionGoldCatalog`, `load_connection_gold_catalog`).
- Coordinating Application Layer use case, inspectable Assertion constructor, and verifier: `packages/application/src/kotekomi_application/deterministic_residual_composition_completion.py`.
- Subject-value Domain Core contract: `packages/domain/src/kotekomi_domain/models.py` (`Assertion`, `ProposedAssertion`) and the generated `schemas/assertion.schema.json` and `schemas/proposed_assertion.schema.json`.
- Selection contract and evaluator: `packages/application/src/kotekomi_application/semantic_selection_contract.py`; policies and fixtures under `data/r17-semantic-selection-contract/`.
- Pipeline entry point: `packages/pipelines/src/kotekomi_pipelines/deterministic_residual_composition_completion.py`.
- Thin runner that invokes the Pipeline entry point: `scripts/run_deterministic_residual_composition_completion.py`.
- Tests: `packages/application/tests/test_deterministic_residual_composition_completion.py`.

## 8. Constraints and Halt Conditions

- R19 executes no model, writes no canonical state, and records no ProposedChange.
- R19 reads no held-out partition Gold and changes no selection-scoring rule and no reviewed-fixture evaluator.
- R19 does not edit the frozen R17 result files or their checksums. R17 reproducibility is bound to R17's frozen implementation revision; R19 records the changed-composer production result separately and never re-runs the R17 evaluator against the changed composer expecting the frozen signals.
- The composer remains deterministic and reference-free at its boundary: the Application Layer use case calls the `EventEntityReferenceProvider` Port and passes validated references into the composer; the composer never calls the Port.
- Halt when the deterministic selector produces a selection that fails the reviewed semantic policy.
- Halt when the canonical-boundary reduction is ambiguous (an unterminated tie or unsupported single-head ambiguity); report a boundary gap instead of guessing.
- Halt when one role's coordination produces more than one content span for the role's single slot; save the typed `unsupported_coordination` hold and drop no conjunct.
- Halt when a trigger-head `obl` dependent realizes time or place content; save the typed `unsupported_time_place` hold instead of reporting an object boundary gap.
- Halt when the `EventEntityReferenceProvider` returns no accepted reference for a required Actor or Organization subject and no reviewed exclusion; do not convert the unresolved subject into a value.
- Halt when a composed role changes authoritative source characters.
- Halt when the report records any model execution, canonical write, or ProposedChange.

## 9. Execution & Experimentation Directive

- Implement the deterministic selector, the `EventEntityReferenceProvider` Port and its Event-Entity Connection Adapter, the `subject_value` representation, the `advmod` `not` polarity fix, the inspectable Assertion constructor, the Application Layer use case, the Pipeline entry point, the thin runner, and the focused tests.
- Run the verifier over `AHE-022`, `AHE-051`, and the `AHE-901`-`AHE-909` regression cases, and check each case against the explicit expected outcomes in the §5 regression table.
- Record per-Event selection signals, the composition result, the Assertion spans, and the report fingerprint in the Run Record, separate from the frozen R17 historical evaluation.
- Report any residual that stays blocked or partial as a typed outcome and do not mark it closed.
- Commit the TDD, the implementation, and the run separately.

## 10. Run Record

R19 has not run.
