"""Seal or revalidate the IPI reserved passage manifest.

The reviewer runs the command; the sealed manifest stays under a custody root
outside this repository. Output names counts and digests only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from kotekomi_devtools.ipi_custody import (
    CustodyError,
    fill_text_digests,
    load_manifest,
    manifest_summary,
    reserved_template,
    seal,
    validate_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipi_reserved_custody",
        description="Seal or revalidate the IPI reserved passage manifest.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    seal_parser = subparsers.add_parser("seal", help="Validate and seal the reserved manifest.")
    seal_parser.add_argument("--source", type=Path, required=True)
    seal_parser.add_argument("--custody-root", type=Path, required=True)
    seal_parser.add_argument("--reviewer", required=True)
    check_parser = subparsers.add_parser("check", help="Revalidate a sealed reserved manifest.")
    check_parser.add_argument("--custody-root", type=Path, required=True)
    check_parser.add_argument("--inspected", type=Path, required=True)
    return parser


def _inspected(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise CustodyError(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise CustodyError(f"{path} is not valid JSON: {error}") from error


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        inspected = _inspected(
            arguments.inspected
            if arguments.command == "check"
            else Path("docs/2026-11-06-ipi-inspected-material.json")
        )
        if arguments.command == "seal":
            template_path = arguments.custody_root / "reserved-manifest.template.json"
            if not template_path.exists():
                arguments.custody_root.mkdir(parents=True, exist_ok=True)
                source_sha256 = hashlib.sha256(arguments.source.read_bytes()).hexdigest()
                template = reserved_template(
                    source_path=arguments.source.as_posix(),
                    source_sha256=source_sha256,
                    reviewer=arguments.reviewer,
                )
                template_path.write_text(
                    json.dumps(template, allow_nan=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print(
                    json.dumps(
                        {
                            "status": "template-written",
                            "path": str(template_path),
                            "next": "Fill the template, then rerun seal.",
                        },
                        sort_keys=True,
                    )
                )
                return 0
            payload = fill_text_digests(load_manifest(template_path))
            path, digest = seal(arguments.custody_root, payload, inspected)
            manifest = validate_manifest(payload, inspected)
            print(
                json.dumps(
                    {
                        "status": "sealed",
                        "path": str(path),
                        "manifest_sha256": digest,
                        "summary": manifest_summary(manifest),
                    },
                    sort_keys=True,
                )
            )
            return 0
        payload = load_manifest(arguments.custody_root / "reserved-manifest.json")
        manifest = validate_manifest(payload, inspected)
        canonical = json.dumps(
            payload, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        print(
            json.dumps(
                {
                    "status": "valid",
                    "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
                    "summary": manifest_summary(manifest),
                },
                sort_keys=True,
            )
        )
        return 0
    except CustodyError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
