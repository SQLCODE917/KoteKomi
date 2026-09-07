from __future__ import annotations

from dataclasses import dataclass

from kotekomi_application import (
    CoreferenceBakeoffReport,
    CoreferenceExecution,
    CoreferenceGoldCase,
    CoreferenceGoldSpan,
    CoreferenceInput,
    CoreferenceSpanProposal,
    evaluate_coreference_proposer,
)


class _Tokenizer:
    tokenizer_id = "fixture-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


@dataclass(frozen=True)
class _Proposer:
    model_id: str

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        antecedent_end = request.source_text.index(" said")
        return CoreferenceExecution(
            self.model_id,
            "v1",
            "fixture-resource",
            (
                (
                    CoreferenceSpanProposal(0, antecedent_end),
                    CoreferenceSpanProposal(request.target_start, request.target_end),
                ),
            ),
            7,
            b'{"clusters":[[[0,5],[29,32]]]}',
        )


def _report(model_id: str = "biu-nlp/f-coref") -> CoreferenceBakeoffReport:
    text = "Trump said Amodei criticized him."
    target = text.index("him")
    return evaluate_coreference_proposer(
        cases=(
            CoreferenceGoldCase(
                "visible-trump",
                "seg_fixture",
                text,
                CoreferenceGoldSpan(target, target + 3),
                (CoreferenceGoldSpan(0, 5),),
                (CoreferenceGoldSpan(0, 5),),
            ),
        ),
        proposer=_Proposer(model_id),
        tokenizer=_Tokenizer(),
    )


def test_bakeoff_reports_exact_metrics_and_data_in_data_out() -> None:
    report = _report()

    assert report.precision == report.recall == report.exact_span_validity == 1.0
    assert report.exact_case_count == report.resolved_count == 1
    assert report.wrong_resolution_count == report.invalid_output_count == 0
    assert report.zero_wrong_resolution_gate_passed is True
    assert report.evaluations[0].source_text == "Trump said Amodei criticized him."
    assert report.evaluations[0].expected_antecedents == ("Trump",)
    assert report.evaluations[0].actual_antecedents == ("Trump",)
    assert report.evaluations[0].result is not None
    assert (
        report.evaluations[0].result.trace.input["source_text"] == report.evaluations[0].source_text
    )


def test_only_fcoref_can_pass_the_production_eligibility_gate() -> None:
    assert _report("sapienzanlp/maverick-mes-ontonotes").zero_wrong_resolution_gate_passed is False
