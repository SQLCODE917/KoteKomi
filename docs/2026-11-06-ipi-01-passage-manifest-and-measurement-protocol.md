# IPI-01 Passage Manifest and Measurement Protocol

- Status: Proposed for human approval
- Package: [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md)
- Baseline revision: `7dc9a44`
- Branch: `feature/ipi-intelligence-pipeline-improvement`
- Reviewer role: a human who agrees the passages, reference statements, and rubric before any measurement run.
- Operator role: a human who runs the workflow and records outcomes and timing.
- Implementing agent: this branch's agent, which never inspects reserved passages.

## 1. Decisions requested

The package needs one human decision before baseline measurement can start.

| ID | Decision | Effect if approved |
| --- | --- | --- |
| D1 | Approve the six development passages and their reference statements in section 3 | The development partition is fixed for the package |
| D2 | Approve the completeness rubric in section 5 and the attempt budget in section 6 | Both conditions are scored the same way |
| D3 | Approve the numerical targets and routes in section 7 | The acceptance gate is fixed before any result exists |
| D4 | Authorize the reserved custody run in section 4 and record its sealed digest | The reserved partition exists outside the agent's context |

A rejection of any item is a scope decision. The agent records it and does not measure against an unapproved manifest.

## 2. Inspected material record

The agent has read the following material.
Reserved passages must not come from it.

| Material | Extent read | Consequence |

## 3. Development passages

Each passage is one authoritative paragraph from a real Document.
The operator locates the paragraph by its anchor text after ingesting the Document.
Footnote markers `[n]` belong to the extracted text and are not part of any reference statement.
The last column records the blocking stage the stored IRA acceptance run shows for that Event; it is diagnostic evidence, not the official baseline.

| Passage | Source and anchor | Reference statement | Required content | Admissible omission | Stored-run blocker |
|---|---|---|---|---|---|
| DEV-01 | `Anthropic–United_States_Department_of_Defense_dispute.pdf` page 1, `The United States Department of Defense established a policy` | R-DEV-01: `The United States Department of Defense established a policy on the use of artificial intelligence in 2012.` | participants, relation, the policy object, the year | the appositive `Directive 3000.09` names the same policy | selection boundary gap, then an unsupported trigger adjunct |
| DEV-01 | same paragraph, `began developing lethal autonomous weapons` | R-DEV-02: `The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.` | participants, relation, the weapons object, the temporal bound | none identified | selection boundary gap |
| DEV-02 | same Document page 1, `Prior to the dispute, the Trump administration had integrated` | R-DEV-03: `The Trump administration had integrated Anthropic's services.` | participants, relation, the services object | `Prior to the dispute` places the event before the dispute and states a separate chronology | unsupported trigger adjunct |
| DEV-03 | same Document page 1, `That month,  Amodei criticized Trump's approach` | R-DEV-04: `Dario Amodei criticized Trump's approach to export restrictions on semiconductors.` | actor, relation, the complete object phrase | the opening `That month` states a separate time frame | selection boundary gap |
| DEV-04 | same Document page 2, `secretary of defense Pete Hegseth announced GenAI.mil` | R-DEV-05: `Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense.` | actor, relation, the platform name and its description | `in December 2025` states the date and is recorded as context | no object role and no review candidate at the subject |
| DEV-05 | `Artificial_intelligence_safety_institute.pdf` page 2, `The Albanese government announced the creation of the Australian AI Safety Institute` | R-DEV-06: `The Albanese government announced the creation of the Australian AI Safety Institute on 25 November 2025.` | actor, relation, the created object, the date | none identified | not ingested at proposal time |
| DEV-06 | same Document page 2, `On 31 January 2025, the government of France created` | R-DEV-07: `The government of France created INESIA on 31 January 2025.` | actor, relation, the created institute, the date | the French legal name and the English gloss name the same institute | not ingested at proposal time |

### Partition shape

| Requirement | Development evidence |
| --- | --- |
| At least two straightforward statements | R-DEV-03, R-DEV-04, R-DEV-07 |
| At least two statements with meaning-bearing qualifiers or complements | R-DEV-01, R-DEV-02, R-DEV-05, R-DEV-06 |
| At least two Documents | `Anthropic–United_States_Department_of_Defense_dispute.pdf`, `Artificial_intelligence_safety_institute.pdf` |
| Passages | 6 |
| Reference statements (`N`) | 7 |

No passage was chosen because the current selector or composer realizes it; three of the seven statements are blocked before composition in the stored run.

## 4. Reserved partition custody

The reviewer seals six reserved passages without showing their text or statements to the implementing agent.

Rules the sealed manifest must satisfy:

- Six passages from `raw/241030_Allen_Safety_Network.pdf`, none from the paragraph recorded in section 2.
- At least two straightforward statements and at least two statements with meaning-bearing qualifiers or complements.
- Every reference statement names its required content, admissible omissions, and why it is in scope.
- The sealed manifest carries the source digest, paragraph digest, exact text, context, reference statements, and partition membership.

The reviewer runs the custody command and reports only the sealed manifest digest and its counts:

```bash
uv run python scripts/ipi_reserved_custody.py seal \
  --source "raw/241030_Allen_Safety_Network.pdf" \
  --custody-root "$HOME/kotekomi-ipi-custody" \
  --reviewer "<name>"
uv run python scripts/ipi_reserved_custody.py check \
  --custody-root "$HOME/kotekomi-ipi-custody" \
  --inspected docs/2026-11-06-ipi-inspected-material.json
```

`seal` writes a review template, validates every rule above, and stores the sealed manifest under the custody root outside this repository.
`check` revalidates the sealed manifest and rejects any passage digest that appears in the inspected-material record.
The command prints only counts, digests, and validation errors; it never prints reserved text.

The operator records the sealed manifest digest in this section and in the package tracker.
The agent never reads the custody root.

## 5. Completeness rubric

A reviewer scores one reference statement per row and reads the complete passage with its context before scoring.

| Criterion | Passes when |
| --- | --- |
| Participants | Every subject and object participant of the reference statement appears with the identity the reviewer identified |
| Relation | The predicate states the reference statement's relation, not a weaker or stronger one |
| Essential complements | Every complement the reviewer marked required appears in the proposed content |
| Polarity and modality | The proposed content matches the Source's negation, hedging, reporting, and quotation meaning |
| Attribution | The proposed content credits the speaker or document the Source credits |
| Required time or place | Every time or place meaning the reviewer marked required appears in the proposed content |
| Identity decisions | The accepted identity is the reviewer's choice, and no identity was accepted outside review |
| Evidence replay | The proposal's evidence resolves to the exact source characters for every participant and required complement |
| Proposal state | A pending ProposedChange exists for this Event, and no Assertion became accepted Ledger state |
| Replay visibility | Saved replay shows the proposal, its spans, and its review handle |

A statement counts as usable only when every criterion passes and the review cost was measured.
A proposal that fails one criterion is recorded as incorrect with the failing criterion, and it does not count toward `C`.

## 6. Attempt budget and timing

- The operator allows at most five active minutes per reference statement in each condition.
- Active time starts when the operator begins reading the packet and ends when the operator has verified replay or recorded the stop reason.
- The operator records an incomplete attempt at the five-minute limit instead of abandoning it silently.
- Waiting time covers every command that does not return within five seconds, measured until the prompt returns.
- Unknown timing invalidates the affected row and the route decision; it never counts as zero.

## 7. Measures and acceptance routes

Let `N` be the number of fixed reference statements in a partition and `C` the number with a usable result.
Let `A` be the total active review seconds, including failed attempts and recovery.

| Measure | Definition |
| --- | --- |
| Usable coverage | `C / N` |
| Review cost | `A / C`, undefined when `C = 0` |
| Active effort | `A`, with per-statement times and correction counts |
| Time to usable result | active seconds plus waiting seconds, with timed-out attempts listed |
| Stage losses | reference statements lost at paragraph discovery, mentions, grounding, Event discovery, selection, composition, review, proposal persistence, or replay |

The package success routes are fixed as follows.

- Capability route: final `C` exceeds baseline `C` by at least two, and review cost does not increase.
- Effort route: usable coverage does not fall, final `C` is at least three, and review cost falls by at least 25 percent.
- If baseline `C = 0`, only the capability route applies and final `C` must be at least two.
- Both routes require zero loss of a previously usable reference statement in the paired comparison.
- Both routes require evidence replay, explicit review, and correct proposed-versus-accepted state for every counted result.

A waiting-time increase above 20 percent requires explicit operator acceptance before completion.

## 8. Operator protocol

The operator runs each condition in a separate disposable state root and uses only supported commands.

Per passage:

```bash
uv run kotekomi-live-replay --config <condition-config> --source "<document.pdf>" \
  --url "<source-url>" --state-root "<condition-root>/<passage>" --plain --paragraph <n>
uv run kotekomi --config <condition-config> ingestions list
uv run kotekomi --config <condition-config> ingestions show <igr_...>
uv run kotekomi --config <condition-config> review event-packet --run <igr_...> --event <sge_...>
uv run kotekomi --config <condition-config> review decide --run <igr_...> --event <sge_...> \
  --candidate-text "<candidate>" --identity-kind <actor|organization> \
  --identity <new:Name|existing:id> --predicate "<predicate>" \
  --assertion-type <reported_observation|reported_claim> \
  --source-authority <primary|secondary|tertiary|unknown> \
  --attribution-basis <direct_document|second_hand_report|anonymous_report|unknown> \
  --reviewer "<name>"
uv run kotekomi --config <condition-config> review recompose --run <igr_...> --event <sge_...>
uv run kotekomi review list --record-type Assertion
uv run kotekomi-live-replay --state-root "<condition-root>/<passage>"
```

Rules the operator follows:

- Start from an empty state root for every passage and condition, including the same declared pre-existing identities.
- Create required identities through the review command in both conditions; never copy an accepted record between roots.
- Record the outcome, the first blocking stage, the hold reason, active seconds, waiting seconds, and corrections for every statement.
- Stop at the attempt budget and record `timeout`.
- Do not edit derived JSON, seed proposals, or accept an Assertion to make a row pass.
- Alternate baseline-first and final-first order across reserved passages and disclose any unblinded comparison.

## 9. Result format

Each condition produces one JSON file with this shape.

```json
{
  "partition": "development",
  "condition": "baseline",
  "revision": "7dc9a44",
  "operator": "<name>",
  "root": "<absolute path>",
  "statements": [
    {
      "reference_id": "R-DEV-01",
      "outcome": "usable|incorrect|hold|timeout|not_attempted",
      "first_blocking_stage": "paragraph_discovery|mentions|grounding|event_discovery|selection|composition|review|proposal|replay|none",
      "hold_reason": "<typed hold or null>",
      "failing_criterion": "<rubric criterion or null>",
      "active_seconds": 0,
      "waiting_seconds": 0,
      "corrections": 0,
      "event_id": "<sge_... or null>",
      "assertion_id": "<ast_... or null>",
      "proposal_id": "<pcg_... or null>",
      "notes": "<short operator note>"
    }
  ]
}
```

`scripts/ipi_measure.py check --result <file>` validates one file.
`scripts/ipi_measure.py compare --baseline <file> --final <file>` prints `N`, `C`, `A`, review cost, waiting time, and the route decision.

## 10. Approval record

| Item | Decision | Reviewer | Date | Note |
| --- | --- | --- | --- | --- |
| D1 development passages and statements | pending | | | |
| D2 rubric and attempt budget | pending | | | |
| D3 targets and routes | pending | | | |
| D4 reserved custody | pending | | | |
| Sealed reserved manifest digest | pending | | | |

- The operator records corrections as the number of supported commands whose printed outcome had to be retried with another supported command.
