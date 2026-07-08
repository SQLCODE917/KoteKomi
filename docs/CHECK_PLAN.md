# KoteKomi Check Plan

## 1. Domain checks
- run Domain Core tests
- verify Domain Core imports no Adapter package

## 2. Schema checks
- validate sample Assertions against JSON schema
- validate sample ProposedChanges against JSON schema

## 3. Ledger checks
- run migrations on empty SQLite database
- run migrations on fixture database
- run repository tests

## 4. Pipeline checks
- run URL ingest fixture
- run local file ingest fixture
- run Assertion proposal fixture
- run Briefing generation fixture

## 5. Documentation checks
- verify glossary terms match Domain Core names
- verify command examples run
- verify cross-references resolve

## 6. Forbidden patterns
- Adapter imports inside Domain Core
- accepted Assertion without ProvenanceActivity
- Source-backed accepted Assertion without EvidenceSpan
- model output written directly as accepted state
- uncited Source-backed Briefing statement
