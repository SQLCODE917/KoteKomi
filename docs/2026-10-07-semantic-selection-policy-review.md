# R17: Human-Adopted Semantic Selection Policies and Answer Fixtures

- Status: operator-adopted, reviewed, and frozen as contract version 1.
- Draft author: Codex, at the operator's explicit request; preserved in the records.
- Human policy author and reviewer: repository operator, recorded as operator self-review.
- Contract: [Semantic Selection Contract](2026-10-07-semantic-selection-contract.md).
- Scope: 11 adopted policies, 26 adopted answer fixtures, zero new model executions.

The operator explicitly accepted the policy records and answer fixtures as written on 2026-10-14.
The [approval attestation](../data/r17-semantic-selection-contract/human_approval.json) preserves the exact approval statement and binds each approved policy, input, task route, and answer fixture by digest.
Every policy-body digest, raw answer, parsed answer, and expected signal remains unchanged from the reviewed set.
The operator performs both human roles; these records do not claim independent review by a second person.
The review commit `6870e53` records this reviewed reference set; acceptance_evidence is true and contract version 1 is frozen.
The R17 acceptance DTO and evaluator are implemented.

Original draft explanations and review questions below remain verbatim for provenance.
The operator's acceptance adopts those decisions as written and resolves their review status.
The R4 implementation limitations remain recorded follow-up work.

The two historical cases were already exposed by R16 and are diagnostic cases.
Their original catalog phase was held_out; they do not provide untouched validation evidence.
The nine supplemental cases use constructed source text and manually authored dependency fixtures.
They do not claim Stanza execution, historical R15 routing, or canonical Actor identity.
No existing Gold selections were used to author these proposals.

## Adopted decisions and implementation follow-up

1. **AHE-022 object scope:** the operator adopts the minimal nominal policy selecting C1 Sacks and C3 Amodei's decision.
   This fixes the reference for R17; it does not establish that the complete sentence meaning has been composed.
2. **R4 polarity divergence:** R4-POL-01 and R4-MOD-01 specify selected-fragment derivation.
   Current code inspects all direct trigger dependents, independently of the selected set.
   Its negation check requires the dependency label neg; the archived AHE-051 not token is labeled advmod.
   The policy gap and the implementation gap are separate; neither is fixed by this draft.
3. **Composition completeness:** the current R4 output drops Paris in AHE-902 and Tomas in AHE-904.
   The operator adopts not_ready despite the composer returning proposition, because required content is lost.
4. **Justified NONE:** the operator adopts AHE-908 as a supported weather Event with an expletive It and no eligible referential argument.
   Its reference set is present but empty; composition remains not_ready under R4, rather than not_applicable.

## Files and verification

- [Adopted policy records](../data/r17-semantic-selection-contract/reference_policy_records.json).
- [Separate observed-answer fixtures](../data/r17-semantic-selection-contract/observed_answers.json).
- [Frozen task-route manifest](../data/r17-semantic-selection-contract/task_manifest.json).
- [Mechanical verifier](../data/r17-semantic-selection-contract/verify_policy_records.py).
- [File checksums](../data/r17-semantic-selection-contract/checksums.json).
- [Exact contract text at review time](../data/r17-semantic-selection-contract/reviewed_contract_spec.md), retained as historical evidence; the current contract remains authoritative.

Run from the repository root:

```bash
.venv/bin/python data/r17-semantic-selection-contract/verify_policy_records.py
```

Expected result: mechanically_valid_human_adopted_policy_records, 11 policy records, 26 answer fixtures, human_review_status=approved, and acceptance_evidence=false.
The verifier checks the operator approval bindings, source ranges, shared DTO parsing, route binding, expected-signal consistency, and reproducible current R4 probes.
It does not decide whether the proposed eligibility policy is correct.
The policy records use a preparation envelope with human adoption metadata; the R17 acceptance DTO and evaluator are not implemented.
The data directory remains ignored by Git, like the preceding experiment runs; this review document is outside that ignored directory.

## Case overview

| Case | Adopted selected set | Reference readiness | Main coverage |
| --- | --- | --- | --- |
| AHE-022 | C1, C3 | not_ready | subject, object, nested_boundaries, diagnostic_AHE_022 |
| AHE-051 | C3 | not_ready | subject, polarity, document_artifacts, diagnostic_AHE_051 |
| AHE-901 | C1, C2 | ready | subject, object, select_all_pass, initially_ready |
| AHE-902 | C1, C2, C3 | not_ready | time, place |
| AHE-903 | C1, C2, C3, C4 | ready | polarity, modality, select_all_fail, nested_boundaries |
| AHE-904 | C1, C2, C3 | not_ready | coordination, subject |
| AHE-905 | C3, C4 | ready | attribution, subject, object |
| AHE-906 | C4, C6 | ready | nested_boundaries, subject, object |
| AHE-907 | C1, C2 | ready | separate_occurrences |
| AHE-908 | NONE | not_ready | justified_NONE, empty_reference_set |
| AHE-909 | C1, C2 | not_ready | subject, object, removed_entity_references |

## AHE-022: Minimal nominal object for viewed (operator-adopted scope)

Source: `Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.`

Marked Event: `viewed` at [6, 12).
Route: `label_only_reselection`; adopted selected set: **C1, C3**.

Propose the smallest identifying nominal arguments of viewed: Sacks and Amodei's decision. Availability of later syntax-attached spans does not alone make them eligible.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-022.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 5) | Sacks | C1 | met |
| object | [13, 30) | Amodei's decision | C3 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 5) | Sacks | selected: Canonical subject. |
| C2 | [13, 21) | Amodei's | ineligible_incomplete: Possessor without the argument head decision. |
| C3 | [13, 30) | Amodei's decision | selected: Canonical minimal nominal object; retain the possessive identity. |
| C4 | [22, 30) | decision | redundant: C3 already contains decision; selecting C4 adds no content, and C4 alone drops the identifying possessor Amodei. |
| C5 | [31, 222) | to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence | ineligible_under_proposed_minimal_argument_policy: Infinitival description lacks the object head decision and mixes the hiring, association, and evidence context; it cannot replace C3 under this proposal. |
| C6 | [31, 270) | to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda | ineligible_under_proposed_minimal_argument_policy: Infinitival description also contains the embedded support conclusion; review whether that content is required beyond the minimal object. |
| C7 | [34, 40) | attend | ineligible_under_proposed_minimal_argument_policy: Attend is a nested predicate describing the decision, not the marked viewed predicate or its nominal argument. |
| C8 | [41, 65) | the World Economic Forum | ineligible_under_proposed_minimal_argument_policy: The World Economic Forum is the object of nested attend; the source does not state it as the place of viewed. |
| C9 | [45, 50) | World | ineligible_under_proposed_minimal_argument_policy: World is an incomplete part of the nested World Economic Forum name. |
| C10 | [51, 59) | Economic | ineligible_under_proposed_minimal_argument_policy: Economic is an incomplete part of the nested World Economic Forum name. |
| C11 | [60, 65) | Forum | ineligible_under_proposed_minimal_argument_policy: Forum is an incomplete part of the nested World Economic Forum name. |
| C12 | [66, 222) | over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence | ineligible_under_proposed_minimal_argument_policy: The comparison over Trump's inauguration belongs to the decision description and extends across later context; review broader object scope. |
| C13 | [71, 78) | Trump's | ineligible_under_proposed_minimal_argument_policy: Trump's is a possessor in the nested inauguration comparison, not the subject or proposed object of viewed. |
| C14 | [79, 85) | second | ineligible_under_proposed_minimal_argument_policy: Second modifies the nested inauguration; it does not establish a time role for viewed. |
| C15 | [86, 98) | inauguration | ineligible_under_proposed_minimal_argument_policy: Inauguration is an Event in the nested attendance comparison; it is not the proposed minimal object of viewed. |
| C16 | [98, 222) | ; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence | ineligible_under_proposed_minimal_argument_policy: This broad span contains hiring, association, and evidence context without the selected decision head; review the coordinated-object alternative. |
| C17 | [100, 103) | his | ineligible_under_proposed_minimal_argument_policy: His identifies the hiring possessor but lacks the hiring head; it is not a complete additional object. |
| C18 | [104, 110) | hiring | ineligible_under_proposed_minimal_argument_policy: Hiring is a possible additional coordinated object, excluded only under this minimal-object proposal; review explicitly. |
| C19 | [111, 129) | of Biden officials | ineligible_under_proposed_minimal_argument_policy: Of Biden officials describes hiring without its head; it is not a complete minimal argument of viewed. |
| C20 | [114, 119) | Biden | ineligible_under_proposed_minimal_argument_policy: Biden is an incomplete modifier of the nested hiring participant Biden officials. |
| C21 | [120, 129) | officials | ineligible_under_proposed_minimal_argument_policy: Officials is an incomplete boundary for Biden officials, nested under hiring. |
| C22 | [129, 222) | ; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence | ineligible_under_proposed_minimal_argument_policy: This span mixes association and evidence content; review whether a separate complete association object is required. |
| C23 | [135, 146) | Anthropic's | ineligible_under_proposed_minimal_argument_policy: Anthropic's identifies the association possessor without its head; it is not a complete additional object. |
| C24 | [147, 158) | association | ineligible_under_proposed_minimal_argument_policy: Association is a possible additional coordinated object but lacks its identifying complements; review broader object content. |
| C25 | [159, 192) | with the philanthropic initiative | ineligible_under_proposed_minimal_argument_policy: With the philanthropic initiative modifies association and lacks the association head. |
| C26 | [168, 181) | philanthropic | ineligible_under_proposed_minimal_argument_policy: Philanthropic is an adjective within the nested initiative phrase. |
| C27 | [182, 192) | initiative | ineligible_under_proposed_minimal_argument_policy: Initiative is a nested association participant; it is not the proposed minimal object of viewed. |
| C28 | [193, 197) | Open | ineligible_under_proposed_minimal_argument_policy: Open is an incomplete part of the nested Organization name Open Philanthropy. |
| C29 | [193, 210) | Open Philanthropy | ineligible_under_proposed_minimal_argument_policy: Open Philanthropy participates in the association description, not the proposed minimal arguments of viewed. |
| C30 | [198, 210) | Philanthropy | ineligible_under_proposed_minimal_argument_policy: Philanthropy is an incomplete part of the nested Organization name Open Philanthropy. |
| C31 | [211, 222) | as evidence | ineligible_under_proposed_minimal_argument_policy: As evidence supplies the source's interpretation of viewed; excluding it is a deliberate review question, not a proven irrelevance. |
| C32 | [223, 270) | that Anthropic would not support Trump's agenda | ineligible_under_proposed_minimal_argument_policy: This is the conclusion for which Sacks treated the preceding items as evidence; review whether it must be preserved in the marked proposition. |
| C33 | [248, 255) | support | ineligible_under_proposed_minimal_argument_policy: Support is the embedded conclusion predicate, distinct from marked viewed. |
| C34 | [256, 270) | Trump's agenda | ineligible_under_proposed_minimal_argument_policy: Trump's agenda is the object of embedded support, not the proposed minimal object of viewed. |
| C35 | [264, 270) | agenda | ineligible_under_proposed_minimal_argument_policy: Agenda is an incomplete boundary for the embedded support object Trump's agenda. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **not_ready**.

- The frozen R16 request supplies no Actor or Organization entity references; the subject cannot resolve.
- The minimal-object proposal is not a claim that the complete sentence meaning has been composed.

Current deterministic composer result: `held` with `subject_unavailable`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2,C3,C4,C5,C6,C7,C8,C9,C10,C11,C12,C13,C14,C15,C16,C17,C18,C19,C20,C21,C22,C23,C24,C25,C26,C27,C28,C29,C30,C31,C32,C33,C34,C35` | R16_archived | valid | unmet | met | not_applicable | not_ready |
| `C1,C3` | constructed | valid | met | met | not_applicable | not_ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Does the proposition require the decision's infinitival description, the hiring and association items, or the as-evidence complement? If yes, reject this minimal-object proposal and specify those required source ranges.
- C3 is a review proposal, not a recovered historical Gold answer. A richer object policy can expose further boundary or composition gaps.

Policy-body SHA-256: `69973d779bf87ed39234e2ee9df6645ed4c1f12aee444549cd7158db7f6bafa3`.

## AHE-051: Correct available subject with missing negation

Source: `[45] The April order is not final.`

Marked Event: `final` at [28, 33).
Route: `best_choice_reselection`; adopted selected set: **C3**.

Adopt the R17-pinned available set {C3}; keep the independently required not source range as a polarity boundary gap.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-051.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [5, 20) | The April order | C3 | met |
| polarity | [24, 27) | not | absent | gap |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | [45] | ineligible_document_artifact: Citation marker [45] is not propositional content. |
| C2 | [1, 3) | 45 | ineligible_document_artifact: 45 is the citation identifier, not an argument. |
| C3 | [5, 20) | The April order | selected: Canonical subject The April order. |
| C4 | [15, 20) | order | ineligible_incomplete: Order alone drops April and definite reference; it is redundant beside C3. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **not_ready**.

- Required not polarity content is absent from the filtered task pool.
- R16 supplies no Actor or Organization reference; the order is not automatically an Actor or Organization.
- Archived Stanza labels not as advmod; current R4 tests neg and would not infer negation from that label.

Current deterministic composer result: `held` with `subject_unavailable`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `NONE` | R16_archived | valid | unmet | gap | unjustified | not_ready |
| `C3` | constructed | valid | met | gap | not_applicable | not_ready |
| `,C3,,` | constructed_negative_strict_grammar | invalid | not_applicable | gap | not_applicable | not_ready |
| `C3,C3` | constructed_negative_strict_grammar | invalid | not_applicable | gap | not_applicable | not_ready |
| `,NONE,` | constructed_negative_strict_grammar | invalid | not_applicable | gap | not_applicable | not_ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Approve the pinned {C3} policy and the separate required not range.
- Closing polarity alone does not resolve the current R4 subject-type and entity-reference requirement.

Policy-body SHA-256: `2a6dee656b7c9bc9ee437aa88e5d8cb7465c96d1f5d945ceba7636a0a27d9b9a`.

## AHE-901: Complete pool: selecting everything is correct

Source: `Mira greeted Tomas.`

Marked Event: `greeted` at [5, 12).
Route: `label_only_reselection`; adopted selected set: **C1, C2**.

The pool contains exactly the two required argument constituents. Both labels are required.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-901.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 4) | Mira | C1 | met |
| object | [13, 18) | Tomas | C2 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | selected: Supplies its declared canonical role content. |
| C2 | [13, 18) | Tomas | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **ready**.

- Required source content, subject identity, and attribution inputs are supplied.

Current deterministic composer result: `proposition`, subject `Mira`, object `Tomas`, polarity `affirmed`, modality `actual`, attribution `source_narrator`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2` | constructed | valid | met | met | not_applicable | ready |
| `C1` | constructed | valid | unmet | met | not_applicable | ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

Policy-body SHA-256: `bffdf18cbbf2859047e3102b588b5778786eec51c497efa32de7bbe2c774103b`.

## AHE-902: Required time and place

Source: `Mira arrived on Monday in Paris.`

Marked Event: `arrived` at [5, 12).
Route: `label_only_reselection`; adopted selected set: **C1, C2, C3**.

The source explicitly constrains the arrival by day and location; both adjuncts are needed.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-902.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 4) | Mira | C1 | met |
| time | [16, 22) | Monday | C2 | met |
| place | [26, 31) | Paris | C3 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | selected: Supplies its declared canonical role content. |
| C2 | [16, 22) | Monday | selected: Supplies its declared canonical role content. |
| C3 | [26, 31) | Paris | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **not_ready**.

- Current R4 emits one object slot; the deterministic probe retains Monday and drops the separate Paris role.

Current deterministic composer result: `proposition`, subject `Mira`, object `Monday`, polarity `affirmed`, modality `actual`, attribution `source_narrator`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2,C3` | constructed | valid | met | met | not_applicable | not_ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Approve bare Monday and Paris as canonical content rather than the larger on Monday and in Paris spans.
- Approve not_ready for complete composition while the current R4 record cannot preserve both adjunct roles.

Policy-body SHA-256: `d443f695189a806dfc0181bc8b51c5050bac2f3c69013f97bc6e1c40486ef675`.

## AHE-903: Negation and hypothetical modality

Source: `Mira would not sign the agreement.`

Marked Event: `sign` at [15, 19).
Route: `label_only_reselection`; adopted selected set: **C1, C2, C3, C4**.

Retain the explicit hypothetical and negative markers separately from the subject and definite object.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-903.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 4) | Mira | C1 | met |
| modality | [5, 10) | would | C2 | met |
| polarity | [11, 14) | not | C3 | met |
| object | [20, 33) | the agreement | C4 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | selected: Supplies its declared canonical role content. |
| C2 | [5, 10) | would | selected: Supplies its declared canonical role content. |
| C3 | [11, 14) | not | selected: Supplies its declared canonical role content. |
| C4 | [20, 33) | the agreement | selected: Supplies its declared canonical role content. |
| C5 | [24, 33) | agreement | ineligible_incomplete: Agreement alone drops the definite reference and adds no required content beside C4. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **ready**.

- Required source content, subject identity, and attribution inputs are supplied.

Current deterministic composer result: `proposition`, subject `Mira`, object `the agreement`, polarity `negated`, modality `hypothetical`, attribution `source_narrator`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2,C3,C4` | constructed | valid | met | met | not_applicable | ready |
| `C1,C2,C3,C4,C5` | constructed | valid | unmet | met | not_applicable | ready |
| `,C3,,` | constructed_negative_strict_grammar | invalid | not_applicable | met | not_applicable | ready |
| `C3,C3` | constructed_negative_strict_grammar | invalid | not_applicable | met | not_applicable | ready |
| `,NONE,` | constructed_negative_strict_grammar | invalid | not_applicable | met | not_applicable | ready |
| `NONE` | constructed_negative_strict_grammar | invalid | not_applicable | met | not_applicable | ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- The dependency fixture deliberately uses neg to exercise R4-POL-01; this is not a claim about production Stanza output.

Policy-body SHA-256: `c6bf352269aece70bea525cb2c4323e6a7d90323732dda8347fc122c94cef4e0`.

## AHE-904: Coordinated subjects require both occurrences

Source: `Mira and Tomas signed the agreement.`

Marked Event: `signed` at [15, 21).
Route: `label_only_reselection`; adopted selected set: **C1, C2, C3**.

A single signing proposition has both named signers; selecting only Mira loses Tomas.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-904.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 4) | Mira | C1 | met |
| subject | [9, 14) | Tomas | C2 | met |
| object | [22, 35) | the agreement | C3 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | selected: Supplies its declared canonical role content. |
| C2 | [9, 14) | Tomas | selected: Supplies its declared canonical role content. |
| C3 | [22, 35) | the agreement | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **not_ready**.

- Current R4 emits one subject role and the deterministic probe drops the coordinated Tomas subject.

Current deterministic composer result: `proposition`, subject `Mira`, object `the agreement`, polarity `affirmed`, modality `actual`, attribution `source_narrator`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2,C3` | constructed | valid | met | met | not_applicable | not_ready |
| `C1,C3` | constructed | valid | unmet | met | not_applicable | not_ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Approve separate Candidates for coordinated subjects and the resulting R4 composition limitation.

Policy-body SHA-256: `5cea5cf386382e089422ff3490262b471764a4307738933bb10000e51041be05`.

## AHE-905: Reporting carrier is a separate attribution input

Source: `Mira said that Tomas signed the agreement.`

Marked Event: `signed` at [21, 27).
Route: `label_only_reselection`; adopted selected set: **C3, C4**.

For marked signed, Mira said supplies attribution through the deterministic reporting split, not a selected content role.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-905.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [15, 20) | Tomas | C3 | met |
| object | [28, 41) | the agreement | C4 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | ineligible_reporting_carrier: Mira reports the signing; she is not its subject. |
| C2 | [0, 9) | Mira said | ineligible_reporting_carrier: Mira said is the attribution carrier, supplied outside the selected set. |
| C3 | [15, 20) | Tomas | selected: Supplies its declared canonical role content. |
| C4 | [28, 41) | the agreement | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **ready**.

- Required source content, subject identity, and attribution inputs are supplied.

Current deterministic composer result: `proposition`, subject `Tomas`, object `the agreement`, polarity `affirmed`, modality `actual`, attribution `targeted`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C3,C4` | constructed | valid | met | met | not_applicable | ready |
| `C1,C3,C4` | constructed | valid | unmet | met | not_applicable | ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

Policy-body SHA-256: `8c281094d0aff3a946be01a7c5924dba1a34766ed850d2e1cef5760f595650a4`.

## AHE-906: Canonical full name inside a larger title phrase

Source: `President Mira Chen signed the agreement.`

Marked Event: `signed` at [20, 26).
Route: `label_only_reselection`; adopted selected set: **C4, C6**.

Choose the full name Mira Chen; containment by President Mira Chen does not make the canonical inner span redundant.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-906.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [10, 19) | Mira Chen | C4 | met |
| object | [27, 40) | the agreement | C6 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 9) | President | ineligible_incomplete: A title without the name does not identify the signer. |
| C2 | [0, 19) | President Mira Chen | redundant: The title adds no required content beyond the proposed canonical name C4. |
| C3 | [10, 14) | Mira | ineligible_incomplete: Mira drops Chen from the source name. |
| C4 | [10, 19) | Mira Chen | selected: Supplies its declared canonical role content. |
| C5 | [15, 19) | Chen | ineligible_incomplete: Chen drops Mira from the source name. |
| C6 | [27, 40) | the agreement | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **ready**.

- Required source content, subject identity, and attribution inputs are supplied.

Current deterministic composer result: `proposition`, subject `Mira Chen`, object `the agreement`, polarity `affirmed`, modality `actual`, attribution `source_narrator`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C4,C6` | constructed | valid | met | met | not_applicable | ready |
| `C2,C4,C6` | constructed | valid | unmet | met | not_applicable | ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Approve the policy that the title President adds no required content to this signing proposition.

Policy-body SHA-256: `9875c280dd539f29b8ce6c7532ec61becca005ed17b5d0046f28866fc98e5dd6`.

## AHE-907: Matching text retains separate source occurrences

Source: `Mira thanked Mira.`

Marked Event: `thanked` at [5, 12).
Route: `label_only_reselection`; adopted selected set: **C1, C2**.

Even with the same frozen Actor reference, the two source occurrences supply distinct roles and retain distinct boundaries.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-907.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 4) | Mira | C1 | met |
| object | [13, 17) | Mira | C2 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | selected: Supplies its declared canonical role content. |
| C2 | [13, 17) | Mira | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **ready**.

- Required source content, subject identity, and attribution inputs are supplied.

Current deterministic composer result: `proposition`, subject `Mira`, object `Mira`, polarity `affirmed`, modality `actual`, attribution `source_narrator`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2` | constructed | valid | met | met | not_applicable | ready |
| `C1` | constructed | valid | unmet | met | not_applicable | ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- This controlled example supplies one Actor reference for both occurrences; it does not test identity resolution.

Policy-body SHA-256: `a0ba8dcb75b8c4535f094dc2f38eb0f5d0e790e56d3bb7af058d00bb8db2c0b9`.

## AHE-908: Justified NONE for a weather Event with no referential argument

Source: `It rained.`

Marked Event: `rained` at [3, 9).
Route: `best_choice_reselection`; adopted selected set: **NONE**.

It is an expletive in the complete weather sentence, not a referential participant. No subject, object, time, place, polarity marker, or modality marker is explicitly needed.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-908.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| No selectable role | none | none | none | met: no required range |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 2) | It | ineligible_expletive: It is non-referential weather syntax, not an Actor or a required source argument. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **not_ready**.

- The reference set is present but empty; current R4 holds selection_empty and requires a resolved subject for composition.

Current deterministic composer result: `held` with `selection_empty`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `NONE` | constructed | valid | met | met | justified | not_ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Approve this frame as supported for selection while its subjectless composition remains not_ready; otherwise replace this justified-NONE fixture rather than fabricating a subject.

Policy-body SHA-256: `6a608818431932b002b2e1a0ed96670cb19636a58633dfa4d3cfa951d07319ca`.

## AHE-909: Entity-reference removal leaves selection quality unchanged

Source: `Mira greeted Tomas.`

Marked Event: `greeted` at [5, 12).
Route: `label_only_reselection`; adopted selected set: **C1, C2**.

This case copies AHE-901 source content and role policy with a distinct fixture Event ID; only the composition entity references are absent.

[Complete frozen inputs](../data/r17-semantic-selection-contract/inputs/AHE-909.json).

### Required source content

| Role | Source range | Required text | Canonical label | Pool coverage |
| --- | --- | --- | --- | --- |
| subject | [0, 4) | Mira | C1 | met |
| object | [13, 18) | Tomas | C2 | met |

### Candidate decisions

| Label | Range | Source text | Adopted decision |
| --- | --- | --- | --- |
| C1 | [0, 4) | Mira | selected: Supplies its declared canonical role content. |
| C2 | [13, 18) | Tomas | selected: Supplies its declared canonical role content. |

### Composition readiness and current R4 result

Adopted reference-set readiness: **not_ready**.

- No Actor or Organization references are supplied, so the reference subject cannot resolve.

Current deterministic composer result: `held` with `subject_unavailable`.
This current-code probe is separate from the adopted R17 readiness judgment.

### Adopted answer fixtures and expected signals

| Raw answer | Origin | Grammar | Selection | Coverage | Abstention | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `C1,C2` | constructed | valid | met | met | not_applicable | not_ready |

Constructed answers test the proposed contract; they do not measure model discrimination.

### Original review questions (adopted as written)

- Compare with AHE-901: selection remains met while readiness changes ready to not_ready.

Policy-body SHA-256: `852a91f7dc42ad311bdeeab08bc53725285dbc758586fe03b5ae2fb1fb06c47d`.

## Human adoption record

The exact operator instruction was:

> I accept this. can you adopt the draft policy records and answer fixtures?

The approval attestation records this instruction, the operator identity, operator self-review, and the approved content digests.
Human adoption and review fields now reference that attestation and the unchanged policy-body and input digests.
Every answer fixture records its reviewed content digest and the same human approval evidence.
Historical R16 responses retain their historical origin; constructed answers retain their constructed origin.
The review commit that records this reviewed reference set is `6870e53`.
The complete R17 contract froze its renderer, scoring rules, thresholds, and reviewed records as version 1 on 2026-10-14.
A future policy or fixture edit changes its digest and requires fresh human review.
