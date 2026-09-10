from pathlib import Path

import pytest
from kotekomi_adapters.deberta_nli import DebertaNliAdapter, require_untruncated_input
from kotekomi_application import NaturalLanguageInferenceInput, NliLabel


def test_deberta_nli_maps_fixed_label_order_without_deciding_admission(tmp_path: Path) -> None:
    adapter = DebertaNliAdapter(
        model_directory=tmp_path.resolve(),
        resource_identity="sha256:fixture",
        predictor=lambda premise, hypothesis: (-3.0, 4.0, -1.0),
    )

    result = adapter.classify(
        NaturalLanguageInferenceInput(
            premise="Amodei criticized Trump.",
            hypothesis="Amodei criticized Trump.",
        )
    )

    assert result.selected_label is NliLabel.ENTAILMENT
    assert result.entailment_score > 0.99
    assert result.resource_identity == "sha256:fixture"


def test_deberta_nli_rejects_non_finite_tool_output(tmp_path: Path) -> None:
    adapter = DebertaNliAdapter(
        model_directory=tmp_path.resolve(),
        resource_identity="sha256:fixture",
        predictor=lambda premise, hypothesis: (0.0, float("nan"), 0.0),
    )

    with pytest.raises(ValueError, match="finite"):
        adapter.classify(NaturalLanguageInferenceInput(premise="A", hypothesis="B"))


class _InputIds:
    def __init__(self, token_count: int) -> None:
        self.shape = (1, token_count)


def test_deberta_nli_rejects_input_that_would_require_silent_truncation() -> None:
    with pytest.raises(ValueError, match="exceed the model limit"):
        require_untruncated_input({"input_ids": _InputIds(513)}, maximum_tokens=512)

    require_untruncated_input({"input_ids": _InputIds(512)}, maximum_tokens=512)
