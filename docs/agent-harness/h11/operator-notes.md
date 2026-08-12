# H11 Operator Notes

## Required main lifecycle shape

Use the main phase only with all three revision arguments:

```bash
uv run kotekomi-agent lifecycle-check .agent/tasks/TASK.toml \
  --phase main \
  --main-base MAIN_BASE \
  --verified VERIFIED_CANDIDATE \
  --head MAIN_MERGE
```

## Candidate order

Candidate lifecycle is an early gate. Run it immediately after candidate commit and before dogfood verification execution, before candidate CI, and before any main merge work.
