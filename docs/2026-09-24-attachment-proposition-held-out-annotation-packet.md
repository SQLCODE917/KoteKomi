# Attachment Proposition Held-Out Annotation Packet

- Status: Human-reviewed
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Catalog purpose: fresh held-out partition for the deterministic dependency-path attachment router (R1/R5)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_e84869f6fcd4ed02c70a550a`
- Source segment policy: `paragraph_segment_v3`
- Annotation status: `human_reviewed_held_out_gold`
- Development overlap count: `0`
- Excluded from held-out (development overlap): the lede sentence "Hegseth, the United States secretary of defense, has publicly rebuked Anthropic chief executive Dario Amodei's approach to artificial intelligence." already appears as `TGE-001` (validation) in `docs/hsq-source-grounded-proposition-gold-v1.json`, so it is omitted to keep `development_overlap_count` at zero.

## Annotation instructions

Each Event is one sentence-bound proposal over one V3 Source Segment of the authoritative Docling representation text.

Narrow or split the proposed fragment so it preserves the Event's complete meaning without importing a neighboring proposition or a citation marker.

Edit the meaning, fragment, requirements, and rationale in place; then re-run `scripts/prepare_attachment_proposition_held_out_gold.py --check` to confirm the Gold catalog reproduces.

## AHE-001

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0003`
- Section path: `Anthropic-United States Department of Defense dispute`
- Source segment label: `s1`
- Event meaning: `Since January 2026, the United States Department of Defense has conflicted with the artificial intelligence company Anthropic over the use of its products for military purposes and mass domestic surveillance.`
- Requirements: `core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Since  January  2026,  the  United  States  Department  of  Defense  has  conflicted  with  the  artificial intelligence  company Anthropic  over  the  use  of  its  products  for  military  purposes  and  mass  domestic surveillance.
```

### Proposed fragment

```text
Since January 2026, the United States Department of Defense has conflicted with the artificial intelligence company Anthropic over the use of its products for military purposes and mass domestic surveillance.
```


## AHE-002

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0008`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Artificial intelligence in the U.S. military`
- Source segment label: `s1`
- Event meaning: `The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.`
- Requirements: `core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan  administration. 
```

### Proposed fragment

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.
```


## AHE-003

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0008`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Artificial intelligence in the U.S. military`
- Source segment label: `s2`
- Event meaning: `The Department of Defense established a policy on the use of artificial intelligence in 2012, Directive 3000.09.`
- Requirements: `core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[1] The  Department  of  Defense  established  a  policy  on  the  use  of  artificial intelligence  in  2012,  Directive  3000.09. 
```

### Proposed fragment

```text
The Department of Defense established a policy on the use of artificial intelligence in 2012, Directive 3000.09.
```


## AHE-004

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0008`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Artificial intelligence in the U.S. military`
- Source segment label: `s3`
- Event meaning: `Efforts to utilize artificial intelligence intensified under the term of Secretary Ash Carter.`
- Requirements: `core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[2] Efforts  to  utilize  artificial  intelligence  intensified  under  the term  of  Secretary Ash  Carter. 
```

### Proposed fragment

```text
Efforts to utilize artificial intelligence intensified under the term of Secretary Ash Carter.
```


## AHE-005

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0008`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Artificial intelligence in the U.S. military`
- Source segment label: `s4`
- Event meaning: `The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.`
- Requirements: `core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[3] The  Department  of  Defense's  use  of  artificial  intelligence  for  Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations. 
```

### Proposed fragment

```text
The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.
```


## AHE-006

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0010`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s1`
- Event meaning: `In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives.`
- Requirements: `core_event, negation, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives. 
```

### Proposed fragment

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives.
```


## AHE-007

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0010`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s2`
- Event meaning: `In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as 'chaotic'.`
- Requirements: `core_event, temporal`
- Review rationale: `Split during review: also 'opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence' and 'noted that Anthropic had held discussions with Trump officials'.`

### Authoritative source text

```text
In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. 
```

### Proposed fragment

```text
In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.
```


## AHE-008

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0010`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s3`
- Event meaning: `Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence.`
- Requirements: `core_event, negation`
- Review rationale: `Split during review: also 'expressed opposition to an artificial intelligence agreement signed among Gulf states'. Strip the leading citation marker.`

### Authoritative source text

```text
[5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East  in  May.  
```

### Proposed fragment

```text
Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.
```


## AHE-009

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0010`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s4`
- Event meaning: `According to Semafor, Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration.`
- Requirements: `attribution, core_event`
- Review rationale: `Split/name the hired officials during review.`

### Authoritative source text

```text
According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. 
```

### Proposed fragment

```text
According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.
```


## AHE-010

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0010`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s5`
- Event meaning: `The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill as 'far too blunt an instrument'.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". 
```

### Proposed fragment

```text
The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument".
```


## AHE-011

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s1`
- Event meaning: `Prior to the dispute, the Trump administration had integrated Anthropic's services.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services. 
```

### Proposed fragment

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services.
```


## AHE-012

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s2`
- Event meaning: `By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services.`
- Requirements: `core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. 
```

### Proposed fragment

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```


## AHE-013

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s3`
- Event meaning: `In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.`
- Requirements: `core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. 
```

### Proposed fragment

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.
```


## AHE-014

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s4`
- Event meaning: `The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.`
- Requirements: `core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. 
```

### Proposed fragment

```text
The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.
```


## AHE-015

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s5`
- Event meaning: `Through its interoperability with Palantir, Anthropic's technology achieved relatively widespread usage in the U.S. military.`
- Requirements: `core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. 
```

### Proposed fragment

```text
Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```


## AHE-016

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s6`
- Event meaning: `The following month, Anthropic announced that it would allow national security customers to use Claude Gov.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Split during review: also 'Anthropic's orthogonal usage policy ... led to a conflict between Anthropic and the Trump administration by September'. Strip the leading citation marker.`

### Authoritative source text

```text
[10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. 
```

### Proposed fragment

```text
The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.
```


## AHE-017

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0011`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s7`
- Event meaning: `That month, Amodei criticized Trump's approach to export restrictions on semiconductors.`
- Requirements: `core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. 
```

### Proposed fragment

```text
That month, Amodei criticized Trump's approach to export restrictions on semiconductors.
```


## AHE-018

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0012`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s1`
- Event meaning: `Anthropic's strategy has mirrored Amodei's views toward Trump.`
- Requirements: `core_event`
- Review rationale: `Split during review: also 'in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a 'feudal warlord''.`

### Authoritative source text

```text
Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord". 
```

### Proposed fragment

```text
Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord".
```


## AHE-019

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0012`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s2`
- Event meaning: `As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins.`
- Requirements: `core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  
```

### Proposed fragment

```text
As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment.
```


## AHE-020

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0012`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s3`
- Event meaning: `David Sacks said that Anthropic was among several 'AI doomers' that support regulation he saw as overly restrictive.`
- Requirements: `attribution, core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
David  Sacks,  Trump's  advisor  for  artificial intelligence  and  cryptocurrency,  said  on All-In (2020-present)  that Anthropic  was  among  several  "AI doomers"  that  support  regulation  he  saw  as  overly  restrictive.  
```

### Proposed fragment

```text
David Sacks, Trump's advisor for artificial intelligence and cryptocurrency, said on All-In (2020-present) that Anthropic was among several "AI doomers" that support regulation he saw as overly restrictive.
```


## AHE-021

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0012`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s4`
- Event meaning: `According to The Wall Street Journal, officials close to Sacks examined whether Anthropic's Claude was a 'woke AI'.`
- Requirements: `attribution, core_event`
- Review rationale: `Split during review: also 'in July, Trump signed an executive order 'Preventing Woke AI in the Federal Government''.`

### Authoritative source text

```text
According  to The  Wall  Street  Journal , officials close to Sacks examined whether Anthropic's Claude was a "woke AI"; in July, Trump signed an executive order "Preventing Woke AI in the Federal Government ". 
```

### Proposed fragment

```text
According to The Wall Street Journal , officials close to Sacks examined whether Anthropic's Claude was a "woke AI"; in July, Trump signed an executive order "Preventing Woke AI in the Federal Government ".
```


## AHE-022

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0013`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s1`
- Event meaning: `Sacks viewed Amodei's decision to attend the World Economic Forum, his hiring of Biden officials, and Anthropic's association with Open Philanthropy as evidence that Anthropic would not support Trump's agenda.`
- Requirements: `attribution, core_event, modality, negation`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda. 
```

### Proposed fragment

```text
Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.
```


## AHE-023

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0013`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s2`
- Event meaning: `In October 2025, Sacks stated that Anthropic was 'running a sophisticated regulatory capture strategy based on fearmongering'.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Split during review: also 'That month, Amodei published a blog post rebuffing 'inaccurate claims' from the Trump administration on Anthropic's policies, intensifying the dispute'. Strip the leading citation marker.`

### Authoritative source text

```text
[15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic's  policies,  intensifying  the  dispute.  
```

### Proposed fragment

```text
In October 2025, Sacks stated that Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration on Anthropic's policies, intensifying the dispute.
```


## AHE-024

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0013`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s3`
- Event meaning: `Amodei's statement included views explicitly espoused by vice president JD Vance.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Amodei's  statement  included  views explicitly espoused by vice president JD Vance. 
```

### Proposed fragment

```text
Amodei's statement included views explicitly espoused by vice president JD Vance.
```


## AHE-025

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0013`
- Section path: `Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration`
- Source segment label: `s4`
- Event meaning: `In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration.`
- Requirements: `core_event, purpose, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[17]  In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration. 
```

### Proposed fragment

```text
In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration.
```


## AHE-026

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0015`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s1`
- Event meaning: `In December 2025, secretary of defense Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In  December  2025,  secretary  of  defense  Pete  Hegseth  announced  GenAI.mil,  an  artificial  intelligence platform  for  the  Department  of  Defense.  
```

### Proposed fragment

```text
In December 2025, secretary of defense Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense.
```


## AHE-027

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0015`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s2`
- Event meaning: `The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
The  department  initially  contracted  Google  Gemini  for  the platform, then OpenAI's ChatGPT. 
```

### Proposed fragment

```text
The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT.
```


## AHE-028

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0015`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s3`
- Event meaning: `The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying 'woke AI'.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[19][20] The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI". 
```

### Proposed fragment

```text
The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI".
```


## AHE-029

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0016`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s1`
- Event meaning: `In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic. 
```

### Proposed fragment

```text
In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.
```


## AHE-030

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0016`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s2`
- Event meaning: `According to Reuters, Anthropic representatives opposed the use of the company's products for surveillance or to develop lethal autonomous weapons.`
- Requirements: `attribution, core_event, negation`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[22] According  to  Reuters,  Anthropic  representatives  opposed  the  use  of  the  company's  products  for surveillance  or  to  develop  lethal  autonomous  weapons. 
```

### Proposed fragment

```text
According to Reuters, Anthropic representatives opposed the use of the company's products for surveillance or to develop lethal autonomous weapons.
```


## AHE-031

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0016`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s3`
- Event meaning: `The dispute between Anthropic and the Department of Defense resulted in the termination of a contract worth an estimated US$200 million.`
- Requirements: `core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[23] The  dispute  between  Anthropic  and  the Department of Defense resulted in the termination of a contract worth an estimated US$200 million. 
```

### Proposed fragment

```text
The dispute between Anthropic and the Department of Defense resulted in the termination of a contract worth an estimated US$200 million.
```


## AHE-032

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s1`
- Event meaning: `In February 2026, Emil Michael stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's Claude, to unclassified and classified domains.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's  Claude,  to  unclassified  and  classified  domains. 
```

### Proposed fragment

```text
In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's Claude, to unclassified and classified domains.
```


## AHE-033

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s2`
- Event meaning: `That month, Axios reported that the Department of Defense had used Claude in the United States intervention in Venezuela.`
- Requirements: `attribution, core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[25] That  month, Axios reported  that  the Department of Defense had used Claude in the United States intervention in Venezuela. 
```

### Proposed fragment

```text
That month, Axios reported that the Department of Defense had used Claude in the United States intervention in Venezuela.
```


## AHE-034

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s3`
- Event meaning: `Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.`
- Requirements: `attribution, core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations. 
```

### Proposed fragment

```text
Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.
```


## AHE-035

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s4`
- Event meaning: `After Anthropic refused to agree to allow the Department of Defense to use Claude for 'all lawful purposes', the department threatened to cancel its contracts with the company.`
- Requirements: `attribution, core_event, negation`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the  department threatened to cancel its contracts with the company. 
```

### Proposed fragment

```text
After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the department threatened to cancel its contracts with the company.
```


## AHE-036

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s5`
- Event meaning: `Hegseth additionally moved to label Anthropic a 'supply chain risk', which would have forced military contractors to cut ties with Anthropic.`
- Requirements: `core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[27] Hegseth  additionally  moved to label  Anthropic  a  "supply  chain  risk",  which  would  have  forced  military  contractors  to  cut  ties  with Anthropic. 
```

### Proposed fragment

```text
Hegseth additionally moved to label Anthropic a "supply chain risk", which would have forced military contractors to cut ties with Anthropic.
```


## AHE-037

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s6`
- Event meaning: `A federal judge blocked most of this designation, describing it as punitive.`
- Requirements: `core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[28] A federal judge blocked most of this designation, describing it as punitive. 
```

### Proposed fragment

```text
A federal judge blocked most of this designation, describing it as punitive.
```


## AHE-038

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0017`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s7`
- Event meaning: `The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems.`
- Requirements: `core_event, temporal`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[29][30]  The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems. 
```

### Proposed fragment

```text
The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems.
```


## AHE-039

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0018`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s1`
- Event meaning: `Michael told reporters that Anthropic should 'cross the Rubicon' and allow the Department of Defense to dictate the terms of how its technology is used.`
- Requirements: `attribution, core_event, modality`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Michael told reporters that Anthropic should "cross the Rubicon" and allow the Department of Defense to dictate the terms of how its technology is used. 
```

### Proposed fragment

```text
Michael told reporters that Anthropic should "cross the Rubicon" and allow the Department of Defense to dictate the terms of how its technology is used.
```


## AHE-040

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0018`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s2`
- Event meaning: `The position of the Department of Defense, and its tactics during the dispute, were widely criticized on grounds including violating the principles of rule-of-law, market independence and national security.`
- Requirements: `core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[32] The position of the Department of Defense, and its tactics during the dispute, were widely criticized on grounds including violating the principles of rule-oflaw, market independence and national security. 
```

### Proposed fragment

```text
The position of the Department of Defense, and its tactics during the dispute, were widely criticized on grounds including violating the principles of rule-oflaw, market independence and national security.
```


## AHE-041

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0019`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s1`
- Event meaning: `In a June 2026 Bloomberg interview, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike, but that, if it had, the use case would not violate Anthropic's red lines.`
- Requirements: `attribution, core_event, negation, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In  a  June  2026  Bloomberg  interview  about  Claude's  reported  role  in  U.S.  military  targeting  systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike,  but  that,  if  it  had,  the  use  case  would  not  violate  Anthropic's  red  lines. 
```

### Proposed fragment

```text
In a June 2026 Bloomberg interview about Claude's reported role in U.S. military targeting systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike, but that, if it had, the use case would not violate Anthropic's red lines.
```


## AHE-042

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0019`
- Section path: `Anthropic-United States Department of Defense dispute > Dispute`
- Source segment label: `s2`
- Event meaning: `The exchange concerned the 2026 Minab school strike, which Amnesty International described as an unlawful U.S. strike that killed 156 people, including 120 children, and which Human Rights Watch said should be investigated as a war crime.`
- Requirements: `attribution, core_event`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[35][36] The  exchange concerned  the  2026  Minab  school  strike,  which Amnesty  International  described  as  an  unlawful  U.S. strike  that  killed  156  people,  including  120  children,  and  which  Human  Rights  Watch  said  should  be investigated as a war crime. 
```

### Proposed fragment

```text
The exchange concerned the 2026 Minab school strike, which Amnesty International described as an unlawful U.S. strike that killed 156 people, including 120 children, and which Human Rights Watch said should be investigated as a war crime.
```


## AHE-043

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0021`
- Section path: `Anthropic-United States Department of Defense dispute > Impact`
- Source segment label: `s1`
- Event meaning: `The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars. 
```

### Proposed fragment

```text
The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars.
```


## AHE-044

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0022`
- Section path: `Anthropic-United States Department of Defense dispute > Impact`
- Source segment label: `s1`
- Event meaning: `Following the government's actions against Anthropic, OpenAI 'rushed', hours before the US started the 2026 Iran war, to get a deal without the constraints that Anthropic had sought.`
- Requirements: `core_event, negation, temporal`
- Review rationale: `Split during review: also 'the US started the 2026 Iran war'.`

### Authoritative source text

```text
Following the government's actions against Anthropic, OpenAI "rushed", [40] hours before the US started the 2026 Iran war, [41] to get a deal without the constraints that Anthropic had sought. 
```

### Proposed fragment

```text
Following the government's actions against Anthropic, OpenAI "rushed", [40] hours before the US started the 2026 Iran war, [41] to get a deal without the constraints that Anthropic had sought.
```


## AHE-045

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0023`
- Section path: `Anthropic-United States Department of Defense dispute > Impact`
- Source segment label: `s1`
- Event meaning: `As of late April, notwithstanding the ND Cal. injunction, DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems.`
- Requirements: `core_event, negation, temporal`
- Review rationale: `Strip the trailing citation marker.`

### Authoritative source text

```text
As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems." [31]
```

### Proposed fragment

```text
As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems."
```


## AHE-046

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0026`
- Section path: `Anthropic-United States Department of Defense dispute > Lawsuits`
- Source segment label: `s1`
- Event meaning: `The Department of War's records show that it designated Anthropic as a supply chain risk because of its 'hostile manner through the press'.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
The Department of War's records show that it designated Anthropic as a supply chain risk because  of  its  'hostile  manner  through  the press.' 
```

### Proposed fragment

```text
The Department of War's records show that it designated Anthropic as a supply chain risk because of its 'hostile manner through the press.'
```


## AHE-047

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0026`
- Section path: `Anthropic-United States Department of Defense dispute > Lawsuits`
- Source segment label: `s2`
- Event meaning: `Punishing Anthropic for bringing public scrutiny to the government's contracting position is classic illegal First Amendment retaliation.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Punishing  Anthropic for bringing public scrutiny to the government's contracting  position  is  classic  illegal  First Amendment retaliation. 
```

### Proposed fragment

```text
Punishing Anthropic for bringing public scrutiny to the government's contracting position is classic illegal First Amendment retaliation.
```


## AHE-048

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0026`
- Section path: `Anthropic-United States Department of Defense dispute > Lawsuits`
- Source segment label: `s4`
- Event meaning: `At bottom, Anthropic has shown that these broad punitive measures were likely unlawful and that it is suffering irreparable harm from them.`
- Requirements: `core_event, modality`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
At bottom, Anthropic has shown that these broad punitive  measures  were  likely  unlawful  and that  it  is  suffering  irreparable  harm  from them.  
```

### Proposed fragment

```text
At bottom, Anthropic has shown that these broad punitive measures were likely unlawful and that it is suffering irreparable harm from them.
```


## AHE-049

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0026`
- Section path: `Anthropic-United States Department of Defense dispute > Lawsuits`
- Source segment label: `s5`
- Event meaning: `Numerous amici have also described wide-ranging harm to the public interest, including the chilling of open discussion about important topics in AI safety.`
- Requirements: `core_event`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
Numerous  amici  have  also  described wide-ranging  harm  to  the  public  interest, including  the  chilling  of  open  discussion about important topics in AI safety.
```

### Proposed fragment

```text
Numerous amici have also described wide-ranging harm to the public interest, including the chilling of open discussion about important topics in AI safety.
```


## AHE-050

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0028`
- Section path: `Anthropic-United States Department of Defense dispute > Anthropic PBC v. Department of War`
- Source segment label: `s1`
- Event meaning: `In April 2026, the Court of Appeals for the D.C. Circuit in a per curiam order denied Anthropic's motion to lift the FASCSA designation.`
- Requirements: `core_event, negation, temporal`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
In  April  2026,  the  Court  of  Appeals  for  the  D.C. Circuit in a per curiam order denied  Anthropic's motion to  lift  the  FASCSA  designation. 
```

### Proposed fragment

```text
In April 2026, the Court of Appeals for the D.C. Circuit in a per curiam order denied Anthropic's motion to lift the FASCSA designation.
```


## AHE-051

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0028`
- Section path: `Anthropic-United States Department of Defense dispute > Anthropic PBC v. Department of War`
- Source segment label: `s2`
- Event meaning: `The April order is not final.`
- Requirements: `core_event, negation`
- Review rationale: `Strip the leading citation marker.`

### Authoritative source text

```text
[45] The April order  is  not  final.  
```

### Proposed fragment

```text
The April order is not final.
```


## AHE-052

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0028`
- Section path: `Anthropic-United States Department of Defense dispute > Anthropic PBC v. Department of War`
- Source segment label: `s3`
- Event meaning: `The court's order said lifting the designation 'would force the United States military to prolong its dealings with an unwanted vendor of critical AI services in the middle of a significant ongoing military conflict'.`
- Requirements: `attribution, core_event, modality`
- Review rationale: `Sentence-bound proposal.`

### Authoritative source text

```text
The  court's  order  said  lifting  the designation "would force the United States military to prolong  its  dealings  with  an  unwanted  vendor  of critical  AI  services  in  the  middle  of  a  significant ongoing military conflict". 
```

### Proposed fragment

```text
The court's order said lifting the designation "would force the United States military to prolong its dealings with an unwanted vendor of critical AI services in the middle of a significant ongoing military conflict".
```


## AHE-053

- Paragraph node: `nod_e84869f6fcd4ed02c70a550a_0028`
- Section path: `Anthropic-United States Department of Defense dispute > Anthropic PBC v. Department of War`
- Source segment label: `s4`
- Event meaning: `According to Wired, several experts in government contracting and corporate rights said Anthropic has a strong case against the government, but the courts sometimes refuse to overrule the White House on matters related to national security.`
- Requirements: `attribution, core_event, negation`
- Review rationale: `Strip the trailing citation marker.`

### Authoritative source text

```text
According to Wired , "Several experts in government contracting and corporate  rights"  said  "Anthropic  has  a  strong  case against  the  government,  but  the  courts  sometimes refuse to overrule the White House on matters related to national security." [46]
```

### Proposed fragment

```text
According to Wired , "Several experts in government contracting and corporate rights" said "Anthropic has a strong case against the government, but the courts sometimes refuse to overrule the White House on matters related to national security."
```


