# R0-A — Ledger repair and immutable commit semantics

This is the immediate next PR.

## 1. Add migration `002_document_ingestion_artifacts.sql`

It should create the tables already expected by `SQLiteLedgerRepository`:

```text
raw_blobs
source_captures
document_revision_relations
document_representations
text_views
document_nodes
document_edges
source_regions
parse_quality_reports
assertion_evidence_links
evidence_reanchoring_relations
```

The current repository already has methods and required-table declarations for these records, but migration `001` only creates the original ledger tables. ([GitHub][2])

Migration tests must cover both:

```text
empty database
    001 → 002

existing database with 001 recorded
    002 only
```

Update the test expectations from:

```python
("001",)
```

to:

```python
("001", "002")
```

for a fresh ledger, while proving an existing `001` ledger upgrades without losing records.

## 2. Split immutable writes from mutable state updates

The current generic `_save()` performs an update whenever an ID already exists:

```sql
ON CONFLICT(id) DO UPDATE SET
    ...
    payload_json = excluded.payload_json
```

That is inappropriate for ingestion artifacts because it permits an earlier representation, capture, blob, or document to be rewritten. ([GitHub][2])

Introduce two explicit internal persistence operations:

```python
def _insert_immutable(
    spec: RecordSpec[T],
    record: T,
) -> ImmutableCommitDisposition:
    ...

def _upsert_mutable(
    spec: RecordSpec[T],
    record: T,
) -> None:
    ...
```

Suggested result and error types:

```python
class ImmutableCommitDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True)
class ImmutableRecordConflict(Exception):
    record_type: str
    record_id: str
    existing_digest: str
    incoming_digest: str
```

The immutable algorithm should be:

```python
incoming_json = canonical_record_json(record)

INSERT ... ON CONFLICT(id) DO NOTHING

if inserted:
    return CREATED

existing_json = load_existing_payload()

if canonicalize(existing_json) == incoming_json:
    return REUSED

raise ImmutableRecordConflict(...)
```

The three allowed outcomes are therefore:

| Existing record | Incoming record       | Outcome                     |
| --------------- | --------------------- | --------------------------- |
| No              | Any valid record      | Insert                      |
| Yes             | Canonically identical | Idempotent reuse            |
| Yes             | Materially different  | Typed conflict, no mutation |

No immutable path should contain `DO UPDATE`.

## 3. Canonicalize stored JSON

Do not rely on incidental Pydantic or dictionary ordering. Add one application-owned function:

```python
def canonical_record_json(record: BaseModel) -> str:
    return json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
```

This same serialization should be used for:

* database comparison;
* conflict digests;
* deterministic tests;
* integrity checks.

## 4. Classify records deliberately

At minimum, these should use immutable insertion:

```text
RawBlob
SourceCapture
Document
DocumentRevisionRelation
DocumentRepresentation
TextView
DocumentNode
DocumentEdge
SourceRegion
ParseQualityReport
AssertionEvidenceLink
EvidenceReanchoringRelation
```

The following genuinely have workflow or current-state transitions and may retain controlled update behavior for now:

```text
ProposedChange
Briefing
reviewed entities and assertions
```

Do not classify records merely from whether their Pydantic model is frozen. “Frozen in memory” and “append-only in persistence” are different guarantees.

### EvidenceSpan special case

`validate_evidence_target()` currently changes validation fields on an existing `EvidenceSpan`, so blindly making the entire table immutable would break that path. Its selector-bearing fields should nevertheless be immutable. ([GitHub][3])

For R0, use a controlled transition:

```text
Allowed to change:
    validation_status
    validator_version
    validated_at
    target_digest

Never allowed to change:
    source_id
    document_id
    representation_id
    text_view_id
    text_view_digest
    exact_text
    prefix_text
    suffix_text
    start_char
    end_char
    node_ids
    pdf_region_ids
    DOM/table selectors
    normalization policy
```

Before applying a validation transition, compare `canonical_evidence_target_digest()` against the existing target selectors. Selector disagreement is an immutable conflict, not a validation update.

A later extraction/coverage milestone can make validation attempts fully append-only. That refactor is not necessary to unblock R0.

## 5. Prefer database enforcement for artifact tables

Application checks are necessary, but SQLite should also prevent accidental updates from future code.

Migration `002` can add `BEFORE UPDATE` and `BEFORE DELETE` triggers for the unconditionally immutable tables. Do not add such a trigger to `evidence_spans` until its validation state is separated or controlled appropriately.

This turns accidental misuse into a hard database failure rather than a convention that future code can bypass.

## R0-A acceptance tests

The PR is not complete unless all of these pass:

```text
Fresh ledger applies migrations 001 and 002.
An existing 001 ledger applies only 002.
All REQUIRED_LEDGER_TABLES exist afterward.

Saving the same immutable record twice succeeds idempotently.
Saving the same ID with one changed field raises ImmutableRecordConflict.
The original payload remains byte-for-byte unchanged after the conflict.
A conflict midway through a transaction leaves no partial records.
A direct SQL UPDATE against an immutable table fails.
Mutable ProposedChange review transitions still work.
The complete existing test suite passes.
```

This restores a safe substrate for the other three gates.

[1]: https://github.com/SQLCODE917/KoteKomi/commits/main "Commits · SQLCODE917/KoteKomi · GitHub"
[2]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/evidence_targets.py "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/source_file_ingest.py "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-source-capture-and-document-versioning.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/domain/src/kotekomi_domain/models.py "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-authoritative-document-ingestion-program.md "raw.githubusercontent.com"

