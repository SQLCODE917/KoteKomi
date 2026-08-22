# DR-3 Successor Closeout

## Context & Problem

DR-3 implementation commits exist on a historical feature branch.

The historical independent verifier failed because the former verification planner treated its committed receipt as an uncovered path.

The repaired planner now accepts a trusted receipt-only commit.

The frozen DR-3 task cannot include the repaired planner baseline without changing its protected specification.

The **handoff patch** is the net product diff from `5e63f47ca1646a6118c6a2cb356e72662cb2f9e6` through `c50e57665940eb00df93e13a202a11c15073cb0a`.

The **successor** is a new feature task that delivers that handoff patch from the repaired `main` baseline.

Primary end-to-end flow:

1. The Harness creates a successor feature branch from the repaired `main` specification.
2. The successor applies the handoff patch without changing its public behavior.
3. The Harness verifies and promotes the successor through feature-tip and main CI.
4. The Harness closes the historical DR-3 run as superseded by the completed successor.

## Goals

- Users receive the accepted DR-3 hybrid retrieval behavior on `main`.
- The historical DR-3 run remains visible as superseded by a completed successor.
- The Harness deletes both feature branches after their terminal results.

## Requirements

### Handoff delivery

- HD-01: The successor delivers the full handoff patch.
- HD-02: The successor preserves every DR-3 public contract in `Document Hybrid Activation`.
- HD-03: The successor does not add DR-4 behavior or modify DR-1 or DR-2 schema assets.
- HD-04: The successor updates only the source, test, scenario, schema, and check-plan paths that the handoff patch changes.

### Verification and closure

- VC-01: The successor uses the canonical feature-branch, independent-verifier, candidate-CI, promotion, main-CI, and cleanup flow.
- VC-02: The successor runs the DR-3 canonical scenario with the locked deposited PDF and `semantic-validation-v1` profile.
- VC-03: The successor closes the historical task only after the successor result tag and cleanup evidence exist.
- VC-04: The historical closure uses the historical merge handoff closure contract.

## Proposed Architecture

```text
Historical DR-3 patch
          |
          v
Successor feature branch -> normal Harness lifecycle -> main
                                                     |
                                                     v
                                      superseded DR-3 closure
```

The successor task owns delivery of the existing DR-3 behavior.

The existing product components retain the ownership that `Document Hybrid Activation` defines.

The Harness owns verification, promotion, and historical task closure.

## Key Interactions

```text
Harness -> Successor branch: apply handoff patch
Verifier -> Successor branch: write Verification Receipt
CI -> Harness: validate feature tip and main promotion
Harness -> Historical DR-3 run: record superseded result
```

## Data Model

This TDD adds no product record or schema beyond the DR-3 handoff patch.

The successor creates normal Harness evidence and the historical task creates superseded result evidence.

## APIs / Interfaces

The successor preserves the normal DR-3 `kotekomi retrieval build-document` and
`kotekomi retrieval query` interfaces.

## Behavior & Domain Rules

The successor retains exact guard precedence and RRF-60 fusion behavior.

The successor sends selected authoritative node IDs to `ContextPlanner`.

The successor keeps derived index state rebuildable from authoritative representation state.

## Acceptance Criteria

- AC-HD-01: The successor candidate patch equals the handoff patch.
- AC-HD-02: The DR-3 Domain, Application, Adapter, Pipeline, and scenario checks pass.
- AC-VC-01: The canonical DR-3 ingest and query suite pass with the locked PDF and pinned profile.
- AC-VC-02: Feature-tip CI and post-merge main CI pass.
- AC-VC-03: The historical DR-3 run reaches terminal `superseded` state with complete cleanup evidence.

## Reference Implementations

- DR-3 contract: `docs/2026-08-21-document-hybrid-activation.md`.
- Historical product commits: `7be5926aaceedeabc32ce5ca7143d8b2332a6b64` and
  `c50e57665940eb00df93e13a202a11c15073cb0a`.
- Historical closure: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.

## Constraints and Halt Conditions

The successor must halt when its candidate patch differs from the handoff patch.

The successor must halt when the locked PDF or pinned semantic model is unavailable.

The successor must not alter the historical DR-3 TDD or Task Manifest.
