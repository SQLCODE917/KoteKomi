from kotekomi_application import BriefingRenderInput
from kotekomi_briefing import MarkdownBriefingRenderer
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    EvidenceSpan,
    Relationship,
    SelectorType,
    Source,
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
            sources=(
                Source(
                    id="src_article_a",
                    source_type=SourceType.ARTICLE,
                    title="Article A",
                ),
            ),
            assertions=(
                Assertion(
                    id="ast_inference",
                    assertion_type=AssertionType.ANALYTIC_INFERENCE,
                    subject_entity_id="org_anthropic",
                    predicate="shared_governance_outcome_with",
                    object_entity_id="org_commerce_department",
                    status=AssertionStatus.CORROBORATED,
                    provenance_activity_ids=("prv_review",),
                    current_assessment="Anthropic and Commerce shared a governance outcome.",
                ),
                Assertion(
                    id="ast_source_claim",
                    assertion_type=AssertionType.SOURCE_CLAIM,
                    subject_entity_id="org_anthropic",
                    predicate="delayed_rollout",
                    object_value={"model": "Claude Fable 5"},
                    status=AssertionStatus.REPORTED,
                    source_ids=("src_article_a",),
                    evidence_span_ids=("evs_article_a_claim",),
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
            argument_edges=(
                ArgumentEdge(
                    id="arg_claim_infers_governance",
                    from_assertion_id="ast_source_claim",
                    to_assertion_id="ast_inference",
                    relation=ArgumentEdgeRelation.INFERS,
                    rationale="The Source claim participates in the governance outcome pattern.",
                    evidence_span_ids=("evs_article_a_claim",),
                    confidence=0.7,
                ),
            ),
            evidence_spans=(
                EvidenceSpan(
                    id="evs_article_a_claim",
                    source_id="src_article_a",
                    document_id="doc_article_a",
                    selector_type=SelectorType.EXACT_TEXT,
                    exact_text="Article A says the rollout was delayed.",
                ),
            ),
            analytic_inference_assertion_ids=("ast_inference",),
        )
    ).markdown

    assert "# Daily Briefing" in markdown
    assert "Previous Briefing: `brf_previous`" in markdown
    assert "`src_article_a`" in markdown
    assert "`evs_article_a_claim`" in markdown
    assert "`ast_inference` (Analytic inference)" in markdown
    assert "Analytic inference `ast_inference`" in markdown
    assert "`rel_shared_governance`" in markdown
    assert "`arg_claim_infers_governance`" in markdown
