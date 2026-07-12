# R0-C — Deterministic representation identity and atomic bundle commit

The present Docling ID uses only the input digest plus the word `docling`:

```python
representation_id = f"rep_{input_digest[:HASH_ID_LENGTH]}_docling"
```

Although parser version and configuration are stored in the representation, the previous ID did not bind the complete processing task. A parser or build upgrade could consequently target the same row. ([GitHub][6])

## Add one shared representation fingerprint

```python
@dataclass(frozen=True)
class RepresentationFingerprintInput:
    document_id: str
    input_blob_digest: str
    parser_name: str
    parser_version: str
    parser_config_digest: str
    build_identity_digest: str
    representation_schema_version: str
```

```python
def deterministic_representation_id(
    fingerprint: RepresentationFingerprintInput,
) -> str:
    return deterministic_id(
        "rep",
        canonical_record_json(fingerprint),
    )
```

Both the local-file adapter and Docling adapter must call this function. No adapter should assemble its own representation ID.

A changed value in any of these fields must yield a different ID:

```text
parser name
parser version
parser configuration
code revision
representation schema/policy
input document or blob
```

## Separate artifact identity from execution time

`created_at` should not affect the representation fingerprint or canonical output digest. Otherwise an identical replay at a later time becomes a false conflict.

Use:

```text
DocumentRepresentation
    deterministic semantic artifact

ProvenanceActivity / parser attempt
    execution time and operational attempt
```

The first committed representation retains its transaction timestamp. A later identical parser run may produce a new provenance activity while reusing the same representation artifact.

This also creates a valuable nondeterminism detector:

```text
same representation fingerprint
same representation ID
different canonical output digest
    → NonDeterministicParserOutputConflict
```

Never silently create “latest output.”

## Commit representations as one bundle

Add a repository operation:

```python
commit_document_representation_bundle(
    bundle: DocumentRepresentationBundle,
) -> BundleCommitOutcome
```

The operation must:

1. validate the complete bundle before writing;
2. insert the representation, views, nodes, edges, regions, and quality report atomically;
3. return `CREATED` when all are new;
4. return `REUSED` when the complete existing bundle is identical;
5. reject any partial or differing pre-existing bundle;
6. roll back every child insertion if one child conflicts.

The existing representation model already validates ranges, tree integrity, region bounds, and canonical output digest, so this commit operation should use the fully validated bundle rather than accepting unrelated individual records. ([GitHub][7])

Derive child IDs from the representation ID plus stable local identity:

```text
TextView:
    representation + view kind

DocumentNode:
    representation + canonical structural path/local node key

SourceRegion:
    representation + page + local region key

QualityReport:
    representation + quality policy version
```

Do not derive child IDs directly from the raw PDF hash.

## R0-C acceptance tests

```text
Same document + same parser fingerprint + same output:
    same representation ID, idempotent reuse

Same document + changed parser version:
    different representation ID

Same document + changed parser configuration:
    different representation ID

Same document + changed code revision:
    different representation ID

Same fingerprint + changed node text/output:
    typed nondeterminism conflict

Conflict in one child:
    no representation or sibling children partially committed

Old representation:
    remains byte-for-byte unchanged after every rerun

Process restart:
    produces the same representation and child identities
```

These tests close the first two agreed release gates.

[1]: https://github.com/SQLCODE917/KoteKomi/commits/main "Commits · SQLCODE917/KoteKomi · GitHub"
[2]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/evidence_targets.py "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/source_file_ingest.py "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-source-capture-and-document-versioning.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/domain/src/kotekomi_domain/models.py "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-authoritative-document-ingestion-program.md "raw.githubusercontent.com"
