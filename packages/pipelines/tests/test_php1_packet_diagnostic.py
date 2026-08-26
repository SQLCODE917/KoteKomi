import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _packet_cases() -> object:
    support_path = ROOT / "scripts/php1_diagnostic_support.py"
    support_spec = importlib.util.spec_from_file_location("php1_diagnostic_support", support_path)
    assert support_spec is not None
    assert support_spec.loader is not None
    support_module = importlib.util.module_from_spec(support_spec)
    sys.modules[support_spec.name] = support_module
    support_spec.loader.exec_module(support_module)
    packet_path = ROOT / "scripts/verify_php1_packet.py"
    packet_spec = importlib.util.spec_from_file_location("verify_php1_packet", packet_path)
    assert packet_spec is not None
    assert packet_spec.loader is not None
    packet_module = importlib.util.module_from_spec(packet_spec)
    packet_spec.loader.exec_module(packet_module)
    return packet_module.packet_cases()


def _support_module() -> object:
    support_path = ROOT / "scripts/php1_diagnostic_support.py"
    support_spec = importlib.util.spec_from_file_location(
        "php1_diagnostic_support_limit", support_path
    )
    assert support_spec is not None
    assert support_spec.loader is not None
    support_module = importlib.util.module_from_spec(support_spec)
    sys.modules[support_spec.name] = support_module
    support_spec.loader.exec_module(support_module)
    return support_module


def test_php1_packet_diagnostic_loads_each_unique_annotation_row() -> None:
    cases = _packet_cases()

    assert len(cases) == 50  # type: ignore[arg-type]
    assert len({case.case_id for case in cases}) == 50  # type: ignore[union-attr]
    assert {case.case_id for case in cases} >= {  # type: ignore[union-attr]
        "AD-01",
        "AI-01",
        "CS-01",
    }
    assert {case.metadata["provisional_eligibility"] for case in cases} >= {  # type: ignore[union-attr]
        "eligible",
        "control",
        "out_of_scope",
    }


def test_php1_segment_v2_prompt_uses_literal_source_segment_labels() -> None:
    prompt = (ROOT / "prompts" / "paragraph_hypothesis_segment_v2.md").read_text(encoding="utf-8")

    assert "SOURCE SEGMENT: sN" in prompt
    assert "claim: s1 |" in prompt
    assert "<sN>" not in prompt
    assert "pronoun" in prompt


def test_php1_eight_claim_evaluation_measures_only_eligible_claim_batches() -> None:
    support = _support_module()
    raw_output = "\n".join(
        f"claim: s1 | Org {index} | works with | Partner {index}" for index in range(1, 10)
    )

    assert support.evaluate_eight_claim_limit(raw_output, "eligible") == {
        "state": "measured",
        "excess_claim_line_count": 1,
    }
    assert support.evaluate_eight_claim_limit(raw_output, "control") == {
        "state": "not_applicable",
        "excess_claim_line_count": 0,
    }
    assert support.evaluate_eight_claim_limit("abstain: no relation", "eligible") == {
        "state": "not_measurable",
        "excess_claim_line_count": 0,
    }


def test_php1_diagnostic_separates_verifier_rejection_from_publication() -> None:
    support = _support_module()

    rejected = {"faithfulness_rejected_claim_count": 1}
    assert support.diagnostic_segment_status("succeeded", 0, rejected) == "faithfulness_rejected"
    assert support.diagnostic_segment_status("succeeded", 1, rejected) == "complete"
    assert support.diagnostic_case_status({"faithfulness_rejected", "abstained"}) == (
        "faithfulness_rejected"
    )
