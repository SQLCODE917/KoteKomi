# H12 Step Script Safety

## Task id

`harness-12-step-script-safety`

## Context

H10 and H11 exposed a repeated dogfood failure mode: large generated shell scripts performed ad hoc patching and recovery. When those scripts failed, they left dirty candidate branches and required bespoke reset scripts. The target harness features were sound, but orchestration defects slowed implementation.

## Goal

Create deterministic harness support for local step preflight, known failed-candidate recovery, and failure recording, then update operator guidance so generated step scripts use those commands.

## Scope

H12 may add devtools commands, tests, and compact guidance for:

- step preflight
- safe recovery from a known failed local candidate branch
- recording a failed local step as a receipt
- standard generated script expectations

## Non-goals

H12 does not change lifecycle-check, verification-plan selection semantics, run-check execution semantics, verify-checks validation semantics, task manifest schema, or CI configuration.
