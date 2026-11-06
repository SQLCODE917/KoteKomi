# IPI Operator Comparison Procedure

- Status: Ready for the operator; no run has started
- Package: [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md)
- Order record: [Implementation order](2026-11-06-ipi-implementation-order.md)
- Manifest: `docs/2026-11-06-ipi-01-development-manifest.json`
- Protocol and rubric: [IPI-01](2026-11-06-ipi-01-passage-manifest-and-measurement-protocol.md)

The reserved evaluation alone decides whether the two implemented changes satisfy the package.
Counterfactual Event counts and agent-run journeys are mechanism evidence and never substitute for usable results or measured operator effort.

## 1. Preconditions

Do not start any timed step until every line below is true.

| Precondition | How to confirm |
| --- | --- |
| D3 targets approved | IPI-01 section 10 shows `approved` |
| D1 passage meanings approved after reading the complete paragraphs | IPI-01 section 10 shows `approved`; the reviewer has read every paragraph in section 3 |
| D2 rubric and timing protocol approved | IPI-01 section 10 shows `approved` |
| Development manifest released | `docs/2026-11-06-ipi-01-development-manifest.json` has `"status": "approved"`, a `reviewer`, and an `approved_on` date |
| Reserved partition sealed | `scripts/ipi_reserved_custody.py check` prints `status: valid`, and IPI-01 section 10 records the manifest digest |
| Product revisions frozen | baseline `7dc9a44`, final `2ec4737` |
| Live model reachable | `curl -s http://127.0.0.1:1234/v1/models` lists the configured model |

The comparator refuses a development manifest whose status is not `approved`, so an accidental early run fails closed.

## 2. Fixed revisions

| Condition | Revision |
| --- | --- |
| Baseline | `7dc9a44` |
| Final | `2ec4737` |

Use two worktrees so no checkout happens mid-run:

```bash
git worktree add ../kotekomi-baseline 7dc9a44
git worktree add ../kotekomi-final 2ec4737
```

Run each condition from its own worktree with `uv run`, so the command, the package code, and the model runtime belong to the condition's revision.
Run the measurement commands from the branch tip checkout, because `scripts/ipi_measure.py` with `--manifest` enforcement exists only there; the comparator reads result files and the manifest and touches no product state.

## 3. Ingestion model and ordinal discovery

`--paragraph` selects the paragraph the replay presents; it does not restrict ingestion.
A fresh run with `--paragraph <n>` still ingests the complete Document, then shows paragraph `n`.
The operator therefore runs **one live ingestion per Document per condition**, not one per passage.

The run ingests three Documents per condition and six in total:

| Document | Development passages | Live ingestions |
| --- | --- | --- |
| Anthropic-DoD dispute PDF | DEV-01 to DEV-04 | 1 per condition |
| AI Safety Institute PDF | DEV-05, DEV-06 | 1 per condition |
| Allen Safety Network PDF | the six reserved passages | 1 per condition |

Total live ingestions: six. No statement attempt triggers its own ingestion.

Each ingestion is started once and its wall-clock wait is recorded:

```bash
time uv run kotekomi-live-replay --config "<your-runtime-config>" --source "<document.pdf>" \
  --url "<source-url>" --state-root "<root>" --plain > "<root>/replay.txt" 2> "<root>/ingestion.err"
```

The command writes `<root>/kotekomi.toml` itself.
That generated file points at `<root>/kotekomi.db` and `<root>/archive` and copies the runtime profile and entity-linking settings from `<your-runtime-config>`.
Use the generated file as `$CONFIG` for every review command; do not hand-edit it, and record it if you ever do.

Ordinals are discovered once, not per condition:

| Passage | Document | Ordinal | How it is known |
| --- | --- | --- | --- |
| DEV-01 | Anthropic-DoD dispute PDF | 3 | deposited stored run, verified by anchor |
| DEV-02 | Anthropic-DoD dispute PDF | 4 | deposited stored run, verified by anchor |
| DEV-03 | Anthropic-DoD dispute PDF | 5 | deposited stored run, verified by anchor |
| DEV-04 | Anthropic-DoD dispute PDF | 8 | deposited stored run, verified by anchor |
| DEV-05 | AI Safety Institute PDF | discovered once | from the baseline condition's own replay output |
| DEV-06 | AI Safety Institute PDF | discovered once | from the baseline condition's own replay output |
| RES-01 to RES-06 | Allen Safety Network PDF | discovered once | from the baseline condition's own replay output |

Anchors to confirm each ordinal:

| Passage | Anchor |
| --- | --- |
| DEV-01 | `The United States Department of Defense began developing lethal autonomous weapons` |
| DEV-02 | `In Donald Trump's second presidency, Anthropic publicly disagreed` |
| DEV-03 | `Prior to the dispute, the Trump administration had integrated` |
| DEV-04 | `secretary  of  defense  Pete  Hegseth  announced  GenAI.mil` |
| DEV-05 | `At the AI Seoul Summit in May 2024` |
| DEV-06 | `the government of France created the Institut national` |
| Reserved | the anchors in the sealed manifest |

Discovery uses one already-required ingestion, not an extra live run:

```bash
uv run kotekomi-live-replay --state-root "<root>" --plain > "<root>/replay.txt"
grep -n "<anchor>" "<root>/replay.txt"
```

Search a short distinctive fragment, because extraction spacing can differ inside a passage.
The nearest preceding `paragraph <n>/<total>` line gives the ordinal; the same ordinals are used in both conditions.
If an anchor never appears because the extraction splits or rewrites the passage, record that representation limitation and keep the statement in the denominator as a hold; do not substitute another passage and do not ingest again to look for it.

## 4. Roots, configuration, and shared state

One root per Document per condition:

```text
<run-root>/development/baseline/anthropic/
<run-root>/development/baseline/aisi/
<run-root>/development/final/anthropic/
<run-root>/development/final/aisi/
<run-root>/reserved/baseline/allen/
<run-root>/reserved/final/allen/
```

Each root holds its own `kotekomi.toml`, written by the ingestion command with this shape:

```toml
ledger_path = "<root>/kotekomi.db"
archive_path = "<root>/archive"
runtime_profile = "hp8-canonical"

[processing]
representation_policy_version = "deposited-source-v1"

[runtime_profiles.hp8-canonical]
adapter = "lm_studio"
endpoint = "http://127.0.0.1:1234/v1"
model = "qwen2.5-14b-instruct"
timeout_seconds = 300.0
context_tokens = 16384
max_output_tokens = 2048

[model_resources]
root = "<model-resources-root>"

[entity_linking]
adapter = "refined"
timeout_seconds = 300.0
```

`CONFIG="<root>/kotekomi.toml"` in every command below, including `review list`.

Shared state inside one root is disclosed and matched:

- All statements from one Document share that root's accepted identities, construction reviews, proposals, and composition outcomes.
- Both conditions use the same statement order within each root, so the sharing acts the same way in both.
- No state crosses Documents; there is no root shared between a development and a reserved passage.
- The root is created once per condition and never re-ingested between statement attempts.

Shared setup time:

- Record each Document ingestion's waiting time in the run log when it finishes.
- The condition result file carries their sum in `setup_waiting_seconds`.
- No statement row includes ingestion time.
- The report adds `setup_waiting_seconds` to the row waits when it reports total waiting time, so shared cost is counted once and never charged per statement.

## 5. One statement attempt

Run from the condition's worktree, after that Document's ingestion has finished.
Start the clock when you begin locating the Event and its packet; the ingestion is already complete and is not part of the row.

```bash
CONFIG="<root>/kotekomi.toml"
uv run kotekomi --config "$CONFIG" ingestions list
uv run kotekomi --config "$CONFIG" ingestions show <igr_...>
uv run kotekomi --config "$CONFIG" review event-packet --run <igr_...> --event <sge_...>
uv run kotekomi --config "$CONFIG" review decide --run <igr_...> --event <sge_...> \
  --candidate-text "<candidate>" --identity-kind <actor|organization> \
  --identity <new:Name|existing:id> --predicate "<predicate>" \
  --assertion-type <reported_observation|reported_claim> \
  --source-authority <primary|secondary|tertiary|unknown> \
  --attribution-basis <direct_document|second_hand_report|anonymous_report|unknown> \
  --reviewer "<name>"
uv run kotekomi --config "$CONFIG" review recompose --run <igr_...> --event <sge_...>
uv run kotekomi --config "$CONFIG" review list --record-type Assertion
uv run kotekomi-live-replay --state-root "<root>" --ingestion-run <igr_...> --paragraph <ordinal> --plain
```

Timing rules:

- Active time is the interval in which you work on the statement; it excludes every recorded wait.
- Waiting time is every command delay you record, long or short; it is added to waiting, never to active.
- Record a substantive correction when you change an identity, predicate, assertion type, authority, attribution basis, or candidate after seeing the first outcome.
- Record a command retry when you repeat an invocation after an error; it is separate from a substantive correction.
- Stop at five active minutes and record `timeout`.

Per-statement row, written into the condition result file:

| Field | Value |
| --- | --- |
| `reference_id` | The manifest identifier |
| `outcome` | `usable`, `incorrect`, `hold`, `timeout`, or `not_attempted` |
| `first_blocking_stage` | `paragraph_discovery`, `mentions`, `grounding`, `event_discovery`, `selection`, `composition`, `review`, `proposal`, `replay`, or `none` |
| `hold_reason` | The typed hold, or null |
| `failing_criterion` | The rubric criterion for `incorrect`, or null |
| `active_seconds` | Measured, positive for every attempted row, excluding waits |
| `waiting_seconds` | Measured waits for this statement, long and short |
| `corrections` | Substantive decision changes |
| `command_retries` | Repeated invocations after errors |
| `event_id`, `assertion_id`, `proposal_id` | From the commands, or null |
| `notes` | One short note |

## 6. Conditions and order

1. Baseline: `../kotekomi-baseline`, revision `7dc9a44`, roots `development/baseline/anthropic` and `development/baseline/aisi`, statements in reference-ID order.
2. Final: `../kotekomi-final`, revision `2ec4737`, the same Document roots, ordinals, and statement order.
3. Reserved: one root per condition for the Allen Document; alternate baseline-first and final-first order across reserved passages and record the order used.
4. Use the same operator for both conditions; if that is impossible, record both operators and treat the comparison as unblinded.

Both conditions start from empty roots and create every required identity through `review decide`; no accepted record is copied between roots.

## 7. Validate and compare

Development:

```bash
uv run python scripts/ipi_measure.py check --result "<dev-baseline-result>.json"
uv run python scripts/ipi_measure.py check --result "<dev-final-result>.json"
uv run python scripts/ipi_measure.py compare \
  --baseline "<dev-baseline-result>.json" --final "<dev-final-result>.json" \
  --manifest docs/2026-11-06-ipi-01-development-manifest.json
```

Reserved, using the sealed manifest outside the repository:

```bash
uv run python scripts/ipi_measure.py compare \
  --baseline "<res-baseline-result>.json" --final "<res-final-result>.json" \
  --manifest "$HOME/kotekomi-ipi-custody/reserved-manifest.json"
```

Exit code `0` means the declared route passed; `2` means it did not or the input was rejected.
The printed JSON carries `N`, `C`, active seconds, row waiting seconds, setup waiting seconds, total waiting seconds, corrections, command retries, review cost, the route decision, and the list of incomplete or regressed references.

## 8. Completion criteria for this procedure

- Both conditions validate with `check`.
- Both comparisons print a decision.
- Every statement row records measured active and waiting time; no row is `not_attempted`.
- The reserved manifest digest and the two revision identifiers are recorded with the results.
- The per-statement table is recorded verbatim in the package report, including failed and timed-out rows.

## 9. What invalidates the comparison

- A development manifest that changed after its approval, or a population change after the baseline.
- A condition that omits, adds, or substitutes reference identifiers; the comparator rejects it.
- An attempt above the five-minute budget; the comparator rejects it.
- A `not_attempted` row; the comparator treats the measurement as incomplete.
- Seeded proposals, edited derived JSON, or an accepted Assertion used to make a row pass.
- A reused root across conditions, or an inherited approval from the other condition.
- Unknown timing, or effort reported as zero because it was not measured.
- Any inspection of reserved material outside the operator's own run.

## 10. What the reserved evaluation decides

The reserved comparison decides the package's product-gain gate under the approved route.
The development comparison reports changed usable coverage and review cost plus semantic and safety regressions; it informs, and does not substitute for, the reserved decision.
If the reserved comparison misses the target, the result is recorded as `Target not met` with the remaining bottleneck table and a scope request.
The two implemented changes stay in place as frozen revisions; no further production cycle starts from this procedure.
