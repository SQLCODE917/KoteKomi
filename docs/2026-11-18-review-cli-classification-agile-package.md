# Review CLI Classification Reliability Agile Package

- Status: Proposed; blocked pending specification acceptance
- Program ID: review-cli-classification-reliability
- Deliverable: RCR-01
- Baseline source: c91089f17bcf9e0ccb9e61fa68fc5079398637f6
- TDD: [Review CLI Classification Choices](2026-11-18-review-cli-classification-choices.md)

## User Outcome

An operator selects an advertised review classification and reaches the existing review workflow.
The command rejects unsupported classifications before it accesses storage.

## Selection and Bounds

The current CLI advertises four strings absent from the Domain Core enums.
The command constructs those enums after loading its Event review packet.
This is an observed deterministic input defect.
The selected correction removes invalid alternatives and retains the existing valid subset.
It introduces no alias or new classification.
Semantic truncation requires a broader content contract and is outside this trial.
Changing ingestion exit semantics affects several interfaces and is outside this trial.
This package permits one implementation approach and one corrective attempt.
Setup ends when the existing Harness reports a blocking lifecycle requirement.
The scope is one production file, one test file, operator documentation, and the check plan.
Production changes must remain under 20 changed lines.

## Deliverable Tracker

| ID | Goal | Status | Evidence |
|---|---|---|---|
| RCR-01 | Reject invalid review classification strings before storage access | Blocked at specification gate | Specification PR pending; no feature checks run |

## Acceptance and Stop Decisions

The TDD defines the finite parser and operational acceptance criteria.
Feature completion requires the declared tests, formatting, lint, and typecheck.
This trial makes no extraction accuracy or operator-effort claim.
The existing Harness controls implementation eligibility.
This draft specification PR tests the GitHub handoff only.
Do not implement until the harness specification gate is satisfied.
Do not merge this PR as part of the handoff test.
A blocking Harness status ends implementation work until its prerequisite is resolved.
A local snapshot does not establish an upstream checkout or remote lifecycle evidence.

## Harness Assessment Protocol

Record the actual status, next action, identifiers, diagnostics, and evidence paths.
Record setup friction and commands attempted.
Keep feature verification separate from Harness lifecycle results.
Assess only stages actually exercised.
Do not claim candidate verification, CI, completion, or measured effort when unobserved.
Preserve failed output and report the smallest prerequisite for continuation.
