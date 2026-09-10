# TDD: Bounded Semantic Reference Resolution

- Status: Corrective reference-discovery integration implemented; canonical verification pending
- Deliverable ID: HSQ-4
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [HSQ-3 Complete Proposition Verification](2026-09-06-complete-proposition-verification.md)

## Context & Problem

HP-2 resolves explicit aliases and abbreviations.

It deliberately leaves semantic references such as `he`, `it`, and `the administration` unresolved.

Those references currently cause argument substitution or lost intelligence.

**CoreferenceObservation** means one model-proposed cluster of exact source spans.

**SemanticReferenceDecision** means KoteKomi's resolved, ambiguous, or unresolved result for one target span.

### Primary end-to-end flow

1. KoteKomi selects one unresolved source expression.
2. KoteKomi constructs a bounded same-paragraph context window.
3. a coreference Adapter proposes source-span clusters.
4. KoteKomi validates every model span without treating it as an authoritative boundary.
5. KoteKomi reconciles the target cluster with upstream, source-validated antecedent candidates.
6. KoteKomi records one SemanticReferenceDecision.

## Goals

- A reviewer can inspect bounded pronoun and nominal-reference decisions.
- Every resolved antecedent remains traceable to authoritative source characters.
- Ambiguous references remain unresolved.

## Requirements

### Application Layer

- BSR-APP-01: The Application Layer defines a CoreferenceProposer Port.
- BSR-APP-02: The request includes the target span and bounded same-paragraph context.
- BSR-APP-03: The Application Layer measures the window with the selected model tokenizer.
- BSR-APP-03A: The window adds nearest preceding sentences in order and stops before exceeding 1,024 input tokens.
- BSR-APP-04: The Application Layer validates every returned character span and preserves the complete model cluster as derived evidence.
- BSR-APP-04A: A model span can select only the best-overlapping upstream, source-validated antecedent candidate; a model boundary does not become the authoritative antecedent boundary.
- BSR-APP-05: A resolved antecedent candidate must precede the target and be classified upstream as a specific entity.
- BSR-APP-06: Repeated equal-literal candidates in one equivalence cluster identify one referent and select the nearest source candidate.
- BSR-APP-06A: Multiple distinct eligible source candidates in one target cluster produce `ambiguous`.
- BSR-APP-07: No valid antecedent produces `unresolved`.
- BSR-APP-08: KoteKomi discovers bounded pronoun and nominal reference markers directly from authoritative SourceSegment characters; reference eligibility does not depend on a named-entity proposer emitting the marker.
- BSR-APP-09: Deterministic marker observations cite their source-discovery trace rather than pretending to be a ModelRun.

### Adapter

- BSR-ADP-01: The evaluation runs pinned F-Coref on frozen source cases.
- BSR-ADP-02: F-Coref is the only production model in this TDD.
- BSR-ADP-03: The production Adapter uses pinned local resources.
- BSR-ADP-04: The Adapter returns CoreferenceObservations without deciding Domain meaning.
- BSR-ADP-05: Normal execution uses a correlated, deadline-bounded offline worker and exact pinned model files.

### Evaluation evidence

- BSR-EVL-01: `docs/hsq4-coreference-gold-v1.json` freezes exact authoritative text, target selectors, eligible antecedent-candidate selectors, and expected canonical antecedent selectors.
- BSR-EVL-02: `scripts/evaluate_hsq4_coreference.py` writes exact input, raw model output, validated spans, deterministic decisions, and aggregate metrics.
- BSR-EVL-03: A production-eligible result requires the pinned F-Coref identity, at least one resolved case, zero wrong resolutions, and no invalid source ranges.

## Proposed Architecture

```text
unresolved source span
         |
         v
bounded context window
         |
         v
CoreferenceProposer Adapter
         |
         v
source-span validation
         |
         v
SemanticReferenceDecision
```

## Key Interactions

```text
Application -> Adapter: exact text, target offsets, model limit
Adapter -> Application: exact proposed clusters
Application -> Domain Core: validated reference decision
```

## Data Model

A CoreferenceObservation stores the exact target, eligible source candidates, model identity, complete cluster spans, and raw-output evidence.

A SemanticReferenceDecision stores target, antecedents, status, and observation identity.

## Behavior & Domain Rules

- BSR-RUL-01: A CoreferenceObservation cannot create or merge an Entity.
- BSR-RUL-02: The resolver does not rewrite authoritative text.
- BSR-RUL-03: Non-commercial coreference models are research references, not repository Adapters.
- BSR-RUL-04: F-Coref ships only after it makes zero wrong held-out antecedent decisions.

## Acceptance Criteria

- AC-BSR-APP-01: `him` resolves to the visible preceding Trump mention in the adjudicated case.
- AC-BSR-APP-02: Two distinct eligible source candidates remain ambiguous.
- AC-BSR-APP-02A: Two preceding `Trump` mentions in one target cluster resolve to the nearest validated `Trump` candidate rather than becoming ambiguous.
- AC-BSR-APP-02B: A model span that includes an article, citation marker, or relative clause reconciles to the best-overlapping source-owned candidate boundary.
- AC-BSR-APP-03: An out-of-range or altered span fails boundary validation.
- AC-BSR-APP-04: `him` reaches semantic resolution even when neither GLiNER nor Qwen proposes it as a named-entity mention.
- AC-BSR-ADP-01: The bake-off reports precision, recall, latency, and exact span validity.
- AC-BSR-ADP-02: Missing or drifted local resources block before inference rather than downloading during ingestion.
- AC-BSR-RUL-01: A resolved reference adds no accepted Ledger record.

## Verification Result

The pinned F-Coref bake-off passed all production-eligibility gates on 2026-09-06.

- 9 of frozen cases resolved to their exact source-owned antecedent boundaries.
- Precision and recall were both `1.0`.
- No false positives, false negatives, invalid outputs, ambiguous results, unresolved results, or wrong resolutions were observed.
- The complete raw model clusters and deterministic reconciliation decisions remain available in the bake-off evidence.

## Reference Implementations

- Reference decisions: follow `packages/application/src/kotekomi_application/hybrid_document_references.py`.
- Managed resources: follow `packages/adapters/src/kotekomi_adapters/model_resources.py`.
- F-Coref API and character-offset contract: <https://github.com/shon-otmazgin/fastcoref>.
- F-Coref paper: <https://aclanthology.org/2022.aacl-demo.6/>.
