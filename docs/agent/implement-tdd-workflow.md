# Implementing a TDD

Run the Harness status command first.

```text
kotekomi-agent implement-tdd <tdd-path>
```

Treat the status record as the lifecycle authority.

Stop when the status is blocked.

Use the reported `next_action` and `producer_arguments`.

Resume the active run by repeating the same command. Use `--new-run` only after
the previous run is terminal. Use `--abandon-run <implementation-run-id>` only
when an operator has decided that a non-terminal run will not continue.

When the next action is `create_task_manifest`, create the manifest at `manifest_path`.

Use the task manifest schema and an existing manifest as the authoring contract.

Use the binding task identifier, TDD path, and TDD digest in that manifest.

Run `verification-plan`, `run-check`, and `verify-checks` for local verification.

Pass `--task-id` and `--run` from `producer_arguments` to every run-scoped
producer. Those commands write canonical evidence and update the run evidence
index; `--output` and `--markdown` are report copies, not evidence discovery.

Run `receipt-chain-status` before reporting completion.

After completion, run `tdd-metrics <tdd-path>` and then `tdd-score <tdd-path>`.

Use `tdd-metrics <tdd-path> --latest` or `--run <implementation-run-id>` only
when selecting one run. With no path or selector, metrics and scorecards cover
all known runs. Use `tdd-compare <tdd-path> <tdd-path>` for TDD inputs, or
repeat `--scorecard <scorecard-json>` for explicit scorecard records.

Report the requested and primary TDD paths, aliases, digest, task identifier, run identifier, lifecycle evidence, metrics path, and scorecard path.

Use one local command block per operator action.

Ask for the command output after each operator action.

Keep failed output as Harness evidence.
