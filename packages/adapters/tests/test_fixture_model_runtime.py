from pathlib import Path

import pytest
from kotekomi_adapters import FixtureModelRuntime

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)


def test_fixture_model_runtime_loads_proposals() -> None:
    runtime = FixtureModelRuntime(FIXTURE_PATH)

    proposals = runtime.propose_assertions(
        document_id="doc_aa67767133655af72fbcf0a8",
        source_id="src_aa67767133655af72fbcf0a8",
        document_text="fixture text",
    )

    assert runtime.model_name == "fixture-extraction-runtime"
    assert runtime.prompt_id == "propose_assertions"
    assert len(proposals) == 16
    assert proposals[0].record_type == "Organization"
    assert proposals[0].stable_label == "anthropic_ai_lab"
    assert proposals[0].record["id"] == "org_anthropic"


def test_fixture_model_output_covers_required_record_types() -> None:
    runtime = FixtureModelRuntime(FIXTURE_PATH)

    record_types = {
        proposal.record_type
        for proposal in runtime.propose_assertions(
            document_id="doc_aa67767133655af72fbcf0a8",
            source_id="src_aa67767133655af72fbcf0a8",
            document_text="fixture text",
        )
    }

    assert {
        "Actor",
        "Organization",
        "Event",
        "Assertion",
        "Outcome",
        "Relationship",
        "EvidenceSpan",
    }.issubset(record_types)


def test_fixture_model_runtime_rejects_malformed_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "bad_output.json"
    fixture_path.write_text('{"proposals": [{"record_type": "Assertion"}]}')

    with pytest.raises(ValueError, match=r"proposals\[0\]\.stable_label"):
        FixtureModelRuntime(fixture_path)


def test_fixture_model_runtime_rejects_invalid_domain_record(tmp_path: Path) -> None:
    fixture_path = tmp_path / "bad_record.json"
    fixture_path.write_text(
        """
        {
          "proposals": [
            {
              "record_type": "Assertion",
              "stable_label": "missing_required_fields",
              "record": {"id": "ast_missing_required_fields"},
              "evidence": {
                "source_id": "src_article_a",
                "document_id": "doc_article_a",
                "exact_text": "text"
              }
            }
          ]
        }
        """
    )

    with pytest.raises(ValueError):
        FixtureModelRuntime(fixture_path)


def test_fixture_model_runtime_rejects_unsupported_record_type(tmp_path: Path) -> None:
    fixture_path = tmp_path / "unsupported_record_type.json"
    fixture_path.write_text(
        """
        {
          "proposals": [
            {
              "record_type": "Place",
              "stable_label": "washington",
              "record": {"id": "plc_washington", "name": "Washington"},
              "evidence": {
                "source_id": "src_article_a",
                "document_id": "doc_article_a",
                "exact_text": "text"
              }
            }
          ]
        }
        """
    )

    with pytest.raises(ValueError, match="Unsupported ModelProposal record_type: Place"):
        FixtureModelRuntime(fixture_path)
