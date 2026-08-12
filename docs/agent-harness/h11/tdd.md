# H11 TDD

## Public behavior

`kotekomi-agent lifecycle-check` remains the public lifecycle gate. For `--phase main`, the command requires:

- `--main-base MAIN_BASE`
- `--verified VERIFIED`
- `--head HEAD`

When any required revision is missing, the JSON output must remain fail-closed and must identify the missing argument explicitly. The diagnostic set must allow an operator to repair the invocation without inferring which option was omitted.

## Diagnostic contract

The main phase must not collapse all missing main revisions into a single opaque error. Missing options should produce stable diagnostics with distinct locations and rules. Acceptable rules include:

- `main_requires_main_base`
- `main_requires_verified`
- `main_requires_head`

The command may emit one diagnostic per missing option. It may keep an aggregate diagnostic only if the specific missing-option diagnostics are also present.

## CLI help contract

The lifecycle-check help text should make the main phase invocation clear enough for a human operator to copy or reconstruct the required argument set.

## Early candidate gate contract

Candidate flow guidance must place `lifecycle-check --phase candidate` immediately after the candidate commit and before expensive dogfood verification execution or CI. This ensures budget, scope, and protected-artifact failures surface before time-consuming checks.

## Test strategy

- Unit tests should exercise the missing main-option diagnostics without requiring network or GitHub state.
- Acceptance tests should cover the lifecycle-check CLI behavior and the AGENTS guidance.
- Existing lifecycle tests remain active.
