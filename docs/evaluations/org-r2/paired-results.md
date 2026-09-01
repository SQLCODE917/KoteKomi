# ORG-R2 paired semantic-qualification results

Each entry compares Qwen2.5 and ReFinED on the same immutable ORG-R1 candidate.
The evaluation is derived from the reviewed Gold catalog; neither producer is authority.
Boundary cases are shown but excluded from semantic scoring.

### development - qfc_dfc696f76ed3353eb1855a7a

> On November 21 and 22, 2024, technical artificial intelligence (AI) experts from nine countries and the European Union will meet for the first time in San Francisco.

Exact candidate: "European Union"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_fddce19273b137f1555995ba

> The agenda: starting the next phase of international cooperation on AI safety science through a network of AI safety institutes (AISIs).

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_33e398a1c11844ca56a1628c

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "United States"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_7bfbb2b76fbba95fcb1d99e6

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "United Kingdom"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_933a409b70dd2e975ef8db7a

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3aeef3042ec35074ce84d54c

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "Japan"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3fa0f91cc5f9436a88de7944

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "Singapore"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, Singapore is mentioned alongside other" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, Singapore is mentioned alongside other" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, Singapore is mentioned alongside other" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_f900f5a5e455338f4039101e

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "South Korea"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_aeeb9a02ad86fbebee8f735e

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "Canada"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_61f323b9efaf6750fee9b0dd

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "France"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_b7a4715dd6438cf1f7890f00

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "Kenya"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_b8b82d5f44756e73daedd189

> The United States, United Kingdom, European Union, Japan, Singapore, South Korea, Canada, France, Kenya, and Australia make up the initial members of the network, which was first launched by U.S. secretary of commerce Gina Raimondo at the May 2024 AI Seoul Summit.

Exact candidate: "Australia"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_dad1785bc3563e88888fe977

> At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.

Exact candidate: "Italy"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_abcd35c0e3ea5d599beb25cf

> At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.

Exact candidate: "Germany"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_2ba27676ac18682ef130cdfb

> At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.

Exact candidate: "the Seoul Statement"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_3696fc329c3281f21cd2b093

> At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.

Exact candidate: "Seoul Statement"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": null} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": null} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": null} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_79f439adf412c516c1df9ec7

> At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.

Exact candidate: "Seoul Statement of Intent toward International Cooperation on AI Safety Science"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_d9a0aa5b7f5c167ad5b378c4

> At the time of the launch, Italy and Germany were also potential members of the network, as signatories to the Seoul Statement of Intent toward International Cooperation on AI Safety Science , or Seoul Statement, the network's founding document.

Exact candidate: "Seoul Statement"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_59ad57b1e2ef6b25ef953762

> However, a September announcement by Raimondo and U.S. secretary of state Antony Blinken confirmed that Kenya would instead be the final member of the AISI International Network at this stage.

Exact candidate: "AISI International Network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e842b0756ed312e8ca23f19d

> According to the Seoul Statement, the international network will serve to 'accelerate the advancement of the science of AI safety' at a global level by promoting 'complementarity and interoperability' between institutes and fostering a 'common international understanding' of AI safety approaches.

Exact candidate: "international network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_ed1045771e3eaf3f334828db

> While the statement does not define specific goals or mechanisms for AISI collaboration, it suggests that they 'may include' coordinating research, sharing resources and relevant information, developing best practices, and exchanging or codeveloping AI model evaluations.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_24e38c6b58a9cadbcfb56f3d

> Now, in the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI network"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_9d57e1f87d01f3c010bdd5a3

> Now, in the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_c14a55ef26e05bda9c9f1531

> Now, in the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_67ecc7675e901e5b33821d2d

> Since 2023, governments around the world have mobilized around AI's rapidly growing capabilities and potential risks.

Exact candidate: "governments"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_f53206db8c82610d5c1f66a0

> As part of this effort, several governments have launched AI safety institutes, publicly funded research institutions focused on mitigating risks from the frontier of AI development.

Exact candidate: "AI safety institutes"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_3cf5931d4a6e005556cfd747

> As part of this effort, several governments have launched AI safety institutes, publicly funded research institutions focused on mitigating risks from the frontier of AI development.

Exact candidate: "publicly funded research institutions"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_a54c895513db937edc546098

> AISIs provide governments with in-house technical expertise and organizational capacity to evaluate and monitor cutting-edge AI models for risks to public and national security.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_960218bccbc87fdf46370fc7

> AISIs have been tasked by governments with a wide-ranging mandate to address the complex challenges posed by advanced AI systems.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_0d2ef05a7a13c1df8e054edc

> They will perform foundational technical research, develop guidance for the public and private sectors, and work closely with companies to test models before deployment.

Exact candidate: "companies"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_ddae204a262a9a837f16fac9

> While it is unusual for a single government entity to tackle all three of these functions at once, the breakneck speed of AI development and the staggering number of open questions in the field of AI safety research mean that governments require in-house capacity on each of them.

Exact candidate: "governments"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nExplanation:\n- \"governments\" in the" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nExplanation:\n- \"governments\" in the" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nExplanation:\n- \"governments\" in the" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_564ae5b69406bbb99ac9be5e

> AISIs are engaging a wide range of stakeholders on each of their core functions.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_1f048b53275700d365e26b13

> Far from fearing the launch of AISIs worldwide, firms and universities engaged in advanced AI have called for governments to increase their capacity to perform AI research, conduct testing, and issue guidance.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_45a6c329d445f5559609578b

> Far from fearing the launch of AISIs worldwide, firms and universities engaged in advanced AI have called for governments to increase their capacity to perform AI research, conduct testing, and issue guidance.

Exact candidate: "firms and universities"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_704784deb2c544946cdd7dae

> Far from fearing the launch of AISIs worldwide, firms and universities engaged in advanced AI have called for governments to increase their capacity to perform AI research, conduct testing, and issue guidance.

Exact candidate: "governments"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_ab61d71565fef53eb057e6ac

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "Google"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_018dcebb215ed99d5261cebf

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "Microsoft"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8cea10c2afd4a9a4bb1c60dc

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_52b6bd3aedaab544c10ab3aa

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "Amazon"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_678ead14b1f3289102b155a7

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "U.S. AISI Consortium"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI Consortium (AISIC)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_113cf283bc7fab15ec35c562

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "U.S. AISI Consortium (AISIC)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_a74db9ea616d94117f979f78

> Earlier this year , top U.S. AI companies such as Google, Microsoft, Anthropic, and Amazon joined the U.S. AISI Consortium (AISIC) as part of its inaugural cohort of members.

Exact candidate: "AISIC"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI Consortium (AISIC)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_6d119b29245f93d782f62141

> AISIC is composed of over 200 organizations from across the private sector, academia, civil society, and government and facilitates collaboration on AI safety research and evaluations.

Exact candidate: "AISIC"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_5ea605881f635727d671ca5c

> In August, OpenAI chief executive officer Sam Altman stated that his company has been working closely with the U.S. AISI on an agreement to provide early access to its next foundation model for safety testing and evaluations.

Exact candidate: "OpenAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_ca6167e8ce697a021ced2c51

> In August, OpenAI chief executive officer Sam Altman stated that his company has been working closely with the U.S. AISI on an agreement to provide early access to its next foundation model for safety testing and evaluations.

Exact candidate: "U.S. AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_f720e0e383cd87fadc5a9af8

> In August, OpenAI chief executive officer Sam Altman stated that his company has been working closely with the U.S. AISI on an agreement to provide early access to its next foundation model for safety testing and evaluations.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_1fd7335b6926f0c32207ca02

> OpenAI is not alone in providing the U.S. AISI access to its models for testing.

Exact candidate: "OpenAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_57fa364225159b9001f3effc

> OpenAI is not alone in providing the U.S. AISI access to its models for testing.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe mention \"AISI\" could refer to" → `None` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe mention \"AISI\" could refer to" → `None` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe mention \"AISI\" could refer to" → `None` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_f1a54a451b0d773e7dde964e

> Director Kelly said that the institute has 'commitments from all of the leading frontier model developers to work with them on these tests.'

Exact candidate: "institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_8f9ceff031e290b5a56e1608

> These commitments demonstrate that leading companies understand the need for AI safety research and recognize the important role that the U.S. AISI has to play.

Exact candidate: "U.S. AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_34fb371c37cc301f7bfaf05b

> These commitments demonstrate that leading companies understand the need for AI safety research and recognize the important role that the U.S. AISI has to play.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_ff4ecf65afab8b9fc8720a37

> While critics have questioned how industry will balance competition and safety, AISIs are free from the financial self-interest which has caused some to question the adequacy of private AI safety efforts in the past.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_631d2d1327cc1ab16e6a881d

> On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year.

Exact candidate: "Amazon"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_8357380ff220a2dc5cfb4f73

> On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year.

Exact candidate: "Meta"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_eebc08de6af232dec421d871

> On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year.

Exact candidate: "Microsoft"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_88894d74a093f57429c072fa

> On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year.

Exact candidate: "OpenAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_a99cac98fa65a16bf4faca2e

> On October 21, top AI developers including Amazon, Meta, Microsoft, and OpenAI signed a letter to Congress calling on lawmakers to authorize the U.S. AISI before the end of the year.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_7a092ffa66c369d5a8b81fb6

> The letter, which was led by Americans for Responsible Innovation and the Information Technology Industry Council (ITI), states that "[a]s other nations around the world are establishing their own AI Safety Institutes, furthering NIST's ongoing efforts is essential to advancing U.S. AI innovation, leadership, and national security." "Authorizing legislation, and the accompanying necessary resources,' it argues, 'will give much needed certainty to NIST's role in AI safety and reliability.'

Exact candidate: "Americans for Responsible Innovation"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8489161f0fc687ac1aa77108

> The letter, which was led by Americans for Responsible Innovation and the Information Technology Industry Council (ITI), states that "[a]s other nations around the world are establishing their own AI Safety Institutes, furthering NIST's ongoing efforts is essential to advancing U.S. AI innovation, leadership, and national security." "Authorizing legislation, and the accompanying necessary resources,' it argues, 'will give much needed certainty to NIST's role in AI safety and reliability.'

Exact candidate: "Information Technology Industry Council (ITI)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3d0a9388130657f243515996

> The letter, which was led by Americans for Responsible Innovation and the Information Technology Industry Council (ITI), states that "[a]s other nations around the world are establishing their own AI Safety Institutes, furthering NIST's ongoing efforts is essential to advancing U.S. AI innovation, leadership, and national security." "Authorizing legislation, and the accompanying necessary resources,' it argues, 'will give much needed certainty to NIST's role in AI safety and reliability.'

Exact candidate: "NIST"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_afd2c23ffd7d6b7b539e1789

> The letter, which was led by Americans for Responsible Innovation and the Information Technology Industry Council (ITI), states that "[a]s other nations around the world are establishing their own AI Safety Institutes, furthering NIST's ongoing efforts is essential to advancing U.S. AI innovation, leadership, and national security." "Authorizing legislation, and the accompanying necessary resources,' it argues, 'will give much needed certainty to NIST's role in AI safety and reliability.'

Exact candidate: "NIST"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_75a2e2602e4f1c13533921c5

> The first AISIs were announced last year, with the United States and United Kingdom launching initiatives at the UK AI Safety Summit in November 2023.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_b7c3496ee0d933c923c4806c

> Japan , Singapore , and the European Union's EU AI Office followed in early 2024.

Exact candidate: "Japan"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_cdd093a9e785b0a65b78e5af

> Japan , Singapore , and the European Union's EU AI Office followed in early 2024.

Exact candidate: "Singapore"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_9d5cbe920ef1b06babdcc6f2

> Japan , Singapore , and the European Union's EU AI Office followed in early 2024.

Exact candidate: "European Union"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "European Union's EU AI Office"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_7db9cbd0e50c89b931dfc04f

> Japan , Singapore , and the European Union's EU AI Office followed in early 2024.

Exact candidate: "European Union's EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_c40f741da87268ac1d853484

> Japan , Singapore , and the European Union's EU AI Office followed in early 2024.

Exact candidate: "EU AI Office"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "European Union's EU AI Office"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_3cbc52715008d41ecbb9b49d

> Since then, Canada and South Korea have revealed plans for their own AISIs.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_3c053d99a233c09a094aeb58

> The inclusion of France, Kenya, and Australia in the AISI network suggests that more institutes are still to come.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_4b937b552fc3d4b46adcb502

> For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.

Exact candidate: "Laboratoire National de Métrologie et d'Essais"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Laboratoire National de Métrologie et d'Essais (LNE)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_8686eba0bddf4ab81b4c8ab2

> For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.

Exact candidate: "Laboratoire National de Métrologie et d'Essais (LNE)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_5f8caebd4dc66ed88e95f3f0

> For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.

Exact candidate: "LNE"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Laboratoire National de Métrologie et d'Essais (LNE)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_6181cad94a419847f90d1e8a

> For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.

Exact candidate: "National Institute for Research in Digital Science and Technology"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "National Institute for Research in Digital Science and Technology (Inria)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_2e28140dc15ba1fbc55310a2

> For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.

Exact candidate: "National Institute for Research in Digital Science and Technology (Inria)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_dda3303167fdd2d20c54a2a8

> For instance, in May French research institutions Laboratoire National de Métrologie et d'Essais (LNE) and National Institute for Research in Digital Science and Technology (Inria) announced a partnership to set up an 'AI Evaluation' program that will advance research and the development of testing and evaluation methods for general-purpose AI models at the national level.

Exact candidate: "Inria"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "National Institute for Research in Digital Science and Technology (Inria)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_74b5ca85d090d6fec89022b9

> It is worth noting, however, that while institutes share many similarities in funding, size, and functions, they are housed under different kinds of public bodies.

Exact candidate: "institutes"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_11966e9aec55fa559bc58f3e

> Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).

Exact candidate: "U.S. National Institute of Standards and Technology (NIST)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_0acb6b5b093ddd2907e9037b

> Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).

Exact candidate: "National Institute of Standards and Technology"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. National Institute of Standards and Technology (NIST)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_021e33e9535439cfc594ae36

> Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).

Exact candidate: "NIST"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. National Institute of Standards and Technology (NIST)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_fb129698afe8d953ef737f7b

> Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).

Exact candidate: "UK Department for Science, Innovation and Technology (DSIT)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_6c4c4079e82673745e0d0ebf

> Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).

Exact candidate: "Japanese Information Technology Promotion Agency"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Japanese Information Technology Promotion Agency (IPA)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_f9fd115609367a988bd94881

> Several institutes are located within government agencies focused on technological innovation and standards, including the U.S. National Institute of Standards and Technology (NIST); the UK Department for Science, Innovation and Technology (DSIT); and the Japanese Information Technology Promotion Agency (IPA).

Exact candidate: "Japanese Information Technology Promotion Agency (IPA)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_b7fe697dd5ffbb7989536be0

> Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University.

Exact candidate: "South Korean Electronics and Telecommunications Research Institute"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "South Korean Electronics and Telecommunications Research Institute (ETRI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_0b2e282678c0443163ef36d9

> Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University.

Exact candidate: "South Korean Electronics and Telecommunications Research Institute (ETRI)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_79865ea5ab3cc223ad5ee3e0

> Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University.

Exact candidate: "ETRI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "South Korean Electronics and Telecommunications Research Institute (ETRI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_3f7c8f3ecab925fb36c12225

> Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University.

Exact candidate: "Singaporean Digital Trust Centre"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_d82a2b6001dd8942180b4f13

> Others are housed in government-funded research organizations, like the South Korean Electronics and Telecommunications Research Institute (ETRI) and the Singaporean Digital Trust Centre, itself a part of Nanyang Technological University.

Exact candidate: "Nanyang Technological University"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_f253d161516832c21599228c

> Finally, as Table 2 illustrates, the EU AI Office has the largest set of functions as an institution that promotes innovation, research, and regulatory compliance to the EU AI Act.

Exact candidate: "EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3803009d9c251bb4c32679ac

> The different kinds of home institutions in which AISIs are housed may have implications for the focus and capacity of different network members, and therefore the strengths that each member may bring to the network.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_52a1d784fc75ac9a66f09582

> In the medium term, network members should look to develop a common, evidence-based approach to AISIs' testing and evaluation methodologies.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_8b13979528a8257dae1b001a

> While not all AISIs may necessarily have the same requirements for assessing models, they should at least have a common understanding of what methodologies such as 'red teaming' comprise.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_868bb281540a73c24576004f

> Developing a consensus on testing and evaluation methods would help to deconflict and de-duplicate efforts between AISIs and to facilitate other areas of collaboration in the future, such as promoting safety guidelines or developing joint evaluation tools.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_807f394b9ea65601243eaa30

> If the AISI network can start by ensuring that AISIs all speak the same language in AI safety, more elaborate collaboration projects can take place.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI network"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_5c112e915ecaaac18453fbb7

> Recommendation: There are two big international events related to AI safety on the horizon that offer some initial deadlines for AISI network deliverables.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI network"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_aa8e3d32595dd3b942da84f3

> In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports.

Exact candidate: "U.S. Department of Commerce"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8a6640f5218c35a5236a09a4

> In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports.

Exact candidate: "U.S. Department of State"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e59f02537571cd0238e51a41

> In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports.

Exact candidate: "the Network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_e2ebca099c4457bb9f3401f9

> In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports.

Exact candidate: "Network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_6ae6e79a23cb094397bbe9a1

> In September, the U.S. Department of Commerce and U.S. Department of State announced that 'the goal of this convening is to kickstart the Network's technical collaboration ahead of the AI Action Summit in Paris in February 2025,' starting with aligning 'on priority work areas for the Network,' as the recommendation above supports.

Exact candidate: "the Network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_d76cce753098e3149b87a73b

> The AI Action Summit will be the third of its kind since the UK AI Safety Summit last year and offers a high-profile, public venue in which to showcase the AISI network and its work.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_f4fa169bb2578adde86c15d7

> These two events-in November 2024 and February 2025-are mere moments away in the context of international collaboration.

Exact candidate: "international collaboration"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_47b6e6e7a210d4a334d7920f

> If AISI members can capitalize on their opportunities, however, they could significantly contribute to the network's mission of accelerating AI safety science.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_4d36dca885862b3927746df8

> The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.

Exact candidate: "United States Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_80a4b8adf5cd342bc67fb7d0

> The United States Department of Defense began developing lethal autonomous weapons as early as the Reagan administration.

Exact candidate: "Reagan administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_93cdc9e3d67c5232ed6dc1b7

> [1] The Department of Defense established a policy on the use of artificial intelligence in 2012, Directive 3000.09.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_58e9d4903b2afb4e8f00e947

> [3] The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_cd2cbfb7db56e972d590ab03

> [3] The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.

Exact candidate: "Project Maven"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_5f06a006f5fc8ef8fc73e2c1

> [3] The Department of Defense's use of artificial intelligence for Project Maven prompted concerns within Google in 2018, leading to protests and mass resignations.

Exact candidate: "Google"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n[3" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n[3" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n[3" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_24655b834f9c9a05c4713f8b

> In Donald Trump's second presidency, Anthropic publicly disagreed with the administration's policies and initiatives.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is likely referring to the AI research company" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is likely referring to the AI research company" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is likely referring to the AI research company" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_191e61a85854ed04a4510e3a

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_e885fa88b749d656f395fb19

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.

Exact candidate: "Stargate"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_2c0db46e8f9036a7ab38e2d7

> In January 2025, Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate as "chaotic" and opposed Trump's rescission of president Joe Biden's Executive Order on Artificial Intelligence, but noted that Anthropic had held discussions with Trump officials about artificial intelligence policy.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_ec4c5968ed602117b9cad20e

> [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_d8da6cd670c61313ba5b045c

> [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.

Exact candidate: "Congress"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3687980398ac12153902149e

> [5] Amid discussions over the One Big Beautiful Bill Act, Anthropic privately lobbied for Congress to vote against a bill preventing states from regulating artificial intelligence and expressed opposition to an artificial intelligence agreement signed among Gulf states in Trump's visit to the Middle East in May.

Exact candidate: "Gulf states"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": false} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": false} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": false} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_e32883c908e6c1918dd33546

> According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.

Exact candidate: "Semafor"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_b342df117c0db9b96cfc1ff6

> According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_c0237786e6865f3d5a656d3d

> According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.

Exact candidate: "Artificial Intelligence Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_c87221a83569edbc32bee91f

> According to Semafor , Trump officials chastised Anthropic's hiring of several officials involved in the Biden administration, including Elizabeth Kelly, the former director of the Artificial Intelligence Safety Institute; Tarun Chhabra, the coordinator for technology and national security in the National Security Council; and Ben Buchanan, Biden's advisor for artificial intelligence.

Exact candidate: "National Security Council"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_0dc07df8bb739a2d4d6736a9

> [6] The following month, Amodei wrote an op-ed in The New York Times describing the artificial intelligence regulation bill, then tied to the One Big Beautiful Bill Act, as "far too blunt an instrument".

Exact candidate: "The New York Times"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_ceea1a4afabaefe5de93f7c5

> Prior to the dispute, the Trump administration had integrated Anthropic's services.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is typically known as a company or organization" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is typically known as a company or organization" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is typically known as a company or organization" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_eb479c0d5b0d0c3f0b27a7d6

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nAnthropic is described in the context of" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nAnthropic is described in the context of" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nAnthropic is described in the context of" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_6b38da5628713b9ff0662e07

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Exact candidate: "Palantir"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_45fa688feeda2dcc1bb90754

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Exact candidate: "Amazon Web Services"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_bd0df9b90508f96967a9df02

> In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.

Exact candidate: "Biden administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_de6e6fc883ce44e4a1cd7a12

> In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is typically known as a company or organization" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is typically known as a company or organization" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is typically known as a company or organization" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_427f5d4a869579b42cbfae53

> In the Biden administration, Anthropic had reached an agreement with the AI Safety Institute and had participated in a nuclear information safety evaluation.

Exact candidate: "AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_f467087a905a58d565fd6891

> [8] The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.

Exact candidate: "Department of Homeland Security"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_6b3824af9299a3ca355175ae

> [8] The Department of Homeland Security authorized its workers to use commercial artificial intelligence systems, including Anthropic's Claude, until May 2025.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_8a9e9a57c2f99ae6d40b4a37

> [9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.

Exact candidate: "Palantir"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_a536607085a9f42903d61643

> [9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e1ba284190265ddc955e4562

> [9] Through its interoperability with Palantir, a company heavily involved in data analysis and analytics at the Department of Defense, Anthropic's technology achieved relatively widespread usage in the U.S. military.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_41d03b97907a4240329a7f57

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_74e022bbde8b9ebe15f8e90e

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_12773aec80662c046a2c1828

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Federal Bureau of Investigation"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_71ce59fbfd7550b32793fff6

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Secret Service"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8e15f2ff12cc1f6ab984b087

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Immigration and Customs Enforcement"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_33c1bc1bbd12240c34ec1b08

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_1dd6a84455f1251a7fb4bd3f

> [10] The following month, Anthropic announced that it would allow national security customers to use Claude Gov. [11][12] Anthropic's orthogonal usage policy to the surveillance systems implemented at the Federal Bureau of Investigation, the Secret Service, and Immigration and Customs Enforcement led to a conflict between Anthropic and the Trump administration by September.

Exact candidate: "Trump administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_cadc45e88b8d112bd5caf5fe

> In December 2025, secretary of defense Pete Hegseth announced GenAI.mil, an artificial intelligence platform for the Department of Defense.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_a083af21fb848a3e1cfff830

> The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT.

Exact candidate: "Google"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_ab13dfa244feb60c19d97960

> The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT.

Exact candidate: "Google Gemini"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Google"

Run 1:

Qwen2.5: "not_organization" → `not_organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "not_organization" → `not_organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "not_organization" → `not_organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_cbc6f818b0cd79d79c954309

> The department initially contracted Google Gemini for the platform, then OpenAI's ChatGPT.

Exact candidate: "OpenAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_f3d00f9c335216e86bef1196

> [19][20] The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI".

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_947e2e0d09b5b74d05a42fe0

> [19][20] The following month, Hegseth announced that the Department of Defense would additionally contract xAI's Grok for use in the military, decrying "woke AI".

Exact candidate: "xAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_3be6a718266ce187cef0cf28

> In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.

Exact candidate: "Semafor"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_490dd2988ec64840d38c527c

> In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3722a8ac82a813df77185cc2

> In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_20a6cef73c79acdaa78d11b2

> In January 2026, Semafor reported that the Department of Defense had conflicted with Anthropic over its policies on lethal military force and that Hegseth's comment on woke AI was a reference to Anthropic.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_70975c877270fc1b6982fc14

> [22] According to Reuters, Anthropic representatives opposed the use of the company's products for surveillance or to develop lethal autonomous weapons.

Exact candidate: "Reuters"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_76c102ee90f41e150659ca97

> [22] According to Reuters, Anthropic representatives opposed the use of the company's products for surveillance or to develop lethal autonomous weapons.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_99011825cbd568089160a521

> [23] The dispute between Anthropic and the Department of Defense resulted in the termination of a contract worth an estimated US$200 million.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_44fc61a79647f45a5618c626

> [23] The dispute between Anthropic and the Department of Defense resulted in the termination of a contract worth an estimated US$200 million.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_f4fedf269131ffd1219a8234

> In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's Claude, to unclassified and classified domains.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_0f565859964cfa9e05776afa

> In February 2026, Emil Michael, the under secretary of defense for research and engineering, stated that the Department of Defense would expand access to commercial artificial intelligence systems, including Anthropic's Claude, to unclassified and classified domains.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of a commercial" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of a commercial" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of a commercial" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_c5a670a8a0b646e1301291ce

> [25] That month, Axios reported that the Department of Defense had used Claude in the United States intervention in Venezuela.

Exact candidate: "Axios"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_1685d7efa894bec511ccc69a

> [25] That month, Axios reported that the Department of Defense had used Claude in the United States intervention in Venezuela.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_4681711672646515fd9a1e0f

> Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_bc73d7f53496b1bf8b5b42b3

> Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.

Exact candidate: "Axios"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_66879a8173a4d6b4ae77685d

> Anthropic told Axios that it would reassess its partnership with the Department of Defense after the revelations.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_cd33cd89df2eb742bd1ce3d8

> [26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the department threatened to cancel its contracts with the company.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_4628e9b08768066ddae0f574

> [26] After Anthropic refused to agree to allow the Department of Defense to use Claude for "all lawful purposes", the department threatened to cancel its contracts with the company.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_93763ae4114deefc89559d45

> [27] Hegseth additionally moved to label Anthropic a "supply chain risk", which would have forced military contractors to cut ties with Anthropic.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_80d387cfe32f30a1712639e2

> [27] Hegseth additionally moved to label Anthropic a "supply chain risk", which would have forced military contractors to cut ties with Anthropic.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_4dea490c4349c4c688257fce

> [29][30] The D.C. Circuit denied Anthropic's emergency motion for a stay of the FASCSA designation in April so it remains in effect for covered systems.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_7920d39398252ea43fd08229

> In a June 2026 Bloomberg interview about Claude's reported role in U.S. military targeting systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike, but that, if it had, the use case would not violate Anthropic's red lines.

Exact candidate: "U.S. military"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_70bd2599a5f7848600be1439

> In a June 2026 Bloomberg interview about Claude's reported role in U.S. military targeting systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike, but that, if it had, the use case would not violate Anthropic's red lines.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_ddaebd0c1030c6f3b2b4848f

> In a June 2026 Bloomberg interview about Claude's reported role in U.S. military targeting systems, Amodei said Anthropic did not know whether Claude had been used in connection with the Minab school strike, but that, if it had, the use case would not violate Anthropic's red lines.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_31ad05d1f47fbb1a340e7cd2

> [35][36] The exchange concerned the 2026 Minab school strike, which Amnesty International described as an unlawful U.S. strike that killed 156 people, including 120 children, and which Human Rights Watch said should be investigated as a war crime.

Exact candidate: "Amnesty International"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_d770b2d880eea27449524f39

> [35][36] The exchange concerned the 2026 Minab school strike, which Amnesty International described as an unlawful U.S. strike that killed 156 people, including 120 children, and which Human Rights Watch said should be investigated as a war crime.

Exact candidate: "Human Rights Watch"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_b920826a3251aa44f49a1ace

> The Department of War's records show that it designated Anthropic as a supply chain risk because of its 'hostile manner through the press.'

Exact candidate: "The Department of War"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Department of War"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_a584dd8b624d964b05e348cb

> The Department of War's records show that it designated Anthropic as a supply chain risk because of its 'hostile manner through the press.'

Exact candidate: "Department of War"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e57529802675e5a8470df497

> The Department of War's records show that it designated Anthropic as a supply chain risk because of its 'hostile manner through the press.'

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in a context that does not" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in a context that does not" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in a context that does not" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_99fd220d267a93c15903d1c3

> Punishing Anthropic for bringing public scrutiny to the government's contracting position is classic illegal First Amendment retaliation.

Exact candidate: "government"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_0acf9f8b7194f2c41aeb2e5e

> At bottom, Anthropic has shown that these broad punitive measures were likely unlawful and that it is suffering irreparable harm from them.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_d94adf016e0b826526475b48

> Numerous amici have also described wide-ranging harm to the public interest, including the chilling of open discussion about important topics in AI safety.

Exact candidate: "Numerous amici"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_840ec52f3a9ecb0997b691ac

> In April 2026, the Court of Appeals for the D.C. Circuit in a per curiam order denied Anthropic's motion to lift the FASCSA designation.

Exact candidate: "Court of Appeals for the D.C. Circuit"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_35ae8b3f11439a43f887b935

> In April 2026, the Court of Appeals for the D.C. Circuit in a per curiam order denied Anthropic's motion to lift the FASCSA designation.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of a legal" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of a legal" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of a legal" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_af5aff6448d136c3285192ee

> The court's order said lifting the designation "would force the United States military to prolong its dealings with an unwanted vendor of critical AI services in the middle of a significant ongoing military conflict".

Exact candidate: "United States military"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_ef5740d938ddc076d36d2c4e

> According to Wired , "Several experts in government contracting and corporate rights" said "Anthropic has a strong case against the government, but the courts sometimes refuse to overrule the White House on matters related to national security." [46]

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### development - qfc_f389c3ac91b2291647e9a337

> According to Wired , "Several experts in government contracting and corporate rights" said "Anthropic has a strong case against the government, but the courts sometimes refuse to overrule the White House on matters related to national security." [46]

Exact candidate: "White House"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "FAC", "failed_class_check": false} → `not_organization` (incorrect; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "FAC", "failed_class_check": false} → `not_organization` (incorrect; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "FAC", "failed_class_check": false} → `not_organization` (incorrect; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_3ec883ec93ceb4213fc9091f

> During the AI Safety Summit in November 2023, the United Kingdom and the United States both created their own AISI.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe term \"AISI\" in the given" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe term \"AISI\" in the given" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe term \"AISI\" in the given" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_18c23aa638a08602bd6c6de0

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "AI Safety Institutes"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_860357d36f674ad95645a67a

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "UK"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_d1cbf50bb9aeec1186820a0e

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "US"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nUS is used as an acting government in" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nUS is used as an acting government in" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nUS is used as an acting government in" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_04c68b6dab50db6623a00aa4

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "Japan"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_ae477c14dce40ed5f2eb0370

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "France"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_5200d00a4888fbed034e070b

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "Germany"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_96799bed802fd8f5892b71c0

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "Italy"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Italy\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Italy\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Italy\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_e4295874c53585fcd08426f1

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "Singapore"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Singapore\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Singapore\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Singapore\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_83d4f29198d3767bb443d3ef

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "South Korea"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_785820fe2111cda3cc05e062

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "Australia"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Australia\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Australia\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Australia\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_87c12cf70d360639fb48b996

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "Canada"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Canada\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Canada\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Canada\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_1b3298907a0ffa1c6e9a1911

> During the AI Seoul Summit in May 2024, international leaders agreed to form a network of AI Safety Institutes, comprising institutes from the UK, the US, Japan, France, Germany, Italy, Singapore, South Korea, Australia, Canada and the European Union.

Exact candidate: "European Union"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_006f2a9a5857dbc60a2e98a1

> [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).

Exact candidate: "UK's AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_55ccec26a0aa6e571ec06c83

> [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).

Exact candidate: "AI Safety Institute"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "UK's AI Safety Institute"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_25643813f90192439d41cf54

> [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).

Exact candidate: "AI Security Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_12e2e40d731996f160910195

> [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).

Exact candidate: "Center for AI Standards and Innovation"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for AI Standards and Innovation (CAISI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_593f9bd84f4a1decf0ee7350

> [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).

Exact candidate: "Center for AI Standards and Innovation (CAISI)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_9c014197cc7a6a9007e4cd65

> [1] In 2025, the UK's AI Safety Institute was renamed the "AI Security Institute", and its US counterpart became the Center for AI Standards and Innovation (CAISI).

Exact candidate: "CAISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for AI Standards and Innovation (CAISI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_bc666a3d556a8ef6d1b761a9

> In 2023, Rishi Sunak, the Prime Minister of the United Kingdom, expressed his intention to "make the UK not just the intellectual home but the geographical home of global AI safety regulation" and unveiled plans for an AI Safety Summit.

Exact candidate: "global AI safety regulation"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_a8900c70b52a2c7b69bc495b

> [3] He emphasized the need for independent safety evaluations, stating that AI companies cannot "mark their own homework".

Exact candidate: "AI companies"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_b44b55e4fbee1b26bcd67707

> [4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.

Exact candidate: "UK AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_45519bad43a2059968454620

> [4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.

Exact candidate: "Frontier AI Taskforce"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_e8fd28c6a66cfa24f5af83aa

> [4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.

Exact candidate: "US AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n[4" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n[4" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n[4" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_06986b3af1a4cef1d79444b2

> [4] During the summit in November 2023, the UK AISI was officially established as an evolution of the Frontier AI Taskforce , [5] and the US AISI as part of the National Institute of Standards and Technology.

Exact candidate: "National Institute of Standards and Technology"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_1bcca530be9f0bde8acb6360

> Japan followed by launching an AI safety institute in February 2024.

Exact candidate: "AI safety institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_ace3917a9304758915709aba

> Politico reported in April 2024 that many AI companies had not shared pre-deployment access to their most advanced AI models for evaluation.

Exact candidate: "Politico"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_38917ab8d0ec7f68dca52bf6

> Politico reported in April 2024 that many AI companies had not shared pre-deployment access to their most advanced AI models for evaluation.

Exact candidate: "AI companies"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_d9845c4daa3bf91d96362984

> Meta's president of global affairs Nick Clegg said that many AI companies were waiting for the UK and the US AI Safety Institutes to work out common evaluation rules and procedures.

Exact candidate: "Meta"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_400f6f3c16e2dd8d87c53e80

> Meta's president of global affairs Nick Clegg said that many AI companies were waiting for the UK and the US AI Safety Institutes to work out common evaluation rules and procedures.

Exact candidate: "AI Safety Institutes"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_554384b51365160fdbb58359

> [8] Initially established in London, the UK AI Safety Institute announced in May 2024 that it would open an office in San Francisco, where many AI companies are located.

Exact candidate: "UK AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_c8260665dc51a6bd87de6a49

> In July 2025, the international network held an exercise to explore issues with evaluating AI agents, especially when it came to leaking sensitive information or cybersecurity.

Exact candidate: "international network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_1e4b6a339cf78e0ba96be879

> [11] Network members also met at NeurIPS 2025 in the city of San Diego.

Exact candidate: "Network members"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_ff8ba391fa621aa1cb2b54d9

> The Albanese government announced the creation of the Australian AI Safety Institute on 25 November 2025.

Exact candidate: "Albanese government"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_78ec0f67dc0d63508671640f

> The Albanese government announced the creation of the Australian AI Safety Institute on 25 November 2025.

Exact candidate: "Australian AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_3f1d9c986651994c9d987a94

> [13] The institute is housed within the Department of Industry, Science and Resources [14] and is supported by a budget of A$29,900,000 over four years.

Exact candidate: "Department of Industry, Science and Resources"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_23dcf5c7b24286318cb3ef02

> [14] Its general manager is Kate Conroy, who is also the lead of responsible AI in the Royal Australian Air Force.

Exact candidate: "Royal Australian Air Force"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e7997694229326076382de8d

> Canada announced in April 2024 that it would create an AI safety institute, [15] and such an institute was officially founded in November 2024.

Exact candidate: "AI safety institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_05b81efd1fb01c03ea5becd0

> [16] The institute is housed under Innovation, Science and Economic Development Canada, though it also partners with the Canadian Institute for Advanced Research (CIFAR).

Exact candidate: "Innovation, Science and Economic Development Canada"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_43e5c6a469f65b06fd2f41d8

> [16] The institute is housed under Innovation, Science and Economic Development Canada, though it also partners with the Canadian Institute for Advanced Research (CIFAR).

Exact candidate: "Canadian Institute for Advanced Research"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Canadian Institute for Advanced Research (CIFAR)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_c762795e0e8a4bc18a8cb31c

> [16] The institute is housed under Innovation, Science and Economic Development Canada, though it also partners with the Canadian Institute for Advanced Research (CIFAR).

Exact candidate: "Canadian Institute for Advanced Research (CIFAR)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_5d472ddf9b6c4b292195eae5

> [16] The institute is housed under Innovation, Science and Economic Development Canada, though it also partners with the Canadian Institute for Advanced Research (CIFAR).

Exact candidate: "CIFAR"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Canadian Institute for Advanced Research (CIFAR)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_829dfff7d0f1cbf6ba1a6cd6

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "The Ministry of Electronics and Information Technology"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Ministry of Electronics and Information Technology"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_3c4eb1b16066c2cbd8600a81

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Meta Platforms"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_61df565ce103154ffb41ab4d

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Google"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_18aa72eb76c1cd22c3fed484

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Microsoft"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_6f2805b4163f0beeaaa1dd51

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "IBM"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_888c13b56dfd63a3ea6362e5

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "OpenAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_fc9f48bebd02bc4fdf09bc44

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "NASSCOM"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8983ce6f56d85188e4bfac59

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Broadband India Forum"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_6b21b711ecf8ee567576abd6

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Software Alliance"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8b717f9e3a5efadeae55b372

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Indian Institutes of Technology (IITs)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e13c03d7600bd9b2a9b221a2

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "The Quantum Hub"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_1b0bf3d0f48ea082b189f38e

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Digital Empowerment Foundation"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_35d581eae1ebcc450087e2c8

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "Access Now"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_6d0458fca515099ec5436366

> The Ministry of Electronics and Information Technology held consultations with Meta Platforms, Google, Microsoft, IBM, OpenAI, NASSCOM, Broadband India Forum, Software Alliance, Indian Institutes of Technology (IITs), The Quantum Hub, Digital Empowerment Foundation, and Access Now on October 7, 2024, in relation to the establishment of the AI Safety Institute.

Exact candidate: "AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_00c6def29b92e3eb1ec7e593

> The AISI may spend the ₹ 20 crore allotted to the Safe and Trusted Pillar of the IndiaAI Mission for the initial budget.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_d9e4bedbcfc5344f3d368bd1

> The AISI may spend the ₹ 20 crore allotted to the Safe and Trusted Pillar of the IndiaAI Mission for the initial budget.

Exact candidate: "IndiaAI Mission"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_6c15aaa88989ab40f3abec29

> Future funding may come from other components of the IndiaAI Mission.

Exact candidate: "IndiaAI Mission"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_044db5823b95e82cb2b221cb

> UNESCO and MeitY began consulting on AI Readiness Assessment Methodology under Safety and Ethics in Artificial Intelligence from 2024.

Exact candidate: "UNESCO"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_6eeaf1f0c186d9b0b7e54ecb

> UNESCO and MeitY began consulting on AI Readiness Assessment Methodology under Safety and Ethics in Artificial Intelligence from 2024.

Exact candidate: "MeitY"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_a3282d677c10026693f9349b

> The study will find areas where government can become involved, especially in attempts to strengthen institutional and regulatory capabilities.

Exact candidate: "government"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_1adaf647e0b2c766b6e49667

> Minister for Electronics & Information Technology Ashwini Vaishnaw announced the creation of an IndiaAI Safety Institute on January 30, 2025, to ensure the ethical and safe application of AI models.

Exact candidate: "IndiaAI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_8728110fcdae27aed70943ae

> The institute will promote domestic R&D that is grounded in India's social, economic, cultural, and linguistic diversity and is based on Indian datasets.

Exact candidate: "The institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_a3bfd93b7e2a2205b8a1c1f3

> With the help of academic and research institutions, as well as private sector partners, the institute will follow the hub-and-spoke approach to carry out projects within Safe and Trusted Pillar of the IndiaAI Mission.

Exact candidate: "IndiaAI Mission"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_981faf71a2e541843b1e72d0

> [23][24] It operates under a "hub-and-spoke" model with collaboration from academic institutions (e.g., IITs), tech firms, and international organizations like UNESCO.

Exact candidate: "IITs"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_355deb964935efa097c102ab

> [23][24] It operates under a "hub-and-spoke" model with collaboration from academic institutions (e.g., IITs), tech firms, and international organizations like UNESCO.

Exact candidate: "tech firms"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_6ef358f92d8dd24b200c2d61

> [23][24] It operates under a "hub-and-spoke" model with collaboration from academic institutions (e.g., IITs), tech firms, and international organizations like UNESCO.

Exact candidate: "UNESCO"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_c3ea92bae9f320f62b84cca1

> The Digital Trust Centre was initially founded in June 2022.

Exact candidate: "The Digital Trust Centre"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Digital Trust Centre"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_3b87872440edc6e1daacb019

> [28] In May 2024, it was renamed to the Singapore AISI.

Exact candidate: "Singapore AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### development - qfc_0cc17f4b5b5e4afc71924ea5

> [28] Part of Nanyang Technological University, the institute partners with Infocomm Media Development Authority [28] and is supported by an investment of S$10,000,000 per year.

Exact candidate: "Nanyang Technological University"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_daca2571196934dc0d9202c0

> [28] Part of Nanyang Technological University, the institute partners with Infocomm Media Development Authority [28] and is supported by an investment of S$10,000,000 per year.

Exact candidate: "Infocomm Media Development Authority"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_f9203f217ad51a5a348e1e61

> The United Kingdom founded in April 2023 a safety organisation called Frontier AI Taskforce , with an initial budget of £100 million.

Exact candidate: "The United Kingdom"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "United Kingdom"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_52353c12386a2b2c6836fdfd

> The United Kingdom founded in April 2023 a safety organisation called Frontier AI Taskforce , with an initial budget of £100 million.

Exact candidate: "Frontier AI Taskforce"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_43229edf99fc931d0901da21

> [31] In November 2023, it evolved into the AI Safety Institute, and continued to be led by Ian Hogarth.

Exact candidate: "AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_4ae858147eba475140f4143a

> The AISI is part of the United Kingdom's Department for Science, Innovation and Technology.

Exact candidate: "The AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_64132831cf34630fe54c1bda

> The AISI is part of the United Kingdom's Department for Science, Innovation and Technology.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_9f0a5f91b63b93e5ddf3342c

> The AISI is part of the United Kingdom's Department for Science, Innovation and Technology.

Exact candidate: "United Kingdom's Department for Science, Innovation and Technology"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_fd078560e73522acdb4bdd28

> The AISI is part of the United Kingdom's Department for Science, Innovation and Technology.

Exact candidate: "Department for Science, Innovation and Technology"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "United Kingdom's Department for Science, Innovation and Technology"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_df4cb406042c8d65c7ba6f50

> In May 2024, the institute open-sourced an AI safety tool called "Inspect", which evaluates AI model capabilities such as reasoning and their degree of autonomy.

Exact candidate: "institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_cfebc032426451df7e7aec63

> In February 2025, the UK body was renamed the AI Security Institute.

Exact candidate: "AI Security Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_472399f3995f2e07f2467803

> Observers saw the name change as a signal that the institute will not focus on ethical issues such as algorithmic bias or freedom of speech in AI applications.

Exact candidate: "institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### development - qfc_4bb6c8518aad6d637b9ab848

> The US AISI was founded in November 2023 as part of the National Institute of Standards and Technology (NIST).

Exact candidate: "US AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_5d7c0d1dfecb6f5b2f896489

> The US AISI was founded in November 2023 as part of the National Institute of Standards and Technology (NIST).

Exact candidate: "National Institute of Standards and Technology"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "National Institute of Standards and Technology (NIST)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_92a9a05fa2f0f65bdfb3b66b

> The US AISI was founded in November 2023 as part of the National Institute of Standards and Technology (NIST).

Exact candidate: "National Institute of Standards and Technology (NIST)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_1ba493d782cb3e0c20065ad1

> The US AISI was founded in November 2023 as part of the National Institute of Standards and Technology (NIST).

Exact candidate: "NIST"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "National Institute of Standards and Technology (NIST)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_b068af51ac6a18eff5d1091c

> In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.

Exact candidate: "US AI Safety Institute Consortium"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "US AI Safety Institute Consortium (AISIC)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_a36748e4decd8fb6fa6a0e8a

> In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.

Exact candidate: "US AI Safety Institute Consortium (AISIC)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_06398e87e97b8b38dc97042f

> In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.

Exact candidate: "AISIC"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "US AI Safety Institute Consortium (AISIC)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_0c34286d68e154d6ffa5e8be

> In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.

Exact candidate: "Google"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_626ebaab82be92db71b3f703

> In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### development - qfc_466cbeaf441742a0338c5ba5

> In February 2024, the US government created the US AI Safety Institute Consortium (AISIC), regrouping more than 200 organizations such as Google, Anthropic or Microsoft.

Exact candidate: "Microsoft"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_85a912d0882153cbcc189d49

> [40] The US and the UK refused to sign the summit's final communique.

Exact candidate: "US"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_8169db17d17d4d7f616e1ff2

> [40] The US and the UK refused to sign the summit's final communique.

Exact candidate: "UK"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_645735d6dff0ec62760b0793

> The name of the agency was changed in June 2025 to the Center for AI Standards and Innovation (CAISI) and its mission transformed.

Exact candidate: "Center for AI Standards and Innovation"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for AI Standards and Innovation (CAISI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_aa7a22f23fb62dc3508b498d

> The name of the agency was changed in June 2025 to the Center for AI Standards and Innovation (CAISI) and its mission transformed.

Exact candidate: "Center for AI Standards and Innovation (CAISI)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_e2494c5bc06ec020497f6873

> The name of the agency was changed in June 2025 to the Center for AI Standards and Innovation (CAISI) and its mission transformed.

Exact candidate: "CAISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for AI Standards and Innovation (CAISI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### development - qfc_963e9fa1c97b0d7cb0fc8d3e

> [42] According to Secretary of Commerce Howard Lutnick, "For far too long, censorship and regulations have been used under the guise of national security. Innovators will no longer be limited by these standards. CAISI will evaluate and enhance US innovation of these rapidly developing commercial AI systems while ensuring they remain secure to our national security standards." [43][44] The United States Department of Commerce stated that CAISI would represent American interests internationally, guarding against burdensome and unnecessary regulation of US technologies by foreign governments.

Exact candidate: "CAISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_7ec4a32335978df9cf58fa9f

> [42] According to Secretary of Commerce Howard Lutnick, "For far too long, censorship and regulations have been used under the guise of national security. Innovators will no longer be limited by these standards. CAISI will evaluate and enhance US innovation of these rapidly developing commercial AI systems while ensuring they remain secure to our national security standards." [43][44] The United States Department of Commerce stated that CAISI would represent American interests internationally, guarding against burdensome and unnecessary regulation of US technologies by foreign governments.

Exact candidate: "United States Department of Commerce"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_b65343f102afa731a49b5c39

> [42] According to Secretary of Commerce Howard Lutnick, "For far too long, censorship and regulations have been used under the guise of national security. Innovators will no longer be limited by these standards. CAISI will evaluate and enhance US innovation of these rapidly developing commercial AI systems while ensuring they remain secure to our national security standards." [43][44] The United States Department of Commerce stated that CAISI would represent American interests internationally, guarding against burdensome and unnecessary regulation of US technologies by foreign governments.

Exact candidate: "CAISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### development - qfc_ea6256dfb8b8b01adfec05ee

> It collaborates with the NIST Information Technology Laboratory.

Exact candidate: "NIST Information Technology Laboratory"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_d18e20b0ec105f979fbb64c2

> In the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI network"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_70ea2963b86b8792f5d16a53

> In the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_d84157fe1668bc550aba8fbf

> In the months following the AI Seoul Summit, AISI network members must begin to articulate the objectives, deliverables, timelines, and avenues for cooperation that will put the promise of AISI cooperation into action.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_02a8deeca893506c9895e694

> This paper examines next steps for developing the International Network of AI Safety Institutes from the Seoul Statement.

Exact candidate: "International Network of AI Safety Institutes"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_cd6fcc30460b0d3e8fc1d265

> This paper examines next steps for developing the International Network of AI Safety Institutes from the Seoul Statement.

Exact candidate: "Seoul Statement"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_57977bdf8dfa3d0c09806ba6

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "Group of Seven"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Group of Seven (G7)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_843802932a489ad345a65f62

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "Group of Seven (G7)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_1ec14c00c673dffac6a38a64

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "United Nations"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_499f52ee9ee3e2a714607f2c

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "Organisation for Economic Co-operation and Development"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Organisation for Economic Co-operation and Development (OECD)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_3eb1c3021354ffff8b26360c

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "Organisation for Economic Co-operation and Development (OECD)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_d2352fc6d1ecace34d93c15b

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "OECD"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Organisation for Economic Co-operation and Development (OECD)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_d92abf4681af4b99a0697609

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "Global Partnership on AI (GPAI)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_92c4c26e8e3c6d560642ed48

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "International Organization for Standardization"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "International Organization for Standardization (ISO)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_cbd8acd7b121747476ac2ab1

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "International Organization for Standardization (ISO)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_f40a8bf0a1ef7d49aed13b86

> The AI governance landscape is increasingly crowded with international initiatives, including from the Group of Seven (G7), the United Nations , the Organisation for Economic Co-operation and Development (OECD), the Global Partnership on AI (GPAI), the International Organization for Standardization (ISO), and more.

Exact candidate: "ISO"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "International Organization for Standardization (ISO)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_35fbb68722ef4c42963b54b7

> All of these demand time from a small (though growing) community of government staff from member countries who can credibly claim to have some expertise on AI governance and safety issues.

Exact candidate: "government staff"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_4ce6036a2079dc9edcd8e45e

> AISI network members should be able to articulate how their grouping is different from these preexisting initiatives, how it will effectively engage with them (or not), and for what purpose.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI network"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_e5895aff65db3798459c99a7

> This paper begins with background on the AISI network and explains its importance.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_e8c3680c5f1908218acc7105

> It concludes with recommendations regarding nine further questions for developing the goals, collaboration mechanisms, and international strategy of the network.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_b92943bda6e5ebb09ec2bb6c

> As defined by the Bletchley Declaration, issued by attendees of the UK AI Safety Summit in November 2023, AI safety is a scientific field of research focused on evaluating, preventing, and mitigating risks from advanced AI systems.

Exact candidate: "UK AI Safety Summit"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_8ecbc6dd5336ee0c3d8e8a99

> This paper's use of the term 'AI safety' follows the U.S. AI Safety Institute's example of focusing exclusively on safety issues related to advanced AI systems.

Exact candidate: "U.S. AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_581a59ac57b3b43cbcc45101

> Meanwhile, process-based safety is concerned with the policies, practices, and procedures that surround AI.

Exact candidate: "process-based safety"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_0bf1c26d753db9be77f43d0b

> As Elizabeth Kelly, director of the U.S. AI Safety Institute, said in a CSIS interview , 'safety promotes trust, which promotes adoption, which drives innovation.'

Exact candidate: "U.S. AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_c18f08dde77f5748b93a6d8d

> As Elizabeth Kelly, director of the U.S. AI Safety Institute, said in a CSIS interview , 'safety promotes trust, which promotes adoption, which drives innovation.'

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_4101d6a4bb73f44e57d99ed0

> Source: 'The U.S. Vision for AI Safety: A Conversation with Elizabeth Kelly, Director of the U.S. AI Safety Institute,' CSIS, July 31, 2024, https://www.csis.org/analysis/us-vision-ai-safety-conversation-elizabeth-kelly-director-us-ai-safety-institute; and 'The United States Artificial Intelligence Safety Institute: Vision, Mission, and Strategic Goals,' U.S. Artificial Intelligence Safety Institute, May 21, 2024, https://www.nist.gov/system/files/ documents/2024/05/21/AISI-vision-21May2024.pdf.

Exact candidate: "U.S. AI Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_7fa06260d8154054d567c841

> Source: 'The U.S. Vision for AI Safety: A Conversation with Elizabeth Kelly, Director of the U.S. AI Safety Institute,' CSIS, July 31, 2024, https://www.csis.org/analysis/us-vision-ai-safety-conversation-elizabeth-kelly-director-us-ai-safety-institute; and 'The United States Artificial Intelligence Safety Institute: Vision, Mission, and Strategic Goals,' U.S. Artificial Intelligence Safety Institute, May 21, 2024, https://www.nist.gov/system/files/ documents/2024/05/21/AISI-vision-21May2024.pdf.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_8cbaf6556d1588bfb970f974

> Source: 'The U.S. Vision for AI Safety: A Conversation with Elizabeth Kelly, Director of the U.S. AI Safety Institute,' CSIS, July 31, 2024, https://www.csis.org/analysis/us-vision-ai-safety-conversation-elizabeth-kelly-director-us-ai-safety-institute; and 'The United States Artificial Intelligence Safety Institute: Vision, Mission, and Strategic Goals,' U.S. Artificial Intelligence Safety Institute, May 21, 2024, https://www.nist.gov/system/files/ documents/2024/05/21/AISI-vision-21May2024.pdf.

Exact candidate: "U.S. Artificial Intelligence Safety Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_bec1c8cb8b3077a2f13e5266

> To keep pace with the cutting edge of AI safety research, AISIs have prioritized the hiring of technical staff and opened offices in cities with deep pools of AI talent like San Francisco.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_ba2f7ad4215ae8f487b87ba4

> In addition to developing expertise internally, AISIs aim to cultivate a robust ecosystem of AI safety researchers in labs, industry, and academia through their guidance on best-in-class evaluation methods.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_e9a16e8bf5a38a7b9d7431ea

> Note that while these nine areas of guidance overlap with the nine core functions of an AI safety institute identified in Section 4 of this paper, they do not cover the full breadth of AISIs' operations.

Exact candidate: "AI safety institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_9a2ecb34dfd8529a18403a78

> Note that while these nine areas of guidance overlap with the nine core functions of an AI safety institute identified in Section 4 of this paper, they do not cover the full breadth of AISIs' operations.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_afe4b1cdbce012a99d11f6e7

> As Section 4 will discuss, AISIs perform functions such as forming consortia of AI researchers, stakeholders, and experts and promoting the international adoption of AI safety guidelines that are outside the scope of the AISIC.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_13ac9892bb114bef17ae3660

> As Section 4 will discuss, AISIs perform functions such as forming consortia of AI researchers, stakeholders, and experts and promoting the international adoption of AI safety guidelines that are outside the scope of the AISIC.

Exact candidate: "AISIC"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_470a8d36c4df6d3208c96d0e

> The letter echoes similar calls for Congress to authorize the AISI by Scale AI Founder and CEO Alexandr Wang earlier in October, as well as a letter from top AI companies to establish the AISI on a statutory basis in July.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_598763b00bdeef443ebbadcc

> The letter echoes similar calls for Congress to authorize the AISI by Scale AI Founder and CEO Alexandr Wang earlier in October, as well as a letter from top AI companies to establish the AISI on a statutory basis in July.

Exact candidate: "Scale AI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_d05bfc5de865c3943f69ff20

> The letter echoes similar calls for Congress to authorize the AISI by Scale AI Founder and CEO Alexandr Wang earlier in October, as well as a letter from top AI companies to establish the AISI on a statutory basis in July.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_f5be02b3ad90ef9b549b3aa1

> The July letter, also published by Americans for Responsible Innovation and ITI, argues that authorizing the AISI "provides a venue to convene the leading experts across industry and government to contribute to the development of voluntary standards that ultimately assist in de-risking adoption of AI technologies.

Exact candidate: "Americans for Responsible Innovation"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Americans for Responsible Innovation and ITI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_418c281cb3da8d8771c258fe

> The July letter, also published by Americans for Responsible Innovation and ITI, argues that authorizing the AISI "provides a venue to convene the leading experts across industry and government to contribute to the development of voluntary standards that ultimately assist in de-risking adoption of AI technologies.

Exact candidate: "ITI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Americans for Responsible Innovation and ITI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_3335849cb8142bf0821d146a

> The July letter, also published by Americans for Responsible Innovation and ITI, argues that authorizing the AISI "provides a venue to convene the leading experts across industry and government to contribute to the development of voluntary standards that ultimately assist in de-risking adoption of AI technologies.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_4e336c6b02c5c11f9946a3b8

> ' It's not just the biggest companies that stand to benefit from the U.S. AISI-crucially, the letter argued that the institute may level the playing field for enterprises that use or develop AI but are unable to perform robust testing and evaluation in-house due to their size or the technical ability of their staff.

Exact candidate: "U.S. AI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_8d322c8365455bc57302c795

> ' It's not just the biggest companies that stand to benefit from the U.S. AISI-crucially, the letter argued that the institute may level the playing field for enterprises that use or develop AI but are unable to perform robust testing and evaluation in-house due to their size or the technical ability of their staff.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_bcadcdb41b20c00e161d4983

> ' It's not just the biggest companies that stand to benefit from the U.S. AISI-crucially, the letter argued that the institute may level the playing field for enterprises that use or develop AI but are unable to perform robust testing and evaluation in-house due to their size or the technical ability of their staff.

Exact candidate: "AISI-crucially"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "not_organization" → `not_organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "not_organization" → `not_organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "not_organization" → `not_organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_9a8e08c1fcc215f2318804f1

> While the concept of a government organization that works closely with AI companies on safety is still new, history shows that this kind of arrangement between government and industry can be highly successful.

Exact candidate: "AI companies"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_0278bdddb0531969f964a362

> One good example is the National Highway Traffic Safety Administration (NHTSA), a U.S. federal agency that performs safety tests of new motor vehicle models for manufacturers.

Exact candidate: "National Highway Traffic Safety Administration"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "National Highway Traffic Safety Administration (NHTSA)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_98287dc0c56aace7ea0e57c3

> One good example is the National Highway Traffic Safety Administration (NHTSA), a U.S. federal agency that performs safety tests of new motor vehicle models for manufacturers.

Exact candidate: "National Highway Traffic Safety Administration (NHTSA)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_9395a0b6f805fa3c4118a5fe

> One good example is the National Highway Traffic Safety Administration (NHTSA), a U.S. federal agency that performs safety tests of new motor vehicle models for manufacturers.

Exact candidate: "NHTSA"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "National Highway Traffic Safety Administration (NHTSA)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_220f0ed9610f16b307a11b83

> Established in the 1970s to reduce accidents and deaths by encouraging manufacturers to produce safer vehicles, NHTSA led what has become today an industry standard of crash testing and rating vehicles out of five stars according to their safety.

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_c651879ef2f1b070668dc3b3

> Some 50 years since its launch, NHTSA continues to perform crash tests and produce star ratings, as well as issue government safety ratings, safety information, and best practices.

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_e23865db64a47368ad0173c7

> NHTSA is a useful model of a third-party government arbiter that has produced substantial win-win results for the public and for companies.

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_8c0af21d800cad709f29228e

> The administration's rating system lowers costs to consumers by supplying accurate, reliable, and simple safety information for free.

Exact candidate: "The administration"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_d41fc92ba4a5a6ec9b63ab66

> Meanwhile, companies are incentivized to adopt new and better safety measures into their vehicles.

Exact candidate: "companies"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_403e49aeaaff1a0da83a2e8e

> As NHTSA's acting administrator has stated , '[o]ur 5-Star Safety Ratings system continues to give Americans the information they need to choose the vehicle that's right for them. The program also encourages vehicle manufacturers to incorporate advanced vehicle safety technologies into more makes and models, ultimately reducing injuries and deaths on America's roads.'

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_9ae525af033a47060048c904

> Because safety is a selling point for customers , most of the United States' manufacturers willingly sign up for the NHTSA's 5-star system and use the results in advertising new vehicle models.

Exact candidate: "United States' manufacturers"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_5ef55a681a63b898f48948aa

> Because safety is a selling point for customers , most of the United States' manufacturers willingly sign up for the NHTSA's 5-star system and use the results in advertising new vehicle models.

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_fe3143801a0028c3c085a41c

> Because safety is a selling point for customers , most of the United States' manufacturers willingly sign up for the NHTSA's 5-star system and use the results in advertising new vehicle models.

Exact candidate: "NHTSA's"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "NHTSA"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_ac6328f0c91f2c1b7bbd015d

> As AISIs mature organizationally, they could fulfill a similar arbiter role for AI models as the NHTSA has for motor vehicles.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_30ab6a9bd51e2807ef106fff

> As AISIs mature organizationally, they could fulfill a similar arbiter role for AI models as the NHTSA has for motor vehicles.

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_0c8e57f039e28d1d4cfcddba

> AI companies could communicate to customers that their model has passed AISI testing and evaluations, which could in turn help to build public trust and make AI models with higher safety standards more commercially competitive among consumers.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_4d79078ee931b71703b229df

> Top frontier AI developers' willingness to work with the U.S. AISI on testing their models before deployment is a good first step to making safety a key feature of AI industry standards, as the NHTSA has done with the U.S. motor vehicle industry over the last 50 years.

Exact candidate: "U.S. AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_93f1454d2275651103a5e2e4

> Top frontier AI developers' willingness to work with the U.S. AISI on testing their models before deployment is a good first step to making safety a key feature of AI industry standards, as the NHTSA has done with the U.S. motor vehicle industry over the last 50 years.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_eac772731df9b01b0870cd49

> Top frontier AI developers' willingness to work with the U.S. AISI on testing their models before deployment is a good first step to making safety a key feature of AI industry standards, as the NHTSA has done with the U.S. motor vehicle industry over the last 50 years.

Exact candidate: "NHTSA"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_e782ae635b033a0a4cffc43f

> The AISI International Network marks a logical next step in a series of recent bilateral agreements between institutes.

Exact candidate: "AISI International Network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_c523963b6b68de6ed1dfe519

> In April 2024, the United States signed a memorandum of understanding with the United Kingdom for close collaboration between institutes and established a dialogue with the EU AI Office to jointly develop evaluation tools for AI models.

Exact candidate: "United States"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_06bc08fb90ad8be922cd59a9

> In April 2024, the United States signed a memorandum of understanding with the United Kingdom for close collaboration between institutes and established a dialogue with the EU AI Office to jointly develop evaluation tools for AI models.

Exact candidate: "United Kingdom"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_a1cf80ddbceee5695d1199c2

> In April 2024, the United States signed a memorandum of understanding with the United Kingdom for close collaboration between institutes and established a dialogue with the EU AI Office to jointly develop evaluation tools for AI models.

Exact candidate: "EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_b5aa30b2c436f7d52d095327

> Meanwhile, the United Kingdom, for its part, has established additional partnerships with Canada and France on AI safety, and the European Union and Japan have indicated future cooperation between safety institutes in the coming months.

Exact candidate: "United Kingdom"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_221034e7de13046d244d3e23

> Meanwhile, the United Kingdom, for its part, has established additional partnerships with Canada and France on AI safety, and the European Union and Japan have indicated future cooperation between safety institutes in the coming months.

Exact candidate: "Canada"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Canada\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Canada\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nIn the given context, \"Canada\" is mentioned" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_c9038b779cdfcef3076bc27d

> Meanwhile, the United Kingdom, for its part, has established additional partnerships with Canada and France on AI safety, and the European Union and Japan have indicated future cooperation between safety institutes in the coming months.

Exact candidate: "France"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_365a38c06b1c18742fd2844d

> Meanwhile, the United Kingdom, for its part, has established additional partnerships with Canada and France on AI safety, and the European Union and Japan have indicated future cooperation between safety institutes in the coming months.

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_20c0ff94b964ac40a701dd56

> Meanwhile, the United Kingdom, for its part, has established additional partnerships with Canada and France on AI safety, and the European Union and Japan have indicated future cooperation between safety institutes in the coming months.

Exact candidate: "Japan"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_997c3a33f7db7b932f798a4f

> One such effort is the G7 Hiroshima AI Process Code of Conduct, which calls for 'robust' and 'trustworthy' AI systems but lacks technical definitions of the terms.

Exact candidate: "G7"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_cd854209289f1c0441def383

> One such effort is the G7 Hiroshima AI Process Code of Conduct, which calls for 'robust' and 'trustworthy' AI systems but lacks technical definitions of the terms.

Exact candidate: "G7 Hiroshima AI Process Code of Conduct"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_70daa786a891bf2f28848f8b

> Shared definitions would help create a common measuring stick by which regulators gauge these characteristics.

Exact candidate: "regulators"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_388b283649aeb114fc5b8e09

> In this example, governments would require different levels of robustness and trustworthiness along the same underlying scale, as is the case for safety in the automobile and aviation industries.

Exact candidate: "governments"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_50886708b3317a590fcaf96f

> A common understanding of AI safety concepts would help clarify the steps countries must take to honor the G7 code of conduct and other international commitments.

Exact candidate: "G7"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_e2cd4bab4e64f71707a36482

> As a previous CSIS paper argued, fragmented legal frameworks that require company compliance with many different obligations can create technical barriers to the free flow of goods and services.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\nambiguous" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_3f3320872a33b41d1f9ee612

> Instead, the AISI International Network could serve as one venue in which to develop a coherent language around AI safety, helping to lower future potential barriers to trade.

Exact candidate: "AISI International Network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_069a10728eac68f1bf1d93ea

> Rather, the EU AI Office-the European Union's representation to the AISI International Network-is tasked with developing codes of practice for the developers of these models, almost all of which are U.S. companies .

Exact candidate: "EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_581bd080eed3f38331d56704

> Rather, the EU AI Office-the European Union's representation to the AISI International Network-is tasked with developing codes of practice for the developers of these models, almost all of which are U.S. companies .

Exact candidate: "EU AI Office-the"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "EU AI Office"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_30fa9d823535a78bcd9d344b

> Rather, the EU AI Office-the European Union's representation to the AISI International Network-is tasked with developing codes of practice for the developers of these models, almost all of which are U.S. companies .

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_ef7fe187320677cbeeafbdab

> Rather, the EU AI Office-the European Union's representation to the AISI International Network-is tasked with developing codes of practice for the developers of these models, almost all of which are U.S. companies .

Exact candidate: "AISI International Network-is"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "AISI International Network"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_0d97ad4e1c163cf2cd8fd63f

> According to Article 56 of the AI Act, the EU AI Office must develop codes of practice for frontier AI companies to identify, assess, manage, and report 'systemic' risks by May 2, 2025.

Exact candidate: "EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_658656d3a530a73e818423fd

> According to Article 56 of the AI Act, the EU AI Office must develop codes of practice for frontier AI companies to identify, assess, manage, and report 'systemic' risks by May 2, 2025.

Exact candidate: "frontier AI companies"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_4a13c99522b54bc057a7da4d

> To meet this tight deadline, it may look to the work of the AISI International Network if it deems it sufficiently mature to draw upon.

Exact candidate: "AISI International Network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_a8e4d364193696bfb454e07a

> Having a seat at the same table as the EU AI Office is therefore a valuable opportunity to help develop safety norms that the European Union may apply to U.S. companies.

Exact candidate: "EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_1b8bb8e532572b6172bd601a

> Having a seat at the same table as the EU AI Office is therefore a valuable opportunity to help develop safety norms that the European Union may apply to U.S. companies.

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_944c95dacc5e81d797c3d66a

> Even if the European Union ultimately decides to develop its codes of practice alone, the network will still provide the United States with a direct line of communication to the EU AI Office for articulating AI safety best practices in the future.

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_2bd3650a7e679001775a08e8

> Even if the European Union ultimately decides to develop its codes of practice alone, the network will still provide the United States with a direct line of communication to the EU AI Office for articulating AI safety best practices in the future.

Exact candidate: "EU AI Office"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_a459230a4aee0d79c2b95195

> It is still early days for AI safety institutes, both as organizations and as concepts.

Exact candidate: "AI safety institutes"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_d1d17daf08a33e5e1aecda6d

> Members of the AISI International Network are highly varied in their organizational maturity, which can be expected given that most are only months old.

Exact candidate: "AISI International Network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_f2d4d317921353d39cab2033

> Even the U.S. AISI, one of the most established institutes, was announced only in November 2023 and became operational in early 2024.

Exact candidate: "U.S. AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_29ab0016b77e05e85e91b835

> Other AISIs, such as those of Japan, Singapore, South Korea, and the European Union, are still in the process of hiring and setting out the priorities of their institutes, according to public documents and conversations by CSIS with officials.

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_6ed8fa651179dc2449af3709

> Other AISIs, such as those of Japan, Singapore, South Korea, and the European Union, are still in the process of hiring and setting out the priorities of their institutes, according to public documents and conversations by CSIS with officials.

Exact candidate: "CSIS"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe mention \"CSIS\" could refer to the" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe mention \"CSIS\" could refer to the" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe mention \"CSIS\" could refer to the" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_46c67e7e788ab24e68bf430a

> Still other network members, like Kenya and Australia, have yet to clearly state whether their governments will even establish an AISI.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_79c5e1ad10fa01e5eaeba01c

> Nevertheless, established AISIs report strong similarities in funding and staff size thus far.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_8d36fbd64d7a3dd86a29e10f

> As Table 1 illustrates, the annual budgets of network members currently hover around $10 million, with some notable exceptions.

Exact candidate: "network members"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_d7d99c4b316747f512efe409

> First, the UK AISI is already an outlier with a budget of approximately £50 million ($65 million) per year, according to CSIS sources.

Exact candidate: "UK AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_f43457622a1e6f3c9c90d489

> First, the UK AISI is already an outlier with a budget of approximately £50 million ($65 million) per year, according to CSIS sources.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nCSIS could refer to the Center for Strategic and" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nCSIS could refer to the Center for Strategic and" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nCSIS could refer to the Center for Strategic and" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_e0053c16718a1adebebe5e4c

> Second, the United States' fiscal year 2025 budget requests an increase of $47.7 million for investment into the U.S. AISI and the advancement of AI research, standards, and testing in line with President Biden's October 2023 AI executive order , which, if approved, would greatly boost the average network budget.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "U.S. AISI"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_7e5479775196ad252acdfe2c

> Finally, an announcement by the Canadian government in April pledges C$50 million (approximately US$36 million) for a Canadian AISI, though the funding period is unspecified.

Exact candidate: "Canadian government"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_93b24f4799b0255086fa17ee

> Finally, an announcement by the Canadian government in April pledges C$50 million (approximately US$36 million) for a Canadian AISI, though the funding period is unspecified.

Exact candidate: "AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Canadian AISI"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_ae59f68a22c641fc32fa2038

> Public statements and private conversations between CSIS and government officials reveal that staff sizes will also be comparable between institutes.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_b6c45b4afdbc30e09af8698a

> More established AISIs currently employ approximately 20 to 30 staff, most of whom are technical experts.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_c63d36c288fe11830a6b5301

> Private conversations with CSIS indicate that the EU AI Office's AI safety unit , which will fulfill most of the same functions as an AISI (Table 2), will likely hold approximately 50 staff members.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_5aaf51f7171124af3d5cd7ee

> Private conversations with CSIS indicate that the EU AI Office's AI safety unit , which will fulfill most of the same functions as an AISI (Table 2), will likely hold approximately 50 staff members.

Exact candidate: "EU AI Office"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "EU AI Office's AI safety unit"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_95fe2b78929adab5801b9794

> Private conversations with CSIS indicate that the EU AI Office's AI safety unit , which will fulfill most of the same functions as an AISI (Table 2), will likely hold approximately 50 staff members.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_35c673bf1714b150c387234d

> Some deliverables predate the AISI, such as the Japanese Ministry of Economy, Trade and Industry's AI Business Guidelines, but have been incorporated and built upon by current AISI efforts.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_b865470d25be4c50d115e9f6

> Some deliverables predate the AISI, such as the Japanese Ministry of Economy, Trade and Industry's AI Business Guidelines, but have been incorporated and built upon by current AISI efforts.

Exact candidate: "Japanese Ministry of Economy, Trade and Industry"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_4b85bb3fcbe39601a83a2a2b

> Some deliverables predate the AISI, such as the Japanese Ministry of Economy, Trade and Industry's AI Business Guidelines, but have been incorporated and built upon by current AISI efforts.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_33a5f3ab7f3c9c9af1698e26

> Others are novel efforts by institutes since their launch, such as the U.S. AISI's guidance for Managing Misuse Risk for Dual-Use Foundation Models , and the UK AISI's Inspect and Singapore's Project Moonshot , two testing and evaluation toolkits for large language models (LLMs).

Exact candidate: "U.S. AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_887a2c1b52d431f2f2177f4e

> Others are novel efforts by institutes since their launch, such as the U.S. AISI's guidance for Managing Misuse Risk for Dual-Use Foundation Models , and the UK AISI's Inspect and Singapore's Project Moonshot , two testing and evaluation toolkits for large language models (LLMs).

Exact candidate: "UK AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_84b8f24d8f2013e7cc44c62d

> Others are novel efforts by institutes since their launch, such as the U.S. AISI's guidance for Managing Misuse Risk for Dual-Use Foundation Models , and the UK AISI's Inspect and Singapore's Project Moonshot , two testing and evaluation toolkits for large language models (LLMs).

Exact candidate: "Singapore's Project Moonshot"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_3fbc71e520d975e99ea21f3d

> Recommendation: The AISI International Network does not have the capacity or resources to effectively collaborate on every domain of AI safety.

Exact candidate: "AISI International Network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_4b1183d2d6be5eae1866277f

> For some domains, such as sharing sensitive information about models, AISIs may even face legal limitations to collaboration.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_1a272b3b6f8835f91d2c8f35

> Rather than spreading finite resources thinly in an effort to achieve everything all at once, network members should first focus on executing a few specific projects well.

Exact candidate: "network members"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_049fabafdc7860338e206a32

> When selecting priority areas, members should consider areas with the greatest overlap in AISI's functions, capacity, and expertise, and deliverables that are both impactful and realistic.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_fe9402e32d5591881e8919ea

> To start, they should establish a research agenda for the network's technical and guidance safety work going forward.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_0261c582f7ec6c54741353ac

> This will help to set the scope of the network's efforts and to keep members on track as they and the network mature.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_2daf620c0e52dafb4ae8f2b5

> This will help to set the scope of the network's efforts and to keep members on track as they and the network mature.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_abd0392555171695449f405e

> As discussed in this paper's recommendation to Question 3, the AISI network conference in November may be a good place to set and present this agenda to the public.

Exact candidate: "AISI network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_650efe95b83705a0b663256c

> Recommendation: It would be premature to assign specific responsibilities to AISI network members today given that most are only months old, if established at all.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_d372a338b9b7c63b128f21d9

> Currently, AISI network members share equal responsibilities by default.

Exact candidate: "AISI"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_ca7e1df9d69deece973af533

> If each member were to take charge on a different project, for instance, the network could risk losing time, capacity, and focus.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_56c82feb1b34b4befae60304

> This kind of structure could also place undue pressure on the capacity and expertise of each of the AISIs to contribute before they are ready.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_3db092d9f54efe7961220ca6

> Instead, the AISI network may consider leveraging each member's comparative advantages in expertise, capacity, and funding.

Exact candidate: "AISI network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_facd0d9d04ade73a32fb29de

> For now, more mature AISIs like those of the United States, the United Kingdom, and Singapore could have greater responsibilities within the network while other members, such as Kenya or Australia, contribute through more specialized ways.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_3b8d06f1743dfb1809e67c81

> These roles could shift over time as AISIs mature, however.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_fc2b0ba4a198d9d89ab09773

> Recommendation: Currently, the AISI network has a horizontal leadership and consensus or opt-in only voting structure by default.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_7f09dfcf70f84eca83d37bde

> Given that the Seoul Statement makes no indication of leadership and voting structure, however, network members are open to consider different possibilities and their trade-offs.

Exact candidate: "network members"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_335ee7b3d642dc5bc19a2eeb

> The network's leadership and voting structures need not be zero sum, however.

Exact candidate: "The network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_2ba87652785505d5d3c38439

> In the long run, members' representation within the network should be proportionate to their contributions; those that invest more time, money, expertise, and resources should be rewarded with a greater say in its direction.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_437d97614000a6b642fb58ab

> This means that the U.S. and UK AISIs would likely be rewarded with leadership of the network due to their organizational capacity.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_3ba41f85723595aaa97514d6

> The United States, for its part, should aspire to lead the AISI network, as discussed in the third section of this paper.

Exact candidate: "The United States"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "United States"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_7914663aa69cfb583e3b1446

> The United States, for its part, should aspire to lead the AISI network, as discussed in the third section of this paper.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_896f1e234f1b024346e0e934

> Leadership should be earned based on the scale of meaningful contributions to the field of AI safety science, a structure that also incentivizes on other network members to participate and invest more into AI safety and the AISI network as well.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_326cf0d417ad0e07449451df

> To do this, the AISI network should emphasize its unique position to provide technical expertise and capacity to governments working on wider AI governance efforts.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_06c9eb48d190658a5425086f

> In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI .

Exact candidate: "Biden administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_1a5547c49d5eae49144513b5

> In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI .

Exact candidate: "EU"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_ce7900007602169999bab501

> In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI .

Exact candidate: "EU AI Act"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_2bd5f5006f3eea54224b3563

> In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI .

Exact candidate: "G7"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_38de18d73712dd22521b7032

> In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI .

Exact candidate: "G7 Hiroshima AI Process Code of Conduct"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_23caf811a3c78dca5b698b7e

> In the past year alone, numerous government initiatives have been launched to ensure responsible frontier AI development, including the Biden administration's AI executive order , the EU AI Act , the G7 Hiroshima AI Process Code of Conduct , and the March 2024 UN resolution on AI .

Exact candidate: "UN"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (incorrect; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_24df1ff68dbf488bcde88cd1

> These initiatives, though commendable, are often staffed by diplomats who lack the depth of in-house technical expertise that the AISI network has demonstrated an ability to amass.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_090831a1245d1cfd3221f56c

> The purpose here is not to make the AISI network into an elite club, but to recognize that the network's goal of accelerating AI safety science cannot be realistically achieved by expanding membership to everyone who wants it.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_99b7a77ee252d04660959e9d

> The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_b8f2037bb4388ee744b3e394

> The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network.

Exact candidate: "GPAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_7ec96c1ecbd80459487b349b

> The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network.

Exact candidate: "OECD"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_22c95b654f56171baa44e3b3

> The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network.

Exact candidate: "Group of 20"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Group of 20 (G20)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_ac7f57125655bef2a30bbbf3

> The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network.

Exact candidate: "Group of 20 (G20)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_0591e62072a7b3bcb0b4dd77

> The AISI network could consider partnership programs with other international organizations like GPAI, the OECD, or the Group of 20 (G20) in order to collaborate with interested countries that do not necessarily have the depth of AI safety expertise to join the network.

Exact candidate: "G20"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Group of 20 (G20)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_d2893b618a57c92f7d5e0269

> Such partnerships could help to foster wider international cooperation on AI safety and engage more developing countries on the AISI network's efforts in particular.

Exact candidate: "AISI network"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_c496fa8fceb420b634dc4914

> While the Seoul Statement is a good start for multilateralizing cooperation between AISIs, network members must now decide how to turn intent into action.

Exact candidate: "AISIs"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_3fe956b29a91c700fd652be4

> At the November convening in San Francisco, they should strive to set the network's goals, mechanisms, and international strategy in preparation for the AI Action Summit in February 2025.

Exact candidate: "network"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_71c7a0ddeec30859a3fcfd6b

> Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.

Exact candidate: "Wadhwani AI Center"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe Wadhwani AI Center is described as" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe Wadhwani AI Center is described as" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe Wadhwani AI Center is described as" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_b71e9e594ce380d6e1bba0bb

> Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.

Exact candidate: "Center for Strategic and International Studies"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for Strategic and International Studies (CSIS)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_362f5ee09f815049938e3f55

> Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.

Exact candidate: "Center for Strategic and International Studies (CSIS)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_0aca211dd8a3e17c2991d4d3

> Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.

Exact candidate: "CSIS"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for Strategic and International Studies (CSIS)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_358beb76e7959a9e917a9819

> Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.

Exact candidate: "Wadhwani AI Center"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe Wadhwani AI Center is described as" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe Wadhwani AI Center is described as" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe Wadhwani AI Center is described as" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_753ebcb0282158ee065f89c9

> Gregory C. Allen is the director of the Wadhwani AI Center at the Center for Strategic and International Studies (CSIS) in Washington, D.C. Georgia Adamson is a research associate with the Wadhwani AI Center at CSIS.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_693d01d00c7cbf4af9e0075f

> This report is produced by the Center for Strategic and International Studies (CSIS), a private, tax-exempt institution focusing on international public policy issues.

Exact candidate: "Center for Strategic and International Studies"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for Strategic and International Studies (CSIS)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_95250bae8bc0be053c7407d2

> This report is produced by the Center for Strategic and International Studies (CSIS), a private, tax-exempt institution focusing on international public policy issues.

Exact candidate: "Center for Strategic and International Studies (CSIS)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_59d78fd29e36dbad5ff02cdc

> This report is produced by the Center for Strategic and International Studies (CSIS), a private, tax-exempt institution focusing on international public policy issues.

Exact candidate: "CSIS"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Center for Strategic and International Studies (CSIS)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_1bbe3a04daf55de8317ab603

> CSIS does not take specific policy positions.

Exact candidate: "CSIS"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_14393cfca3c9deebeb29674e

> © 2024 by the Center for Strategic and International Studies.

Exact candidate: "Center for Strategic and International Studies"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_e2719128c0a11f24c82c7f69

> Hegseth, the United States secretary of defense, has publicly rebuked Anthropic chief executive Dario Amodei's approach to artificial intelligence.

Exact candidate: "United States"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": false} → `not_organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": false} → `not_organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "GPE", "failed_class_check": false} → `not_organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_8367061bc90d935430ed0f34

> Hegseth, the United States secretary of defense, has publicly rebuked Anthropic chief executive Dario Amodei's approach to artificial intelligence.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_b0ed69748ffd47e64df9d46e

> Since January 2026, the United States Department of Defense has conflicted with the artificial intelligence company Anthropic over the use of its products for military purposes and mass domestic surveillance.

Exact candidate: "United States Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_d31cb2f7840b7fa14b46a6f4

> Since January 2026, the United States Department of Defense has conflicted with the artificial intelligence company Anthropic over the use of its products for military purposes and mass domestic surveillance.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is described as an artificial intelligence company," → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is described as an artificial intelligence company," → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is described as an artificial intelligence company," → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_8bbcdc5ece67efaf2e3644ba

> Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord".

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_bcb5cd25dc32f701fd744c95

> Anthropic's strategy has mirrored Amodei's views toward Trump; in a Facebook post ahead of the 2024 presidential election, Amodei urged his associates to vote for vice president Kamala Harris over Trump, describing him as a "feudal warlord".

Exact candidate: "Facebook"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (incorrect; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_73123837eba76ed564b4ba98

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment.

Exact candidate: "Trump administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_de750ba8afcbcb476ddbc787

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment.

Exact candidate: "Skadden, Arps, Slate, Meagher & Flom"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Skadden", "Arps", "Slate", "Meagher & Flom"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_de34c723db67f0ee4b9318dc

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment.

Exact candidate: "Latham & Watkins"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_9e7d4d365f6a35bafd0d3308

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment.

Exact candidate: "Trump administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_45d78e15212577d0922c3a41

> David Sacks, Trump's advisor for artificial intelligence and cryptocurrency, said on All-In (2020-present) that Anthropic was among several "AI doomers" that support regulation he saw as overly restrictive.

Exact candidate: "All-In"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "WORK_OF_ART", "failed_class_check": false} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "WORK_OF_ART", "failed_class_check": false} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "WORK_OF_ART", "failed_class_check": false} → `not_organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_6570b4cd809e31691aec0acd

> David Sacks, Trump's advisor for artificial intelligence and cryptocurrency, said on All-In (2020-present) that Anthropic was among several "AI doomers" that support regulation he saw as overly restrictive.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_38bb900de76ba043ca36fd98

> According to The Wall Street Journal , officials close to Sacks examined whether Anthropic's Claude was a "woke AI"; in July, Trump signed an executive order "Preventing Woke AI in the Federal Government ".

Exact candidate: "Anthropic"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_82bc7b293a7b953208084624

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.

Exact candidate: "World Economic Forum"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_aecd654923061cd95814184d

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_36ead00dd452d34ee275945f

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.

Exact candidate: "Open Philanthropy"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_f6627ae057072f88221f79eb

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_a0fcb2f69c39d0721decd573

> [15] In October 2025, Sacks stated that Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration on Anthropic's policies, intensifying the dispute.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_ad753cd85df0e937336fa964

> [15] In October 2025, Sacks stated that Anthropic was "running a sophisticated regulatory capture strategy based on fearmongering." [16] That month, Amodei published a blog post rebuffing "inaccurate claims" from the Trump administration on Anthropic's policies, intensifying the dispute.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization\nnot_organization\nambiguous\n\n[direct_prose]\n[paragraph]\n" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_8d8d3441866db19e6a6ac1e3

> [17] In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_334eaa724a84ea6a46420644

> [17] In December, Amodei met with Trump officials and several senators in an effort to improve Anthropic's relationship with the Trump administration.

Exact candidate: "Trump administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_fd8ce71dc4b9126a6e625a90

> Michael told reporters that Anthropic should "cross the Rubicon" and allow the Department of Defense to dictate the terms of how its technology is used.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_2257a551ba2616515eb20ddd

> Michael told reporters that Anthropic should "cross the Rubicon" and allow the Department of Defense to dictate the terms of how its technology is used.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_05b0f4c6065a5312c1bc0d37

> [32] The position of the Department of Defense, and its tactics during the dispute, were widely criticized on grounds including violating the principles of rule-oflaw, market independence and national security.

Exact candidate: "Department of Defense"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_e71fbdd7b911265b34d62817

> The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars.

Exact candidate: "1789 Capital"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_e3f0133d8382fe3f771f7fa2

> The dispute caused 1789 Capital, a venture capital firm associated with Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of millions of dollars.

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of receiving investment" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of receiving investment" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nAnthropic is mentioned in the context of receiving investment" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_06c2d1ccc1af3e7da16a4e73

> Following the government's actions against Anthropic, OpenAI "rushed", [40] hours before the US started the 2026 Iran war, [41] to get a deal without the constraints that Anthropic had sought.

Exact candidate: "OpenAI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_56d1d2483193c6c2c0d578cf

> Following the government's actions against Anthropic, OpenAI "rushed", [40] hours before the US started the 2026 Iran war, [41] to get a deal without the constraints that Anthropic had sought.

Exact candidate: "US"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_6ba06749cc0c1226bfdc56c0

> As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems." [31]

Exact candidate: "DoW"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_d256046675abfc904f8fc464

> As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems." [31]

Exact candidate: "DoW"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_c65ba04771d637629dffb12b

> As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems." [31]

Exact candidate: "Anthropic"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_86faca36a50b450bd8ba2cc8

> As of late April, notwithstanding the ND Cal. injunction, "DoW contract cancellations proceed, removal of Claude from DoW systems continues on a 180-day timeline, and Anthropic cannot be used as a prime contractor or subcontractor on DoW covered systems." [31]

Exact candidate: "DoW"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_4575c9ad18a6e0693908bd8a

> An artificial intelligence safety institute [1] is a type of state-backed organization aiming to evaluate and ensure the safety of advanced artificial intelligence (AI) models, also called frontier AI models.

Exact candidate: "An artificial intelligence safety institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_fe7e533c01c9cb647ca2af3c

> At the AI Seoul Summit in May 2024, the European Union and other countries agreed to create their own AI safety institutes, forming an international network.

Exact candidate: "European Union"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_483d7517aa0b23211e57766b

> On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security.

Exact candidate: "government of France"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_e1fff98ed4782e4c9b79b21c

> On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security.

Exact candidate: "Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA)"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_9cf6d5bd0ce799392e7a4d6c

> On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security.

Exact candidate: "INESIA"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_747368ed53f71c86d610c400

> On 31 January 2025, the government of France created the Institut national pour l'évaluation et la sécurité de l'intelligence artificielle (INESIA), or the National Institute for AI Evaluation and Security.

Exact candidate: "National Institute for AI Evaluation and Security"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_183a824a550d6472ce16f25b

> The Japan AISI (or J-AISI) [26] was founded in February 2024.

Exact candidate: "Japan AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Japan AISI (or J-AISI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_2d5d62762614d7f9751b5ec3

> The Japan AISI (or J-AISI) [26] was founded in February 2024.

Exact candidate: "J-AISI"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "Japan AISI (or J-AISI)"

Run 1:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "organization" → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_d32b91ded45f5f4c06979abd

> Part of the Information Technology Promotion Agency, it employs about 23 people.

Exact candidate: "Information Technology Promotion Agency"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_a744d9239a7a5c3e6d5c8bf1

> [15] The institute consists of the Council of AISI, the AISI Steering Committee, and a secretariat with six teams.

Exact candidate: "Council of AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_2a5112494e1f6ae1e23126f6

> [15] The institute consists of the Council of AISI, the AISI Steering Committee, and a secretariat with six teams.

Exact candidate: "AISI Steering Committee"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_041e87a376c6f1be1abbe3c1

> [15] The institute consists of the Council of AISI, the AISI Steering Committee, and a secretariat with six teams.

Exact candidate: "secretariat"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe term \"secretariat\" can refer to a" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe term \"secretariat\" can refer to a" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe term \"secretariat\" can refer to a" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_1eeb716b3028be8fed3f80eb

> [26] Akiko Murakami (previously of IBM Japan and Sompo Japan) serves as the institute's executive director, and Kenji Hiramoto and Suguru [26]

Exact candidate: "IBM Japan"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_d6852a0011b8759b208a5eff

> [26] Akiko Murakami (previously of IBM Japan and Sompo Japan) serves as the institute's executive director, and Kenji Hiramoto and Suguru [26]

Exact candidate: "Sompo Japan"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nSompo Japan could be considered an organization as it" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nSompo Japan could be considered an organization as it" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nSompo Japan could be considered an organization as it" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_77745820df6f492734d99c6d

> [26] Akiko Murakami (previously of IBM Japan and Sompo Japan) serves as the institute's executive director, and Kenji Hiramoto and Suguru [26]

Exact candidate: "Suguru"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": null} → `not_organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": null} → `not_organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": "PERSON", "failed_class_check": null} → `not_organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_155ae29c04bbf36923b2def2

> Kenya agreed to join the international network of AI safety institutes, but the country has not announced any details yet.

Exact candidate: "Kenya"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_6b75ce14341ccefb5655fa8d

> Kenya agreed to join the international network of AI safety institutes, but the country has not announced any details yet.

Exact candidate: "international network of AI safety institutes"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": null} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_4580751016a22d6498d4f2fe

> Kenya agreed to join the international network of AI safety institutes, but the country has not announced any details yet.

Exact candidate: "AI safety institutes"
Gold expectation: boundary case, excluded from semantic scoring; overlaps "international network of AI safety institutes"

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (not scored: non-exact Gold overlap is an ORG-R1 boundary case)
Evaluation: neither result is semantically scored because the candidate boundary is unresolved

### held-out - qfc_b12dfcbe0e1c6257085f4cd9

> South Korea announced in May 2024 that it would create an AI safety institute under the umbrella of the Electronics and Telecommunications Research Institute.

Exact candidate: "South Korea"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: only ReFinED agrees with Gold

### held-out - qfc_f07f3aca15708a1fc8c0e5f6

> South Korea announced in May 2024 that it would create an AI safety institute under the umbrella of the Electronics and Telecommunications Research Institute.

Exact candidate: "Electronics and Telecommunications Research Institute"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_58395e6555a384d96afd4aae

> [15] The institute was founded in November 2024 [29] and is based in Bundang District within the city of Seongnam.

Exact candidate: "The institute"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "ambiguous" → `ambiguous` (incorrect abstention; Gold expects not_organization)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_6403daa0cff0e01e014c0981

> [37] Observers noted that this investment is relatively small, especially considering the presence of many big AI companies in the US.

Exact candidate: "Observers"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "not_organization" → `not_organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_429953a552931094ff1af377

> The NIST itself, which hosts the AISI, is also known for its chronic lack of funding.

Exact candidate: "NIST"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": false} → `organization` (correct)
Evaluation: both producers agree with Gold

### held-out - qfc_432f7df52805dc9a1adf0f77

> The NIST itself, which hosts the AISI, is also known for its chronic lack of funding.

Exact candidate: "AISI"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "not_organization\nambiguous\n\nThe AISI is mentioned in the context of being" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "not_organization\nambiguous\n\nThe AISI is mentioned in the context of being" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "not_organization\nambiguous\n\nThe AISI is mentioned in the context of being" → `None` (not a semantic result: invalid_output)
ReFinED: {"coarse_mention_type": "ORG", "failed_class_check": true} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: neither producer agrees with Gold

### held-out - qfc_3888d9904320e119f6fb6bb1

> [38][6] Biden administration's request for additional funding was met with further budget cuts from congressional appropriators.

Exact candidate: "Biden administration"
Gold expectation: `organization` (exact_gold)

Run 1:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (correct)
ReFinED: {"coarse_mention_type": null, "failed_class_check": false} → `ambiguous` (incorrect abstention; Gold expects organization)
Evaluation: only Qwen2.5 agrees with Gold

### held-out - qfc_bbe54f8b01158d7b22e72dba

> [38][6] Biden administration's request for additional funding was met with further budget cuts from congressional appropriators.

Exact candidate: "congressional appropriators"
Gold expectation: `not_organization` (disjoint_gold)

Run 1:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 2:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold

Run 3:

Qwen2.5: "organization" → `organization` (incorrect; Gold expects not_organization)
ReFinED: {"coarse_mention_type": null, "failed_class_check": null} → `ambiguous` (incorrect abstention; Gold expects not_organization)
Evaluation: neither producer agrees with Gold
