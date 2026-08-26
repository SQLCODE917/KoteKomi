# TDD: Paragraph Hypothesis Literal Output Hardening

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1.1
- Depends on: [PHP-1 Bounded Paragraph Hypothesis MVP](2026-08-26-paragraph-hypothesis-mvp.md)
- Evaluation corpus: [CIR Evaluation Annotation Packet](2026-08-26-cir-evaluation-annotation-packet.md)

## 1. Context & Problem

PHP-1 reads one authoritative Paragraph and proposes direct Organization relationships.

PHP-1 requires a claim to cite a source-segment label such as `s1`.

The PHP-1 v1 renderer displays `[s1]`.

The PHP-1 v1 prompt shows `<sN>` in its claim example.

The local model emitted literal labels such as `<s1>` for 23 packet rows.

The Application Layer correctly rejected those rows because `<s1>` is not `s1`.

PHP-1 also rejected batches that contained more than eight claims or mixed claims with an abstention.

The 50-row packet remains a human-review corpus.

It does not define a release-quality threshold.

### Terms

**Literal source-segment label** means the exact `sN` token that identifies one SourceSegment.

**Source order** means increasing SourceSegment label number.

**Packet diagnostic** means a local run over every row in the CIR Evaluation Annotation Packet.

### Primary end-to-end flow

1. ContextPlanner renders each SourceSegment with its literal source-segment label and a delimiter before the next label.
2. The Pipeline sends the v3 prompt and one authoritative Paragraph to the ModelTaskRuntime.
3. The ModelTaskRuntime returns a bounded text batch that uses literal source-segment labels.
4. The Application Layer validates the unchanged PHP-1 response contract.
5. The Application Layer writes verified pending ProposedChanges or records a visible ModelRun outcome.
6. The packet diagnostic records every local outcome without creating a release gate.

## 2. Goals

- A model sees one spelling for each source-segment label.
- A model receives clear instructions for exact Organization mention copying.
- A model receives an explicit bounded selection rule for high-cardinality Paragraphs.
- An operator can replay all 50 packet rows and inspect every raw outcome.
- PHP-1 preserves strict rejection for malformed and ungrounded model output.

## 3. Requirements

### ContextPlanner

- PHP11-CONTEXT-01: ContextPlanner renders each PHP-1 SourceSegment as `SOURCE SEGMENT: sN` followed by exact source text.
- PHP11-CONTEXT-02: ContextPlanner keeps `paragraph_segment_v1` because SourceSegment boundaries and offsets do not change.
- PHP11-CONTEXT-03: ContextPlanner records `paragraph_hypothesis_context_v3` in each v3 ContextManifest.

### Pipeline prompt

- PHP11-PROMPT-01: The Pipeline pins `paragraph_hypothesis_mvp_v3` and its prompt digest.
- PHP11-PROMPT-02: The v3 prompt shows `s1` as a literal claim label.
- PHP11-PROMPT-03: The v3 prompt forbids punctuation around a literal source-segment label.
- PHP11-PROMPT-04: The v3 prompt requires character-for-character Organization mentions from the cited SourceSegment.
- PHP11-PROMPT-05: The v3 prompt treats named companies, government bodies, institutes, universities, consortia, networks, and international bodies as organizations for this bounded task.
- PHP11-PROMPT-06: The v3 prompt instructs the model to return the first eight eligible claims in source order.
- PHP11-PROMPT-07: The v3 prompt instructs the model to return an abstention only when it returns no claim.

### Application Layer

- PHP11-VALIDATE-01: The Application Layer keeps `paragraph_hypothesis_text_v1` unchanged.
- PHP11-VALIDATE-02: The Application Layer rejects `<s1>` because it is not the literal label `s1`.
- PHP11-VALIDATE-03: The Application Layer rejects a batch with more than eight claims.
- PHP11-VALIDATE-04: The Application Layer rejects a batch that mixes one or more claims with an abstention.
- PHP11-VALIDATE-05: The Application Layer creates no ProposedChange from an invalid batch.
- PHP11-VALIDATE-06: Two distinct valid claims that cite one SourceSegment reuse one EvidenceTarget.

### Packet diagnostic

- PHP11-DIAG-01: The packet diagnostic reads all rows from the CIR Evaluation Annotation Packet.
- PHP11-DIAG-02: The packet diagnostic rejects a packet that does not define exactly 50 unique case IDs.
- PHP11-DIAG-03: The packet diagnostic uses isolated Ledger and Archive paths.
- PHP11-DIAG-04: The packet diagnostic records source Paragraph text, raw model output, ModelRun status, validation error, execution diagnostics, and ProposedChange IDs.
- PHP11-DIAG-05: The packet diagnostic writes progress events to standard error.
- PHP11-DIAG-06: The packet diagnostic writes one final JSON object to standard output.
- PHP11-DIAG-07: The packet diagnostic writes its complete result to an explicit output path when the operator supplies `--output`.
- PHP11-DIAG-08: The packet diagnostic reports `fixture_missing` and `selection_missing` explicitly.
- PHP11-DIAG-09: The packet diagnostic records outcomes without setting a quality threshold or a CI gate.

## 4. Proposed Architecture

```text
ContextPlanner
    -> v3 ContextManifest
    -> ModelTaskRuntime
    -> PHP-1 validator
    -> ModelRun and ProposedChanges
    -> packet diagnostic result
```

ContextPlanner owns source-segment rendering.

The Pipeline owns prompt selection.

The Application Layer owns output validation and pending record creation.

The packet diagnostic owns local replay and result reporting.

## 5. Key Interactions

```text
Operator       Packet diagnostic     Pipeline path       Application Layer
   |                   |                   |                    |
   | run packet        |                   |                    |
   |------------------>| build context     |                    |
   |                   |------------------>| invoke model       |
   |                   |                   |------------------->|
   |                   |                   | raw batch          |
   |                   |                   |<-------------------|
   |                   | record outcome    |                    |
   |                   |<---------------------------------------|
   | final JSON        |                   |                    |
   |<------------------|                   |                    |
```

## 6. Data Model

PHP-1 keeps the existing SourceSegment, ContextManifest, ModelRun, EvidenceTarget, and ProposedChange records.

The v3 ContextManifest stores the v3 prompt bytes, prompt digest, and renderer version.

The packet diagnostic result is a local JSON record.

The packet diagnostic result does not create accepted Ledger records.

## 7. APIs / Interfaces

The v2 model response keeps the existing PHP-1 text contract.

```text
claim: s1 | <organization subject> | <relation label> | <organization object>
```

The packet diagnostic exposes this command.

```text
uv run python scripts/verify_php1_packet.py --config PATH --output PATH
```

## 8. Behavior & Domain Rules

The Pipeline records each v3 prompt digest in the ContextManifest and ModelRun.

The Application Layer does not repair bracketed labels.

The Application Layer does not accept a partial batch.

The packet diagnostic retains raw model output in its explicit local result file.

The packet diagnostic deletes its isolated Ledger and Archive after it writes the result file.

## 9. Acceptance Criteria

- AC-PHP11-01: ContextPlanner tests prove v3 ContextManifest text uses `SOURCE SEGMENT: s1`, separates adjacent labels, and preserves SourceSegment reconstruction.
- AC-PHP11-02: Application tests prove `s1` creates a verified pending batch.
- AC-PHP11-03: Application tests prove `<s1>` creates an `invalid_output` ModelRun and no ProposedChange.
- AC-PHP11-04: Application tests prove over-eight and mixed batches remain invalid.
- AC-PHP11-04A: Application tests prove valid distinct claims from one SourceSegment share one EvidenceTarget.
- AC-PHP11-05: Pipeline tests prove automatic extraction pins the v3 prompt and v3 renderer.
- AC-PHP11-06: Diagnostic tests prove the packet parser loads exactly 50 unique rows.
- AC-PHP11-07: The local packet diagnostic records all 50 rows without a silent skip.
- AC-PHP11-08: Formatting, lint, type, Application, Adapter, and Pipeline checks pass.

## 10. Reference Implementations

- Context rendering: `packages/application/src/kotekomi_application/context_planning.py`.
- Batch validation: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Automatic extraction: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Local diagnostic output: `scripts/verify_php1_diagnostic.py`.

## 11. Constraints and Halt Conditions

PHP-1.1 does not add Organization types, Actor types, Event types, Place types, literal objects, predicate vocabulary, retries, or output repair.

PHP-1.1 does not make the packet a CI gate or a release threshold.

PHP-1.1 stops after the v3 packet diagnostic produces replayable outcomes for all 50 rows.
