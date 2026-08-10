# H9 Portable Harness TDD

Searchable labels: H9-PORTABLE-HARNESS, H9-KOTEKOMI-ADAPTER, H9-CORE-EXTRACTION, H9-COPYABLE-GUIDANCE, H9-DDD-BOUNDARY.

## Purpose

The Terra High implementation-agent harness is orthogonal to KoteKomi product goals. H9 documents the boundary so the harness can later be shared with other projects.

## Design

```text
H9-PORTABLE-HARNESS
[Agent Harness Core]
  task ledger / goal ledger / receipts / lifecycle / retrospective metrics / scope and budget gates
        |
        v
[Project Adapter]
  repo paths / package manager commands / CI provider / test commands / AGENTS guidance
        |
        v
[KoteKomi Adapter] H9-KOTEKOMI-ADAPTER
```
Core rule: cross-project concepts belong to the harness core. Adapter rule: KoteKomi paths and commands belong to the adapter.

## Acceptance criteria

- H9 docs distinguish harness core from KoteKomi adapter.
- Copyable guidance does not assume KoteKomi product context.
- Copyable guidance marks project-specific placeholders.
- Architecture docs define future module extraction boundaries.
- H9 final goal report tracks portable harness work as documentation, not completed extraction.

## Definition of Done

Acceptance tests must guarantee:

- `test_portable_harness_docs_define_core_and_adapter`
- `test_copyable_agents_guidance_has_project_placeholders`
- `test_copyable_agents_guidance_forbids_manual_state_files`
- `test_copyable_agents_guidance_mentions_goal_coverage_gate`
- `test_portable_harness_extraction_is_deferred_with_future_task`

Unit tests must guarantee:

- `test_project_adapter_config_requires_repo_root`
- `test_project_adapter_config_requires_test_commands`
- `test_core_domain_objects_do_not_reference_kotekomi_paths`
