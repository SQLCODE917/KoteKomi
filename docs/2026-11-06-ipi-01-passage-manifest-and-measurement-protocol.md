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

### DEV-01: the dispute opening

- Source: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`, page 1.
- Anchor: `Since  January  2026`
- Reference statement R-DEV-01: `The United States Department of Defense has conflicted with Anthropic since January 2026.`
- Required content: both participants, the relation `conflicted`, and the temporal bound `since January 2026`.
- Admissible omission: the closing phrase `over the use of its products for military purposes and mass domestic surveillance` states a second, separate meaning; it is out of scope for R-DEV-01.
- Why in scope: an ordinary lead sentence in the target domain with one required temporal qualifier.

### DEV-02: GenAI.mil announcement

- Source: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`, page 2.
- Anchor: `In  December  2025,  secretary  of  defense  Pete  Hegseth  announced`
- Reference statements:
  - R-DEV-02: `Pete Hegseth announced GenAI.mil in December 2025.`
  - R-DEV-03: `The Department of Defense contracted Google Gemini for GenAI.mil.`
  - R-DEV-04: `The Department of Defense contracted OpenAI's ChatGPT for GenAI.mil.`
- Required content: participants, relation, the product, and the temporal qualifier for R-DEV-02.
- Admissible omissions: the appositive `an artificial intelligence platform for the Department of Defense` describes GenAI.mil; `initially` and `then` order the two contracts without changing either statement; `decrying "woke AI"` states a separate meaning about a later contract.
- Anaphora: `The department` denotes `the Department of Defense`; the reference statements use the full name.
- Why in scope: two straightforward statements and one time-qualified statement from one announcement paragraph.

### DEV-03: Australian institute announcement

- Source: `raw/Artificial_intelligence_safety_institute.pdf`, page 2.
- Anchor: `The Albanese government announced the creation of the Australian AI Safety Institute`
- Reference statement R-DEV-05: `The Albanese government announced the creation of the Australian AI Safety Institute on 25 November 2025.`
- Required content: actor, relation, the created object as a whole phrase, and the date.
- Admissible omission: none identified.
- Why in scope: a straightforward statement whose object carries a required complement and whose statement carries a required date.

### DEV-04: French institute creation

- Source: `raw/Artificial_intelligence_safety_institute.pdf`, page 2.
- Anchor: `On 31 January 2025, the government of France created`
- Reference statement R-DEV-06: `The government of France created INESIA on 31 January 2025.`
- Required content: actor, relation, the created institute, and the date.
- Admissible omission: the French legal name and the English gloss name the same institute; `INESIA` is the short name the Source gives.
- Why in scope: an ordinary creation statement with a required date and a named object.

### DEV-05: United Kingdom institute establishment

- Source: `raw/Artificial_intelligence_safety_institute.pdf`, page 1.
- Anchor: `During the summit in November 2023, the UK AISI was officially established`
- Reference statement R-DEV-07: `The UK AI Safety Institute was established in November 2023.`
- Required content: the institute, the passive relation `was established`, and the month.
- Admissible omission: `as an evolution of the Frontier AI Taskforce` names a predecessor and states a separate lineage meaning.
- Why in scope: a passive construction with a required time qualifier, common in institutional reporting.

### DEV-06: Canadian institute announcement

- Source: `raw/Artificial_intelligence_safety_institute.pdf`, page 2.
- Anchor: `Canada announced in April 2024 that it would create an AI safety institute`
- Reference statement R-DEV-08: `Canada announced in April 2024 that it would create an AI safety institute.`
- Required content: actor `Canada`, the reporting relation `announced`, the announced content as the object, the month, and the reported modality `would`.
- Admissible omission: the following clause about the founding date states a separate later fact.
- Why in scope: a reported-speech construction with an embedded clause and a required date.

### Partition shape

| Requirement | Development evidence |
| --- | --- |
| At least two straightforward statements | R-DEV-03, R-DEV-04, R-DEV-06 |
| At least two statements with meaning-bearing qualifiers or complements | R-DEV-01, R-DEV-02, R-DEV-05, R-DEV-07, R-DEV-08 |
| At least two Documents | `Anthropic–United_States_Department_of_Defense_dispute.pdf`, `Artificial_intelligence_safety_institute.pdf` |
| Passages | 6 |
| Reference statements (`N`) | 8 |

No passage was chosen because the current selector or composer realizes it.

| --- | --- | --- |
| `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf` | `pdftotext` pages 1-2 in full; 160-character previews of all 36 ingested paragraphs; full text of ingested paragraphs 1, 2, 3, 8, and 13 | This Document is excluded from the reserved partition |
| `raw/Artificial_intelligence_safety_institute.pdf` | `pdftotext` pages 1-2 in full; organization annotation packet paragraphs `_0002`, `_0008` | This Document is excluded from the reserved partition |
| `raw/241030_Allen_Safety_Network.pdf` | One paragraph quoted in [the organization held-out annotation packet](2026-08-28-organization-mention-held-out-annotation-packet.md): node `nod_e2ef007787e60f415d0334cd_0009`, paragraph text digest `0ca5e176…656f2` | Pages 1, 3-17 remain unread; the reserved partition uses this Document |

The reserved partition therefore uses `raw/241030_Allen_Safety_Network.pdf` only, and the custody check rejects any passage whose paragraph digest equals the one quoted above or whose source is one of the two excluded Documents.


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
