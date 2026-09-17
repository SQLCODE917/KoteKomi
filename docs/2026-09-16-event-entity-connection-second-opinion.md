# Event-Entity Connection Second Opinion

This document answers the request in
[Event-Entity Connection Second-Opinion Handoff](2026-09-16-event-entity-connection-second-opinion-handoff.md).

It recomputes the reported numbers from the preserved artifacts.

It evaluates H1 to H8 and answers the eight questions in handoff §14.

It changes no contract, no schema, and no production code.

## 1. Commission and Method

The handoff asks the second reviewer to evaluate H1, H2, H5, and H6 first, then H3, H4, H7, and H8.

I recomputed every headline number from the archived run records.

I did not rerun either model arm.

I did not run a stronger reference model.

I did not run an SRL specialist.

I treated the Stanza diagnostic as model-free evidence.

Two aggregation levels exist at this boundary and I report both:

- candidate occurrence: one ordered inventory row per Event and occurrence pair;
- expected identity: one expected actor or organization per Event.

The distinction matters because the archived reports count identities for matched and missing and
occurrences for extras.

The evaluation is span-strict.

Every candidate is graded `Y` or `N` against approved gold accepted occurrences.

A one-character span difference changes the grade.

### 1.1 Evidence Base

| Artifact | Role | Identity |
|---|---|---|
| `docs/hsq-event-entity-connection-gold-v2.json` | approved gold catalog, 40 Events | sha256 `f7d7534c04fa624d021c7884a20c599ff070fc5c6f21ee07f317de21193ce642` |
| `/private/tmp/kotekomi-fedramp-development-preflight-20260916/report.json` | pairwise arm, development | `6975798edfe9eee0ea9e32fa4a6549e76b53d877a386ac29c5c93029d1e3cb7a` |
| `/private/tmp/kotekomi-fedramp-validation-preflight-20260916/report.json` | pairwise arm, validation | `36e68175806d2a2a061288d691ec7b5ad7997822d0df4695739210f4de05db06` |
| `/private/tmp/kotekomi-event-entity-contrastive-v6-development-r1-20260916/report.json` | batched arm r1, development | `3c4272092d92c602a86d667663da3253fa54f6bd38358d43d7cef33a9d5602b5` |
| `/private/tmp/kotekomi-event-entity-contrastive-v6-validation-r1-20260916/report.json` | batched arm r1, validation | `6bbd1ee0daf2ee992a3d56a80d1b8c73005233f71ee078a3924d032344f8ec50` |
| `/private/tmp/kotekomi-event-entity-contrastive-v6-comparison-20260916.json` | repetition comparison | `development_stable: true` |
| `/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-20260916/` | model-free diagnostic | `6a3c5002665dcf026272c0fee9774ce157f9db5d39ada62be10eb2f144d2f890` |
| `/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-replay-20260916/` | byte-identical replay | `diagnostic.json` identical under `cmp` |
| `/private/tmp/kotekomi-stanza-predicate-argument-full-tests-20260916.xml` | repository verification | tests 1575, skipped 1 |
| `/private/tmp/kotekomi-event-entity-contrastive-v6-development-r2-20260916/`, `...-r3-20260916/` | repeats | decision fingerprints equal to r1 |

The run implementations are tracked in
[Stanza Predicate Argument Diagnostic](2026-09-16-stanza-predicate-argument-diagnostic.md) and in the
[Event-Entity Connection Experiment](2026-09-12-event-entity-connection-experiment.md).

## 2. Handoff Numbers Reproduced

No numeric claim in the handoff failed recomputation.

Two handoff claims need sharper wording; both are detailed in §5.4 and §6.3.

Three rows of this review needed correction during the recomputation pass, all flagged in place: this
review attributed a character offset to the handoff's §9.1 trigger quote that the handoff does not
print, the identity-level extra figure it read from the run records is occurrence-level, and the §3.1
ordering sentence cites F1 rather than precision.

| Handoff claim | Handoff value | Recomputed value | Verdict |
|---|---|---|---|
| §2, §5 corpus size | 40 Events, 90 expected identities, 116 occurrence alternatives | 20 + 20 Events, 47 + 43 identities, 63 + 53 = 116 alternatives | Exact |
| §8.1 candidate readiness | 47 of 47 and 43 of 43, 0 missing | `candidate_available_entity_count` 47 / 43, `candidate_missing_entity_count` 0 / 0 | Exact |
| §8.2 pairwise development | 35 matched, 12 missing, 31 extra, 166 calls | 35, 12, 31, 166 | Exact |
| §8.2 pairwise validation | 38 matched, 5 missing, 32 extra, 106 calls | 38, 5, 32, 106 | Exact |
| §8.2 unstated | not reported | unresolved 0 / 1, passed Events 2 / 6, elapsed 148,620 ms / 97,991 ms, input tokens 90,491 / 56,453 | New |
| §8.3 batched development | 21 matched, 26 missing, 44 extra, 23 unresolved, 20 calls | 21, 26, 44, 23, 20 | Exact |
| §8.3 batched validation | 28, 15, 20, 5, 20 | 28, 15, 20, 5, 20 | Exact |
| §8.3 repetitions | three development repetitions identical | r1, r2, r3 share decision fingerprint `3c4272092d92...`; `development_stable: true`; validation fingerprint equal to r1 | Exact |
| §8.3 call count | 166 to 20, and 106 to 20 | same | Exact |
| §8.3 tokens | 90,491 to 27,397 (development) | sum of `input_admission.formatted_input_token_count`: 90,491 / 27,397 | Exact |
| §8.3 largest request | 577 to 1,823 | 577 at TGE-028 (pairwise development), 1,823 at TGE-018 (batched development r1) | Exact |
| §8.3 unstated | not reported | batched validation largest 2,041 (TGE-051), sum 21,516; pairwise validation largest 601 (TGE-060) | New |
| §8.3 wrong answer count | one thirteen-candidate task returned fourteen answers | TGE-018: 13 candidates, raw answer text `YNYNNYYYYNYYYN` (14 characters), 0 judgments, 13 unresolved | Exact |
| §8.3 elapsed | about 157 s / about 100 s | 156,847 ms / 99,925 ms | Exact |
| §8.4 candidate accounting | 177 / 115 candidates, 47 / 43 identities, 46 / 36 covered, 1 / 7 remainder, 61 / 41 matches, 95 / 40 extras, 0.3910 / 0.5062 precision, 0 / 3 gaps, 0 model calls | same; `missing_candidate_entity_ids` empty in both phases | Exact |

| §8.4 precision denominator | not stated | 0.3910 = 61 / (61 + 95) and 0.5062 = 41 / (41 + 40); the `implicit_negative_retained` rows (20 / 27) and remainder rows stay outside the denominator | Clarification |
| §8.4 direct_argument | 12 matches 0 extras (development), 16 matches 2 extras (validation) | same | Exact |
| §8.4 routing hypothesis | not supported, diagnostic run passed | `summary.json`: `passed: true`, `routing_hypothesis_supported: false`, `model_execution_count: 0` | Exact |
| §9.1 to §9.4 triggers | relative clause, qualification, temporal adjunct, attribution source, each identified by quoted text and no offsets | TGE-016 `agreements`, TGE-017 `avoid`, TGE-054 `partnered`, TGE-055 `offered`, TGE-038 `criticized`, TGE-051 `chastised`; source texts reproduced | Exact |
| §6.4 repository verification | 1,574 tests and one skip | junit `tests="1575"` with `skipped="1"` | Consistent |
| §15 replay | byte-identical, fingerprint `6a3c50...` | `cmp` identical; replay fingerprint equal | Exact |

## 3. Results at Both Aggregation Levels

### 3.1 Candidate Level

| Arm and phase | Candidate rows | Scored gold rows | Y | TP | FP | FN | U | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| Pairwise development | 177 | 62 | 77 | 46 | 31 | 16 | 0 | 0.597 | 0.742 | 0.662 |
| Pairwise validation | 115 | 48 | 74 | 42 | 32 | 6 | 1 | 0.568 | 0.875 | 0.689 |
| Batched development r1 | 177 | 62 | 68 | 24 | 44 | 38 | 10 | 0.353 | 0.387 | 0.369 |
| Batched validation r1 | 115 | 48 | 51 | 31 | 20 | 17 | 5 | 0.608 | 0.646 | 0.626 |
| Batched development r1, TGE-018 excluded | 164 | 52 | 68 | 24 | 44 | 28 | 10 | 0.353 | 0.462 | 0.400 |

A row is one candidate of one Event, scored against the frozen diagnostic label for that span.

`Y` is the number of rows the arm connected; `U` is a row the arm left without a decision.

Scored gold rows are the rows whose span is an accepted occurrence of an expected identity,
plus the remainder rows described in §5.1.

An undecided row scores as not connected; §5.4 reports the two boundary variants.

F1 orders the arms the same way in both phases: pairwise validation 0.689, pairwise development 0.662,
batched validation 0.626, batched development 0.369.

In development the pairwise arm leads on both precision and recall; in validation it leads on
recall (0.875 to 0.646) and trails on precision (0.568 to 0.608).

The batched development collapse is concentrated in one mechanically invalid Event and in
undecided rows; excluding TGE-018 lifts its recall from 0.387 to 0.462 with precision unchanged.

### 3.2 Identity Level

| Arm and phase | Expected identities | Matched | Missing | Share |
|---|---|---|---|---|
| Pairwise development | 47 | 35 | 12 | 0.745 |
| Pairwise validation | 43 | 38 | 5 | 0.884 |
| Batched development r1 | 47 | 21 | 26 | 0.447 |
| Batched validation r1 | 43 | 28 | 15 | 0.651 |

I recomputed these counts by linking candidate spans to expected occurrences exactly.

The recomputed numbers equal the report `matched` and `missing` counts in all four cells.

Identity-level scoring counts only expected identities: the report supplies `matched_entity_count`,
`missing_entity_count`, and `false_negative_entity_count`, and no field counts identities outside the
expected set. Its only extra figure, `extra_connection_count`, is occurrence-level: it equals the
false-positive row count exactly in all four cells, 31, 32, 44, and 20.

Recomputed by name, those extra rows split three ways, in the order of the table above: rows naming an
identity the Event already expects at another occurrence (9, 9, 6, 4), rows naming a catalog identity
the Event does not expect (19, 16, 30, 13 rows over 18, 15, 25, 13 distinct Event-identity pairs), and
rows whose proposed name matches no catalog identity at all (3, 7, 8, 3, including `wrote an`,
`president`, and one whole sentence).

So the two aggregation levels disagree in every cell: an arm can be wrong on an occurrence without
creating an identity connection, and it can connect an identity the Event does not expect while the
identity-level coverage counts stay unchanged.

### 3.3 Catalog Identity Transitions

A transition asks which arm connected each expected identity anywhere in its Event.

The identity universe is 47 development and 43 validation identities, with TGE-018 included.

| Phase | Both arms | Pairwise only | Batched only | Neither arm |
|---|---|---|---|---|
| Development | 19 | 16 | 2 | 10 |
| Validation | 25 | 13 | 3 | 2 |
| Both, TGE-018 excluded | 44 | 24 | 5 | 12 |

The combined row is over 85 identities because the single invalid Event contributes 5 identities,
all of which the pairwise arm connected and the batched arm did not.

Without TGE-018, the batched arm ever connects 49 of 85 identities; the pairwise arm ever connects
68 of 85.

The 16 pairwise-only development identities are `TGE-003 / EGE-003 Trump`;
`TGE-005 / EGE-006 Anthropic`; `TGE-005 / EGE-007 Trump officials`;
`TGE-006 / EGE-008 Anthropic`; `TGE-006 / EGE-009 Trump officials`;
`TGE-015 / EGE-011 Amodei`; `TGE-015 / EGE-012 Skadden, Arps, Slate, Meagher & Flom`;
`TGE-015 / EGE-013 Latham & Watkins`; `TGE-018 / EGE-019 Sacks`; `TGE-018 / EGE-020 Amodei`;
`TGE-018 / EGE-022 Trump`; `TGE-018 / EGE-023 Anthropic`; `TGE-018 / EGE-024 Open Philanthropy`;
`TGE-019 / EGE-025 Amodei`; `TGE-025 / EGE-092 Sacks`; `TGE-054 / EGE-085 Palantir`.

The 13 pairwise-only validation identities are `TGE-013 / EGE-054 Trump`; `TGE-030 / EGE-057 JD Vance`;
`TGE-038 / EGE-060 Trump`; `TGE-039 / EGE-062 Trump officials`; `TGE-051 / EGE-068 Trump officials`;
`TGE-051 / EGE-069 Anthropic`; `TGE-052 / EGE-070 Anthropic`; `TGE-052 / EGE-074 Tarun Chhabra`;
`TGE-053 / EGE-078 Anthropic`; `TGE-056 / EGE-080 AI Safety Institute`;
`TGE-069 / EGE-098 Anthropic representatives`; `TGE-069 / EGE-099 Anthropic`;
`TGE-085 / EGE-101 Court of Appeals for the D.C. Circuit`.

The combined row removes the five TGE-018 identities from the development count, which leaves
11 + 13 = 24 pairwise-only identities over 85.

The 5 batched-only identities are `TGE-016 / EGE-016 Trump administration` and
`TGE-055 / EGE-091 Amazon Web Services` in development; `TGE-052 / EGE-071 Biden administration`,
`TGE-052 / EGE-073 Artificial Intelligence Safety Institute`, `TGE-052 / EGE-075 National Security Council`
in validation.

The two validation identities that no arm connects are `TGE-007 / EGE-045 The New York Times` and
`TGE-064 / EGE-097 Trump administration`.

The ten development identities that no arm connects are `TGE-003 / EGE-082 Joe Biden`,
`TGE-004 / EGE-083 Joe Biden`, `TGE-016 / EGE-014 and EGE-015` (Skadden, Arps, Slate, Meagher & Flom;
Latham & Watkins), `TGE-017 / EGE-017 and EGE-018` (the same two firms), `TGE-027 / EGE-038` and
`TGE-028 / EGE-041` (Trump administration twice), `TGE-055 / EGE-090 Palantir` and `TGE-055 / EGE-093 FedRAMP`.

Three of the five batched-only identities belong to the remainder class of TGE-052, where the
batched arm connects a row that no structural route supports and the pairwise arm does not.

## 4. Where the Arms Differ by Structural Class

Every candidate row carries the routing hypothesis that produced it.

Both arms face the same rows with the same hypotheses: 177 and 115 rows per phase, identical spans,
zero class disagreements.

The only difference between the arms is the answer.

The class names below are routing artifacts, not semantic function labels, because H1's requested
function labels do not exist yet; they are nevertheless the best available partition of the row space.

### 4.1 Development

| Routing class | Rows | Gold rows | Purity | Pairwise Y (TP/FP) | Batched Y (TP/FP) | Batched U |
|---|---|---|---|---|---|---|
| direct_argument | 12 | 12 | 1.00 | 10 (10/0) | 6 (6/0) | 1 |
| coordinated_argument | 23 | 7 | 0.30 | 12 (7/5) | 12 (4/8) | 0 |
| inherited_argument | 72 | 22 | 0.31 | 32 (19/13) | 29 (8/21) | 5 |
| qualified_argument | 31 | 13 | 0.42 | 13 (9/4) | 12 (4/8) | 2 |
| relative_clause_argument | 18 | 7 | 0.39 | 1 (0/1) | 6 (2/4) | 1 |
| semantic_remainder | 10 | 1 | 0.10 | 9 (1/8) | 3 (0/3) | 1 |
| different_sentence | 11 | 0 | 0.00 | 0 (0/0) | 0 (0/0) | 0 |
| diagnostic_gap | 0 | 0 | — | — | — | — |
| Total | 177 | 62 | 0.35 | 77 (46/31) | 68 (24/44) | 10 |

### 4.2 Validation

| Routing class | Rows | Gold rows | Purity | Pairwise Y (TP/FP) | Batched Y (TP/FP) | Batched U |
|---|---|---|---|---|---|---|
| direct_argument | 18 | 16 | 0.89 | 16 (15/1) | 9 (9/0) | 1 |
| coordinated_argument | 6 | 2 | 0.33 | 4 (1/3) | 1 (1/0) | 1 |
| inherited_argument | 34 | 7 | 0.21 | 22 (7/15) | 18 (5/13) | 1 |
| qualified_argument | 23 | 16 | 0.70 | 21 (15/6) | 14 (10/4) | 2 |
| relative_clause_argument | 0 | 0 | — | — | — | — |
| semantic_remainder | 22 | 7 | 0.32 | 10 (4/6) | 9 (6/3) | 0 |
| different_sentence | 9 | 0 | 0.00 | 0 (0/0) | 0 (0/0) | 0 |
| diagnostic_gap | 3 | 0 | 0.00 | 1 (0/1) | 0 (0/0) | 0 |
| Total | 115 | 48 | 0.42 | 74 (42/32) | 51 (31/20) | 5 |

### 4.3 Reading

- Purity varies by a factor of ten across classes: `direct_argument` is 1.00 and 0.89, the large
  `inherited_argument` class 0.31 and 0.21, `different_sentence` 0.00 in both phases.
- Both arms leave every `different_sentence` row at `N`. This is their shared correct suppression:
  0 of 20 connections per phase in the one class with no gold rows.
- The pairwise arm fails `relative_clause_argument` in development: 0 of 7 gold rows, and its single
  connection in that class is one of its false positives.
- The batched arm's development losses concentrate in `inherited_argument` (8 of 22 gold rows),
  `coordinated_argument` (4 of 7), and `qualified_argument` (4 of 13).
- In validation the batched arm loses most in `direct_argument` (9 of 16) and `qualified_argument`
  (10 of 16), where the pairwise arm reaches 15 of 16 in both.
- The batched arm wins the validation `semantic_remainder` class 6 of 7 against 4 of 7, but those are
  the rows with no structural support at all; §5.1 shows what that win means.
- Class-level failure splits cleanly: the pairwise arm is capped by the one class no structural route
  reaches (`relative_clause_argument`, 18 rows, 7 of them gold), while the batched arm is capped by
  recall loss in classes that need no context to judge (9 of 16 `direct_argument` in validation).

## 5. Measurement Validity of the Comparison

### 5.1 The Scored Row Set and the Eight Remainder Rows

Scoring unit: one candidate row of one Event; 177 development rows and 115 validation rows.

Gold labels come from the frozen diagnostic `comparison` field, which I did not recompute.

Gold-Y rows are rows whose span is an accepted occurrence: 61 plus 1 in development and 41 plus 7 in
validation. The added rows are the `expected_semantic_remainder` rows: their spans are accepted
occurrence spans, but no structural route supports them, and any arm that answers `Y` scores a true
positive.

| Phase | Event | Span | Name | Identity | Pairwise | Batched |
|---|---|---|---|---|---|---|
| development | TGE-006 | (239, 248) | Anthropic | EGE-008 | Y | U |
| validation | TGE-052 | (117, 138) | Biden administration | EGE-071 | N | Y |
| validation | TGE-052 | (152, 168) | Elizabeth Kelly | EGE-072 | Y | Y |
| validation | TGE-052 | (203, 243) | Artificial Intelligence Safety Institute | EGE-073 | N | Y |
| validation | TGE-052 | (245, 258) | Tarun Chhabra | EGE-074 | Y | N |
| validation | TGE-052 | (320, 345) | National Security Council | EGE-075 | N | Y |
| validation | TGE-052 | (351, 363) | Ben Buchanan | EGE-076 | Y | Y |
| validation | TGE-056 | (29, 38) | Anthropic | EGE-079 | Y | Y |

Consequence one: the recall figures in §3.1 are decision recall over rows, not structural coverage of
accepted occurrences.

Consequence two: neither arm is structurally conservative. In validation the batched arm connects 6 of
7 rows that no structural route supports, and the pairwise arm connects 4 of 7.

Consequence three: TGE-052 supplies 6 of the 8 remainder rows and 3 of the 5 batched-only identities
in §3.3, so one Event carries the largest single share of the validation arm difference.

The diagnostic's own structural coverage remains the §2 figures: 61 of 62 and 41 of 48 gold rows
matched, with the same 8 rows as the unmatched remainder.

### 5.2 Occurrence Coverage and Span Variants

The catalog holds 116 accepted occurrence alternatives, 63 in development and 53 in validation.

110 of them have a candidate row at the identical span; six do not.

| Event | Accepted occurrence without its own candidate | Nearest candidate row |
|---|---|---|
| TGE-078 | (47, 72) `the Department of Defense` | (51, 72) |
| TGE-064 | (122, 133) `Anthropic's` | (122, 131) |
| TGE-064 | (351, 375) `the Trump administration` | (355, 375) |
| TGE-069 | (81, 93) `the  company` | (30, 39), a different occurrence of the same identity |
| TGE-085 | (18, 65) `the  Court  of  Appeals  for  the  D.C. Circuit` | (23, 65) |
| TGE-085 | (96, 107) `Anthropic's` | (96, 105) |

Every affected identity keeps at least one covered alternative, so no identity is unscorable, and the
six rows cost both arms identically.

The variants are leading determiners, possessives, and doubled spaces such as `Biden  administration`.

Near-variants can land on opposite sides of the boundary: TGE-069 holds (81, 95) `the  company's` as a
gold-negative candidate while the accepted (81, 93) form has no candidate row at all.

Name strings diverge from identity labels in six gold rows: `Amodei` for canonical `Dario Amodei`
(development TGE-002, TGE-003, TGE-005) and `the Trump administration` for canonical
`Trump administration` (development TGE-027, TGE-028; validation TGE-040).

One candidate couples a wrong name to a span: validation TGE-038 records (5, 15) `That month` with
`entity_name` `Anthropic`, a temporal adjunct carrying an organization name.

A downstream consumer that keys on names instead of identity IDs would split or merge identities on
these rows, which is why the Ledger keys connections by identity.

TGE-038 also shows a trigger detail worth recording, and a correction to this review: the frozen
diagnostic records the trigger `criticized` with head span (25, 35) in TGE-038, while the handoff
identifies the same trigger by quoted text and prints no offsets at all. An earlier draft of this
section attributed (25, 34) to the handoff; that figure has no source in either document.

### 5.3 Diagnostic Gap Rows

Development has zero gap rows; validation has three.

| Event | Span | Text | Candidate kind | `gap_code` | Pairwise | Batched |
|---|---|---|---|---|---|---|
| TGE-007 | (32, 40) | `wrote an` | actor | `entity_anchor_ambiguous` | N | N |
| TGE-008 | (32, 40) | `wrote an` | actor | `entity_anchor_ambiguous` | Y | N |
| TGE-009 | (32, 40) | `wrote an` | actor | `entity_anchor_ambiguous` | N | N |

All three rows are the same character span in three different Events, so this class is one repeated
proposal defect rather than three independent cases.

`wrote an` is a verb plus a determiner, and the proposal layer emitted it as an `actor` candidate whose
anchor the routing could not resolve to any entity.

The diagnostic records `structurally_supported` false and `comparison` `implicit_negative_retained` on
all three.

The diagnostic summary counts `diagnostic_gap_count` 3 against `expected_diagnostic_gap_count` 0, so
the gold expected no gaps at all.

A gap row can never score a true positive: any `Y` on it is a false positive by construction.

The pairwise arm's single `Y` at TGE-008 is one of its 32 validation false positives; the batched arm
answers `N` on all three.

Two consequences for the comparison:

- Three of 115 validation rows, 2.6 percent of validation and 1.0 percent of all 292 rows, carry no
  usable entity anchor, so they dilate the false-positive surface for both arms without any possible
  reward.
- The proposal layer needs a shape check before the model sees a candidate: a span with no noun or
  proper-noun token, or a candidate whose `entity_kind` contradicts its head token, should fail at
  proposal time instead of reaching the model as an `actor`.

### 5.4 Boundary Variants and the Precision Denominator

The handoff §8.4 reports structural precision 0.3910 and 0.5062 without stating its denominator, and
§2 above records the arithmetic.

Four candidate cohorts exist per phase and only two of them enter that denominator.

| Cohort (`comparison`) | Development | Validation | Enters handoff §8.4 precision | Content |
|---|---:|---:|---|---|
| `structural_match` | 61 | 41 | numerator | gold `Y` with a supporting path |
| `structural_extra` | 95 | 40 | denominator | gold `N` with a supporting path |
| `implicit_negative_retained` | 20 | 27 | excluded | non-gold rows with no path: `different_sentence` 11 / 9, non-gold `semantic_remainder` 9 / 15, diagnostic gap 0 / 3 |
| `expected_semantic_remainder` | 1 | 7 | excluded | gold `Y` with no supporting path |
| Total | 177 | 115 | | |

0.3910 = 61 / (61 + 95) and 0.5062 = 41 / (41 + 40), so the handoff figure is the routing's
structural precision and not an arm precision.

The arm precisions in §3.1 use all 177 and 115 rows.

Both figures are correct under their own conventions, but they are not comparable, and a reader who
puts them in one table would compare a 156-row subset against a 177-row set.

The rows below place the same numerators over each convention.

| Convention | Pairwise development | Pairwise validation | Batched development | Batched validation |
|---|---:|---:|---:|---:|
| All rows (§3.1) | 46 / 77 = 0.597 | 42 / 74 = 0.568 | 24 / 68 = 0.353 | 31 / 51 = 0.608 |
| Structural rows only; retained negatives excluded from the denominator, correct remainder answers credited | 46 / 69 = 0.667 | 42 / 67 = 0.627 | 24 / 65 = 0.369 | 31 / 48 = 0.646 |
| Handoff §8.4 style; remainder rows excluded from numerator and denominator | 45 / 68 = 0.662 | 38 / 63 = 0.603 | 24 / 65 = 0.369 | 25 / 42 = 0.595 |

The validation precision ordering is convention-dependent: all rows give batched 0.608 over pairwise
0.568, and the §8.4 style gives pairwise 0.603 over batched 0.595.

The reversal comes from the seven `expected_semantic_remainder` rows: the batched arm connects 6 of
them and the pairwise arm 4, and every `Y` there is a true positive under the strict span anchor.

Those rows have no structural support, so the §8.4 style credits neither arm for them.

The F1 ordering is not convention-dependent: pairwise leads batched in both phases under both
conventions, 0.662 against 0.369 and 0.689 against 0.626 under §3.1, and 0.698 against 0.378 and 0.731
against 0.602 under the §8.4 style.

The retained-negative cohort shows an arm policy difference rather than a quality difference: the
pairwise arm connects 8 of 20 development and 7 of 27 validation rows of that cohort, and the batched
arm 3 of 20 and 3 of 27.

Both answers are graded; the cohort exists to keep those rows out of the structural claim, not out of
the comparison.

Undecided rows supply the second boundary variant.

| Arm and phase | `U` rows | Strict precision | Strict recall | Optimistic precision | Optimistic recall |
|---|---:|---:|---:|---:|---:|
| Pairwise development | 0 | 0.597 | 0.742 | 0.597 | 0.742 |
| Pairwise validation | 1 | 0.568 | 0.875 | 0.560 | 0.875 |
| Batched development r1 | 10 | 0.353 | 0.387 | 0.372 | 0.433 |
| Batched validation r1 | 5 | 0.608 | 0.646 | 0.625 | 0.673 |

The optimistic variant is the best case for the arm: every undecided row resolves to connected, so
undecided gold-`Y` rows become true positives and undecided gold-`N` rows become false positives.

The pairwise validation row shows the variant working against the arm, because its one undecided row
is gold `N`.

The variant moves the batched arm more, in development recall 0.387 to 0.433 and in validation
precision 0.608 to 0.625, because the batched contract leaves more rows undecided.

Neither variant changes any ordering of §3.1.

A third variant applies to development only: excluding the mechanically invalid TGE-018 inventory
drops 13 rows whose 10 gold-`Y` candidates could never be judged, and lifts batched development recall
from 0.387 to 0.462 with precision unchanged at 0.353, the last row of §3.1.

All four run reports record `passed: false`, so the tables above are the arms' disagreement surface
and not an accepted result.

## 6. Verification of the Supporting Claims

### 6.1 Record Integrity and the Zero-Write Audit

| Check | Evidence | Result |
|---|---|---|
| Gold identity | `shasum -a 256 docs/hsq-event-entity-connection-gold-v2.json` equals `catalog_sha256` in all four run reports and in the diagnostic summary | `f7d7534c04fa624d021c7884a20c599ff070fc5c6f21ee07f317de21193ce642` |
| Diagnostic fingerprint | `summary.json` `result_fingerprint`, equal in the replay directory | `6a3c5002665dcf026272c0fee9774ce157f9db5d39ada62be10eb2f144d2f890` |
| Diagnostic replay | `cmp` of `diagnostic.json` in run and replay directories | byte-identical |
| Batched repetitions | r1, r2, r3 `result_fingerprint`; comparison artifact `development_stable` | `3c4272092d92...` three times, `true` |
| Validation fingerprint | r1 `result_fingerprint` against the comparison artifact | `6bbd1ee0daf2...`, equal |
| Accepted-state writes | `accepted_ledger_change_count` 0 and `proposed_change_count` 0 in all four reports, 0 in every per-event record, 0 in both diagnostic phases | zero |
| Source exclusions | `violated_exclusion_count` 0 in all four reports; `excluded_expression_count` 2 development / 0 validation | honored |
| Acceptance state | four run reports `passed: false`; comparison `passed: false`, `production_integration: not_activated`; diagnostic `passed: true` with `routing_hypothesis_supported: false` | nothing promoted |

Across the four run directories 312 model runs exist, 311 with status `succeeded` and 1 with status
`invalid_output`, the TGE-018 task of §3.1.

The handoff's claims of exact source and execution evidence and of zero accepted-state writes are
therefore machine-verifiable in the preserved records, and no artifact of this boundary is currently
promotable.

### 6.2 Run Accounting

| Measure | Pairwise development | Pairwise validation | Batched development r1 | Batched validation r1 |
|---|---:|---:|---:|---:|
| Model calls | 166 | 106 | 20 | 20 |
| Formatted input tokens | 90,491 | 56,453 | 27,397 | 21,516 |
| Largest single request | 577 (TGE-028) | 601 (TGE-060) | 1,823 (TGE-018) | 2,041 (TGE-051) |
| Summed model elapsed | 148,620 ms | 97,991 ms | 156,847 ms | 99,925 ms |
| Calls per Event | 8.3 | 5.3 | 1.0 | 1.0 |
| Formatted input per Event | 4,525 | 2,823 | 1,370 | 1,076 |

Token and elapsed totals are sums over `model_runs` entries in the per-event records, and the largest
request is the maximum `input_admission.formatted_input_token_count` in a phase.

Batching cut calls from 8.3 to 1.0 per Event and formatted input by a factor of 3.3 in development and
2.6 in validation.

It did not cut wall-clock time: the batched arm used 5.5 percent more model time in development and
2.0 percent more in validation, and its largest request grew by a factor of 3.2.

All 312 runs share one model identity, `qwen2.5-14b-instruct` on `lm_studio` with tokenizer
`lm_studio_loaded_model_tokenizer_v1:qwen2.5-14b-instruct`, and one sampling configuration, `seed` 17
with `temperature` 0.

`weights_digest` is null in every run, so model identity rests on name, runtime, and tokenizer rather
than on a weights hash.

The fixed seed and zero temperature explain the equal repetition fingerprints: an identical request
reproduces an identical decision, so the stable failures of the handoff §8.3 are contract properties
and not sampling noise.

The batched contract then spends its saved calls on much larger decisions: one 1,823-token request
carried 13 candidates and returned a 14-character answer, which is the failure mode the pairwise
contract cannot have by construction.

### 6.3 Repository Verification Count

The handoff §6.4 records 1,574 tests and one skip.

The preserved junit report counts `tests="1575"` with `skipped="1"`, and the log ends
`1574 passed, 1 skipped in 338.42s` with `exit_code` 0.

The sharpened wording is 1,575 collected, 1,574 passed, 1 skipped, so the handoff's number is the
passed count rather than the collected count.

The suite is the repository's own verification at the revision that produced the diagnostic.

It constrains none of the accuracies above, because no arm behavior is asserted by the repository
tests.

## 7. Hypothesis Evaluation

### 7.1 H1 and H2

**H1, the binary target conflates incompatible semantic functions: supported.**

- Class purity spans 0.00 to 1.00 in both phases (§4): `direct_argument` 1.00 and 0.89,
  `qualified_argument` 0.42 and 0.70, `inherited_argument` 0.31 and 0.21, `coordinated_argument` 0.30
  and 0.33, `different_sentence` 0.00.
- Both arms are most accurate exactly where the function is a direct argument, 10 of 12 and 6 of 12
  connected development rows and 15 of 16 and 9 of 16 validation rows.
- A row decision is not a stable property of its surface: exactly one arm is wrong on 75 of 177
  development rows and 53 of 115 validation rows, and both arms are wrong on another 27 and 11.
- The two validation `direct_argument` extras that the handoff §8.4 identifies are a temporal
  expression and an attribution source, the same span geometry with a different function.
- The H1 test itself, diagnostic function labels on the same occurrences with agreement measured
  before any binary mapping, has not been run; the routing classes are the closest existing instrument,
  which makes this support rather than the experiment.

**H2, the marked Event expression is too narrow for the complete proposition: supported in development,
unconfirmed in validation.**

- Development `relative_clause_argument` holds 18 rows and 7 gold rows, and the pairwise arm connects
  0 of the 7 while the batched arm connects 2 (§4.1).
- The one development row with a gold `Y` and no structural support, TGE-006 (239, 248) `Anthropic`, is
  a proposition-level relation: the accepted occurrence sits behind a clausal complement
  (`held` then `discussions` then `Anthropic`) rather than behind the marked head.
- The opposite symptom, entities of other sentences entering the inventory, is the
  `different_sentence` class: 11 development and 9 validation rows, zero gold, and both arms suppress
  every one of them.
- Validation contains no `relative_clause_argument` rows at all: its handoff §9 cases, TGE-038
  `criticized` and TGE-051 `chastised`, route as `direct_argument`, so the held-out phase cannot
  confirm or reject H2 on the same instrument.
- The proposition-envelope comparison of the H2 test has not been run.

### 7.2 H5 and H6

**H5, a semantic-role or Event-argument specialist can supply a better proposal layer: partially
supported.**

- The diagnostic is the only specialist evidence in the record, and it supplies syntax rather than
  semantics: it proposes candidate occurrences with near-complete coverage of the gold, 61 of 62 and 41
  of 48 gold rows and 46 of 47 and 36 of 43 identities, `structural_entity_recall` 0.9787 and 0.8372.
- Proposal precision is the part that fails: 95 and 40 extras, which is 1.56 and 0.98 extras per matched
  gold row, plus 20 and 27 retained negatives.
- Adjunct rejection is exactly what the record does not measure. The classes that carry temporal,
  attributive, and background material are `qualified_argument`, `different_sentence`, and
  `semantic_remainder`, and no SRL or Event-argument extractor was run to test whether a role-aware
  proposer rejects them.
- The three diagnostic gap rows of §5.3 show a proposal shape defect that any specialist would have to
  fix or avoid.
- The H5 test, one pinned specialist with span mapping and the four measures, has not been run. An
  adoption bar should require at least today's identity coverage with a materially lower
  extras-per-match ratio.

### 7.3 H3 and H4

**H3, candidate batching causes cross-candidate interference: partly supported as a mechanical risk,
open as a semantic claim.**

- Development is asymmetric in the direction H3 predicts: the batched arm is the only wrong arm on 55
  rows against 20 for the pairwise arm.
- Validation is symmetric, 26 against 27, and the batched arm leads precision there, so the same
  batching change does not produce the same penalty in both phases.
- The mechanical defect is documented: one of 312 runs reports `invalid_output`, with a 13-candidate
  inventory, a 14-character answer, 0 judgments, 13 unresolved rows, and the largest request in the
  corpus at 1,823 tokens (§3.1, §6.2).
- Repeats are identical, so the count drift is deterministic. A contract that cannot absorb an
  off-by-one is fragile, but a reproducible failure is not by itself evidence of interference.
- The H3 falsification test, identical occurrences through one-candidate, small-group, and full-Event
  tasks, has not been run, so the semantic half of H3 stays open.

**H4, Qwen2.5 has reached a semantic capability ceiling: not evaluable from these records.**

- The stronger-model replay of the H4 test has not been run, so no preserved artifact separates contract
  failure from capability.
- What the records do refute is the noise variant: `seed` 17, `temperature` 0, and equal repetition
  fingerprints make every recorded failure reproducible.
- A large share of the error is not arm-specific. Both arms are wrong on the same 27 development and 11
  validation rows, and exactly one arm is wrong on another 75 and 53. That shared floor is what any
  stronger model or contract change has to move.
- The single most informative missing control is one sealed replay with a stronger reference model
  under the unchanged contract and evaluator.

### 7.4 H7 and H8

**H7, identity-level scoring hides occurrence-level boundary defects: supported.**

- The records' only extra figure is occurrence-level: `extra_connection_count` equals the 31, 32, 44,
  and 20 false-positive rows, while identity-level fields cover expected identities only, and a
  name-based recomputation finds extras outside the Event's expected set in every cell (§3.2).
- The two aggregation levels disagree on the same runs: pairwise development shows a 0.745 identity
  share against 0.597 occurrence precision and 0.742 occurrence recall, and batched development shows
  0.447 against 0.353 and 0.387.
- Six accepted occurrence forms have no candidate row at all (§5.2), so no occurrence-level metric can
  see them while an identity-level count hides the gap.
- The recommendation stands: occurrence-level precision and recall are the primary report, identity
  consolidation is a query convenience, and future experiments must carry both.

**H8, the current corpus is too narrow to select a general production policy: a validity constraint
rather than an open failure hypothesis.**

- Both phases come from one PDF: one source, one subject area, and one document's sentence style.
- The held-out phase is same-document and easier for both arms, recall 0.742 to 0.875 for the pairwise
  arm and 0.387 to 0.646 for the batched arm, so it carries no distribution-shift evidence.
- Nothing in these records estimates behavior on another source, and the handoff itself states that H8
  does not explain the current same-document failures.
- The H8 test, a second human-reviewed packet from another source and subject area under one frozen
  contract, has not been run, and no production threshold should be calibrated on these 40 Events alone.

### 7.5 Verdict Summary

| Hypothesis | Verdict | Strongest recorded evidence | Missing control |
|---|---|---|---|
| H1 | Supported | class purity 0.00 to 1.00; 75 and 53 rows where exactly one arm is wrong | function-labeled gold with measured agreement |
| H2 | Supported in development | `relative_clause_argument` 0 of 7 and 2 of 7; the TGE-006 remainder row | proposition envelope on both phases |
| H5 | Partially supported | identity coverage 46 of 47 and 36 of 43 | one pinned specialist scored for adjunct rejection |
| H6 | Partially supported | 23 zero-gold rows removable with one false positive | extras falling under envelope plus labels |
| H3 | Open; mechanical risk shown | 55 against 20 arm-only-wrong rows in development; one `invalid_output` run | one-candidate and small-group arms |
| H4 | Not evaluable | deterministic failures; a shared floor of 27 and 11 rows | stronger-model replay |
| H7 | Supported | occurrence extras 31 to 44 against identity fields that cover expected identities only | occurrence-level reporting in every experiment |
| H8 | Validity constraint | one PDF; an easier held-out phase | a second packet from another source |

## 8. Answers to the Handoff Questions

### 8.1 Questions 1 to 4

**1. Is `belongs to the complete source proposition` a coherent atomic target?**

No as an atomic edge label, yes as a scope.

It bundles at least three separable questions: which proposition the Event marks, whether an entity
takes part in it, and what function the entity carries there.

The recorded rows show the bundle failing: two contracts judge the same inventory differently on 75
development and 53 validation rows with exactly one arm wrong, and class purity runs from 0.00 to 1.00.

Keep the proposition as the retrieval scope, attach the function as its own attribute, and keep source
grounding as an invariant, exact span and exact sentence, rather than as part of the label.

**2. Must core participants and source-grounded qualifications use separate edge kinds?**

Yes.

Qualifications are the largest predictable error source: `qualified_argument` purity is 0.42 and 0.70
while `direct_argument` purity is 1.00 and 0.89, and the handoff §9.2 examples `partnered` and `offered`
are qualification relations.

One label forces the model to trade participation recall against qualification rejection, and it hides
that trade inside a single precision number.

Separate edge kinds let the Ledger keep both, let a query include or exclude qualification edges
without re-adjudication, and make the mismatch visible when an expected participant turns out to be a
qualifier, which is precisely what the H1 test measures.

**3. Can a small function inventory avoid an exhaustive Event-role ontology?**

Yes, and the corpus already constrains its size to eight labels: core participant, content or subject,
counterparty or controller, qualification, attribution source, temporal or locative adjunct,
background, and neighboring Event, plus one explicit unknown for review.

The routing emitted seven class names that map onto those without loss, and the one class with no gold
at all, `different_sentence`, is a scope question rather than a role.

What matters is not ontology depth but a declared include or exclude policy per label and per-class
gold, which the frozen 292 rows can supply at the occurrence level.

**4. Does proposition-first extraction fit KoteKomi better than entity-pair classification?**

Yes as the front half of the contract, provided function labels travel with it.

Proposition-first removes 23 zero-gold rows, 11 development and 12 validation, and the call difference
is 8.3 against 1.0 per Event, so the surface reduction is cheap and safe.

But the 95 and 40 recorded extras are in-proposition, and no boundary alone rejects them; an envelope
without function labels would shrink the model surface and keep the same error rate on the rows that
remain.

The recorded evidence therefore supports envelope plus labels, with occurrence-level scoring kept
primary.

### 8.2 Questions 5 to 8

**5. Which local specialist can propose semantic arguments on Apple Silicon within a 24 GB budget?**

The only verified proposer in this record is the dependency layer already pinned in the repository that
produced the diagnostic: local, deterministic, reproducible, and covering 61 of 62 and 41 of 48 gold
rows.

It is syntax rather than semantic roles, so it can propose participants but cannot reject adjuncts, and
its extras-per-match ratio is 1.56 and 0.98.

The family to test next is a compact PropBank-style SRL tagger exported to ONNX or CoreML at int8,
which fits a 24 GB budget and can be scored directly against the frozen gold.

The acceptance test matters more than the checkpoint name: exact character offsets reproduced for every
proposed span, because a one-character difference already changes grades (§5.2); deterministic decoding
across two replays; a pinned revision and license; and the four H5 measures, core recall, adjunct
rejection, latency, and replay stability, recorded before any Ledger admission.

No specific checkpoint is qualified by this review, and selecting one before the H1 and H4 controls
report would spend budget on a proposer for a target that still conflates functions.

**6. Which experiment best separates task-contract failure from Qwen capability limits?**

A two-by-two over contract and solver on the sealed inputs: the binary pair contract against a
function-labeled proposition envelope, crossed with the pinned Qwen and one stronger reference, all
scored span-strict at occurrence level against the frozen gold with the count-drift gate.

The record holds one cell, binary pair with Qwen, and it shows that the cell is stable, because
`temperature` 0 with a fixed seed reproduces every decision, so remaining differences would come from
contract or solver rather than sampling.

Add the one-candidate and small-group tasks of the H3 test as a third factor if budget allows, because
development shows the largest arm-specific asymmetry there, 55 against 20, while validation does not, 26
against 27.

The separating statistic is the shared floor: today both arms fail the same 27 development and 11
validation rows. If a stronger model under the labeled contract clears that floor, the target was the
problem; if it fails there too, capability or scope is.
**7. How can KoteKomi preserve source precision while making edges queryable?**

By keeping precision and queryability in different places.

The connection record carries the exact character span, the sentence identity, the Event trigger
identity, the function label, and the provenance activity.

The queryable dimension is the function label plus the identity key, never the surface name.

The records show why: six gold rows carry a display name that differs from the identity label and one
candidate couples a wrong name to a span (§5.2), so an edge keyed on names would split or merge
identities, while an edge keyed on identity IDs with an exact source span survives both name drift and
span variants.

Syntax or path evidence belongs in the edge as evidence and never as the identity of the edge.

Every such edge remains derived state and must be rebuildable from the Ledger and the source.

**8. What evidence threshold justifies production integration without weakening Ledger integrity?**

A conjunction that the current record does not approach: occurrence-level precision and recall of at
least 0.90 on two sealed packets from different documents and subject areas, against today's 0.353 to
0.608 precision and 0.387 to 0.875 recall on one PDF; zero count-drift or parse failures among admitted
runs, against one in 312; every accepted edge carrying an exact source span, a function label, and a
provenance activity; connections without structural or labeled support quarantined as reviewable
ProposedChange records rather than accepted; identical result fingerprints across two replays; and a
rebuild path from the Ledger alone.

Identity-level shares must never be the promotion metric by themselves, because they count expected
identities only while occurrence false positives run to 44 and extras naming identities outside the
expected set run to 30.

## 9. Verdict

The handoff's numbers hold: every figure I recomputed from the preserved artifacts matched, the two
wording issues are resolved in §5.4 and §6.3, and the zero accepted-state write claim is
machine-verifiable.

The arms do not hold up: all four run reports record `passed: false`, and neither arm approaches a
production target at occurrence level.

The comparison itself is sound but narrow: one PDF, the same 40 Events across both phases, one pinned
model with no stronger reference, no specialist proposer, and span-strict gold that leaves six accepted
forms unscorable.

What the comparison establishes:

- The binary target is not a stable property of the row surface: exactly one arm is wrong on 75
  development and 53 validation rows, and class purity spans 0.00 to 1.00 (H1, H7).
- Per-Event batching cuts calls from 8.3 to 1.0 and formatted input by a factor of 3.3 without
  reducing wall-clock time, and it damages development for reasons that are partly mechanical, one
  invalid inventory, and partly arm-specific, 55 against 20.
- Identity-level reporting would have hidden the boundary problem: the identity fields count only
  expected identities, while occurrence false positives run 31 to 44 and extras naming identities outside
  the expected set run 13 to 30.
- The routing layer itself cannot be promoted: 0.3910 and 0.5062 structural precision.

What it does not establish:

- Whether contract shape or model capability is the binding constraint (H3, H4).
- Whether any local specialist actually rejects adjuncts (H5).
- Any cross-document generalization (H8).
- Any defensible production threshold.

Recommended next step, bounded to one experiment:

- Contract: function-labeled proposition envelope with the eight labels of §8.1 question 3,
  occurrence-level span-strict scoring, the count-drift gate, and zero writes.
- Solvers: the pinned `qwen2.5-14b-instruct` and one stronger reference.
- Tasks: one-candidate and per-Event batch over the identical occurrence set.
- Inputs: the sealed 40 Events plus, if budget allows, a second human-reviewed packet from another
  source and subject area.
- Reporting: both aggregation levels and all boundary variants of §5.4.

Do not retune the binary vector prompt, do not promote routing path classes, do not select a specialist
before the function-labeled contract reports, and do not accept any edge on identity-level metrics
alone.

## 10. Limits and Residual Uncertainty

I reran no arm and invoked no model: every number above comes from preserved artifacts, so any defect
in those artifacts propagates into this review.

No stronger reference model and no SRL or Event-argument extractor was run, so the H4, H5, and H6
acceptance clauses remain untested.

Grading is span-strict against the frozen diagnostic labels and I did not rebuild gold, so known gold
and proposal defects matter: six accepted occurrence forms have no candidate row while every affected
identity keeps a covered alternative, six gold rows carry a proposal name that differs from the
identity's canonical label (§5.2), and one inventory is mechanically invalid (§3.1).

My polarity mapping grades an accepted occurrence `Y`, everything else `N`, and counts rejected vectors
and abstentions as not connected; §5.4 exposes the strict and optimistic variants of that choice.

The cohort names and the class boundaries are the diagnostic's, not mine, and its classes approximate
the function inventory of H1 rather than testing it.

The TGE-018 row set is reported both ways, excluded in §3.1 and included there and in §7.3.

The corpus is one PDF with no second source, so no cross-document claim is supported.

`weights_digest` is null in all 312 model runs, so the model identity claim rests on name, runtime,
tokenizer, and the paired reports.

The run implementations are pinned but a dependency or parser upgrade would move every routing class of
§4 and every structural figure of §5.

The recomputation used disposable scripts reading the preserved artifacts, listed in §11, so
re-verification requires both the scripts and those local files.

## 11. Reproducing This Review

Checks I ran, with their exact commands:

- gold identity: `shasum -a 256 docs/hsq-event-entity-connection-gold-v2.json`;
- diagnostic replay: `cmp` on `diagnostic.json` in the run and replay directories;
- row scoring, class tables, and the false-positive decomposition: `python3 /tmp/kk_final.py`;
- identity transitions: `python3 /tmp/kk_transitions.py`;
- the §3, §4, and §5 recomputation pass, including the class tables and the identity counts:
  `python3 /tmp/kk_verify_final.py`;
- run accounting: aggregation over `model_runs[].input_admission.formatted_input_token_count` and
  `model_runs[].execution_diagnostics.elapsed_milliseconds` in the four `events/*.json` directories;
- repository verification: the junit report and log of
  `/private/tmp/kotekomi-stanza-predicate-argument-full-tests-20260916.xml`.

The scripts compose stable deterministic functions over the frozen artifacts, are disposable, and are
not repository code, so a re-verification starts by recreating them from the definitions in §1, §3, and
§5.

Tests run: none by this review; every figure is a recomputation over preserved records.

Tests not run: the repository suite, either model arm, the stronger reference model, and any specialist
proposer.
End of review.