"""Generate committed JSON Schema files from Domain Core models."""

from __future__ import annotations

from pathlib import Path

from kotekomi_domain.schemas import write_schemas


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    write_schemas(repo_root / "schemas")


if __name__ == "__main__":
    main()
