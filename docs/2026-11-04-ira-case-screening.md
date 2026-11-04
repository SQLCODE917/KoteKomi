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

## Decision required before IRA-01-A can close

1. Extend the Assertion representation so this construction can carry its complement, for example
   the evidence complement that distinguishes `viewed` from `viewed as evidence that`.
   That is a semantic capability change and needs an explicit scope revision.
2. Choose a source whose sentences are complete simple propositions, for example a deposit with
   short declarative sentences, and screen it the same way before approval.

## Reproduction

For each paragraph in the run: load its paragraph inputs and token artifact, build the constituent
inventory for the Event, run `select_source_grounded_constituents`, then call
`compose_event_from_resolution` with one synthetic accepted organization reference.
Record the selection status, realized roles, canonical boundaries, and composition hold reason.
No model call is involved.
