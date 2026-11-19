#!/usr/bin/env bash
# Canonical KoteKomi verification entry point.
#
# Run the full local gate from the repository root:
#
#     ./scripts/verify.sh
#
# The full gate generates JSON Schemas, fails on schema drift, runs Ruff format
# and Ruff lint, runs Pyright, and runs the complete pytest collection. Extra
# arguments pass through to pytest, so `./scripts/verify.sh --junitxml=report.xml`
# keeps working.
#
# CI runs this same entry point in explicit modes:
#
#     ./scripts/verify.sh fast
#         Static checks plus the smoke selection. The smoke selection runs no
#         PDF tooling and no live inference, so this mode needs no APT step and
#         returns the first useful signal.
#
#     ./scripts/verify.sh shard <name>
#         One full-suite shard from the shard plan.
#
#     ./scripts/verify.sh shard-plan
#         Prints the shard plan and the smoke selection as JSON. The CI
#         verification regression reads this plan.
#
#     ./scripts/verify.sh shard-needs-pdf-tools <name>
#         Prints `true` or `false` for one shard.
#
#     ./scripts/verify.sh aggregate <job>=<result> [...]
#         Fails unless every named CI job reports `success`. The CI `verify`
#         job passes the `needs` results here; an empty result means the job is
#         missing from the gate.
#
# The shard plan partitions the complete pytest collection. Every node ID that
# pytest collects from `testpaths` in pyproject.toml belongs to exactly one
# shard. The smoke selection intentionally overlaps shards and only contains
# tests that need no PDF tooling.
#
# The CI workflow provisions the platform tooling *before* invoking this script:
#   * Ubuntu: `sudo apt-get install --yes poppler-utils qpdf`, only for shards
#     whose plan entry declares `needs_pdf_tools=true`
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

# Shard plan entries: "<name>|<space-separated pytest paths>|<space-separated
# excluded test files>|<true|false>". Excluded files are selected by exactly one
# other shard; the coverage regression proves that assignment. The paths are
# explicit so a shard cannot silently narrow its selection.
shard_plan=(
  "core|packages/adapters/tests packages/application/tests packages/briefing/tests packages/devtools/tests packages/domain/tests packages/exporters/tests||true"
  "pipelines|packages/pipelines/tests|packages/pipelines/tests/test_operator_journey.py packages/pipelines/tests/test_r20_ingestion_transition.py packages/pipelines/tests/test_user_ingestion_run.py|true"
  "journeys|packages/pipelines/tests/test_operator_journey.py packages/pipelines/tests/test_r20_ingestion_transition.py packages/pipelines/tests/test_user_ingestion_run.py||true"
)

# Smoke selection: deterministic contracts with no PDF tooling and no live
# inference. The selection stays small by running the devtools unit contracts
# instead of the subprocess-driven devtools acceptance contracts. This selection
# overlaps the `core` shard on purpose.
smoke_paths=(
  "packages/briefing/tests"
  "packages/devtools/tests/unit"
  "packages/domain/tests"
  "packages/exporters/tests"
)

pytest_prefix=(-p no:cacheprovider -rs --durations=30)

# Prints one pytest selection argument per line: paths, then explicit ignores.
shard_selection() {
  local paths="$1" excludes="$2" item
  # shellcheck disable=SC2206
  local selection=($paths)
  printf '%s\n' "${selection[@]}"
  # shellcheck disable=SC2206
  for item in $excludes; do
    printf -- '--ignore=%s\n' "$item"
  done
}

run_static_checks() {
  step "generate JSON Schemas"
  uv run python scripts/generate_schemas.py

  step "verify committed schemas are unchanged"
  git diff --exit-code -- schemas

  step "ruff format"
  uv run ruff format --check .

  step "ruff check"
  uv run ruff check

  step "pyright"
  uv run pyright
}

run_full() {
  run_static_checks

  step "pytest"
  uv run pytest --durations=30 "$@"
}

run_fast() {
  if [ "$#" -ne 0 ]; then
    printf 'fast mode takes no extra arguments\n' >&2
    exit 2
  fi

  run_static_checks

  step "pytest smoke selection"
  uv run pytest "${pytest_prefix[@]}" "${smoke_paths[@]}"
}

shard_index() {
  local wanted="$1" index name
  for index in "${!shard_plan[@]}"; do
    IFS='|' read -r name _ _ _ <<< "${shard_plan[$index]}"
    if [ "$name" = "$wanted" ]; then
      printf '%s\n' "$index"
      return 0
    fi
  done
  return 1
}

run_shard() {
  if [ "$#" -ne 1 ]; then
    printf 'shard mode requires exactly one shard name\n' >&2
    exit 2
  fi

  local name="$1" index paths excludes needs_pdf_tools argument
  if ! index="$(shard_index "$name")"; then
    printf 'unknown shard: %s\n' "$name" >&2
    exit 2
  fi

  IFS='|' read -r _ paths excludes needs_pdf_tools <<< "${shard_plan[$index]}"
  local -a selection=()
  while IFS= read -r argument; do
    selection+=("$argument")
  done < <(shard_selection "$paths" "$excludes")

  if [ "$needs_pdf_tools" = "true" ]; then
    local tool
    for tool in qpdf pdftotext; do
      if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'shard %s requires %s on PATH\n' "$name" "$tool" >&2
        exit 2
      fi
    done
  fi

  step "pytest shard $name"
  uv run pytest "${pytest_prefix[@]}" "${selection[@]}"
}

shard_needs_pdf_tools() {
  if [ "$#" -ne 1 ]; then
    printf 'shard-needs-pdf-tools requires exactly one shard name\n' >&2
    exit 2
  fi

  local index _ needs_pdf_tools
  if ! index="$(shard_index "$1")"; then
    printf 'unknown shard: %s\n' "$1" >&2
    exit 2
  fi

  IFS='|' read -r _ _ _ needs_pdf_tools <<< "${shard_plan[$index]}"
  printf '%s\n' "$needs_pdf_tools"
}

print_json_strings() {
  local first=1 item
  for item in "$@"; do
    if [ "$first" -eq 0 ]; then
      printf ','
    fi
    printf '"%s"' "$item"
    first=0
  done
}

print_shard_plan() {
  local first=1 entry name paths excludes needs_pdf_tools index argument

  printf '{"schema_version":1,"smoke":{"paths":['
  print_json_strings "${smoke_paths[@]}"
  printf '],"pytest_arguments":['
  print_json_strings "${pytest_prefix[@]}" "${smoke_paths[@]}"
  printf ']},"shards":['

  for index in "${!shard_plan[@]}"; do
    IFS='|' read -r name paths excludes needs_pdf_tools <<< "${shard_plan[$index]}"
    # shellcheck disable=SC2206
    local selection=($paths)
    # shellcheck disable=SC2206
    local exclusions=($excludes)
    local -a arguments=()
    while IFS= read -r argument; do
      arguments+=("$argument")
    done < <(shard_selection "$paths" "$excludes")

    if [ "$first" -eq 0 ]; then
      printf ','
    fi
    printf '{"name":"%s","needs_pdf_tools":%s,"paths":[' "$name" "$needs_pdf_tools"
    print_json_strings "${selection[@]}"
    printf '],"excludes":['
    # Bash 3.2 rejects an empty array under `set -u`; expand only when present.
    print_json_strings ${exclusions[@]+"${exclusions[@]}"}
    printf '],"pytest_arguments":['
    print_json_strings "${pytest_prefix[@]}" "${arguments[@]}"
    printf ']}'
    first=0
  done

  printf ']}\n'
}

run_aggregate() {
  if [ "$#" -lt 2 ]; then
    printf 'aggregate mode requires <job>=<result> arguments\n' >&2
    exit 2
  fi

  local pair job result
  for pair in "$@"; do
    job="${pair%%=*}"
    result="${pair#*=}"
    if [ "$result" != "success" ]; then
      printf 'aggregate: required job %s reported %s\n' "$job" "${result:-missing}" >&2
      exit 1
    fi
  done

  printf 'aggregate: all required jobs succeeded\n'
}

mode="${1:-full}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$mode" in
  full)
    run_full "$@"
    ;;
  fast)
    run_fast "$@"
    ;;
  shard)
    run_shard "$@"
    ;;
  shard-plan)
    if [ "$#" -ne 0 ]; then
      printf 'shard-plan mode takes no extra arguments\n' >&2
      exit 2
    fi
    print_shard_plan
    ;;
  shard-needs-pdf-tools)
    shard_needs_pdf_tools "$@"
    ;;
  aggregate)
    run_aggregate "$@"
    ;;
  *)
    # Backward-compatible pass-through: pytest arguments, not a mode name.
    run_full "$mode" "$@"
    ;;
esac
