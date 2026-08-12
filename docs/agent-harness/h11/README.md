# H11 Lifecycle Ergonomics and Early Gates

## Task id

`harness-11-lifecycle-ergonomics-early-gates`

## Context

H10 and the H10 log-integrity follow-up completed verification execution accountability. The next dogfood task is to remove two operator hazards observed during that work:

1. Main lifecycle invocations can omit `--main-base`, `--verified`, or `--head`, but the diagnostic currently collapses all cases into one generic missing-merge-revisions message.
2. A candidate can spend time on local checks, dogfood verification execution, or CI before lifecycle rejects it for an avoidable candidate-phase issue such as a budget violation.

## Goal

Make the harness more self-correcting by improving lifecycle-check diagnostics and by requiring candidate lifecycle earlier in the candidate flow.

## Scope

H11 is a small harness ergonomics task. It may change lifecycle diagnostics, CLI help text, compact package-level agent guidance, and lifecycle tests.

## Non-goals

H11 does not change verification-plan semantics, run-check execution semantics, verify-checks record semantics, receipt schema, task manifest schema, or GitHub CI behavior.
