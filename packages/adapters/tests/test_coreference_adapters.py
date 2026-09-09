import sys
from pathlib import Path

import pytest
from kotekomi_adapters.correlated_worker_transport import CorrelatedWorkerExchange
from kotekomi_adapters.fcoref import FCorefAdapter, FCorefConfig
from kotekomi_application import CoreferenceInput


class _BlockedTransport:
    def request(self, payload: dict[str, object]) -> CorrelatedWorkerExchange:
        del payload
        response: dict[str, object] = {
            "schema_version": "fcoref_failure_v1",
            "status": "blocked",
            "failure": "resources_unavailable",
            "diagnostics": ["Pinned resources are absent."],
        }
        return CorrelatedWorkerExchange("rwr_" + "1" * 32, response, b"blocked")

    def discard(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_fcoref_preserves_character_ranges_and_model_identity(tmp_path: Path) -> None:
    source_text = "Trump said Amodei criticized him."
    target = source_text.index("him")
    trump = source_text.index("Trump")

    def predict(text: str) -> tuple[tuple[tuple[int, int], ...], ...]:
        assert text == source_text
        return (((trump, trump + 5), (target, target + 3)),)

    adapter = FCorefAdapter(
        FCorefConfig(
            python_executable=Path(sys.executable).resolve(),
            worker_script=Path(__file__).resolve(),
            model_directory=tmp_path.resolve(),
            resource_identity="fcoref-resource",
        ),
        predictor=predict,
    )

    result = adapter.propose(CoreferenceInput("seg_fixture", source_text, target, target + 3))

    assert result.model_id == "biu-nlp/f-coref"
    assert result.clusters[0][1].start == target


def test_fcoref_preserves_typed_worker_failure_diagnostics(tmp_path: Path) -> None:
    adapter = FCorefAdapter(
        FCorefConfig(
            python_executable=Path(sys.executable).resolve(),
            worker_script=Path(__file__).resolve(),
            model_directory=tmp_path.resolve(),
            resource_identity="fcoref-resource",
        ),
        transport=_BlockedTransport(),
    )

    with pytest.raises(
        RuntimeError,
        match="resources_unavailable.*Pinned resources are absent",
    ):
        adapter.count_tokens(b"A bounded source segment.")
