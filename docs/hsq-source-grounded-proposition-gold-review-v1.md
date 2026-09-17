# Source-Grounded Proposition Scope Gold Review

Review status: `approved`

## Review contract

Gold records the source meaning required at this boundary, not the current model's convenience, a final knowledge graph, or unqualified world truth.

KoteKomi supplies the authoritative SourceSegment, one exact Event expression, and one exact Fragment Candidate.

Stanza supplies tokenization, part-of-speech, lemma, and dependency evidence; it does not decide semantic truth, proposition scope, or chronology.

QANom proposes whether a noun is eventive; it does not decide participants, time, truth, or proposition scope.

GLiNER proposes entity spans and type hints, ReFinED proposes external identity, and F-Coref proposes antecedent links; none of them decides proposition scope.

Qwen2.5 receives the complete SourceSegment, one marked Event expression, and one marked Fragment Candidate, then answers only `Y`, `N`, or `U` about semantic membership.

Qwen2.5 does not construct KoteKomi identifiers, source offsets, Domain Core records, semantic roles, Event-to-Event edges, or a timeline.

KoteKomi validates source characters, maps each answer to its supplied candidate, constructs records, and preserves data-in/data-out traces.

Human review defines Gold and authorizes any later accepted Ledger state.

A candidate-generation gap and a semantic-judgment error are different failures and must remain separately measurable.

Gold can require an exact fragment-membership decision only when deterministic candidates can represent that fragment.

Gold does not require normalized semantic roles, Event-to-Event edges, external world knowledge, or temporal ordering beyond this experiment's boundary.

A temporal phrase belongs to an Event proposition only when the SourceSegment's grammar binds that phrase to the Event.

Nested Event mentions remain distinct: an outer Event can include a nested Event expression without proving a date, role, or independent occurrence that the Source does not establish.

## TGE-002 — development

Exact SourceSegment:

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. 

Expected meaning: In January 2025, Dario Amodei criticized Stargate.

Required exact fragments:

- `In January 2025,` — temporal — `PGF-TGE-002-01`
- `Anthropic CEO Dario Amodei` — core_event — `PGF-TGE-002-02`
- `criticized` — core_event — `PGF-TGE-002-03`
- `the artificial intelligence investment project Stargate` — core_event — `PGF-TGE-002-04`
- `as "chaotic"` — core_event — `PGF-TGE-002-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-003 — development

Exact SourceSegment:

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. 

Expected meaning: In January 2025, Anthropic CEO Dario Amodei opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence.

Required exact fragments:

- `In January 2025,` — temporal — `PGF-TGE-003-01`
- `Anthropic CEO Dario Amodei` — core_event — `PGF-TGE-003-02`
- `opposed` — core_event — `PGF-TGE-003-03`
- `Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence` — core_event — `PGF-TGE-003-04`

Review rationale: The proposition preserves the opposition time, complete Actor expression, Event expression, and exact nested target. It excludes the coordinated Stargate criticism and later discussion proposition. The temporal phrase dates the opposition, not the nested rescission or Executive Order issuance.

## TGE-004 — development

Exact SourceSegment:

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. 

Expected meaning: The Source refers to Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence.

Required exact fragments:

- `Trump's` — core_event — `PGF-TGE-004-01`
- `rescission` — core_event — `PGF-TGE-004-02`
- `of president Joe Biden's Executive Order on Artificial Intelligence` — core_event — `PGF-TGE-004-03`

Review rationale: The proposition preserves the source-grounded nominal rescission mention and its exact possessive and object phrases. It does not import January 2025 into the nested rescission or assign semantic roles, Event-to-Event edges, or an Executive Order issuance date.

## TGE-005 — development

Exact SourceSegment:

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. 

Expected meaning: In January 2025, Dario Amodei noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.

Required exact fragments:

- `In January 2025,` — temporal — `PGF-TGE-005-01`
- `Anthropic CEO Dario Amodei` — core_event — `PGF-TGE-005-02`
- `noted` — attribution, core_event — `PGF-TGE-005-03`
- `that Anthropic had held discussions with Trump officials about artificial intelligence policy` — attribution, core_event — `PGF-TGE-005-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-006 — development

Exact SourceSegment:

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. 

Expected meaning: Anthropic had held discussions with Trump officials about artificial intelligence policy.

Required exact fragments:

- `Anthropic CEO Dario Amodei` — attribution — `PGF-TGE-006-01`
- `noted` — attribution — `PGF-TGE-006-02`
- `that` — attribution — `PGF-TGE-006-03`
- `Anthropic` — core_event — `PGF-TGE-006-04`
- `had` — core_event — `PGF-TGE-006-05`
- `held` — core_event — `PGF-TGE-006-06`
- `discussions` — core_event — `PGF-TGE-006-07`
- `with Trump officials` — core_event — `PGF-TGE-006-08`
- `about artificial intelligence policy` — core_event — `PGF-TGE-006-09`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-014 — development

Exact SourceSegment:

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  

Expected meaning: The Trump administration targeted law firms as Amodei cut ties with two of them.

Required exact fragments:

- `As` — temporal — `PGF-TGE-014-01`
- `the Trump administration` — core_event — `PGF-TGE-014-02`
- `targeted` — core_event — `PGF-TGE-014-03`
- `law firms` — core_event — `PGF-TGE-014-04`
- `Amodei` — core_event — `PGF-TGE-014-05`
- `cut` — core_event — `PGF-TGE-014-06`
- `ties` — core_event — `PGF-TGE-014-07`
- `with the firms` — core_event — `PGF-TGE-014-08`
- `Skadden, Arps, Slate, Meagher & Flom` — core_event — `PGF-TGE-014-09`
- `and` — core_event — `PGF-TGE-014-10`
- `Latham & Watkins` — core_event — `PGF-TGE-014-11`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-015 — development

Exact SourceSegment:

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  

Expected meaning: Amodei cut ties with two law firms as the Trump administration targeted law firms.

Required exact fragments:

- `As the Trump administration targeted law firms,` — core_event, temporal — `PGF-TGE-015-01`
- `Amodei` — core_event — `PGF-TGE-015-02`
- `cut` — core_event — `PGF-TGE-015-03`
- `ties` — core_event — `PGF-TGE-015-04`
- `with the firms` — core_event — `PGF-TGE-015-05`
- `Skadden, Arps, Slate, Meagher & Flom` — core_event — `PGF-TGE-015-06`
- `and` — core_event — `PGF-TGE-015-07`
- `Latham & Watkins` — core_event — `PGF-TGE-015-08`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-016 — development

Exact SourceSegment:

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  

Expected meaning: The law firms reached agreements with the Trump administration.

Required exact fragments:

- `Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins` — core_event — `PGF-TGE-016-01`
- `which` — core_event — `PGF-TGE-016-02`
- `reached` — core_event — `PGF-TGE-016-03`
- `agreements` — core_event — `PGF-TGE-016-04`
- `with  the  Trump  administration` — core_event — `PGF-TGE-016-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-017 — development

Exact SourceSegment:

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  

Expected meaning: The law firms intended to avoid punishment.

Required exact fragments:

- `Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins` — core_event — `PGF-TGE-017-01`
- `which` — core_event — `PGF-TGE-017-02`
- `reached` — core_event — `PGF-TGE-017-03`
- `agreements with  the  Trump  administration` — core_event — `PGF-TGE-017-04`
- `to` — purpose — `PGF-TGE-017-05`
- `avoid` — core_event, purpose — `PGF-TGE-017-06`
- `punishment` — core_event, purpose — `PGF-TGE-017-07`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-018 — development

Exact SourceSegment:

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda. 

Expected meaning: Sacks viewed several matters as evidence.

Required exact fragments:

- `Sacks` — core_event — `PGF-TGE-018-01`
- `viewed` — core_event — `PGF-TGE-018-02`
- `Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda` — comparison, core_event, modality, negation — `PGF-TGE-018-03`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-019 — development

Exact SourceSegment:

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda. 

Expected meaning: Amodei decided to attend the World Economic Forum instead of Trump's second inauguration.

Required exact fragments:

- `Amodei's` — core_event — `PGF-TGE-019-01`
- `decision to attend the World Economic Forum over Trump's second inauguration` — comparison, core_event — `PGF-TGE-019-02`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-022 — development

Exact SourceSegment:

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda. 

Expected meaning: Amodei hired Biden officials.

Required exact fragments:

- `his` — core_event — `PGF-TGE-022-01`
- `hiring` — core_event — `PGF-TGE-022-02`
- `of  Biden  officials` — core_event — `PGF-TGE-022-03`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-023 — development

Exact SourceSegment:

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda. 

Expected meaning: Sacks assessed that Anthropic would not support Trump's agenda.

Required exact fragments:

- `Sacks` — attribution — `PGF-TGE-023-01`
- `viewed` — attribution — `PGF-TGE-023-02`
- `as` — attribution — `PGF-TGE-023-03`
- `evidence` — attribution — `PGF-TGE-023-04`
- `that` — attribution — `PGF-TGE-023-05`
- `Anthropic` — core_event — `PGF-TGE-023-06`
- `would` — modality — `PGF-TGE-023-07`
- `not` — negation — `PGF-TGE-023-08`
- `support` — core_event — `PGF-TGE-023-09`
- `Trump's agenda` — core_event — `PGF-TGE-023-10`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-025 — development

Exact SourceSegment:

> [15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic's  policies,  intensifying  the  dispute.  

Expected meaning: In October 2025, Sacks stated that Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering."

Required exact fragments:

- `In October 2025,` — temporal — `PGF-TGE-025-01`
- `Sacks` — attribution — `PGF-TGE-025-02`
- `stated` — attribution — `PGF-TGE-025-03`
- `that` — attribution — `PGF-TGE-025-04`
- `Anthropic` — core_event — `PGF-TGE-025-05`
- `was` — core_event — `PGF-TGE-025-06`
- `running` — core_event — `PGF-TGE-025-07`
- `a sophisticated regulatory capture strategy` — core_event — `PGF-TGE-025-08`
- `based on fearmongering` — core_event — `PGF-TGE-025-09`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-026 — development

Exact SourceSegment:

> [15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic's  policies,  intensifying  the  dispute.  

Expected meaning: That month, Amodei published a blog post.

Required exact fragments:

- `That month,` — temporal — `PGF-TGE-026-01`
- `Amodei` — core_event — `PGF-TGE-026-02`
- `published` — core_event — `PGF-TGE-026-03`
- `a blog post` — core_event — `PGF-TGE-026-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-027 — development

Exact SourceSegment:

> [15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic's  policies,  intensifying  the  dispute.  

Expected meaning: That month, the blog post rebuffed claims from the Trump administration.

Required exact fragments:

- `That month,` — temporal — `PGF-TGE-027-01`
- `Amodei` — core_event — `PGF-TGE-027-02`
- `published` — core_event — `PGF-TGE-027-03`
- `a` — core_event — `PGF-TGE-027-04`
- `blog` — core_event — `PGF-TGE-027-05`
- `post` — core_event — `PGF-TGE-027-06`
- `rebuffing` — core_event — `PGF-TGE-027-07`
- `"inaccurate claims"` — core_event — `PGF-TGE-027-08`
- `from the Trump administration` — core_event — `PGF-TGE-027-09`
- `on  Anthropic's  policies` — core_event — `PGF-TGE-027-10`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-028 — development

Exact SourceSegment:

> [15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic's  policies,  intensifying  the  dispute.  

Expected meaning: That month, the publication intensified the dispute.

Required exact fragments:

- `That month,` — temporal — `PGF-TGE-028-01`
- `Amodei` — core_event — `PGF-TGE-028-02`
- `published` — core_event — `PGF-TGE-028-03`
- `a` — core_event — `PGF-TGE-028-04`
- `blog` — core_event — `PGF-TGE-028-05`
- `post` — core_event — `PGF-TGE-028-06`
- `rebuffing` — core_event — `PGF-TGE-028-07`
- `"inaccurate claims"` — core_event — `PGF-TGE-028-08`
- `from the Trump administration` — core_event — `PGF-TGE-028-09`
- `on  Anthropic's  policies` — core_event — `PGF-TGE-028-10`
- `intensifying` — core_event — `PGF-TGE-028-11`
- `the  dispute` — core_event — `PGF-TGE-028-12`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-054 — development

Exact SourceSegment:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. 

Expected meaning: By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services.

Required exact fragments:

- `By November 2024,` — temporal — `PGF-TGE-054-01`
- `Anthropic` — core_event — `PGF-TGE-054-02`
- `had` — core_event — `PGF-TGE-054-03`
- `already` — temporal — `PGF-TGE-054-04`
- `partnered` — core_event — `PGF-TGE-054-05`
- `with` — core_event — `PGF-TGE-054-06`
- `Palantir` — core_event — `PGF-TGE-054-07`
- `and` — core_event — `PGF-TGE-054-08`
- `Amazon Web Services` — core_event — `PGF-TGE-054-09`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-055 — development

Exact SourceSegment:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. 

Expected meaning: Palantir and Amazon Web Services offered services with FedRAMP authorization.

Required exact fragments:

- `Palantir` — core_event — `PGF-TGE-055-01`
- `and Amazon Web Services` — core_event — `PGF-TGE-055-02`
- `companies` — core_event — `PGF-TGE-055-03`
- `that` — core_event — `PGF-TGE-055-04`
- `offered` — core_event — `PGF-TGE-055-05`
- `services` — core_event — `PGF-TGE-055-06`
- `with FedRAMP authorization` — core_event — `PGF-TGE-055-07`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-078 — development

Exact SourceSegment:

> [26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the  department threatened to cancel its contracts with the company. 

Expected meaning: After Anthropic refused to allow the Department of Defense to use Claude for "all lawful purposes", the Department of Defense threatened to cancel its contracts with Anthropic.

Required exact fragments:

- `After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes",` — core_event, temporal — `PGF-TGE-078-01`
- `the  department` — core_event — `PGF-TGE-078-02`
- `threatened` — core_event — `PGF-TGE-078-03`
- `to cancel its contracts with the company` — core_event, modality — `PGF-TGE-078-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-001 — validation

Exact SourceSegment:

> Hegseth, the United States secretary of defense, has publicly rebuked Anthropic chief executive Dario Amodei's approach to artificial intelligence.

Expected meaning: Hegseth has publicly rebuked Dario Amodei's approach.

Required exact fragments:

- `Hegseth, the United States secretary of defense,` — core_event — `PGF-TGE-001-01`
- `has` — core_event — `PGF-TGE-001-02`
- `publicly` — core_event — `PGF-TGE-001-03`
- `rebuked` — core_event — `PGF-TGE-001-04`
- `Anthropic chief executive Dario Amodei's approach to artificial intelligence` — core_event — `PGF-TGE-001-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-007 — validation

Exact SourceSegment:

> [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". 

Expected meaning: The following month, Amodei wrote an op-ed in The New York Times.

Required exact fragments:

- `The following month,` — temporal — `PGF-TGE-007-01`
- `Amodei` — core_event — `PGF-TGE-007-02`
- `wrote` — core_event — `PGF-TGE-007-03`
- `an op-ed` — core_event — `PGF-TGE-007-04`
- `in The New York Times` — core_event — `PGF-TGE-007-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-008 — validation

Exact SourceSegment:

> [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". 

Expected meaning: In the op-ed written the following month, Amodei described the artificial intelligence regulation bill.

Required exact fragments:

- `The following month,` — temporal — `PGF-TGE-008-01`
- `Amodei` — attribution — `PGF-TGE-008-02`
- `wrote` — attribution — `PGF-TGE-008-03`
- `an op-ed` — attribution — `PGF-TGE-008-04`
- `in The New York Times` — attribution — `PGF-TGE-008-05`
- `describing` — core_event — `PGF-TGE-008-06`
- `the  artificial  intelligence  regulation bill` — core_event — `PGF-TGE-008-07`
- `as "far too blunt an instrument"` — core_event — `PGF-TGE-008-08`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-009 — validation

Exact SourceSegment:

> [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". 

Expected meaning: The regulation bill was then tied to the One Big Beautiful Bill Act.

Required exact fragments:

- `the` — core_event — `PGF-TGE-009-01`
- `artificial` — core_event — `PGF-TGE-009-02`
- `intelligence  regulation` — core_event — `PGF-TGE-009-03`
- `bill` — core_event — `PGF-TGE-009-04`
- `then` — temporal — `PGF-TGE-009-05`
- `tied` — core_event — `PGF-TGE-009-06`
- `to the One Big Beautiful Bill Act` — core_event — `PGF-TGE-009-07`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-011 — validation

Exact SourceSegment:

> Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord". 

Expected meaning: In a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for Kamala Harris over Trump.

Required exact fragments:

- `in a Facebook post ahead of the 2024 presidential election,` — temporal — `PGF-TGE-011-01`
- `Amodei` — core_event — `PGF-TGE-011-02`
- `urged` — core_event — `PGF-TGE-011-03`
- `his associates` — core_event — `PGF-TGE-011-04`
- `to vote for vice president Kamala Harris over Trump` — comparison, core_event — `PGF-TGE-011-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-013 — validation

Exact SourceSegment:

> Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord". 

Expected meaning: In a Facebook post ahead of the 2024 presidential election, Amodei described Trump as a feudal warlord.

Required exact fragments:

- `in a Facebook post ahead of the 2024 presidential election,` — temporal — `PGF-TGE-013-01`
- `Amodei` — core_event — `PGF-TGE-013-02`
- `describing` — core_event — `PGF-TGE-013-03`
- `him` — core_event — `PGF-TGE-013-04`
- `as a "feudal warlord"` — core_event — `PGF-TGE-013-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-030 — validation

Exact SourceSegment:

> Amodei's  statement  included  views explicitly espoused by vice president JD Vance. 

Expected meaning: Amodei's statement included views that JD Vance had explicitly espoused.

Required exact fragments:

- `Amodei's  statement` — core_event — `PGF-TGE-030-01`
- `included` — core_event — `PGF-TGE-030-02`
- `views explicitly espoused by vice president JD Vance` — core_event — `PGF-TGE-030-03`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-038 — validation

Exact SourceSegment:

> [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. 

Expected meaning: That month, Amodei criticized Trump's approach to export restrictions on semiconductors.

Required exact fragments:

- `That month,` — temporal — `PGF-TGE-038-01`
- `Amodei` — core_event — `PGF-TGE-038-02`
- `criticized` — core_event — `PGF-TGE-038-03`
- `Trump's approach to export restrictions on semiconductors` — core_event — `PGF-TGE-038-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-039 — validation

Exact SourceSegment:

> [17]  In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration. 

Expected meaning: In December, Amodei met Trump officials and senators.

Required exact fragments:

- `In December,` — temporal — `PGF-TGE-039-01`
- `Amodei` — core_event — `PGF-TGE-039-02`
- `met` — core_event — `PGF-TGE-039-03`
- `with Trump officials and several senators` — core_event — `PGF-TGE-039-04`
- `in an effort to improve Anthropic's relationship with the Trump administration` — purpose — `PGF-TGE-039-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-040 — validation

Exact SourceSegment:

> [17]  In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration. 

Expected meaning: In December, Amodei sought to improve Anthropic's relationship with the administration.

Required exact fragments:

- `In December,` — temporal — `PGF-TGE-040-01`
- `Amodei` — core_event — `PGF-TGE-040-02`
- `met` — core_event — `PGF-TGE-040-03`
- `with Trump officials and several senators` — core_event — `PGF-TGE-040-04`
- `in` — purpose — `PGF-TGE-040-05`
- `an` — purpose — `PGF-TGE-040-06`
- `effort` — purpose — `PGF-TGE-040-07`
- `to` — modality, purpose — `PGF-TGE-040-08`
- `improve` — core_event, modality, purpose — `PGF-TGE-040-09`
- `Anthropic's relationship with the Trump administration` — core_event — `PGF-TGE-040-10`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-041 — validation

Exact SourceSegment:

> Since  January  2026,  the  United  States  Department  of  Defense  has  conflicted  with  the  artificial intelligence  company Anthropic  over  the  use  of  its  products  for  military  purposes  and  mass  domestic surveillance.

Expected meaning: Since January 2026, the United States Department of Defense and Anthropic have conflicted over the use of Anthropic's products for military purposes and mass domestic surveillance.

Required exact fragments:

- `Since  January  2026,` — temporal — `PGF-TGE-041-01`
- `the  United  States  Department  of  Defense` — core_event — `PGF-TGE-041-02`
- `has` — core_event — `PGF-TGE-041-03`
- `conflicted` — core_event — `PGF-TGE-041-04`
- `with  the  artificial intelligence  company Anthropic` — core_event — `PGF-TGE-041-05`
- `over  the  use  of  its  products  for  military  purposes  and  mass  domestic surveillance` — core_event — `PGF-TGE-041-06`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-051 — validation

Exact SourceSegment:

> According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. 

Expected meaning: Trump officials chastised Anthropic's hiring.

Required exact fragments:

- `According  to Semafor ,` — attribution — `PGF-TGE-051-01`
- `Trump  officials` — core_event — `PGF-TGE-051-02`
- `chastised` — core_event — `PGF-TGE-051-03`
- `Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence` — core_event — `PGF-TGE-051-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-052 — validation

Exact SourceSegment:

> According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. 

Expected meaning: Anthropic hired several Biden administration officials.

Required exact fragments:

- `According  to Semafor ,` — attribution — `PGF-TGE-052-01`
- `Trump  officials` — attribution — `PGF-TGE-052-02`
- `chastised` — attribution — `PGF-TGE-052-03`
- `Anthropic's` — core_event — `PGF-TGE-052-04`
- `hiring` — core_event — `PGF-TGE-052-05`
- `of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence` — core_event — `PGF-TGE-052-06`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-053 — validation

Exact SourceSegment:

> Prior to the dispute, the Trump administration had integrated Anthropic's services. 

Expected meaning: Prior to the dispute, the Trump administration had integrated Anthropic's services.

Required exact fragments:

- `Prior to the dispute,` — temporal — `PGF-TGE-053-01`
- `the Trump administration` — core_event — `PGF-TGE-053-02`
- `had` — core_event — `PGF-TGE-053-03`
- `integrated` — core_event — `PGF-TGE-053-04`
- `Anthropic's services` — core_event — `PGF-TGE-053-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-056 — validation

Exact SourceSegment:

> In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. 

Expected meaning: In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute.

Required exact fragments:

- `In the Biden administration,` — temporal — `PGF-TGE-056-01`
- `Anthropic` — core_event — `PGF-TGE-056-02`
- `had` — core_event — `PGF-TGE-056-03`
- `reached` — core_event — `PGF-TGE-056-04`
- `an` — core_event — `PGF-TGE-056-05`
- `agreement` — core_event — `PGF-TGE-056-06`
- `with the AI Safety Institute` — core_event — `PGF-TGE-056-07`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-057 — validation

Exact SourceSegment:

> In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. 

Expected meaning: In the Biden administration, Anthropic had participated in a nuclear information safety evaluation.

Required exact fragments:

- `In the Biden administration,` — temporal — `PGF-TGE-057-01`
- `Anthropic` — core_event — `PGF-TGE-057-02`
- `had` — core_event — `PGF-TGE-057-03`
- `participated` — core_event — `PGF-TGE-057-04`
- `in a nuclear information safety evaluation` — core_event — `PGF-TGE-057-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-060 — validation

Exact SourceSegment:

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. 

Expected meaning: The following month, Anthropic announced that it would allow national security customers to use Claude Gov.

Required exact fragments:

- `The following month,` — temporal — `PGF-TGE-060-01`
- `Anthropic` — attribution, core_event — `PGF-TGE-060-02`
- `announced` — attribution, core_event — `PGF-TGE-060-03`
- `that it would allow national security customers to use Claude Gov.` — core_event, modality — `PGF-TGE-060-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-064 — validation

Exact SourceSegment:

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. 

Expected meaning: By September, Anthropic's usage policy led to a conflict between Anthropic and the Trump administration.

Required exact fragments:

- `Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement` — core_event — `PGF-TGE-064-01`
- `led` — core_event — `PGF-TGE-064-02`
- `to a conflict between Anthropic and the Trump administration by September` — core_event, temporal — `PGF-TGE-064-03`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-069 — validation

Exact SourceSegment:

> [22] According  to  Reuters,  Anthropic  representatives  opposed  the  use  of  the  company's  products  for surveillance  or  to  develop  lethal  autonomous  weapons. 

Expected meaning: According to Reuters, Anthropic representatives opposed using Anthropic's products for surveillance or to develop lethal autonomous weapons.

Required exact fragments:

- `According  to  Reuters,` — attribution — `PGF-TGE-069-01`
- `Anthropic  representatives` — core_event — `PGF-TGE-069-02`
- `opposed` — core_event — `PGF-TGE-069-03`
- `the  use  of  the  company's  products  for surveillance` — core_event — `PGF-TGE-069-04`
- `or  to  develop  lethal  autonomous  weapons` — core_event — `PGF-TGE-069-05`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.

## TGE-085 — validation

Exact SourceSegment:

> In  April  2026,  the  Court  of  Appeals  for  the  D.C. Circuit in a per curiam order denied  Anthropic's motion to  lift  the  FASCSA  designation. 

Expected meaning: In April 2026, the Court of Appeals for the D.C. Circuit denied Anthropic's motion to lift the FASCSA designation.

Required exact fragments:

- `In  April  2026,` — temporal — `PGF-TGE-085-01`
- `the  Court  of  Appeals  for  the  D.C. Circuit in a per curiam order` — core_event — `PGF-TGE-085-02`
- `denied` — core_event, negation — `PGF-TGE-085-03`
- `Anthropic's motion to  lift  the  FASCSA  designation` — core_event — `PGF-TGE-085-04`

Review rationale: The reviewed fragments preserve this Event's exact participants, predicate, complements, and applicable qualifications while excluding neighboring propositions and citation markers.
