from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiCitationRegistry,
    WikiEvidenceReference,
    WikiPageInput,
    WikiStatement,
)
from kotekomi_exporters import MarkdownCandidateWikiRenderer


def test_renderer_is_deterministic_visible_and_keeps_ids_out_of_markdown() -> None:
    plan = _plan()

    first = MarkdownCandidateWikiRenderer().render(plan)
    second = MarkdownCandidateWikiRenderer().render(plan)

    assert first == second
    assert first.manifest.build_id.startswith("wkb_")
    page = next(item.payload.decode() for item in first.files if item.relative_path == "index.md")
    assert "Unpublished Candidate Wiki" in page
    assert "[PENDING]" in page
    assert "proposed relation `hired`" in page
    assert "[Acme](organizations/Acme.md)" in page
    assert '```"literal value"```' not in page
    assert "Acme hired Alice." in page
    assert not any(prefix in page for prefix in ("org_", "evt_", "ast_", "src_", "doc_"))


def _plan() -> CandidateWikiPlan:
    evidence = WikiEvidenceReference(
        citation_number=1,
        reference_key="proposal:pcg_example",
        reference_kind="proposal_evidence",
        source_id="src_example",
        document_id="doc_example",
        representation_id="rep_example",
        text_view_id="tvw_example",
        start_char=0,
        end_char=17,
        exact_text="Acme hired Alice.",
        prefix_text="",
        suffix_text="",
        node_ids=("nod_example",),
        page_numbers=(1,),
        evidence_target_id=None,
        evidence_validation_attempt_id=None,
        proposed_change_id="pcg_example",
    )
    statement = WikiStatement(
        subject_label="Hiring",
        subject_path="events/Hiring.md",
        relation_label="hired",
        object_label="Acme",
        object_path="organizations/Acme.md",
        state="pending",
        citation_numbers=(1,),
    )
    page = WikiPageInput(
        relative_path="index.md",
        page_kind="home",
        display_label="Candidate Wiki",
        state=None,
        details=(),
        links=(),
        outgoing_statements=(statement,),
        inbound_statements=(),
        citation_numbers=(1,),
        input_fingerprint="a" * 64,
    )
    return CandidateWikiPlan(
        view_policy_id="candidate_wiki_view_v1",
        renderer_policy_id="deterministic_markdown_wiki_v1",
        ingestion_run_id="igr_example",
        ingestion_change_set_id="ics_example",
        candidate_snapshot_digest="b" * 64,
        pages=(page,),
        citation_registry=WikiCitationRegistry("b" * 64, (evidence,)),
        counts=(("Assertion.pending", 1),),
    )
