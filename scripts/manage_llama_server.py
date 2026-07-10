"""Install, inspect, or remove the current user's shared llama-server service."""

from __future__ import annotations

import argparse
from pathlib import Path

from kotekomi_pipelines.managed_llama_server import (
    ManagedLlamaServerConfig,
    get_managed_llama_server_status,
    install_managed_llama_server,
    uninstall_managed_llama_server,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--llama-server-path", required=True, type=Path)
    subparsers.add_parser("status")
    subparsers.add_parser("uninstall")
    args = parser.parse_args(argv)
    home_path = Path.home()

    if args.command == "install":
        agent_path = install_managed_llama_server(
            ManagedLlamaServerConfig(
                executable_path=args.llama_server_path.resolve(),
                home_path=home_path,
            )
        )
        print(agent_path)
        return 0
    if args.command == "status":
        status = get_managed_llama_server_status(home_path=home_path)
        print(f"installed={str(status.installed).lower()}")
        print(f"loaded={str(status.loaded).lower()}")
        print(f"agent_path={status.agent_path}")
        return 0
    if args.command == "uninstall":
        print(uninstall_managed_llama_server(home_path=home_path))
        return 0
    raise AssertionError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
