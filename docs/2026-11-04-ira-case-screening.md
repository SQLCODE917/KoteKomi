# IRA-01 Case Screening: No Stored Event Expresses a Complete Simple Proposition

- Status: Open (IRA-01-A blocked pending a scope decision)
- Parent: [Operator Workflow TDD](2026-11-04-ira-operator-workflow.md)
- Population: run `igr_3a167add040a4fcc8aec6aba36363502`, 167 Event outcomes, 21 token artifacts

## Finding

The previously proposed case `sge_8f37b32d221d8974c7725e42` is a semantic-loss counterexample.
Its source sentence is `Sacks viewed Amodei's decision to attend the World Economic Forum over
Trump's second inauguration`, and with its neighbour it continues `... as evidence that Anthropic
would not support Trump's agenda`.
The selected Assertion `Sacks viewed Amodei's decision` drops the decision's content, the
coordinated evidence, and the `viewed ... as evidence that ...` complement that carries Sacks's
inference.
Structural acceptance does not establish semantic completeness.
The R19 precedent records previously implemented behaviour; it is not used here to justify
correctness.

## Gates applied

| Gate | Result |
|---|---|
| 1. Read the whole sentence and state its complete meaning | Applied to every Event |
| 2. Confirm the Assertion representation can express it | Not demonstrated by the current path; requires the bounded complement increment below |
| 3. Verify the stored selector and composer path | Applied to every Event |
| 4. Present the case for approval | Not reached |

## Population evidence

- 28 Events realize both a subject role and an object role.
- 5 of those have non-referring subjects (`it`, `that`, `which`), which cannot carry a reviewed identity.
- 2 hold on `unsupported_time_place` although selection realized both roles:
  `sge_6054fa9e10adfd8c6ec99d0a` and `sge_fc5ecf8c1d8dfb15a312e0e4`.
- The remaining Events drop a meaning-bearing complement, modifier, or coordination that the
  current subject / predicate / object Assertion cannot express.

| Event | Selected object | Dropped from the sentence |
|---|---|---|
| `sge_23773afb43a271e3a806cbfc` | `an op-ed` | `in The New York Times describing the artificial intelligence regulation bill` |
| `sge_4c20fd200372030b26e51d52` | `his associates` | `to vote for vice president Kamala Harris over Trump` |
| `sge_f5a3ad7173de77615bde69c8` | `ties` | `with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins` |
| `sge_14b44ada5ff18cabf168a42b` | `a blog post` | `rebuffing "inaccurate claims" from the Trump administration` |
| `sge_abb8c164cc2b1999e2a9ca0e` | `views` | `explicitly espoused by vice president JD Vance` |
| `sge_acb0020374260d9dd45e0e1a` | `Google Gemini` | `for the platform, then OpenAI's ChatGPT` |
| `sge_b2be68f5274d8e1265ec2838` | `Anthropic's emergency motion` | `for a stay of the FASCSA designation in April` |

## Recommended case (demonstrated on the stored parse; content approval pending)

Screening for a case whose full required content survives the shared path produced eight
composed candidates. Most drop a meaning-bearing complement, carry a non-referring subject
(`which`, `that`), or state an embedded hypothetical. One candidate keeps a complete
atomic claim:

| Element | Verified value |
|---|---|
| Event | `sge_fe4ca1d0afb0c91dbfa9df9d` |
| Paragraph node | `nod_da86f9a7f68fd497cb47a88e_0022`, node start 8720 |
| Trigger | `started`, 96..103 (label `start`) |
| Subject boundary | `the US`, 89..95 |
| Object boundary | `the 2026 Iran war`, 104..121 |
| Statement span | 89..121, `the US started the 2026 Iran war` |
| Completion | none required: the object head governs no `acl` |
| Composition | `composed` with the unmodified derivation |

Source context: `... OpenAI "rushed", hours before the US started the 2026 Iran war, to get a
deal without the constraints that Anthropic ...`. The temporal phrase frames the clause; the
clause itself is a complete subject-predicate-object claim.

Proposed expected Assertion (agent-drafted; awaiting human review):

| Field | Proposed value |
|---|---|
| Type | `reported_observation` |
| Epistemic scope | `source_report` |
| Subject | accepted `Organization` for the United States (identity review required) |
| Predicate | `started` |
| Object | value `the 2026 Iran war` |
| Qualifiers | `polarity: affirmed`, `modality: actual` |
| Source authority | `secondary` |
| Attribution basis | `direct_document` |
| Evidence | statement EvidenceTarget over 8809..8841 |
| Status | `proposed` |

### Subject span relationship (resolved)

The existing composer resolves an identity whose accepted occurrence is **contained within**
the selected fragment (`_resolve_entity`).
Selected subject `the US` at 89..95 with an accepted occurrence for `US` at 93..95 therefore
resolves to that identity; `composition: proposition`, `hold: None`, subject entity set.
No determiner rule and no enlarged occurrence is needed, and the source-exact `US` occurrence
stays as reviewed.
Regression: `test_contained_identity_resolves_a_determiner_prefixed_subject`.

## Conclusion (narrowed)


The current selection/composition path has **not demonstrated a semantically complete
acceptance case**.
This is a limitation of that path, not a proven limitation of the Domain Core:
`Assertion.object_value` can already carry a complete source phrase.

## Bounded scope revision (accepted direction, implementation open)

### Selected construction: participial object complement

Case `sge_14b44ada5ff18cabf168a42b` from the stored run:

> Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration.

| Element | Value |
|---|---|
| Paragraph node | `nod_da86f9a7f68fd497cb47a88e_0013`, node start 4682 |
| Paragraph digest | `c608ac71f813d95607a005494b5cc90fb949590778631fcec2e34bf09e57327a` |
| Trigger | `published`, 441..450 (label `publish`) |
| Selection | `selected`, realized roles `subject`, `object` |
| Composition | `composed`, no structural hold (verified with a synthetic reference) |
| Subject | `Amodei` (Actor candidate; review required) |
| Object today | `a blog post`, 451..462 |
| Object required | `a blog post rebuffing "inaccurate claims" from the Trump administration` |

### Semantic contract

- Required content: subject, predicate, and the object head **with its participial complement**,
  because the participle states what the post does and carries the claim.
- Omittable: the preceding time adjunct (`That month,`) and neighbouring sentences; the claim is
  unchanged without them.
- Hold when: the complement is not contiguous with the object phrase, when more than one such
  complement attaches to the same object head, or when the complement contains coordination or a
  further clause the current path does not represent.
- Unchanged: identity review, evidence validation, and every other construction.

### Implementation finding (bounded, evidence-backed)

Flipping the shared detached-clause policy is **not** the fix.
Removing bare `acl` from `_DETACHED_CLAUSE_RELATIONS` in
`parser_constituent_candidate_generation` widens every noun-phrase candidate; on the stored parse it
made this Event stop realizing a subject role, so the claim was lost rather than completed.
That change is reverted and parser-constituent tests pass on the reverted tree.

### Explicit composition contract (implementation pending)

The completed object content must reach composition through an explicit input.
Editing `realized_roles[*].canonical_boundary` alone is insufficient: the composer resolves the
selected label back to its candidate in the inventory, so an expanded annotation next to an
unchanged candidate would make selection, composition, and replay disagree.

The increment must satisfy all six conditions.

1. Preserve the existing selection of the object head. The object label and its candidate stay
   exactly as selected; the increment never rewrites a candidate label's meaning.
2. Derive the permitted participial complement from the pinned dependency graph: one `acl`
   dependent of the object head token, whose subtree is contiguous with the object span.
3. Validate the complete span against authoritative source text: exact characters, single
   contiguous range, inside the paragraph, and starting at the selected object head's start.
4. Supply the completed content as an explicit composition input, for example
   `ObjectContentCompletion(event_id, head_range, completed_range, derivation)` carried into
   `compose_event_from_resolution` and applied to the object role only after the same validation.
   A validated expanded candidate selected by its own new label is an acceptable alternative; a
   silent mutation of an existing candidate is not.
5. Use the completed span for packet presentation, Assertion construction, the supporting object
   span, and the statement evidence target, so all four agree.
6. Hold explicitly when the complement is absent, non-contiguous, plural, or contains
   coordination or a further clause.

Required regressions, all built from the stored tokens of
`sge_14b44ada5ff18cabf168a42b`:

- The proposed Assertion's `object_value` equals the exact full phrase
  `a blog post rebuffing "inaccurate claims" from the Trump administration`.
- The pending `Assertion` `ProposedChange` carries the same object phrase.
- The packet's object text, the supporting object span, and the statement evidence text all
  equal that phrase.
- Subject selection is unchanged: subject `Amodei`, same span as before the increment.
- Rejections: non-contiguous complement, two `acl` dependents, coordinated complement, and a
  completed span whose characters do not match the source.
- The retained counterexamples still hold: `sge_8f37b32d221d8974c7725e42` (semantic loss),
  `sge_6054fa9e10adfd8c6ec99d0a` and `sge_fc5ecf8c1d8dfb15a312e0e4` (`unsupported_time_place`).

IRA-01-A stays open until these regressions pass and the case is approved.

## Reproduction

For each paragraph in the run: load its paragraph inputs and token artifact, build the constituent
inventory for the Event, run `select_source_grounded_constituents`, then call
`compose_event_from_resolution` with one synthetic accepted organization reference.
Record the selection status, realized roles, canonical boundaries, and composition hold reason.
No model call is involved.

## Content decision

The reviewer accepted the proposed content as a `source_report` development expectation:
subject the United States government classified as an Organization, predicate `started`, object
`the 2026 Iran war`, affirmed/actual, secondary/direct_document.
Human approval is still recorded through the operator workflow during the live run.
