# Unattended Ingestion Stabilization Implementation Prompt

Use the following text as the implementation instruction.

```text
Implement every deliverable in docs/2026-11-03-ingestion-stabilization-agile-package.md.
The package is accepted and implementation is authorized.
Work independently until all six deliverables and their acceptance checks are complete.
Execute them in dependency order: ISC-01, ISC-04, ISC-02, ISC-03, ISC-05, ISC-06.
Do not stop after a plan, a TDD, a preparatory component, or a single deliverable.

Read AGENTS.md, the nearest package instructions, routed docs/agent guidance,
the master design document, the package, and docs/CHECK_PLAN.md.
Follow the repository's authority order and existing implementation workflow.
Treat this instruction as authorization for routine design, implementation,
local verification, and commits within the package's scope.
Do not ask for permission again for those steps.

Start by inspecting Git status and recording the starting revision.
Use an isolated work branch.
Preserve unrelated work and all historical evidence.
The startup and warning-display fixes are committed prerequisites; verify them,
but do not count them as completed cleanup deliverables.

Use this loop for each deliverable:

1. Inspect the original committed implementation and its actual callers.
   Record the relevant user-visible behavior, invariants, and failure behavior.
   Existing code is the behavioral baseline unless a verified bug or an explicit
   correction in the accepted package requires different behavior.
   Higher-authority domain rules and accepted contracts remain authoritative.

2. Write a focused TDD before changing a boundary contract.
   Resolve routine implementation choices using the accepted package and code.
   Commit the design, then proceed without waiting for another approval.
   Mechanical formatting uses the package checklist and a separate commit.

3. Write characterization tests and run them against the original code first.
   Exercise the real boundary: public ingestion entry points, SQLite transactions,
   source coordinates, subprocess startup/cancellation, persistence, and replay
   where the deliverable crosses those boundaries.
   Substitute deterministic fixtures only for external analyzer/model output.
   Validate those fixtures through the production DTOs and parsers.
   Do not seed expected composition outcomes or bypass the path being tested.

4. For an intended behavior correction, add a separate regression that fails
   against the original implementation and explains the violated requirement.
   For a newly discovered bug, reproduce it before changing code.
   Fix bugs within this package's scope; record unrelated defects separately.
   Do not preserve a verified bug merely to keep a characterization test green.
   Do not call an unexplained test failure pre-existing or unrelated.
   Establish that attribution with the correct baseline and import resolution.

5. Refactor the single retained implementation.
   Move shared production contracts out of experiment-specific ownership.
   Preserve inward dependencies: the Application Layer owns decisions and Ports;
   Adapters own persistence/translation; Pipelines compose use cases.
   Update all callers and remove superseded definitions in the same change.
   Add no parallel DTOs, compatibility shims, or speculative frameworks.

6. Re-run the same characterization tests and the correction regressions.
   Preserve reviewed expected results rather than regenerating them from new code.
   Normalize only explicitly justified execution IDs or timestamps when comparing
   independent runs; do not erase meaningful differences.
   Do not weaken assertions, add xfail/skip, suppress failures, or alter historical
   evidence to make the suite pass.

7. Run applicable formatting, lint, typecheck, and regression checks.
   Inspect changes for accidental coupling, dead code, and changed semantics.
   Keep model prompts, selection/grounding policies, source text and coordinates,
   review requirements, and accepted-state invariants unchanged except for the
   explicit corrections specified by the package.

8. Update the package tracker and CHECK_PLAN with exact commands and results.
   Complete a deliverable only after every acceptance check has evidence.
   Commit the implementation and its verification record, then immediately
   continue to the next deliverable.

Verification authorization for this unattended task:
- Run deterministic local checks, full suites, and pinned historical reproduction
  yourself, including operations longer than 60 seconds.
- This overrides the repository's human-start handoff for those checks only.
- Use existing verification machinery for durable, validated results.
  Record the command, tested revision, completion status, and evidence location.
- Keep subprocesses bounded and inspect terminal results; communicate meaningful
  progress without busy polling or introducing a new verification framework.
- Do not invoke live models, create accepted records in the operator's Ledger,
  push, merge, or deploy. Those actions are outside this authorization.
- Use pinned historical checkouts with their own environments and verify imports
  resolve to the intended checkout. Frozen reports and reviewed inputs stay intact.

Before finishing, run the full current regression suite and whole-tree checks.
Verify all ingestion interfaces produce equivalent semantic outcomes, final
composition results appear live, saved replay stays read-only, atomic writes and
review rollback still work, and subprocess checks pass with PYTHONPATH unset.
Keep the formatting-only commit separate from behavioral and structural edits.

Do not stop because the work spans several modules or one attempt failed.
Keep WIP and resume from it instead of deleting progress to obtain a clean tree.
If context is compacted, resume from the tracker, commits, and recorded evidence.
Stop early only for a concrete blocker requiring an unavailable external
capability or a decision outside the accepted scope; finish independent work
first, describe the exact failure, and leave incomplete checkboxes open.

Mark the package Complete only when all six deliverables pass their checks.
Report the branch, commits, test results, preserved historical fingerprints,
intentional behavior corrections, and any remaining limitations.
Do not claim improved extraction accuracy, model latency, or held-out validation
from this structural cleanup.
```
