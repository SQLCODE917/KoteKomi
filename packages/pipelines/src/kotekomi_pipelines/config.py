"""Pipeline configuration loading."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

DEFAULT_CONFIG_PATH = Path("kotekomi.toml")
DEFAULT_LEDGER_PATH = Path("data/kotekomi.db")
DEFAULT_ARCHIVE_PATH = Path("data/archive")
DEFAULT_PROMPT_PATH = Path("prompts/propose_assertions.md")
DEFAULT_RUNTIME_PROFILE = "macbook"


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    provider: Literal["llama_cpp", "ollama"]
    base_url: str
    model_name: str
    context_window: int
    timeout_seconds: float


@dataclass(frozen=True)
class PipelineConfig:
    ledger_path: Path
    archive_path: Path
    prompt_path: Path
    runtime_profile: RuntimeProfile


def load_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
    runtime_profile_override: str | None = None,
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
    prompt_path = _path_from_config(raw_config, "prompt_path", DEFAULT_PROMPT_PATH, config_base)

    if ledger_path_override is not None:
        ledger_path = ledger_path_override
    if archive_path_override is not None:
        archive_path = archive_path_override
    profile_name = runtime_profile_override or _runtime_profile_name(raw_config)

    return PipelineConfig(
        ledger_path=ledger_path.resolve(),
        archive_path=archive_path.resolve(),
        prompt_path=prompt_path.resolve(),
        runtime_profile=_load_runtime_profile(raw_config, profile_name),
    )


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


def _runtime_profile_name(raw_config: dict[str, object]) -> str:
    value = raw_config.get("runtime_profile", DEFAULT_RUNTIME_PROFILE)
    if not isinstance(value, str) or not value.strip():
        raise TypeError("Config key runtime_profile must be a non-empty string.")
    return value


def _load_runtime_profile(raw_config: dict[str, object], profile_name: str) -> RuntimeProfile:
    profiles = _configured_profiles(raw_config)
    profile = profiles.get(profile_name)
    if profile is None:
        available = ", ".join(sorted(profiles))
        raise ValueError(
            f"Unknown runtime profile: {profile_name}. Available profiles: {available}."
        )
    return profile


def _configured_profiles(raw_config: dict[str, object]) -> dict[str, RuntimeProfile]:
    profiles: dict[str, dict[str, object]] = {
        "macbook": {
            "provider": "llama_cpp",
            "base_url": "http://127.0.0.1:8080/v1",
            "model_name": "hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M",
            "context_window": 16384,
            "timeout_seconds": 120.0,
        },
        "wsl-4090": {
            "provider": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "model_name": "qwen3:30b",
            "context_window": 16384,
            "timeout_seconds": 120.0,
        },
    }
    configured = raw_config.get("runtime_profiles")
    if configured is None:
        return {name: _validated_profile(name, value) for name, value in profiles.items()}
    if not isinstance(configured, dict):
        raise TypeError("Config key runtime_profiles must be a table.")
    configured_profiles = cast_str_object_mapping(
        cast(dict[object, object], configured),
        "runtime_profiles",
    )
    for name, value in configured_profiles.items():
        if not isinstance(value, dict):
            raise TypeError(f"Runtime profile {name} must be a table.")
        override = cast_str_object_mapping(
            cast(dict[object, object], value),
            f"runtime_profiles.{name}",
        )
        if name in profiles:
            profiles[name] = {
                **profiles[name],
                **override,
            }
        else:
            profiles[name] = override
    return {name: _validated_profile(name, value) for name, value in profiles.items()}


def _validated_profile(name: str, profile: dict[str, object]) -> RuntimeProfile:
    provider = profile.get("provider")
    if provider not in {"llama_cpp", "ollama"}:
        raise ValueError(f"Runtime profile {name}.provider must be llama_cpp or ollama.")
    base_url = profile.get("base_url")
    model_name = profile.get("model_name")
    context_window = profile.get("context_window")
    timeout_seconds = profile.get("timeout_seconds")
    if not isinstance(base_url, str) or not base_url.strip():
        raise TypeError(f"Runtime profile {name}.base_url must be a non-empty string.")
    if not isinstance(model_name, str) or not model_name.strip():
        raise TypeError(f"Runtime profile {name}.model_name must be a non-empty string.")
    if (
        not isinstance(context_window, int)
        or isinstance(context_window, bool)
        or context_window <= 0
    ):
        raise TypeError(f"Runtime profile {name}.context_window must be a positive integer.")
    if (
        not isinstance(timeout_seconds, int | float)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise TypeError(f"Runtime profile {name}.timeout_seconds must be a positive number.")
    return RuntimeProfile(
        name=name,
        provider=cast(Literal["llama_cpp", "ollama"], provider),
        base_url=base_url,
        model_name=model_name,
        context_window=context_window,
        timeout_seconds=float(timeout_seconds),
    )


def cast_str_object_mapping(value: dict[object, object], context: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"Config table {context} contains a non-string key.")
        result[key] = item
    return result
