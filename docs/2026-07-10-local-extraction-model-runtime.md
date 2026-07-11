# Local Extraction Model Runtime

## 1. Context & Problem

KoteKomi currently proposes Domain records through a fixture-backed `ModelRuntime` Adapter.
The production Pipeline cannot extract proposals from a new Document.
This TDD adds local extraction through operator-owned llama-server and Ollama processes.

## 2. Goals

- Use llama-server on the M5 Mac as the default extraction runtime.
- Use Ollama on WSL/Ubuntu with an RTX 4090 as an optional extraction runtime.
- Return the same validated Application Layer DTOs from both Adapters.
- Preserve ProposedChange review as the only route from model output to accepted Ledger state.
- Give humans and agents a read-only runtime readiness command.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not start or stop either model server.
- This TDD does not download or update models.
- This TDD does not add Document chunking, embeddings, or entity reconciliation.
- This TDD does not add automatic retries, cloud fallback, or model routing.
- This TDD does not change accepted Domain record shapes or the Ledger schema.

Forbidden approaches:

- An Adapter must not return unvalidated tool-native JSON.
- An Adapter must not repair, drop, coerce, or skip an invalid proposal.
- A Pipeline must not write model output directly as accepted state.
- A failed proposal batch must not create partial ProposedChange or ProvenanceActivity records.
- KoteKomi must not infer runtime selection from host hardware.

## 4. Requirements

- The Application Layer must define the complete model proposal batch boundary contract.
- The contract must generate the JSON schema sent to each runtime.
- The contract must bind each supported `record_type` to its Domain Core record shape.
- The supported record types must remain Actor, Organization, Event, EvidenceSpan, Assertion, Relationship, Outcome, and ArgumentEdge.
- Both Adapters must request non-streaming schema-constrained JSON at temperature zero.
- Both Adapters must include Source ID, Document ID, Document text, and the extraction prompt in each request.
- Every proposal must identify the input Source and Document.
- Every proposal must contain exact evidence text present in the input Document.
- `prompt_id` must include a SHA-256 digest of the exact prompt text.
- `model_name` must identify the configured Adapter and model.
- The default runtime profile must use llama-server at `http://127.0.0.1:8080/v1`.
- The optional WSL profile must use Ollama at `http://127.0.0.1:11434`.
- Fixture execution must require explicit fixture runtime selection.
- `kotekomi model status --format json` must expose structured readiness state.
- Pipeline command plans must contain resolved runtime arguments.

## 5. Invariants

- ModelRuntime remains an Application Layer Port.
- Adapters depend inward on Application Layer DTOs and Domain Core records.
- Model output creates only pending ProposedChange records.
- Invalid model output creates no Ledger state.
- Accepted Ledger records still require explicit review and reference validation.
- Runtime readiness state is derived and never becomes canonical state.
- The Ledger and Archive remain the only canonical stores.

## 6. Proposed Architecture

The Pipeline selects a configured Adapter and composes the existing proposal use case.
The Application Layer owns the proposal batch DTO, schema, validation, and transaction intent.
Each Adapter translates one server API into the shared proposal batch DTO.
The external server owns model loading and hardware acceleration.

```text
+------------------+       +----------------------+       +-------------------+
| Pipeline         | ----> | Application Layer    | <---- | Domain Core       |
| config and CLI   |       | ModelRuntime Port    |       | record contracts  |
+--------+---------+       +----------+-----------+       +-------------------+
         |                            ^
         |                            |
         v                            |
+------------------+       +----------+-----------+
| Runtime Adapter  | ----> | Operator-owned       |
| llama or Ollama  |       | local model server   |
+------------------+       +----------------------+
```

## 7. Key Interactions

### Extract Proposals

```text
User -> Pipeline: source propose-assertions
Pipeline -> Runtime Adapter: configure endpoint, model, and prompt
Application Layer -> Runtime Adapter: propose Assertions from Document text
Runtime Adapter -> Model Server: schema-constrained completion
Runtime Adapter -> Application Layer: validated ModelProposal batch
Application Layer -> Ledger: pending ProposedChanges and ProvenanceActivity
```

### Reject Invalid Output

```text
Model Server -> Runtime Adapter: malformed or invalid response
Runtime Adapter -> Application Layer DTO: parse and validate
Application Layer DTO -> Runtime Adapter: exact validation error
Runtime Adapter -> Pipeline: ModelOutputValidationError
Pipeline -> Ledger: rollback transaction
```

### Check Runtime

```text
Agent -> Pipeline: model status --format json
Pipeline -> Runtime Adapter: check readiness
Runtime Adapter -> Model Server: model inventory and schema probe
Runtime Adapter -> Pipeline: ModelRuntimeStatus
Pipeline -> Agent: structured JSON
```

## 8. Data Model

`ModelProposalBatch` contains an ordered tuple of validated ModelProposal records.

`ModelProposalEvidence` contains:

```text
- selector_type = exact_text
- exact_text
- source_id
- document_id
```

`ModelRuntimeStatus` contains:

```text
- adapter
- endpoint
- model
- reachable
- model_available
- model_state
- idle_slots
- total_slots
- ready
- error_code
- error_message
```

`ModelExecutionConfig` contains runtime-only settings:

```text
- adapter
- endpoint
- model
- timeout_seconds
- context_tokens
- max_output_tokens
```

## 9. APIs / Interfaces

The Application Layer adds a `ModelRuntimeReadiness` Port.

The Application Layer adds proposal batch parsing and JSON schema functions.

The Pipeline adds:

```text
kotekomi model status
kotekomi model status --format json
```

The proposal and Pipeline planning commands accept:

```text
--model-runtime llama_server|ollama|fixture
--model-endpoint <url>
--model-name <name>
--model-timeout-seconds <seconds>
--model-context-tokens <count>
--model-max-output-tokens <count>
--model-output-fixture <path>
```

The TOML configuration adds `runtime_profile` and `[runtime_profiles.<name>]` tables.

The Pipeline resolves the selected profile into the shared `ModelExecutionConfig`.

The existing `[model_runtime]` table can override resolved profile fields.

## 10. Behavior & Domain Rules

The default profile uses:

```toml
[model_runtime]
adapter = "llama_server"
endpoint = "http://127.0.0.1:8080/v1"
model = "qwen3-14b-q4_k_m"
timeout_seconds = 300
context_tokens = 32768
max_output_tokens = 8192
```

The optional WSL profile uses:

```toml
[model_runtime]
adapter = "ollama"
endpoint = "http://127.0.0.1:11434"
model = "qwen3:30b-a3b-instruct-2507-q4_K_M"
timeout_seconds = 300
context_tokens = 16384
max_output_tokens = 8192
```

Configuration and CLI flags select the runtime explicitly.

`macbook` is the default profile.

`wsl-4090` selects the Ollama Adapter on the configured WSL endpoint.

`--runtime-profile` selects a named profile.
CLI flags override TOML values.
The fixture runtime requires `--model-output-fixture`.
Non-fixture runtimes reject `--model-output-fixture`.

The Adapter validates the server envelope before reading completion content.
The Adapter parses completion content through `ModelProposalBatch`.
The Application Layer validates all proposal references before its first Ledger write.
An exact evidence mismatch fails the complete batch.
An empty valid proposal batch records a completed model run with no ProposedChanges.

`model status` performs only passive inventory and occupancy checks.
The command does not mutate the Ledger, Archive, or model server state.
An unavailable service, absent model, loading model, sleeping model, or busy slot returns `ready = false`.

The Mac runtime uses the managed llama-server defined in
`docs/2026-07-10-managed-llama-server.md`.

## 11. Acceptance Criteria

- Application tests prove the proposal batch schema covers every supported record type.
- Application tests prove unsupported record types fail.
- Application tests prove evidence text must occur in the Document.
- Application tests prove one invalid proposal prevents all Ledger writes.
- Adapter tests prove llama-server request and response translation.
- Adapter tests prove Ollama request and response translation.
- Adapter tests prove exact failures for unreachable, missing-model, HTTP, envelope, and output errors.
- Adapter tests prove both readiness checks return structured status.
- Pipeline tests prove the Mac profile is the default.
- Pipeline tests prove the WSL TOML profile selects Ollama.
- Pipeline tests prove fixture mode remains deterministic and explicit.
- Pipeline tests prove command plans contain resolved runtime arguments.
- Optional live checks can exercise each operator-owned server.
- Ruff, Pyright, and the full test suite pass.

## 12. Cross-Cutting Concerns

The Adapters use bounded HTTP timeouts.
Errors include the Adapter, endpoint, model, and exact failure category.
Errors must not include the complete Document or model response.
The default test suite performs no network requests.

## 13. Reference Implementations

- `packages/adapters/src/kotekomi_adapters/fixture_model_runtime.py`
- `packages/application/src/kotekomi_application/assertion_proposal.py`
- `packages/application/src/kotekomi_application/model_proposal_validation.py`
- [llama-server HTTP API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama hardware support](https://docs.ollama.com/gpu)

## 14. Alternatives Considered

- Use Ollama on both targets: rejected because the Mac already uses llama-server.
- Use llama-server on both targets: rejected because WSL already uses Ollama.
- Manage server processes in KoteKomi: rejected because Pipelines invoke external capabilities but do not own services.
- Accept plain JSON mode: rejected because both selected servers expose schema-constrained output.
- Retry invalid output automatically: rejected because the first slice must expose invalid model behavior directly.

## 15. Halt Conditions

- Halt if either Adapter requires tool-specific types in the Application Layer.
- Halt if structured output cannot express the current supported proposal union.
- Halt if runtime failure can leave partial ProposedChange records.
- Halt if the default test suite requires a running local model server.
