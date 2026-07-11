"""Pipeline composition for configured ModelRuntime Adapters."""

from __future__ import annotations

from pathlib import Path

from kotekomi_adapters import (
    LlamaServerModelRuntime,
    OllamaModelRuntime,
)
from kotekomi_application import ModelRuntimeReadiness

from kotekomi_pipelines.config import ModelRuntimeConfig


def build_model_runtime_readiness(config: ModelRuntimeConfig) -> ModelRuntimeReadiness:
    if config.adapter == "fixture":
        raise ValueError("model status requires llama_server or ollama runtime.")
    prompt_text = _read_prompt(config.prompt_path)
    if config.adapter == "llama_server":
        return LlamaServerModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            prompt_text=prompt_text,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    if config.adapter == "ollama":
        return OllamaModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            prompt_text=prompt_text,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    raise ValueError(f"Unsupported model runtime: {config.adapter}")


def _read_prompt(prompt_path: Path) -> str:
    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read model prompt: {prompt_path}") from exc
    if not prompt_text.strip():
        raise ValueError(f"Model prompt is empty: {prompt_path}")
    return prompt_text
