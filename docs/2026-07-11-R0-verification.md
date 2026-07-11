# Verification verdict

**The four narrow R0 mechanics are implemented, but R0 is not yet complete as a greenfield architectural cutover. Overall status remains AMBER.**

The latest visible `main` commit is **`64921a4` (`R0`)**, following the R0-A through R0-D sequence on July 11, 2026. The repository now contains immutable artifact persistence, stable source capture and revisioning, deterministic representation commits, atomic evidence-gated assertion acceptance, and a restart-safe repository-level proof. ([GitHub][1])

| R0 gate                                | Verdict                    | Qualification                                                                                                                                                |
| -------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Immutable artifact persistence         | **PASS**                   | Insert-or-identical behavior and immutable-table classification are present.                                                                                 |
| Stable source identity and revisioning | **PASS, narrow**           | Stable IDs, conflicts, and revision cycles are covered, but the production file-ingestion path still has closure and revision-policy problems.               |
| Deterministic representation commits   | **PASS, repository-level** | Atomic bundle commits and nondeterminism detection exist, but production adapters still use an unknown code revision.                                        |
| Evidence-gated assertion acceptance    | **PASS, repository-level** | Acceptance replays evidence and commits assertion plus links atomically, but separate bypass-style evidence and proposal APIs remain.                        |
| Final authoritative proof              | **PARTIAL**                | It proves repository composition and restart replay, but manually constructs most artifacts rather than exercising the public ingestion and extraction path. |

The dedicated tests cover the intended source-capture, representation, evidence-acceptance, and restart-proof behaviors. ([GitHub][2])

## Verification limitation

I reviewed `main` at `64921a4` file-by-file and inspected the relevant tests. I did not execute `pytest`, Ruff, or Pyright. Therefore, the PASS decisions above mean **source-and-test verification**, not independently observed runtime certification. ([GitHub][3])

---

# Greenfield violations that remain

The current main TDD now explicitly says:

* no compatibility paths;
* no whole-document proposal adapter;
* every evidence span is pinned;
* superseded fields and ports are replaced in the same change;
* rollback never deletes archived inputs.

Those are the correct greenfield rules. The production code does not yet satisfy all of them. ([GitHub][4])

## P0 — Authoritative archive objects can be deleted during rollback

`source_file_ingest.py` deletes already promoted archive objects when a later operation fails. It also exposes `cleanup_created_source_archive_objects()`, which blindly deletes the raw and extracted-text paths. The CLI invokes that cleanup after an outer transaction failure. ([GitHub][5])

The local archive adapter itself treats an existing final object as an error and provides an unconditional unlink operation. ([GitHub][6])

This creates two correctness hazards:

1. A database rollback can remove bytes that should remain an authoritative record of what was received.
2. A retried or shared content-addressed object may be deleted even though another capture or document still refers to it.

It also makes crash recovery asymmetric: a crash after filesystem promotion but before ledger commit leaves an object that causes the retry to fail with `FileExistsError`.

This directly contradicts the TDD’s “rollback never deletes archived inputs” rule.

### Required replacement

The authoritative archive API should be:

```python
put_if_absent_or_identical(
    object_id: str,
    payload: bytes,
    expected_digest: str,
) -> ArchivePutOutcome
```

with exactly three outcomes:

```text
object absent                     → create
object exists with identical bytes → reuse
object exists with different bytes → immutable conflict
```

Only temporary staging files may be deleted during rollback. Unreferenced authoritative objects should be handled by an explicit, reachability-based garbage collector with a retention policy—not transaction compensation.

---

## P0 — File-ingestion success does not prove a complete artifact closure

The local-file ingestion fast path returns success when it finds an existing capture, document, and provenance activity. It does **not** verify that the representation bundle, text view, node, quality report, extracted archive object, and raw archive bytes all exist and agree. ([GitHub][5])

A failed earlier attempt can therefore leave:

```text
Capture       exists
Document      exists
Provenance    exists
Representation missing
```

and a retry can return a `representation_id` as though ingestion were complete.

The later logic also creates the representation only when the `Document` is new. An existing document with a missing representation is therefore not repaired by that path. ([GitHub][5])

### Required replacement

Define one explicit authoritative closure:

```text
AuthoritativeCaptureClosure
├── Source
├── RawBlob and archived bytes
├── SourceCapture
├── CaptureDocumentResolution
├── Document
├── DocumentRepresentationBundle
└── ProcessingAttempt
```

An operation may return `REUSED` only when every member exists and every identity and digest agrees.

A partial closure must either:

* deterministically append the missing artifacts; or
* return a typed `INCOMPLETE_CLOSURE` failure.

It must never report success merely because a subset exists.

---

## P0 — The superseded whole-document model architecture is still active

The accepted TDD states that no whole-document proposal adapter remains. Nevertheless, the repository still contains:

```python
propose_assertions_for_document(...)
```

which reads the entire archived document text and passes it to:

```python
ModelRuntime.propose_assertions(
    document_id=...,
    source_id=...,
    document_text=...,
)
```

([GitHub][7])

This is not dormant compatibility code. The CLI still exposes:

```text
kotekomi source propose-assertions
```

and invokes that application use case. ([GitHub][8])

That path bypasses the planned architecture:

```text
DocumentRepresentation
→ AnalysisPlan
→ ContextManifest
→ bounded ExtractionTask
→ ModelRun
→ grounded candidates
```

It also retains the old generic `ModelProposal` object rather than typed, stage-specific outputs.

### Delete rather than wrap

Remove:

* `assertion_proposal.py`;
* `model_proposal_validation.py`;
* `ModelProposal`;
* `ModelRuntime.propose_assertions`;
* the `source propose-assertions` CLI command;
* the whole-document fixture/runtime implementations;
* the existing whole-document assertion prompt;
* exports and tests that exist solely for this path.

Keep only model transport and readiness functionality. The semantic model interface should later become something like:

```python
class ModelExecutor(Protocol):
    def execute(
        self,
        task: ModelTaskEnvelope,
    ) -> RawModelResponse: ...
```

The executor should know nothing about documents, assertions, canonical IDs, or the ledger.

Having temporarily **no extraction command** is better than retaining an authoritative-looking command with the wrong architecture.

---

## P1 — Evidence still contains the old and new models simultaneously

`EvidenceSpan` currently supports both:

* the new pinned target fields; and
* the old `assertion_id`, generic `location`, singular `selector_type`, and optional representation/offset fields.

Its representation, text-view digest, and positions are still optional. ([GitHub][9])

Validation also mutates the canonical `EvidenceSpan` between `UNVALIDATED`, `FAILED`, and `VALIDATED`, replacing validator metadata on the same record. ([GitHub][10])

Finally, `link_assertion_evidence()` can add an evidence relationship to an already accepted assertion outside the reviewed atomic assertion-acceptance operation. ([GitHub][10])

That is exactly the kind of dual architecture that greenfield development should avoid.

### Required replacement

Use two immutable concepts:

```text
EvidenceTarget
    immutable selector identity and source occurrence

EvidenceValidationAttempt
    append-only result of replaying one EvidenceTarget
```

`EvidenceTarget` should always require:

```text
source_id
document_id
representation_id
text_view_id
text_view_digest
start_char
end_char
exact_text
normalization_policy
at least one structural/occurrence selector
```

Remove:

```text
assertion_id
generic location
optional pinning
validation state
validator version
validated_at
target_digest as mutable state
```

An accepted `AssertionEvidenceLink` should reference both:

```text
evidence_target_id
successful_validation_attempt_id
```

Delete the standalone `link_assertion_evidence()` use case. Adding or replacing evidence after acceptance should require a reviewed `AssertionAmendment`, committed through the same authority boundary as the original assertion.

---

## P1 — Parser and processing identity is not authoritative yet

The local-file representation fingerprint and stored representation use:

```python
code_revision="unknown"
```

([GitHub][5])

That undermines the otherwise-correct deterministic representation identity. A parser-code change with the same nominal parser version and configuration can target the same representation ID and appear to be nondeterministic output rather than a legitimate new implementation version.

`ProvenanceActivity` is also not classified as immutable. Its repository save goes through the generic mutable upsert path, so repeated use of one activity ID can replace prior attempt information. ([GitHub][11])

### Required replacement

Inject a mandatory build identity:

```python
@dataclass(frozen=True)
class BuildIdentity:
    package_version: str
    source_revision: str
    artifact_digest: str
    representation_policy_version: str
```

There should be no `"unknown"` default in an authoritative execution. Startup or execution must fail closed when build identity is unavailable.

Also split semantic work from execution attempts:

```text
ProcessingTaskFingerprint
    deterministic identity of intended work

ProcessingAttempt
    unique append-only execution, including success, block, failure, or cancellation
```

Every retry creates a new `ProcessingAttempt`; no attempt is updated or overwritten.

---

## P1 — Source and document concepts still contain transport-era fields

`Source` still stores title, URI, and publication time rather than explicitly storing the identity policy and canonical identity key. `Document` stores `raw_path`, `extracted_text_path`, and only one `created_from_capture_id`. ([GitHub][9])

Those fields create several conceptual leaks:

* `RawBlob.storage_locator` already owns raw-byte location.
* Extracted text belongs to a parser representation, not `Document`.
* One immutable document can be resolved from multiple captures, but `created_from_capture_id` represents only the first one.
* Title, URI, and publication time may vary by capture or document revision without changing logical source identity.

Revision validation also only checks that predecessor and relation type are supplied together and that a document does not point to itself. It does not enforce semantic consistency between `version_kind` and relation type. Provider conflict and revision lookups scan all documents or relations. ([GitHub][12])

### Required replacement

```text
Source
    identity_policy_id
    canonical_identity_key
    provider_namespace
    provider_item_id

SourceCapture
    retrieval envelope and observed metadata

Document
    immutable content/version metadata

CaptureDocumentResolution
    capture_id
    document_id
    resolution_policy
    resolution_basis

RawBlob
    byte digest and storage locator

DocumentRepresentation
    derived text and structural views
```

Revision semantics should be enforced:

```text
ORIGINAL    → no predecessor
UPDATE      → UPDATES or SUPERSEDES
CORRECTION  → CORRECTS
WITHDRAWAL  → WITHDRAWS
```

A changed local file should not be guessed to be an update. Without an explicit revision decision, return `UNCLASSIFIED_REVISION`.

---

## P1 — Current persistence will not scale to real PDFs

To load one representation bundle, the SQLite adapter currently loads every text view, node, edge, region, and quality report in the database and filters them in Python. ([GitHub][11])

That may be invisible with fixtures. It becomes immediately problematic when one PDF contributes thousands of nodes and the corpus contains many documents.

### Required replacement

Retain canonical JSON payloads where useful, but add relational ownership columns and indexes:

```text
document_representations.document_id
text_views.representation_id
document_nodes.representation_id
document_nodes.parent_node_id
document_edges.representation_id
source_regions.representation_id
parse_quality_reports.representation_id
source_captures.source_id
source_captures.blob_id
documents.source_id
capture_document_resolutions.capture_id
```

Use foreign keys, unique constraints, and repository methods such as:

```python
list_nodes_for_representation(representation_id)
get_quality_report_for_representation(representation_id)
find_document_by_provider_version(...)
list_revision_relations_from(document_id)
```

No authoritative ingestion or evidence operation should call a corpus-wide `list_*()` and filter in application memory.

Because this is greenfield, squash the current development migrations into one clean baseline once the canonical schema is decided. Preserve migration machinery for future released schemas, not development archaeology.

---

# Recommended next milestone

## R0.1 — Greenfield Cutover and Authoritative Intake Closure

Do this **before** expanding Docling, adding OCR, implementing context planning, or starting Reuters/AP adapters.

### Slice A — Remove unsafe and superseded entry points

Immediately:

1. Remove destructive rollback of authoritative archive objects.
2. Remove the whole-document proposal application use case and CLI command.
3. Remove standalone post-acceptance evidence linking.
4. Reject authoritative parser execution without a real build identity.
5. Add CI on Python 3.12 for Ruff, Pyright, schema regeneration checks, and the full test suite.

Add architectural tests that fail when any of these reappear:

```text
propose_assertions_for_document
ModelRuntime.propose_assertions
document_text model input
source propose-assertions
cleanup_created_source_archive_objects
standalone link_assertion_evidence
code_revision="unknown"
```

The GitHub Actions page currently exposes no project workflow, so this guard should be added now rather than after the system becomes harder to validate. ([GitHub][3])

### Slice B — Make the domain model singular

In one breaking change:

* replace mutable/optional `EvidenceSpan` with immutable, always-pinned evidence targets;
* add append-only evidence-validation attempts;
* add processing-task fingerprints and append-only attempts;
* clean `Source`, `Document`, and `RawBlob` ownership;
* add `CaptureDocumentResolution`;
* enforce the revision-kind/relation matrix;
* regenerate schemas;
* remove superseded fields, ports, aliases, and compatibility validators;
* replace the development migration chain with one clean baseline.

Do not leave deprecated fields in the schema “for later.”

### Slice C — Implement convergent authoritative intake

Create one application operation whose success means the entire closure exists:

```python
commit_authoritative_capture(
    request: AuthoritativeCaptureRequest,
) -> AuthoritativeCaptureOutcome
```

It should:

1. deterministically calculate all expected identities;
2. put raw bytes using absent-or-identical semantics;
3. append the capture and document resolution;
4. commit the representation bundle atomically;
5. append the processing attempt;
6. validate the completed closure before returning;
7. reconcile a partial prior attempt on retry;
8. never delete an authoritative archive object during rollback.

Fault-injection tests should stop execution after every boundary:

```text
after archive write
after Source insert
after RawBlob insert
after SourceCapture insert
after CaptureDocumentResolution insert
after Document insert
after each representation child
after quality report
after ProcessingAttempt
before transaction commit
after transaction commit
```

Restarting and retrying after every injected failure must converge on the same complete closure.

### Slice D — Replace corpus scans with indexed repository operations

Add relational ownership columns, foreign keys, and targeted queries before creating large PDF node sets.

A scale test should insert a synthetic corpus with at least one very large representation and prove that fetching one bundle queries only that representation’s rows. The test should inspect query plans or instrument fetched row counts, not rely solely on elapsed time.

### Slice E — Run a real production-path proof

The new final proof must invoke public application/CLI entry points rather than manually seeding intermediate records:

```text
local source file
→ immutable archive
→ SourceCapture
→ CaptureDocumentResolution
→ Document
→ DocumentRepresentationBundle
→ immutable EvidenceTarget
→ EvidenceValidationAttempt
→ bounded typed model-task fixture
→ ProposedChange
→ review
→ atomic Assertion + evidence links
→ process restart
→ exact replay to archived bytes
```

It must additionally prove:

* same bytes under a new capture never cause an old blob to be deleted;
* a promoted-but-uncommitted object is safely reused;
* a partial representation cannot be reported as complete;
* unknown build identity fails;
* changed bytes without revision semantics are blocked;
* mismatched version and relation kinds are rejected;
* attempts are append-only;
* no evidence link can bypass review;
* all identities and digests survive restart.

## R0.1 completion rule

R0.1 is complete only when all of these statements are true:

```text
No whole-document model API exists.
No model allocates canonical IDs.
No rollback deletes authoritative archive data.
No success result represents a partial artifact closure.
No representation records an unknown build revision.
No EvidenceTarget can be created unpinned.
No validation or processing attempt is overwritten.
No evidence relationship can bypass reviewed acceptance.
Every capture has an explicit Document resolution.
Every revision kind has a consistent lineage relation.
No representation lookup scans unrelated corpus records.
The real public ingestion path passes the restart proof.
CI is green on the pinned Python version.
```

---

# Bottom line

**R0 fixed the four repository-level mechanisms it was meant to fix.** The work is real and useful.

But the repository still carries the active pre-program extraction path, destructive archive compensation, dual evidence models, incomplete ingestion closure, transport-oriented domain fields, mutable attempt records, and fixture-scale persistence.

The correct immediate implementation is therefore **R0.1 Greenfield Cutover**, beginning with removal of the unsafe archive cleanup and superseded whole-document/unlinked entry points. Do not build another feature on top of the current seams.

[1]: https://github.com/SQLCODE917/KoteKomi/commits/main/ "Commits · SQLCODE917/KoteKomi · GitHub"
[2]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/adapters/tests/test_authoritative_commit_boundary.py?plain=1 "KoteKomi/packages/adapters/tests/test_authoritative_commit_boundary.py at main · SQLCODE917/KoteKomi · GitHub"
[3]: https://github.com/SQLCODE917/KoteKomi/actions "Actions · SQLCODE917/KoteKomi · GitHub"
[4]: https://github.com/SQLCODE917/KoteKomi/blob/main/docs/2026-07-11-authoritative-document-ingestion-program.md?plain=1 "KoteKomi/docs/2026-07-11-authoritative-document-ingestion-program.md at main · SQLCODE917/KoteKomi · GitHub"
[5]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/application/src/kotekomi_application/source_file_ingest.py?plain=1 "KoteKomi/packages/application/src/kotekomi_application/source_file_ingest.py at main · SQLCODE917/KoteKomi · GitHub"
[6]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/adapters/src/kotekomi_adapters/local_archive.py?plain=1 "KoteKomi/packages/adapters/src/kotekomi_adapters/local_archive.py at main · SQLCODE917/KoteKomi · GitHub"
[7]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/application/src/kotekomi_application/assertion_proposal.py?plain=1 "KoteKomi/packages/application/src/kotekomi_application/assertion_proposal.py at main · SQLCODE917/KoteKomi · GitHub"
[8]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/pipelines/src/kotekomi_pipelines/cli.py?plain=1 "KoteKomi/packages/pipelines/src/kotekomi_pipelines/cli.py at main · SQLCODE917/KoteKomi · GitHub"
[9]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/domain/src/kotekomi_domain/models.py?plain=1 "KoteKomi/packages/domain/src/kotekomi_domain/models.py at main · SQLCODE917/KoteKomi · GitHub"
[10]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/application/src/kotekomi_application/evidence_targets.py?plain=1 "KoteKomi/packages/application/src/kotekomi_application/evidence_targets.py at main · SQLCODE917/KoteKomi · GitHub"
[11]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py?plain=1 "KoteKomi/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py at main · SQLCODE917/KoteKomi · GitHub"
[12]: https://github.com/SQLCODE917/KoteKomi/blob/main/packages/application/src/kotekomi_application/source_capture.py?plain=1 "KoteKomi/packages/application/src/kotekomi_application/source_capture.py at main · SQLCODE917/KoteKomi · GitHub"

