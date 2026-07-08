"""KoteKomi command-line entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kotekomi_adapters import SQLiteLedgerInitializer
from kotekomi_application import initialize_ledger

from kotekomi_pipelines.config import PipelineConfig, load_config


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ledger" and args.ledger_command == "init":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return init_ledger(config)

    parser.print_help()
    return 2


def entrypoint() -> None:
    raise SystemExit(main())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kotekomi")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to kotekomi.toml.",
    )
    subparsers = parser.add_subparsers(dest="command")

    ledger_parser = subparsers.add_parser("ledger", help="Ledger commands.")
    ledger_subparsers = ledger_parser.add_subparsers(dest="ledger_command")
    init_parser = ledger_subparsers.add_parser("init", help="Create or migrate the Ledger.")
    init_parser.add_argument("--ledger-path", type=Path, default=None)
    init_parser.add_argument("--archive-path", type=Path, default=None)

    return parser


def init_ledger(config: PipelineConfig) -> int:
    config.archive_path.mkdir(parents=True, exist_ok=True)
    result = initialize_ledger(SQLiteLedgerInitializer(config.ledger_path))
    if result.applied_migrations:
        migrations = ", ".join(result.applied_migrations)
    else:
        migrations = "none"
    print(f"Ledger initialized: {result.ledger_path}")
    print(f"Archive path ready: {config.archive_path}")
    print(f"Applied migrations: {migrations}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
