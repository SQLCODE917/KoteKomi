#!/usr/bin/env bash
#
# canonical_test_ingest.sh
#
# Idempotent end-to-end check: ingest the locked Anthropic/DoD PDF from raw/
# through the public Hybrid Pipeline and verify it produces review-ready
# candidates. This is a thin, deterministic wrapper around the HP-8
# document-orchestration verifier (scripts/verify_hp8_document_orchestration.py).
#
# The verifier is already idempotent: it isolates its own Ledger/Archive in a
# fresh temporary directory, ingests the locked source twice (forward run +
# zero-call replay), and overwrites a single report file. This wrapper only
# adds a cheap, deterministic preflight so a long model run is never started
# on a missing config, a missing source, or a modified PDF.
#
# Usage:
#   scripts/canonical_test_ingest.sh [--config PATH] [--output PATH]
#                                    [--state-root PATH] [--reuse-state]
#                                    [--help]
#
# Environment (flags take precedence over environment):
#   KOTEKOMI_CONFIG           Path to kotekomi.toml. Default resolution is
#                             ./kotekomi.toml if present, otherwise
#                             "${XDG_CONFIG_HOME:-$HOME/.config}/kotekomi/kotekomi.toml".
#   KOTEKOMI_HP8_REPORT       Report output path.
#                             Default: data/canonical/hp8-document-orchestration-report.json
#   KOTEKOMI_HP8_STATE        Optional isolated Ledger/Archive state root to
#                             preserve durable evidence across runs.
#   KOTEKOMI_HP8_REUSE_STATE  When set (="1"), rebuild the report from an
#                             already-completed state root instead of ingesting.
#
# Success criteria:
#   - exit status 0, and
#   - the printed JSON summary has "passed": true, and
#   - "paragraph_proposed_changes" > 0 (candidates were actually produced).
#
# The model runtime in KOTEKOMI_CONFIG must be a real (non-"fixture") adapter
# for candidates to be produced; a fixture adapter yields 0 proposed changes
# and the verifier reports a finding (exit status 1).

set -euo pipefail

# --- Paths -------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCRIPT_PATH="${SCRIPT_DIR}/$(basename -- "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd -- "${REPO_ROOT}"

SOURCE_PDF="raw/Anthropic–United_States_Department_of_Defense_dispute.pdf"
SOURCE_URL="https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute"
SOURCE_SHA256="c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624"
VERIFIER="scripts/verify_hp8_document_orchestration.py"

# --- Option defaults ---------------------------------------------------------
CONFIG="${KOTEKOMI_CONFIG:-}"
OUTPUT="${KOTEKOMI_HP8_REPORT:-data/canonical/hp8-document-orchestration-report.json}"
STATE_ROOT="${KOTEKOMI_HP8_STATE:-}"
REUSE_STATE="${KOTEKOMI_HP8_REUSE_STATE:-}"

# --- Helpers -----------------------------------------------------------------
die() {
  printf '\033[1;31merror:\033[0m %s\n' "$*" >&2
  exit 1
}

info() {
  printf '\033[1;34m==>\033[0m %s\n' "$*" >&2
}

usage() {
  sed -n '2,/^set -euo pipefail$/p' "${SCRIPT_PATH}" \
    | sed -e 's/^# \{0,1\}//' -e '/^set -euo pipefail$/d'
  exit 0
}

resolved_config() {
  # Mirror the CLI precedence: explicit flag/env, then ./kotekomi.toml, then
  # the XDG-style user location (without creating it).
  if [[ -n "${CONFIG}" ]]; then
    printf '%s\n' "${CONFIG}"
    return
  fi
  if [[ -f "kotekomi.toml" ]]; then
    printf '%s\n' "$(pwd -P)/kotekomi.toml"
    return
  fi
  printf '%s\n' "${XDG_CONFIG_HOME:-${HOME}/.config}/kotekomi/kotekomi.toml"
}

sha256_file() {
  local file="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${file}" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${file}" | awk '{print $1}'
  else
    python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "${file}"
  fi
}

# --- Argument parsing --------------------------------------------------------
while (($# > 0)); do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || die "--config requires a path"
      CONFIG="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || die "--output requires a path"
      OUTPUT="$2"
      shift 2
      ;;
    --state-root)
      [[ $# -ge 2 ]] || die "--state-root requires a path"
      STATE_ROOT="$2"
      shift 2
      ;;
    --reuse-state)
      REUSE_STATE=1
      shift
      ;;
    --help | -h)
      usage
      ;;
    *)
      die "unknown argument: $1 (try --help)"
      ;;
  esac
done

# --- Resolve variables -------------------------------------------------------
CONFIG="$(resolved_config)"
[[ -n "${CONFIG}" ]] || die "could not resolve a config path"

# --- Preflight (cheap, deterministic — fails before any model work) ----------
command -v uv >/dev/null 2>&1 || die "uv is not on PATH; install it or activate its environment"

[[ -f "${CONFIG}" ]] || die "config not found: ${CONFIG} (set KOTEKOMI_CONFIG or pass --config)"

[[ -f "${SOURCE_PDF}" ]] || die "canonical source missing: ${SOURCE_PDF}"

actual_sha="$(sha256_file "${SOURCE_PDF}")"
[[ "${actual_sha}" == "${SOURCE_SHA256}" ]] \
  || die "canonical source sha256 mismatch (expected ${SOURCE_SHA256}, got ${actual_sha})"

[[ -f "${VERIFIER}" ]] || die "verifier missing: ${VERIFIER}"

if [[ -n "${STATE_ROOT}" ]]; then
  if [[ -e "${STATE_ROOT}" && "${REUSE_STATE}" != "1" ]]; then
    die "state root already exists: ${STATE_ROOT} (set KOTEKOMI_HP8_REUSE_STATE=1 or pass --reuse-state to rebuild)"
  fi
  if [[ ! -e "${STATE_ROOT}" && "${REUSE_STATE}" == "1" ]]; then
    die "state root does not exist, cannot reuse: ${STATE_ROOT}"
  fi
fi

mkdir -p -- "$(dirname -- "${OUTPUT}")"

# --- Build the verifier invocation ------------------------------------------
args=(
  --config "${CONFIG}"
  --source "${SOURCE_PDF}"
  --url "${SOURCE_URL}"
  --output "${OUTPUT}"
)
if [[ -n "${STATE_ROOT}" ]]; then
  args+=(--state-root "${STATE_ROOT}")
fi
if [[ "${REUSE_STATE}" == "1" ]]; then
  args+=(--reuse-state)
fi

info "config:      ${CONFIG}"
info "source:      ${SOURCE_PDF} (sha256 ${actual_sha:0:12}…)"
info "output:      ${OUTPUT}"
if [[ -n "${STATE_ROOT}" ]]; then
  info "state-root:  ${STATE_ROOT}"
  [[ "${REUSE_STATE}" == "1" ]] && info "reuse-state: yes"
fi

# --- Run ---------------------------------------------------------------------
set +e
uv run python "${VERIFIER}" "${args[@]}"
rc=$?
set -e

# --- Report terminal result --------------------------------------------------
if [[ ${rc} -eq 0 ]]; then
  printf '\033[1;32mPASS\033[0m\n' >&2
else
  printf '\033[1;31mFAIL\033[0m\n' >&2
fi
printf 'report: %s\n' "${OUTPUT}" >&2
exit "${rc}"