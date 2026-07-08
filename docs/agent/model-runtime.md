# Model Runtime Rules

## Purpose

Local models propose structure and draft text.

Local models do not own canonical state.

## Runtime Targets

Support macOS on Apple Silicon.

Support WSL/Ubuntu with NVIDIA GPU.

Initial runtime Adapters:

- Ollama
- llama.cpp

Later runtime Adapters:

- MLX-backed Adapter
- vLLM Adapter
- cloud LLM Adapter

## Model Roles

Use separate model roles.

| Role | Responsibility |
|---|---|
| embedding model | create vectors for Document chunks |
| extraction model | propose Assertions and EvidenceSpans |
| reconciliation model | propose entity matches |
| synthesis model | draft Briefings and analytic summaries |
| reranker model | rank retrieved evidence |

## Model Output Rules

Model output creates ProposedChange records.

Model output does not create accepted Assertions directly.

Prompt output shape must match the current ProposedChange schema.

Prompt changes that affect output shape require fixture updates.

Model output must preserve Source and Document references.

Model output must preserve EvidenceSpan text when it proposes Source-backed Assertions.

## Prompt Rules

Prompts live in `prompts/`.

Prompts use canonical terms from `docs/agent/domain.md`.

Prompts must ask for structured output when a Pipeline consumes the output.

Prompts must separate Source report confidence from world truth confidence.

Prompts must label analytic inference as analytic inference.
