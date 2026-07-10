"""Pipeline configuration loading."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

DEFAULT_CONFIG_PATH = Path("kotekomi.toml")
DEFAULT_LEDGER_PATH = Path("data/kotekomi.db")
DEFAULT_ARCHIVE_PATH = Path("data/archive")
DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts/propose_assertions.md"
DEFAULT_MODEL_RUNTIME_ADAPTER = "llama_server"
DEFAULT_MODEL_ENDPOINT = "http://127.0.0.1:8080/v1"
DEFAULT_MODEL_NAME = "Qwen/Qwen3-14B-GGUF:Q4_K_M"
DEFAULT_MODEL_TIMEOUT_SECONDS = 300.0
DEFAULT_MODEL_CONTEXT_TOKENS = 16384
DEFAULT_MODEL_MAX_OUTPUT_TOKENS = 8192
MODEL_RUNTIME_ADAPTERS = ("llama_server", "ollama", "fixture")
MODEL_RUNTIME_CONFIG_KEYS = frozenset(
    {
        "adapter",
        "endpoint",
        "model",
        "prompt_path",
        "timeout_seconds",
        "context_tokens",
        "max_output_tokens",
    }
)


@dataclass(frozen=True)
class ModelRuntimeConfig:
    adapter: str
    endpoint: str
    model: str
    prompt_path: Path
    timeout_seconds: float
    context_tokens: int
    max_output_tokens: int


@dataclass(frozen=True)
class PipelineConfig:
    ledger_path: Path
    archive_path: Path
    model_runtime: ModelRuntimeConfig


def load_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
    model_runtime_adapter_override: str | None = None,
    model_endpoint_override: str | None = None,
    model_name_override: str | None = None,
    model_prompt_path_override: Path | None = None,
    model_timeout_seconds_override: float | None = None,
    model_context_tokens_override: int | None = None,
    model_max_output_tokens_override: int | None = None,
) -> PipelineConfig:
    selected_config_path = config_path or DEFAULT_CONFIG_PATH
    raw_config: dict[str, object] = {}
    config_base = selected_config_path.parent
    if selected_config_path.exists():
        with selected_config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    elif config_path is not None:
        raise FileNotFoundError(f"Config file does not exist: {selected_config_path}")

    ledger_path = _path_from_config(raw_config, "ledger_path", DEFAULT_LEDGER_PATH, config_base)
    archive_path = _path_from_config(raw_config, "archive_path", DEFAULT_ARCHIVE_PATH, config_base)
    model_runtime = _model_runtime_from_config(raw_config, config_base)

    if ledger_path_override is not None:
        ledger_path = ledger_path_override
    if archive_path_override is not None:
        archive_path = archive_path_override
    model_runtime = _apply_model_runtime_overrides(
        model_runtime,
        adapter=model_runtime_adapter_override,
        endpoint=model_endpoint_override,
        model=model_name_override,
        prompt_path=model_prompt_path_override,
        timeout_seconds=model_timeout_seconds_override,
        context_tokens=model_context_tokens_override,
        max_output_tokens=model_max_output_tokens_override,
    )

    return PipelineConfig(
        ledger_path=ledger_path.resolve(),
        archive_path=archive_path.resolve(),
        model_runtime=model_runtime,
    )


def _model_runtime_from_config(
    raw_config: dict[str, object],
    config_base: Path,
) -> ModelRuntimeConfig:
    raw_value = raw_config.get("model_runtime", {})
    if not isinstance(raw_value, dict):
        raise TypeError("Config key model_runtime must be a table.")
    raw_runtime = cast(dict[object, object], raw_value)
    runtime: dict[str, object] = {}
    for key, value in raw_runtime.items():
        if not isinstance(key, str):
            raise TypeError("Config model_runtime keys must be strings.")
        runtime[key] = value
    unknown_keys = sorted(set(runtime) - MODEL_RUNTIME_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"Unknown model_runtime config keys: {', '.join(unknown_keys)}.")

    adapter = _string_value(runtime, "adapter", DEFAULT_MODEL_RUNTIME_ADAPTER)
    if adapter not in MODEL_RUNTIME_ADAPTERS:
        allowed = ", ".join(MODEL_RUNTIME_ADAPTERS)
        raise ValueError(f"Config model_runtime.adapter must be one of: {allowed}.")
    endpoint = _string_value(runtime, "endpoint", DEFAULT_MODEL_ENDPOINT)
    model = _string_value(runtime, "model", DEFAULT_MODEL_NAME)
    prompt_path = _runtime_prompt_path(runtime, config_base)
    timeout_seconds = _positive_float(
        runtime,
        "timeout_seconds",
        DEFAULT_MODEL_TIMEOUT_SECONDS,
    )
    context_tokens = _positive_int(runtime, "context_tokens", DEFAULT_MODEL_CONTEXT_TOKENS)
    max_output_tokens = _positive_int(
        runtime,
        "max_output_tokens",
        DEFAULT_MODEL_MAX_OUTPUT_TOKENS,
    )
    return ModelRuntimeConfig(
        adapter=adapter,
        endpoint=endpoint,
        model=model,
        prompt_path=prompt_path,
        timeout_seconds=timeout_seconds,
        context_tokens=context_tokens,
        max_output_tokens=max_output_tokens,
    )


def _apply_model_runtime_overrides(
    config: ModelRuntimeConfig,
    *,
    adapter: str | None,
    endpoint: str | None,
    model: str | None,
    prompt_path: Path | None,
    timeout_seconds: float | None,
    context_tokens: int | None,
    max_output_tokens: int | None,
) -> ModelRuntimeConfig:
    selected_adapter = adapter or config.adapter
    if selected_adapter not in MODEL_RUNTIME_ADAPTERS:
        allowed = ", ".join(MODEL_RUNTIME_ADAPTERS)
        raise ValueError(f"Model runtime must be one of: {allowed}.")
    selected_timeout = timeout_seconds if timeout_seconds is not None else config.timeout_seconds
    selected_context = context_tokens if context_tokens is not None else config.context_tokens
    selected_output = (
        max_output_tokens if max_output_tokens is not None else config.max_output_tokens
    )
    if selected_timeout <= 0 or selected_context <= 0 or selected_output <= 0:
        raise ValueError("Model runtime numeric settings must be positive.")
    selected_endpoint = _override_string(endpoint, config.endpoint, "model_endpoint")
    selected_model = _override_string(model, config.model, "model_name")
    return ModelRuntimeConfig(
        adapter=selected_adapter,
        endpoint=selected_endpoint,
        model=selected_model,
        prompt_path=(prompt_path.resolve() if prompt_path is not None else config.prompt_path),
        timeout_seconds=selected_timeout,
        context_tokens=selected_context,
        max_output_tokens=selected_output,
    )


def _override_string(value: str | None, default: str, name: str) -> str:
    if value is None:
        return default
    if not value.strip():
        raise ValueError(f"{name} override must be a non-empty string.")
    return value


def _runtime_prompt_path(runtime: dict[str, object], config_base: Path) -> Path:
    value = runtime.get("prompt_path")
    if value is None:
        return DEFAULT_PROMPT_PATH
    if not isinstance(value, str) or not value.strip():
        raise TypeError("Config key model_runtime.prompt_path must be a string path.")
    path = Path(value)
    if path.is_absolute():
        return path
    return (config_base / path).resolve()


def _string_value(values: dict[str, object], key: str, default: str) -> str:
    value = values.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Config key model_runtime.{key} must be a non-empty string.")
    return value


def _positive_float(values: dict[str, object], key: str, default: float) -> float:
    value = values.get(key, default)
    if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
        raise TypeError(f"Config key model_runtime.{key} must be a positive number.")
    return float(value)


def _positive_int(values: dict[str, object], key: str, default: int) -> int:
    value = values.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TypeError(f"Config key model_runtime.{key} must be a positive integer.")
    return value


def _path_from_config(
    raw_config: dict[str, object],
    key: str,
    default: Path,
    config_base: Path,
) -> Path:
    value = raw_config.get(key)
    if value is None:
        path = default
    elif isinstance(value, str):
        path = Path(value)
    else:
        raise TypeError(f"Config key {key} must be a string path.")

    if path.is_absolute():
        return path
    return config_base / path
