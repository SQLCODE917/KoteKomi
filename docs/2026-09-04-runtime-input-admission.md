# TDD: Runtime Input Admission

- **Status:** Accepted
- **Parent:** [Ingestion Architecture Review](2026-09-04-Ingestion-Architecture-Review.md)
- **Depends on:** [Deterministic Context Planning](2026-07-11-deterministic-context-planning.md), [Staged Model Extraction](2026-07-11-staged-model-extraction.md)

## 1. Context and problem

KoteKomi currently checks a `ContextManifest` with a whitespace-based estimate, then appends
task-local input and sends the larger request without another capacity decision. The LM Studio
Adapter stores the configured context limit but does not verify it against the loaded model or use
it to admit the complete request.

A local probe produced a ready manifest with a count of 38, appended 2,000 task-local words, and
sent a complete count of 2,039 through a profile limited to 512. The probe used a fake runtime, so
2,039 is not an exact Qwen token count. It proves that complete-request admission is absent.

LM Studio documents a three-part fit check: apply the loaded model's prompt template, tokenize the
formatted request with that model, and compare the count with `get_context_length()`.

## 2. User story

As a KoteKomi user, I want every model request checked against both my configured policy and the
capacity of the actually loaded model, so ingestion never silently sends an oversized task and I
can inspect why blocked model work did not run.

## 3. Goals

- Measure the complete request after task-local composition.
- Use the loaded model's tokenizer and prompt template for the final admission count.
- Verify the loaded runtime context length rather than trusting configuration alone.
- Preserve configured context, output reserve, and safety margin as Application policy.
- Block before transport when the complete request does not fit.
- Preserve an immutable, typed admission decision for every attempted model task.
- Preserve runtime-reported input usage as a distinct, non-authoritative accounting observation.

## 4. Non-goals and forbidden approaches

This TDD does not optimize source splitting, change prompts, tune model quality, pin Qwen weights,
or redesign recovery for other runtimes.

Forbidden:

- whitespace counts in the production LM Studio path;
- checking only the base `ContextManifest`;
- trusting configured context length as observed runtime capacity;
- trusting a model's theoretical maximum instead of the loaded instance;
- adding a fixed correction factor between SDK and HTTP counts;
- silently truncating source context, task-local material, or output reserve;
- invoking the model after a blocked admission;
- accepting output whose runtime input count disagrees with the admission;
- falling back to an estimated tokenizer when LM Studio inspection is unavailable.

## 5. Contract decisions

### 5.1 Two bounded records

`ContextManifest` remains the immutable record of selected authoritative context, prompt, schema,
and deterministic rendering.

`ModelInputAdmission` is the immutable record of the complete model request after task-local
composition and runtime-specific formatting.

The admission does not make model-formatted text authoritative source material.

### 5.2 Effective capacity

The Application Layer computes:

```text
effective_context_limit = min(configured_context_limit, loaded_context_limit)

required_capacity =
    formatted_input_token_count
    + reserved_output_tokens
    + safety_margin_tokens
```

An admission is `ready` only when `required_capacity <= effective_context_limit`.

An over-capacity admission is `context_budget_blocked` with reason
`complete_request_exceeds_context_budget`.

### 5.3 Responsibility boundary

The runtime Adapter reports facts:

- loaded model instance identity;
- loaded context length;
- tokenizer identity;
- prompt-template identity;
- prompt-template-formatted input digest;
- formatted input token count.

The Application Layer validates those facts and decides `ready` or `context_budget_blocked`.

The Pipeline composes the configured runtime and passes no production fallback tokenizer.

### 5.4 Attempt semantics

A blocked admission creates no external model invocation and no execution receipt. KoteKomi may
retain a terminal `ModelRun` attempt envelope with `input_blocked` status so existing extraction
lineage remains total, but that record must say `runtime_invoked=false` and reference the complete
admission. It is not evidence of a model response.

The admission belongs to the `ModelRun`, not the retry-stable `ExtractionTask`. Two attempts for
one deterministic task may observe different loaded model instances or capacities without
changing or conflicting with the immutable task record.

### 5.5 Admission count and runtime usage are different token domains

The loaded-model SDK's prompt-template-formatted count is the context-capacity authority. The
Responses API's `usage.input_tokens` is runtime-reported request accounting. KoteKomi preserves
both, but does not require them to be equal.

The bounded live probe against `qwen2.5-14b-instruct` demonstrated the distinction: the supported
SDK rendered the one-user-message request with the model's default system text and counted 36
formatted tokens, while `/v1/responses` reported 11 input tokens. A fixed offset would be invalid:
the difference depends on the loaded prompt template, API accounting, and runtime behavior. LM
Studio also has an open upstream report where repeated identical Responses input can report zero
input tokens.

Postflight integrity therefore binds the response to the exact logical-input digest, model
identity, generation parameters, and the Adapter's immediate pre-transport reinspection. Runtime
usage remains required and auditable, but it does not override or invalidate the admission.

## 6. Requirements

### Domain Core

- RIA-DOM-01: `ModelInputAdmissionStatus` contains `ready` and `context_budget_blocked`.
- RIA-DOM-02: `ModelInputAdmission` contains configured, loaded, and effective limits; formatted
  input count; output reserve; safety margin; required capacity; runtime, model-instance,
  tokenizer, and formatting identities; logical and formatted input digests; status; and reason.
- RIA-DOM-03: Domain validation recomputes effective capacity and required capacity.
- RIA-DOM-04: `ready` has no blocked reason and fits the effective limit.
- RIA-DOM-05: `context_budget_blocked` uses the canonical reason and exceeds the effective limit.
- RIA-DOM-06: A model execution attempt records the admission and whether transport was invoked.
- RIA-DOM-07: `input_blocked` permits no output artifact or execution receipt.

### Application Layer

- RIA-APP-01: The `ModelTaskRuntime` Port exposes a typed complete-input inspection operation.
- RIA-APP-02: The inspection request binds the configured model identity and exact logical input
  digest.
- RIA-APP-03: `run_bounded_extraction` composes task-local material before inspection.
- RIA-APP-04: The Application Layer creates and validates `ModelInputAdmission` from Adapter facts
  and `ContextManifest` policy.
- RIA-APP-05: A blocked admission persists the task and terminal attempt, calls no runtime
  generation operation, archives no output, and creates no `ProposedChange`.
- RIA-APP-06: A ready admission is included in the request passed to generation.
- RIA-APP-07: The generation Adapter must reject a request whose admission identity, logical input
  digest, model instance, or loaded capacity no longer matches.
- RIA-APP-08: The Application Layer validates response identity, generation settings, and the exact
  logical-input digest before parsing output.
- RIA-APP-09: The Application Layer preserves runtime-reported input usage separately from the
  admitted formatted-input count and does not infer context fit from runtime usage.
- RIA-APP-10: Extraction-stage diagnostics distinguish input blocking from runtime failure.

### LM Studio Adapter

- RIA-LMS-01: The Adapter uses the official LM Studio loaded-model API for prompt-template
  formatting, tokenization, and `get_context_length()`.
- RIA-LMS-02: It selects the configured loaded model and fails explicitly if selection is missing
  or ambiguous.
- RIA-LMS-03: It reports no tool-native SDK value across the Application boundary.
- RIA-LMS-04: It parses actual `usage.input_tokens` and `usage.output_tokens` from Responses
  results as runtime-accounting observations.
- RIA-LMS-05: It does not replace a failed inspection with whitespace estimation.
- RIA-LMS-06: A conformance test preserves both SDK preflight count and Responses usage for the
  same one-user-message request without requiring cross-domain equality.

### Pipeline

- RIA-PIPE-01: Production hybrid ingestion uses the configured runtime's exact tokenizer and input
  inspector.
- RIA-PIPE-02: Fixture ingestion uses an explicitly named deterministic fixture tokenizer and
  inspector.
- RIA-PIPE-03: Runtime readiness exposes configured, loaded, and effective context limits when
  inspection is available.

## 7. Proposed interaction

```text
ContextManifest + task-local bytes
  -> complete logical request
  -> LM Studio Adapter applies loaded prompt template
  -> LM Studio Adapter tokenizes formatted request
  -> LM Studio Adapter reads loaded context length
  -> Application constructs ModelInputAdmission
     -> blocked: persist and stop before generation
     -> ready: invoke exact request
  -> Adapter returns separately labelled runtime usage
  -> Application verifies response identity and exact logical-input digest
  -> parse and validate output
```

## 8. Acceptance criteria

- AC-RIA-01: The documented 512-limit regression creates `context_budget_blocked`, invokes the
  runtime zero times, archives no output, and creates no proposal.
- AC-RIA-02: Tests cover exact fit and one token over the effective limit.
- AC-RIA-03: Tests prove task-local material alone can change a ready ContextManifest into a
  blocked complete request.
- AC-RIA-04: Tests prove the lower of configured and loaded limits wins in both directions.
- AC-RIA-05: Tests prove reserved output and safety margin participate in admission.
- AC-RIA-06: Adapter tests prove punctuation, Unicode, and no-whitespace input use runtime tokens,
  not whitespace words.
- AC-RIA-07: Adapter tests prove prompt-template overhead is included.
- AC-RIA-08: In-budget execution sends byte-identical logical input to the existing Responses
  endpoint.
- AC-RIA-09: Unequal admitted-formatted and runtime-reported input counts remain separately
  auditable and do not invalidate an otherwise correctly bound response.
- AC-RIA-10: SQLite restart reloads blocked and ready admission evidence without changing it.
- AC-RIA-11: Missing LM Studio inspection fails closed without generation.
- AC-RIA-12: Formatting, lint, type checking, Domain, Application, Adapter, and focused Pipeline
  tests pass.

## 9. Verification

Run focused deterministic checks for Domain validation, the bounded-extraction regression, SQLite
persistence, LM Studio mapping, and hybrid Pipeline composition.

Run one bounded live LM Studio conformance probe with minimal output to preserve preflight count
and `usage.input_tokens` as distinct observations. This is not a PDF ingestion. If that probe is
delegated under the long-running-operation policy, retain its exact command and result.

The next planned document ingestion supplies the full production-path validation. This TDD does
not require a separate long canonical ingestion.

## 10. Compatibility and supersession

This TDD refines Context Planning requirements 5 and 12 through 14: a ContextManifest count alone
is insufficient after task-local composition. It refines Staged Model Extraction so a preflight
blocked attempt is not described as an external model invocation.

Historical ModelRuns remain read-only evidence. New attempts use the Runtime Input Admission
contract.

## 11. References

- [LM Studio: Get Context Length](https://lmstudio.ai/docs/python/model-info/get-context-length)
- [LM Studio: Tokenization](https://lmstudio.ai/docs/python/tokenization)
- [LM Studio: Python project setup](https://lmstudio.ai/docs/python/getting-started/project-setup)
- [LM Studio REST API comparison](https://lmstudio.ai/docs/developer/rest)
- [LM Studio issue: repeated Responses input can report zero input tokens](https://github.com/lmstudio-ai/lms/issues/553)

## 12. Halt conditions

Halt and revise if the loaded instance cannot be identified, if exact SDK inspection requires
copying tool-native model objects into the Application Layer, or if the Adapter cannot preserve
Responses usage separately from admission evidence.
