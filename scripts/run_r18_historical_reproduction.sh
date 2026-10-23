#!/usr/bin/env bash
# Reproduce the frozen R18 semantic-instruction-discrimination run against its
# pinned pre-R19 implementation revision.
#
# R18 `prepare`/`report` re-verify the frozen R17 four-digest contract binding,
# whose scoring digest binds the live R4 composer source. The R19 composer change
# therefore makes the current checkout reject the frozen contract, so the
# historical R18 run reproduces only in the pre-R19 checkout that also holds the
# frozen R18 run root. That is commit `c46d5e6` (the R18 record commit, still
# pre-R19); the earlier R18 implementation commit `3998862` predates the frozen
# run data and cannot reproduce it. Current runner regression coverage instead
# uses an explicitly bound current test contract under
# `data/r18-current-test-contract`.
#
# This script creates an isolated git worktree at the pinned commit with its own
# `uv` environment, so editable package imports resolve to that checkout rather
# than the current repository. It is a long-running handoff: start it, monitor it,
# and inspect the durable result record afterwards.
#
# The re-run is deterministic and leaves one typed result record:
#   data/r18-semantic-instruction-discrimination-runs/historical-reproduction-<short>.json
# recording the sealed R18 report `result_fingerprint`, rebuilt offline by
# `scripts/run_semantic_instruction_discrimination.py report` (no model calls) and
# re-verified by `show` inside the pinned checkout, plus the frozen evidence
# rebuilding test suite.
set -euo pipefail

R18_BASELINE="${R18_BASELINE:-c46d5e6c15b81412ad86961d8306edce7e47554a}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE="${WORKTREE:-$REPO_ROOT/.git-worktrees/r18-baseline-${R18_BASELINE:0:12}}"
RUN_ROOT="$REPO_ROOT/data/r18-semantic-instruction-discrimination-runs"
RESULT_FILE="${RESULT_FILE:-$RUN_ROOT/historical-reproduction-${R18_BASELINE:0:12}.json}"

echo "==> Pin: $R18_BASELINE"

# A linked git worktree stores its git metadata in a `.git` file, not a
# directory, so presence is checked with -e (which holds for both file and dir).
if [ -e "$WORKTREE/.git" ]; then
  actual="$(git -C "$WORKTREE" rev-parse HEAD 2>/dev/null || true)"
  if [ "$actual" != "$R18_BASELINE" ]; then
    echo "Error: worktree HEAD '$actual' != pinned baseline '$R18_BASELINE'." >&2
    echo "Remove '$WORKTREE' and re-run, or pass an explicit WORKTREE." >&2
    exit 1
  fi
  if [ -n "$(git -C "$WORKTREE" status --porcelain)" ]; then
    echo "Error: worktree '$WORKTREE' has uncommitted changes; expected a clean checkout." >&2
    exit 1
  fi
  echo "==> Reusing clean pinned worktree: $WORKTREE"
else
  git -C "$REPO_ROOT" worktree add --detach "$WORKTREE" "$R18_BASELINE"
fi

echo "==> Isolate environment (editable packages resolve to the worktree)."
# A fresh sync inside the worktree installs its own .venv and editable packages
# bound to the pinned revision, independent of the current checkout's environment.
( cd "$WORKTREE" && uv sync --frozen )

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
PYTEST_OUT="$TMP_DIR/pytest.out"
REPORT_STDOUT="$TMP_DIR/report.stdout"
REPORT_STDERR="$TMP_DIR/report.stderr"
SHOW_STDOUT="$TMP_DIR/show.stdout"
SHOW_STDERR="$TMP_DIR/show.stderr"
RUN_COPY="$TMP_DIR/run-001"

EXPECTED_FINGERPRINT="$(cd "$WORKTREE" && uv run python -c 'import json; print(json.load(open("data/r18-semantic-instruction-discrimination-runs/run-001/report.json"))["result_fingerprint"])')"

# Copy the frozen run root so `report` does not rewrite the pinned evidence in place.
cp -R "$WORKTREE/data/r18-semantic-instruction-discrimination-runs/run-001" "$RUN_COPY"

echo "==> Rebuild and re-verify the sealed R18 report (offline, no model calls)."
set +e
( cd "$WORKTREE" && uv run python scripts/run_semantic_instruction_discrimination.py report --run-root "$RUN_COPY" ) \
  > "$REPORT_STDOUT" 2> "$REPORT_STDERR"
REPORT_STATUS=$?
( cd "$WORKTREE" && uv run python scripts/run_semantic_instruction_discrimination.py show --run-root "$RUN_COPY" ) \
  > "$SHOW_STDOUT" 2> "$SHOW_STDERR"
SHOW_STATUS=$?
set -e
if [ "$REPORT_STATUS" -eq 0 ]; then
  cat "$REPORT_STDOUT"
else
  echo "run_semantic_instruction_discrimination.py report failed (exit $REPORT_STATUS):" >&2
  cat "$REPORT_STDERR" >&2
fi
if [ "$SHOW_STATUS" -ne 0 ]; then
  echo "run_semantic_instruction_discrimination.py show failed (exit $SHOW_STATUS):" >&2
  cat "$SHOW_STDERR" >&2
fi

REPORT_FINGERPRINT=""
SHOW_FINGERPRINT=""
if [ "$REPORT_STATUS" -eq 0 ]; then
  REPORT_FINGERPRINT="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["result_fingerprint"])' "$REPORT_STDOUT")"
fi
if [ "$SHOW_STATUS" -eq 0 ]; then
  SHOW_FINGERPRINT="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["result_fingerprint"])' "$SHOW_STDOUT")"
fi
REPORT_REPRODUCED="no"
if [ "$REPORT_FINGERPRINT" = "$EXPECTED_FINGERPRINT" ] && [ "$SHOW_FINGERPRINT" = "$EXPECTED_FINGERPRINT" ]; then
  REPORT_REPRODUCED="yes"
fi

echo "==> Reproduce the frozen R18 evidence-rebuilding tests."
set +e
( cd "$WORKTREE" && uv run pytest -q \
    packages/application/tests/test_semantic_instruction_discrimination.py \
    packages/pipelines/tests/test_semantic_instruction_discrimination_runner.py ) \
  > "$PYTEST_OUT" 2>&1
PYTEST_STATUS=$?
set -e
tail -n 4 "$PYTEST_OUT" || true
PYTEST_SUMMARY="$(tail -n 1 "$PYTEST_OUT" | tr -d '\n\r')"

if [ "$REPORT_STATUS" -ne 0 ] || [ "$SHOW_STATUS" -ne 0 ] \
    || [ "$REPORT_REPRODUCED" != "yes" ] || [ "$PYTEST_STATUS" -ne 0 ]; then
  OVERALL="failed"
else
  OVERALL="passed"
fi
if [ "$REPORT_REPRODUCED" != "yes" ]; then
  echo "==> Sealed report fingerprint NOT reproduced:" >&2
  echo "    expected=$EXPECTED_FINGERPRINT rebuilt=$REPORT_FINGERPRINT show=$SHOW_FINGERPRINT" >&2
fi

REVISION="$(git -C "$REPO_ROOT" rev-parse HEAD)"

REPO_ROOT="$REPO_ROOT" \
RESULT_FILE="$RESULT_FILE" \
R18_BASELINE="$R18_BASELINE" \
REVISION="$REVISION" \
WORKTREE="$WORKTREE" \
REPORT_STATUS="$REPORT_STATUS" \
SHOW_STATUS="$SHOW_STATUS" \
EXPECTED_FINGERPRINT="$EXPECTED_FINGERPRINT" \
REPORT_FINGERPRINT="$REPORT_FINGERPRINT" \
SHOW_FINGERPRINT="$SHOW_FINGERPRINT" \
REPORT_REPRODUCED="$REPORT_REPRODUCED" \
PYTEST_STATUS="$PYTEST_STATUS" \
PYTEST_SUMMARY="$PYTEST_SUMMARY" \
OVERALL="$OVERALL" \
python3 - <<'PY'
import json
import os
from pathlib import Path

baseline = os.environ["R18_BASELINE"]
result_file = Path(os.environ["RESULT_FILE"])

record = {
    "schema_version": "r18_historical_reproduction_v1",
    "baseline_revision": baseline,
    "reproduction_revision": os.environ["REVISION"],
    "worktree": os.environ["WORKTREE"],
    "verification_outcomes": {
        "report_reproduction": {
            "report_exit_code": int(os.environ["REPORT_STATUS"]),
            "show_exit_code": int(os.environ["SHOW_STATUS"]),
            "expected_fingerprint": os.environ["EXPECTED_FINGERPRINT"],
            "rebuilt_fingerprint": os.environ["REPORT_FINGERPRINT"],
            "show_fingerprint": os.environ["SHOW_FINGERPRINT"],
            "status": "passed" if os.environ["REPORT_REPRODUCED"] == "yes" else "failed",
        },
        "pytest": {
            "exit_code": int(os.environ["PYTEST_STATUS"]),
            "status": "passed" if os.environ["PYTEST_STATUS"] == "0" else "failed",
            "summary_line": os.environ["PYTEST_SUMMARY"],
        },
    },
    "report_fingerprint": os.environ["REPORT_FINGERPRINT"],
    "overall": os.environ["OVERALL"],
}

result_file.parent.mkdir(parents=True, exist_ok=True)
result_file.write_text(
    json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"==> Recorded result: {result_file}")
PY

echo "==> Done ($OVERALL). Remove the worktree with:"
echo "    git -C '$REPO_ROOT' worktree remove --force '$WORKTREE'"

if [ "$OVERALL" = "failed" ]; then
  exit 1
fi