#!/usr/bin/env bash
# Canonical KoteKomi verification entry point.
#
# This is the single command run by both CI (.github/workflows/ci.yml) and local
# development to verify the repository. Run it from the repository root:
#
#     ./scripts/verify.sh
#
# The CI workflow provisions the platform tooling *before* invoking this script:
#   * Ubuntu: `sudo apt-get install --yes poppler-utils qpdf`
#   * Python 3.12 via `astral-sh/setup-uv`
#   * `KOTEKOMI_QPDF_EXECUTABLE=/usr/bin/qpdf`
# Local runs must provide the same interpreters and system tools (macOS:
# `brew install poppler qpdf`, or an equivalent qpdf/poppler install on PATH)
# for results to stay comparable. This script intentionally does not install
# tooling: it only verifies, so the environment stays the caller's concern.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

step() { printf '\n==> %s\n' "$*"; }

step "generate JSON Schemas"
uv run python scripts/generate_schemas.py

step "verify committed schemas are unchanged"
git diff --exit-code -- schemas

step "ruff check"
uv run ruff check

step "pyright"
uv run pyright

step "pytest"
uv run pytest