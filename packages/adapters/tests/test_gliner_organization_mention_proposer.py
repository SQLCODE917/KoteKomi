from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from kotekomi_adapters.gliner_organization_mention_proposer import (
    GLINER_DEVICE,
    GLINER_LABEL,
    GLINER_MODEL_REVISION,
    GLINER_THRESHOLD,
    GlinerMentionProposer,
    GlinerOrganizationMentionProposer,
)
from kotekomi_application import (
    MentionProposalInput,
    OrganizationMentionProposalInput,
    SourceSegment,
)


class FakeGlinerModel:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = results
        self.calls: list[tuple[str, list[str], float]] = []

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        *,
        threshold: float,
    ) -> list[dict[str, object]]:
        self.calls.append((text, labels, threshold))
        return self.results


def _clock(*values: float) -> Iterator[float]:
    yield from values


def _version_028(package: str) -> str:
    del package
    return "0.2.28"


def _version_029(package: str) -> str:
    del package
    return "0.2.29"


def test_gliner_adapter_pins_identity_and_maps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_028,
    )
    model = FakeGlinerModel(
        [{"text": "Anthropic", "start": 0, "end": 9, "score": 0.91, "label": "organization"}]
    )
    loads: list[tuple[Path, str]] = []
    times = _clock(1.0, 1.125, 2.0, 2.01)

    proposer = GlinerOrganizationMentionProposer(
        model_directory=Path("/resources/gliner/model"),
        model_loader=lambda model_directory, device: (
            loads.append((model_directory, device)) or model
        ),
        monotonic_clock=lambda: next(times),
    )
    result = proposer.propose(OrganizationMentionProposalInput("Anthropic"))

    assert loads == [(Path("/resources/gliner/model"), GLINER_DEVICE)]
    assert model.calls == [("Anthropic", [GLINER_LABEL], GLINER_THRESHOLD)]
    assert result.model_revision == GLINER_MODEL_REVISION
    assert result.load_elapsed_milliseconds == 125
    assert result.inference_elapsed_milliseconds == 10
    assert result.proposals[0].text == "Anthropic"


def test_gliner_adapter_rejects_malformed_tool_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_028,
    )
    model = FakeGlinerModel([{"text": "Anthropic"}])
    times = _clock(1.0, 1.0, 2.0, 2.0)
    proposer = GlinerOrganizationMentionProposer(
        model_directory=Path("/resources/gliner/model"),
        model_loader=lambda model_directory, device: model,
        monotonic_clock=lambda: next(times),
    )

    with pytest.raises(ValueError, match="fields"):
        proposer.propose(OrganizationMentionProposalInput("Anthropic"))


def test_gliner_adapter_rejects_unpinned_package_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_029,
    )

    with pytest.raises(RuntimeError, match="must be 0.2.28"):
        GlinerOrganizationMentionProposer(model_directory=Path("/resources/gliner/model"))


def test_generic_gliner_adapter_uses_requested_labels_and_source_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_028,
    )
    model = FakeGlinerModel(
        [{"text": "Gemini", "start": 0, "end": 6, "score": 0.87, "label": "product"}]
    )
    loads: list[tuple[Path, str]] = []
    times = _clock(1.0, 1.125, 2.0, 2.01)
    proposer = GlinerMentionProposer(
        model_directory=Path("/resources/gliner/model"),
        model_loader=lambda model_directory, device: (
            loads.append((model_directory, device)) or model
        ),
        monotonic_clock=lambda: next(times),
    )
    proposal_input = MentionProposalInput(
        (SourceSegment("s1", 0, 14, "Gemini acted."),),
        ("organization", "product"),
    )

    result = proposer.propose(proposal_input)

    assert loads == [(Path("/resources/gliner/model"), GLINER_DEVICE)]
    assert model.calls == [("Gemini acted.", ["organization", "product"], GLINER_THRESHOLD)]
    assert result.configuration == (
        ("device", "cpu"),
        ("threshold", 0.5),
        ("tokenizer_id", "microsoft/deberta-v3-base"),
        ("tokenizer_revision", "8ccc9b6f36199bec6961081d44eb72fb3f7353f3"),
    )
    assert result.proposals[0].source_segment_label == "s1"
    assert result.proposals[0].type_hints == ("product",)


def test_default_gliner_loader_uses_only_the_managed_local_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_028,
    )
    model = FakeGlinerModel([])
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeGliner:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> FakeGlinerModel:
            calls.append((model_id, kwargs))
            return model

    module = ModuleType("gliner")
    module.GLiNER = FakeGliner  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gliner", module)
    model_directory = (tmp_path / "managed-model").resolve()
    proposer = GlinerMentionProposer(model_directory=model_directory)

    proposer.propose(
        MentionProposalInput(
            (SourceSegment("s1", 0, 10, "Anthropic."),),
            ("organization",),
        )
    )

    assert calls == [
        (
            str(model_directory),
            {"map_location": "cpu", "local_files_only": True},
        )
    ]


def test_default_loader_suppresses_only_the_pinned_deberta_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_028,
    )
    model = FakeGlinerModel([])
    model_directory = (tmp_path / "managed-model").resolve()
    _write_pinned_deberta_resource_shape(model_directory)
    transformers_logger = logging.getLogger("transformers.tokenization_utils_tokenizers")
    regex_warning = (
        f"The tokenizer you are loading from '{model_directory}' with an incorrect "
        "regex pattern: https://huggingface.co/mistralai/"
        "Mistral-Small-3.1-24B-Instruct-2503/discussions/84#69121093e8b480e709447d5e. "
        "This will lead to incorrect tokenization. You should set the "
        "`fix_mistral_regex=True` flag when loading this tokenizer to fix this issue."
    )

    class FakeGliner:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> FakeGlinerModel:
            del model_id, kwargs
            transformers_logger.warning(regex_warning)
            transformers_logger.warning("A different tokenizer warning remains visible.")
            return model

    module = ModuleType("gliner")
    module.GLiNER = FakeGliner  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gliner", module)

    with caplog.at_level(logging.WARNING, logger=transformers_logger.name):
        proposer = GlinerMentionProposer(model_directory=model_directory)
        proposer.propose(
            MentionProposalInput(
                (SourceSegment("s1", 0, 10, "Anthropic."),),
                ("organization",),
            )
        )

    messages = [record.getMessage() for record in caplog.records]
    assert regex_warning not in messages
    assert "A different tokenizer warning remains visible." in messages


def test_default_loader_does_not_hide_warning_for_a_different_tokenizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        "kotekomi_adapters.gliner_organization_mention_proposer.version",
        _version_028,
    )
    model = FakeGlinerModel([])
    model_directory = (tmp_path / "managed-model").resolve()
    _write_pinned_deberta_resource_shape(model_directory)
    (model_directory / "config.json").write_text(
        json.dumps({"model_type": "mistral"}),
        encoding="utf-8",
    )
    transformers_logger = logging.getLogger("transformers.tokenization_utils_tokenizers")
    regex_warning = (
        f"The tokenizer you are loading from '{model_directory}' with an incorrect "
        "regex pattern: https://huggingface.co/mistralai/"
        "Mistral-Small-3.1-24B-Instruct-2503/discussions/84."
    )

    class FakeGliner:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> FakeGlinerModel:
            del model_id, kwargs
            transformers_logger.warning(regex_warning)
            return model

    module = ModuleType("gliner")
    module.GLiNER = FakeGliner  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gliner", module)

    with caplog.at_level(logging.WARNING, logger=transformers_logger.name):
        proposer = GlinerMentionProposer(model_directory=model_directory)
        proposer.propose(
            MentionProposalInput(
                (SourceSegment("s1", 0, 10, "Anthropic."),),
                ("organization",),
            )
        )

    assert regex_warning in [record.getMessage() for record in caplog.records]


def _write_pinned_deberta_resource_shape(model_directory: Path) -> None:
    model_directory.mkdir()
    (model_directory / "gliner_config.json").write_text(
        json.dumps({"model_name": "microsoft/deberta-v3-base"}),
        encoding="utf-8",
    )
    (model_directory / "config.json").write_text(
        json.dumps({"model_type": "deberta-v2"}),
        encoding="utf-8",
    )
    (model_directory / "tokenizer_config.json").write_text(
        json.dumps({"vocab_type": "spm"}),
        encoding="utf-8",
    )
    (model_directory / "spm.model").write_bytes(b"pinned-sentencepiece-placeholder")
