"""Repository test configuration for spawned interpreters.

A spawned worker imports test support modules from this checkout. This file puts
the checkout root and its package source directories on the child interpreter's
`PYTHONPATH`, so subprocess tests resolve the code under test rather than a
package installed from another worktree.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _package_source_paths() -> list[Path]:
    packages = ROOT / "packages"
    return [path / "src" for path in sorted(packages.iterdir()) if (path / "src").is_dir()]


CHILD_IMPORT_PATHS = [ROOT, *_package_source_paths()]


def _prepend_child_paths() -> None:
    existing = [part for part in os.environ.get("PYTHONPATH", "").split(os.pathsep) if part]
    ordered = [str(path) for path in CHILD_IMPORT_PATHS]
    merged = ordered + [part for part in existing if part not in ordered]
    os.environ["PYTHONPATH"] = os.pathsep.join(merged)


_prepend_child_paths()
