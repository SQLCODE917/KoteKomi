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

## 5. Review one Event and accept its prerequisites

Ingestion produces grounding candidates, not accepted identities.
The review commands read stored ingestion records, so the operator supplies decisions only:
no IDs, no evidence selectors, no dependency tokens, and no recomposition JSON.

1. List the runs and find the Event ID:

```bash
uv run kotekomi ingestions list
uv run kotekomi ingestions show <igr_...>
```

2. Open the Event's review packet. It shows the source passage, the trigger, the
   statement span, the review candidates, the required decisions, and any hold:

```bash
uv run kotekomi --config <config> review event-packet --run <igr_...> --event <sge_...>
```

3. Record the reviewed decision. `--identity new:<name>` proposes a new identity;
   `--identity existing:<act_...|org_...>` links an existing one. An accepted
   occurrence may sit inside the selected boundary, for example `US` inside `the US`:

```bash
uv run kotekomi --config <config> review decide --run <igr_...> --event <sge_...> \
  --candidate-text <exact candidate text> --identity-kind <actor|organization> \
  --identity <new:Name|existing:id> --predicate <predicate> \
  --assertion-type <reported_observation|reported_claim> \
  --source-authority <primary|secondary|tertiary|unknown> \
  --attribution-basis <direct_document|second_hand_report|anonymous_report|unknown> \
  --reviewer <name>
```

The command accepts the identity occurrence, its replayable `EvidenceTarget`, the
occurrence association, and a `ProvenanceActivity` together, and stores one approved
construction review bound to the run, paragraph, and source digest.
A repeated identical decision returns the stored review and writes nothing; a different
decision for the same Event is rejected.

4. A review hold stays visible. `unsupported_object_complement` means the object governs a
   clause or coordination this construction cannot represent; the Event stays held and no
   Assertion is proposed.

## 6. Explicit recomposition

Approval does not recompose automatically. Recomposition loads the stored tokens, the
constituent inventory, the accepted occurrence, the statement evidence, and the reviewed
decisions, then runs the retained composition path:

```bash
uv run kotekomi --config <config> review recompose --run <igr_...> --event <sge_...>
uv run kotekomi review list --record-type Assertion
```

The command prints the composed outcome and writes it through the same composition store
as ingestion and replay. The Assertion is `proposed`: a pending `ProposedChange` appears in
`review list`, and accepting it remains a separate review action.
`scripts/recompose_ingested_event.py` remains available when a full recomposition request
is already prepared.

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
