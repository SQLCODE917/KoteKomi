# Organization Mention Held-Out Annotation Packet

- Status: Human-reviewed; ready for deterministic catalog compilation
- Program: [Organization Mention Reconciliation and Resolution Program](2026-08-28-organization-mention-reconciliation-program.md)
- Catalog purpose: held-out evaluation of boundary reconciliation, Organization qualification, and cross-segment acronym and reference resolution
- Selection count: 50 authoritative paragraphs
- Selection source: fresh isolated test ingestions through the public deposited-source path
- Development separation: no selected paragraph contains a V3 Source segment present in `docs/php1-organization-mention-gold-v1.json`

## Annotation instructions

Read the complete authoritative paragraph and list every Organization that the paragraph denotes in this context.

Copy an Organization expression character for character when the complete expression appears in the paragraph.

Prefix a resolved Organization name with `resolved:` when the paragraph uses a discontinuous or context-dependent reference.

Explain every resolved name and its source expression in Reviewer notes.

Repeat a literal expression when it occurs more than once only if each occurrence must become a separate exact Mention in the later machine catalog.

Use `- None` when the paragraph contains no Organization Mention.

Leave the field as the empty `-` placeholder while it is unreviewed.

Use Reviewer notes for hard distinctions such as country-as-government, product versus Organization, initiative versus Organization, or a reference that requires prior context.

The condition tags explain why the paragraph was selected.

They are not expected answers and must not influence the Gold labels.

## Selection coverage

The packet includes exact and overlapping boundary questions, parenthetical names and acronyms, possessives and geographic qualifiers, countries and supranational actors, organizations versus products or initiatives, generic and pronominal references, collective references, and negative controls.

The packet is a reviewed human oracle.

A deterministic compiler must create exact spans and typed reference-resolution expectations before an automated benchmark uses it.

## HO-001

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0002`
- Paragraph text SHA-256: `377c75c2999935fb1984a2c1a6761a73798539536409742f95cd527cc40f3eb5`
- Source pages: 1
- Section path: Anthropic-United States Department of Defense dispute
- Selection conditions: `country_or_supranational`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Hegseth, the United States secretary of defense, has publicly rebuked Anthropic chief executive Dario Amodei's approach to artificial intelligence.
```

### Gold Organization Mentions

- Anthropic

### Reviewer notes



## HO-002

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0003`
- Paragraph text SHA-256: `86ba43dd74f414301968e6caca8a1aba6ddd61895d412266d69c158eea552116`
- Source pages: 1
- Section path: Anthropic-United States Department of Defense dispute
- Selection conditions: `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`

### Complete authoritative paragraph text

```text
Since  January  2026,  the  United  States  Department  of  Defense  has  conflicted  with  the  artificial intelligence  company Anthropic  over  the  use  of  its  products  for  military  purposes  and  mass  domestic surveillance.
```

### Gold Organization Mentions

- United  States  Department  of  Defense
- Anthropic

### Reviewer notes



## HO-003

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0012`
- Paragraph text SHA-256: `0338f74b8efaea1dbb6d74bdbd6eb4e00a01626af369a3c2bf12b0f14a684bf4`
- Source pages: 2
- Section path: Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration
- Selection conditions: `collective_agent_typing`, `coordinated_names`, `country_or_supranational`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord". As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with  the  Trump  administration  to  avoid  punishment.  David  Sacks,  Trump's  advisor  for  artificial intelligence  and  cryptocurrency,  said  on All-In (2020-present)  that Anthropic  was  among  several  "AI doomers"  that  support  regulation  he  saw  as  overly  restrictive.  According  to The  Wall  Street  Journal , officials close to Sacks examined whether Anthropic's Claude was a "woke AI"; in July, Trump signed an executive order "Preventing Woke AI in the Federal Government ". [15]
```

### Gold Organization Mentions

- Anthropic
- Facebook
- Trump administration
- Skadden
- Arps
- Slate
- Meagher & Flom
- Latham & Watkins
- Trump  administration
- Anthropic
- The  Wall  Street  Journal

### Reviewer notes

Multiple mentions of "Anthropic".
"Anthropic's Claude" I'm leaving out because it's a reference to the product, but not an explicit mention of the Anthropic company.

## HO-004

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0013`
- Paragraph text SHA-256: `c608ac71f813d95607a005494b5cc90fb949590778631fcec2e34bf09e57327a`
- Source pages: 2
- Section path: Anthropic-United States Department of Defense dispute > Background > Anthropic in the second Trump administration
- Selection conditions: `collective_agent_typing`, `coordinated_names`, `country_or_supranational`, `organization_or_nonorganization`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his  hiring  of  Biden  officials;  and  Anthropic's  association  with  the  philanthropic  initiative  Open Philanthropy as evidence that Anthropic would not support Trump's agenda. [15] In October 2025, Sacks stated that  Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration  on  Anthropic's  policies,  intensifying  the  dispute.  Amodei's  statement  included  views explicitly espoused by vice president JD Vance. [17]  In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration. [18]
```

### Gold Organization Mentions

- World Economic Forum
- Anthropic
- Open Philanthropy
- Anthropic
- Anthropic
- Trump administration
- Anthropic
- Anthropic
- Trump administration

### Reviewer notes

World Economic Forum is an Organization, even though it might sound like an event. All five literal Anthropic expressions denote the company.

## HO-005

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0018`
- Paragraph text SHA-256: `fb3661d0d43a3966fa48c039d9f5f4cd6f9878f93d640ec0db1401d22330ad9c`
- Source pages: 3
- Section path: Anthropic-United States Department of Defense dispute > Dispute
- Selection conditions: `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`

### Complete authoritative paragraph text

```text
Michael told reporters that Anthropic should "cross the Rubicon" and allow the Department of Defense to dictate the terms of how its technology is used. [32] The position of the Department of Defense, and its tactics during the dispute, were widely criticized on grounds including violating the principles of rule-oflaw, market independence and national security. [33][34]
```

### Gold Organization Mentions

- Anthropic
- Department of Defense
- Department of Defense

### Reviewer notes



## HO-006

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0021`
- Paragraph text SHA-256: `af5146ef1fb3234e596bb2944db14ef2d93ebbcf973fc5fef1e09ce3e93adc14`
- Source pages: 3
- Section path: Anthropic-United States Department of Defense dispute > Impact
- Selection conditions: `country_or_supranational`

### Complete authoritative paragraph text

```text
The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars. [39]
```

### Gold Organization Mentions

- 1789 Capital
- Anthropic

### Reviewer notes



## HO-007

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0022`
- Paragraph text SHA-256: `0ec18a94e536a91da22ec17ff7ccbc058baf7bde7ee8b27f0d7e96350789db02`
- Source pages: 3
- Section path: Anthropic-United States Department of Defense dispute > Impact
- Selection conditions: `collective_agent_typing`, `country_or_supranational`, `generic_or_pronominal_reference`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Following the government's actions against Anthropic, OpenAI "rushed", [40] hours before the US started the 2026 Iran war, [41] to get a deal without the constraints that Anthropic had sought. [42]
```

### Gold Organization Mentions

- Anthropic
- OpenAI
- US
- Anthropic

### Reviewer notes



## HO-008

- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Representation: `rep_8bcf8ef98031a6bfe43efec9`
- Paragraph node: `nod_8bcf8ef98031a6bfe43efec9_0023`
- Paragraph text SHA-256: `eabaaa4a69d24ecc112a1ab5505580a58a52e61f0f25c109ed2ecf08ae3067bd`
- Source pages: 3
- Section path: Anthropic-United States Department of Defense dispute > Impact
- Selection conditions: `country_or_supranational`

### Complete authoritative paragraph text

```text
As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems." [31]
```

### Gold Organization Mentions

- ND Cal.
- DoW
- DoW
- Anthropic
- DoW

### Reviewer notes

- ND Cal. is The Northern District of California Court

## HO-009

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0002`
- Paragraph text SHA-256: `84d7632331c5af8be2344b8d589143fec8a0f884f6851416a55e5f45b732bb80`
- Source pages: 1
- Section path: Artificial intelligence safety institute
- Selection conditions: `collective_agent_typing`, `multiple_acronyms`, `parenthetical_acronym`

### Complete authoritative paragraph text

```text
An artificial intelligence safety institute [1] is a type of state-backed organization aiming to evaluate and ensure the safety of advanced artificial intelligence (AI) models, also called frontier AI models. [2]
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-010

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0008`
- Paragraph text SHA-256: `c29d914849803e39af70dbf0cbfb77be6ccb2938abb0e454162d737193fa2a87`
- Source pages: 1
- Section path: Artificial intelligence safety institute > International network
- Selection conditions: `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
At the AI Seoul Summit in May 2024, the European Union and other countries agreed to create their own AI safety institutes, forming an international network. [1]
```

### Gold Organization Mentions

- European Union

### Reviewer notes



## HO-011

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0018`
- Paragraph text SHA-256: `fc8ccd6b5ed67bcd24abf42693d73b302d92ef0534d23acb85b6d281827a2afa`
- Source pages: 2
- Section path: Artificial intelligence safety institute > International network > France
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `parenthetical_acronym`

### Complete authoritative paragraph text

```text
On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security. [17][18]
```

### Gold Organization Mentions

- government of France
- Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA)
- National Institute for AI Evaluation and Security

### Reviewer notes

The segment names the institure and translates it - the real test of the whole system is whether or not it detects that these are 2 names for the same Organization - only one in French, another in English

## HO-012

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0024`
- Paragraph text SHA-256: `d6eb25ebf1fa2398b2f19fb925f298d5056b76441fdc12be7b4bf362d1202077`
- Source pages: 3
- Section path: Artificial intelligence safety institute > International network > Japan
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
The  Japan  AISI  (or  J-AISI) [26] was  founded  in  February 2024. Part of the Information Technology Promotion Agency, it  employs  about  23  people. [15] The  institute  consists  of  the Council of AISI, the  AISI Steering Committee, and a secretariat with six teams. [26] Akiko Murakami (previously of IBM  Japan  and  Sompo  Japan)  serves  as the institute's executive director, and Kenji Hiramoto and Suguru [26]
```

### Gold Organization Mentions

- Japan  AISI  (or  J-AISI)
- Information Technology Promotion Agency
- Council of AISI
- AISI Steering Committee
- IBM  Japan
- Sompo  Japan

### Reviewer notes



## HO-013

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0027`
- Paragraph text SHA-256: `238f4b1981732d31de57018bee8c89a2b7b486b268e99e25db65c4984557a150`
- Source pages: 3
- Section path: Artificial intelligence safety institute > International network > Kenya
- Selection conditions: `collective_agent_typing`, `country_or_supranational`, `generic_or_pronominal_reference`

### Complete authoritative paragraph text

```text
Kenya agreed to join the international network of AI safety institutes, but the country has not announced any details yet. [15] It is the only African state in the network. [27]
```

### Gold Organization Mentions

- Kenya
- international network of AI safety institutes

### Reviewer notes

The definite article makes me think this is about the AISI network, probably mentioend by name in the previous paragraph.

## HO-014

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0031`
- Paragraph text SHA-256: `c44392b20a0f9e6f1374c8a0ed144e2998d946ee4b2d6028e110cddcb54515c5`
- Source pages: 3
- Section path: Artificial intelligence safety institute > International network > South Korea
- Selection conditions: `collective_agent_typing`, `generic_or_pronominal_reference`

### Complete authoritative paragraph text

```text
South Korea announced in May 2024 that it would create an AI safety institute under the umbrella of the Electronics and Telecommunications Research Institute. It will be supported by a tentative investment of somewhere between 10 and 20 million South Korean won per year, and employ at least 30 people. [15] The  institute  was  founded  in  November  2024 [29] and  is  based  in  Bundang  District  within  the  city  of Seongnam. [30]
```

### Gold Organization Mentions

- South Korea
- Electronics and Telecommunications Research Institute

### Reviewer notes



## HO-015

- Fixture: `raw/Artificial_intelligence_safety_institute.pdf`
- Fixture SHA-256: `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253`
- Representation: `rep_561e34f74a03ac8f05edb4a3`
- Paragraph node: `nod_561e34f74a03ac8f05edb4a3_0040`
- Paragraph text SHA-256: `061b9b949704daeed594445470fc8e7595173dbe91abc128489a4591808ef246`
- Source pages: 4
- Section path: Artificial intelligence safety institute > International network > United States
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
In  March  2024,  a  budget  of  $10  million  was  allocated. [37] Observers  noted  that  this  investment  is relatively  small,  especially  considering  the  presence  of  many  big AI  companies  in  the  US.  The  NIST itself,  which hosts the AISI, is also known for its chronic lack of funding. [38][6] Biden administration's request for additional funding was met with further budget cuts from congressional appropriators. [39][38]
```

### Gold Organization Mentions

- NIST
- AISI
- Biden administration

### Reviewer notes

AISI in this case is the US AISI - a specific, not a type of, organization.

## HO-016

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0009`
- Paragraph text SHA-256: `0ca5e1768c21b392d33b4d4e2c86bc9468eccb8e4177cb1630eebdbb235656f2`
- Source pages: 2
- Section path: The AI Safety Institute International Network > Overview
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `coordinated_names`, `country_or_supranational`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
In the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.
```

### Gold Organization Mentions

- AISI network

### Reviewer notes

Requires inferring from the text that the specific AISI network exists while at the same time realizing that "AISI cooperation" means the type of organization, not a specific one.

## HO-017

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0010`
- Paragraph text SHA-256: `d864796d1c3d843322993a670e7ed3cc0a18348ef0c416d3a3e48ab3c8093e2d`
- Source pages: 2
- Section path: The AI Safety Institute International Network > Overview
- Selection conditions: `collective_agent_typing`, `context_dependent_reference`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
This paper examines next steps for developing the International Network of AI Safety Institutes from the Seoul Statement. It provides recommendations to members ahead of the inaugural network meeting in San Francisco this November and the AI Action Summit in Paris in February 2025. These recommendations fall in line with three key questions:
```

### Gold Organization Mentions

- International Network of AI Safety Institutes

### Reviewer notes



## HO-018

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0014`
- Paragraph text SHA-256: `dd77be4f9d6b1c61e45f873c9d6464dc2d8678b16c4964805d5aee974cfc04d5`
- Source pages: 2
- Section path: The AI Safety Institute International Network > Overview
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `generic_or_pronominal_reference`, `multiple_acronyms`, `parenthetical_acronym`

### Complete authoritative paragraph text

```text
The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more. All of these demand time from a small (though growing) community of government staff from member countries who can credibly claim to have some expertise on AI governance and safety issues. AISI network members should be able to articulate how their grouping is different from these preexisting initiatives, how it will effectively engage with them (or not), and for what purpose.
```

### Gold Organization Mentions

- Group of Seven (G7)
- United Nations
- Organisation for Economic Co-operation and Development (OECD)
- Global Partnership on AI (GPAI)
- International Organization for Standardization (ISO)
- AISI network

### Reviewer notes

Requires realizing that AISI network is the specific international network being discussed in the article

## HO-019

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0016`
- Paragraph text SHA-256: `839be48d289ec9e146361ff45c1e950a4e5a3dfcebf505a4261fdd5c0fc4f60c`
- Source pages: 3
- Section path: The AI Safety Institute International Network > Overview
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `generic_or_pronominal_reference`

### Complete authoritative paragraph text

```text
This paper begins with background on the AISI network and explains its importance. Next, it offers an overview of network members' organizations and stated functions. It concludes with recommendations regarding nine further questions for developing the goals, collaboration mechanisms, and international strategy of the network.
```

### Gold Organization Mentions

- AISI network

### Reviewer notes



## HO-020

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0019`
- Paragraph text SHA-256: `fe402d0d38a052eafb4b3aba62e4b1745d94868541ea3b8ce818894ac9419514`
- Source pages: 3
- Section path: The AI Safety Institute International Network > Background > WHAT IS AI SAFETY AND WHY DOES IT MATTER?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`, `possessive_boundary`

### Complete authoritative paragraph text

```text
As defined by the Bletchley Declaration, issued by attendees of the UK AI Safety Summit in November 2023, AI safety is a scientific field of research focused on evaluating, preventing, and mitigating risks from advanced AI systems. In this case, it refers narrowly to AI systems at or beyond the current state of the art. These risks can range from deepfakes to the use of AI for bioterrorism; new risks will emerge as AI's capabilities continue to evolve. Somewhat confusingly, other individuals and organizations may define AI safety more broadly to include lower-performing systems that are not operating at the technical frontier. Still others may or may not include issues around ethics and bias when using the term 'AI safety.' This paper's use of the term 'AI safety' follows the U.S. AI Safety Institute's example of focusing exclusively on safety issues related to advanced AI systems.
```

### Gold Organization Mentions

- U.S. AI Safety Institute

### Reviewer notes



## HO-021

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0025`
- Paragraph text SHA-256: `f02bf93b1abb0148ba5ec76e55e630c6785203012e0995f18a94406ced6136d1`
- Source pages: 3
- Section path: The AI Safety Institute International Network > Background > WHAT IS AI SAFETY AND WHY DOES IT MATTER?
- Selection conditions: `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
Meanwhile, process-based safety is concerned with the policies, practices, and procedures that surround AI. This stream of AI safety is more operational in nature. It focuses on how frontier AI developers, deployers, and users build, manage, and monitor AI models, including by evaluating models for capabilities, limitations, and risks, and documenting and reporting model information. It may also include processes that are implemented by the users of AI.
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-022

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0026`
- Paragraph text SHA-256: `c801f2f44261dc1e3ad5b4f889db4141d0886b01049888176fe6e83cb5b8e034`
- Source pages: 3
- Section path: The AI Safety Institute International Network > Background > WHAT IS AI SAFETY AND WHY DOES IT MATTER?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `coordinated_names`, `country_or_supranational`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
Beyond preventing adverse risks, AI safety serves to accelerate adoption and innovation by building public trust. As Elizabeth Kelly, director of the U.S. AI Safety Institute, said in a CSIS interview , 'safety promotes trust, which promotes adoption, which drives innovation.' AI safety boosts public trust by allowing people to pause, stop, or change course as needed.
```

### Gold Organization Mentions

- U.S. AI Safety Institute
- CSIS

### Reviewer notes



## HO-023

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0034`
- Paragraph text SHA-256: `46e01a76a15739ee6cd626719cd63328adc0a95d84ff7f53cd1970dc9fbff13e`
- Source pages: 4
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `coordinated_names`, `country_or_supranational`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
Source: 'The U.S. Vision for AI Safety: A Conversation with Elizabeth Kelly, Director of the U.S. AI Safety Institute,' CSIS, July 31, 2024, https://www.csis.org/analysis/us-vision-ai-safety-conversation-elizabeth-kelly-director-us-ai-safety-institute; and 'The United States Artificial Intelligence Safety Institute: Vision, Mission, and Strategic Goals,' U.S. Artificial Intelligence Safety Institute, May 21, 2024, https://www.nist.gov/system/files/ documents/2024/05/21/AISI-vision-21May2024.pdf.
```

### Gold Organization Mentions

- U.S. AI Safety Institute
- CSIS
- United States Artificial Intelligence Safety Institute
- U.S. Artificial Intelligence Safety Institute

### Reviewer notes



## HO-024

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0036`
- Paragraph text SHA-256: `ca4708f147863997a3fcc549f459ac894a4bb0b5b8c27785bce1169d394b769e`
- Source pages: 5
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `context_dependent_reference`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
To keep pace with the cutting edge of AI safety research, AISIs have prioritized the hiring of technical staff and opened offices in cities with deep pools of AI talent like San Francisco. In addition to developing expertise internally, AISIs aim to cultivate a robust ecosystem of AI safety researchers in labs, industry, and academia through their guidance on best-in-class evaluation methods.
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-025

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0049`
- Paragraph text SHA-256: `2689a648a4145620e2bcbb9462d4aea088ec43364bf99df68f521bdc0b6fdcbe`
- Source pages: 5
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
Note that while these nine areas of guidance overlap with the nine core functions of an AI safety institute identified in Section 4 of this paper, they do not cover the full breadth of AISIs' operations. As Section 4 will discuss, AISIs perform functions such as forming consortia of AI researchers, stakeholders, and experts and promoting the international adoption of AI safety guidelines that are outside the scope of the AISIC.
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-026

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0053`
- Paragraph text SHA-256: `f097c591cfa5bca62ce64f000a09434874bda6814b8c63ee9525bbadf1e7a906`
- Source pages: 6
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
The letter echoes similar calls for Congress to authorize the AISI by Scale AI Founder and CEO Alexandr Wang earlier in October, as well as a letter from top AI companies to establish the AISI on a statutory basis in July. The July letter, also published by Americans for Responsible Innovation and ITI, argues that authorizing the AISI "provides a venue to convene the leading experts across industry and government to contribute to the development of voluntary standards that ultimately assist in de-risking adoption of AI technologies.' It's not just the biggest companies that stand to benefit from the U.S. AISI-crucially, the letter argued that the institute may level the playing field for enterprises that use or develop AI but are unable to perform robust testing and evaluation in-house due to their size or the technical ability of their staff.
```

### Gold Organization Mentions

- Congress
- AISI
- Scale AI
- AISI
- Americans for Responsible Innovation and ITI
- AISI
- U.S. AISI

### Reviewer notes



## HO-027

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0054`
- Paragraph text SHA-256: `7f18cbcec8e50ee82bb44f625ec66398cc340da60c2a19553d7862df08696d20`
- Source pages: 6
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `parenthetical_acronym`

### Complete authoritative paragraph text

```text
While the concept of a government organization that works closely with AI companies on safety is still new, history shows that this kind of arrangement between government and industry can be highly successful. One good example is the National Highway Traffic Safety Administration (NHTSA), a U.S. federal agency that performs safety tests of new motor vehicle models for manufacturers. Established in the 1970s to reduce accidents and deaths by encouraging manufacturers to produce safer vehicles, NHTSA led what has become today an industry standard of crash testing and rating vehicles out of five stars according to their safety. Some 50 years since its launch, NHTSA continues to perform crash tests and produce star ratings, as well as issue government safety ratings, safety information, and best practices.
```

### Gold Organization Mentions

- National Highway Traffic Safety Administration (NHTSA)
- NHTSA
- NHTSA

### Reviewer notes



## HO-028

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0055`
- Paragraph text SHA-256: `6f9f63c91f683dca9f35f19120ae024df1cd742f8c2f20293f021e41b068d640`
- Source pages: 6, 7
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`, `possessive_boundary`

### Complete authoritative paragraph text

```text
NHTSA is a useful model of a third-party government arbiter that has produced substantial win-win results for the public and for companies. The administration's rating system lowers costs to consumers by supplying accurate, reliable, and simple safety information for free. Meanwhile, companies are incentivized to adopt new and better safety measures into their vehicles. As NHTSA's acting administrator has stated , '[o]ur 5-Star Safety Ratings system continues to give Americans the information they need to choose the vehicle that's right for them. The program also encourages vehicle manufacturers to incorporate advanced vehicle safety technologies into more makes and models, ultimately reducing injuries and deaths on America's roads.' Because safety is a selling point for customers , most of the United States' manufacturers willingly sign up for the NHTSA's 5-star system and use the results in advertising new vehicle models.
```

### Gold Organization Mentions

- NHTSA
- NHTSA
- NHTSA

### Reviewer notes



## HO-029

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0057`
- Paragraph text SHA-256: `5a6c2bd5dc638b12b3e0707cc298fe2c30a7c3c4573aaea2209293f55119be4c`
- Source pages: 7
- Section path: The AI Safety Institute International Network > Background > WHAT ARE AI SAFETY INSTITUTES AND WHAT WILL THEY DO?
- Selection conditions: `acronym_reference`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
As AISIs mature organizationally, they could fulfill a similar arbiter role for AI models as the NHTSA has for motor vehicles. As has been the case with motor vehicles, testing AI models could lead to innovation in which safety is a key competitive feature. AI companies could communicate to customers that their model has passed AISI testing and evaluations, which could in turn help to build public trust and make AI models with higher safety standards more commercially competitive among consumers. Top frontier AI developers' willingness to work with the U.S. AISI on testing their models before deployment is a good first step to making safety a key feature of AI industry standards, as the NHTSA has done with the U.S. motor vehicle industry over the last 50 years.
```

### Gold Organization Mentions

- NHTSA
- AISI
- U.S. AISI
- NHTSA

### Reviewer notes



## HO-030

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0060`
- Paragraph text SHA-256: `173104fa8372de0ea49889b3f6d8d70529cf38168593a5657120620408cc9499`
- Source pages: 7
- Section path: The AI Safety Institute International Network > Background > TIMELINE OF AI SAFETY INSTITUTES
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
The AISI International Network marks a logical next step in a series of recent bilateral agreements between institutes. In April 2024, the United States signed a memorandum of understanding with the United Kingdom for close collaboration between institutes and established a dialogue with the EU AI Office to jointly develop evaluation tools for AI models. Meanwhile, the United Kingdom, for its part, has established additional partnerships with Canada and France on AI safety, and the European Union and Japan have indicated future cooperation between safety institutes in the coming months.
```

### Gold Organization Mentions

- AISI International Network
- United States
- United Kingdom
- EU AI Office
- United Kingdom
- Canada
- France
- European Union
- Japan

### Reviewer notes

Country names as references to the governments

## HO-031

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0067`
- Paragraph text SHA-256: `f2ee2fcc6f154ae713b57eadda8bb01209ad84c0241507de4fbf4e23ebfcb5fa`
- Source pages: 9
- Section path: The AI Safety Institute International Network > Why The AISI International Network Matters
- Selection conditions: `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
International consensus would increase regulatory interoperability, or the degree to which different domestic regulatory systems can smoothly interface and interact. Interoperability allows for the even implementation of international AI governance efforts. One such effort is the G7 Hiroshima AI Process Code of Conduct, which calls for 'robust' and 'trustworthy' AI systems but lacks technical definitions of the terms. Shared definitions would help create a common measuring stick by which regulators gauge these characteristics. Countries could choose policy options along such a ruler based on their risk tolerance for given AI applications. In this example, governments would require different levels of robustness and trustworthiness along the same underlying scale, as is the case for safety in the automobile and aviation industries. A common understanding of AI safety concepts would help clarify the steps countries must take to honor the G7 code of conduct and other international commitments.
```

### Gold Organization Mentions

- None

### Reviewer notes

"G7 ... code of conduct" is a document, not a reference to the G7 itself

## HO-032

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0068`
- Paragraph text SHA-256: `b120761346de9c44e3bd3daa4b19ed89c43667c429cb5a38767ecf3fb66b329e`
- Source pages: 9
- Section path: The AI Safety Institute International Network > Why The AISI International Network Matters
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `country_or_supranational`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
In this way, interoperability based on common definitions, procedures, and best practices can help to facilitate trade in the future. As a previous CSIS paper argued, fragmented legal frameworks that require company compliance with many different obligations can create technical barriers to the free flow of goods and services. Diverging regulatory approaches that require companies to demonstrate that a product is 'safe' according to 10 different metrics from 10 different jurisdictions, for instance, is not only highly inefficient but often prohibitively costly. Instead, the AISI International Network could serve as one venue in which to develop a coherent language around AI safety, helping to lower future potential barriers to trade.
```

### Gold Organization Mentions

- CSIS
- AISI International Network

### Reviewer notes



## HO-033

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0072`
- Paragraph text SHA-256: `5a9002e2b61f9aac9979dd5153666bf99e5ec139401288ca190c2c1a6a48b9f8`
- Source pages: 10
- Section path: The AI Safety Institute International Network > Why The AISI International Network Matters
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `multiple_acronyms`, `organization_or_nonorganization`, `parenthetical_acronym`, `possessive_boundary`

### Complete authoritative paragraph text

```text
This is important for not only setting safety norms at home, but also advocating for U.S. interests abroad. Consider, for instance, the EU AI Act: while the first wave of the act came into force on August 1, the requirements for developers of frontier AI models above 10^25 floating operation points (FLOPS) of compute power have yet to be defined. Rather, the EU AI Office-the European Union's representation to the AISI International Network-is tasked with developing codes of practice for the developers of these models, almost all of which are U.S. companies .
```

### Gold Organization Mentions

- U.S.
- EU AI Office
- European Union
- AISI International Network

### Reviewer notes



## HO-034

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0073`
- Paragraph text SHA-256: `c543298ac64c76504c3c2b2199417c8b1022eacec6e8e43e47093f96508d1bfa`
- Source pages: 10
- Section path: The AI Safety Institute International Network > Why The AISI International Network Matters
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
According to Article 56 of the AI Act, the EU AI Office must develop codes of practice for frontier AI companies to identify, assess, manage, and report 'systemic' risks by May 2, 2025. To meet this tight deadline, it may look to the work of the AISI International Network if it deems it sufficiently mature to draw upon. Having a seat at the same table as the EU AI Office is therefore a valuable opportunity to help develop safety norms that the European Union may apply to U.S. companies. Even if the European Union ultimately decides to develop its codes of practice alone, the network will still provide the United States with a direct line of communication to the EU AI Office for articulating AI safety best practices in the future.
```

### Gold Organization Mentions

- EU AI Office
- AISI International Network
- EU AI Office
- European Union
- European Union
- United States
- EU AI Office

### Reviewer notes

Both literal European Union expressions refer to the supranational Organization acting through policy decisions.

## HO-035

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0075`
- Paragraph text SHA-256: `3e2173ceca64f3a0fc67762a8b824ddcc33bd58ed05d14559f5a0657f6563e27`
- Source pages: 10
- Section path: The AI Safety Institute International Network > Overview of AISI Network Members
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`

### Complete authoritative paragraph text

```text
It is still early days for AI safety institutes, both as organizations and as concepts. Members of the AISI International Network are highly varied in their organizational maturity, which can be expected given that most are only months old. Even the U.S. AISI, one of the most established institutes, was announced only in November 2023 and became operational in early 2024. Other AISIs, such as those of Japan, Singapore, South Korea, and the European Union, are still in the process of hiring and setting out the priorities of their institutes, according to public documents and conversations by CSIS with officials. Still other network members, like Kenya and Australia, have yet to clearly state whether their governments will even establish an AISI.
```

### Gold Organization Mentions

- AISI International Network
- U.S. AISI
- Japan
- Singapore
- South Korea
- European Union
- Kenya
- Australia

### Reviewer notes

This one is a good one - contextually, the "Other AISIs" list of countries needs to be resolved - it's clearly meaning the countries as organizations, but there's a difference: Japan ... European Union are references to those countries' AISIs. However, Kenya and Australiamare references to those countries' governments, since they have not established AISIs. I expect this one to be challenging to fully resolve.

## HO-036

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0076`
- Paragraph text SHA-256: `d6a8667c7974e1934ffc6a452851b9d7612e447f544967afff9755ccff695ba3`
- Source pages: 10
- Section path: The AI Safety Institute International Network > Overview of AISI Network Members
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `country_or_supranational`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Nevertheless, established AISIs report strong similarities in funding and staff size thus far. As Table 1 illustrates, the annual budgets of network members currently hover around $10 million, with some notable exceptions. First, the UK AISI is already an outlier with a budget of approximately £50 million ($65 million) per year, according to CSIS sources. Second, the United States' fiscal year 2025 budget requests an increase of $47.7 million for investment into the U.S. AISI and the advancement of AI research, standards, and testing in line with President Biden's October 2023 AI executive order , which, if approved, would greatly boost the average network budget. Finally, an announcement by the Canadian government in April pledges C$50 million (approximately US$36 million) for a Canadian AISI, though the funding period is unspecified.
```

### Gold Organization Mentions

- UK AISI
- CSIS
- United States
- U.S. AISI
- Canadian government
- Canadian AISI

### Reviewer notes



## HO-037

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0077`
- Paragraph text SHA-256: `edaa22a040bf679e2e035c1ba719bc23897074e88912c5d93f5600e142691e1b`
- Source pages: 10
- Section path: The AI Safety Institute International Network > Overview of AISI Network Members
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `country_or_supranational`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Public statements and private conversations between CSIS and government officials reveal that staff sizes will also be comparable between institutes. More established AISIs currently employ approximately 20 to 30 staff, most of whom are technical experts. Private conversations with CSIS indicate that the EU AI Office's AI safety unit , which will fulfill most of the same functions as an AISI (Table 2), will likely hold approximately 50 staff members.
```

### Gold Organization Mentions

- CSIS
- CSIS
- EU AI Office's AI safety unit

### Reviewer notes



## HO-038

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0248`
- Paragraph text SHA-256: `dbf9b1005076f0383872dbe8c91b54b72cf1df987c76ae58bac1906571e15f38`
- Source pages: 12
- Section path: The AI Safety Institute International Network > Overview of AISI Network Members
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`, `possessive_boundary`

### Complete authoritative paragraph text

```text
It also shows that some institutes have already begun to produce work related to their stated functions. Some deliverables predate the AISI, such as the Japanese Ministry of Economy, Trade and Industry's AI Business Guidelines, but have been incorporated and built upon by current AISI efforts. Others are novel efforts by institutes since their launch, such as the U.S. AISI's guidance for Managing Misuse Risk for Dual-Use Foundation Models , and the UK AISI's Inspect and Singapore's Project Moonshot , two testing and evaluation toolkits for large language models (LLMs).
```

### Gold Organization Mentions

- Japanese Ministry of Economy, Trade and Industry
- U.S. AISI
- UK AISI

### Reviewer notes

Going to include the Japanese Ministry here because it's obvious from the text that it exists, even though it's not the focus of the sentence.

## HO-039

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0257`
- Paragraph text SHA-256: `ec12a27f15c7034a91230cd4cdb7aef3b5e4c7b5513d88d71c9ba59fa3dfbf6d`
- Source pages: 13
- Section path: The AI Safety Institute International Network > GOALS OF COLLABORATION: WHAT IS THE AISI NETWORK TRYING TO ACHIEVE AND WHEN?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
Recommendation: The AISI International Network does not have the capacity or resources to effectively collaborate on every domain of AI safety. For some domains, such as sharing sensitive information about models, AISIs may even face legal limitations to collaboration. Rather than spreading finite resources thinly in an effort to achieve everything all at once, network members should first focus on executing a few specific projects well. These should be attainable in the near future to demonstrate continued momentum from the AI Seoul Summit.
```

### Gold Organization Mentions

- AISI International Network

### Reviewer notes



## HO-040

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0258`
- Paragraph text SHA-256: `ddebd202db5a874450a5083ef1c9700348945a9ee978003e91126e11160b860c`
- Source pages: 13
- Section path: The AI Safety Institute International Network > GOALS OF COLLABORATION: WHAT IS THE AISI NETWORK TRYING TO ACHIEVE AND WHEN?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
When selecting priority areas, members should consider areas with the greatest overlap in AISI's functions, capacity, and expertise, and deliverables that are both impactful and realistic. To start, they should establish a research agenda for the network's technical and guidance safety work going forward. This will help to set the scope of the network's efforts and to keep members on track as they and the network mature. As discussed in this paper's recommendation to Question 3, the AISI network conference in November may be a good place to set and present this agenda to the public.
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-041

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0269`
- Paragraph text SHA-256: `e3abafdfb9c7ce5f0149b2e1fbb629285b82f12ae6d2133e2d171c25b1cab1ca`
- Source pages: 14, 15
- Section path: The AI Safety Institute International Network > MECHANISMS OF COLLABORATION: WHAT WILL THE AISI NETWORK DO AND HOW WILL IT WORK?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `coordinated_names`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
Recommendation: It would be premature to assign specific responsibilities to AISI network members today given that most are only months old, if established at all. However, members should consider the benefits and drawbacks of different organizational structures as the network develops. Currently, AISI network members share equal responsibilities by default. While this can be useful for promoting equal participation and accountability from members, it can also add unnecessary costs to collaboration. If each member were to take charge on a different project, for instance, the network could risk losing time, capacity, and focus. This kind of structure could also place undue pressure on the capacity and expertise of each of the AISIs to contribute before they are ready.
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-042

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0271`
- Paragraph text SHA-256: `b657e57b5dd7b32949948d85545cb859a599c128b4b164782afc5b93f5a48c73`
- Source pages: 15
- Section path: The AI Safety Institute International Network > MECHANISMS OF COLLABORATION: WHAT WILL THE AISI NETWORK DO AND HOW WILL IT WORK?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `possessive_boundary`

### Complete authoritative paragraph text

```text
Instead, the AISI network may consider leveraging each member's comparative advantages in expertise, capacity, and funding. Those that are most able to contribute to projects, for instance, should be able and incentivized to do so, as is discussed in Question 7. For now, more mature AISIs like those of the United States, the United Kingdom, and Singapore could have greater responsibilities within the network while other members, such as Kenya or Australia, contribute through more specialized ways. These roles could shift over time as AISIs mature, however.
```

### Gold Organization Mentions

- resolved: United States AISI
- resolved: United Kingdom AISI
- resolved: Singapore AISI

### Reviewer notes

Requires the system to resolve "AISIs like those of the ..."

## HO-043

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0276`
- Paragraph text SHA-256: `b549a4081a8e3f7bdd0d0f0db98a004824844502efbf7a9943af7b8a323e4006`
- Source pages: 15
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > 7. What will the network's leadership and voting structure look like?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `organization_or_nonorganization`

### Complete authoritative paragraph text

```text
Recommendation: Currently, the AISI network has a horizontal leadership and consensus or opt-in only voting structure by default. Given that the Seoul Statement makes no indication of leadership and voting structure, however, network members are open to consider different possibilities and their trade-offs. For example, a consensus-based structure can help to foster good intentions for international cooperation, but it can also make it challenging to take meaningful collective action. Similarly, having just one member serve as a leader may seem unfair, but a rotating leadership structure can be ineffectual and prioritize the interests of that country (or bloc) for that period.
```

### Gold Organization Mentions

- AISI network

### Reviewer notes



## HO-044

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0277`
- Paragraph text SHA-256: `7d2f9aa6b2c32dff63afdbb08a7bb139bb5a157181088f40592525f762b9f879`
- Source pages: 15
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > 7. What will the network's leadership and voting structure look like?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `possessive_boundary`

### Complete authoritative paragraph text

```text
The network's leadership and voting structures need not be zero sum, however. In the long run, members' representation within the network should be proportionate to their contributions; those that invest more time, money, expertise, and resources should be rewarded with a greater say in its direction. This means that the U.S. and UK AISIs would likely be rewarded with leadership of the network due to their organizational capacity. The United States, for its part, should aspire to lead the AISI network, as discussed in the third section of this paper. Rather than merely insisting on leading, however, it should commit the resources and time that positions it to deserve to lead. Leadership should be earned based on the scale of meaningful contributions to the field of AI safety science, a structure that also incentivizes on other network members to participate and invest more into AI safety and the AISI network as well.
```

### Gold Organization Mentions

- resolved: U.S. AISI
- resolved: UK AISI
- United States
- AISI network
- AISI network

### Reviewer notes

- Requires resolving "U.S. and UK AISIs" as "U.S. AISI" and "UK AISI".
- Both literal AISI network expressions denote the Organization.

## HO-045

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0282`
- Paragraph text SHA-256: `89471c9b4648b55ee6f5626d501c3bb2abb3ab587cb89c3d4957010adec8d6ff`
- Source pages: 16
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > INTERNATIONAL STRATEGY: HOW WILL THE AISI NETWORK FIT INTO AND ENGAGE WITH OTHER INTERNATIONAL AI EFFORTS?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `country_or_supranational`, `generic_or_pronominal_reference`, `multiple_acronyms`, `organization_or_nonorganization`, `possessive_boundary`

### Complete authoritative paragraph text

```text
To do this, the AISI network should emphasize its unique position to provide technical expertise and capacity to governments working on wider AI governance efforts. In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI . These initiatives, though commendable, are often staffed by diplomats who lack the depth of in-house technical expertise that the AISI network has demonstrated an ability to amass. It is this expertise that could turn what are currently high-level principles and frameworks into practical implementation for developers.
```

### Gold Organization Mentions

- AISI network
- Biden administration
- AISI network

### Reviewer notes

Both literal AISI network expressions denote the Organization.

## HO-046

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0288`
- Paragraph text SHA-256: `54346df73584b5fceb5972463c78be6d892898ded665631cc7f2d6ddc28b64ab`
- Source pages: 17
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > INTERNATIONAL STRATEGY: HOW WILL THE AISI NETWORK FIT INTO AND ENGAGE WITH OTHER INTERNATIONAL AI EFFORTS?
- Selection conditions: `acronym_reference`, `collective_agent_typing`, `context_dependent_reference`, `generic_or_pronominal_reference`, `multiple_acronyms`, `parenthetical_acronym`, `possessive_boundary`

### Complete authoritative paragraph text

```text
One way to address this could be requiring prospective members to demonstrate their ability to meaningfully contribute to the network-such as through a minimum degree of expertise and capacity-before they can join. The purpose here is not to make the AISI network into an elite club, but to recognize that the network's goal of accelerating AI safety science cannot be realistically achieved by expanding membership to everyone who wants it. The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network. Such partnerships could help to foster wider international cooperation on AI safety and engage more developing countries on the AISI network's efforts in particular.
```

### Gold Organization Mentions

- AISI network
- AISI network
- GPAI
- OECD
- Group of 20 (G20)
- AISI network

### Reviewer notes



## HO-047

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0291`
- Paragraph text SHA-256: `344b2b631b460052ae0619e8c175d0199d8e26e9184b266e994fc3ecf8436b24`
- Source pages: 17
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > INTERNATIONAL STRATEGY: HOW WILL THE AISI NETWORK FIT INTO AND ENGAGE WITH OTHER INTERNATIONAL AI EFFORTS? > Conclusion
- Selection conditions: `collective_agent_typing`, `country_or_supranational`, `generic_or_pronominal_reference`, `organization_or_nonorganization`, `possessive_boundary`

### Complete authoritative paragraph text

```text
While the Seoul Statement is a good start for multilateralizing cooperation between AISIs, network members must now decide how to turn intent into action. At the November convening in San Francisco, they should strive to set the network's goals, mechanisms, and international strategy in preparation for the AI Action Summit in February 2025. In doing so, they must ask tough questions, including about priorities, leadership, and membership.  ■
```

### Gold Organization Mentions

- None

### Reviewer notes



## HO-048

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0292`
- Paragraph text SHA-256: `590c66545d13a65f5e3a9e46c0cd6f6831f30845df0288a20654834df302b877`
- Source pages: 17
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > INTERNATIONAL STRATEGY: HOW WILL THE AISI NETWORK FIT INTO AND ENGAGE WITH OTHER INTERNATIONAL AI EFFORTS? > Conclusion
- Selection conditions: `acronym_reference`, `coordinated_names`, `multiple_acronyms`, `parenthetical_acronym`

### Complete authoritative paragraph text

```text
Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.
```

### Gold Organization Mentions

- Wadhwani AI Center
- Center for Strategic and International Studies (CSIS)
- Wadhwani AI Center
- CSIS

### Reviewer notes



## HO-049

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0294`
- Paragraph text SHA-256: `f02f97b9a8f37bd06951ac6b6b95c99f891a649a9f588947ec5f8b9fa57e8fe8`
- Source pages: 17
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > INTERNATIONAL STRATEGY: HOW WILL THE AISI NETWORK FIT INTO AND ENGAGE WITH OTHER INTERNATIONAL AI EFFORTS? > Conclusion
- Selection conditions: `acronym_reference`, `context_dependent_reference`, `country_or_supranational`, `multiple_acronyms`, `parenthetical_acronym`

### Complete authoritative paragraph text

```text
This report is produced by the Center for Strategic and International Studies (CSIS), a private, tax-exempt institution focusing on international public policy issues. Its research is nonpartisan and nonproprietary. CSIS does not take specific policy positions. Accordingly, all views, positions, and conclusions expressed in this publication should be understood to be solely those of the author(s).
```

### Gold Organization Mentions

- Center for Strategic and International Studies (CSIS)
- CSIS

### Reviewer notes



## HO-050

- Fixture: `raw/241030_Allen_Safety_Network.pdf`
- Fixture SHA-256: `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`
- Representation: `rep_e2ef007787e60f415d0334cd`
- Paragraph node: `nod_e2ef007787e60f415d0334cd_0295`
- Paragraph text SHA-256: `035dd88e4999dedea0c2f64a21d375f74a91eae885f7ca96765d26867ca2917a`
- Source pages: 17
- Section path: The AI Safety Institute International Network > 6. Will the AI safety summits continue to serve as the principal international venue for AISIs and the AISI network? > INTERNATIONAL STRATEGY: HOW WILL THE AISI NETWORK FIT INTO AND ENGAGE WITH OTHER INTERNATIONAL AI EFFORTS? > Conclusion
- Selection conditions: `negative_control`

### Complete authoritative paragraph text

```text
© 2024 by the Center for Strategic and International Studies. All rights reserved.
```

### Gold Organization Mentions

- Center for Strategic and International Studies

### Reviewer notes
