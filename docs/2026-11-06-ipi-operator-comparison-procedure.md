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

## 3. Ordinal lookup (untimed, once)

Each passage is ingested alone with `--paragraph <n>`.
Record the ordinal per passage before any timed run, and use the same ordinals in both conditions.

Known ordinals from the stored run, to verify by anchor:

| Passage | Document | Ordinal | Anchor to confirm |
| --- | --- | --- | --- |
| DEV-01 | Anthropic-DoD dispute PDF | 3 | `The United States Department of Defense began developing lethal autonomous weapons` |
| DEV-02 | Anthropic-DoD dispute PDF | 4 | `In Donald Trump's second presidency, Anthropic publicly disagreed` |
| DEV-03 | Anthropic-DoD dispute PDF | 5 | `Prior to the dispute, the Trump administration had integrated` |
| DEV-04 | Anthropic-DoD dispute PDF | 8 | `secretary  of  defense  Pete  Hegseth  announced  GenAI.mil` |
| DEV-05 | AI Safety Institute PDF | unknown | `At the AI Seoul Summit in May 2024` |
| DEV-06 | AI Safety Institute PDF | unknown | `the government of France created the Institut national` |

For the two unknown ordinals, run one throwaway lookup root at the baseline revision and scan ordinals until the anchor appears:

```bash
cd ../kotekomi-baseline
uv run kotekomi-live-replay --config "<runtime-config>" --source raw/Artificial_intelligence_safety_institute.pdf \
  --url "<source-url>" --state-root "<lookup-root>/<n>" --plain --paragraph <n>
```

Stop scanning when both anchors are found.
Record the ordinal table in the run log.
If an anchor never appears because the extraction splits or rewrites the passage, record that representation limitation and keep the statement in the denominator as a hold; do not substitute another passage.

## 4. State roots and configuration

One root per passage per condition:

```text
<run-root>/<partition>/<condition>/DEV-01/
<run-root>/<partition>/<condition>/DEV-02/
...
<run-root>/reserved/<condition>/RES-01/
...
```

Each root holds its own `kotekomi.toml`.
Start from the operator's working runtime configuration and change only the two paths:

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

## 5. One statement attempt

Run from the condition's worktree.
Every command uses `$CONFIG`, so it reads that condition's Ledger.

```bash
CONFIG="<root>/kotekomi.toml"
uv run kotekomi-live-replay --config "$CONFIG" --source "<document.pdf>" --url "<source-url>" \
  --state-root "<root>" --plain --paragraph <ordinal>
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
uv run kotekomi-live-replay --state-root "<root>"
```

Timing rules:

- Start the clock when you begin locating the Event and its packet.
- Stop when replay verification finishes or the five active minutes are spent.
- Record every wait longer than five seconds as waiting seconds; record short waits too and sum them.
- Count a substantive correction when you change an identity, predicate, assertion type, authority, attribution basis, or candidate after seeing the first outcome.
- Count a command retry when you repeat an invocation after an error; it is separate from a substantive correction.
- Stop at five active minutes and record `timeout`.

Per-statement row, written into the condition result file:

| Field | Value |
| --- | --- |
| `reference_id` | The manifest identifier |
| `outcome` | `usable`, `incorrect`, `hold`, `timeout`, or `not_attempted` |
| `first_blocking_stage` | `paragraph_discovery`, `mentions`, `grounding`, `event_discovery`, `selection`, `composition`, `review`, `proposal`, `replay`, or `none` |
| `hold_reason` | The typed hold, or null |
| `failing_criterion` | The rubric criterion for `incorrect`, or null |
| `active_seconds` | Measured, positive for every attempted row |
| `waiting_seconds` | Measured, including short waits |
| `corrections` | Substantive decision changes |
| `command_retries` | Repeated invocations after errors |
| `event_id`, `assertion_id`, `proposal_id` | From the commands, or null |
| `notes` | One short note |

## 6. Conditions and order

1. Baseline: `../kotekomi-baseline`, revision `7dc9a44`, one root per passage, statements attempted in reference-ID order.
2. Final: `../kotekomi-final`, revision `2ec4737`, the same ordinals and the same statement order.
3. Reserved passages alternate baseline-first and final-first order; record which order each reserved passage used.
4. Use the same operator for both conditions; if that is impossible, record both operators and treat the comparison as unblinded.

Both conditions must start from equivalent fresh roots, including the same declared pre-existing identities.
Create every required identity through `review decide` in both conditions; never copy an accepted record between roots.

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
The printed JSON carries `N`, `C`, active seconds, waiting seconds, corrections, command retries, review cost, the route decision, and the list of incomplete or regressed references.

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
