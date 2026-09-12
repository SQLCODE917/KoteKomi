import hashlib
import json
from dataclasses import replace

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiAssertionPresentation,
    WikiAuditCatalog,
    WikiAuditRecord,
    WikiAuditRecordType,
    WikiCitationRegistry,
    WikiEventPresentation,
    WikiEvidenceReference,
    WikiOntologyEdge,
    WikiOntologyQualifier,
    WikiPageInput,
)
from kotekomi_domain.models import JsonValue
from kotekomi_exporters import MarkdownCandidateWikiRenderer


def test_renderer_is_deterministic_lean_and_exposes_stable_audit_handles() -> None:
    plan = _plan()

    first = MarkdownCandidateWikiRenderer().render(plan)
    second = MarkdownCandidateWikiRenderer().render(plan)

    assert first == second
    assert first.manifest.build_id.startswith("wkb_")
    page = next(
        item.payload.decode() for item in first.files if item.relative_path == "actors/Amodei.md"
    )
    assert "Unpublished Candidate Wiki" in page
    assert f'kotekomi_wiki_build_id: "{first.manifest.build_id}"' in page
    assert 'kotekomi_record_id: "act_amodei"' in page
    assert "## At a glance" in page
    assert '**described Donald Trump as a "feudal warlord"**' in page
    assert "`evt_characterization`" in page
    assert (
        '**Extracted roles:** characterization **"feudal warlord"**; '
        "evaluated subject [Donald Trump](Donald_Trump.md); evaluator Amodei"
    ) in page
    assert "**Source, page 2:**" in page
    assert '> Amodei described Donald Trump as a "feudal warlord".' in page
    assert "Amodei characterized Donald Trump" not in page
    assert "## Relationships requiring review" in page
    assert 'Amodei — **described as feudal warlord** → **"feudal warlord"**' in page
    assert "`ast_incomplete`" in page
    assert "**Exact source, page 2:**" in page
    assert page.count('> Amodei described Donald Trump as a "feudal warlord".') == 2
    assert "## Event details" not in page
    assert "Ontology object graph" not in page
    assert "`has_argument`" not in page
    assert "`frame_role_id`" not in page
    assert "Source evidence" not in page
    assert "<summary>Audit trail</summary>" not in page
    audit = json.loads(
        next(item.payload for item in first.files if item.relative_path == "audit.json")
    )
    citations = json.loads(
        next(item.payload for item in first.files if item.relative_path == "citations.json")
    )
    assert audit["records"][0]["record_id"] == "act_amodei"
    assert citations["citations"][0]["exact_text"] == (
        'Amodei described Donald Trump as a "feudal warlord".'
    )


def test_renderer_escapes_record_and_source_control_text() -> None:
    plan = _plan()
    page = plan.pages[0]
    assertion = page.presentations[1]
    assert isinstance(assertion, WikiAssertionPresentation)
    escaped_assertion = replace(
        assertion,
        edge=replace(
            assertion.edge,
            predicate="used | <script>",
            object_label="[unsafe]",
        ),
    )
    escaped_page = replace(
        page,
        presentations=(page.presentations[0], escaped_assertion),
    )
    escaped_evidence = tuple(
        replace(item, exact_text="[source] | <script>\nnext")
        for item in plan.citation_registry.citations
    )
    escaped_plan = replace(
        plan,
        pages=(escaped_page,),
        citation_registry=replace(plan.citation_registry, citations=escaped_evidence),
    )

    markdown = next(
        item.payload.decode()
        for item in MarkdownCandidateWikiRenderer().render(escaped_plan).files
        if item.relative_path == "actors/Amodei.md"
    )

    assert "used \\| &lt;script&gt;" in markdown
    assert "**\\[unsafe\\]**" in markdown
    assert "<script>" not in markdown
    assert "> \\[source\\] \\| &lt;script&gt; next" in markdown


def test_renderer_preserves_each_exact_source_grounded_event_label() -> None:
    plan = _plan()
    page = plan.pages[0]
    event = page.presentations[0]
    assert isinstance(event, WikiEventPresentation)

    for event_label in ("privately lobbied", 'criticized Stargate as "chaotic"'):
        source_event = replace(event, event_label=event_label)
        frame_page = replace(page, presentations=(source_event,))
        markdown = next(
            item.payload.decode()
            for item in MarkdownCandidateWikiRenderer()
            .render(replace(plan, pages=(frame_page,)))
            .files
            if item.relative_path == "actors/Amodei.md"
        )

        assert f"**{event_label}**" in markdown
        assert "**Extracted roles:**" in markdown
        assert "Ontology object graph" not in markdown


def _plan() -> CandidateWikiPlan:
    evidence = WikiEvidenceReference(
        citation_number=1,
        reference_key="target:etg_example:eva_example",
        reference_kind="evidence_target",
        source_id="src_example",
        document_id="doc_example",
        representation_id="rep_example",
        text_view_id="tvw_example",
        start_char=120,
        end_char=177,
        exact_text='Amodei described Donald Trump as a "feudal warlord".',
        prefix_text="",
        suffix_text="",
        node_ids=("nod_example",),
        page_numbers=(2,),
        evidence_target_id="etg_example",
        evidence_validation_attempt_id="eva_example",
        proposed_change_id=None,
    )
    proposal_evidence = replace(
        evidence,
        citation_number=2,
        reference_key="proposal:pcg_event:0",
        reference_kind="proposal_evidence",
        evidence_target_id=None,
        evidence_validation_attempt_id=None,
        proposed_change_id="pcg_event",
    )
    event = WikiEventPresentation(
        presentation_id="event:evt_characterization",
        event_id="evt_characterization",
        assertion_ids=(
            "ast_characterization",
            "ast_evaluated_subject",
            "ast_evaluator",
            "ast_event_type",
            "ast_modality",
            "ast_polarity",
        ),
        proposed_change_ids=("pcg_event", "pcg_characterization"),
        event_label='described Donald Trump as a "feudal warlord"',
        state="pending",
        edges=(
            _edge("ast_event_type", "has_event_type", "characterization"),
            _edge(
                "ast_characterization",
                "has_argument",
                '"feudal warlord"',
                qualifiers=(
                    WikiOntologyQualifier("frame_role_id", "characterization.characterization"),
                    WikiOntologyQualifier("upper_role", "content"),
                ),
            ),
            _edge(
                "ast_evaluated_subject",
                "has_argument",
                "Donald Trump",
                object_path="actors/Donald_Trump.md",
                qualifiers=(
                    WikiOntologyQualifier("frame_role_id", "characterization.evaluated_subject"),
                    WikiOntologyQualifier("upper_role", "theme"),
                ),
            ),
            _edge(
                "ast_evaluator",
                "has_argument",
                "Amodei",
                object_path="actors/Amodei.md",
                qualifiers=(
                    WikiOntologyQualifier("frame_role_id", "characterization.evaluator"),
                    WikiOntologyQualifier("upper_role", "agent"),
                ),
            ),
            _edge("ast_polarity", "has_polarity", "affirmed"),
            _edge("ast_modality", "has_modality", "actual"),
        ),
        issues=(),
        citation_numbers=(1, 2),
        related_paths=("actors/Amodei.md", "actors/Donald_Trump.md", "events/Event.md"),
    )
    assertion = WikiAssertionPresentation(
        presentation_id="assertion:ast_incomplete",
        proposed_change_id="pcg_incomplete",
        edge=WikiOntologyEdge(
            assertion_id="ast_incomplete",
            subject_label="Amodei",
            subject_path="actors/Amodei.md",
            predicate="described as feudal warlord",
            object_label='"feudal warlord"',
            object_path=None,
            qualifiers=(),
        ),
        state="pending",
        citation_numbers=(1, 2),
        related_paths=("actors/Amodei.md",),
    )
    page = WikiPageInput(
        relative_path="actors/Amodei.md",
        page_kind="actor",
        record_id="act_amodei",
        display_label="Amodei",
        state="pending",
        details=(),
        links=(),
        presentations=(event, assertion),
        citation_numbers=(1, 2),
        input_fingerprint="a" * 64,
    )
    return CandidateWikiPlan(
        view_policy_id="candidate_wiki_view_v5",
        renderer_policy_id="source_grounded_markdown_wiki_v8",
        ingestion_run_id="igr_example",
        ingestion_change_set_id="ics_example",
        candidate_snapshot_digest="b" * 64,
        pages=(page,),
        citation_registry=WikiCitationRegistry("b" * 64, (evidence, proposal_evidence)),
        audit_catalog=_audit_catalog(event, assertion),
        counts=(("Assertion.pending", 1),),
    )


def _audit_catalog(
    event: WikiEventPresentation,
    assertion: WikiAssertionPresentation,
) -> WikiAuditCatalog:
    records = [
        _audit_record(
            "act_amodei",
            "Actor",
            edges=(),
            evidence_reference_keys=(),
        ),
        _audit_record(
            event.event_id,
            "Event",
            edges=event.edges,
            evidence_reference_keys=("proposal:pcg_event:0", "target:etg_example:eva_example"),
        ),
        _audit_record(
            assertion.edge.assertion_id,
            "Assertion",
            edges=(assertion.edge,),
            evidence_reference_keys=("proposal:pcg_event:0", "target:etg_example:eva_example"),
        ),
    ]
    records.extend(
        _audit_record(
            edge.assertion_id,
            "Assertion",
            edges=(edge,),
            evidence_reference_keys=("proposal:pcg_event:0", "target:etg_example:eva_example"),
        )
        for edge in event.edges
    )
    return WikiAuditCatalog("b" * 64, tuple(sorted(records, key=lambda item: item.record_id)))


def _audit_record(
    record_id: str,
    record_type: WikiAuditRecordType,
    *,
    edges: tuple[WikiOntologyEdge, ...],
    evidence_reference_keys: tuple[str, ...],
) -> WikiAuditRecord:
    payload: dict[str, JsonValue] = {"id": record_id}
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return WikiAuditRecord(
        record_id=record_id,
        record_type=record_type,
        state="pending",
        review_status="pending",
        record_payload=payload,
        record_payload_sha256=digest,
        proposed_change_ids=(),
        provenance_activity_ids=(),
        evidence_reference_keys=evidence_reference_keys,
        ontology_edges=edges,
    )


def _edge(
    assertion_id: str,
    predicate: str,
    object_label: str,
    *,
    object_path: str | None = None,
    qualifiers: tuple[WikiOntologyQualifier, ...] = (),
) -> WikiOntologyEdge:
    return WikiOntologyEdge(
        assertion_id=assertion_id,
        subject_label="Characterization",
        subject_path="events/Event.md",
        predicate=predicate,
        object_label=object_label,
        object_path=object_path,
        qualifiers=qualifiers,
    )
