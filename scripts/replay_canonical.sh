#!/usr/bin/env bash
#
# replay_canonical.sh
#
# No-config end-to-end demo: run the canonical HP-8 ingestion once, then replay
# every paragraph's accepted HP-8 stage annotations line by line.
#
# This is a thin, deterministic wrapper around two already-idempotent pieces:
#
#   1. scripts/canonical_test_ingest.sh - the canonical end-to-end check that
#      ingests the locked Anthropic/DoD PDF through the public Hybrid Pipeline
#      and preserves durable Ledger/Archive evidence under a state root.
#   2. kotekomi-replay - the sacrificial, read-only replay reader
#      (packages/pipelines/src/kotekomi_pipelines/replay_reader/) that renders
#      each paragraph's HP-1..HP-10 stage annotations.
#
# Config resolution mirrors scripts/canonical_test_ingest.sh: an explicit
# --config flag or KOTEKOMI_CONFIG wins, then ./kotekomi.toml, then the XDG
# user location. The model runtime in that config must be a real (non-fixture)
# adapter for stage annotations to be produced.
#
# Usage:
#   scripts/replay_canonical.sh [--config PATH] [--state-root PATH] [--delay SEC]
#                               [--paragraph N] [--reuse-state] [--help]
#
# Environment (flags take precedence over environment):
#   KOTEKOMI_CONFIG          Path to kotekomi.toml (see resolution above).
#   KOTEKOMI_REPLAY_STATE    Isolated Ledger/Archive state root.
#                            Default: data/canonical/replay-state
#   KOTEKOMI_REPLAY_DELAY    Seconds between reveal lines during replay.
#                            Default: 0.12 (use 0 to render whole blocks at once)
#   KOTEKOMI_REPLAY_REUSE_STATE  When set (="1"), skip re-ingesting and reuse an
#                            already completed state root.
#
# Success criteria:
#   - scripts/canonical_test_ingest.sh reports PASS (exit status 0), and
#   - kotekomi-replay prints one annotated block per paragraph (exit status 0).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCRIPT_PATH="${SCRIPT_DIR}/$(basename -- "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd -- "${REPO_ROOT}"

INGEST_SCRIPT="${SCRIPT_DIR}/canonical_test_ingest.sh"

# --- Option defaults ---------------------------------------------------------
CONFIG="${KOTEKOMI_CONFIG:-}"
STATE_ROOT="${KOTEKOMI_REPLAY_STATE:-data/canonical/replay-state}"
DELAY="${KOTEKOMI_REPLAY_DELAY:-0.12}"
REUSE_STATE="${KOTEKOMI_REPLAY_REUSE_STATE:-}"
PARAGRAPH=""

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

# --- Argument parsing --------------------------------------------------------
while (($# > 0)); do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || die "--config requires a path"
      CONFIG="$2"
      shift 2
      ;;
    --state-root)
      [[ $# -ge 2 ]] || die "--state-root requires a path"
      STATE_ROOT="$2"
      shift 2
      ;;
    --delay)
      [[ $# -ge 2 ]] || die "--delay requires seconds"
      DELAY="$2"
      shift 2
      ;;
    --paragraph)
      [[ $# -ge 2 ]] || die "--paragraph requires a one-based ordinal"
      PARAGRAPH="$2"
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

# --- Preflight (cheap, deterministic) ----------------------------------------
command -v uv >/dev/null 2>&1 \
  || die "uv is not on PATH; install it or activate its environment"

[[ -f "${INGEST_SCRIPT}" ]] || die "canonical ingest script missing: ${INGEST_SCRIPT}"

# --- Run the canonical ingestion once ----------------------------------------
ingest_args=(--state-root "${STATE_ROOT}")
[[ -n "${CONFIG}" ]] && ingest_args+=(--config "${CONFIG}")
[[ "${REUSE_STATE}" == "1" ]] && ingest_args+=(--reuse-state)

info "ingesting canonical HP-8 document into ${STATE_ROOT}"
"${INGEST_SCRIPT}" "${ingest_args[@]}"

# --- Replay every paragraph, live --------------------------------------------
replay_args=(--state-root "${STATE_ROOT}" --delay "${DELAY}")
[[ -n "${PARAGRAPH}" ]] && replay_args+=(--paragraph "${PARAGRAPH}")

info "replaying HP-8 stage annotations"
uv run kotekomi-replay "${replay_args[@]}"