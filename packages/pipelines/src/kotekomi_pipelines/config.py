"""Pipeline configuration loading and named local runtime profile resolution."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from kotekomi_application import BuildIdentity, EmbeddingProfile

PROJECT_CONFIG_PATH = Path("kotekomi.toml")
DEFAULT_LEDGER_PATH = Path("data/kotekomi.db")
DEFAULT_ARCHIVE_PATH = Path("data/archive")
DEFAULT_RUNTIME_PROFILE = "lm-studio"
DEFAULT_REPRESENTATION_POLICY_VERSION = "deposited-source-v1"
MODEL_RUNTIME_ADAPTERS = ("lm_studio", "llama_server", "ollama", "fixture")
EMBEDDING_ADAPTERS = ("lm_studio", "llama_server", "ollama")
ENTITY_LINKING_ADAPTERS = ("refined",)
ENTITY_LINKING_CONFIG_KEYS = frozenset({"adapter", "timeout_seconds"})
MODEL_RESOURCE_CONFIG_KEYS = frozenset({"root"})
DEFAULT_ENTITY_LINKING_TIMEOUT_SECONDS = 300.0
MODEL_RUNTIME_CONFIG_KEYS = frozenset(
    {
        "adapter",
        "endpoint",
        "model",
        "timeout_seconds",
        "context_tokens",
        "max_output_tokens",
    }
)


@dataclass(frozen=True)
class ModelExecutionConfig:
    adapter: str
    endpoint: str
    model: str
    timeout_seconds: float
    context_tokens: int
    max_output_tokens: int
    profile_name: str | None = None


@dataclass(frozen=True)
class EntityLinkingConfig:
    adapter: str
    timeout_seconds: float


@dataclass(frozen=True)
class PipelineConfig:
    ledger_path: Path
    archive_path: Path
    model_execution: ModelExecutionConfig
    embedding_profiles: dict[str, EmbeddingProfile]
    document_retrieval_embedding_profile_id: str | None
    model_resource_root: Path = field(
        default_factory=lambda: (default_user_data_path() / "model-resources").resolve()
    )
    entity_linking: EntityLinkingConfig = field(
        default_factory=lambda: EntityLinkingConfig(
            adapter="refined",
            timeout_seconds=DEFAULT_ENTITY_LINKING_TIMEOUT_SECONDS,
        )
    )


@dataclass(frozen=True)
class StorageConfig:
    ledger_path: Path
    archive_path: Path


@dataclass(frozen=True)
class ProcessingConfig:
    storage: StorageConfig
    build_identity: BuildIdentity


@dataclass(frozen=True)
class ProcessingStorageConfig:
    storage: StorageConfig
    representation_policy_version: str


class ProcessingConfigurationError(ValueError):
    """A safe user-facing failure while selecting processing configuration."""


class MissingProcessingConfigurationError(ProcessingConfigurationError):
    pass


class InvalidProcessingConfigurationError(ProcessingConfigurationError):
    pass


class CheckoutBuildIdentityError(ProcessingConfigurationError):
    pass


def default_user_config_path() -> Path:
    """Return the XDG-style user configuration location without creating it."""
    config_home = _environment_path("XDG_CONFIG_HOME", Path.home() / ".config")
    return config_home / "kotekomi" / "kotekomi.toml"


def default_user_data_path() -> Path:
    """Return the XDG-style user data location without creating it."""
    data_home = _environment_path("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return data_home / "kotekomi"


def select_config_path(config_path: Path | None) -> Path:
    """Select explicit, project-local, then user-local configuration."""
    if config_path is not None:
        return config_path
    if PROJECT_CONFIG_PATH.exists():
        return PROJECT_CONFIG_PATH
    return default_user_config_path()


def initialize_user_processing_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
) -> tuple[Path, ProcessingStorageConfig, bool]:
    """Create a non-destructive user processing config and return its storage settings."""
    target = (config_path or default_user_config_path()).expanduser().resolve()
    if target.exists():
        if ledger_path_override is not None or archive_path_override is not None:
            raise InvalidProcessingConfigurationError(
                "Existing KoteKomi configuration is not changed by init; "
                "remove path overrides or choose a new --config path."
            )
        return (
            target,
            load_processing_storage_config(
                config_path=target,
                ledger_path_override=None,
                archive_path_override=None,
            ),
            False,
        )

    if config_path is None:
        data_root = default_user_data_path()
        default_ledger_path = data_root / "kotekomi.db"
        default_archive_path = data_root / "archive"
    else:
        data_root = target.parent / "data"
        default_ledger_path = data_root / "kotekomi.db"
        default_archive_path = data_root / "archive"
    ledger_path = (ledger_path_override or default_ledger_path).expanduser().resolve()
    archive_path = (archive_path_override or default_archive_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _render_user_processing_config(
            ledger_path,
            archive_path,
            default_user_data_path() / "model-resources",
        ),
        encoding="utf-8",
    )
    return (
        target,
        load_processing_storage_config(
            config_path=target,
            ledger_path_override=None,
            archive_path_override=None,
        ),
        True,
    )


def load_processing_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
) -> ProcessingConfig:
    processing = load_processing_storage_config(
        config_path=config_path,
        ledger_path_override=ledger_path_override,
        archive_path_override=archive_path_override,
    )
    identity = derive_checkout_build_identity(processing.representation_policy_version)
    identity.snapshot()
    return ProcessingConfig(storage=processing.storage, build_identity=identity)


def load_processing_storage_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
) -> ProcessingStorageConfig:
    """Load storage and policy settings without deriving a processing identity."""
    selected_config_path = select_config_path(config_path).expanduser()
    if not selected_config_path.exists():
        raise MissingProcessingConfigurationError(
            "No KoteKomi configuration found at "
            f"{selected_config_path}. Run 'kotekomi init' or pass --config PATH."
        )
    try:
        with selected_config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
        config_base = selected_config_path.parent
        ledger_path = _path_from_config(raw_config, "ledger_path", DEFAULT_LEDGER_PATH, config_base)
        archive_path = _path_from_config(
            raw_config, "archive_path", DEFAULT_ARCHIVE_PATH, config_base
        )
        if ledger_path_override is not None:
            ledger_path = ledger_path_override
        if archive_path_override is not None:
            archive_path = archive_path_override
        processing_value = raw_config.get("processing")
        if not isinstance(processing_value, dict):
            raise TypeError("Config processing must be a table.")
        processing = cast(dict[str, object], processing_value)
        if set(processing) != {"representation_policy_version"}:
            raise ValueError("Config processing requires only representation_policy_version.")
        policy_version = _string_value(processing, "representation_policy_version")
    except tomllib.TOMLDecodeError as error:
        raise InvalidProcessingConfigurationError(
            f"Invalid KoteKomi configuration at {selected_config_path}: {error}."
        ) from error
    except (TypeError, ValueError) as error:
        raise InvalidProcessingConfigurationError(
            f"Invalid KoteKomi configuration at {selected_config_path}: {error}"
        ) from error
    return ProcessingStorageConfig(
        storage=StorageConfig(ledger_path.resolve(), archive_path.resolve()),
        representation_policy_version=policy_version,
    )


def derive_checkout_build_identity(representation_policy_version: str) -> BuildIdentity:
    """Derive an identity from the code currently executing in a Git checkout."""
    checkout_root = _executing_checkout_root()
    package_version = _checkout_package_version(checkout_root)
    source_revision = _git_output(checkout_root, "rev-parse", "HEAD")
    return BuildIdentity(
        package_version=package_version,
        source_revision=source_revision,
        artifact_digest=checkout_artifact_digest(checkout_root),
        representation_policy_version=representation_policy_version,
    )


def _render_user_processing_config(
    ledger_path: Path,
    archive_path: Path,
    model_resource_root: Path,
) -> str:
    return (
        f'ledger_path = "{ledger_path.as_posix()}"\n'
        f'archive_path = "{archive_path.as_posix()}"\n'
        "\n"
        "# LM Studio is the default local extraction runtime.\n"
        'runtime_profile = "lm-studio"\n'
        "\n"
        "# Alternative profiles are available for model-status. CIR-2 extraction uses LM Studio.\n"
        '# runtime_profile = "macbook"\n'
        '# runtime_profile = "wsl-4090"\n'
        "\n"
        "[processing]\n"
        f'representation_policy_version = "{DEFAULT_REPRESENTATION_POLICY_VERSION}"\n'
        "\n"
        "[model_resources]\n"
        f'root = "{model_resource_root.as_posix()}"\n'
    )


def _executing_checkout_root() -> Path:
    source_path = Path(__file__).resolve()
    for candidate in source_path.parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "packages").is_dir():
            try:
                root = Path(_git_output(candidate, "rev-parse", "--show-toplevel"))
            except CheckoutBuildIdentityError:
                break
            if root == candidate:
                return root
    raise CheckoutBuildIdentityError(
        "Cannot derive authoritative build identity from the executing KoteKomi checkout. "
        "Run KoteKomi from a Git checkout."
    )


def _git_output(checkout_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ("git", "-C", str(checkout_root), *arguments),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise CheckoutBuildIdentityError(
            "Cannot derive authoritative build identity because Git is unavailable. "
            "Run KoteKomi from a Git checkout."
        ) from error
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise CheckoutBuildIdentityError(
            "Cannot derive authoritative build identity from the executing KoteKomi checkout. "
            "Run KoteKomi from a Git checkout."
        )
    return value


def _checkout_package_version(checkout_root: Path) -> str:
    with (checkout_root / "pyproject.toml").open("rb") as project_file:
        raw_project = tomllib.load(project_file)
    project = raw_project.get("project")
    if not isinstance(project, dict):
        raise CheckoutBuildIdentityError(
            "Cannot derive authoritative build identity because project metadata is invalid."
        )
    project_values = cast(dict[str, Any], project)
    version = project_values.get("version")
    if not isinstance(version, str) or not version.strip():
        raise CheckoutBuildIdentityError(
            "Cannot derive authoritative build identity because project version is unavailable."
        )
    return version


def checkout_artifact_digest(checkout_root: Path) -> str:
    tracked_paths = [checkout_root / "pyproject.toml"]
    tracked_paths.extend(sorted((checkout_root / "packages").glob("*/pyproject.toml")))
    tracked_paths.extend(sorted((checkout_root / "packages").glob("*/src/**/*.py")))
    digest = hashlib.sha256()
    for path in tracked_paths:
        relative_path = path.relative_to(checkout_root).as_posix().encode("utf-8")
        digest.update(relative_path)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
    runtime_profile_override: str | None = None,
    model_runtime_adapter_override: str | None = None,
    model_endpoint_override: str | None = None,
    model_name_override: str | None = None,
    model_timeout_seconds_override: float | None = None,
    model_context_tokens_override: int | None = None,
    model_max_output_tokens_override: int | None = None,
) -> PipelineConfig:
    selected_config_path = select_config_path(config_path).expanduser()
    raw_config: dict[str, object] = {}
    config_base = Path.cwd()
    if selected_config_path.exists():
        with selected_config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
        config_base = selected_config_path.parent
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
        timeout_seconds=model_timeout_seconds_override,
        context_tokens=model_context_tokens_override,
        max_output_tokens=model_max_output_tokens_override,
    )

    embedding_profiles = _embedding_profiles(raw_config, config_base)
    return PipelineConfig(
        ledger_path=ledger_path.resolve(),
        archive_path=archive_path.resolve(),
        model_execution=model_runtime,
        embedding_profiles=embedding_profiles,
        document_retrieval_embedding_profile_id=_document_retrieval_embedding_profile_id(
            raw_config, embedding_profiles
        ),
        model_resource_root=_model_resource_root(raw_config, config_base),
        entity_linking=_entity_linking_config(raw_config, config_base),
    )


def _entity_linking_config(raw_config: dict[str, object], config_base: Path) -> EntityLinkingConfig:
    del config_base
    value = raw_config.get("entity_linking")
    if value is None:
        return EntityLinkingConfig(
            adapter="refined",
            timeout_seconds=DEFAULT_ENTITY_LINKING_TIMEOUT_SECONDS,
        )
    if not isinstance(value, dict):
        raise TypeError("Config entity_linking must be a table.")
    fields = {str(key): item for key, item in cast(dict[object, object], value).items()}
    if any(not isinstance(key, str) for key in cast(dict[object, object], value)):
        raise TypeError("Config entity_linking keys must be strings.")
    unknown = sorted(set(fields) - ENTITY_LINKING_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"Unknown entity_linking config keys: {', '.join(unknown)}.")
    missing = sorted(ENTITY_LINKING_CONFIG_KEYS - set(fields))
    if missing:
        raise ValueError(f"Missing entity_linking config keys: {', '.join(missing)}.")
    adapter = _string_value(fields, "adapter")
    if adapter not in ENTITY_LINKING_ADAPTERS:
        raise ValueError("Entity-linking adapter must be refined.")
    return EntityLinkingConfig(
        adapter=adapter,
        timeout_seconds=_positive_float(fields, "timeout_seconds"),
    )


def _model_resource_root(raw_config: dict[str, object], config_base: Path) -> Path:
    value = raw_config.get("model_resources")
    if value is None:
        return (default_user_data_path() / "model-resources").resolve()
    if not isinstance(value, dict):
        raise TypeError("Config model_resources must be a table.")
    fields = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in fields):
        raise TypeError("Config model_resources keys must be strings.")
    values = {cast(str, key): item for key, item in fields.items()}
    unknown = sorted(set(values) - MODEL_RESOURCE_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"Unknown model_resources config keys: {', '.join(unknown)}.")
    missing = sorted(MODEL_RESOURCE_CONFIG_KEYS - set(values))
    if missing:
        raise ValueError(f"Missing model_resources config keys: {', '.join(missing)}.")
    configured = Path(_string_value(values, "root")).expanduser()
    return (configured if configured.is_absolute() else config_base / configured).resolve()


def _model_runtime_from_config(
    raw_config: dict[str, object],
    config_base: Path,
    profile_name: str,
) -> ModelExecutionConfig:
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
        "lm-studio": {
            "adapter": "lm_studio",
            "endpoint": "http://127.0.0.1:1234/v1",
            "model": "qwen2.5-14b-instruct",
            "timeout_seconds": 300.0,
            "context_tokens": 16384,
            "max_output_tokens": 2048,
        },
        "macbook": {
            "adapter": "llama_server",
            "endpoint": "http://127.0.0.1:8080/v1",
            "model": "Qwen/Qwen3-14B-GGUF:Q4_K_M",
            "timeout_seconds": 300.0,
            "context_tokens": 16384,
            "max_output_tokens": 8192,
        },
        "wsl-4090": {
            "adapter": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "qwen3:30b-a3b-instruct-2507-q4_K_M",
            "timeout_seconds": 300.0,
            "context_tokens": 16384,
            "max_output_tokens": 8192,
        },
        "fixture": {
            "adapter": "fixture",
            "endpoint": "fixture://runtime",
            "model": "fixture-model",
            "timeout_seconds": 1.0,
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
) -> ModelExecutionConfig:
    adapter = _string_value(runtime, "adapter")
    if adapter not in MODEL_RUNTIME_ADAPTERS:
        allowed = ", ".join(MODEL_RUNTIME_ADAPTERS)
        raise ValueError(f"Model runtime adapter must be one of: {allowed}.")
    return ModelExecutionConfig(
        profile_name=profile_name,
        adapter=adapter,
        endpoint=_string_value(runtime, "endpoint"),
        model=_string_value(runtime, "model"),
        timeout_seconds=_positive_float(runtime, "timeout_seconds"),
        context_tokens=_positive_int(runtime, "context_tokens"),
        max_output_tokens=_positive_int(runtime, "max_output_tokens"),
    )


def _apply_model_runtime_overrides(
    config: ModelExecutionConfig,
    *,
    adapter: str | None,
    endpoint: str | None,
    model: str | None,
    timeout_seconds: float | None,
    context_tokens: int | None,
    max_output_tokens: int | None,
) -> ModelExecutionConfig:
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
    return ModelExecutionConfig(
        profile_name=config.profile_name,
        adapter=selected_adapter,
        endpoint=_override_string(endpoint, config.endpoint, "model_endpoint"),
        model=_override_string(model, config.model, "model_name"),
        timeout_seconds=selected_timeout,
        context_tokens=selected_context,
        max_output_tokens=selected_output,
    )


def _string_value(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Config key {key} must be a non-empty string.")
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


def _environment_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def _embedding_profiles(
    raw_config: dict[str, object], config_base: Path
) -> dict[str, EmbeddingProfile]:
    value = raw_config.get("embedding_profiles", {})
    if not isinstance(value, dict):
        raise TypeError("Config embedding_profiles must be a table.")
    profiles: dict[str, EmbeddingProfile] = {}
    for profile_id, raw_profile in cast(dict[object, object], value).items():
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise TypeError("Embedding profile IDs must be non-empty strings.")
        if not isinstance(raw_profile, dict):
            raise TypeError(f"Embedding profile {profile_id} must be a table.")
        fields = _validated_embedding_profile_table(
            cast(dict[object, object], raw_profile), profile_id
        )
        path = Path(_string_value(fields, "model_path"))
        profiles[profile_id] = EmbeddingProfile(
            profile_id=profile_id,
            adapter_id=_string_value(fields, "adapter"),
            endpoint=_string_value(fields, "endpoint"),
            model_id=_string_value(fields, "model"),
            model_path=str(path if path.is_absolute() else config_base / path),
            model_digest=_sha256_value(fields, "model_digest"),
            expected_vector_dimension=_positive_int(fields, "vector_dimension"),
            maximum_rendered_characters=_positive_int(fields, "maximum_rendered_characters"),
            timeout_seconds=_positive_float(fields, "timeout_seconds"),
        )
    return profiles


def _document_retrieval_embedding_profile_id(
    raw_config: dict[str, object], profiles: dict[str, EmbeddingProfile]
) -> str | None:
    value = raw_config.get("document_retrieval")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("Config document_retrieval must be a table.")
    fields = cast(dict[object, object], value)
    if set(fields) != {"default_embedding_profile"}:
        raise ValueError("Config document_retrieval requires only default_embedding_profile.")
    profile_id = _string_value(
        {key: item for key, item in fields.items() if isinstance(key, str)},
        "default_embedding_profile",
    )
    if profile_id not in profiles:
        raise ValueError("Config document_retrieval default_embedding_profile is unknown.")
    return profile_id


def _validated_embedding_profile_table(
    raw_profile: dict[object, object], profile_id: str
) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key, value in raw_profile.items():
        if not isinstance(key, str):
            raise TypeError(f"Embedding profile {profile_id} keys must be strings.")
        fields[key] = value
    required = {
        "adapter",
        "endpoint",
        "model",
        "model_path",
        "model_digest",
        "vector_dimension",
        "maximum_rendered_characters",
        "timeout_seconds",
    }
    unknown = sorted(set(fields) - required)
    missing = sorted(required - set(fields))
    if unknown:
        raise ValueError(f"Unknown embedding profile {profile_id} keys: {', '.join(unknown)}.")
    if missing:
        raise ValueError(f"Embedding profile {profile_id} is missing: {', '.join(missing)}.")
    adapter = _string_value(fields, "adapter")
    if adapter not in EMBEDDING_ADAPTERS:
        allowed = ", ".join(EMBEDDING_ADAPTERS)
        raise ValueError(f"Embedding profile adapter must be one of: {allowed}.")
    return fields


def _sha256_value(values: dict[str, object], key: str) -> str:
    value = _string_value(values, key)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"Embedding profile {key} must be a lowercase SHA-256 digest.")
    return value
