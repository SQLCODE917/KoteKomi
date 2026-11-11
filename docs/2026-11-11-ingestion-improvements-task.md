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

- Implementation verification: announcement focused checks pass; whole-tree verification remains pending.
  The context reuse correction has not started.
- Demonstrated capability: R-DEV-06 preserves its required meaning through review, persistence, supported Assertion acceptance, and saved replay.
  Retention of the three promoted cases awaits the full regression gate for this increment.
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
Whole-tree verification and integration remain pending.
The latency correction and the two additional assessments have not started.

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
