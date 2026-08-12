# H15 TDD notes

Start with failing tests for complete, missing, and digest-mismatched receipt chains. The first implementation should parse requested receipt entries, compute SHA-256, compare expected digest values, and emit deterministic JSON.

Acceptance tests should invoke the CLI in fixture directories and assert exact status, diagnostic codes, and stable output fields. Avoid network access.
