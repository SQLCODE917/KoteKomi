# Operational Guidance

## Minimal AGENTS guidance

Do not put touched-path test rules into long prose instructions. Use this compact instruction instead:

```text
Before implementation and before candidate verification, run `kotekomi-agent verification-plan`.
Run every required check it returns.
Do not manually infer, omit, or replace the returned checks.
```

## Post-merge preflight

`preflight-task` is an execution-base readiness check. It should be run before implementation at the task execution base.

After a candidate is merged into main, HEAD is the merge commit, not the execution base. At that point, `preflight-task` is not the correct main gate.

Post-merge verification should use:

- local targeted checks,
- scope audit,
- budget audit,
- main CI,
- `lifecycle-check --phase main`,
- deterministic receipts.

## Main lifecycle command

Use main-specific flags:

```bash
uv run kotekomi-agent lifecycle-check MANIFEST \
  --phase main \
  --main-base MAIN_BASE \
  --verified VERIFIED_CANDIDATE \
  --head MAIN_MERGE
```

Do not substitute generic `--base` for `--main-base`. `--base` belongs to candidate-style range checks. Main lifecycle checks merge parent structure.

## H9 concrete invocation

```bash
uv run kotekomi-agent lifecycle-check \
  .agent/tasks/harness-09-task-ledger-accountability.toml \
  --phase main \
  --main-base 85cfb0992153a75ef2fb7824d64dc526bfce49f8 \
  --verified b97ea7a7910a5f2f3ea421961aad68db63549dab \
  --head 176443db0bab8aeda9f0c077f603e150a0f0a812
```
