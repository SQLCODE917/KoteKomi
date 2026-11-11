# Deliver the Next Ingestion Improvements

Status: In progress.
The user approved this successor's delivery sequence and delegated semantic review in the implementation request.
Historical IPI remains **Target not met**.

## Operator result and scope

An operator must obtain a complete proposed Assertion for R-DEV-06 and accept a verified Assertion into a disposable Ledger.
An Assertion states one atomic meaning; a ProposedChange retains that proposed record until review.
The required R-DEV-06 meaning is frozen from the reviewed development manifest:

> Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense, in December 2025.

The argument text, time qualifier, and EvidenceTargets must retain exact Source characters.
The agent performs semantic review under delegation; this establishes neither independent validation nor reduced human effort.
Original operator Ledgers remain untouched.

## Delivery order

1. Retain the production promotion on main.
2. Deliver [complete announcement statements](2026-11-11-complete-announcement-statements.md) and integrate after verification.
3. Deliver request-scoped reuse of one validated ingestion context per review command.
4. Exercise supported Assertion acceptance and saved replay on disposable state.
5. Freeze implementation before selecting two previously unused statements from retained development captures.

Each production correction requires focused checks, whole-tree formatting, lint, typecheck, and a human-started full suite.
The human monitors CI and reports terminal results before merge.
The user authorized scoped pushes and merges; repository permissions and protections still apply.
The agent must not bypass these gates.

## Selection and bounds

The announcement outranks onset and agreement statements, which require clausal complements and more argument handling.
The disagreement statement requires coordination, a prepositional argument, and contextual identity.
The INESIA statement has multilingual name boundaries.
Paragraph discovery has recorded failures but no demonstrated corrective mechanism.
The selected announcement already has captured subject and object dependencies.
One bounded typed inspection confirmed `nmod:desc`, nominal `appos`, and month/year `nmod:unmarked` dependencies.
No further diagnostic experiment or evaluation framework is planned.

The second correction removes confirmed duplicate ingestion-context loading in recomposition.
It preserves public signatures and transaction reads of current review and proposal state.
It introduces no persistent or cross-command cache.
Observed command durations will remain separate from unknown human effort.

The scope permits two production corrections, each with one bounded corrective attempt.
Ordinary debugging within the selected contracts remains authorized.
Paragraph discovery repair remains outside this delivery.

## Completion decisions

- Implementation verification: announcement focused and whole-tree checks pass at `6596490`.
  The context reuse correction passes focused checks; its whole-tree gate remains pending.
- Demonstrated capability: R-DEV-06 preserves its required meaning through review, persistence, supported Assertion acceptance, and saved replay.
  The full regression gate also preserves the three promoted development cases.
- Broader successor target: at least one complete additional result among two statements selected after implementation freezes.

Missing the broader target retains safe verified improvements and ends assessment as **Target not met**.
The next decision must compare remaining argument failures and paragraph discovery across Pipeline stages.

## Evidence

- Promotion `5916390` integrated through PR #1 at `32835a2d1c861fa9a964d58218c8a6383d3f7e41`.
- The agent inspected terminal [main CI](https://github.com/SQLCODE917/KoteKomi/actions/runs/42880865063) after the human reported success.
- CI passed; pytest occupied 37m 32s of the 39m 23s job.
- The original promotion's full suite recorded 2,742 passed and three documented skips.
- The development cases retained by that promotion cover Department of Defense policy, Amodei criticism, and Anthropic services integration.
- The isolated successor worktree starts at integrated main; original uncommitted guidance and operator records remain preserved.

## Announcement implementation evidence

The failing-first announcement regressions reproduced missing title selection, nominal completion, and month/year derivation.
The selected correction now retains the exact title and complete platform description while keeping the selected object label unchanged.
Negative regressions require explicit gaps or holds for unrelated, competing, coordinated, clausal, and disconnected descriptions.
An exact name candidate still takes priority over its valid descriptive title.

The disposable production journey exposed a further integration defect before acceptance.
The pending Assertion proposal lacked the explicit `evidence_links` required by the supported review operation.
Recomposition now uses existing evidence validation and replay use cases to bind that specification to the reviewed statement.
Validation and proposal persistence share a transaction.
The injected proposal-write failure proves that both writes roll back together.

The focused journey has passed supported acceptance and saved replay on disposable SQLite and Archive state.
This is delegated agent assessment of R-DEV-06 as a complete `source_report`.
It establishes neither independent truth nor a broader accuracy rate.
The announcement's whole-tree verification and integration have passed.
The latency correction started after announcement integration.
The two additional assessments have not started.

## Focused verification at `3c63b37`

The committed correction passed 87 focused tests with zero skips, failures, or errors.
The run covers `test_announcement_completion.py`, `test_object_content_completion.py`, `test_source_grounded_selection_completion.py`, `test_trigger_time_qualifier.py`, `test_source_grounded_selection.py`, `test_decontextualization_composition.py`, and `test_announcement_review.py`.
The separate `test_ipi_production_promotion.py -k proposal` regression also passed, including evidence-validation rollback.
Whole-tree `ruff format --check .` and `ruff check .` passed.
Changed-file pyright checks passed with zero errors or warnings.
`git diff --check`, local documentation links, and `bash -n scripts/check_ingestion_announcement.sh` passed.
The full suite, schema-generation drift check, and whole-tree typecheck await human execution.

Durable focused records are under `/private/tmp/kotekomi-announcement-evidence-3c63b37/`.
They include `revision.txt`, `exit-code.txt`, `pytest.xml`, `pytest.log`, and the disposable test state under `tests/`.
The supported production journey took 3.93 seconds in this run.
That duration includes test setup, review, recomposition, acceptance, and saved replay; it is not a recomposition benchmark or human-effort measure.

The accepted disposable Ledger is `tests/test_complete_announcement_rev0/state/kotekomi.db` beneath that evidence directory.
Typed reload and evidence replay verified these records:

| Record | Identifier |
| --- | --- |
| Accepted Assertion, `reported`, `source_report` | `ast_c6e9cf486dc508a0b7b43e7fa885b7b4` |
| Approved ProposedChange | `pcg_2c53dbbff1b32dd0a19c4fb9` |
| Review ProvenanceActivity | `prv_1575c54c433f36b39d4e842e` |
| Complete statement EvidenceTarget | `etg_225ea1294b67786ecffdffb1` |
| Successful EvidenceValidationAttempt | `eva_7b9b7e3035c87d141657e88f` |

The test verifies the accepted Actor reference and AssertionEvidenceLink as well as the proposal's approved status in saved replay.
The original operator Ledger remains unchanged.

## Human verification handoff

Run from `/private/tmp/kotekomi-ingestion-announcement`:

```bash
bash scripts/check_ingestion_announcement.sh /private/tmp/kotekomi-announcement-verification
```

The output directory retains `revision.txt`, `working-tree.txt`, `exit-code.txt`, `schemas.log`, `schema-drift.log`, `format.log`, `lint.log`, `typecheck.log`, `pytest.log`, and `pytest.xml`.
Disposable test Ledgers and Archives remain beneath `tests/`.
The script refuses to overwrite an existing verification record.
Use a new output directory for an authorized rerun.

Completion probe:

```bash
cat /private/tmp/kotekomi-announcement-verification/exit-code.txt
```

The file exists only after termination.
Durable evidence summary:

```bash
tail -n 40 /private/tmp/kotekomi-announcement-verification/pytest.log
```

Success requires exit code zero, the intended revision, schema consistency, passing formatting, lint, typecheck, and the full suite.
Every skip requires an inspected reason.
The agent will inspect terminal records after the human reports completion, then prepare the authorized push and PR.
CI and integration must finish before the latency correction begins.

## Whole-tree verification at `6596490`

The human started the declared check command and reported exit code zero.
The agent inspected the terminal records in `/private/tmp/kotekomi-announcement-verification/`.
`revision.txt` identifies `65964909223dc3108c13124cc529b4d647120714`; `working-tree.txt` is empty.
Schema generation, schema drift, whole-tree formatting, lint, and typecheck passed.
JUnit records 2,765 passed tests, three skips, zero failures, and zero errors.
The full suite took 971.88 seconds, or 16m 11s.
One skipped test requires an explicitly selected live LM Studio model.
Two skipped tests require the original retained operator run, which this isolated worktree excludes.

The complete announcement acceptance and saved-replay test passed in 4.158 seconds.
All six promotion regressions passed, including Department of Defense policy, Amodei criticism, Anthropic services integration, and transaction failure injections.
This confirms implementation verification and retention on the named captured development cases.
The broader successor target remains unassessed.
The following section records the announcement's subsequent integration and terminal CI result.

## Announcement integration and context reuse

The user reported announcement integration and green CI for `6e780b4f91d1928dd375bdc98bd96b9d0bb337aa`.
The agent fetched main and inspected terminal [CI run 43014981509](https://github.com/SQLCODE917/KoteKomi/actions/runs/43014981509).
CI passed; pytest took 39m 58s of the 41m 41s job.
This duration is an observation of the complete suite, not a recomposition benchmark.

The [context reuse correction](2026-11-11-review-command-context-reuse.md) removes duplicate loading within recomposition.
The failing-first captured regression observed two paragraph loads where the required count was one.
The private context now carries validated paragraph, Event, token artifact, TextView, and candidate inventory values within one command.
Recomposition still reads current review, identity, evidence, and proposal state through the existing transactions.
No persistent or cross-command cache is introduced.

The focused captured test verifies one paragraph load, token load, and inventory construction per recomposition.
A retry performs a new load and remains idempotent.
A later command rejects a corrupt token artifact instead of using stale values.
The same test separately accepts the correct Assertion and verifies evidence, provenance, and saved replay.

| Observed command | Seconds | Condition |
| --- | ---: | --- |
| First announcement recomposition | 1.043399 | Integrated announcement code, instrumented failing regression |
| First announcement recomposition | 0.532524 | Working tree with request-scoped reuse |
| Retry announcement recomposition | 0.512659 | Same captured test after reuse |

These are single observed calls on one captured development case.
They establish neither a general latency ratio nor reduced human effort.
The corrected command demonstrates one validated ingestion-context load; whole-suite verification remains pending.
No whole-suite or CI duration reduction is claimed.
Paragraph discovery repair and further argument extensions remain outside this increment.
CI now prints the 30 slowest test phases through the existing pytest `--durations=30` option.
This matches the local verification command and provides timing evidence without changing test selection or concurrency.

## Context verification and handoff

The focused announcement acceptance and saved-replay regression passed with the context-count and corruption assertions.
The captured derived-outcome failure and recovery regression passed in 13.53 seconds.
Two operator packet regressions passed, preserving rejection of a changed Source and an Event from another run.
Whole-tree `ruff format --check .` and `ruff check .` passed.
Pyright passed on the changed implementation and test with zero errors or warnings.
Documentation links and `git diff --check` passed.
The whole-tree typecheck, schema-drift check, full suite, CI, and integration remain pending for this increment.

Run the existing verification command from `/private/tmp/kotekomi-ingestion-context`:

```bash
bash scripts/check_ingestion_announcement.sh /private/tmp/kotekomi-context-verification
```

The output directory retains `revision.txt`, `working-tree.txt`, `exit-code.txt`, `schemas.log`, `schema-drift.log`, `format.log`, `lint.log`, `typecheck.log`, `pytest.log`, and `pytest.xml`.
Disposable test Ledgers and Archives remain beneath `tests/`.
The script refuses to overwrite a previous verification record.

Completion probe:

```bash
cat /private/tmp/kotekomi-context-verification/exit-code.txt
```

Durable evidence summary:

```bash
tail -n 40 /private/tmp/kotekomi-context-verification/pytest.log
```

Success requires exit code zero, the intended revision, a clean working tree, schema consistency, and passing formatting, lint, typecheck, and full-suite results.
Every skip requires an inspected reason.
The agent will inspect terminal records after the human reports completion, then prepare the authorized push and PR.
The two additional statements will be selected and assessed after integration with the implementation frozen.

## Context verification correction

The human-started check at `1a41ddbe66026efd28d179521dfe2c04fa637cfb` exited with code one.
The agent inspected `/private/tmp/kotekomi-context-verification/` after the human reported termination.
Schema generation, schema drift, formatting, and lint passed.
Whole-tree pyright rejected three private imports used by the test's counting wrappers.
Pytest did not start; this run produced no test result or runtime failure.

The test now imports each wrapped function from its owning module.
It still patches the review Pipeline's bindings and calls the real validators.
The production implementation remains unchanged.
Pyright on the changed test and implementation now passes in this worktree's own environment.
The focused acceptance, context-count, corruption, and replay regression also passes.
The whole-tree gate remains pending.

Run the existing check from `/private/tmp/kotekomi-ingestion-context` with a fresh output directory:

```bash
bash scripts/check_ingestion_announcement.sh /private/tmp/kotekomi-context-verification-v2
```

Outputs retain the same revision, working-tree, exit-code, per-step log, JUnit, and disposable-state paths beneath the new directory.
The original failed verification record remains preserved.

Completion probe:

```bash
cat /private/tmp/kotekomi-context-verification-v2/exit-code.txt
```

Durable evidence summary:

```bash
tail -n 40 /private/tmp/kotekomi-context-verification-v2/pytest.log
```

Success still requires every declared whole-tree check to pass with exit code zero and inspected skip reasons.
