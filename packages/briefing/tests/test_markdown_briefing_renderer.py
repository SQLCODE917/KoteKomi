from kotekomi_application import (
    BriefingAnalyticTraceRow,
    BriefingCitation,
    BriefingCitationRegistry,
    BriefingCollectionRequirement,
    BriefingEntityEventIndexRow,
    BriefingEvidenceQuality,
    BriefingJudgmentBasis,
    BriefingNarrative,
    BriefingNarrativeSentence,
    BriefingReferenceAppendix,
    BriefingRenderInput,
)
from kotekomi_briefing import MarkdownBriefingRenderer
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Document,
    EpistemicScope,
    Event,
    EvidenceTarget,
    Organization,
    Outcome,
    Relationship,
    Source,
    SourceAuthority,
    SourceType,
)


def test_markdown_renderer_includes_citations_and_analytic_inference_label() -> None:
    renderer = MarkdownBriefingRenderer()

    markdown = renderer.render(
        BriefingRenderInput(
            briefing_id="brf_daily",
            title="Daily Briefing",
            generated_at="2026-07-09T12:00:00+00:00",
            previous_briefing_id="brf_previous",
            narrative=BriefingNarrative(
                executive_judgment=BriefingNarrativeSentence(
                    text=(
                        "KoteKomi assesses that Commerce review pressure became a "
                        "release-governance constraint on Anthropic's Claude Fable 5 rollout."
                    ),
                    citation_numbers=(2,),
                ),
                what_changed=(
                    BriefingNarrativeSentence(
                        text="Source report: Anthropic delayed rollout.",
                        citation_numbers=(1,),
                    ),
                ),
                judgment_basis=(
                    BriefingJudgmentBasis(
                        source_basis=(
                            BriefingNarrativeSentence(
                                text="The article states that Anthropic delayed rollout.",
                                citation_numbers=(1,),
                            ),
                        ),
                        observed_effects=(
                            BriefingNarrativeSentence(
                                text="The article states that Anthropic delayed rollout.",
                                citation_numbers=(1,),
                            ),
                        ),
                        assessment=BriefingNarrativeSentence(
                            text=(
                                "KoteKomi infers a release-governance constraint because "
                                "Commerce review and the rollout delay connect government "
                                "review to Anthropic release timing."
                            ),
                            citation_numbers=(2,),
                        ),
                        confidence=BriefingNarrativeSentence(
                            text=(
                                "Moderate. The inference is supported by one source-backed "
                                "Assertion from one Source; the Source authority is secondary."
                            ),
                            citation_numbers=(2,),
                        ),
                    ),
                ),
                evidence_quality=(
                    BriefingEvidenceQuality(
                        claim=BriefingNarrativeSentence(
                            text="Source report: Anthropic delayed rollout.",
                            citation_numbers=(1,),
                        ),
                        source_authority=SourceAuthority.SECONDARY,
                        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
                        source_count=1,
                        evidence_target_count=1,
                        citation_numbers=(1,),
                    ),
                ),
                collection_gaps=(
                    BriefingNarrativeSentence(
                        text="The analytic inference is not directly stated by a Source.",
                        citation_numbers=(2,),
                    ),
                ),
                indicators_to_watch=(
                    BriefingNarrativeSentence(
                        text="Watch for primary-source statements on model-release review.",
                        citation_numbers=(3,),
                    ),
                ),
                implications=(
                    BriefingNarrativeSentence(
                        text=(
                            "KoteKomi analysis treats government review as an operational "
                            "release constraint."
                        ),
                        citation_numbers=(2,),
                    ),
                ),
                reference_appendix=BriefingReferenceAppendix(
                    analytic_trace=(
                        BriefingAnalyticTraceRow(
                            finding=(
                                "Anthropic and Commerce Department share a "
                                "release-governance outcome."
                            ),
                            support="Anthropic delayed rollout.",
                            relation="supports",
                            confidence_label="Moderate",
                            citation_numbers=(4,),
                        ),
                    ),
                    collection_requirements=(
                        BriefingCollectionRequirement(
                            gap="The analytic inference is not directly stated by a Source.",
                            closes_with=(
                                "A Source that directly states the inferred governance "
                                "relationship."
                            ),
                            citation_numbers=(2,),
                        ),
                    ),
                    entity_event_index=(
                        BriefingEntityEventIndexRow(
                            record_type="Organization",
                            name="Anthropic",
                            context="Selected Organization.",
                        ),
                        BriefingEntityEventIndexRow(
                            record_type="Organization",
                            name="Commerce Department",
                            context="Selected Organization.",
                        ),
                        BriefingEntityEventIndexRow(
                            record_type="Event",
                            name="Emergency release review call",
                            context="Participants: Anthropic and Commerce Department",
                        ),
                        BriefingEntityEventIndexRow(
                            record_type="Outcome",
                            name="Anthropic resumed access with notice commitments.",
                            context="Links Anthropic, Commerce Department, and event.",
                        ),
                    ),
                ),
            ),
            citation_registry=BriefingCitationRegistry(
                briefing_id="brf_daily",
                citations=(
                    BriefingCitation(
                        number=1,
                        citation_key="ctn_source_claim",
                        label="Source-backed Assertion",
                        summary="Source report: Anthropic delayed rollout.",
                        confidence_label="Moderate",
                        is_analytic_inference=False,
                        source_ids=("src_article_a",),
                        document_ids=("doc_article_a",),
                        evidence_target_ids=("etg_article_a_claim",),
                        assertion_ids=("ast_source_claim",),
                    ),
                    BriefingCitation(
                        number=2,
                        citation_key="ctn_inference",
                        label="Analytic inference",
                        summary=(
                            "Inference: Anthropic and Commerce Department share "
                            "a release-governance outcome."
                        ),
                        confidence_label="Moderate",
                        is_analytic_inference=True,
                        source_ids=("src_article_a",),
                        document_ids=("doc_article_a",),
                        evidence_target_ids=("etg_article_a_claim",),
                        assertion_ids=("ast_inference", "ast_source_claim"),
                        argument_edge_ids=("arg_claim_infers_governance",),
                    ),
                    BriefingCitation(
                        number=3,
                        citation_key="ctn_open_question",
                        label="Event",
                        summary="What role did Commerce play beyond recorded participation?",
                        confidence_label="Not assessed",
                        is_analytic_inference=False,
                        organization_ids=("org_commerce_department",),
                        event_ids=("evt_review_call",),
                    ),
                    BriefingCitation(
                        number=4,
                        citation_key="ctn_argument_edge",
                        label="ArgumentEdge",
                        summary=(
                            "Source report support: Anthropic delayed rollout supports the "
                            "inference that Anthropic and Commerce Department share "
                            "a release-governance outcome."
                        ),
                        confidence_label="Moderate",
                        is_analytic_inference=False,
                        source_ids=("src_article_a",),
                        document_ids=("doc_article_a",),
                        evidence_target_ids=("etg_article_a_claim",),
                        assertion_ids=("ast_inference", "ast_source_claim"),
                        argument_edge_ids=("arg_claim_infers_governance",),
                    ),
                ),
            ),
            entities=(),
            actors=(),
            organizations=(
                Organization(id="org_anthropic", name="Anthropic"),
                Organization(id="org_commerce_department", name="Commerce Department"),
            ),
            places=(),
            events=(
                Event(
                    id="evt_review_call",
                    name="Emergency release review call",
                    participant_organization_ids=("org_anthropic", "org_commerce_department"),
                ),
            ),
            sources=(
                Source(
                    id="src_article_a",
                    source_type=SourceType.ARTICLE,
                    identity_policy_id="fixture_v1",
                    canonical_identity_key="article_a",
                ),
            ),
            documents=(
                Document(
                    id="doc_article_a",
                    source_id="src_article_a",
                    content_sha256="a" * 64,
                ),
            ),
            assertions=(
                Assertion(
                    id="ast_inference",
                    assertion_type=AssertionType.ANALYTIC_INFERENCE,
                    epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
                    subject_entity_id="org_anthropic",
                    predicate="shared_governance_outcome_with",
                    object_entity_id="org_commerce_department",
                    status=AssertionStatus.CORROBORATED,
                    source_authority=SourceAuthority.NOT_APPLICABLE,
                    attribution_basis=AttributionBasis.NOT_APPLICABLE,
                    provenance_activity_ids=("prv_review",),
                    current_assessment="Anthropic and Commerce shared a governance outcome.",
                ),
                Assertion(
                    id="ast_source_claim",
                    assertion_type=AssertionType.SOURCE_CLAIM,
                    epistemic_scope=EpistemicScope.SOURCE_REPORT,
                    subject_entity_id="org_anthropic",
                    predicate="delayed_rollout",
                    object_value={"model": "Claude Fable 5"},
                    status=AssertionStatus.REPORTED,
                    source_authority=SourceAuthority.SECONDARY,
                    attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
                    source_ids=("src_article_a",),
                    evidence_target_ids=("etg_article_a_claim",),
                    provenance_activity_ids=("prv_review",),
                ),
            ),
            relationships=(
                Relationship(
                    id="rel_shared_governance",
                    subject_id="org_anthropic",
                    predicate="shared_governance_outcome_with",
                    object_id="org_commerce_department",
                    assertion_ids=("ast_inference",),
                ),
            ),
            outcomes=(
                Outcome(
                    id="out_monitoring_commitment",
                    description="Anthropic resumed access with notice commitments.",
                    organization_ids=("org_anthropic", "org_commerce_department"),
                    event_ids=("evt_review_call",),
                    assertion_ids=("ast_inference", "ast_source_claim"),
                ),
            ),
            argument_edges=(
                ArgumentEdge(
                    id="arg_claim_infers_governance",
                    from_assertion_id="ast_source_claim",
                    to_assertion_id="ast_inference",
                    relation=ArgumentEdgeRelation.INFERS,
                    rationale="The Source claim participates in the governance outcome pattern.",
                    evidence_target_ids=("etg_article_a_claim",),
                    confidence=0.7,
                ),
            ),
            evidence_targets=(
                EvidenceTarget(
                    id="etg_article_a_claim",
                    source_id="src_article_a",
                    document_id="doc_article_a",
                    representation_id="rep_article_a",
                    text_view_id="tvw_article_a",
                    text_view_digest="0" * 64,
                    start_char=0,
                    end_char=37,
                    exact_text="Article A says the rollout was delayed.",
                    normalization_policy="fixture_v1",
                    node_ids=("nod_article_a",),
                ),
            ),
            analytic_inference_assertion_ids=("ast_inference",),
        )
    ).markdown

    assert "# Daily Briefing" in markdown
    assert "Previous Briefing: `brf_previous`" in markdown
    expected_sections = (
        "## Executive Judgment",
        "## What Changed",
        "## Judgment Basis",
        "## Evidence and Source Quality",
        "## Open Questions and Collection Gaps",
        "## Indicators to Watch",
        "## Implications",
        "## Reference Appendix",
    )
    rendered_sections = tuple(line for line in markdown.splitlines() if line.startswith("## "))
    assert rendered_sections == expected_sections
    for removed_heading in (
        "## Bottom Line",
        "## Judgment",
        "## Key Judgments",
        "## Evidence Basis",
        "## Analytic Trace",
        "## Citations",
    ):
        assert removed_heading not in rendered_sections
    assert "Source report: Anthropic delayed rollout.[1]" in markdown
    assert (
        "KoteKomi assesses that Commerce review pressure became a release-governance "
        "constraint on Anthropic's Claude Fable 5 rollout.[2]" in markdown
    )
    assert "Source basis:" in markdown
    assert "Observed effects:" in markdown
    assert "Confidence: Moderate" in markdown
    assert (
        "| Source report: Anthropic delayed rollout.[1] | Secondary | Reported By Source | "
        "1 | 1 |" in markdown
    )
    assert "The analytic inference is not directly stated by a Source.[2]" in markdown
    assert "Watch for primary-source statements on model-release review.[3]" in markdown
    assert (
        "KoteKomi analysis treats government review as an operational release constraint.[2]"
        in markdown
    )
    expected_appendix_sections = (
        "### Citation Register",
        "### Source Quality Register",
        "### Analytic Trace",
        "### Collection Requirements",
        "### Entity and Event Index",
    )
    rendered_appendix_sections = tuple(
        line for line in markdown.splitlines() if line.startswith("### ")
    )
    assert rendered_appendix_sections == expected_appendix_sections
    for removed_appendix_heading in (
        "### Citations",
        "### Key Entities",
        "### Key Organizations",
        "### Key Actors",
        "### Key Places",
        "### Key Events",
        "### Outcomes",
        "### Sources",
    ):
        assert removed_appendix_heading not in markdown
    assert "| [1] | Source-backed Assertion | Source report: Anthropic delayed rollout." in markdown
    assert (
        "| [2] | Analytic inference | Inference: Anthropic and Commerce Department share"
        in markdown
    )
    assert "Source-backed Assertion: Source report" not in markdown
    assert "ArgumentEdge:" not in markdown
    assert "Support link" in markdown
    assert "| [4] | Support link | Source report support:" in markdown
    assert "Relationship:" not in markdown
    assert "Outcome:" not in markdown
    assert "### Analytic Trace" in markdown
    assert "| Anthropic and Commerce Department share a release-governance outcome.[4]" in markdown
    assert "| Anthropic delayed rollout. | supports | Moderate |" in markdown
    assert "### Collection Requirements" in markdown
    assert "A Source that directly states the inferred governance relationship." in markdown
    assert "### Entity and Event Index" in markdown
    assert "Anthropic" in markdown
    assert "Commerce Department" in markdown
    assert "Emergency release review call" in markdown
    assert "Anthropic resumed access with notice commitments." in markdown
    for raw_prefix in (
        "act_",
        "arg_",
        "ast_",
        "ctn_",
        "doc_",
        "evt_",
        "evt_",
        "org_",
        "rel_",
        "src_",
    ):
        assert raw_prefix not in markdown
