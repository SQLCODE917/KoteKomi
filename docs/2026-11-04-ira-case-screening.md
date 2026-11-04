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
| 2. Confirm the Assertion representation can express it | **Fails for the entire population** |
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

### Next bounded step

Extend the object role's selected boundary after selection, inside the shared Application Layer
path, to absorb a contiguous `acl` subtree of the object head, and rebuild the selected answer's
canonical boundary before composition.
Retain the counterexamples as negative tests: `sge_8f37b32d221d8974c7725e42` (semantic loss),
`sge_6054fa9e10adfd8c6ec99d0a` and `sge_fc5ecf8c1d8dfb15a312e0e4` (`unsupported_time_place`).
IRA-01-A stays open until that construction works and the case is approved.

## Reproduction

For each paragraph in the run: load its paragraph inputs and token artifact, build the constituent
inventory for the Event, run `select_source_grounded_constituents`, then call
`compose_event_from_resolution` with one synthetic accepted organization reference.
Record the selection status, realized roles, canonical boundaries, and composition hold reason.
No model call is involved.
