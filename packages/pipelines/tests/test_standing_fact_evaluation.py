from __future__ import annotations

from pathlib import Path

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiAssertionPresentation,
    WikiAuditCatalog,
    WikiCitationRegistry,
    WikiEvidenceReference,
    WikiOntologyEdge,
    WikiPageInput,
)
from kotekomi_domain import ProposedChange
from kotekomi_pipelines.standing_fact_evaluation import (
    StandingFactReconciledRecord,
    StandingFactRuntimeDecision,
    StandingFactRuntimeDraft,
    StandingFactRuntimeEvidence,
    StandingFactRuntimeRecord,
    evaluate_standing_fact_gold,
    load_standing_fact_gold,
    standing_fact_reconciliation_from_proposed_changes,
)

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "docs/hsq-standing-fact-gold-v1.json"


def test_standing_fact_gold_names_all_three_current_acceptance_cases() -> None:
    catalog = load_standing_fact_gold(GOLD)

    assert tuple(item.item_id for item in catalog.items) == ("AMO-02", "AMO-07", "ANT-11")
    assert all(
        value in item.source_text
        for item in catalog.items
        for value in (item.subject_text, *item.accepted_relation_texts, item.object_text)
    )


def test_standing_fact_evaluation_reports_each_missing_item_independently() -> None:
    catalog = load_standing_fact_gold(GOLD)

    report = evaluate_standing_fact_gold(
        catalog,
        {},
        reconciled_records=(),
        wiki_plan=None,
    )

    assert report.passed is False
    assert report.item_count == report.missing_count == 3
    assert tuple(item.status for item in report.items) == ("missing", "missing", "missing")


def test_standing_fact_evaluation_proves_source_proposal_and_wiki_visibility() -> None:
    catalog = load_standing_fact_gold(GOLD)
    expected = next(item for item in catalog.items if item.item_id == "AMO-07")
    draft = _draft(expected.source_text, expected.source_text_sha256)
    evidence = StandingFactRuntimeEvidence(
        paragraph_ordinal=expected.paragraph_ordinal,
        drafts=(draft,),
        decisions=(
            StandingFactRuntimeDecision(
                id="sfdc_fixture",
                draft_id=draft.id,
                disposition="proposed",
                proposed_change_ids=("pcg_fixture",),
            ),
        ),
        proposed_records=(
            StandingFactRuntimeRecord(
                proposed_change_id="pcg_fixture",
                record_id="ast_fixture",
            ),
        ),
    )

    report = evaluate_standing_fact_gold(
        catalog,
        {expected.paragraph_ordinal: evidence},
        reconciled_records=_reconciled_records(),
        wiki_plan=_wiki(expected.source_text),
    )
    result = next(item for item in report.items if item.item_id == expected.item_id)

    assert result.status == "exact"
    assert result.passed is True
    assert result.matched_draft == draft
    assert result.proposed_record_ids == ("ast_fixture",)
    assert result.reconciled_records == _reconciled_records()
    assert result.wiki_page_paths == ("organizations/Anthropic.md",)


def test_standing_fact_reconciliation_maps_parent_proposal_to_current_record() -> None:
    records = standing_fact_reconciliation_from_proposed_changes(
        (
            ProposedChange(
                id="pcg_reconciled",
                proposed_json={
                    "record_type": "Assertion",
                    "record": {"id": "ast_reconciled"},
                    "identity_reconciliation": {
                        "preview_id": "erp_fixture",
                        "parent_proposed_change_id": "pcg_fixture",
                        "rewritten_record_ids": {
                            "org_original": "org_reconciled",
                        },
                    },
                },
            ),
        )
    )

    assert records == _reconciled_records()


def _reconciled_records() -> tuple[StandingFactReconciledRecord, ...]:
    return (
        StandingFactReconciledRecord(
            source_proposed_change_id="pcg_fixture",
            reconciled_proposed_change_id="pcg_reconciled",
            reconciled_record_id="ast_reconciled",
        ),
    )


def _draft(source_text: str, source_text_sha256: str) -> StandingFactRuntimeDraft:
    subject = "Anthropic"
    relation = "strategy has mirrored"
    object_text = "Amodei's views toward Trump"
    return StandingFactRuntimeDraft(
        id="sfd_fixture",
        source_text_sha256=source_text_sha256,
        subject_text=subject,
        subject_start=source_text.index(subject),
        subject_end=source_text.index(subject) + len(subject),
        relation_label=relation,
        relation_start=source_text.index(relation),
        relation_end=source_text.index(relation) + len(relation),
        object_text=object_text,
        object_start=source_text.index(object_text),
        object_end=source_text.index(object_text) + len(object_text),
    )


def _wiki(source_text: str) -> CandidateWikiPlan:
    citation = WikiEvidenceReference(
        citation_number=1,
        reference_key="source:1",
        reference_kind="proposal_evidence",
        source_id="src_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        text_view_id="tvw_fixture",
        start_char=0,
        end_char=len(source_text),
        exact_text=source_text,
        prefix_text="",
        suffix_text="",
        node_ids=("nod_fixture",),
        page_numbers=(1,),
        evidence_target_id="etg_fixture",
        evidence_validation_attempt_id="eva_fixture",
        proposed_change_id="pcg_reconciled",
    )
    edge = WikiOntologyEdge(
        assertion_id="ast_reconciled",
        subject_label="Anthropic",
        subject_path="organizations/Anthropic.md",
        predicate="strategy has mirrored",
        object_label="Amodei's views toward Trump",
        object_path=None,
        qualifiers=(),
    )
    page = WikiPageInput(
        relative_path="organizations/Anthropic.md",
        page_kind="Organization",
        record_id="org_fixture",
        display_label="Anthropic",
        state="pending",
        details=(),
        links=(),
        presentations=(
            WikiAssertionPresentation(
                presentation_id="wpr_fixture",
                proposed_change_id="pcg_reconciled",
                edge=edge,
                state="pending",
                citation_numbers=(1,),
                related_paths=(),
            ),
        ),
        citation_numbers=(1,),
        input_fingerprint="a" * 64,
    )
    return CandidateWikiPlan(
        view_policy_id="fixture",
        renderer_policy_id="fixture",
        ingestion_run_id="igr_fixture",
        ingestion_change_set_id="ics_fixture",
        candidate_snapshot_digest="b" * 64,
        pages=(page,),
        citation_registry=WikiCitationRegistry(
            candidate_snapshot_digest="b" * 64,
            citations=(citation,),
        ),
        audit_catalog=WikiAuditCatalog(
            candidate_snapshot_digest="b" * 64,
            records=(),
        ),
        counts=(),
    )
