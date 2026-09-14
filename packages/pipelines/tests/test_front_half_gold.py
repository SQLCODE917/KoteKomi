from __future__ import annotations

import json
from pathlib import Path

from kotekomi_pipelines.front_half_stage_local import load_front_half_gold

ROOT = Path(__file__).resolve().parents[3]
AMODEI = ROOT / "docs/hsq-front-half-amodei-gold-v1.json"
ANTHROPIC = ROOT / "docs/hsq-front-half-anthropic-gold-v1.json"
BOUNDARY_PROMPT = ROOT / "prompts/hybrid_mention_boundary_adjudication_v2.md"
REFERENCE_PROMPT = ROOT / "prompts/semantic_reference_challenge_v4.md"
REFERENCE_VALIDATION_PROMPT = ROOT / "prompts/semantic_reference_candidate_validation_v1.md"
STANDING_FACT_PROMPT = ROOT / "prompts/hybrid_standing_fact_task_v3.md"
EVENT_PROMPTS = tuple(
    path
    for path in sorted((ROOT / "prompts").glob("event_*_v1.md"))
    if path.name.startswith(("event_noun_", "event_verb_"))
)


def test_front_half_gold_preserves_twenty_cases_for_each_focus_entity() -> None:
    amodei = load_front_half_gold(AMODEI)
    anthropic = load_front_half_gold(ANTHROPIC)

    assert len(amodei.items) == len(anthropic.items) == 20
    assert amodei.focus_entity.accepted_source_literals == ("Dario Amodei", "Amodei")
    assert anthropic.focus_entity.accepted_source_literals == ("Anthropic",)
    assert {item.item_id for item in amodei.items}.isdisjoint(
        item.item_id for item in anthropic.items
    )


def test_front_half_gold_contains_no_retired_event_admission_fields() -> None:
    retired = {
        "expected_route",
        "expected_trigger_head_text",
        "expected_frame_id",
        "expected_roles",
        "expected_qualifiers",
        "expected_polarity",
        "expected_modality",
        "expected_attribution",
        "expected_disposition",
        "allocation_cases",
        "accepted_trigger_expression_texts",
        "expected_standing_fact",
    }

    for path in (AMODEI, ANTHROPIC):
        value = json.loads(path.read_bytes())
        assert not any(retired & set(item) for item in value["items"])


def test_front_half_gold_stores_the_reviewed_ant14_antecedent_directly() -> None:
    catalog = load_front_half_gold(ANTHROPIC)
    item = next(item for item in catalog.items if item.item_id == "ANT-14")

    assert item.expected_references[0].reference_text == "he"
    assert item.expected_references[0].accepted_antecedent_texts == ("David  Sacks",)


def test_boundary_prompt_preserves_complete_proper_name_possessors_without_gold_leakage() -> None:
    prompt = BOUNDARY_PROMPT.read_text()

    assert "A proper name that identifies a referent remains complete" in prompt
    assert "both `Acme` and `Acme's services` are complete" in prompt
    assert "Do not prefer the longest candidate" in prompt
    assert "Complete every line listed under `required_output_prefixes` exactly once" in prompt
    assert "<supplied" not in prompt
    assert "ontology kind" not in prompt
    assert "source offsets" not in prompt
    assert "Ledger records" not in prompt
    assert "Anthropic" not in prompt
    assert "Amodei" not in prompt


def test_reference_prompt_asks_only_for_one_task_local_semantic_choice() -> None:
    prompt = REFERENCE_PROMPT.read_text()

    assert "Perform only semantic antecedent selection" in prompt
    assert "Resolve only the exact target" in prompt
    assert "nearby wording that identifies its occurrence" in prompt
    assert "Select one supplied `aN` label" in prompt
    assert "Return exactly those two lines" in prompt
    assert "smallest complete clause" not in prompt
    assert "Substitute each supplied candidate expression" not in prompt
    assert "F-Coref" not in prompt
    assert "source range" not in prompt
    assert "Entity ID" not in prompt
    assert "Ledger record" not in prompt


def test_reference_validation_prompt_asks_one_binary_semantic_question() -> None:
    prompt = REFERENCE_VALIDATION_PROMPT.read_text()

    assert "one supplied antecedent candidate" in prompt
    assert "Decide only whether the target reference means" in prompt
    assert "`supported`" in prompt
    assert "`unsupported`" in prompt
    assert "`unclear`" in prompt
    assert "Return exactly those two lines" in prompt
    assert "F-Coref" not in prompt
    assert "candidate ID" not in prompt
    assert "source offset" not in prompt
    assert "Ledger" not in prompt


def test_trigger_prompts_each_assign_one_bounded_semantic_task() -> None:
    assert len(EVENT_PROMPTS) == 8
    for path in EVENT_PROMPTS:
        prompt = path.read_text()
        assert "Return exactly one" in prompt
        assert "marked" in prompt.casefold()
        if path.name == "event_verb_role_v1.md":
            assert all(f"{answer} means" in prompt for answer in ("E", "S", "H"))
        else:
            assert " N" in prompt
            assert any(
                f"Answer {answer}" in prompt or f"{answer} means" in prompt for answer in ("E", "Y")
            )
        assert "SourceOccurrence" not in prompt
        assert "occurrence_id" not in prompt
        assert "source offset" not in prompt
        assert "Ledger" not in prompt
        assert "Anthropic" not in prompt
        assert "Amodei" not in prompt


def test_standing_fact_prompt_uses_source_choices_without_gold_leakage() -> None:
    prompt = STANDING_FACT_PROMPT.read_text()

    assert "The occurrence location distinguishes candidates whose names repeat." in prompt
    assert "select the complete phrase as a literal object" in prompt
    assert "select the smallest contiguous relation range" in prompt.casefold()
    assert "literal | <supplied oN[-oN] object selector>" in prompt
    assert "Northstar's policy mirrors Rivera's views on exports" in prompt
    assert "Anthropic" not in prompt
    assert "Amodei" not in prompt
    assert "Ledger" not in prompt
    assert "source offset" not in prompt
