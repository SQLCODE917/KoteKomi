# Pipeline Rules

## Purpose

Pipelines expose user-visible workflows.

Pipelines compose Application Layer use cases.

## Pipeline Boundary

A Pipeline has one user-visible workflow.

A Pipeline composes Application Layer use cases.

A Pipeline reads configuration from explicit configuration files or command flags.

A Pipeline writes canonical state through the Application Layer.

A Pipeline writes generated files into the Archive.

A Pipeline command has a fixture-backed test when it changes domain state.

## MVP Pipeline Shape

```text
fetch_source
-> extract_document_text
-> create_document_chunks
-> embed_document_chunks
-> propose_assertions
-> reconcile_entities
-> review_proposed_changes
-> update_relationships
-> mine_connections
-> generate_briefing
-> export_records
```

## Add a Pipeline

1. Define the user story in a TDD or accepted issue.
2. Compose Application Layer use cases.
3. Add CLI help.
4. Add a fixture run.
5. Add output examples when the Pipeline writes files.
6. Run applicable checks from `docs/CHECK_PLAN.md`.

## Pipeline State Rules

Pipelines do not bypass the Application Layer.

Pipelines do not write accepted Assertions from model output.

Pipelines write ProposedChange records before review.

Pipelines record ProvenanceActivity records for state changes.
