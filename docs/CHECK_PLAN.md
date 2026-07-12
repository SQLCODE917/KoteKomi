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
- validate sample Briefings against JSON schema with `packages/domain/tests/test_schema_generation.py`
- verify Assertion epistemic scope and Source authority validation with `packages/domain/tests/test_assertion_rules.py`

## 3. Ledger checks
- run `uv run pytest packages/application/tests`
- run `uv run pytest packages/adapters/tests`
- run `uv run pytest packages/pipelines/tests`
- run migrations on empty SQLite database with `packages/adapters/tests/test_sqlite_ledger_migrations.py`
- run migrations on fixture database with `packages/adapters/tests/test_sqlite_ledger_migrations.py`
- run repository tests with `packages/adapters/tests/test_sqlite_ledger_repository.py`
- verify stable Source identity, retry idempotency, immutable revisions, and capture conflicts with `uv run pytest packages/application/tests/test_source_capture.py packages/application/tests/test_add_source_from_file.py packages/adapters/tests/test_sqlite_source_capture.py packages/pipelines/tests/test_source_add_file.py`
- verify deterministic representation identity, one authoritative logical TextView body, atomic bundle commits, and scoped large-corpus bundle loading with `uv run pytest packages/domain/tests/test_document_representations.py packages/application/tests/test_representation_identity.py packages/adapters/tests/test_representation_bundle_commit.py packages/adapters/tests/test_docling_pdf_parser.py`
- verify durable processing task/attempt/outcome records, exhaustive retry reconciliation, immutable SQLite storage, indexed retry lookup, and PDF production-path outcomes with `uv run pytest packages/domain/tests/test_processing_records.py packages/adapters/tests/test_processing_records.py packages/application/tests/test_add_source_from_file.py packages/application/tests/test_pdf_ingest.py packages/adapters/tests/test_pdf_production_path.py`
- verify local-file capture recovery and changed-BuildIdentity representation closure after archive, Ledger, attempt, and transaction failures with `uv run pytest packages/adapters/tests/test_authoritative_capture_fault_matrix.py`
- verify replayable EvidenceTarget validation and reviewed-only atomic Assertion evidence-link acceptance with `uv run pytest packages/application/tests/test_evidence_targets.py packages/adapters/tests/test_atomic_assertion_acceptance.py`
- verify atomic grounded-candidate submission and run the public-path restart-safe authoritative commit-boundary Final Proof with `uv run pytest packages/application/tests/test_grounded_candidates.py packages/adapters/tests/test_authoritative_commit_boundary.py`
- verify the Docling adapter loads lazily and classifies source-access conditions as typed blocked results with `uv run pytest packages/adapters/tests/test_docling_pdf_parser.py`
- verify the born-digital press-release PDF enters Archive, Ledger, deterministic page geometry, text, nodes, regions, reading order, and an acceptable quality report with `uv run pytest packages/adapters/tests/test_docling_pdf_r1a.py`
- verify the press-release priority sentence enters a deterministic ContextManifest, immutable EvidenceTarget, successful validation attempt, reviewed direct-support Assertion link, and restart replay with `uv run pytest packages/adapters/tests/test_docling_pdf_r1a.py`
- verify deterministic analysis units, required CHIP definition closure, exact token budgeting, furniture exclusions, split, and `context_budget_blocked` outcomes with `uv run pytest packages/application/tests/test_context_planning.py packages/adapters/tests/test_docling_pdf_r1a.py`
- verify planner-owned deterministic AnalysisUnit identities, immutable ContextManifest records, atomic split-child persistence, exact manifest verification, and the real-PDF restart-safe `ready`, `split`, and `context_budget_blocked` matrix with `uv run pytest packages/application/tests/test_context_planning.py packages/adapters/tests/test_docling_pdf_r1a.py`
- verify bounded staged extraction admits the manifest-pinned execution specification, archives every model response, rejects receipt disagreement and out-of-manifest references, preserves identical and different SQLite outputs across Run A/B/C, rolls back every successful-publication fault point, preserves review decisions, and maps valid PDF candidates to canonical pending proposals with `uv run pytest packages/application/tests/test_grounded_candidates.py packages/adapters/tests/test_docling_pdf_r1a.py`

## 4. Archive checks
- verify archive cleanup accepts only `StagedArchiveObject` capabilities and run `uv run pytest packages/adapters/tests/test_local_archive_store.py`

## 5. Pipeline checks
- run URL ingest fixture
- run local file ingest fixture with `uv run pytest packages/pipelines/tests/test_source_add_file.py`
- verify llama-server and Ollama Adapter contracts with `uv run pytest packages/adapters/tests/test_local_model_runtimes.py`
- verify local model runtime config and agent status JSON with `uv run pytest packages/pipelines/tests/test_cli.py`
- verify named `macbook` and `wsl-4090` profiles resolve into the shared ModelExecution configuration with `uv run pytest packages/pipelines/tests/test_cli.py`
- optionally probe llama-server with `KOTEKOMI_LIVE_LLAMA_SERVER_MODEL=<alias> uv run pytest packages/adapters/tests/test_local_model_runtimes_live.py`
- optionally probe Ollama with `KOTEKOMI_LIVE_OLLAMA_MODEL=<tag> uv run pytest packages/adapters/tests/test_local_model_runtimes_live.py`
- run ProposedChange review Application test with `uv run pytest packages/application/tests/test_review_proposed_change.py`
- run ProposedChange review Pipeline fixture with `uv run pytest packages/pipelines/tests/test_review_proposed_change.py`
- run Review Queue and Review Packet Application tests with `uv run pytest packages/application/tests/test_review_queue_packet.py`
- run Review Queue and Review Packet Pipeline fixture with `uv run pytest packages/pipelines/tests/test_review_queue_packet.py`
- verify Review Readiness and agent JSON state with `uv run pytest packages/application/tests/test_review_queue_packet.py packages/pipelines/tests/test_review_queue_packet.py`
- verify Review-Next execution with `uv run pytest packages/application/tests/test_review_queue_packet.py packages/pipelines/tests/test_review_queue_packet.py`
- verify Explicit Review-Next Decision Execution with `uv run pytest packages/application/tests/test_review_proposed_change.py packages/pipelines/tests/test_review_proposed_change.py`
- verify Review Drain Queue with `uv run pytest packages/application/tests/test_review_proposed_change.py packages/pipelines/tests/test_review_proposed_change.py`
- verify Pipeline Readiness and agent next-step orchestration with `uv run pytest packages/application/tests/test_pipeline_readiness.py packages/pipelines/tests/test_pipeline_readiness.py`
- verify Pipeline executable agent next-step plans with `uv run pytest packages/application/tests/test_pipeline_readiness.py packages/pipelines/tests/test_pipeline_readiness.py`
- verify Pipeline run-next execution with `uv run pytest packages/application/tests/test_pipeline_readiness.py packages/pipelines/tests/test_pipeline_readiness.py`
- verify accepted Ledger writes reject missing cross-record references with `uv run pytest packages/application/tests/test_review_proposed_change.py`
- run graph projection Application test with `uv run pytest packages/application/tests/test_project_ledger_graph.py`
- run graph projection Adapter test with `uv run pytest packages/adapters/tests/test_networkx_graph_analyzer.py`
- run graph projection Pipeline fixture with `uv run pytest packages/pipelines/tests/test_graph_project.py`
- run graph mining Application test with `uv run pytest packages/application/tests/test_mine_graph_connections.py`
- run graph mining Pipeline fixture with `uv run pytest packages/pipelines/tests/test_graph_mine.py`
- run Briefing generation fixture with `uv run pytest packages/pipelines/tests/test_briefing_generate.py`
- verify Briefing narrative sections use numbered citations without raw canonical Domain IDs with `uv run pytest packages/briefing/tests/test_markdown_briefing_renderer.py packages/pipelines/tests/test_briefing_generate.py`
- verify Briefing Markdown renders the orthogonal eight-section outline with `uv run pytest packages/briefing/tests/test_markdown_briefing_renderer.py packages/pipelines/tests/test_briefing_generate.py`
- verify Briefing citation numbers resolve through structured registry data with `uv run pytest packages/application/tests/test_generate_briefing.py packages/pipelines/tests/test_briefing_generate.py`

## 6. Documentation checks
- verify glossary terms match Domain Core names
- verify command examples run
- verify cross-references resolve
- verify new Port contracts have Application Layer fake-Port tests and Adapter tests
- verify managed llama-server LaunchAgent rendering and user-domain lifecycle with `uv run pytest packages/pipelines/tests/test_managed_llama_server.py`
- verify happy-path fixtures contain no dangling cross-record references

## 7. Forbidden patterns
- Adapter imports inside Domain Core
- Adapter code deciding Domain meaning, status transitions, review outcomes, or repair policy
- accepted Assertion without ProvenanceActivity
- Source-backed accepted Assertion without EvidenceTarget
- accepted Ledger state change without ProvenanceActivity
- canonical state stored outside the Ledger or Archive
- model output written directly as accepted state
- tool-native model response passed across the ModelRuntime Port
- model evidence text absent from the referenced Document
- implicit fixture runtime selection in production Pipeline commands
- derived graph, vector, Briefing, or export state treated as canonical state
- uncited Source-backed Briefing statement
- agent citation resolution by parsing Markdown instead of structured registry data
- unsupported claim introduced by Briefing narrative text
- raw canonical Domain IDs in default human-facing Briefing Markdown
