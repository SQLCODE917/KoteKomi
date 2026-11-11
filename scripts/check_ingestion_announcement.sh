#!/usr/bin/env bash
# Human-started whole-tree checks with durable terminal records. No model calls.
set -euo pipefail

check_dir="${1:?Usage: bash scripts/check_ingestion_announcement.sh OUTPUT_DIRECTORY}"
mkdir -p "$check_dir"
check_dir="$(cd "$check_dir" && pwd)"
if test -e "$check_dir/revision.txt"; then
  echo "Output directory already contains a verification record: $check_dir" >&2
  exit 2
fi
trap 'check_status=$?; printf "%s\n" "$check_status" > "$check_dir/exit-code.txt"' EXIT
git rev-parse HEAD > "$check_dir/revision.txt"
git status --porcelain > "$check_dir/working-tree.txt"

uv run python scripts/generate_schemas.py > "$check_dir/schemas.log" 2>&1
git diff --exit-code -- schemas > "$check_dir/schema-drift.log" 2>&1
uv run ruff format --check . > "$check_dir/format.log" 2>&1
uv run ruff check . > "$check_dir/lint.log" 2>&1
uv run pyright > "$check_dir/typecheck.log" 2>&1
uv run pytest --durations=30 --junitxml="$check_dir/pytest.xml" \
  --basetemp="$check_dir/tests" > "$check_dir/pytest.log" 2>&1
