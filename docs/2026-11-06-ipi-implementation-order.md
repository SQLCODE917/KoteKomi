# IPI Implementation Order and Reference Reconciliation

- Status: Recorded; no further production cycle starts
- Package: [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md)
- Baseline revision: `7dc9a44`
- Branch: `feature/ipi-intelligence-pipeline-improvement`

## 1. What happened, in order

| Order | Event | Revision |
| --- | --- | --- |
| 1 | Package opened; baseline recorded | `3ab08be` |
| 2 | IPI-01 material proposed: manifest, rubric, custody, measurement format | `b2a7484` |
| 3 | Agent diagnostic over the stored run; cross-stage ranking recorded (IPI-02) | `b2a7484` onward |
| 4 | Cycle 1 implemented and verified on a copied run: noun-phrase boundary completion | `d001544` |
| 5 | Cycle 2 implemented and verified on a copied run: trigger time qualifier | `2ec4737` |
| 6 | Manifest made source-bound; comparator and custody tightened at human review | `e94b4fb`, `48e7be7` |
| 7 | This record and the operator procedure | pending |

The package's intended order was IPI-01 approval, then the operator baseline, then implementation.
The two implementations happened before D1, D2, and D4 were approved and before any operator baseline.

## 2. Why that order was used, and what it does not entitle

The implementing agent worked under the instruction to complete the deliverables autonomously and to treat fixture authoring, worker wiring, and failing tests as implementation work.
Development material may inform implementation choices, and the agent used only development material and one stored human-run ingestion.
No reserved passage was inspected; the custody root was never created; no operator evidence was modified.

This order does not entitle the implementations to count as a package gain.
Their agent-run journeys and counterfactual counts are mechanism evidence.
Only the reserved evaluation with measured operator effort can decide whether the package is satisfied.

## 3. Freeze

The product behaviour under test is frozen.

| Condition | Product revision | Rule |
| --- | --- | --- |
| Baseline | `7dc9a44` | The pre-change revision recorded when the package opened |
| Final | `2ec4737` | The last production-code commit; later commits change documentation and measurement tooling only |

No production cycle starts after this record.
If the reserved comparison misses the target, the outcome is `Target not met` and a scope decision, not another local change.

## 4. Reference reconciliation

The development manifest was reissued after human review, and its statement identifiers changed.
These documents now use the reissued identifiers.

| Document | Earlier reference | Current reference | Meaning |
| --- | --- | --- | --- |
| [IPI-03 evidence](2026-11-06-ipi-03-evidence.md) | R-DEV-04 | R-DEV-05 | `Dario Amodei criticized Trump's approach to export restrictions on semiconductors` |
| [IPI-04 evidence](2026-11-06-ipi-04-evidence.md) | R-DEV-03 | R-DEV-04 | `The Trump administration had integrated Anthropic's services` |
| [IPI-04 evidence](2026-11-06-ipi-04-evidence.md) | R-DEV-04 | R-DEV-05 | `Dario Amodei criticized ...` |
| [IPI-04 evidence](2026-11-06-ipi-04-evidence.md) | R-DEV-05 | R-DEV-06 | `Pete Hegseth announced GenAI.mil ...` |
| [IPI-04 evidence](2026-11-06-ipi-04-evidence.md) | R-DEV-06, R-DEV-07 | R-DEV-07, R-DEV-08 | The two AI Safety Institute statements |

The current identifiers are fixed in `docs/2026-11-06-ipi-01-development-manifest.json`.
The comparator refuses any condition whose reference identifiers differ from that manifest, so a stale identifier cannot silently enter a measurement.

The manifest also reissued passage membership: the earlier proposal used a lead sentence and a separate criticized paragraph; the current manifest binds six exact paragraphs, including two from the AI Safety Institute Document.
No operator baseline has run against either revision of the manifest, so the change does not invalidate a measurement; it only means the approved population is the current one.

## 5. What remains open

| Item | State |
| --- | --- |
| D1 passage and statement approval | Pending human reading of the complete context |
| D2 rubric and timing protocol approval | Pending |
| D4 reserved custody | Pending; the first `seal` invocation only writes a template |
| Timed baseline | Not started |
| Timed final | Not started |
| Reserved evaluation | Not started; no reserved passage inspected |
| Package completion | Undecided; the reserved evaluation decides it |
