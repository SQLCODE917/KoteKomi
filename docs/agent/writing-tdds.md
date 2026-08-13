# Writing Technical Design Documents (TDDs)

## File Location

Place TDDs in `docs/`.

Name each TDD with a date and title:

```text
YYYY-MM-DD-meaningful-title.md
```

## Instructions

Read this file in full before writing a TDD, and follow it exactly.

You are writing a Technical Design Document (TDD).
The TDD will be reviewed by a human and then handed to a coding agent for implementation.
Its job is to pin down every decision that crosses a contract boundary, and to stay silent on everything the implementer can decide for itself.

A TDD should be self-contained, meaning that a reader who has not seen any prior conversations must be able to identify the actors, named features, current behavior, missing behavior, etc from the TDD alone.

You are to use language in the style of Simplified Technical English:

- Active voice. The component that acts is the subject of the sentence.
  ("The worker writes claims," not "claims are written.")
- State behavior positively. Say what the system does before what it forbids.
- No gerund/participle chains as nouns.
  Prefer "extract claims" over "the extraction of claims" / "claim extraction processing."
- Noun clusters max 3 words. Break up "source-plan-bound extraction result contract."
- One term per concept, every time — see the glossary below. Never vary a defined term for style.
- Use established product and repository terms when they identify real concepts.
  Define unfamiliar technical terms before using them.
  Do not replace a concrete actor, component, action, input, or observable result with an invented summary label, i.e.
  Bad: User directory boundary.
  Good: Authenticated endpoint backed by Users table.
- Introduce a new term only when it names a real concept required by the design.
  Define the term before use and use it consistently.
  Do not introduce a term merely to summarize several concrete components or actions.
- Each sentence must have one main, testable claim.
  Give it an explicit subject and verb.
  Split independent claims into separate sentences.
- Never shorten sentences by compressing concepts into terse and imprecise noun clusters.
  If you need to shorten sentences, just limit the number of instructions or facts per sentence.

You are to avoid elements of style in your language - what's a virtue in prose is a defect in a TDD.

**Sizing gate (apply BEFORE writing):**

One TDD = one independently shippable and revertable unit of work.
If the architecture diagram would need more than ~6 components, or the doc would need more than 3–4 sequence diagrams, or any diagram cannot be drawn in simple ASCII — the scope is too big or too low-level.
Stop and propose a split into multiple TDDs instead of writing one.

**Narrative Spine Rule**

Always think of a design as 3 levels:

1. User outcome, i.e.

   A user enters recipient emails and sees which accounts can receive the command.

2. System boundaries, i.e.

   The shared Recipient component calls the directory endpoint.
   The endpoint uses the directory service.
   The service reads the Users table.
   Each modal user of the Recipient component then calls its existing command API.

3. Contracts and edge cases, i.e.

   Canonicalization, limits, inactive accounts, response order, retries, idempotency, and race conditions.

Once you grouped concerns into the 3 levels, organize the TDD from outcome to ownership to contract to verification, i.e.

First explain what the user does and what is missing.
Then identify which component owns each responsibility.
Then specify cross-boundary contracts and edge cases.
Finally define acceptance tests for those contracts.

**TDD Planning/Drafting sequence**

1. Write the user action and expected outcome.
2. State the current behavior and its observable limitation.
3. Describe the Primary end-to-end Flow - 3~6 numbered steps from user action to visible result.
4. Identify the components that own each step.
5. Define only the terms needed to distinguish those components or data.
6. Specify boundary contracts and edge cases.
7. Derive acceptance criteria from those contracts.
8. Remove details that do not reject an alternative implementation.

**Structure (use these sections, in order):**

- Give the TDD a deliberate descent:

```
User outcome
  -> primary flow
    -> component ownership
      -> boundary requirements
        -> contracts and edge cases
          -> evidence
```

1. **Context & Problem** — why this change exists.

- After reading Context & Problem and Proposed Architecture, a reader must be able to describe the primary end-to-end flow without reading the API, data model, or acceptance criteria sections.
- Put the Primary end-to-end Flow here.
- Mark unimplemented behavior explicitly with terms such as "planned," "does not yet," or "will." Do not describe planned behavior as existing behavior.

2. **Goals** — the results that users and operators will observe.

- Goals are visible outcomes, not implementation details: they do not name routes, components, tables, indexes, protocols, etc.

- Bulleted, observable, measurable.

3. **Requirements** — what each boundary must do, grouped by boundary.

- Each requirement has to have one owner, i.e. browser, network, database, etc.
- Each requirement must be unambiguous (one possible reading) and verifiable (a finite check could confirm it).

4. **Proposed Architecture** — which component owns each responsibility.

- To support the description in prose, add a C4 Container-level diagram in plain ASCII.

5. **Key Interactions** — the order of the main user and system actions.

- Add one primary sequence diagram.
- You may add an additional sequence diagram only when a separate boundary or failure rule needs it.

6. **Data Model** — stored records and access patterns only.

- Schema sketches are fine; full DDL is not.
- Clearly state what already exists and what will need to be created.

7. **APIs / Interfaces** — cross-boundary contracts only.

- No request/response schemas or signatures UNLESS the type itself is a contract decision — i.e. if the implementer chose a different shape, the PR would be rejected.

8. **Behavior & Domain Rules** — state changes and edge cases over time.

9. **Acceptance Criteria** — verification gates mapped to requirements.

10. **Reference Implementations** — pointers to existing files/modules in the repo whose patterns the implementer should imitate, one line each (e.g. "error handling: follow src/handlers/x.ts").

11. **Constraints and Halt Conditions** - OPTIONAL

- Any unresolved decisions
- Any implementations that appear natural to an implementing agent, but would otherwise trap it in a wrong implementation

Any fact appears first in the section that owns it's question.
Later sections reference that fact by a requiremnet identifier, instead of restating it, i.e:

- in Requirements, owned by the "Directory Endpoint":

```
- DE-01: The endpoint accepts one through twenty email strings.
- DE-02: The endpoint preserves request order.
```

- in Acceptance Criteria, they become traceable without re-explaining:

```
- AC-DE-01: Route tests prove one, twenty, and twenty-one email inputs.
- AC-DE-02: Route tests prove response order matches request order.
```

**Style constraints:**

- Avoid the `Elegant variation` antipattern:
  Use one token per concept and use it identically every time.
  Do not give the same concept many names, and one name for many concepts:
  "final wiki placement" / "final pages" / "page metadata" / PageMetadata / "planned target page metadata" / "target page metadata" / "planned page metadata" / "planned target page."
  Likewise "route hint" appears as "route hints," "legacy route hints," "metadata-only hint," "route rationale," and "source-plan route rationale."
  Each rename forces the reviewer to decide is this a new thing or the same thing?
- Follow the `No undefined terms` rule:
  Define terms before use in a glossary in the **Context & Problem** section.
- Avoid the `Stacked negation` antipattern: do not negate already negative concepts:
  "Do not publish unsupported claims as supported"
  "Tests prove no extraction output contains final page paths as authority."
- Stop `Specification by prohibition` abuse:
  Describe what it is, do not describe what it isn't.
- Avid `Weak words and uncalibrated modals` antipattern:
  "Relevant page contracts" (relevant by what test?).
  "source span when available" (available when? decided by whom?)
  "may show summarized gaps" (must|can|may|cannot are used colloquially)
  Each require interpretation and must be banned as "weak phrases" that punt a hidden decision to the reader.
- Avoid `Nominalization and hidden actors` antipattern:
  No abstract nouns doing actions: "Extraction," "Projection," "synthesis," "placement," "ingestion," "coverage claims" - unqualified, these are "zombie nouns" and oppose the rule that characters should be subjects and actions should be verbs.
  When combined with the agentless passive ("output must be accepted only through a schema-validated artifact" — accepted by what?), the reviewer cannot answer the basic spec question: which component is responsible for which behavior.
  Compound-noun pile-ups make it worse: "extraction target set," "schema-validated artifact named extraction-results.json scoped to source plan id."
- Avoid `Redundancy across sections` antipattern:
  "Do not run source-plan-bound extraction in Zarya" (§3), "must not read raw extraction artifacts or serve extracted claims as pages" (§6), "Halt if Zarya must execute extraction for ingestion to proceed" (§15).
  The evidence-for-supported-claims rule and the no-unauthorized-paths rule each appear in Goals, Requirements, Invariants, Behavior Rules, and Acceptance Criteria.
  Because the restatements drift in wording, the reviewer can't tell whether §11 is derived from §4 or adds new constraints, so they must diff five sections against each other. That cross-checking is pure extraneous load.
- Avoid the `non-parallel enumerations` antipattern:
  "ExtractionGap records missing evidence, unsupported hints, ambiguous variants, and out-of-scope material" — four items at four different levels of abstraction (an absence, a hint type, a variant, a material category).
  The reader hunts for the organizing principle and finds none, which is its own small tax repeated throughout the lists.
- All diagrams are plain ASCII.
  If something can't be expressed in a simple ASCII diagram, it is too low-level for this document — omit it or escalate via the sizing gate.
- No pseudocode, no implementation snippets, no function signatures — except public contract types per section 9.
- State technology choices as decisions, not arguments.
  "Uses DynamoDB" — not three paragraphs comparing it to Postgres.
  If a choice needs justification, write a one-line ADR pointer.
- Soft cap: ~300 lines.
- Soft line cap: ~100 character per line
- Hard rule: One sentence per line.
- Write for an engineer who already knows the stack.
  Don't explain what GitHub Actions or DynamoDB is.
- Prefer prose for design rationale; bullets for enumerable lists.
- Editing pass before finishing: delete any sentence describing HOW to build something rather than WHAT must be true.
  The test for inclusion: "if the implementer decided this differently, would the PR be rejected?"
  If no, cut it.

