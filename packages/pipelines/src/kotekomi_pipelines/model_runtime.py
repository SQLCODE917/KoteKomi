"""Pipeline composition for configured ModelRuntime Adapters."""

from __future__ import annotations

from kotekomi_adapters import (
    LlamaServerModelRuntime,
    OllamaModelRuntime,
)
from kotekomi_application import ModelRuntimeReadiness

from kotekomi_pipelines.config import ModelExecutionConfig


def build_model_runtime_readiness(config: ModelExecutionConfig) -> ModelRuntimeReadiness:
    if config.adapter == "fixture":
        raise ValueError("model status requires llama_server or ollama runtime.")
    if config.adapter == "llama_server":
        return LlamaServerModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    if config.adapter == "ollama":
        return OllamaModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    raise ValueError(f"Unsupported model runtime: {config.adapter}")
