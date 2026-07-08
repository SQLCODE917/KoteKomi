# KoteKomi Check Plan

## 1. Domain checks
- run `uv run pytest packages/domain/tests`
- run `uv run pyright`
- run `uv run ruff check`
- verify Domain Core imports no Adapter package with `packages/domain/tests/test_import_boundary.py`

## 2. Schema checks
- run `uv run python scripts/generate_schemas.py`
- validate sample Assertions against JSON schema with `packages/domain/tests/test_schema_generation.py`
- validate sample ProposedChanges against JSON schema with `packages/domain/tests/test_schema_generation.py`

## 3. Ledger checks
- run `uv run pytest packages/application/tests`
- run `uv run pytest packages/adapters/tests`
- run `uv run pytest packages/pipelines/tests`
- run migrations on empty SQLite database with `packages/adapters/tests/test_sqlite_ledger_migrations.py`
- run migrations on fixture database with `packages/adapters/tests/test_sqlite_ledger_migrations.py`
- run repository tests with `packages/adapters/tests/test_sqlite_ledger_repository.py`

## 4. Archive checks
- run `uv run pytest packages/adapters/tests/test_local_archive_store.py`

## 5. Pipeline checks
- run URL ingest fixture
- run local file ingest fixture with `uv run pytest packages/pipelines/tests/test_source_add_file.py`
- run Assertion proposal Application test with `uv run pytest packages/application/tests/test_propose_assertions_for_document.py`
- run Assertion proposal Adapter fixture with `uv run pytest packages/adapters/tests/test_fixture_model_runtime.py`
- run Assertion proposal Pipeline fixture with `uv run pytest packages/pipelines/tests/test_source_propose_assertions.py`
- run ProposedChange review Application test with `uv run pytest packages/application/tests/test_review_proposed_change.py`
- run ProposedChange review Pipeline fixture with `uv run pytest packages/pipelines/tests/test_review_proposed_change.py`
- run Briefing generation fixture

## 6. Documentation checks
- verify glossary terms match Domain Core names
- verify command examples run
- verify cross-references resolve

## 7. Forbidden patterns
- Adapter imports inside Domain Core
- accepted Assertion without ProvenanceActivity
- Source-backed accepted Assertion without EvidenceSpan
- model output written directly as accepted state
- uncited Source-backed Briefing statement
