# IRA Operator Handoff: Fresh-Root Acceptance Run

Use a fresh state root. Do not reuse `data/operator-r20-20261103-150517`: that retained run
contains approvals created by earlier automated tests.

## 1. Prepare the fresh root

```bash
ROOT="$PWD/data/ira-acceptance-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ROOT/state"
```

Write `"$ROOT/kotekomi.toml"` with absolute paths inside that root, the canonical runtime
profile, and your model-resource root:

```toml
ledger_path = "<ROOT>/state/kotekomi.db"
archive_path = "<ROOT>/state/archive"
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
root = "<absolute model-resources path>"
```

## 2. Ingest the PDF

```bash
uv run kotekomi --config "$ROOT/kotekomi.toml" ingest \
  "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf" --url "<source-url>"
uv run kotekomi --config "$ROOT/kotekomi.toml" ingestions list
```

## 3. Discover the new run's Event IDs

Each ingested Event persists one composition outcome named by its Event ID:

```bash
ls "$ROOT/state/composition-outcomes" | sed 's/\.json$//'
uv run python -c 'import json,sys,pathlib
root = pathlib.Path(sys.argv[1])
for path in sorted(root.glob("*.json")):
    record = json.loads(path.read_text())
    print(record["event_id"], record["status"], record.get("hold_reason"))' \
  "$ROOT/state/composition-outcomes"
```

## 3a. Identify the agreed Event by its trigger and source clause

`review event-packet` prints the trigger, the statement span, and the source passage, so it is the
actionable way to find the agreed `started` Event. Run it for every Event ID and keep one line per
Event:

```bash
for event in $(ls "$ROOT/state/composition-outcomes" | sed 's/\.json$//'); do
  uv run kotekomi --config "$ROOT/kotekomi.toml" review event-packet \
    --run <igr_...> --event "$event" > "$ROOT/packet-$event.json"
  uv run python -c 'import json,sys
packet = json.load(open(sys.argv[1]))
print(packet["event_id"], "|", packet["trigger"]["text"], "|", packet["statement"]["text"],
      "|", packet.get("hold_reason"))' "$ROOT/packet-$event.json"
done
```

Choose the line whose trigger is `started` and whose statement text is
`the US started the 2026 Iran war`. That Event ID is the one to review.

## 4. Review and recompose the agreed case

Agreed content: subject the United States government as an `Organization`, predicate
`started`, object `the 2026 Iran war`, affirmed/actual, secondary/direct_document.
Select the Event whose trigger is `started` and whose statement is
`the US started the 2026 Iran war`.

```bash
uv run kotekomi --config "$ROOT/kotekomi.toml" review event-packet \
  --run <igr_...> --event <sge_...>

uv run kotekomi --config "$ROOT/kotekomi.toml" review decide \
  --run <igr_...> --event <sge_...> --candidate-text US \
  --identity-kind organization --identity "new:United States" \
  --predicate started --assertion-type reported_observation \
  --source-authority secondary --attribution-basis direct_document \
  --reviewer <name>

uv run kotekomi --config "$ROOT/kotekomi.toml" review recompose \
  --run <igr_...> --event <sge_...>

uv run kotekomi review list --record-type Assertion \
  --ledger-path "$ROOT/state/kotekomi.db"
uv run kotekomi-live-replay --state-root "$ROOT/state"
```

## 5. Completion probes

```bash
uv run python -c 'import json,sys,pathlib
state = pathlib.Path(sys.argv[1])
outcomes = [json.loads(p.read_text()) for p in sorted((state / "composition-outcomes").glob("*.json"))]
composed = [r for r in outcomes if r["status"] == "composed"]
held = [r for r in outcomes if r["status"] != "composed"]
print("events", len(outcomes), "composed", len(composed), "held", len(held))
for record in composed:
    assertion = record.get("assertion")
    print(record["event_id"], assertion["predicate"] if assertion else None,
          assertion.get("object_value") if assertion else None)
reasons = {}
for record in held:
    key = record.get("hold_reason")
    reasons[key] = reasons.get(key, 0) + 1
print("holds", reasons)' "$ROOT/state"
```

Success requires:

- the selected Event reports `composed`, predicate `started`, object `the 2026 Iran war`;
- `review list --record-type Assertion` shows exactly one pending Assertion for it;
- replay shows the composition section with both supporting spans.

Durable paths: `<ROOT>/state/kotekomi.db`, `<ROOT>/state/archive/`,
`<ROOT>/state/token-artifacts/`, `<ROOT>/state/composition-outcomes/<sge_...>.json`.

## 5a. If the fresh run does not reproduce the case

A fresh model run may not reproduce the selected Event or its candidate.
If it does not, keep the run and report the exact missing stage or hold:
which paragraph has no Event, which Event realized no object, or which hold reason replaced
composition.
Do not substitute an older Event ID, and do not repair the output by hand.

## 6. Measures-report inputs to send back

- the fresh root path and the assigned `igr_...`;
- the selected `sge_...` and the reviewer name;
- the probe output above (events, composed, held, and holds by reason);
- the `review list --record-type Assertion` output for that Event;
- the number of review commands you ran and any manual repair you performed.
