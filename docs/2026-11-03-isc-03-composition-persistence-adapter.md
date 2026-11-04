# TDD: One Adapter for Event Composition Persistence

- Status: Accepted
- Deliverable: ISC-03
- Parent: [Ingestion Stabilization](2026-11-03-ingestion-stabilization-agile-package.md)

## 1. User outcome

Ingestion, recomposition, and replay read and write one composition outcome the same way.
A reader never observes a half-written outcome.
A corrupt outcome is reported, not silently ignored.

## 2. Current behavior

Before this change the Application Layer exposed path-based helpers
(`write_event_composition_record`, `load_event_composition_record`,
`load_event_composition_records`, `composition_annotations_for`).
Each caller chose its own directory, wrote the file with `Path.write_text`, and decided
whether to validate. The recomposition script wrote its own JSON.

The consequences were these.

- Persistence and validation rules had several owners.
- A truncated write could leave an unreadable outcome.
- A malformed outcome could look like a missing one.

## 3. Ownership

| Concern | Owner |
|---|---|
| Record shape and validation | `EventCompositionRecord` |
| Persistence operations | `kotekomi_application.source_grounded_reference_composition.EventCompositionStore` (Port) |
| Filesystem implementation | `kotekomi_adapters.composition_outcome_store.CompositionOutcomeStore` |
| Replay annotation mapping | `composition_annotation` |

Pipelines and command scripts compose the Adapter.
No module writes composition JSON on its own path.

## 4. Contract

The Port declares three operations.

- `save(record)` writes one record for its Event identifier.
- `load(event_id)` returns one validated record and raises on a malformed or missing file.
- `annotations(event_ids)` returns replay annotations for the Events a paragraph shows.

The Adapter uses the existing replay source location, `<ledger parent>/composition-outcomes`.
The Adapter writes a temporary file in the same directory, flushes it, and replaces the
target with one atomic rename.
A failure before the rename removes the temporary file and leaves the previous record intact.
The Adapter validates every loaded record through `EventCompositionRecord`.

## 5. Preserved behavior

- Existing persisted outcomes stay readable with their Event, source binding, Assertion, and
  supporting spans.
- Held records and composed records keep their contract validation.
- Replay stays read-only.

## 6. Acceptance tests

| Check | Test |
|---|---|
| ISC-03-A | `test_ingestion_recomposition_and_replay_share_one_store` |
| ISC-03-B | `test_interrupted_replacement_preserves_the_previous_record` |
| ISC-03-C | `test_corrupt_record_raises_a_validation_error` |
| ISC-03-D | `test_saved_r20_outcomes_remain_readable` |

## 7. Verification

- `uv run pytest packages/adapters/tests/test_composition_outcome_store.py
  packages/adapters/tests/test_replay_composition_display.py
  packages/pipelines/tests/test_ingestion_composition_transition.py -q`
- `uv run ruff format --check`, `uv run ruff check`, and `uv run pyright` on changed files.
