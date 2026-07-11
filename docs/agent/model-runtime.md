# Model Runtime Rules

## Purpose

Local models propose structure and draft text.

Local models do not own canonical state.

## Runtime Targets

Support macOS on Apple Silicon.

Support WSL/Ubuntu with NVIDIA GPU.

Initial runtime Adapters:

- llama-server on macOS Apple Silicon through `LlamaServerModelRuntime`
- Ollama on WSL/Ubuntu NVIDIA through `OllamaModelRuntime`

## Runtime Profiles

Pipelines select an explicit named runtime profile from configuration. They do
not infer the operating system, GPU, server, or installed model.

| Profile | Adapter | Default model | Context window |
|---|---|---|---|
| `macbook` | llama-server | `Qwen/Qwen3-14B-GGUF:Q4_K_M` | 16,384 |
| `wsl-4090` | Ollama | `qwen3:30b-a3b-instruct-2507-q4_K_M` | 16,384 |

`macbook` is the default. Select the workstation profile with
`kotekomi source propose-assertions --runtime-profile wsl-4090 ...`.
The Pipeline resolves a profile into `ModelRuntimeConfig` before it constructs an Adapter.
A fixture-backed runtime is only an explicit test override; it is not a runtime fallback.

Later runtime Adapters:

- MLX-backed Adapter
- vLLM Adapter
- cloud LLM Adapter

## Model Roles

Use separate model roles.

| Role | Responsibility |
|---|---|
| embedding model | create vectors for Document chunks |
| extraction model | propose Assertions and EvidenceTargets |
| reconciliation model | propose entity matches |
| synthesis model | draft Briefings and analytic summaries |
| reranker model | rank retrieved evidence |

## Model Output Rules

Model output creates ProposedChange records.

Model output does not create accepted Assertions directly.

Prompt output shape must match the current ProposedChange schema.

Prompt changes that affect output shape require fixture updates.

Model output must preserve Source and Document references.

Model output must preserve EvidenceTarget text when it proposes Source-backed Assertions.

Model output is non-deterministic.

ModelRuntime Adapters parse model output through Application Layer DTOs before returning it.

Invalid model output must fail validation before it becomes a ProposedChange.

Recovery from invalid model output must be explicit.

Allowed recovery paths are rejection, quarantine, validation errors, or reviewable ProposedChange records.

ModelRuntime Adapters must not silently repair, drop, coerce, skip, or clean up invalid model output.

ModelRuntime Adapters must not write accepted state.

## Prompt Rules

Prompts live in `prompts/`.

Prompts use canonical terms from `docs/agent/domain.md`.

Prompts must ask for structured output when a Pipeline consumes the output.

Prompts must separate Source report confidence from world truth confidence.

Prompts must label analytic inference as analytic inference.
