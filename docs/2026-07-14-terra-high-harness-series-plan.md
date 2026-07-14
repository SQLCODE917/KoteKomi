# Terra-High Agent Harness Series Plan

## Status

Document class: Design Series Plan

Planning status: Accepted

Planning baseline: `d8b8e854fefd832b42b07a979471ff110e8a65ac`

Authoritative baseline verification: GitHub Actions run `29350049516`

Target implementation profile: Terra with high reasoning

## 1. Context & Problem

KoteKomi has repeatedly required corrective commits after an implementation agent reported completion.

The correction tails exposed missing authority, scope, failure, integration, and verification contracts.

The repository already defines strong architecture, testing, and TDD-writing rules.

Those rules remain advisory during task execution.

The repository does not define an immutable task boundary.

The repository does not separate candidate completion from independent verification.

The implementing agent can currently change the code, tests, documentation, and completion checklist together.

This series creates an enforceable workflow for small deterministic Terra-high implementation tasks.

## 2. Goals

- Define one machine-readable execution boundary for each Terra-high task.
- Freeze the accepted Leaf TDD before implementation begins.
- Freeze independent acceptance checks before implementation begins.
- Prevent the implementer from changing the task or its protected acceptance oracle.
- Separate candidate completion, leaf verification, series integration, and retention.
- Verify candidates from Git revisions rather than an agent completion statement.
- Preserve verified acceptance checks as permanent regression requirements.
- Measure prospective task performance against KoteKomi history.
- Keep every implementation leaf within Terra-high scope.
- Keep product packages independent from the harness package.

## 3. Non-Goals & Forbidden Approaches

### Non-Goals

- This series does not implement a KoteKomi product capability.
- This series does not redesign Domain Core, Application Layer, Adapters, or Pipelines.
- This series does not repair platform-sensitive PDF goldens.
- This series does not make macOS PDF output authoritative over Linux CI output.
- This series does not certify AP, Reuters, or another external provider.
- This series does not migrate every historical `CHECK_PLAN.md` rule immediately.
- This series does not execute remote model calls in CI.

### Forbidden Approaches

- Do not submit this series plan directly to an implementation agent.
- Do not combine several harness leaves into one Terra-high task.
- Do not let the implementer edit its Leaf TDD.
- Do not let the implementer edit protected black-box acceptance tests.
- Do not let the implementer mark its own task verified.
- Do not treat a successful local macOS PDF run as the authoritative full-suite oracle.
- Do not weaken an existing product test to make a harness task pass.
- Do not use arbitrary shell command strings in task manifests.
- Do not import KoteKomi product packages from the harness package.
- Do not import the harness package from KoteKomi product packages.
- Do not automatically re-prompt a failed oversized task.

## 4. Terms

**Design Series Plan**

A planning document that coordinates several independently shippable Leaf TDDs.

A Design Series Plan is not an implementation assignment.

**Leaf TDD**

An accepted technical design document for one independently shippable contract slice.

One accepted Leaf TDD maps to one Terra-high task.

**Task Manifest**

A machine-readable execution boundary for one accepted Leaf TDD.

The Task Manifest identifies scope, authority, protected files, checks, and stop conditions.

**Protected Acceptance Artifact**

A prewritten black-box test, fixture, golden file, TDD, or Task Manifest.

The implementation agent cannot change a Protected Acceptance Artifact.

**Candidate Commit**

The Git commit produced by one Terra-high implementation run.

A Candidate Commit records provisional completion only.

**Verification Receipt**

A machine-generated JSON record that identifies the exact candidate and verification results.

Only the independent verifier creates a successful Verification Receipt.

**Acceptance Registry**

The durable list of active verified task checks.

A registry entry remains active until an approved supersession replaces it.

**Retained Task**

A verified task whose registered checks continue passing on later mainline revisions.

**Series Closure Contract**

A prewritten set of public flows, fault cases, forbidden paths, and integration fixtures.

The series verifier uses this contract after all required leaves pass.

## 5. Design Commitments

### 5.1 Fixed implementation profile

Every implementation task targets Terra with high reasoning.

Planning must shrink work until it fits that profile.

Planning must not escalate model effort to compensate for unresolved design.

### 5.2 Small execution units

A Terra-high task has one dominant observable outcome.

A Terra-high task changes one closely related contract family.

A Terra-high task introduces or changes at most one external side-effect boundary.

A wiring task can call several established ports only after their contracts are verified.

### 5.3 Planning owns ambiguity

Collaborative planning selects algorithms before algorithm implementation.

Collaborative planning defines symbol ownership before refactoring.

Collaborative planning defines state transitions before orchestration.

Collaborative planning defines failure and retry behavior before adapter wiring.

The implementation agent chooses private helpers and local control flow.

### 5.4 Independent verification

The implementer can report candidate completion.

The verifier decides whether the candidate satisfies the frozen task.

The verifier performs no product-code edits.

### 5.5 Durable acceptance

A verified task registers permanent acceptance checks.

Later tasks run all active checks affected by their changes.

A later task cannot remove a check without an explicit supersession.

### 5.6 Progressive disclosure

The root `AGENTS.md` remains a concise repository map.

Detailed task workflow rules live in `docs/agent/agent-task-workflow.md`.

Harness package rules live in `packages/devtools/AGENTS.md`.

Each implementation task loads only its manifest, Leaf TDD, protected oracle, and bounded references.

## 6. Authority Model

| Decision | Authoritative record |
|---|---|
| Product behavior | Accepted Leaf TDD at a fixed digest |
| Task execution boundary | Task Manifest at a fixed digest |
| Acceptance oracle | Protected tests, fixtures, goldens, and commands |
| Implementation result | Candidate Commit |
| Verification result | Verification Receipt |
| Durable task state | Acceptance Registry |
| Series completion | Series Verification Receipt |
| Experimental interpretation | Experiment Outcome record |

The implementing agent owns only the Candidate Commit.

The planning authority owns the Leaf TDD and Task Manifest.

The verification authority owns the Verification Receipt and registry promotion.

## 7. Harness Architecture

```text
Design Series Plan
        |
        v
     Leaf TDD --------> Protected Acceptance Artifacts
        |                             |
        v                             |
   Task Manifest                      |
        |                             |
        v                             v
 Terra-high Implementer ------> Candidate Commit
                                      |
                                      v
                              Independent Verifier
                                      |
                                      v
                             Verification Receipt
                                      |
                                      v
                              Acceptance Registry
                                      |
                              +-------+-------+
                              |               |
                              v               v
                       Retained Checks   Experiment Metrics
```

### Planning documents

Planning documents define product choices, task boundaries, and series closure.

### Task manifests

Task manifests define execution metadata without prescribing private implementation structure.

### Devtools package

`packages/devtools` contains the harness parser, validators, verifier, registry tooling, and CLI.

The package name is `kotekomi-devtools`.

The command name is `kotekomi-agent`.

### Verification receipts

Verification receipts bind one manifest, execution base, candidate revision, and result set.

### Acceptance registry

The registry identifies every active permanent task check.

### Experiment records

Experiment records preserve machine facts and human-reviewed failure classifications separately.

## 8. File Layout

```text
docs/
  agent/
    agent-task-workflow.md
    writing-tdds.md
  2026-07-14-terra-high-harness-series-plan.md
  CHECK_PLAN.md

packages/
  devtools/
    AGENTS.md
    pyproject.toml
    src/
      kotekomi_devtools/
    tests/
      acceptance/
      unit/

.agent/
  schemas/
  tasks/
  series/
  receipts/
  experiments/

tests/
  acceptance/
    task-registry.toml
```

The `.agent` directory contains tracked contracts and receipts.

Ephemeral command output remains outside the repository.

## 9. Runtime Verification Profiles

### Portable local profile

The portable local profile runs on the developer workstation.

It covers harness unit tests, harness acceptance tests, Ruff, Pyright, and deterministic file checks.

A task can add other local checks only when they are platform-independent.

### Authoritative Linux profile

GitHub Actions provides the authoritative full repository verification environment.

The current authoritative environment uses Ubuntu, Python 3.12, Poppler, and qpdf.

A candidate cannot become leaf verified until its required Linux profile passes.

### Private conformance profile

Private provider fixtures and credentials use a separate entitlement-gated profile.

Private conformance does not run in public CI.

Public contract verification and private provider certification remain distinct states.

## 10. Git Protocol

The process preserves specification, candidate, and verification commits.

```text
B  verified mainline baseline
|
S  specification commit
|  Leaf TDD
|  Task Manifest
|  Protected Acceptance Artifacts
|
C  Terra-high Candidate Commit
|
V  independent verification commit
   Verification Receipt
   Registry promotion
```

The Candidate Commit must descend from the specification commit.

The verifier rejects changes to protected artifacts between `S` and `C`.

The verification commit cannot change product or harness implementation code.

Do not squash, rebase, or amend a candidate after successful verification.

Any code change after verification requires another candidate and receipt.

## 11. Task States

### Design document states

```text
draft
accepted
superseded
```

### Task states

```text
ready_for_terra_high
candidate_complete
leaf_verified
retained
superseded
```

The implementer can report `candidate_complete`.

Only the verifier can establish `leaf_verified`.

A verified task becomes retained after ten consecutive mainline CI passes.

A retention failure resets the consecutive-pass count.

### Series states

```text
planned
series_integrated
retained
superseded
```

Series integration requires every required leaf and the frozen Series Closure Contract.

## 12. Terra-High Readiness Gate

A Leaf TDD can become `ready_for_terra_high` only when every condition passes.

- The Leaf TDD has one dominant observable outcome.
- The Leaf TDD changes one closely related contract family.
- The Leaf TDD identifies one public or testable entry point.
- The Leaf TDD identifies the authoritative record and identity key.
- The Leaf TDD defines the exact inclusion and selection scope.
- The Leaf TDD changes at most one external side-effect boundary.
- The Leaf TDD defines failure, cleanup, retry, and idempotency behavior.
- The Leaf TDD defines retained and forbidden legacy behavior.
- The Leaf TDD includes at least one decisive negative proof.
- Every blocking acceptance criterion has one executable interpretation.
- Required protected acceptance artifacts exist before implementation.
- Required prerequisites already have successful receipts.
- The task does not depend on a later leaf for current completion.
- The task contains no unresolved Halt Condition.
- The task can be reverted without reverting unrelated work.
- The task manifest identifies a portable or authoritative execution profile.
- The task manifest limits changed paths.
- The task manifest names stop conditions for unexpected scope discoveries.

A task that fails this gate returns to collaborative planning.

## 13. Protected Acceptance Rules

The specification commit freezes these records:

- The accepted Leaf TDD.
- The Task Manifest.
- Black-box acceptance tests.
- Normative fixtures.
- Normative golden files.
- Required command definitions.
- Series closure fixtures that apply to the task.

The implementer can add implementation-focused unit tests.

The implementer cannot change a protected record.

An acceptance change requires a new specification revision.

The new revision records whether the cause was a specification gap or oracle gap.

## 14. Failure Classification

| Classification | Meaning | Required response |
|---|---|---|
| `implementation_defect` | The frozen contract was clear and the implementation was wrong | Create a narrow corrective task |
| `specification_gap` | Required behavior was not pinned | Return to collaborative planning |
| `scope_gap` | The leaf contained more than one viable task | Split the Leaf TDD |
| `oracle_gap` | The acceptance oracle could not distinguish correctness | Revise the protected oracle |
| `integration_gap` | Leaves passed but the series public flow remained incomplete | Revise series planning |
| `environment_gap` | The required runtime or fixture was unavailable or unstable | Repair the harness environment |
| `regression` | A later task broke a retained contract | Block the later task |
| `approved_scope_change` | The behavior is genuinely new | Create a new product TDD |

The verifier reports machine outcomes.

A human reviewer assigns semantic failure classifications.

## 15. Series Leaf Inventory

This inventory defines intended boundaries.

Each leaf still requires its own collaborative readiness review.

| Order | Leaf | Dominant outcome | Target size |
|---:|---|---|---|
| H1 | Task Manifest contract and validation | Accept or reject one manifest with stable diagnostics | M |
| H2 | Task preflight and protected-oracle locks | Prove one task is ready to begin | M |
| H3 | Candidate verification and receipt generation | Verify one candidate and emit one receipt | M |
| H4 | Protected acceptance integrity checks | Reject common oracle weakening | S |
| H5 | Acceptance registry and promotion | Promote one successful receipt into durable task state | M |
| H6 | Retained acceptance runner | Execute all active retained checks for one profile | M |
| H7 | Generated `CHECK_PLAN.md` projection and CI integration | Keep registry checks visible and enforced | M |
| H8 | Series Manifest and series verifier | Verify one frozen Series Closure Contract | M |
| H9 | Experiment Outcome contract and metrics | Measure prospective task performance | M |
| H10 | Historical KoteKomi baseline backfill | Compute comparable historical episode metrics | S-M |

Do not elaborate every leaf before H1 begins.

Elaborate only the next one or two leaves.

Split a listed leaf when its readiness review exceeds Terra-high scope.

## 16. Bootstrap Protocol

The complete verifier does not exist for H1.

H1 uses a manual frozen-oracle bootstrap.

The planning commit contains the H1 Leaf TDD, manifest, schema, tests, and fixtures.

The user records their digests before Terra begins.

Terra receives only the allowed implementation paths.

The user runs the protected checks independently after the candidate.

The user confirms that protected paths did not change.

H1 receives a bootstrap receipt marked `manual_frozen_oracle`.

H2 can use the same bootstrap mode.

H3 and later leaves use the automated verifier when their prerequisites permit it.

Bootstrap results remain separate from completed-harness prospective results.

## 17. Measurement Plan

### Cohorts

| Cohort | Purpose |
|---|---|
| `historical` | Measure correction tails before the new process |
| `harness_bootstrap` | Measure H1 and H2 under manual frozen-oracle verification |
| `harness_prospective` | Measure later harness leaves under growing automation |
| `product_prospective` | Measure product leaves under the completed harness |

Do not combine cohort pass rates.

### Primary metric

The primary metric is first authoritative verification success.

A success requires the first frozen candidate to pass without human rebriefing.

### Secondary metrics

- Preflight rejection count.
- Human rebrief count.
- TDD revision after candidate completion.
- Protected-oracle revision after candidate completion.
- Scope escape count.
- Corrective diff burden.
- Verified-task reopen count.
- Retention regression count.
- Failure classification distribution.
- Results by task class and target size.

A preflight rejection is a successful prevention event.

### Initial calibration target

Use the first ten product leaves as the first product cohort.

Target at least eight first-candidate verification successes.

Target zero scope escapes.

Target zero protected-oracle changes during implementation.

Target zero verified tasks reopened for omitted original scope.

Target zero retention regressions during the first ten-run window.

## 18. Series Closure Contract

The series closes through a disposable Git repository fixture.

The fixture must prove these flows:

1. A valid Task Manifest passes validation.
2. A valid specification commit passes preflight.
3. An in-scope candidate passes verification.
4. An out-of-scope candidate fails verification.
5. A protected TDD edit fails verification.
6. A protected acceptance-test edit fails verification.
7. A skipped protected check fails integrity validation.
8. A nondeterministic declared output fails repeated verification.
9. A successful receipt promotes into the registry.
10. A retained-check run executes the promoted task.
11. A supersession preserves historical receipt evidence.
12. A series cannot integrate before every required leaf passes.
13. Product packages remain independent from `kotekomi-devtools`.
14. The full authoritative Linux repository profile passes.

The Series Closure Contract must exist before the final leaf begins.

## 19. First Planning Target

The first Leaf TDD is H1.

H1 defines the Task Manifest contract and validation command.

H1 does not inspect Git history.

H1 does not execute acceptance commands.

H1 does not create verification receipts.

H1 does not modify the acceptance registry.

H1 does not integrate CI.

H1 accepts TOML input.

H1 validates input against a versioned JSON Schema.

H1 produces stable machine-readable diagnostics.

H1 rejects arbitrary shell command strings.

H1 imports no KoteKomi product package.

## 20. Review Gate

Accept these decisions before authoring the H1 Leaf TDD:

- Use `packages/devtools` for the independent harness package.
- Use `kotekomi-devtools` as the package name.
- Use `kotekomi-agent` as the command name.
- Use TOML for task and series manifests.
- Use JSON Schema for manifest and receipt contracts.
- Use canonical JSON for verification receipts.
- Track `.agent` contracts and receipts in Git.
- Preserve separate specification, candidate, and verification commits.
- Use GitHub Actions as the authoritative full Linux verifier.
- Keep local macOS checks limited to portable task checks.
- Protect the Leaf TDD, Task Manifest, black-box tests, fixtures, and goldens.
- Elaborate only H1 after this plan is accepted.
