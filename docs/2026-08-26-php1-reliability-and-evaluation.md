# TDD: PHP-1 Reliability and Evaluation

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.8
- Depends on: PHP-1.7

## 1. Context & Problem

PHP-1 sends one source sentence to a local model.
The authoritative PDF text can contain repeated layout whitespace.
The model can collapse that whitespace while retaining the same words.
The current literal validator then rejects an otherwise source-grounded hypothesis.
The current annotation packet also evaluates whole Paragraphs while PHP-1 executes one Source segment.

### Terms

**Source copy view** means a derived text view that replaces each non-empty whitespace run with one ASCII space.

**Segment evaluation** means one expected PHP-1 result for one Source segment.

### Primary end-to-end flow

1. The ContextPlanner derives one authoritative Source segment.
2. The Application Layer derives its Source copy view.
3. The ModelTaskRuntime receives the Source copy view and a pinned prompt.
4. The Application Layer maps each accepted source mention through the Source copy view.
5. The Application Layer creates EvidenceTargets only from the authoritative Source segment.
6. The diagnostic reports legacy paragraph results and PHP-1 segment results.

## 2. Goals

- A layout-whitespace difference does not reject an otherwise exact source mention.
- Every accepted hypothesis remains traceable to authoritative text and offsets.
- Operators can distinguish PHP-1 quality from out-of-scope packet expectations.
- Every PHP-1 replay records the model generation settings that the Adapter applied.

## 3. Requirements

### Source copy view

- PHP18-COPY-01: The Application Layer derives `paragraph_segment_v3` from the authoritative Source segment.
- PHP18-COPY-02: The Source copy view replaces each whitespace run with one ASCII space.
- PHP18-COPY-03: The Source copy view preserves every non-whitespace code point and source order.
- PHP18-COPY-04: The Application Layer validates PHP-1 subject and object text against the Source copy view.
- PHP18-COPY-05: The Application Layer creates each EvidenceTarget from the unchanged authoritative Source segment.

### Model execution

- PHP18-RUNTIME-01: The Pipeline pins `max_output_tokens`, `temperature`, and `seed` in each PHP-1 ModelExecutionSpec.
- PHP18-RUNTIME-02: The LM Studio Adapter sends every declared supported generation parameter.
- PHP18-RUNTIME-03: The LM Studio Adapter rejects an unsupported generation parameter before it calls LM Studio.

### Prompt and verifier

- PHP18-PROMPT-01: The Pipeline pins a versioned PHP-1 prompt.
- PHP18-PROMPT-02: The prompt requires literal named organization mentions from the Source copy view.
- PHP18-PROMPT-03: The prompt directs the model to abstain for pronouns, generic descriptions, and co-participants without an explicit bilateral relation.
- PHP18-PROMPT-04: The verifier rejects a hypothesis whose subject or object is a pronoun or generic description.

### Evaluation

- PHP18-EVAL-01: The existing 50-row report remains a legacy paragraph report.
- PHP18-EVAL-02: The diagnostic writes a separate PHP-1 segment report.
- PHP18-EVAL-03: The segment report identifies one of `in_scope`, `needs_coreference`, `needs_multi_segment`, or `out_of_scope` for every assessed expectation.
- PHP18-EVAL-04: The segment report never counts a relation from another segment as a match.

## 4. Proposed Architecture

```text
Authoritative Source segment
    -> Source copy view
    -> ModelTaskRuntime
    -> PHP-1 hypothesis
    -> Source copy validation
    -> authoritative EvidenceTarget
```

The Application Layer derives and validates the Source copy view.
The Pipeline pins prompts and generation settings.
The LM Studio Adapter translates declared generation settings.
The diagnostic evaluates PHP-1 only at Source-segment scope.

## 5. Key Interactions

```text
Pipeline     Application Layer     LM Studio       Ledger
   |                 |                 |             |
   | Source copy view|                 |             |
   |---------------->| task + settings |             |
   |                 |---------------->|             |
   |                 | raw hypothesis  |             |
   |                 |<----------------|             |
   |                 | validate        |             |
   |                 |------------------------------>|
```

## 6. Data Model

The authoritative DocumentRepresentationBundle remains unchanged.
The Source copy view is derived state inside the ContextManifest rendering policy.
The ContextManifest records `paragraph_segment_v3`.
The existing ModelRun records the generation parameter digest.
The diagnostic report is disposable local output.

## 7. APIs / Interfaces

The PHP-1 text response remains the existing claim-or-abstain contract.
The LM Studio Adapter accepts `max_output_tokens`, `temperature`, and `seed` execution settings.

## 8. Behavior & Domain Rules

The Source copy view does not become source evidence.
The Application Layer does not mutate authoritative text.
The Application Layer does not create a pending ProposedChange from a rejected verifier result.
PHP-1 does not resolve pronouns or generic descriptions.
PHP-3 will add bounded same-paragraph antecedent resolution.
PHP-3 will provide nearest preceding sentences first and stop at 1,024 input tokens.

## 9. Acceptance Criteria

- AC-PHP18-01: Application tests prove the Source copy view preserves non-whitespace characters and validates collapsed layout whitespace.
- AC-PHP18-02: Application tests prove EvidenceTargets retain original authoritative Source-segment text.
- AC-PHP18-03: Adapter tests prove LM Studio receives all supported declared settings and rejects unsupported settings.
- AC-PHP18-04: Pipeline tests prove PHP-1 pins a versioned prompt and deterministic generation settings.
- AC-PHP18-05: Application tests prove the verifier rejects pronoun and generic-description hypotheses.
- AC-PHP18-06: Diagnostic tests prove legacy and segment reports remain distinct.
- AC-PHP18-07: The local 50-row replay writes both reports.

## 10. Reference Implementations

- Source segmentation: `packages/application/src/kotekomi_application/context_planning.py`.
- PHP-1 validation: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- LM Studio boundary: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`.
- Packet diagnostic: `scripts/verify_php1_packet.py`.

## 11. Constraints and Halt Conditions

PHP-1 does not add coreference, Entity resolution, Event extraction, or ontology types.
PHP-1 does not alter the eight-claim limit.
PHP-1 retains the 50-row report as a non-gating diagnostic.

H1 evaluated `paragraph_hypothesis_segment_v6`.

H1 did not accept V6 as the production prompt.

The Pipeline continues to use `paragraph_hypothesis_segment_v3`.
