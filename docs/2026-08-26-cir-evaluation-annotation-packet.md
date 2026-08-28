# CIR Evaluation Annotation Packet

Expanded reviewer view: [PHP-1 Data-In / Expected-Out Review Packet](2026-08-28-php1-data-in-expected-out-review.md)

- **Status:** Exact Organization Mentions are human-reviewed; broad semantic expectations remain provisional.
- **Purpose:** Seed an independent evaluation set for extraction and evidence-grounding work.
- **Release status:** This packet is not a held-out release or generalization benchmark.

## 1. Corpus snapshot

This packet uses only deposited local files.
The Pipeline created each listed `DocumentRepresentationBundle` through the public `source add-file` path.
Each case identifies one authoritative paragraph `DocumentNode`.
The node ID and source-text digest make the span replayable from the pinned representation.

| Source | Archived blob SHA-256 | DocumentRepresentationBundle |
| --- | --- | --- |
| Anthropic–United States Department of Defense dispute | `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624` | `rep_355e4a2012f9cf3978bcf34a` |
| Artificial intelligence safety institute | `2220220010291aa4a2ccc8286b2f4c5e96cdbb673392f289682c2c84104f5253` | `rep_10c2e7b4f6020f1a3a68d389` |
| The AI Safety Institute International Network: Next Steps and Recommendations | `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f` | `rep_3b54ac13ce63f97638fd10cd` |

The CSIS report `241030_Allen_Safety_Network.pdf` is present in the Archive as blob `16f65bb7730939b5f813a6c538d9c24674183ad492dfaa5be091e00783f9670f`.
Its PDF declares AES-256 encryption with an empty user password.
Preview, Poppler, and qpdf open the local bytes without a password.
The authoritative PDF adapter records its qpdf decryption transformation and creates the listed representation.

## 2. Annotation rules

Each case covers the whole referenced paragraph as its initial evidence span.
The eventual corpus can split a paragraph into smaller `EvidenceTarget` spans after reviewer confirmation.
`Expected semantic work` describes the fact or distinction a system must preserve.
It does not prescribe a current canonical predicate.
`Control` cases identify a result that must remain attributed, conditional, ambiguous, or absent.

| Case | Evidence span | Anchor | Class | Expected semantic work |
| --- | --- | --- | --- | --- |
| AD-01 | `nod_355e4a2012f9cf3978bcf34a_0008` p. 1 | `Directive 3000.09` | direct | Identify that the Department of Defense established the 2012 AI-use policy. |
| AD-02 | `nod_355e4a2012f9cf3978bcf34a_0008` p. 1 | `Project Maven prompted concerns within Google` | causal | Preserve the stated causal chain to protests and resignations without inventing a policy conflict. |
| AD-03 | `nod_355e4a2012f9cf3978bcf34a_0010` pp. 1–2 | `held discussions with Trump officials` | direct | Identify the Anthropic-to-Trump-officials policy-discussion relation. |
| AD-04 | `nod_355e4a2012f9cf3978bcf34a_0010` pp. 1–2 | `privately lobbied for Congress` | multiple | Extract lobbying and opposition as separate relations, not one vague political stance. |
| AD-05 | `nod_355e4a2012f9cf3978bcf34a_0010` pp. 1–2 | `According to Semafor` | attribution | Preserve Semafor attribution for officials chastising Anthropic. |
| AD-06 | `nod_355e4a2012f9cf3978bcf34a_0011` p. 2 | `partnered with Palantir and Amazon Web Services` | multiple | Produce two distinct partnership candidates. |
| AD-07 | `nod_355e4a2012f9cf3978bcf34a_0011` p. 2 | `reached an agreement with the AI Safety Institute` | cross-source control | Do not resolve the generic name to a source-two institute without an explicit identity discriminator. |
| AD-08 | `nod_355e4a2012f9cf3978bcf34a_0011` p. 2 | `authorized its workers to use` | temporal | Preserve the Department of Homeland Security actor, Claude inclusion, and the May 2025 end date. |
| AD-09 | `nod_355e4a2012f9cf3978bcf34a_0011` p. 2 | `Through its interoperability with Palantir` | mediated | Preserve Palantir as the stated mechanism for wider military usage. |
| AD-10 | `nod_355e4a2012f9cf3978bcf34a_0015` p. 2 | `initially contracted Google Gemini...then OpenAI's ChatGPT` | ordered multiple | Preserve the contract order and keep Gemini and ChatGPT distinct products. |
| AD-11 | `nod_355e4a2012f9cf3978bcf34a_0016` p. 3 | `According to Reuters` | attributed multiple | Extract Anthropic opposition to surveillance use and lethal autonomous weapons with Reuters attribution. |
| AD-12 | `nod_355e4a2012f9cf3978bcf34a_0016` p. 3 | `termination of a contract worth an estimated US$200 million` | causal | Preserve the estimated amount and avoid asserting a precise contractual value. |
| AD-13 | `nod_355e4a2012f9cf3978bcf34a_0017` p. 3 | `all lawful purposes` | direct | Identify Anthropic's refusal and the Department's threatened cancellation as separate actions. |
| AD-14 | `nod_355e4a2012f9cf3978bcf34a_0017` p. 3 | `A federal judge blocked most` | legal | Distinguish the judge's blocking action from Hegseth's attempted designation. |
| AD-15 | `nod_355e4a2012f9cf3978bcf34a_0019` p. 3 | `did not know whether Claude had been used` | uncertainty control | Do not accept that Claude was used in the strike or that the use case complied with red lines. |
| AD-16 | `nod_355e4a2012f9cf3978bcf34a_0026` p. 4 | `records show that it designated Anthropic` | quotation control | Preserve that the wording occurs in a legal quotation and separate quoted arguments from adjudicated fact. |
| AD-17 | `nod_355e4a2012f9cf3978bcf34a_0028` p. 4 | `order is not final` | legal status | Extract the D.C. Circuit denial and retain its non-final status. |
| AI-01 | `nod_10c2e7b4f6020f1a3a68d389_0003` p. 1 | `United Kingdom and the United States both created their own AISI` | direct multiple | Produce separate UK and US institute-creation candidates. |
| AI-02 | `nod_10c2e7b4f6020f1a3a68d389_0003` p. 1 | `network of AI Safety Institutes` | membership | Preserve the listed network membership without treating every country as the same institute. |
| AI-03 | `nod_10c2e7b4f6020f1a3a68d389_0005` p. 1 | `evolution of the Frontier AI Taskforce` | identity lineage | Identify the UK institute's predecessor relationship. |
| AI-04 | `nod_10c2e7b4f6020f1a3a68d389_0005` p. 1 | `part of the National Institute of Standards and Technology` | organizational placement | Identify the US AISI-to-NIST placement. |
| AI-05 | `nod_10c2e7b4f6020f1a3a68d389_0006` p. 1 | `Politico reported` | attribution control | Keep the claim about companies withholding pre-deployment access attributed to Politico. |
| AI-06 | `nod_10c2e7b4f6020f1a3a68d389_0006` p. 1 | `agreement ... to collaborate on at least one joint safety test` | direct | Identify the April 2024 UK–US collaboration agreement. |
| AI-07 | `nod_10c2e7b4f6020f1a3a68d389_0009` p. 1 | `exercise to explore issues` | event | Identify the network exercise and its two stated risk themes. |
| AI-08 | `nod_10c2e7b4f6020f1a3a68d389_0012` p. 2 | `housed within the Department` | multiple | Separate Australian institute creation, departmental placement, budget, and named leadership. |
| AI-09 | `nod_10c2e7b4f6020f1a3a68d389_0014` p. 2 | `partners with the Canadian Institute` | direct | Identify the Canadian institute–CIFAR partnership and retain its government placement. |
| AI-10 | `nod_10c2e7b4f6020f1a3a68d389_0020` p. 2 | `held consultations with` | high-cardinality | Enumerate the consultation participants without collapsing them into one entity. |
| AI-11 | `nod_10c2e7b4f6020f1a3a68d389_0020` p. 2 | `shift focus from regulation` | policy change | Preserve the three new focus areas and the stated need for interoperable technologies. |
| AI-12 | `nod_10c2e7b4f6020f1a3a68d389_0021` p. 2 | `UNESCO and MeitY began consulting` | direct | Identify the two parties and the named assessment methodology. |
| AI-13 | `nod_10c2e7b4f6020f1a3a68d389_0022` pp. 2–3 | `hub-and-spoke` | organizational model | Identify the IndiaAI Safety Institute's creation, mission, and collaboration model without treating every participant as a founder. |
| AI-14 | `nod_10c2e7b4f6020f1a3a68d389_0029` p. 3 | `renamed to the Singapore AISI` | identity lineage | Identify the Digital Trust Centre-to-Singapore-AISI rename, NTU placement, and IMDA partnership separately. |
| AI-15 | `nod_10c2e7b4f6020f1a3a68d389_0033` p. 3 | `continued to be led by Ian Hogarth` | multiple | Preserve UK Taskforce lineage, leadership continuity, and Department for Science placement. |
| AI-16 | `nod_10c2e7b4f6020f1a3a68d389_0035` p. 4 | `open-sourced an AI safety tool called...Inspect` | product capability | Identify the institute's publication and the tool's stated evaluation capabilities. |
| AI-17 | `nod_10c2e7b4f6020f1a3a68d389_0036` p. 4 | `Observers saw the name change` | interpretation control | Keep the inferred future focus attributed to observers. |
| AI-18 | `nod_10c2e7b4f6020f1a3a68d389_0038` p. 4 | `US AISI was founded` | direct multiple | Identify the November 2023 founding, NIST placement, and Elizabeth Kelly leadership. |
| AI-19 | `nod_10c2e7b4f6020f1a3a68d389_0039` p. 4 | `more than 200 organizations such as Google, Anthropic or Microsoft` | high-cardinality | Identify AISIC creation and named examples without inventing membership beyond the source. |
| AI-20 | `nod_10c2e7b4f6020f1a3a68d389_0041` p. 4 | `refused to sign the summit's final communique` | multiple | Identify the US and UK refusal separately from JD Vance's attributed policy position. |
| AI-21 | `nod_10c2e7b4f6020f1a3a68d389_0042` p. 4 | `name of the agency was changed` | identity and attribution | Identify the CAISI rename and transformed mission while preserving Commerce and Lutnick attribution. |
| CS-01 | `nod_3b54ac13ce63f97638fd10cd_0006` p. 1 | `initial members of the network` | high-cardinality and temporal | Identify the named initial network members, launch event, and later Kenya confirmation without treating Italy and Germany as members. |
| CS-02 | `nod_3b54ac13ce63f97638fd10cd_0008` p. 2 | `According to the Seoul Statement` | attribution and modality control | Preserve the statement attribution and its `may include` modality for proposed collaboration mechanisms. |
| CS-03 | `nod_3b54ac13ce63f97638fd10cd_0031` p. 4 | `publicly funded research institutions` | direct | Identify the report's stated AISI purpose and government technical-capacity role. |
| CS-04 | `nod_3b54ac13ce63f97638fd10cd_0032` p. 4 | `research, testing, and guidance` | multiple | Decompose the three functions without claiming they are already complete outcomes. |
| CS-05 | `nod_3b54ac13ce63f97638fd10cd_0037` p. 5 | `Anthropic ... joined the U.S. AISI Consortium` | cross-source direct | Identify Anthropic's AISIC membership and distinguish the Consortium from the generic AISI name. |
| CS-06 | `nod_3b54ac13ce63f97638fd10cd_0051` p. 6 | `Sam Altman stated` | attributed direct | Preserve Altman's statement about OpenAI's early-access agreement and Kelly's separate statement about commitments. |
| CS-07 | `nod_3b54ac13ce63f97638fd10cd_0052` p. 6 | `signed a letter to Congress` | high-cardinality and quotation | Identify the named companies, the letter's organizers, and the request without presenting the letter's advocacy as established fact. |
| CS-08 | `nod_3b54ac13ce63f97638fd10cd_0059` p. 7 | `suggests that more institutes are still to come` | inference control | Preserve the report's tentative language about future institutes and France's not-yet-official status. |
| CS-09 | `nod_3b54ac13ce63f97638fd10cd_0251` pp. 12–13 | `housed under different kinds of public bodies` | organizational comparison | Extract stated institutional homes while retaining the report's qualified claim about possible implications. |
| CS-10 | `nod_3b54ac13ce63f97638fd10cd_0257` p. 13 | `Recommendation` | recommendation control | Do not convert the authors' proposed project prioritization into a network decision or existing policy. |
| CS-11 | `nod_3b54ac13ce63f97638fd10cd_0259` p. 13 | `should look to develop` | recommendation and modality control | Preserve the proposed common methodology and its stated rationale as a recommendation. |
| CS-12 | `nod_3b54ac13ce63f97638fd10cd_0264` p. 14 | `Department of Commerce and U.S. Department of State announced` | attributed event | Separate the agencies' quoted convening goal from the report authors' recommendation and forecast. |

## 3. Coverage summary

The packet contains 50 paragraph-level evidence spans.
It includes direct, decomposable, high-cardinality, and cross-source cases.
It includes explicit controls for attribution, uncertainty, legal status, identity ambiguity, modality, and recommendations.
At least 15 paragraphs require more than one output candidate for complete coverage.
It includes one deliberate cross-source identity control around the ambiguous name `AI Safety Institute`.

The packet does not claim source-level completeness.
It supplies a first representative review set for testing a scalable extraction design.

## 4. PHP-1 development eligibility labels

These labels classify the current PHP-1 organization-to-organization task.
They provide reviewed development feedback for the current packet.

| Case | Label | Reason |
| --- | --- | --- |
| AD-01 | out_of_scope | The paragraph states one policy action. |
| AD-02 | out_of_scope | The paragraph requires causal-event extraction. |
| AD-03 | needs_coreference | The object is unnamed Trump officials. |
| AD-04 | eligible | Anthropic and Congress are named organizations. |
| AD-05 | control | The paragraph tests source attribution. |
| AD-06 | eligible | The paragraph states two named partnerships. |
| AD-07 | eligible | The direct agreement remains reviewable despite identity ambiguity. |
| AD-08 | out_of_scope | The paragraph relates an organization to a product and date. |
| AD-09 | eligible | The paragraph names Anthropic and Palantir. |
| AD-10 | out_of_scope | The paragraph concerns products and contract sequence. |
| AD-11 | out_of_scope | The paragraph concerns policy positions and uses. |
| AD-12 | out_of_scope | The paragraph concerns a value and causal result. |
| AD-13 | eligible | The paragraph names Anthropic and the Department. |
| AD-14 | out_of_scope | The paragraph concerns legal actions by a person. |
| AD-15 | control | The paragraph tests uncertainty. |
| AD-16 | control | The paragraph tests quoted legal argument. |
| AD-17 | out_of_scope | The paragraph concerns a court order status. |
| AI-01 | out_of_scope | The paragraph names states rather than named organizations. |
| AI-02 | needs_multi_segment | The paragraph lists memberships across several spans. |
| AI-03 | eligible | The paragraph states organization lineage. |
| AI-04 | eligible | The paragraph states organization placement. |
| AI-05 | control | The paragraph tests attribution. |
| AI-06 | eligible | The paragraph names two institutes in one agreement. |
| AI-07 | out_of_scope | The paragraph concerns an event and risk themes. |
| AI-08 | needs_multi_segment | The paragraph combines placement, budget, and leadership. |
| AI-09 | eligible | The paragraph states a named partnership. |
| AI-10 | needs_multi_segment | The paragraph enumerates many consultation participants. |
| AI-11 | out_of_scope | The paragraph concerns policy priorities. |
| AI-12 | eligible | The paragraph names UNESCO and MeitY. |
| AI-13 | needs_multi_segment | The paragraph combines creation, mission, and collaboration. |
| AI-14 | eligible | The paragraph states rename, placement, and partnership relations. |
| AI-15 | eligible | The paragraph states organization lineage and placement. |
| AI-16 | out_of_scope | The paragraph concerns a tool and its capabilities. |
| AI-17 | control | The paragraph tests attributed interpretation. |
| AI-18 | eligible | The paragraph states organization founding and placement. |
| AI-19 | needs_multi_segment | The paragraph lists many potential member organizations. |
| AI-20 | out_of_scope | The paragraph concerns a diplomatic refusal and position. |
| AI-21 | needs_multi_segment | The paragraph combines rename, mission, and attribution. |
| CS-01 | needs_multi_segment | The paragraph lists members, events, and later status. |
| CS-02 | control | The paragraph tests attribution and modality. |
| CS-03 | out_of_scope | The paragraph defines a report purpose. |
| CS-04 | out_of_scope | The paragraph lists functions rather than organization relations. |
| CS-05 | eligible | The paragraph states a named consortium membership. |
| CS-06 | needs_multi_segment | The paragraph contains separate attributed statements. |
| CS-07 | needs_multi_segment | The paragraph lists signatories, organizers, and a request. |
| CS-08 | control | The paragraph tests tentative future inference. |
| CS-09 | needs_multi_segment | The paragraph compares several institutional homes. |
| CS-10 | control | The paragraph tests a recommendation. |
| CS-11 | control | The paragraph tests recommendation modality. |
| CS-12 | out_of_scope | The paragraph concerns an attributed event and forecast. |
