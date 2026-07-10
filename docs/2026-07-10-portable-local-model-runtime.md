# Portable Local Model Runtime

## Decision

KoteKomi runs local assertion proposal through the existing Application Layer
`ModelRuntime` Port. The Domain Core remains unaware of runtime providers,
hardware, endpoints, model tags, and prompts.

The default `macbook` profile uses `LlamaCppModelRuntime` against a local
llama.cpp server serving `hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M` with a 16,384-token
context. The explicit `wsl-4090` profile uses `OllamaModelRuntime` against local
Ollama serving `qwen3:30b` with the same context cap.

## Boundary

Both adapters implement `ModelRuntime.propose_assertions`. They map their
runtime-native HTTP request and response shapes to `ModelProposal`, validate
through Application Layer validation, and return no partial result on transport,
JSON, or record-validation failure. The assertion proposal use case alone creates
ProposedChange and ProvenanceActivity records.

## Configuration

Runtime profiles live in `kotekomi.toml` or built-in defaults. `--runtime-profile`
selects a named profile. Unknown or malformed profiles fail before a model request.
No host auto-detection or runtime fallback is allowed.

Fixture JSON remains available only through `--model-output-fixture` for repeatable
tests.
