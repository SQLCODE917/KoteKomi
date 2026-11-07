# IPI Ingestion Evidence

- Status: Six ingestions complete; statement review not started
- Run root: `/Users/DSerbarinov/kotekomi-ipi-run-20261106`
- Baseline revision: `7dc9a44`; final revision: `2ec4737`
- Runtime configuration: `/Users/DSerbarinov/gits/KoteKomi/data/ira-acceptance-20261105-141506-176099/kotekomi.toml`
- Model: `qwen2.5-14b-instruct` at `http://127.0.0.1:1234/v1`

## 1. What these numbers are

Ingestion is setup, not a statement result.
The durations below are recorded once per Document and condition and are never charged to a statement row.
No review, acceptance, or comparator action was performed for this record.

## 2. Ingestions

| Condition | Document | Root | IngestionRun | Wall clock | Run elapsed | Model runs | Failed stage records | Complete / gap paragraphs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | Anthropic-DoD | `development/baseline/anthropic` | `igr_9887843eb08e4705b89072481c3ed14a` | 5768.7 s (96.1 min) | 5694.5 s | 1087 | 2 | 17 / 19 |
| baseline | AI Safety Institute | `development/baseline/aisi` | `igr_351e9b817c58449f835be378ad58106c` | 5919.4 s (98.7 min) | 5852.8 s | 1060 | 10 | 2 / 26 |
| baseline | Allen Safety Network | `reserved/baseline/allen` | `igr_22ba21e36dff4271b3ecd3e5ac1caf56` | 19747.9 s (329.1 min) | 19416.3 s | 4208 | 30 | 169 / 54 |
| final | Anthropic-DoD | `development/final/anthropic` | `igr_26f4e593dffd45b6a920c8b613b2c7f8` | 5349.9 s (89.2 min) | 5274.7 s | 1087 | 2 | 17 / 19 |
| final | AI Safety Institute | `development/final/aisi` | `igr_4937f3581fb84cbebe085dd21538958e` | 5902.5 s (98.4 min) | 5837.3 s | 1060 | 10 | 2 / 26 |
| final | Allen Safety Network | `reserved/final/allen` | `igr_20fdd0a74506448482305c731531613f` | 18727.8 s (312.1 min) | 18393.3 s | 4208 | 30 | 169 / 54 |

Totals: 17.06 hours of wall clock; 12,710 model runs.
Every run reports `status: captured`, exits 0, and has no `failure_code` or `failure_stage`.
Every run carries the pinned product revision in its launcher receipt.

## 3. What the ingestion numbers do and do not show

- The final runs were collectively 4.6 percent faster in wall clock.
  Record that as an observed timing difference only.
  It is not attributed to the two production changes, and the two changes are not definitively excluded as a cause: identical extraction volumes, model-run counts, evidence counts, and failed stage records make an extraction-side explanation unlikely, but a single paired run with a shared machine cannot separate code effects from machine and model-runtime variance.
- Identical evidence and model-run counts also show that neither change altered extraction; the changes act at selection, composition, and Assertion construction.
- The failed stage records (2, 10, and 30 per run) and the paragraph gaps remain part of the assessment.
  They are recorded, not repaired; a statement whose Event or candidate is missing stays in the denominator as a hold.
- AISI has only 2 complete paragraphs of 28; both development passages from that Document fall in gap paragraphs.
  The operator records the first blocking stage for each statement rather than replacing the passage.

## 4. Integrity checks performed on the durable records

- Six condition roots, each with its own `state/` directory holding `kotekomi.db`, `archive/`, `composition-outcomes/`, `token-artifacts/`, and the generated `state/kotekomi.toml`; no state is shared between conditions or Documents.
- Launcher receipts record `product_revision` `7dc9a44` for baseline roots and `2ec4737` for final roots.
- Launcher receipts record the same runtime-configuration digest for all six runs.
- No review command, ProposedChange approval, or Assertion acceptance was performed during ingestion.
- The roots are retained as the basis for statement review; no rerun is needed because of stage gaps.
- Every review command reads the generated `<root>/state/kotekomi.toml`, and every replay uses `--state-root <root>/state`.

## 5. Next milestone

Timed statement review in the six retained roots, following the [operator comparison procedure](2026-11-06-ipi-operator-comparison-procedure.md).
The package has no success decision yet: usable coverage, review cost, and semantic completeness are unmeasured.
