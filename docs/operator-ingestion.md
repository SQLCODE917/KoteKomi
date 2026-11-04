# Operator Guide: Ingestion, Replay, and Review

This guide describes the current ingestion workflow.
It matches the commands that `uv run kotekomi --help`, `uv run kotekomi-live-replay --help`,
and the scripts in `scripts/` accept.

## 1. Configure the runtime

KoteKomi reads one TOML file.
Pass it with `--config <path>` or place it at the default location.

```toml
ledger_path = "/absolute/path/kotekomi.db"
archive_path = "/absolute/path/archive"
runtime_profile = "hp8-canonical"

[processing]
representation_policy_version = "deposited-source-v1"

[runtime_profiles.hp8-canonical]
adapter = "lm_studio"
endpoint = "http://127.0.0.1:1234/v1"
model = "qwen2.5-14b-instruct"
timeout_seconds = 300
context_tokens = 32768
max_output_tokens = 4096

[model_resources]
root = "/absolute/path/model-resources"
```

Use `runtime_profile = "fixture"` only for deterministic local checks.
A fixture run uses deterministic analyzer and model responses.

## 2. Fresh ingestion

Terminal ingestion persists extraction and the derived composition outcomes.
It prints progress and exits with the ingestion code.

```bash
uv run kotekomi --config <kotekomi.toml> ingest <source-file> --url <source-url>
```

Interactive or plain live ingestion runs the same workflow and adds presentation.

```bash
uv run kotekomi-live-replay --config <kotekomi.toml> --source <source-file> \
  --url <source-url> --state-root <state-root>
```

Add `--plain` for ANSI-free output. Without a terminal, the command selects plain output.
`--paragraph <n>` limits the run to one one-based paragraph ordinal.
`--delay <seconds>` sets the pause between stored phase results.

All three interfaces persist the same semantic outcome: extraction, the coverage report,
and one composition record per Event. A composition failure reports one diagnostic line on
the error stream and never changes the ingestion exit code.

## 3. Durable output paths

| Path | Content |
|---|---|
| `<state-root>/kotekomi.db` | Ledger |
| `<state-root>/archive/` | Archive |
| `<state-root>/token-artifacts/<paragraph-node>.json` | Pinned dependency tokens for one Event-bearing paragraph |
| `<state-root>/composition-outcomes/<event-id>.json` | One Event composition outcome |

A composition outcome is either a hold with a hold reason or a composed Assertion with
supporting spans.

## 4. Saved replay

Saved replay reads persisted state and starts no ingestion.
Point it at an existing state root.

```bash
uv run kotekomi-live-replay --state-root <state-root>
```

`--ingestion-run <igr_...>` selects one stored run.
`--paragraph <n>` and `--delay <seconds>` behave as above.

The live screen shows a `composition` section for every Event that realized a trigger.
Press `w` to switch between the annotated body and the scrollable output pane.
The output pane keeps warning and error lines that ingestion wrote to its error stream.
Press `c` to copy the current paragraph summary.
`[` and `]` move between paragraphs.

## 5. Review a candidate and accept an occurrence

Ingestion produces grounding candidates, not accepted identities.
A candidate is reviewable when HP-3 marks it eligible and links it to an external
identity. `ingested_grounding_candidates` returns those candidates bound to their exact
source occurrence.

Follow these steps.

1. Inspect the run: `uv run kotekomi ingestions list`, then
   `uv run kotekomi ingestions show <igr_...>`.
2. Inspect one paragraph's typed evidence:
   `uv run kotekomi ingestions paragraph <igr_...> --node <node-id> --phase hp3_grounding`.
3. Record the review decision through `propose_identity_occurrence`, then
   `accept_identity_occurrence`.
   Acceptance validates the identity, the replayable `EvidenceTarget`, the occurrence, and
   its `ProvenanceActivity` together, and commits all of them or none.

Before the decision, the Event stays held with a visible reason.
After the decision, recomposition can use the accepted reference.

## 6. Explicit recomposition

Approval does not recompose automatically.
Run the explicit command after an accepted occurrence exists.

```bash
uv run python scripts/recompose_ingested_event.py --request <request.json> \
  --ledger <state-root>/kotekomi.db --out <state-root>/composition-outcomes/<event-id>.json
```

The command writes through the same composition Adapter as ingestion and replay, so the
record is validated and replaced atomically.
Reload replay to see the Event change from held to composed.

## 7. Completion checks

- Ingestion exits with code 0 and the Ledger holds one new IngestionRun.
- `<state-root>/composition-outcomes/` holds one record per Event the run realized.
- Every record names either a hold reason or a composed Assertion with a supporting span.
- Saved replay starts no ingestion and shows the same composition status.
- After an accepted occurrence and explicit recomposition, the same Event reports composed.

## 8. Warning and error output

Ingestion writes warnings to the error stream.
The interactive screen shows those lines in the output pane, so a warning is not lost when
the screen redraws.
Plain and terminal modes write them directly to standard error.
A derived composition failure appears as one `Composition pass failed: ...` line.
