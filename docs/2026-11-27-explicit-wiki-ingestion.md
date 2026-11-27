# Explicit ingestion selection for Candidate Wiki builds

## Outcome and current behavior

An operator or agent can name a particular ingestion and publish its Candidate Wiki without interactive input.
Currently `wiki build <filename> --candidate` selects a sole eligible ingestion or prompts when several share the filename.
The command has no explicit ingestion selector.
Other commands use `--ingestion-run`; investigate that convention for this optional selector while preserving filename-only use.
The existing promise that human users need no canonical Domain ID remains satisfied by the interactive workflow.

## Ownership and constraints

Trace selection through the candidate view, rendering, and publication before choosing the implementation.
The Pipeline owns CLI interaction and composition, the Application Layer owns candidate eligibility and view construction, and the Archive Adapter owns immutable publication and activation.
Retain those decision owners and the existing authorization, identity, eligibility, and publication contracts.
The optional selector must not silently choose another ingestion or bypass validation.
Private decomposition, work order, and fixtures remain the implementing agent's decisions.
Use current [implementation guidance](agent/implement-tdd-workflow.md) for contract-preserving discoveries and package corrections on this branch.

## Acceptance examples

- With two eligible ingestions sharing a filename, explicitly selecting the older ingestion publishes that ingestion's Wiki without prompting.
- Unknown, ineligible, and filename-mismatched selections fail clearly and preserve the currently published Wiki.
- Repeating the same valid selection reuses its existing build; selecting the other ingestion publishes its corresponding output through the existing mechanism.
- The Wiki build performs no inference and changes no accepted Ledger intelligence.
- Filename-only single-ingestion and interactive multiple-ingestion use retain their behavior.

## Evidence and completion

Selection is a pure operation over typed ingestion records; it does not read storage or construct Wiki content.
The Pipeline supplies the records and retains I/O ownership.
Selection tests use only those inputs.
Public-command tests exercise real storage, view construction, rendering, and publication using [captured inputs owned by KoteKomi](../packages/pipelines/tests/fixtures/candidate_wiki/README.md).
Their assertions cover selected identity, rejected selection, reuse, preserved output, and unchanged Ledger contents.
The input fixture has no proposals or evidence records because their interpretation is outside selection and publication.
Choose evidence at the changed connection that distinguishes the intended ingestion from a plausible wrong selection.
Preserve independent expectations and existing tests for unchanged behavior; add only missing proof.
Use focused checks while implementing, fast checks before candidate publication, and full PR CI as the full-suite merge gate.
Use the same KoteKomi-owned fixture for reproducible CLI UAT in a fresh temporary directory.
It must let the operator exercise the accepted behavior through the real public command without touching their existing Ledger or Archive.
This fixture demonstrates selection and publication, not ingestion quality.
Human UAT and merge close the package.

## Review handoff

The implementing agent is the sole product-code writer in the shared checkout.
After committing, submit fast checks followed by push as one bounded job addressed to `spymaster`, then end the turn.
The generated completion is the review request for its named candidate; no forwarding turn or separate request is required.
Spymaster reads this package and the updated project guidance, reviews the diff and evidence, and sends approval to operator or one actionable revision request to implementer-1.
Review the promised behavior and preserved contracts rather than conformity to a private implementation proposal.
Use existing results and focused probes for concrete concerns; do not repeat the full suite or create another receipt.
A failed or uncertain job is inspected before any retry.
The coordinator observes full CI and records what required intervention using existing comments and logs.
