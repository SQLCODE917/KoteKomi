"""Pipeline configuration loading and named local runtime profile resolution."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

DEFAULT_CONFIG_PATH = Path("kotekomi.toml")
DEFAULT_LEDGER_PATH = Path("data/kotekomi.db")
DEFAULT_ARCHIVE_PATH = Path("data/archive")
DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts/propose_assertions.md"
DEFAULT_RUNTIME_PROFILE = "macbook"
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
    profile_name: str | None = None


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
    runtime_profile_override: str | None = None,
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
    profile_name = runtime_profile_override or _runtime_profile_name(raw_config)
    model_runtime = _model_runtime_from_config(raw_config, config_base, profile_name)

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
    profile_name: str,
) -> ModelRuntimeConfig:
    profile = _runtime_profiles(raw_config).get(profile_name)
    if profile is None:
        available = ", ".join(sorted(_runtime_profiles(raw_config)))
        raise ValueError(
            f"Unknown runtime profile: {profile_name}. Available profiles: {available}."
        )
    runtime = {**profile, **_runtime_table(raw_config, "model_runtime")}
    return _validated_model_runtime(runtime, config_base, profile_name)


def _runtime_profiles(raw_config: dict[str, object]) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {
        "macbook": {
            "adapter": "llama_server",
            "endpoint": "http://127.0.0.1:8080/v1",
            "model": "Qwen/Qwen3-14B-GGUF:Q4_K_M",
            "prompt_path": str(DEFAULT_PROMPT_PATH),
            "timeout_seconds": 300.0,
            "context_tokens": 16384,
            "max_output_tokens": 8192,
        },
        "wsl-4090": {
            "adapter": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "qwen3:30b-a3b-instruct-2507-q4_K_M",
            "prompt_path": str(DEFAULT_PROMPT_PATH),
            "timeout_seconds": 300.0,
            "context_tokens": 16384,
            "max_output_tokens": 8192,
        },
    }
    for name, override in _runtime_profile_table(raw_config).items():
        profiles[name] = {**profiles.get(name, {}), **override}
    return profiles


def _runtime_profile_name(raw_config: dict[str, object]) -> str:
    value = raw_config.get("runtime_profile", DEFAULT_RUNTIME_PROFILE)
    if not isinstance(value, str) or not value.strip():
        raise TypeError("Config key runtime_profile must be a non-empty string.")
    return value


def _runtime_profile_table(raw_config: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_profiles = raw_config.get("runtime_profiles", {})
    if not isinstance(raw_profiles, dict):
        raise TypeError("Config key runtime_profiles must be a table.")
    profiles: dict[str, dict[str, object]] = {}
    for name, value in cast(dict[object, object], raw_profiles).items():
        if not isinstance(name, str):
            raise TypeError("Config runtime_profiles keys must be strings.")
        if not isinstance(value, dict):
            raise TypeError(f"Runtime profile {name} must be a table.")
        profiles[name] = _validated_runtime_table(
            cast(dict[object, object], value),
            f"runtime_profiles.{name}",
        )
    return profiles


def _runtime_table(raw_config: dict[str, object], name: str) -> dict[str, object]:
    value = raw_config.get(name, {})
    if not isinstance(value, dict):
        raise TypeError(f"Config key {name} must be a table.")
    return _validated_runtime_table(cast(dict[object, object], value), name)


def _validated_runtime_table(values: dict[object, object], name: str) -> dict[str, object]:
    runtime: dict[str, object] = {}
    for key, value in values.items():
        if not isinstance(key, str):
            raise TypeError(f"Config {name} keys must be strings.")
        runtime[key] = value
    unknown_keys = sorted(set(runtime) - MODEL_RUNTIME_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"Unknown {name} config keys: {', '.join(unknown_keys)}.")
    return runtime


def _validated_model_runtime(
    runtime: dict[str, object], config_base: Path, profile_name: str
) -> ModelRuntimeConfig:
    adapter = _string_value(runtime, "adapter")
    if adapter not in MODEL_RUNTIME_ADAPTERS:
        allowed = ", ".join(MODEL_RUNTIME_ADAPTERS)
        raise ValueError(f"Model runtime adapter must be one of: {allowed}.")
    return ModelRuntimeConfig(
        profile_name=profile_name,
        adapter=adapter,
        endpoint=_string_value(runtime, "endpoint"),
        model=_string_value(runtime, "model"),
        prompt_path=_runtime_prompt_path(runtime, config_base),
        timeout_seconds=_positive_float(runtime, "timeout_seconds"),
        context_tokens=_positive_int(runtime, "context_tokens"),
        max_output_tokens=_positive_int(runtime, "max_output_tokens"),
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
    return ModelRuntimeConfig(
        profile_name=config.profile_name,
        adapter=selected_adapter,
        endpoint=_override_string(endpoint, config.endpoint, "model_endpoint"),
        model=_override_string(model, config.model, "model_name"),
        prompt_path=prompt_path.resolve() if prompt_path is not None else config.prompt_path,
        timeout_seconds=selected_timeout,
        context_tokens=selected_context,
        max_output_tokens=selected_output,
    )


def _runtime_prompt_path(runtime: dict[str, object], config_base: Path) -> Path:
    path = Path(_string_value(runtime, "prompt_path"))
    return path if path.is_absolute() else (config_base / path).resolve()


def _string_value(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Model runtime {key} must be a non-empty string.")
    return value


def _positive_float(values: dict[str, object], key: str) -> float:
    value = values.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
        raise TypeError(f"Model runtime {key} must be a positive number.")
    return float(value)


def _positive_int(values: dict[str, object], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TypeError(f"Model runtime {key} must be a positive integer.")
    return value


def _override_string(value: str | None, default: str, name: str) -> str:
    if value is None:
        return default
    if not value.strip():
        raise ValueError(f"{name} override must be a non-empty string.")
    return value


def _path_from_config(
    raw_config: dict[str, object], key: str, default: Path, config_base: Path
) -> Path:
    value = raw_config.get(key)
    if value is None:
        path = default
    elif isinstance(value, str):
        path = Path(value)
    else:
        raise TypeError(f"Config key {key} must be a string path.")
    return path if path.is_absolute() else config_base / path
