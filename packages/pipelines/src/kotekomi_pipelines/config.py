"""Pipeline configuration loading."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("kotekomi.toml")
DEFAULT_LEDGER_PATH = Path("data/kotekomi.db")
DEFAULT_ARCHIVE_PATH = Path("data/archive")


@dataclass(frozen=True)
class PipelineConfig:
    ledger_path: Path
    archive_path: Path


def load_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
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

    if ledger_path_override is not None:
        ledger_path = ledger_path_override
    if archive_path_override is not None:
        archive_path = archive_path_override

    return PipelineConfig(
        ledger_path=ledger_path.resolve(),
        archive_path=archive_path.resolve(),
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
