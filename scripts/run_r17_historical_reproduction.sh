#!/usr/bin/env bash
# Reproduce the frozen R17 semantic-selection historical evaluation against its
# pinned pre-R19 implementation revision.
#
# Historical reproducibility is separate from current regression: the frozen
# verifier re-runs the live composer and requires byte-identical probes, so it
# only passes against the pre-R19 composer checkout it was frozen with. The
# current checkout keeps one live composer for R19 and must not reproduce the
# frozen probe.
#
# This script creates an isolated git worktree at the pinned commit with its own
# `uv` environment, so editable package imports resolve to that checkout rather
# than the current repository. It is a long-running handoff: start it, monitor it,
# and inspect the durable result record afterwards.
#
# The re-run is deterministic and leaves one typed result record:
#   data/r17-semantic-selection-contract-runs/historical-reproduction-<short>.json
# recording, separately:
#   * verifier_summary_sha256 -- the canonical SHA-256 of the frozen verifier's
#     sealed status/count summary (the verifier's own proof bound);
#   * report_fingerprint -- the sealed R17 report `result_fingerprint`, rebuilt by
#     `scripts/run_semantic_selection_contract.py evaluate` and re-verified by
#     `show` inside the pinned checkout.
set -euo pipefail

R17_BASELINE="${R17_BASELINE:-39988621c3e565f1b4f1af260f3fe7cd280e0e49}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE="${WORKTREE:-$REPO_ROOT/.git-worktrees/r17-baseline-${R17_BASELINE:0:12}}"
RUN_ROOT="$REPO_ROOT/data/r17-semantic-selection-contract-runs"
RESULT_FILE="${RESULT_FILE:-$RUN_ROOT/historical-reproduction-${R17_BASELINE:0:12}.json}"

echo "==> Pin: $R17_BASELINE"

# A linked git worktree stores its git metadata in a `.git` file, not a
# directory, so presence is checked with -e (which holds for both file and dir).
if [ -e "$WORKTREE/.git" ]; then
  actual="$(git -C "$WORKTREE" rev-parse HEAD 2>/dev/null || true)"
  if [ "$actual" != "$R17_BASELINE" ]; then
    echo "Error: worktree HEAD '$actual' != pinned baseline '$R17_BASELINE'." >&2
    echo "Remove '$WORKTREE' and re-run, or pass an explicit WORKTREE." >&2
    exit 1
  fi
  if [ -n "$(git -C "$WORKTREE" status --porcelain)" ]; then
    echo "Error: worktree '$WORKTREE' has uncommitted changes; expected a clean checkout." >&2
    exit 1
  fi
  echo "==> Reusing clean pinned worktree: $WORKTREE"
else
  git -C "$REPO_ROOT" worktree add --detach "$WORKTREE" "$R17_BASELINE"
fi

echo "==> Isolate environment (editable packages resolve to the worktree)."
# A fresh sync inside the worktree installs its own .venv and editable packages
# bound to the pinned revision, independent of the current checkout's environment.
( cd "$WORKTREE" && uv sync --frozen )

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
VERIFY_STDOUT="$TMP_DIR/verify.stdout"
VERIFY_STDERR="$TMP_DIR/verify.stderr"
PYTEST_OUT="$TMP_DIR/pytest.out"
EVAL_STDOUT="$TMP_DIR/evaluate.stdout"
EVAL_STDERR="$TMP_DIR/evaluate.stderr"
SHOW_STDOUT="$TMP_DIR/show.stdout"
SHOW_STDERR="$TMP_DIR/show.stderr"

echo "==> Reproduce the frozen R17 evaluation (verify_policy_records.py)."
set +e
( cd "$WORKTREE" && uv run python data/r17-semantic-selection-contract/verify_policy_records.py ) \
  > "$VERIFY_STDOUT" 2> "$VERIFY_STDERR"
VERIFY_STATUS=$?
set -e
if [ "$VERIFY_STATUS" -eq 0 ]; then
  cat "$VERIFY_STDOUT"
else
  echo "verify_policy_records.py failed (exit $VERIFY_STATUS):" >&2
  cat "$VERIFY_STDERR" >&2
fi

echo "==> Reproduce the frozen digest-boundary and contract tests."
set +e
( cd "$WORKTREE" && uv run pytest -q \
    packages/application/tests/test_r17_verifier_digest_boundary.py \
    packages/application/tests/test_semantic_selection_contract.py ) \
  > "$PYTEST_OUT" 2>&1
PYTEST_STATUS=$?
set -e
tail -n 4 "$PYTEST_OUT" || true
PYTEST_SUMMARY="$(tail -n 1 "$PYTEST_OUT" | tr -d '\n\r')"

echo "==> Rebuild and re-verify the sealed R17 report fingerprint."
EXPECTED_FINGERPRINT="$(cd "$WORKTREE" && uv run python -c 'import json; print(json.load(open("data/r17-semantic-selection-contract-runs/run-001/run.json"))["result_fingerprint"])')"
set +e
( cd "$WORKTREE" && uv run python scripts/run_semantic_selection_contract.py evaluate ) \
  > "$EVAL_STDOUT" 2> "$EVAL_STDERR"
EVAL_STATUS=$?
( cd "$WORKTREE" && uv run python scripts/run_semantic_selection_contract.py show ) \
  > "$SHOW_STDOUT" 2> "$SHOW_STDERR"
SHOW_STATUS=$?
set -e
if [ "$EVAL_STATUS" -eq 0 ]; then
  cat "$EVAL_STDOUT"
else
  echo "run_semantic_selection_contract.py evaluate failed (exit $EVAL_STATUS):" >&2
  cat "$EVAL_STDERR" >&2
fi
if [ "$SHOW_STATUS" -ne 0 ]; then
  echo "run_semantic_selection_contract.py show failed (exit $SHOW_STATUS):" >&2
  cat "$SHOW_STDERR" >&2
fi

REPORT_FINGERPRINT=""
SHOW_FINGERPRINT=""
if [ "$EVAL_STATUS" -eq 0 ]; then
  REPORT_FINGERPRINT="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["result_fingerprint"])' "$EVAL_STDOUT")"
fi
if [ "$SHOW_STATUS" -eq 0 ]; then
  SHOW_FINGERPRINT="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["result_fingerprint"])' "$SHOW_STDOUT")"
fi
REPORT_REPRODUCED="no"
if [ "$REPORT_FINGERPRINT" = "$EXPECTED_FINGERPRINT" ] && [ "$SHOW_FINGERPRINT" = "$EXPECTED_FINGERPRINT" ]; then
  REPORT_REPRODUCED="yes"
fi

if [ "$VERIFY_STATUS" -ne 0 ] || [ "$PYTEST_STATUS" -ne 0 ] \
    || [ "$EVAL_STATUS" -ne 0 ] || [ "$SHOW_STATUS" -ne 0 ] \
    || [ "$REPORT_REPRODUCED" != "yes" ]; then
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
R17_BASELINE="$R17_BASELINE" \
REVISION="$REVISION" \
WORKTREE="$WORKTREE" \
VERIFY_STDOUT="$VERIFY_STDOUT" \
VERIFY_STATUS="$VERIFY_STATUS" \
PYTEST_STATUS="$PYTEST_STATUS" \
PYTEST_SUMMARY="$PYTEST_SUMMARY" \
EVAL_STATUS="$EVAL_STATUS" \
SHOW_STATUS="$SHOW_STATUS" \
EXPECTED_FINGERPRINT="$EXPECTED_FINGERPRINT" \
REPORT_FINGERPRINT="$REPORT_FINGERPRINT" \
SHOW_FINGERPRINT="$SHOW_FINGERPRINT" \
REPORT_REPRODUCED="$REPORT_REPRODUCED" \
OVERALL="$OVERALL" \
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

baseline = os.environ["R17_BASELINE"]
result_file = Path(os.environ["RESULT_FILE"])
summary_raw = Path(os.environ["VERIFY_STDOUT"]).read_text().strip()
verify_status = int(os.environ["VERIFY_STATUS"])

verify_summary = None
if verify_status == 0 and summary_raw:
    verify_summary = json.loads(summary_raw)

verifier_summary_sha256 = None
if verify_summary is not None:
    verifier_summary_sha256 = hashlib.sha256(
        json.dumps(
            verify_summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

record = {
    "schema_version": "r17_historical_reproduction_v1",
    "baseline_revision": baseline,
    "reproduction_revision": os.environ["REVISION"],
    "worktree": os.environ["WORKTREE"],
    "verification_outcomes": {
        "verify_policy_records": {
            "exit_code": verify_status,
            "status": "passed" if verify_status == 0 else "failed",
            "summary": verify_summary,
        },
        "pytest": {
            "exit_code": int(os.environ["PYTEST_STATUS"]),
            "status": "passed" if os.environ["PYTEST_STATUS"] == "0" else "failed",
            "summary_line": os.environ["PYTEST_SUMMARY"],
        },
        "report_reproduction": {
            "evaluate_exit_code": int(os.environ["EVAL_STATUS"]),
            "show_exit_code": int(os.environ["SHOW_STATUS"]),
            "expected_fingerprint": os.environ["EXPECTED_FINGERPRINT"],
            "rebuilt_fingerprint": os.environ["REPORT_FINGERPRINT"],
            "show_fingerprint": os.environ["SHOW_FINGERPRINT"],
            "status": "passed" if os.environ["REPORT_REPRODUCED"] == "yes" else "failed",
        },
    },
    "verifier_summary_sha256": verifier_summary_sha256,
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