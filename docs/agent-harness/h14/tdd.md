# H14 TDD notes

Start with tests that express the coverage map before changing planner
behavior.

Unit tests should cover direct path-to-check selection for known harness areas
and the unknown-path fail-closed case. Acceptance tests should use fixture
repositories to verify that changed paths produce a ready plan with the expected
check IDs, reasons, and sources.

Keep the tests deterministic and network-free.
