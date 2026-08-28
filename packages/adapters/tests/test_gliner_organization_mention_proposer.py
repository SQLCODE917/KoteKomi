from __future__ import annotations

from collections.abc import Iterator

import pytest
from kotekomi_adapters.gliner_organization_mention_proposer import (
    GLINER_DEVICE,
    GLINER_LABEL,
    GLINER_MODEL_ID,
    GLINER_MODEL_REVISION,
    GLINER_THRESHOLD,
    GlinerOrganizationMentionProposer,
)
from kotekomi_application import OrganizationMentionProposalInput


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
    loads: list[tuple[str, str, str]] = []
    times = _clock(1.0, 1.125, 2.0, 2.01)

    proposer = GlinerOrganizationMentionProposer(
        model_loader=lambda model_id, revision, device: (
            loads.append((model_id, revision, device)) or model
        ),
        monotonic_clock=lambda: next(times),
    )
    result = proposer.propose(OrganizationMentionProposalInput("Anthropic"))

    assert loads == [(GLINER_MODEL_ID, GLINER_MODEL_REVISION, GLINER_DEVICE)]
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
        model_loader=lambda model_id, revision, device: model,
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
        GlinerOrganizationMentionProposer()
