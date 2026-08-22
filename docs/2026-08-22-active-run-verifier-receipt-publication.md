# Active-Run Verifier Receipt Publication

## Context & Problem

The Harness verifies a feature candidate through `kotekomi-agent verify-candidate`.
An active run supplies task, run, and state-root arguments.
The verifier must publish a receipt commit on the remote feature branch.
The verifier must index the same receipt in the active run evidence catalog.
The live active-run invocation returned no result and published no receipt.
Existing verifier tests do not combine an active run, a remote feature branch, and receipt publication.

**Terms**

- **Active run** means a run with canonical specification, feature branch, and candidate evidence.
- **Receipt commit** means one commit that changes only the canonical verification receipt path.
- **Local remote** means a disposable bare Git repository used as `origin` in a test.

Primary end-to-end flow:

1. The Harness test creates an active run and pushes its candidate feature tip to the local remote.
2. The verifier checks the frozen candidate in a detached worktree.
3. The verifier writes one receipt commit and advances the remote feature branch.
4. The verifier indexes the receipt for the active run.
5. The CLI emits the complete JSON result.

## Goals

- Operators receive one machine-readable result from every active verifier invocation.
- A passing active verifier invocation publishes and indexes one matching receipt.
- A deterministic active verifier failure publishes no receipt and reports its diagnostic.

## Requirements

### Candidate verifier

- CV-01: The verifier accepts an active run when its canonical evidence matches the supplied revisions.
- CV-02: The verifier publishes one receipt commit when the remote feature tip equals the candidate.
- CV-03: The verifier advances the remote feature branch to the receipt commit.
- CV-04: The verifier indexes the published receipt as `candidate_verification_receipt`.
- CV-05: A repeated invocation reuses the matching receipt and does not create another receipt commit.
- CV-06: A remote-tip mismatch returns an `invalid` result with a deterministic diagnostic.

### CLI

- CLI-01: The CLI emits the verifier JSON result for every active invocation.

## Proposed Architecture

The candidate verifier owns receipt publication and catalog indexing.
The local remote fixture owns Git transport proof.

```text
active run evidence
        |
        v
candidate verifier -> local remote feature branch
        |                     |
        v                     v
run evidence catalog      receipt commit
```

## Key Interactions

```text
test -> verifier: active run and candidate revisions
verifier -> local remote: push receipt commit
verifier -> evidence catalog: index receipt
verifier -> test: JSON result
```

## Data Model

This TDD creates no new evidence type or receipt field.
The existing `candidate_verification_receipt` record remains the active-run receipt record.

## APIs / Interfaces

The public `verify-candidate` command keeps its current arguments and JSON result shape.

## Behavior & Domain Rules

The verifier writes a receipt only after it validates the active run and remote candidate tip.
The verifier indexes a receipt only after the local remote points to its receipt commit.
The verifier returns an `invalid` result when the remote tip does not equal the candidate.

## Acceptance Criteria

- AC-CV-01: A local remote fixture proves successful active receipt publication and indexing.
- AC-CV-02: The fixture proves a repeated invocation reuses the first receipt commit.
- AC-CV-03: The fixture proves a remote-tip mismatch returns JSON and leaves the remote unchanged.
- AC-CLI-01: The public CLI subprocess emits parseable JSON for each active fixture invocation.
- AC-CV-04: Existing independent-verifier receipt tests, Ruff, and Pyright pass.

## Reference Implementations

- Verifier behavior: `packages/devtools/src/kotekomi_devtools/candidate_verifier.py`.
- Verifier subprocess tests: `packages/devtools/tests/acceptance/test_independent_verifier_receipt_contract.py`.
- Canonical evidence writes: `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

## Constraints and Halt Conditions

The implementation stops if the fixture requires GitHub access.
The implementation stops if it adds a broad exception handler that hides a deterministic failure.
The implementation stops if it changes receipt fields or a public verifier argument.
