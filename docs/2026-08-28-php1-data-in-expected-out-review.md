# PHP-1 Data-In / Expected-Out Review Packet

- **Status:** Human review completed for all exact Organization mention expectations; broad semantic expectations remain provisional.
- **Source:** The 50-case CIR evaluation packet and three locked local PDFs.
- **Authority:** Paragraph and Source-segment text was reconstructed from fresh public-path ingestion; model output was not used as an oracle.
- **Purpose:** Determine whether failures reflect model quality, task complexity, segmentation, or an incorrect expectation.
- **Mention instructions:** [`prompts/paragraph_organization_mention_v1.md`](../prompts/paragraph_organization_mention_v1.md)
- **Relation instructions:** [`prompts/paragraph_organization_pair_relation_v1.md`](../prompts/paragraph_organization_pair_relation_v1.md)
- **Expected mention catalog:** [`php1-organization-mention-gold-v1.json`](php1-organization-mention-gold-v1.json)
- **Expected relation catalog:** [`php1-direct-organization-relation-benchmark-v2.json`](php1-direct-organization-relation-benchmark-v2.json)

## How to review

Each item separates three contracts that should not be confused.

1. The complete paragraph is the authoritative evidence span selected by the original packet.
2. PHP-1 mention extraction receives one bounded Source segment at a time, not the whole paragraph.
3. The broad semantic expectation describes desired intelligence; it is not automatically an exact PHP-1 output contract.

Where the relation benchmark has a complete current-ontology target, this file shows the exact candidate pair and expected plain-text relation result.

## Exact mention review outcome

The reviewer examined all 50 packet cases one Source segment at a time on 2026-08-28.

The resulting Gold contains 164 Source segments and 209 exact Organization Mention occurrences.

The exact Organization mention catalog is the human-reviewed evaluation oracle under `named_organization_mention_v1`.

Every Organization extraction evaluation must use this catalog as its only expected Mention oracle.

Production extraction must not read the catalog or specialize behavior for its names.

Country and supranational names count when the segment assigns them institutional agency, such as membership, signing, refusal, founding, or another deliberate act.

The exact mention remains the literal source span; a later reference-resolution capability may narrow that mention to a specific government agency or other national body.

Segment-local extraction cannot reliably determine whether forms such as `AISIs`, `it`, `companies`, or `the Network` denote a class, an alias, or a specific prior Organization.

A later bounded reference-resolution stage should resolve those forms against authoritative neighboring Source segments before Entity construction.

Model and span-proposer outputs remain diagnostic evidence and never define the expected result.

### AD-01 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0008` p. 1

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0008`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan  administration. [1] The  Department  of  Defense  established  a  policy  on  the  use  of  artificial intelligence  in  2012,  Directive  3000.09. [2] Efforts  to  utilize  artificial  intelligence  intensified  under  the term  of  Secretary Ash  Carter. [3] The  Department  of  Defense's  use  of  artificial  intelligence  for  Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations. [4]
```

Provisional expected semantic result:

> Identify that the Department of Defense established the 2012 AI-use policy.

Class: `direct`

Anchor: `Directive 3000.09`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph states one policy action.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.
```

Expected result:

```text
mention: s1 | United States Department of Defense
mention: s1 | Reagan administration
```

Source segment `s2` input:

```text
[1] The Department of Defense established a policy on the use of artificial intelligence in 2012, Directive 3000.09.
```

Expected result:

```text
mention: s2 | Department of Defense
```

Source segment `s3` input:

```text
[2] Efforts to utilize artificial intelligence intensified under the term of Secretary Ash Carter.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[3] The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.
```

Expected result:

```text
mention: s4 | Department of Defense
mention: s4 | Project Maven
mention: s4 | Google
```

Source segment `s5` input:

```text
[4]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-02 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0008` p. 1

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0008`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan  administration. [1] The  Department  of  Defense  established  a  policy  on  the  use  of  artificial intelligence  in  2012,  Directive  3000.09. [2] Efforts  to  utilize  artificial  intelligence  intensified  under  the term  of  Secretary Ash  Carter. [3] The  Department  of  Defense's  use  of  artificial  intelligence  for  Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations. [4]
```

Provisional expected semantic result:

> Preserve the stated causal chain to protests and resignations without inventing a policy conflict.

Class: `causal`

Anchor: `Project Maven prompted concerns within Google`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph requires causal-event extraction.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.
```

Expected result:

```text
mention: s1 | United States Department of Defense
mention: s1 | Reagan administration
```

Source segment `s2` input:

```text
[1] The Department of Defense established a policy on the use of artificial intelligence in 2012, Directive 3000.09.
```

Expected result:

```text
mention: s2 | Department of Defense
```

Source segment `s3` input:

```text
[2] Efforts to utilize artificial intelligence intensified under the term of Secretary Ash Carter.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[3] The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.
```

Expected result:

```text
mention: s4 | Department of Defense
mention: s4 | Project Maven
mention: s4 | Google
```

Source segment `s5` input:

```text
[4]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-03 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0010` pp. 1–2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0010`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives. In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East  in  May.  According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". [7]
```

Provisional expected semantic result:

> Identify the Anthropic-to-Trump-officials policy-discussion relation.

Class: `direct`

Anchor: `held discussions with Trump officials`

Current PHP-1 eligibility: `needs_coreference`

Eligibility rationale: The object is unnamed Trump officials.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives.
```

Expected result:

```text
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Stargate
mention: s2 | Anthropic
```

Source segment `s3` input:

```text
[5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Congress
```

Source segment `s4` input:

```text
According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.
```

Expected result:

```text
mention: s4 | Semafor
mention: s4 | Anthropic
mention: s4 | Biden administration
mention: s4 | Artificial Intelligence Safety Institute
mention: s4 | National Security Council
```

Source segment `s5` input:

```text
[6] The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument".
```

Expected result:

```text
mention: s5 | The New York Times
```

Source segment `s6` input:

```text
[7]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-04 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0010` pp. 1–2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0010`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives. In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East  in  May.  According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". [7]
```

Provisional expected semantic result:

> Extract lobbying and opposition as separate relations, not one vague political stance.

Class: `multiple`

Anchor: `privately lobbied for Congress`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: Anthropic and Congress are named organizations.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives.
```

Expected result:

```text
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Stargate
mention: s2 | Anthropic
```

Source segment `s3` input:

```text
[5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Congress
```

Source segment `s4` input:

```text
According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.
```

Expected result:

```text
mention: s4 | Semafor
mention: s4 | Anthropic
mention: s4 | Biden administration
mention: s4 | Artificial Intelligence Safety Institute
mention: s4 | National Security Council
```

Source segment `s5` input:

```text
[6] The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument".
```

Expected result:

```text
mention: s5 | The New York Times
```

Source segment `s6` input:

```text
[7]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ad-04-anthropic-congress`

Candidate pair: `Anthropic` / `Congress`

Bounded Source-segment input:

```text
[5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.
```

Expected result:

```text
claim: s3 | Anthropic | privately lobbied for | Congress
```

### AD-05 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0010` pp. 1–2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0010`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives. In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy. [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East  in  May.  According  to Semafor ,  Trump  officials  chastised  Anthropic's  hiring  of  several  officials involved  in  the  Biden  administration,  including  Elizabeth  Kelly,  the  former  director  of  the  Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence. [6] The following month, Amodei wrote an op-ed in The New York Times describing  the  artificial  intelligence  regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument". [7]
```

Provisional expected semantic result:

> Preserve Semafor attribution for officials chastising Anthropic.

Class: `attribution`

Anchor: `According to Semafor`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests source attribution.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives.
```

Expected result:

```text
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Stargate
mention: s2 | Anthropic
```

Source segment `s3` input:

```text
[5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Congress
```

Source segment `s4` input:

```text
According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.
```

Expected result:

```text
mention: s4 | Semafor
mention: s4 | Anthropic
mention: s4 | Biden administration
mention: s4 | Artificial Intelligence Safety Institute
mention: s4 | National Security Council
```

Source segment `s5` input:

```text
[6] The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument".
```

Expected result:

```text
mention: s5 | The New York Times
```

Source segment `s6` input:

```text
[7]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-06 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0011` p. 2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0011`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services. By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. [8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. [9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. [14]
```

Provisional expected semantic result:

> Produce two distinct partnership candidates.

Class: `multiple`

Anchor: `partnered with Palantir and Amazon Web Services`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states two named partnerships.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services.
```

Expected result:

```text
mention: s1 | Trump administration
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Palantir
mention: s2 | Amazon Web Services
```

Source segment `s3` input:

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.
```

Expected result:

```text
mention: s3 | Biden administration
mention: s3 | Anthropic
mention: s3 | AI Safety Institute
```

Source segment `s4` input:

```text
[8] The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.
```

Expected result:

```text
mention: s4 | Department of Homeland Security
mention: s4 | Anthropic
```

Source segment `s5` input:

```text
[9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```

Expected result:

```text
mention: s5 | Palantir
mention: s5 | Department of Defense
mention: s5 | Anthropic
mention: s5 | U.S. military
```

Source segment `s6` input:

```text
[10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.
```

Expected result:

```text
mention: s6 | Anthropic
mention: s6 | Anthropic
mention: s6 | Federal Bureau of Investigation
mention: s6 | Secret Service
mention: s6 | Immigration and Customs Enforcement
mention: s6 | Anthropic
mention: s6 | Trump administration
```

Source segment `s7` input:

```text
[13] That month, Amodei criticized Trump's approach to export restrictions on semiconductors.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s8` input:

```text
[14]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ad-06-anthropic-palantir`

Candidate pair: `Anthropic` / `Palantir`

Bounded Source-segment input:

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```

Expected result:

```text
claim: s2 | Anthropic | partnered with | Palantir
```

Expectation: `php1-target-ad-06-anthropic-aws`

Candidate pair: `Anthropic` / `Amazon Web Services`

Bounded Source-segment input:

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```

Expected result:

```text
claim: s2 | Anthropic | partnered with | Amazon Web Services
```

### AD-07 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0011` p. 2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0011`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services. By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. [8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. [9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. [14]
```

Provisional expected semantic result:

> Do not resolve the generic name to a source-two institute without an explicit identity discriminator.

Class: `cross-source control`

Anchor: `reached an agreement with the AI Safety Institute`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The direct agreement remains reviewable despite identity ambiguity.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services.
```

Expected result:

```text
mention: s1 | Trump administration
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Palantir
mention: s2 | Amazon Web Services
```

Source segment `s3` input:

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.
```

Expected result:

```text
mention: s3 | Biden administration
mention: s3 | Anthropic
mention: s3 | AI Safety Institute
```

Source segment `s4` input:

```text
[8] The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.
```

Expected result:

```text
mention: s4 | Department of Homeland Security
mention: s4 | Anthropic
```

Source segment `s5` input:

```text
[9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```

Expected result:

```text
mention: s5 | Palantir
mention: s5 | Department of Defense
mention: s5 | Anthropic
mention: s5 | U.S. military
```

Source segment `s6` input:

```text
[10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.
```

Expected result:

```text
mention: s6 | Anthropic
mention: s6 | Anthropic
mention: s6 | Federal Bureau of Investigation
mention: s6 | Secret Service
mention: s6 | Immigration and Customs Enforcement
mention: s6 | Anthropic
mention: s6 | Trump administration
```

Source segment `s7` input:

```text
[13] That month, Amodei criticized Trump's approach to export restrictions on semiconductors.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s8` input:

```text
[14]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ad-07-anthropic-aisi`

Candidate pair: `Anthropic` / `AI Safety Institute`

Bounded Source-segment input:

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.
```

Expected result:

```text
claim: s3 | Anthropic | reached an agreement with | AI Safety Institute
```

### AD-08 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0011` p. 2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0011`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services. By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. [8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. [9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. [14]
```

Provisional expected semantic result:

> Preserve the Department of Homeland Security actor, Claude inclusion, and the May 2025 end date.

Class: `temporal`

Anchor: `authorized its workers to use`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph relates an organization to a product and date.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services.
```

Expected result:

```text
mention: s1 | Trump administration
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Palantir
mention: s2 | Amazon Web Services
```

Source segment `s3` input:

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.
```

Expected result:

```text
mention: s3 | Biden administration
mention: s3 | Anthropic
mention: s3 | AI Safety Institute
```

Source segment `s4` input:

```text
[8] The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.
```

Expected result:

```text
mention: s4 | Department of Homeland Security
mention: s4 | Anthropic
```

Source segment `s5` input:

```text
[9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```

Expected result:

```text
mention: s5 | Palantir
mention: s5 | Department of Defense
mention: s5 | Anthropic
mention: s5 | U.S. military
```

Source segment `s6` input:

```text
[10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.
```

Expected result:

```text
mention: s6 | Anthropic
mention: s6 | Anthropic
mention: s6 | Federal Bureau of Investigation
mention: s6 | Secret Service
mention: s6 | Immigration and Customs Enforcement
mention: s6 | Anthropic
mention: s6 | Trump administration
```

Source segment `s7` input:

```text
[13] That month, Amodei criticized Trump's approach to export restrictions on semiconductors.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s8` input:

```text
[14]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-09 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0011` p. 2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0011`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services. By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization. In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation. [8]  The Department of Homeland Security  authorized  its  workers  to  use  commercial  artificial  intelligence  systems,  including Anthropic's  Claude,  until  May  2025. [9] Through  its  interoperability  with  Palantir,  a  company  heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military. [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the  surveillance  systems  implemented  at  the  Federal  Bureau  of  Investigation,  the  Secret  Service,  and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September. [13] That month,  Amodei criticized Trump's approach to export restrictions on semiconductors. [14]
```

Provisional expected semantic result:

> Preserve Palantir as the stated mechanism for wider military usage.

Class: `mediated`

Anchor: `Through its interoperability with Palantir`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph names Anthropic and Palantir.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Prior to the dispute, the Trump administration had integrated Anthropic's services.
```

Expected result:

```text
mention: s1 | Trump administration
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.
```

Expected result:

```text
mention: s2 | Anthropic
mention: s2 | Palantir
mention: s2 | Amazon Web Services
```

Source segment `s3` input:

```text
In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.
```

Expected result:

```text
mention: s3 | Biden administration
mention: s3 | Anthropic
mention: s3 | AI Safety Institute
```

Source segment `s4` input:

```text
[8] The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.
```

Expected result:

```text
mention: s4 | Department of Homeland Security
mention: s4 | Anthropic
```

Source segment `s5` input:

```text
[9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```

Expected result:

```text
mention: s5 | Palantir
mention: s5 | Department of Defense
mention: s5 | Anthropic
mention: s5 | U.S. military
```

Source segment `s6` input:

```text
[10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.
```

Expected result:

```text
mention: s6 | Anthropic
mention: s6 | Anthropic
mention: s6 | Federal Bureau of Investigation
mention: s6 | Secret Service
mention: s6 | Immigration and Customs Enforcement
mention: s6 | Anthropic
mention: s6 | Trump administration
```

Source segment `s7` input:

```text
[13] That month, Amodei criticized Trump's approach to export restrictions on semiconductors.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s8` input:

```text
[14]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ad-09-anthropic-palantir`

Candidate pair: `Anthropic` / `Palantir`

Bounded Source-segment input:

```text
[9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```

Expected result:

```text
claim: s5 | Anthropic | interoperability with | Palantir
```

Expectation: `php1-target-ad-09-palantir-dod`

Candidate pair: `Palantir` / `Department of Defense`

Bounded Source-segment input:

```text
[9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.
```

Expected result:

```text
claim: s5 | Palantir | heavily involved in data analysis and analytics at | Department of Defense
```

### AD-10 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0015` p. 2

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0015`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In  December  2025,  secretary  of  defense  Pete  Hegseth  announced  GenAI.mil,  an  artificial  intelligence platform  for  the  Department  of  Defense.  The  department  initially  contracted  Google  Gemini  for  the platform, then OpenAI's ChatGPT. [19][20] The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI". [21]
```

Provisional expected semantic result:

> Preserve the contract order and keep Gemini and ChatGPT distinct products.

Class: `ordered multiple`

Anchor: `initially contracted Google Gemini...then OpenAI's ChatGPT`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns products and contract sequence.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In December 2025, secretary of defense Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense.
```

Expected result:

```text
mention: s1 | Department of Defense
```

Source segment `s2` input:

```text
The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT.
```

Expected result:

```text
mention: s2 | Google
mention: s2 | OpenAI
```

Source segment `s3` input:

```text
[19][20] The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI".
```

Expected result:

```text
mention: s3 | Department of Defense
mention: s3 | xAI
```

Source segment `s4` input:

```text
[21]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-11 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0016` p. 3

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0016`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic. [22] According  to  Reuters,  Anthropic  representatives  opposed  the  use  of  the  company's  products  for surveillance  or  to  develop  lethal  autonomous  weapons. [23] The  dispute  between  Anthropic  and  the Department of Defense resulted in the termination of a contract worth an estimated US$200 million. [24]
```

Provisional expected semantic result:

> Extract Anthropic opposition to surveillance use and lethal autonomous weapons with Reuters attribution.

Class: `attributed multiple`

Anchor: `According to Reuters`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns policy positions and uses.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.
```

Expected result:

```text
mention: s1 | Semafor
mention: s1 | Department of Defense
mention: s1 | Anthropic
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
[22] According to Reuters, Anthropic representatives opposed the use of the company's products for surveillance or to develop lethal autonomous weapons.
```

Expected result:

```text
mention: s2 | Reuters
mention: s2 | Anthropic
```

Source segment `s3` input:

```text
[23] The dispute between Anthropic and the Department of Defense resulted in the termination of a contract worth an estimated US$200 million.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Department of Defense
```

Source segment `s4` input:

```text
[24]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-12 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0016` p. 3

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0016`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic. [22] According  to  Reuters,  Anthropic  representatives  opposed  the  use  of  the  company's  products  for surveillance  or  to  develop  lethal  autonomous  weapons. [23] The  dispute  between  Anthropic  and  the Department of Defense resulted in the termination of a contract worth an estimated US$200 million. [24]
```

Provisional expected semantic result:

> Preserve the estimated amount and avoid asserting a precise contractual value.

Class: `causal`

Anchor: `termination of a contract worth an estimated US$200 million`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns a value and causal result.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.
```

Expected result:

```text
mention: s1 | Semafor
mention: s1 | Department of Defense
mention: s1 | Anthropic
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
[22] According to Reuters, Anthropic representatives opposed the use of the company's products for surveillance or to develop lethal autonomous weapons.
```

Expected result:

```text
mention: s2 | Reuters
mention: s2 | Anthropic
```

Source segment `s3` input:

```text
[23] The dispute between Anthropic and the Department of Defense resulted in the termination of a contract worth an estimated US$200 million.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Department of Defense
```

Source segment `s4` input:

```text
[24]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-13 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0017` p. 3

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0017`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's  Claude,  to  unclassified  and  classified  domains. [25] That  month, Axios reported  that  the Department of Defense had used Claude in the United States intervention in Venezuela. Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations. [26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the  department threatened to cancel its contracts with the company. [27] Hegseth  additionally  moved to label  Anthropic  a  "supply  chain  risk",  which  would  have  forced  military  contractors  to  cut  ties  with Anthropic. [28] A federal judge blocked most of this designation, describing it as punitive. [29][30]  The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems. [31]
```

Provisional expected semantic result:

> Identify Anthropic's refusal and the Department's threatened cancellation as separate actions.

Class: `direct`

Anchor: `all lawful purposes`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph names Anthropic and the Department.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's Claude, to unclassified and classified domains.
```

Expected result:

```text
mention: s1 | Department of Defense
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
[25] That month, Axios reported that the Department of Defense had used Claude in the United States intervention in Venezuela.
```

Expected result:

```text
mention: s2 | Axios
mention: s2 | Department of Defense
```

Source segment `s3` input:

```text
Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Axios
mention: s3 | Department of Defense
```

Source segment `s4` input:

```text
[26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the department threatened to cancel its contracts with the company.
```

Expected result:

```text
mention: s4 | Anthropic
mention: s4 | Department of Defense
```

Source segment `s5` input:

```text
[27] Hegseth additionally moved to label Anthropic a "supply chain risk", which would have forced military contractors to cut ties with Anthropic.
```

Expected result:

```text
mention: s5 | Anthropic
mention: s5 | Anthropic
```

Source segment `s6` input:

```text
[28] A federal judge blocked most of this designation, describing it as punitive.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s7` input:

```text
[29][30] The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems.
```

Expected result:

```text
mention: s7 | D.C. Circuit
mention: s7 | Anthropic
```

Source segment `s8` input:

```text
[31]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ad-13-anthropic-dod`

Candidate pair: `Anthropic` / `Department of Defense`

Bounded Source-segment input:

```text
[26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the department threatened to cancel its contracts with the company.
```

Expected result:

```text
claim: s4 | Anthropic | refused to agree to allow | Department of Defense
```

### AD-14 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0017` p. 3

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0017`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's  Claude,  to  unclassified  and  classified  domains. [25] That  month, Axios reported  that  the Department of Defense had used Claude in the United States intervention in Venezuela. Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations. [26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the  department threatened to cancel its contracts with the company. [27] Hegseth  additionally  moved to label  Anthropic  a  "supply  chain  risk",  which  would  have  forced  military  contractors  to  cut  ties  with Anthropic. [28] A federal judge blocked most of this designation, describing it as punitive. [29][30]  The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems. [31]
```

Provisional expected semantic result:

> Distinguish the judge's blocking action from Hegseth's attempted designation.

Class: `legal`

Anchor: `A federal judge blocked most`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns legal actions by a person.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's Claude, to unclassified and classified domains.
```

Expected result:

```text
mention: s1 | Department of Defense
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
[25] That month, Axios reported that the Department of Defense had used Claude in the United States intervention in Venezuela.
```

Expected result:

```text
mention: s2 | Axios
mention: s2 | Department of Defense
```

Source segment `s3` input:

```text
Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.
```

Expected result:

```text
mention: s3 | Anthropic
mention: s3 | Axios
mention: s3 | Department of Defense
```

Source segment `s4` input:

```text
[26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the department threatened to cancel its contracts with the company.
```

Expected result:

```text
mention: s4 | Anthropic
mention: s4 | Department of Defense
```

Source segment `s5` input:

```text
[27] Hegseth additionally moved to label Anthropic a "supply chain risk", which would have forced military contractors to cut ties with Anthropic.
```

Expected result:

```text
mention: s5 | Anthropic
mention: s5 | Anthropic
```

Source segment `s6` input:

```text
[28] A federal judge blocked most of this designation, describing it as punitive.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s7` input:

```text
[29][30] The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems.
```

Expected result:

```text
mention: s7 | D.C. Circuit
mention: s7 | Anthropic
```

Source segment `s8` input:

```text
[31]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-15 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0019` p. 3

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0019`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In  a  June  2026  Bloomberg  interview  about  Claude's  reported  role  in  U.S.  military  targeting  systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike,  but  that,  if  it  had,  the  use  case  would  not  violate  Anthropic's  red  lines. [35][36] The  exchange concerned  the  2026  Minab  school  strike,  which Amnesty  International  described  as  an  unlawful  U.S. strike  that  killed  156  people,  including  120  children,  and  which  Human  Rights  Watch  said  should  be investigated as a war crime. [37][38]
```

Provisional expected semantic result:

> Do not accept that Claude was used in the strike or that the use case complied with red lines.

Class: `uncertainty control`

Anchor: `did not know whether Claude had been used`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests uncertainty.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In a June 2026 Bloomberg interview about Claude's reported role in U.S. military targeting systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike, but that, if it had, the use case would not violate Anthropic's red lines.
```

Expected result:

```text
mention: s1 | Bloomberg
mention: s1 | U.S. military
mention: s1 | Anthropic
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
[35][36] The exchange concerned the 2026 Minab school strike, which Amnesty International described as an unlawful U.S. strike that killed 156 people, including 120 children, and which Human Rights Watch said should be investigated as a war crime.
```

Expected result:

```text
mention: s2 | Amnesty International
mention: s2 | Human Rights Watch
```

Source segment `s3` input:

```text
[37][38]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-16 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0026` p. 4

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0026`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
The Department of War's records show that it designated Anthropic as a supply chain risk because  of  its  'hostile  manner  through  the press.' Punishing  Anthropic for bringing public scrutiny to the government's contracting  position  is  classic  illegal  First Amendment retaliation. (...) At bottom, Anthropic has shown that these broad punitive  measures  were  likely  unlawful  and that  it  is  suffering  irreparable  harm  from them.  Numerous  amici  have  also  described wide-ranging  harm  to  the  public  interest, including  the  chilling  of  open  discussion about important topics in AI safety.
```

Provisional expected semantic result:

> Preserve that the wording occurs in a legal quotation and separate quoted arguments from adjudicated fact.

Class: `quotation control`

Anchor: `records show that it designated Anthropic`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests quoted legal argument.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The Department of War's records show that it designated Anthropic as a supply chain risk because of its 'hostile manner through the press.'
```

Expected result:

```text
mention: s1 | Department of War
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
Punishing Anthropic for bringing public scrutiny to the government's contracting position is classic illegal First Amendment retaliation.
```

Expected result:

```text
mention: s2 | Anthropic
```

Source segment `s3` input:

```text
(...)
```

Expected result:

```text
not_applicable_nonlexical
```

Source segment `s4` input:

```text
At bottom, Anthropic has shown that these broad punitive measures were likely unlawful and that it is suffering irreparable harm from them.
```

Expected result:

```text
mention: s4 | Anthropic
```

Source segment `s5` input:

```text
Numerous amici have also described wide-ranging harm to the public interest, including the chilling of open discussion about important topics in AI safety.
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AD-17 — reviewed packet item

Packet locator: `nod_355e4a2012f9cf3978bcf34a_0028` p. 4

Current reanchored node: `nod_37b059ad0a6c1245a366cf9a_0028`

Current representation: `rep_37b059ad0a6c1245a366cf9a`

Locked PDF SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`

Complete authoritative paragraph text:

```text
In  April  2026,  the  Court  of  Appeals  for  the  D.C. Circuit in a per curiam order denied  Anthropic's motion to  lift  the  FASCSA  designation. [45] The April order  is  not  final.  The  court's  order  said  lifting  the designation "would force the United States military to prolong  its  dealings  with  an  unwanted  vendor  of critical  AI  services  in  the  middle  of  a  significant ongoing military conflict". According to Wired , "Several experts in government contracting and corporate  rights"  said  "Anthropic  has  a  strong  case against  the  government,  but  the  courts  sometimes refuse to overrule the White House on matters related to national security." [46]
```

Provisional expected semantic result:

> Extract the D.C. Circuit denial and retain its non-final status.

Class: `legal status`

Anchor: `order is not final`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns a court order status.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In April 2026, the Court of Appeals for the D.C. Circuit in a per curiam order denied Anthropic's motion to lift the FASCSA designation.
```

Expected result:

```text
mention: s1 | Court of Appeals for the D.C. Circuit
mention: s1 | Anthropic
```

Source segment `s2` input:

```text
[45] The April order is not final.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
The court's order said lifting the designation "would force the United States military to prolong its dealings with an unwanted vendor of critical AI services in the middle of a significant ongoing military conflict".
```

Expected result:

```text
mention: s3 | United States military
```

Source segment `s4` input:

```text
According to Wired , "Several experts in government contracting and corporate rights" said "Anthropic has a strong case against the government, but the courts sometimes refuse to overrule the White House on matters related to national security." [46]
```

Expected result:

```text
mention: s4 | Wired
mention: s4 | Anthropic
mention: s4 | White House
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-01 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0003` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0003`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
AI safety gained prominence in 2023, notably with public declarations about potential existential risks from AI. During the AI Safety Summit in November 2023, the United Kingdom and the United States both created their own AISI. During the AI Seoul Summit in May 2024, international leaders agreed to form  a  network  of  AI  Safety  Institutes,  comprising  institutes  from  the  UK,  the  US,  Japan,  France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union. [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).
```

Provisional expected semantic result:

> Produce separate UK and US institute-creation candidates.

Class: `direct multiple`

Anchor: `United Kingdom and the United States both created their own AISI`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph names states rather than named organizations.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
AI safety gained prominence in 2023, notably with public declarations about potential existential risks from AI.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
During the AI Safety Summit in November 2023, the United Kingdom and the United States both created their own AISI.
```

Expected result:

```text
mention: s2 | United Kingdom
mention: s2 | United States
```

Source segment `s3` input:

```text
During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).
```

Expected result:

```text
mention: s4 | UK's AI Safety Institute
mention: s4 | AI Security Institute
mention: s4 | Center for AI Standards and Innovation (CAISI)
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-02 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0003` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0003`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
AI safety gained prominence in 2023, notably with public declarations about potential existential risks from AI. During the AI Safety Summit in November 2023, the United Kingdom and the United States both created their own AISI. During the AI Seoul Summit in May 2024, international leaders agreed to form  a  network  of  AI  Safety  Institutes,  comprising  institutes  from  the  UK,  the  US,  Japan,  France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union. [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).
```

Provisional expected semantic result:

> Preserve the listed network membership without treating every country as the same institute.

Class: `membership`

Anchor: `network of AI Safety Institutes`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph lists memberships across several spans.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
AI safety gained prominence in 2023, notably with public declarations about potential existential risks from AI.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
During the AI Safety Summit in November 2023, the United Kingdom and the United States both created their own AISI.
```

Expected result:

```text
mention: s2 | United Kingdom
mention: s2 | United States
```

Source segment `s3` input:

```text
During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).
```

Expected result:

```text
mention: s4 | UK's AI Safety Institute
mention: s4 | AI Security Institute
mention: s4 | Center for AI Standards and Innovation (CAISI)
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-03 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0005` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0005`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
In 2023, Rishi Sunak, the Prime Minister of the United Kingdom, expressed his intention to "make the UK not just the intellectual home but the geographical home of global AI safety regulation" and unveiled plans for an AI Safety Summit. [3] He emphasized the need for independent safety evaluations, stating that AI  companies  cannot  "mark  their  own  homework". [4] During  the  summit  in  November  2023,  the  UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology. Japan followed by launching an AI safety institute in February 2024. [6]
```

Provisional expected semantic result:

> Identify the UK institute's predecessor relationship.

Class: `identity lineage`

Anchor: `evolution of the Frontier AI Taskforce`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states organization lineage.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In 2023, Rishi Sunak, the Prime Minister of the United Kingdom, expressed his intention to "make the UK not just the intellectual home but the geographical home of global AI safety regulation" and unveiled plans for an AI Safety Summit.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
[3] He emphasized the need for independent safety evaluations, stating that AI companies cannot "mark their own homework".
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
[4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.
```

Expected result:

```text
mention: s3 | UK AISI
mention: s3 | Frontier AI Taskforce
mention: s3 | US AISI
mention: s3 | National Institute of Standards and Technology
```

Source segment `s4` input:

```text
Japan followed by launching an AI safety institute in February 2024.
```

Expected result:

```text
mention: s4 | Japan
```

Source segment `s5` input:

```text
[6]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ai-03-uk-aisi-frontier-taskforce`

Candidate pair: `UK AISI` / `Frontier AI Taskforce`

Bounded Source-segment input:

```text
[4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.
```

Expected result:

```text
claim: s3 | UK AISI | was officially established as an evolution of | Frontier AI Taskforce
```

### AI-04 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0005` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0005`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
In 2023, Rishi Sunak, the Prime Minister of the United Kingdom, expressed his intention to "make the UK not just the intellectual home but the geographical home of global AI safety regulation" and unveiled plans for an AI Safety Summit. [3] He emphasized the need for independent safety evaluations, stating that AI  companies  cannot  "mark  their  own  homework". [4] During  the  summit  in  November  2023,  the  UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology. Japan followed by launching an AI safety institute in February 2024. [6]
```

Provisional expected semantic result:

> Identify the US AISI-to-NIST placement.

Class: `organizational placement`

Anchor: `part of the National Institute of Standards and Technology`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states organization placement.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In 2023, Rishi Sunak, the Prime Minister of the United Kingdom, expressed his intention to "make the UK not just the intellectual home but the geographical home of global AI safety regulation" and unveiled plans for an AI Safety Summit.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
[3] He emphasized the need for independent safety evaluations, stating that AI companies cannot "mark their own homework".
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
[4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.
```

Expected result:

```text
mention: s3 | UK AISI
mention: s3 | Frontier AI Taskforce
mention: s3 | US AISI
mention: s3 | National Institute of Standards and Technology
```

Source segment `s4` input:

```text
Japan followed by launching an AI safety institute in February 2024.
```

Expected result:

```text
mention: s4 | Japan
```

Source segment `s5` input:

```text
[6]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ai-04-us-aisi-nist`

Candidate pair: `US AISI` / `National Institute of Standards and Technology`

Bounded Source-segment input:

```text
[4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.
```

Expected result:

```text
claim: s3 | US AISI | as part of | National Institute of Standards and Technology
```

### AI-05 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0006` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0006`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
Politico reported in April 2024 that many AI companies had not shared pre-deployment access to their most advanced AI models for evaluation. Meta's president of global affairs Nick Clegg said that many AI companies were waiting for the UK and the US AI Safety Institutes to work out common evaluation rules and procedures. [7] An  agreement  was  indeed  concluded  between  the  UK  and  the  US  in April  2024  to collaborate on at least one joint safety test. [8] Initially established in London, the UK AI Safety Institute announced in May 2024 that it would open an office in San Francisco, where many AI companies are located.  This  is  part  of  a  plan  to  "set  new,  international  standards  on  AI  safety",  according  to  UK's technology minister Michele Donelan. [9][10]
```

Provisional expected semantic result:

> Keep the claim about companies withholding pre-deployment access attributed to Politico.

Class: `attribution control`

Anchor: `Politico reported`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests attribution.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Politico reported in April 2024 that many AI companies had not shared pre-deployment access to their most advanced AI models for evaluation.
```

Expected result:

```text
mention: s1 | Politico
```

Source segment `s2` input:

```text
Meta's president of global affairs Nick Clegg said that many AI companies were waiting for the UK and the US AI Safety Institutes to work out common evaluation rules and procedures.
```

Expected result:

```text
mention: s2 | Meta
```

Aspirational context-resolved Organizations, which are not contiguous literal spans and therefore are not scored by the current PHP-1 exact-span oracle:

```text
resolved organization: Meta
resolved organization: UK AI Safety Institute
resolved organization: US AI Safety Institute
```

Source segment `s3` input:

```text
[7] An agreement was indeed concluded between the UK and the US in April 2024 to collaborate on at least one joint safety test.
```

Expected result:

```text
mention: s3 | UK
mention: s3 | US
```

Source segment `s4` input:

```text
[8] Initially established in London, the UK AI Safety Institute announced in May 2024 that it would open an office in San Francisco, where many AI companies are located.
```

Expected result:

```text
mention: s4 | UK AI Safety Institute
```

Source segment `s5` input:

```text
This is part of a plan to "set new, international standards on AI safety", according to UK's technology minister Michele Donelan.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s6` input:

```text
[9][10]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-06 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0006` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0006`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
Politico reported in April 2024 that many AI companies had not shared pre-deployment access to their most advanced AI models for evaluation. Meta's president of global affairs Nick Clegg said that many AI companies were waiting for the UK and the US AI Safety Institutes to work out common evaluation rules and procedures. [7] An  agreement  was  indeed  concluded  between  the  UK  and  the  US  in April  2024  to collaborate on at least one joint safety test. [8] Initially established in London, the UK AI Safety Institute announced in May 2024 that it would open an office in San Francisco, where many AI companies are located.  This  is  part  of  a  plan  to  "set  new,  international  standards  on  AI  safety",  according  to  UK's technology minister Michele Donelan. [9][10]
```

Provisional expected semantic result:

> Identify the April 2024 UK–US collaboration agreement.

Class: `direct`

Anchor: `agreement ... to collaborate on at least one joint safety test`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph names two institutes in one agreement.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Politico reported in April 2024 that many AI companies had not shared pre-deployment access to their most advanced AI models for evaluation.
```

Expected result:

```text
mention: s1 | Politico
```

Source segment `s2` input:

```text
Meta's president of global affairs Nick Clegg said that many AI companies were waiting for the UK and the US AI Safety Institutes to work out common evaluation rules and procedures.
```

Expected result:

```text
mention: s2 | Meta
```

Aspirational context-resolved Organizations, which are not contiguous literal spans and therefore are not scored by the current PHP-1 exact-span oracle:

```text
resolved organization: Meta
resolved organization: UK AI Safety Institute
resolved organization: US AI Safety Institute
```

Source segment `s3` input:

```text
[7] An agreement was indeed concluded between the UK and the US in April 2024 to collaborate on at least one joint safety test.
```

Expected result:

```text
mention: s3 | UK
mention: s3 | US
```

Source segment `s4` input:

```text
[8] Initially established in London, the UK AI Safety Institute announced in May 2024 that it would open an office in San Francisco, where many AI companies are located.
```

Expected result:

```text
mention: s4 | UK AI Safety Institute
```

Source segment `s5` input:

```text
This is part of a plan to "set new, international standards on AI safety", according to UK's technology minister Michele Donelan.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s6` input:

```text
[9][10]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-07 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0009` p. 1

Current reanchored node: `nod_29c11f54a9a08065139530f3_0009`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
In  July  2025,  the  international  network  held  an  exercise  to  explore  issues  with  evaluating AI  agents, especially when it came to leaking sensitive information or cybersecurity. [11]  Network members also met at NeurIPS 2025 in the city of San Diego. [12]
```

Provisional expected semantic result:

> Identify the network exercise and its two stated risk themes.

Class: `event`

Anchor: `exercise to explore issues`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns an event and risk themes.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In July 2025, the international network held an exercise to explore issues with evaluating AI agents, especially when it came to leaking sensitive information or cybersecurity.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
[11] Network members also met at NeurIPS 2025 in the city of San Diego.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
[12]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-08 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0012` p. 2

Current reanchored node: `nod_29c11f54a9a08065139530f3_0012`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The Albanese government announced the creation of the Australian AI Safety Institute on 25 November 2025. [13] The  institute  is  housed  within  the  Department  of  Industry,  Science  and  Resources [14] and  is supported by a budget of A$29,900,000 over four years. [14] Its general manager is Kate Conroy, who is also the lead of responsible AI in the Royal Australian Air Force. [14]
```

Provisional expected semantic result:

> Separate Australian institute creation, departmental placement, budget, and named leadership.

Class: `multiple`

Anchor: `housed within the Department`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph combines placement, budget, and leadership.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The Albanese government announced the creation of the Australian AI Safety Institute on 25 November 2025.
```

Expected result:

```text
mention: s1 | Albanese government
mention: s1 | Australian AI Safety Institute
```

Source segment `s2` input:

```text
[13] The institute is housed within the Department of Industry, Science and Resources [14] and is supported by a budget of A$29,900,000 over four years.
```

Expected result:

```text
mention: s2 | Department of Industry, Science and Resources
```

Source segment `s3` input:

```text
[14] Its general manager is Kate Conroy, who is also the lead of responsible AI in the Royal Australian Air Force.
```

Expected result:

```text
mention: s3 | Royal Australian Air Force
```

Source segment `s4` input:

```text
[14]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-09 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0014` p. 2

Current reanchored node: `nod_29c11f54a9a08065139530f3_0014`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
Canada announced in April 2024 that it would create an AI safety institute, [15] and such an institute was officially  founded  in  November  2024. [16] The  institute  is  housed  under  Innovation,  Science  and Economic  Development  Canada,  though  it  also  partners  with  the  Canadian  Institute  for  Advanced Research (CIFAR). [16] It is supported by a budget of CA$50,000,000 for a five-year timespan. [16]
```

Provisional expected semantic result:

> Identify the Canadian institute–CIFAR partnership and retain its government placement.

Class: `direct`

Anchor: `partners with the Canadian Institute`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states a named partnership.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Canada announced in April 2024 that it would create an AI safety institute, [15] and such an institute was officially founded in November 2024.
```

Expected result:

```text
mention: s1 | Canada
```

Source segment `s2` input:

```text
[16] The institute is housed under Innovation, Science and Economic Development Canada, though it also partners with the Canadian Institute for Advanced Research (CIFAR).
```

Expected result:

```text
mention: s2 | Innovation, Science and Economic Development Canada
mention: s2 | Canadian Institute for Advanced Research (CIFAR)
```

Source segment `s3` input:

```text
[16] It is supported by a budget of CA$50,000,000 for a five-year timespan.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[16]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-10 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0020` p. 2

Current reanchored node: `nod_29c11f54a9a08065139530f3_0020`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute. The decision was made to shift focus from  regulation  to  standards-setting,  risk  identification,  and  damage  detection-all  of  which  require interoperable technologies. The AISI may spend the ₹ 20 crore allotted to the Safe and Trusted Pillar of the  IndiaAI  Mission  for  the  initial  budget.  Future  funding  may  come  from  other  components  of  the IndiaAI Mission. [19][20]
```

Provisional expected semantic result:

> Enumerate the consultation participants without collapsing them into one entity.

Class: `high-cardinality`

Anchor: `held consultations with`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph enumerates many consultation participants.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.
```

Expected result:

```text
mention: s1 | Ministry of Electronics and Information Technology
mention: s1 | Meta Platforms
mention: s1 | Google
mention: s1 | Microsoft
mention: s1 | IBM
mention: s1 | OpenAI
mention: s1 | NASSCOM
mention: s1 | Broadband India Forum
mention: s1 | Software Alliance
mention: s1 | Indian Institutes of Technology (IITs)
mention: s1 | The Quantum Hub
mention: s1 | Digital Empowerment Foundation
mention: s1 | Access Now
mention: s1 | AI Safety Institute
```

Source segment `s2` input:

```text
The decision was made to shift focus from regulation to standards-setting, risk identification, and damage detection-all of which require interoperable technologies.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
The AISI may spend the ₹ 20 crore allotted to the Safe and Trusted Pillar of the IndiaAI Mission for the initial budget.
```

Expected result:

```text
mention: s3 | AISI
```

Review difficulty: `external_knowledge_sensitive`.

`IndiaAI Mission` is an initiative rather than an Organization, but this segment does not explain that entity type.
Treating it as an Organization is a lower-severity error than contradicting an explicit type in the segment.

Source segment `s4` input:

```text
Future funding may come from other components of the IndiaAI Mission.
```

Expected result:

```text
abstain: no literal organization mention
```

Review difficulty: `external_knowledge_sensitive`.

`IndiaAI Mission` is an initiative rather than an Organization, but this segment does not explain that entity type.

Source segment `s5` input:

```text
[19][20]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-11 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0020` p. 2

Current reanchored node: `nod_29c11f54a9a08065139530f3_0020`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute. The decision was made to shift focus from  regulation  to  standards-setting,  risk  identification,  and  damage  detection-all  of  which  require interoperable technologies. The AISI may spend the ₹ 20 crore allotted to the Safe and Trusted Pillar of the  IndiaAI  Mission  for  the  initial  budget.  Future  funding  may  come  from  other  components  of  the IndiaAI Mission. [19][20]
```

Provisional expected semantic result:

> Preserve the three new focus areas and the stated need for interoperable technologies.

Class: `policy change`

Anchor: `shift focus from regulation`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns policy priorities.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.
```

Expected result:

```text
mention: s1 | Ministry of Electronics and Information Technology
mention: s1 | Meta Platforms
mention: s1 | Google
mention: s1 | Microsoft
mention: s1 | IBM
mention: s1 | OpenAI
mention: s1 | NASSCOM
mention: s1 | Broadband India Forum
mention: s1 | Software Alliance
mention: s1 | Indian Institutes of Technology (IITs)
mention: s1 | The Quantum Hub
mention: s1 | Digital Empowerment Foundation
mention: s1 | Access Now
mention: s1 | AI Safety Institute
```

Source segment `s2` input:

```text
The decision was made to shift focus from regulation to standards-setting, risk identification, and damage detection-all of which require interoperable technologies.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
The AISI may spend the ₹ 20 crore allotted to the Safe and Trusted Pillar of the IndiaAI Mission for the initial budget.
```

Expected result:

```text
mention: s3 | AISI
```

Review difficulty: `external_knowledge_sensitive`.

`IndiaAI Mission` is an initiative rather than an Organization, but this segment does not explain that entity type.
Treating it as an Organization is a lower-severity error than contradicting an explicit type in the segment.

Source segment `s4` input:

```text
Future funding may come from other components of the IndiaAI Mission.
```

Expected result:

```text
abstain: no literal organization mention
```

Review difficulty: `external_knowledge_sensitive`.

`IndiaAI Mission` is an initiative rather than an Organization, but this segment does not explain that entity type.

Source segment `s5` input:

```text
[19][20]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-12 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0021` p. 2

Current reanchored node: `nod_29c11f54a9a08065139530f3_0021`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
UNESCO  and  MeitY  began  consulting  on  AI  Readiness  Assessment  Methodology  under  Safety  and Ethics  in Artificial  Intelligence  from  2024.  It  is  to  encourage  the  ethical  and  responsible  use  of AI  in industries. The study will find areas where government can become involved, especially in attempts to strengthen institutional and regulatory capabilities. [21][22]
```

Provisional expected semantic result:

> Identify the two parties and the named assessment methodology.

Class: `direct`

Anchor: `UNESCO and MeitY began consulting`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph names UNESCO and MeitY.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
UNESCO and MeitY began consulting on AI Readiness Assessment Methodology under Safety and Ethics in Artificial Intelligence from 2024.
```

Expected result:

```text
mention: s1 | UNESCO
mention: s1 | MeitY
```

Source segment `s2` input:

```text
It is to encourage the ethical and responsible use of AI in industries.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
The study will find areas where government can become involved, especially in attempts to strengthen institutional and regulatory capabilities.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[21][22]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-13 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0022` pp. 2–3

Current reanchored node: `nod_29c11f54a9a08065139530f3_0022`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
Minister  for  Electronics  &  Information  Technology  Ashwini  Vaishnaw  announced  the  creation  of  an IndiaAI Safety Institute on January 30, 2025, to ensure the ethical and safe application of AI models. The institute will promote domestic R&D that is grounded in India's social, economic, cultural, and linguistic diversity and is based on Indian datasets. With the help of academic and research institutions, as well as private sector partners, the institute will follow the hub-and-spoke approach to carry out projects within Safe and Trusted Pillar of the IndiaAI Mission. [23][24] It  operates  under a "hub-and-spoke" model with collaboration  from  academic  institutions  (e.g.,  IITs),  tech  firms,  and  international  organizations  like UNESCO. [25]
```

Provisional expected semantic result:

> Identify the IndiaAI Safety Institute's creation, mission, and collaboration model without treating every participant as a founder.

Class: `organizational model`

Anchor: `hub-and-spoke`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph combines creation, mission, and collaboration.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Minister for Electronics & Information Technology Ashwini Vaishnaw announced the creation of an IndiaAI Safety Institute on January 30, 2025, to ensure the ethical and safe application of AI models.
```

Expected result:

```text
mention: s1 | IndiaAI Safety Institute
```

Source segment `s2` input:

```text
The institute will promote domestic R&D that is grounded in India's social, economic, cultural, and linguistic diversity and is based on Indian datasets.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
With the help of academic and research institutions, as well as private sector partners, the institute will follow the hub-and-spoke approach to carry out projects within Safe and Trusted Pillar of the IndiaAI Mission.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[23][24] It operates under a "hub-and-spoke" model with collaboration from academic institutions (e.g., IITs), tech firms, and international organizations like UNESCO.
```

Expected result:

```text
mention: s4 | IITs
mention: s4 | UNESCO
```

Source segment `s5` input:

```text
[25]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-14 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0029` p. 3

Current reanchored node: `nod_29c11f54a9a08065139530f3_0029`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The Digital Trust  Centre  was  initially  founded  in  June  2022. [28] In  May  2024,  it  was  renamed  to  the Singapore  AISI. [28] Part  of  Nanyang  Technological  University,  the  institute  partners  with  Infocomm Media Development Authority [28] and is supported by an investment of S$10,000,000 per year. [15]
```

Provisional expected semantic result:

> Identify the Digital Trust Centre-to-Singapore-AISI rename, NTU placement, and IMDA partnership separately.

Class: `identity lineage`

Anchor: `renamed to the Singapore AISI`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states rename, placement, and partnership relations.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The Digital Trust Centre was initially founded in June 2022.
```

Expected result:

```text
mention: s1 | Digital Trust Centre
```

Source segment `s2` input:

```text
[28] In May 2024, it was renamed to the Singapore AISI.
```

Expected result:

```text
mention: s2 | Singapore AISI
```

Source segment `s3` input:

```text
[28] Part of Nanyang Technological University, the institute partners with Infocomm Media Development Authority [28] and is supported by an investment of S$10,000,000 per year.
```

Expected result:

```text
mention: s3 | Nanyang Technological University
mention: s3 | Infocomm Media Development Authority
```

Source segment `s4` input:

```text
[15]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-15 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0033` p. 3

Current reanchored node: `nod_29c11f54a9a08065139530f3_0033`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The United Kingdom  founded in April 2023 a safety organisation  called Frontier  AI  Taskforce ,  with  an  initial budget of £100 million. [31] In November 2023, it evolved into the  AI  Safety  Institute,  and  continued  to  be  led  by  Ian Hogarth. The AISI is part of the United Kingdom's Department for Science, Innovation and Technology. [5]
```

Provisional expected semantic result:

> Preserve UK Taskforce lineage, leadership continuity, and Department for Science placement.

Class: `multiple`

Anchor: `continued to be led by Ian Hogarth`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states organization lineage and placement.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The United Kingdom founded in April 2023 a safety organisation called Frontier AI Taskforce , with an initial budget of £100 million.
```

Expected result:

```text
mention: s1 | United Kingdom
mention: s1 | Frontier AI Taskforce
```

Source segment `s2` input:

```text
[31] In November 2023, it evolved into the AI Safety Institute, and continued to be led by Ian Hogarth.
```

Expected result:

```text
mention: s2 | AI Safety Institute
```

Source segment `s3` input:

```text
The AISI is part of the United Kingdom's Department for Science, Innovation and Technology.
```

Expected result:

```text
mention: s3 | AISI
mention: s3 | United Kingdom's Department for Science, Innovation and Technology
```

Source segment `s4` input:

```text
[5]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ai-15-aisi-dsit`

Candidate pair: `AISI` / `United Kingdom's Department for Science, Innovation and Technology`

Bounded Source-segment input:

```text
The AISI is part of the United Kingdom's Department for Science, Innovation and Technology.
```

Expected result:

```text
claim: s3 | AISI | is part of | United Kingdom's Department for Science, Innovation and Technology
```

### AI-16 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0035` p. 4

Current reanchored node: `nod_29c11f54a9a08065139530f3_0035`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
In  May  2024,  the  institute  open-sourced  an AI  safety  tool  called  "Inspect",  which  evaluates AI  model capabilities such as reasoning and their degree of autonomy. [32]
```

Provisional expected semantic result:

> Identify the institute's publication and the tool's stated evaluation capabilities.

Class: `product capability`

Anchor: `open-sourced an AI safety tool called...Inspect`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns a tool and its capabilities.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In May 2024, the institute open-sourced an AI safety tool called "Inspect", which evaluates AI model capabilities such as reasoning and their degree of autonomy.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
[32]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-17 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0036` p. 4

Current reanchored node: `nod_29c11f54a9a08065139530f3_0036`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
In February 2025, the UK body was renamed the AI Security Institute. Observers saw the name change as a signal that the institute will not focus on ethical issues such as algorithmic bias or freedom of speech in AI applications. [33]
```

Provisional expected semantic result:

> Keep the inferred future focus attributed to observers.

Class: `interpretation control`

Anchor: `Observers saw the name change`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests attributed interpretation.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In February 2025, the UK body was renamed the AI Security Institute.
```

Expected result:

```text
mention: s1 | AI Security Institute
```

Source segment `s2` input:

```text
Observers saw the name change as a signal that the institute will not focus on ethical issues such as algorithmic bias or freedom of speech in AI applications.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
[33]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-18 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0038` p. 4

Current reanchored node: `nod_29c11f54a9a08065139530f3_0038`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The  US  AISI  was  founded  in  November  2023  as  part  of  the  National  Institute  of  Standards  and Technology  (NIST).  This  happened  the  day  after  the  signature  of  the  Executive  Order  14110. [34] In February 2024, Joe Biden's former economic policy adviser Elizabeth Kelly was appointed to lead it. [35]
```

Provisional expected semantic result:

> Identify the November 2023 founding, NIST placement, and Elizabeth Kelly leadership.

Class: `direct multiple`

Anchor: `US AISI was founded`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states organization founding and placement.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The US AISI was founded in November 2023 as part of the National Institute of Standards and Technology (NIST).
```

Expected result:

```text
mention: s1 | US AISI
mention: s1 | National Institute of Standards and Technology (NIST)
```

Source segment `s2` input:

```text
This happened the day after the signature of the Executive Order 14110.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
[34] In February 2024, Joe Biden's former economic policy adviser Elizabeth Kelly was appointed to lead it.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[35]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-ai-18-us-aisi-nist`

Candidate pair: `US AISI` / `National Institute of Standards and Technology (NIST)`

Bounded Source-segment input:

```text
The US AISI was founded in November 2023 as part of the National Institute of Standards and Technology (NIST).
```

Expected result:

```text
claim: s1 | US AISI | was founded in November 2023 as part of | National Institute of Standards and Technology (NIST)
```

### AI-19 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0039` p. 4

Current reanchored node: `nod_29c11f54a9a08065139530f3_0039`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft. [36]
```

Provisional expected semantic result:

> Identify AISIC creation and named examples without inventing membership beyond the source.

Class: `high-cardinality`

Anchor: `more than 200 organizations such as Google, Anthropic or Microsoft`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph lists many potential member organizations.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.
```

Expected result:

```text
mention: s1 | US government
mention: s1 | US AI Safety Institute Consortium (AISIC)
mention: s1 | Google
mention: s1 | Anthropic
mention: s1 | Microsoft
```

Source segment `s2` input:

```text
[36]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-20 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0041` p. 4

Current reanchored node: `nod_29c11f54a9a08065139530f3_0041`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
Under President Trump, plans for members of the agency to attend the February 2025 AI Action Summit in Paris were scrapped. [40] The US and the UK refused to sign the summit's final communique. US Vice President JD Vance said "pro-growth AI policies" should be prioritised over safety. [41]
```

Provisional expected semantic result:

> Identify the US and UK refusal separately from JD Vance's attributed policy position.

Class: `multiple`

Anchor: `refused to sign the summit's final communique`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns a diplomatic refusal and position.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Under President Trump, plans for members of the agency to attend the February 2025 AI Action Summit in Paris were scrapped.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
[40] The US and the UK refused to sign the summit's final communique.
```

Expected result:

```text
US
UK
```

Source segment `s3` input:

```text
US Vice President JD Vance said "pro-growth AI policies" should be prioritised over safety.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
[41]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### AI-21 — reviewed packet item

Packet locator: `nod_10c2e7b4f6020f1a3a68d389_0042` p. 4

Current reanchored node: `nod_29c11f54a9a08065139530f3_0042`

Current representation: `rep_29c11f54a9a08065139530f3`

Locked PDF SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`

Complete authoritative paragraph text:

```text
The name of the agency was changed in June 2025 to the Center for AI Standards and Innovation (CAISI) and its mission transformed. [42] According to Secretary of Commerce Howard Lutnick, "For far too long, censorship and regulations have been used under the guise of national security. Innovators will no longer be  limited  by  these  standards.  CAISI  will  evaluate  and  enhance  US  innovation  of  these  rapidly developing  commercial  AI  systems  while  ensuring  they  remain  secure  to  our  national  security standards." [43][44] The  United  States  Department  of  Commerce  stated  that  CAISI  would  represent American  interests  internationally,  guarding  against  burdensome  and  unnecessary  regulation  of  US technologies by foreign governments. It collaborates with the NIST Information Technology Laboratory. [44]
```

Provisional expected semantic result:

> Identify the CAISI rename and transformed mission while preserving Commerce and Lutnick attribution.

Class: `identity and attribution`

Anchor: `name of the agency was changed`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph combines rename, mission, and attribution.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The name of the agency was changed in June 2025 to the Center for AI Standards and Innovation (CAISI) and its mission transformed.
```

Expected result:

```text
mention: s1 | Center for AI Standards and Innovation (CAISI)
```

Source segment `s2` input:

```text
[42] According to Secretary of Commerce Howard Lutnick, "For far too long, censorship and regulations have been used under the guise of national security. Innovators will no longer be limited by these standards. CAISI will evaluate and enhance US innovation of these rapidly developing commercial AI systems while ensuring they remain secure to our national security standards." [43][44] The United States Department of Commerce stated that CAISI would represent American interests internationally, guarding against burdensome and unnecessary regulation of US technologies by foreign governments.
```

Expected result:

```text
mention: s2 | CAISI
mention: s2 | United States Department of Commerce
mention: s2 | CAISI
```

Source segment `s3` input:

```text
It collaborates with the NIST Information Technology Laboratory.
```

Expected result:

```text
mention: s3 | NIST Information Technology Laboratory
```

Source segment `s4` input:

```text
[44]
```

Expected result:

```text
not_applicable_nonlexical
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-01 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0006` p. 1

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0006`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
On November 21 and 22, 2024, technical artificial intelligence (AI) experts from nine countries and the European Union will meet for the first time in San Francisco. The agenda: starting the next phase of international cooperation on AI safety science through a network of AI safety institutes (AISIs). The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit. At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document. However, a September announcement by Raimondo and U.S. secretary of state Antony Blinken confirmed that Kenya would instead be the final member of the AISI International Network at this stage.
```

Provisional expected semantic result:

> Identify the named initial network members, launch event, and later Kenya confirmation without treating Italy and Germany as members.

Class: `high-cardinality and temporal`

Anchor: `initial members of the network`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph lists members, events, and later status.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
On November 21 and 22, 2024, technical artificial intelligence (AI) experts from nine countries and the European Union will meet for the first time in San Francisco.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
The agenda: starting the next phase of international cooperation on AI safety science through a network of AI safety institutes (AISIs).
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.
```

Expected result:

```text
mention: s3 | United States
mention: s3 | United Kingdom
mention: s3 | European Union
mention: s3 | Japan
mention: s3 | Singapore
mention: s3 | South Korea
mention: s3 | Canada
mention: s3 | France
mention: s3 | Kenya
mention: s3 | Australia
```

Source segment `s4` input:

```text
At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.
```

Expected result:

```text
mention: s4 | Italy
mention: s4 | Germany
```

Source segment `s5` input:

```text
However, a September announcement by Raimondo and U.S. secretary of state Antony Blinken confirmed that Kenya would instead be the final member of the AISI International Network at this stage.
```

Expected result:

```text
mention: s5 | Kenya
mention: s5 | AISI International Network
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-02 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0008` p. 2

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0008`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
According to the Seoul Statement, the international network will serve to 'accelerate the advancement of the science of AI safety' at a global level by promoting 'complementarity and interoperability' between institutes and fostering a 'common international understanding' of AI safety approaches. While the statement does not define specific goals or mechanisms for AISI collaboration, it suggests that they 'may include' coordinating research, sharing resources and relevant information, developing best practices, and exchanging or codeveloping AI model evaluations. Now, in the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.
```

Provisional expected semantic result:

> Preserve the statement attribution and its `may include` modality for proposed collaboration mechanisms.

Class: `attribution and modality control`

Anchor: `According to the Seoul Statement`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests attribution and modality.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
According to the Seoul Statement, the international network will serve to 'accelerate the advancement of the science of AI safety' at a global level by promoting 'complementarity and interoperability' between institutes and fostering a 'common international understanding' of AI safety approaches.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
While the statement does not define specific goals or mechanisms for AISI collaboration, it suggests that they 'may include' coordinating research, sharing resources and relevant information, developing best practices, and exchanging or codeveloping AI model evaluations.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
Now, in the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.
```

Expected result:

```text
mention: s3 | AISI network
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-03 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0031` p. 4

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0031`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
Since 2023, governments around the world have mobilized around AI's rapidly growing capabilities and potential risks. As part of this effort, several governments have launched AI safety institutes, publicly funded research institutions focused on mitigating risks from the frontier of AI development. AISIs provide governments with in-house technical expertise and organizational capacity to evaluate and monitor cutting-edge AI models for risks to public and national security.
```

Provisional expected semantic result:

> Identify the report's stated AISI purpose and government technical-capacity role.

Class: `direct`

Anchor: `publicly funded research institutions`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph defines a report purpose.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Since 2023, governments around the world have mobilized around AI's rapidly growing capabilities and potential risks.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
As part of this effort, several governments have launched AI safety institutes, publicly funded research institutions focused on mitigating risks from the frontier of AI development.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
AISIs provide governments with in-house technical expertise and organizational capacity to evaluate and monitor cutting-edge AI models for risks to public and national security.
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-04 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0032` p. 4

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0032`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
AISIs have been tasked by governments with a wide-ranging mandate to address the complex challenges posed by advanced AI systems. They will perform foundational technical research, develop guidance for the public and private sectors, and work closely with companies to test models before deployment. While it is unusual for a single government entity to tackle all three of these functions at once, the breakneck speed of AI development and the staggering number of open questions in the field of AI safety research mean that governments require in-house capacity on each of them. According to Kelly , it is important that these three functions-research, testing, and guidance-reinforce each other to form a 'virtuous' cycle (Figure 1):
```

Provisional expected semantic result:

> Decompose the three functions without claiming they are already complete outcomes.

Class: `multiple`

Anchor: `research, testing, and guidance`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph lists functions rather than organization relations.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
AISIs have been tasked by governments with a wide-ranging mandate to address the complex challenges posed by advanced AI systems.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
They will perform foundational technical research, develop guidance for the public and private sectors, and work closely with companies to test models before deployment.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
While it is unusual for a single government entity to tackle all three of these functions at once, the breakneck speed of AI development and the staggering number of open questions in the field of AI safety research mean that governments require in-house capacity on each of them.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
According to Kelly , it is important that these three functions-research, testing, and guidance-reinforce each other to form a 'virtuous' cycle (Figure 1):
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-05 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0037` p. 5

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0037`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
AISIs are engaging a wide range of stakeholders on each of their core functions. Far from fearing the launch of AISIs worldwide, firms and universities engaged in advanced AI have called for governments to increase their capacity to perform AI research, conduct testing, and issue guidance. Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members. AISIC is composed of over 200 organizations from across the private sector, academia, civil society, and government and facilitates collaboration on AI safety research and evaluations. Members are expected to contribute to one of nine key areas of guidance , reproduced verbatim below:
```

Provisional expected semantic result:

> Identify Anthropic's AISIC membership and distinguish the Consortium from the generic AISI name.

Class: `cross-source direct`

Anchor: `Anthropic ... joined the U.S. AISI Consortium`

Current PHP-1 eligibility: `eligible`

Eligibility rationale: The paragraph states a named consortium membership.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
AISIs are engaging a wide range of stakeholders on each of their core functions.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
Far from fearing the launch of AISIs worldwide, firms and universities engaged in advanced AI have called for governments to increase their capacity to perform AI research, conduct testing, and issue guidance.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.
```

Expected result:

```text
mention: s3 | Google
mention: s3 | Microsoft
mention: s3 | Anthropic
mention: s3 | Amazon
mention: s3 | U.S. AISI Consortium (AISIC)
```

Source segment `s4` input:

```text
AISIC is composed of over 200 organizations from across the private sector, academia, civil society, and government and facilitates collaboration on AI safety research and evaluations.
```

Expected result:

```text
mention: s4 | AISIC
```

Source segment `s5` input:

```text
Members are expected to contribute to one of nine key areas of guidance , reproduced verbatim below:
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

Expectation: `php1-target-cs-05-google-aisic`

Candidate pair: `Google` / `U.S. AISI Consortium (AISIC)`

Bounded Source-segment input:

```text
Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.
```

Expected result:

```text
claim: s3 | Google | joined | U.S. AISI Consortium (AISIC)
```

Expectation: `php1-target-cs-05-microsoft-aisic`

Candidate pair: `Microsoft` / `U.S. AISI Consortium (AISIC)`

Bounded Source-segment input:

```text
Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.
```

Expected result:

```text
claim: s3 | Microsoft | joined | U.S. AISI Consortium (AISIC)
```

Expectation: `php1-target-cs-05-anthropic-aisic`

Candidate pair: `Anthropic` / `U.S. AISI Consortium (AISIC)`

Bounded Source-segment input:

```text
Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.
```

Expected result:

```text
claim: s3 | Anthropic | joined | U.S. AISI Consortium (AISIC)
```

Expectation: `php1-target-cs-05-amazon-aisic`

Candidate pair: `Amazon` / `U.S. AISI Consortium (AISIC)`

Bounded Source-segment input:

```text
Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.
```

Expected result:

```text
claim: s3 | Amazon | joined | U.S. AISI Consortium (AISIC)
```

### CS-06 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0051` p. 6

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0051`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
In August, OpenAI chief executive officer Sam Altman stated that his company has been working closely with the U.S. AISI on an agreement to provide early access to its next foundation model for safety testing and evaluations. OpenAI is not alone in providing the U.S. AISI access to its models for testing. Director Kelly said that the institute has 'commitments from all of the leading frontier model developers to work with them on these tests.' These commitments demonstrate that leading companies understand the need for AI safety research and recognize the important role that the U.S. AISI has to play. While critics have questioned how industry will balance competition and safety, AISIs are free from the financial self-interest which has caused some to question the adequacy of private AI safety efforts in the past.
```

Provisional expected semantic result:

> Preserve Altman's statement about OpenAI's early-access agreement and Kelly's separate statement about commitments.

Class: `attributed direct`

Anchor: `Sam Altman stated`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph contains separate attributed statements.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In August, OpenAI chief executive officer Sam Altman stated that his company has been working closely with the U.S. AISI on an agreement to provide early access to its next foundation model for safety testing and evaluations.
```

Expected result:

```text
mention: s1 | OpenAI
mention: s1 | U.S. AISI
```

Source segment `s2` input:

```text
OpenAI is not alone in providing the U.S. AISI access to its models for testing.
```

Expected result:

```text
mention: s2 | OpenAI
mention: s2 | U.S. AISI
```

Source segment `s3` input:

```text
Director Kelly said that the institute has 'commitments from all of the leading frontier model developers to work with them on these tests.'
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
These commitments demonstrate that leading companies understand the need for AI safety research and recognize the important role that the U.S. AISI has to play.
```

Expected result:

```text
mention: s4 | U.S. AISI
```

Source segment `s5` input:

```text
While critics have questioned how industry will balance competition and safety, AISIs are free from the financial self-interest which has caused some to question the adequacy of private AI safety efforts in the past.
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-07 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0052` p. 6

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0052`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year. The letter, which was led by Americans for Responsible Innovation and the Information Technology Industry Council (ITI), states that "[a]s other nations around the world are establishing their own AI Safety Institutes, furthering NIST's ongoing efforts is essential to advancing U.S. AI innovation, leadership, and national security." "Authorizing legislation, and the accompanying necessary resources,' it argues, 'will give much needed certainty to NIST's role in AI safety and reliability.'
```

Provisional expected semantic result:

> Identify the named companies, the letter's organizers, and the request without presenting the letter's advocacy as established fact.

Class: `high-cardinality and quotation`

Anchor: `signed a letter to Congress`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph lists signatories, organizers, and a request.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year.
```

Expected result:

```text
mention: s1 | Amazon
mention: s1 | Meta
mention: s1 | Microsoft
mention: s1 | OpenAI
mention: s1 | Congress
mention: s1 | U.S. AISI
```

Source segment `s2` input:

```text
The letter, which was led by Americans for Responsible Innovation and the Information Technology Industry Council (ITI), states that "[a]s other nations around the world are establishing their own AI Safety Institutes, furthering NIST's ongoing efforts is essential to advancing U.S. AI innovation, leadership, and national security." "Authorizing legislation, and the accompanying necessary resources,' it argues, 'will give much needed certainty to NIST's role in AI safety and reliability.'
```

Expected result:

```text
mention: s2 | Americans for Responsible Innovation
mention: s2 | Information Technology Industry Council (ITI)
mention: s2 | NIST
mention: s2 | NIST
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-08 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0059` p. 7

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0059`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
The first AISIs were announced last year, with the United States and United Kingdom launching initiatives at the UK AI Safety Summit in November 2023. Japan , Singapore , and the European Union's EU AI Office followed in early 2024. Since then, Canada and South Korea have revealed plans for their own AISIs. The inclusion of France, Kenya, and Australia in the AISI network suggests that more institutes are still to come. For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level. While this program has not yet been named as an official AI safety institute for France, an announcement may take place at the AI Action Summit in France in February 2025, similar to the announcement made by South Korea at the AI Seoul Summit in May.
```

Provisional expected semantic result:

> Preserve the report's tentative language about future institutes and France's not-yet-official status.

Class: `inference control`

Anchor: `suggests that more institutes are still to come`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests tentative future inference.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
The first AISIs were announced last year, with the United States and United Kingdom launching initiatives at the UK AI Safety Summit in November 2023.
```

Expected result:

```text
mention: s1 | United States
mention: s1 | United Kingdom
```

Source segment `s2` input:

```text
Japan , Singapore , and the European Union's EU AI Office followed in early 2024.
```

Expected result:

```text
mention: s2 | Japan
mention: s2 | Singapore
mention: s2 | European Union's EU AI Office
```

Source segment `s3` input:

```text
Since then, Canada and South Korea have revealed plans for their own AISIs.
```

Expected result:

```text
mention: s3 | Canada
mention: s3 | South Korea
```

Source segment `s4` input:

```text
The inclusion of France, Kenya, and Australia in the AISI network suggests that more institutes are still to come.
```

Expected result:

```text
mention: s4 | France
mention: s4 | Kenya
mention: s4 | Australia
mention: s4 | AISI network
```

Source segment `s5` input:

```text
For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.
```

Expected result:

```text
mention: s5 | Laboratoire National de Métrologie et d'Essais (LNE)
mention: s5 | National Institute for Research in Digital Science and Technology (Inria)
```

Source segment `s6` input:

```text
While this program has not yet been named as an official AI safety institute for France, an announcement may take place at the AI Action Summit in France in February 2025, similar to the announcement made by South Korea at the AI Seoul Summit in May.
```

Expected result:

```text
mention: s6 | South Korea
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-09 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0251` pp. 12–13

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0251`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
It is worth noting, however, that while institutes share many similarities in funding, size, and functions, they are housed under different kinds of public bodies. Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA). Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University. Finally, as Table 2 illustrates, the EU AI Office has the largest set of functions as an institution that promotes innovation, research, and regulatory compliance to the EU AI Act. The different kinds of home institutions in which AISIs are housed may have implications for the focus and capacity of different network members, and therefore the strengths that each member may bring to the network.
```

Provisional expected semantic result:

> Extract stated institutional homes while retaining the report's qualified claim about possible implications.

Class: `organizational comparison`

Anchor: `housed under different kinds of public bodies`

Current PHP-1 eligibility: `needs_multi_segment`

Eligibility rationale: The paragraph compares several institutional homes.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
It is worth noting, however, that while institutes share many similarities in funding, size, and functions, they are housed under different kinds of public bodies.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).
```

Expected result:

```text
mention: s2 | U.S. National Institute of Standards and Technology (NIST)
mention: s2 | UK Department for Science, Innovation and Technology (DSIT)
mention: s2 | Japanese Information Technology Promotion Agency (IPA)
```

Source segment `s3` input:

```text
Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University.
```

Expected result:

```text
mention: s3 | South Korean Electronics and Telecommunications Research Institute (ETRI)
mention: s3 | Singaporean Digital Trust Centre
mention: s3 | Nanyang Technological University
```

Source segment `s4` input:

```text
Finally, as Table 2 illustrates, the EU AI Office has the largest set of functions as an institution that promotes innovation, research, and regulatory compliance to the EU AI Act.
```

Expected result:

```text
mention: s4 | EU AI Office
```

Source segment `s5` input:

```text
The different kinds of home institutions in which AISIs are housed may have implications for the focus and capacity of different network members, and therefore the strengths that each member may bring to the network.
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-10 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0257` p. 13

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0003`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
Next Steps and Recommendations
```

Provisional expected semantic result:

> Do not convert the authors' proposed project prioritization into a network decision or existing policy.

Class: `recommendation control`

Anchor: `Recommendation`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests a recommendation.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Next Steps and Recommendations
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-11 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0259` p. 13

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0259`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
In the medium term, network members should look to develop a common, evidence-based approach to AISIs' testing and evaluation methodologies. While not all AISIs may necessarily have the same requirements for assessing models, they should at least have a common understanding of what methodologies such as 'red teaming' comprise. Developing a consensus on testing and evaluation methods would help to deconflict and de-duplicate efforts between AISIs and to facilitate other areas of collaboration in the future, such as promoting safety guidelines or developing joint evaluation tools. If the AISI network can start by ensuring that AISIs all speak the same language in AI safety, more elaborate collaboration projects can take place.
```

Provisional expected semantic result:

> Preserve the proposed common methodology and its stated rationale as a recommendation.

Class: `recommendation and modality control`

Anchor: `should look to develop`

Current PHP-1 eligibility: `control`

Eligibility rationale: The paragraph tests recommendation modality.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
In the medium term, network members should look to develop a common, evidence-based approach to AISIs' testing and evaluation methodologies.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s2` input:

```text
While not all AISIs may necessarily have the same requirements for assessing models, they should at least have a common understanding of what methodologies such as 'red teaming' comprise.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
Developing a consensus on testing and evaluation methods would help to deconflict and de-duplicate efforts between AISIs and to facilitate other areas of collaboration in the future, such as promoting safety guidelines or developing joint evaluation tools.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s4` input:

```text
If the AISI network can start by ensuring that AISIs all speak the same language in AI safety, more elaborate collaboration projects can take place.
```

Expected result:

```text
mention: s4 | AISI network
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.

### CS-12 — reviewed packet item

Packet locator: `nod_3b54ac13ce63f97638fd10cd_0264` p. 14

Current reanchored node: `nod_ab8f6792527c6c788e56e1e3_0264`

Current representation: `rep_ab8f6792527c6c788e56e1e3`

Locked PDF SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`

Complete authoritative paragraph text:

```text
Recommendation: There are two big international events related to AI safety on the horizon that offer some initial deadlines for AISI network deliverables. First, the November 2024 San Francisco convening is an obvious date to publicly initiate international collaboration on AI safety. In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports. The February summit, therefore, is an important second date for network deliverables. The AI Action Summit will be the third of its kind since the UK AI Safety Summit last year and offers a high-profile, public venue in which to showcase the AISI network and its work. These two events-in November 2024 and February 2025-are mere moments away in the context of international collaboration. If AISI members can capitalize on their opportunities, however, they could significantly contribute to the network's mission of accelerating AI safety science.
```

Provisional expected semantic result:

> Separate the agencies' quoted convening goal from the report authors' recommendation and forecast.

Class: `attributed event`

Anchor: `Department of Commerce and U.S. Department of State announced`

Current PHP-1 eligibility: `out_of_scope`

Eligibility rationale: The paragraph concerns an attributed event and forecast.

#### Exact PHP-1 mention tasks

Source segment `s1` input:

```text
Recommendation: There are two big international events related to AI safety on the horizon that offer some initial deadlines for AISI network deliverables.
```

Expected result:

```text
mention: s1 | AISI network
```

Source segment `s2` input:

```text
First, the November 2024 San Francisco convening is an obvious date to publicly initiate international collaboration on AI safety.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s3` input:

```text
In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports.
```

Expected result:

```text
mention: s3 | U.S. Department of Commerce
mention: s3 | U.S. Department of State
```

Source segment `s4` input:

```text
The February summit, therefore, is an important second date for network deliverables.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s5` input:

```text
The AI Action Summit will be the third of its kind since the UK AI Safety Summit last year and offers a high-profile, public venue in which to showcase the AISI network and its work.
```

Expected result:

```text
mention: s5 | AISI network
```

Source segment `s6` input:

```text
These two events-in November 2024 and February 2025-are mere moments away in the context of international collaboration.
```

Expected result:

```text
abstain: no literal organization mention
```

Source segment `s7` input:

```text
If AISI members can capitalize on their opportunities, however, they could significantly contribute to the network's mission of accelerating AI safety science.
```

Expected result:

```text
abstain: no literal organization mention
```

#### Exact PHP-1 directed-relation oracle

No complete directed-relation oracle is defined for this case under the current PHP-1 ontology.
