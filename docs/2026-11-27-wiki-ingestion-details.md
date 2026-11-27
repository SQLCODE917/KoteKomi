# Candidate Wiki ingestion details

## Outcome and observed behavior

Opening a generated Candidate Wiki identifies which ingestion supplied its content and when that ingestion completed.
At merged baseline `d49021d`, the public command publishes both pages without either detail in their visible content.
The manifest contains ingestion identity, but inspecting it interrupts ordinary reading.
The existing captured-input example reproduces this gap for `igr_older` and `igr_newer`, which share `report.pdf`.
This extends explicit ingestion selection without changing which runs qualify.

## Ownership and constraints

Trace the public build command through selection, view construction, planning, rendering, and Archive publication.
The Application Layer owns interpretation of the selected ingestion; the Exporter renders its page inputs.
The Archive Adapter retains ownership of immutable builds and activation.
Use the selected ingestion's stored completion time, not the current clock, build time, or Source publication date.
Display its identity and a clearly labeled completion timestamp on the index and Document page.
Use an unambiguous timezone-bearing timestamp; equivalent timezone representations must identify the same instant.
If existing eligible records can omit completion time, display its absence honestly without changing eligibility.
The current eligible-record contract requires a completion timestamp; display `Unavailable` when it is absent or lacks timezone information.
Normalize displayed completion instants to UTC with a trailing `Z`.
Keep filename-only and explicit selection, navigation, quotations, and structured audit/citation meaning intact.
Changed output must publish successfully over a pre-feature build for the same ingestion while preserving that build.
A repeated unchanged build reuses its output; builds perform no inference and leave Ledger contents unchanged.
Private decomposition, layout, and fixture arrangement remain implementation decisions under [the normal workflow](agent/implement-tdd-workflow.md).

## Acceptance and evidence

- Selecting the older of two ingestions displays that run's identity and stored completion time on both pages.
- Selecting the newer run changes both details to that run's values, even though its filename is identical.
- The timestamp describes ingestion completion and remains independent of the machine's current time and timezone.
- Publishing after upgrading from existing output succeeds, retains the previous build, and then reuses the new build on repetition.

Use [Testing Rules](agent/testing.md): typed inputs for narrow rules and real connected components for publication claims.
Keep expectations about visible meaning independent of exact Markdown layout or private helper calls.
Reuse [the existing captured-input fixture](../packages/pipelines/tests/fixtures/candidate_wiki/README.md) where the public CLI boundary needs it.
Do not run extraction or create unrelated intelligence solely to prepare these tests.
Keep existing assertions for unchanged behavior; extend evidence only where the new outcome needs it.
Run affected tests and fast checks, then use full PR CI as the full-suite gate.

## UAT and review handoff

Use the documented KoteKomi fixture loader in a fresh temporary directory and the real public command.
Build `igr_older`, read the index and follow its Document link, then build `igr_newer` and compare both details.
A pre-feature build is retained at `/private/tmp/kotekomi-ingestion-details-uat` for the coordinator's upgrade check.
Keep that directory untouched until review; prepare other examples in a separate fresh directory.
Human UAT and merge close the package.
The implementer commits, submits fast checks followed by push as one bounded job to `spymaster`, and ends the turn.
The completion requests review; the reviewer uses current project guidance and existing results.
The coordinator observes full CI and records any corrections in the existing Spymaster feature document.
