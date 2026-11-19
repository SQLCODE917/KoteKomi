# Agile package: Faster CI feedback

**Depends on:** close out [harness pilot PR #2](https://github.com/SQLCODE917/KoteKomi/pull/2). This is a separate draft PR; do not make CI changes in the pilot.

| Slice | Outcome | Release evidence |
| --- | --- | --- |
| MVP | Fast feedback in its own job and a parallel full gate with the same coverage | [Leaf TDD](2026-11-19-ci-verification-feedback-and-sharding.md); baseline versus candidate timing and node-ID parity; stable aggregate result |
| Follow-up, only if justified | One full run per PR update, plus full verification on main | Verify check configuration and exact-SHA receipt consumers before changing triggers |
| Follow-up, only if still blocking | More reliable native PDF tooling setup | Setup failure data and a bounded change that preserves real PDF checks |

When the pilot is complete, reconcile the branch with current `main` without rewriting the pinned spec. If the task baseline needs refreshing, publish and explicitly pin a new spec revision before implementation. Implement and review on this same draft PR and branch. Keep measurements and tradeoffs in the PR; no automatic merge.
