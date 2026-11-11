# IPI-01 Passage Manifest, Rubric, and Measurement Protocol

- Status: Proposed; the numerical targets are approved and the passage meanings are pending
- Package: [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md)
- Baseline revision: `7dc9a44`
- Branch: `feature/ipi-intelligence-pipeline-improvement`
- Machine-readable development manifest: `docs/2026-11-06-ipi-01-development-manifest.json` (status `proposed`)
- Reviewer role: a human who reads the complete passages and approves their reference meanings.
- Operator role: a human who runs the timed workflow and records outcomes.
- Implementing agent: this branch's agent, which never inspects reserved passages.

## 1. Decisions

| ID | Decision | Status |
| --- | --- | --- |
| D3 | Retain the package's numerical targets and routes | Approved 2026-11-06 |
| D1 | Approve the eight-statement assessment scope, with the amendments recorded in section 3: R-DEV-02 is an onset with a temporal bound, R-DEV-07 requires `agreed to create`, and every excluded claim is listed with its reason | Conditionally approved 2026-11-06; the amendments are recorded in section 3 |
| D2 | Approve the completeness rubric and the timing protocol, with active time excluding separately recorded waiting time | Approved 2026-11-06 |
| D4 | Authorize the human-run custody preparation and sealing | Authorized 2026-11-06; authorization does not assert that reserved passages are reviewed or sealed |

The targets were fixed before any result existed.
The eight statements are the whole denominator; section 3 lists the claims each passage contains that this assessment does not score.

## 2. Inspected material record

The agent has read the following material.
Reserved passages must not come from it, and the custody command enforces that by source and by paragraph digest.

| Source | SHA-256 | Pages read | Paragraphs whose full text the agent saw | Consequence |
| --- | --- | --- | --- | --- |
| `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf` | `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624` | 1-2 in full | `_0003` `86ba43dd…`, `_0008` `cd155e49…`, `_0010`, `_0011`, `_0013` `c608ac71…`, `_0015` `c5b74218…`; 160-character previews of all 36 ingested paragraphs | Excluded from the reserved partition |
| `raw/Artificial_intelligence_safety_institute.pdf` | `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253` | 1-2 in full | Organization annotation packet paragraphs `_0002` `84d76323…`, `_0008` `c29d9148…`, `_0018` `fc8ccd6b…`, `_0024` `d6eb25eb…`, `_0040` `061b9b94…` | Excluded from the reserved partition |
| `raw/241030_Allen_Safety_Network.pdf` | `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f` | none in full | Packet paragraph `_0009` `0ca5e176…` only | Reserved partition uses this Document and rejects `0ca5e176…` |

The full inspected list is recorded machine-readably in `docs/2026-11-06-ipi-inspected-material.json`.
The agent has not opened the Allen Document itself; only that one quoted paragraph is in its context.

## 3. Development passages and reference meanings

The reviewer approved the eight-statement assessment scope with the amendments recorded below.
N counts only the eight approved reference statements. Every paragraph below contains further atomic claims; each excluded claim and its exclusion reason is recorded beside its passage. The measure is a bounded sample of ordinary statements, not paragraph-level completeness, and it must not be reported as one.

The same content is recorded machine-readably in `docs/2026-11-06-ipi-01-development-manifest.json`, which the comparator requires before any comparison can run.
Passage text is the exact ingested paragraph text, including its original spacing and footnote markers; the digest covers exactly that text.
Context before and after is the neighbouring paragraph text from the same Document, or the nearest annotated paragraph when the adjacent paragraph is not recorded.

### DEV-01
- Source: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`, page 1, paragraph node `nod_f1e64380625a2f2c533fc277_0008`
- Paragraph digest: `cd155e49324b2678a0d80829f2476812f6301df6f55a963d991d6c402361c227`
- Context before: 'Since  January  2026,  the  United  States  Department  of  Defense  has  conflicted  with  the  artificial intelligence  company Anthropic  over  the  use  of  its  products  for  military  purposes  and  mass  domestic surveillance.'
- Context after: 'In Donald Trump\'s second presidency, Anthropic publicly disagreed with the administration\'s policies and initiatives. In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump\'s rescission of president Joe Biden\'s Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump\'s visit to the Middle East  in  May.  According  to Semafor ,  Trump  officials  chastised  Anthropic\'s  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden\'s advisor for artificial intelligence. [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". [7]'

Complete paragraph text:

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan  administration. [1] The  Department  of  Defense  established  a  policy  on  the  use  of  artificial intelligence  in  2012,  Directive  3000.09. [2] Efforts  to  utilize  artificial  intelligence  intensified  under  the term  of  Secretary Ash  Carter. [3] The  Department  of  Defense's  use  of  artificial  intelligence  for  Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations. [4]
```

| Reference | Kind | Statement | Required content | Admissible omissions | In-scope reason |
| --- | --- | --- | --- | --- | --- |
| R-DEV-01 | qualified | The Department of Defense established a policy on the use of artificial intelligence in 2012. | The Department of Defense; established; a policy on the use of artificial intelligence; the year 2012 | `, Directive 3000.09` is an order number that names the same policy. | An ordinary institutional action with one required year inside a paragraph that also contains three further statements. |
| R-DEV-02 | qualified | The Department of Defense began developing lethal autonomous weapons as early as the Reagan administration. | The Department of Defense; the onset relation `began developing`; lethal autonomous weapons; the onset bound `as early as the Reagan administration` | The footnote marker `[1]` is not part of the meaning. | An onset statement whose temporal bound is required; it is not a duration statement. |

Claims in this paragraph that are outside the assessment denominator:

| Excluded claim | Why it is outside N |
| --- | --- |
| Efforts to utilize artificial intelligence intensified under the term of Secretary Ash Carter. | a separate atomic claim about a different period and actor |
| The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations. | a separate atomic claim with a participial result clause |

### DEV-02
- Source: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`, page 1, paragraph node `nod_f1e64380625a2f2c533fc277_0010`
- Paragraph digest: `f9e7331550f2264199d6fa7570d4444647a81630d80629db9b78d1561b0e295c`
- Context before: "The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan  administration. [1] The  Department  of  Defense  established  a  policy  on  the  use  of  artificial intelligence  in  2012,  Directive  3000.09. [2] Efforts  to  utilize  artificial  intelligence  intensified  under  the term  of  Secretary Ash  Carter. [3] The  Department  of  Defense's  use  of  artificial  intelligence  for  Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations. [4]"
- Context after: "Prior to the dispute, the Trump administration had integrated Anthropic's services. By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. [8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. [9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. [14]"

Complete paragraph text:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives. In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East  in  May.  According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". [7]
```

| Reference | Kind | Statement | Required content | Admissible omissions | In-scope reason |
| --- | --- | --- | --- | --- | --- |
| R-DEV-03 | qualified | Anthropic publicly disagreed with the administration's policies and initiatives. | Anthropic; publicly disagreed; the coordinated object `the administration's policies and initiatives`; the identity of the administration | None. The opening frame `In Donald Trump's second presidency` fixes which administration the sentence means, so it is required context. | A stance statement whose object is a coordination and whose administration identity depends on the opening frame. |

Claims in this paragraph that are outside the assessment denominator:

| Excluded claim | Why it is outside N |
| --- | --- |
| In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence. | a separate atomic claim with its own quoted object |
| Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states. | two further atomic claims about lobbying and about a separate agreement |
| According to Semafor, Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration. | a separate attributed claim with a list of officials |
| The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill as "far too blunt an instrument". | a separate claim whose object carries a participial complement |

### DEV-03
- Source: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`, page 1, paragraph node `nod_f1e64380625a2f2c533fc277_0011`
- Paragraph digest: `d950958d35ca62e8710eeb4147ead86f010d1be215d82b0c25eb4f5c3c8793f0`
- Context before: 'In Donald Trump\'s second presidency, Anthropic publicly disagreed with the administration\'s policies and initiatives. In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump\'s rescission of president Joe Biden\'s Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump\'s visit to the Middle East  in  May.  According  to Semafor ,  Trump  officials  chastised  Anthropic\'s  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden\'s advisor for artificial intelligence. [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". [7]'
- Context after: 'Anthropic\'s strategy has mirrored Amodei\'s views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord". As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  David  Sacks,  Trump\'s  advisor  for  artificial intelligence  and  cryptocurrency,  said  on All-In (2020-present)  that Anthropic  was  among  several  "AI doomers"  that  support  regulation  he  saw  as  overly  restrictive.  According  to The  Wall  Street  Journal , officials close to Sacks examined whether Anthropic\'s Claude was a "woke AI"; in July, Trump signed an executive order "Preventing Woke AI in the Federal Government ". [15]'

Complete paragraph text:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services. By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. [8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. [9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. [14]
```

| Reference | Kind | Statement | Required content | Admissible omissions | In-scope reason |
| --- | --- | --- | --- | --- | --- |
| R-DEV-04 | qualified | The Trump administration had integrated Anthropic's services. | The Trump administration; had integrated; Anthropic's services | `Prior to the dispute` states relative chronology; the statement's meaning does not depend on the dispute. | A past-perfect integration statement with a required object and an optional time frame. |
| R-DEV-05 | straightforward | Dario Amodei criticized Trump's approach to export restrictions on semiconductors. | Dario Amodei; criticized; the complete object phrase including the nested complement | `That month` is relative time that does not change the statement. | A straightforward transitive statement whose object carries a nested prepositional complement. |

Claims in this paragraph that are outside the assessment denominator:

| Excluded claim | Why it is outside N |
| --- | --- |
| By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. | a separate claim with a coordinated object and an appositive description |
| In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. | two further atomic claims about a separate period |
| The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025. | a separate claim with a purpose complement and a time bound |
| Through its interoperability with Palantir, Anthropic's technology achieved relatively widespread usage in the U.S. military. | a separate claim whose subject is a possessive noun phrase |
| The following month, Anthropic announced that it would allow national security customers to use Claude Gov. | a separate reported-speech claim |
| Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. | a separate claim with a coordinated list and a result complement |

### DEV-04
- Source: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`, page 2, paragraph node `nod_f1e64380625a2f2c533fc277_0015`
- Paragraph digest: `c5b74218e413464bcf1cb1f82e9293b44bebc035b5c224c7b1a09d081654afb9`
- Context before: 'Sacks viewed Amodei\'s decision to attend the World Economic Forum over Trump\'s second inauguration; his  hiring  of  Biden  officials;  and  Anthropic\'s  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump\'s agenda. [15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic\'s  policies,  intensifying  the  dispute.  Amodei\'s  statement  included  views explicitly espoused by vice president JD Vance. [17]  In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic\'s relationship with the Trump administration. [18]'
- Context after: "In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic. [22] According  to  Reuters,  Anthropic  representatives  opposed  the  use  of  the  company's  products  for surveillance  or  to  develop  lethal  autonomous  weapons. [23] The  dispute  between  Anthropic  and  the Department of Defense resulted in the termination of a contract worth an estimated US$200 million. [24]"

Complete paragraph text:

```text
In  December  2025,  secretary  of  defense  Pete  Hegseth  announced  GenAI.mil,  an  artificial  intelligence platform  for  the  Department  of  Defense.  The  department  initially  contracted  Google  Gemini  for  the platform, then OpenAI's ChatGPT. [19][20] The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI". [21]
```

| Reference | Kind | Statement | Required content | Admissible omissions | In-scope reason |
| --- | --- | --- | --- | --- | --- |
| R-DEV-06 | qualified | Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense, in December 2025. | Pete Hegseth; announced; GenAI.mil; the platform description; the month | The footnote markers `[19][20]` are not part of the meaning. | An announcement whose object carries an appositive description and whose statement carries a required date; it is qualified, not straightforward. |

Claims in this paragraph that are outside the assessment denominator:

| Excluded claim | Why it is outside N |
| --- | --- |
| The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT. | two further atomic claims with an anaphoric subject |
| The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI". | a separate reported-speech claim with a participial clause |

### DEV-05
- Source: `raw/Artificial_intelligence_safety_institute.pdf`, page 1, paragraph node `nod_561e34f74a03ac8f05edb4a3_0008`
- Paragraph digest: `c29d914849803e39af70dbf0cbfb77be6ccb2938abb0e454162d737193fa2a87`
- Context before: 'An artificial intelligence safety institute [1] is a type of state-backed organization aiming to evaluate and ensure the safety of advanced artificial intelligence (AI) models, also called frontier AI models. [2]'
- Context after: "On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security. [17][18]"

Complete paragraph text:

```text
At the AI Seoul Summit in May 2024, the European Union and other countries agreed to create their own AI safety institutes, forming an international network. [1]
```

| Reference | Kind | Statement | Required content | Admissible omissions | In-scope reason |
| --- | --- | --- | --- | --- | --- |
| R-DEV-07 | qualified | The European Union and other countries agreed to create their own AI safety institutes in May 2024. | The European Union; other countries; the relation `agreed to create`; their own AI safety institutes; May 2024 | `At the AI Seoul Summit` names the venue and `forming an international network` states the consequence; each is a separate meaning. | A collective action whose relation includes the complement `to create`; the bare verb `agreed` would not preserve the statement. |

Claims in this paragraph that are outside the assessment denominator:

| Excluded claim | Why it is outside N |
| --- | --- |
| forming an international network | a separate consequence claim inside the same sentence; declared as an omission for R-DEV-07 and excluded from this denominator |

### DEV-06
- Source: `raw/Artificial_intelligence_safety_institute.pdf`, page 2, paragraph node `nod_561e34f74a03ac8f05edb4a3_0018`
- Paragraph digest: `fc8ccd6b5ed67bcd24abf42693d73b302d92ef0534d23acb85b6d281827a2afa`
- Context before: 'At the AI Seoul Summit in May 2024, the European Union and other countries agreed to create their own AI safety institutes, forming an international network. [1]'
- Context after: 'The  Japan  AISI  (or  J-AISI) [26] was  founded  in  February 2024. Part of the Information Technology Promotion Agency, it  employs  about  23  people. [15]'

Complete paragraph text:

```text
On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security. [17][18]
```

| Reference | Kind | Statement | Required content | Admissible omissions | In-scope reason |
| --- | --- | --- | --- | --- | --- |
| R-DEV-08 | straightforward | The government of France created INESIA on 31 January 2025. | The government of France; created; the named institute; the date | The French legal name and the English gloss name the same institute; `INESIA` is the short name the Source gives. | A straightforward creation statement with a required date and a named object. |

Claims in this paragraph that are outside the assessment denominator:

| Excluded claim | Why it is outside N |
| --- | --- |
| the French legal name, the English gloss, and the short name INESIA | an identity decision about three names for one institute; it is recorded inside R-DEV-08 rather than assessed as a separate claim |

### Partition shape

| Requirement | Development evidence |
| --- | --- |
| At least two straightforward statements | R-DEV-05, R-DEV-08 |
| At least two statements with meaning-bearing qualifiers or complements | R-DEV-01, R-DEV-02, R-DEV-03, R-DEV-04, R-DEV-06, R-DEV-07 |
| At least two Documents | Anthropic-DoD dispute PDF, AI Safety Institute PDF |
| Passages | 6 |
| Reference statements (`N`) | 8 |

The eight statements are the whole denominator of this assessment.
Each paragraph contains the further claims listed above, and none of them is scored.
A result of `C / 8` therefore says nothing about how completely the Pipeline represents these six paragraphs; it says how many of eight selected ordinary statements it delivered.
The agent did not choose a passage because the current selector or composer realizes it.
Stored-run note: five of the eight statements are blocked before review; the three statements from the second Document are unverified because that Document is not yet ingested.

## 4. Reserved partition custody

The reviewer seals six reserved passages without showing their text or statements to the implementing agent.

Rules the sealed manifest must satisfy:

- Six passages from `raw/241030_Allen_Safety_Network.pdf`, none equal to the paragraph recorded in section 2.
- At least two straightforward statements and at least two statements with meaning-bearing qualifiers or complements.
- Every statement carries non-empty statement text, required content, admissible omissions, and an in-scope reason.
- Every passage carries its exact text, its source digest, its page, non-empty `context_before` and `context_after` (the literal `none` when there is no surrounding text), and its text digest.
- The sealed manifest carries `attempt_budget_seconds`, so the reserved comparison enforces the same five-minute budget as development.
- The passage text must appear in the declared Source; the command extracts the Source and proves membership rather than trusting entered text.

The reviewer runs the custody command.
The first invocation writes a template under the custody root and seals nothing; the second invocation validates the completed template, proves source membership, and writes the sealed manifest.

```bash
uv run python scripts/ipi_reserved_custody.py seal --source raw/241030_Allen_Safety_Network.pdf --custody-root "$HOME/kotekomi-ipi-custody" --reviewer "<name>"
# Fill $HOME/kotekomi-ipi-custody/reserved-manifest.template.json, place the passages, then rerun the same command.
uv run python scripts/ipi_reserved_custody.py check --custody-root "$HOME/kotekomi-ipi-custody" --inspected docs/2026-11-06-ipi-inspected-material.json
```

The command prints only counts, digests, and validation errors; it never prints reserved text.
The operator records the sealed manifest digest here and in the package tracker. The agent never reads the custody root.

The custody tool needs `pdftotext` on the path to prove source membership.

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

## 6. Timing protocol

Active time covers the whole operator attempt for one reference statement:

1. Locating the Event and its review packet in the run, including listing runs and reading the ingestion summary.
2. Reading the packet and the complete passage context.
3. Recording the decision, including any second attempt after a rejected or wrong decision.
4. Recomposition, review-queue inspection, and saved replay verification.
5. Recovery from a wrong command, a wrong identity, or a rejected decision.

Active time starts when the operator begins locating the Event and ends when replay verification finishes or the budget is reached.

Waiting time covers every command that does not return within five seconds.
Short waits are recorded too; they are summed into waiting time and never dropped.
Active time and waiting time are disjoint: a recorded wait is waiting time and never also counts as active time, so the two totals cannot double-count a command delay.
Ingestion that serves a whole Document is recorded once per condition as setup waiting time and is not charged to any statement row; the report adds it to the row waits when it reports total waiting time.

Limits and recording rules:

- The operator allows at most five active minutes per reference statement in each condition.
- The operator records an incomplete attempt at that limit as `timeout` instead of abandoning it silently.
- A row whose active seconds exceed the limit is rejected by the comparator.
- Unknown timing invalidates the row and the comparison.
- A correction is a substantive decision change: a different identity, predicate, assertion type, authority, attribution basis, or candidate after the operator saw the first outcome. Retrying a command after a transport or argument error is recorded separately as a command retry, not as a substantive correction.
- The row records both counts: `corrections` for substantive changes and `command_retries` for repeated invocations.

## 7. Measures and acceptance routes

Let `N` be the number of approved reference statements in a partition and `C` the number with a usable result.
Let `A` be the total active review seconds, including failed attempts and recovery.

| Measure | Definition |
| --- | --- |
| Usable coverage | `C / N` |
| Review cost | `A / C`, undefined when `C = 0` |
| Active effort | `A`, with per-statement times and correction counts |
| Time to usable result | active seconds plus waiting seconds, with timed-out attempts listed |
| Stage losses | reference statements lost at paragraph discovery, mentions, grounding, Event discovery, selection, composition, review, proposal persistence, or replay |

The routes are those the package states, and they are approved.

- Capability route: final `C` exceeds baseline `C` by at least two, and review cost does not increase.
- Effort route: usable coverage does not fall, final `C` is at least three, and review cost falls by at least 25 percent.
- If baseline `C = 0`, only the capability route applies, final `C` must be at least two, and the final total active effort must not exceed the baseline attempt budget (`N x 300` seconds).
- Both routes require zero loss of a previously usable reference statement.
- Both routes require evidence replay, explicit review, and correct proposed-versus-accepted state for every counted result.
- A not-attempted statement is incomplete measurement; the comparison cannot pass.
- A waiting-time increase above 20 percent requires explicit operator acceptance before completion.

## 8. Operator protocol

The operator runs one disposable state root per Document per condition and uses only supported commands with that root's configuration.
`--paragraph` selects the paragraph the replay presents; it never restricts ingestion, so each root is ingested once.
The exact commands, roots, ordinals, and shared-cost handling are in [the operator comparison procedure](2026-11-06-ipi-operator-comparison-procedure.md).

```bash
CONFIG="<root>/state/kotekomi.toml"
uv run kotekomi-live-replay --config "$CONFIG" --source "<document.pdf>" --url "<source-url>" --state-root "<root>/state"
uv run kotekomi --config "$CONFIG" ingestions list
uv run kotekomi --config "$CONFIG" ingestions show <igr_...>
uv run kotekomi --config "$CONFIG" review event-packet --run <igr_...> --event <sge_...>
uv run kotekomi --config "$CONFIG" review decide --run <igr_...> --event <sge_...> \
  --candidate-text "<candidate>" --identity-kind <actor|organization> \
  --identity <new:Name|existing:id> --predicate "<predicate>" \
  --assertion-type <reported_observation|reported_claim> \
  --source-authority <primary|secondary|tertiary|unknown> \
  --attribution-basis <direct_document|second_hand_report|anonymous_report|unknown> \
  --reviewer "<name>"
uv run kotekomi --config "$CONFIG" review recompose --run <igr_...> --event <sge_...>
uv run kotekomi --config "$CONFIG" review list --record-type Assertion
uv run kotekomi-live-replay --state-root "<root>/state" --ingestion-run <igr_...> --paragraph <ordinal> --plain
```

Every review command, including `review list`, uses the root's `--config` so it reads that root's Ledger and shows only that root's proposals.

Rules the operator follows:

- Start every Document root empty in both conditions, including the same declared pre-existing identities.
- Create required identities through the review command in both conditions; never copy an accepted record between roots.
- Use the same statement order within a root in both conditions, and record the order.
- Record the outcome, the first blocking stage, the hold reason, active seconds, waiting seconds, corrections, and command retries for every statement.
- Record each Document ingestion's waiting once in the condition's `setup_waiting_seconds`; charge no ingestion time to a statement row.
- Stop at the attempt budget and record `timeout`.
- Do not edit derived JSON, seed proposals, or accept an Assertion to make a row pass.
- Alternate baseline-first and final-first order across reserved passages and disclose any unblinded comparison.

## 9. Result format and comparison

Each condition produces one JSON file with this shape.

```json
{
  "partition": "development",
  "condition": "baseline",
  "revision": "7dc9a44",
  "operator": "<name>",
  "root": "<absolute path>",
  "setup_waiting_seconds": 0,
  "waiting_time_accepted": false,
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
      "command_retries": 0,
      "event_id": "<sge_... or null>",
      "assertion_id": "<ast_... or null>",
      "proposal_id": "<pcg_... or null>",
      "notes": "<short operator note>"
    }
  ]
}
```

`setup_waiting_seconds` is the sum of the Document ingestion waits for this condition; it is added to the row waits when the report states total waiting time, so shared cost is counted once and never charged per statement.
`scripts/ipi_measure.py check --result <file>` validates one condition file.
`scripts/ipi_measure.py compare --baseline <file> --final <file> --manifest docs/2026-11-06-ipi-01-development-manifest.json` prints the measures and the route decision.

The comparator refuses to run unless the manifest is approved, both conditions carry exactly the manifest's reference identifiers, no attempt exceeds the budget, and no statement is not attempted.

## 10. Approval record

| Item | Decision | Reviewer | Date | Note |
| --- | --- | --- | --- | --- |
| D3 targets and routes | approved | human reviewer | 2026-11-06 | Targets retained; measurement wording corrected |
| D1 eight-statement scope | conditionally approved | human reviewer | 2026-11-06 | Approved with three amendments: R-DEV-02 onset rationale, R-DEV-07 `agreed to create`, excluded claims listed per passage |
| D2 rubric and timing protocol | approved | human reviewer | 2026-11-06 | Active time excludes separately recorded waiting time; long and short waits count as waiting |
| D4 reserved custody | authorized | human reviewer | 2026-11-06 | Authorizes preparation and sealing; it does not assert that reserved passages are reviewed or sealed |
| Sealed reserved manifest digest | sealed | Dmitri | 2026-11-06 | `a9198da4a9543623997ab00dc85109b95a733df7e3c657709af6d0ac886953e1`; 6 passages, 8 statements (2 straightforward, 6 qualified), 1 source; `check` reports `valid` against the inspected-material record |

## 11. Execution handoff

The exact human-run baseline and final procedure is [the operator comparison procedure](2026-11-06-ipi-operator-comparison-procedure.md).
It fixes the baseline revision `7dc9a44`, the final revision `2ec4737`, the per-passage roots, the ordinal lookup, the timing worksheet, the comparison commands, and the invalidation rules.
The out-of-order implementation and the reference reconciliation are recorded in [the implementation order](2026-11-06-ipi-implementation-order.md).
No timed run has started and the reserved partition is not sealed.
