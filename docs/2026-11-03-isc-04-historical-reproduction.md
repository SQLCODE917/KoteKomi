# TDD: Separate Historical Reproduction from Current Regressions

- Status: Accepted
- Deliverable: ISC-04
- Parent: [Ingestion Stabilization](2026-11-03-ingestion-stabilization-agile-package.md)

## 1. User outcome

Historical reproduction verifies the original evidence at its pinned revision.
Current regressions verify reviewed behaviour and run after an ordinary code move.

## 2. Current behaviour before this change

One development contract file bound four digests: reviewed policy records, reviewed
decision texts, renderer source, and scoring source.
Every current regression compared all four with the live code, so a behaviour-preserving
move or import change required a manual rebind.
The first correction removed that comparison for all four digests at once.

## 3. Correction: approve reviewed content, adopt only implementation bindings

Reviewed content is approval evidence and stays frozen.
The contract loader verifies two hashes against `reviewed_expectations.json`:

- `policy_records_sha256` for the reviewed policy records.
- `thresholds_sha256` for the reviewed decision texts and signal definitions.

A changed eligibility rule, boundary rule, none rule, or signal definition fails with a
validation error before any record loads.
Only `renderer_sha256` and `scoring_rules_sha256` follow the live implementation, so a
behaviour-preserving move needs no rebind and no reviewed text can change silently.

## 4. Preserved behaviour

- Response replay, approval membership, route binding, comparison recomputation, and
  tamper rejection keep their negative tests.
- A changed behavioural expectation requires an explicit reviewed edit of the
  expectations file, never a regenerated expectation from the implementation.
- Historical reproduction keeps its pinned revision and recorded fingerprint.

## 5. Acceptance tests

| Check | Test |
|---|---|
| ISC-04-A | `test_behavior_preserving_move_needs_no_contract_rebind` |
| ISC-04-B | the report negative tests in `test_semantic_instruction_discrimination_runner.py` |
| ISC-04-C | `scripts/run_r18_historical_reproduction.sh` result record |
| ISC-04-D | `docs/CHECK_PLAN.md` historical and current sections |
| Altered reviewed text | `test_altered_reviewed_decision_text_is_rejected` |

## 6. Verification

- `uv run pytest packages/pipelines/tests/test_semantic_instruction_discrimination_runner.py -q`
- `bash scripts/run_r18_historical_reproduction.sh` at the pinned revision.
