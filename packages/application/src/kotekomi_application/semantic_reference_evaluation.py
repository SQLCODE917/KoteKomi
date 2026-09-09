"""Frozen-case evaluation for source-span coreference proposers."""

from __future__ import annotations

from dataclasses import dataclass

from kotekomi_domain import ModelRunStatus

from kotekomi_application.semantic_reference_challenge_model_output import (
    SemanticReferenceChallengeSelection,
)
from kotekomi_application.semantic_references import (
    CoreferenceAntecedentInput,
    CoreferenceInput,
    CoreferenceProposerPort,
    CoreferenceSpan,
    CoreferenceTokenizer,
    SemanticReferenceChallengeExecution,
    SemanticReferenceChallengeInput,
    SemanticReferenceResult,
    SemanticReferenceStatus,
    resolve_semantic_reference,
)


class _SpecialistCandidateProjection:
    """Expose the specialist candidate set without pretending it is semantic authority."""

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution:
        selection = (
            SemanticReferenceChallengeSelection(
                request.antecedent_candidates[0].id,
                False,
                "The bake-off projects the sole specialist candidate for measurement.",
            )
            if len(request.antecedent_candidates) == 1
            else SemanticReferenceChallengeSelection(
                None,
                True,
                "The bake-off projects every specialist candidate for measurement.",
            )
        )
        return SemanticReferenceChallengeExecution(
            selection=selection,
            extraction_task_id="ext_evaluation_specialist_projection",
            model_run_id="mrn_evaluation_specialist_projection",
            model_status=ModelRunStatus.SUCCEEDED,
            producer_id="deterministic_specialist_candidate_projection",
            model_visible_task=b"specialist candidate-set measurement",
            raw_output_sha256=None,
        )


@dataclass(frozen=True)
class CoreferenceGoldSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("A Coreference Gold span requires a valid half-open range.")


@dataclass(frozen=True)
class CoreferenceGoldCase:
    case_id: str
    source_segment_id: str
    source_text: str
    target: CoreferenceGoldSpan
    antecedent_candidates: tuple[CoreferenceGoldSpan, ...]
    expected_antecedents: tuple[CoreferenceGoldSpan, ...]

    def __post_init__(self) -> None:
        if not self.case_id or not self.source_segment_id or not self.source_text:
            raise ValueError("A Coreference Gold case requires complete source identity.")
        for span in (self.target, *self.antecedent_candidates, *self.expected_antecedents):
            if span.end > len(self.source_text):
                raise ValueError("A Coreference Gold span lies outside its source text.")
        if tuple(sorted(set(self.expected_antecedents), key=lambda x: (x.start, x.end))) != (
            self.expected_antecedents
        ):
            raise ValueError("Expected antecedents must be ordered and distinct.")
        if tuple(sorted(set(self.antecedent_candidates), key=lambda x: (x.start, x.end))) != (
            self.antecedent_candidates
        ):
            raise ValueError("Antecedent candidates must be ordered and distinct.")
        if not set(self.expected_antecedents).issubset(self.antecedent_candidates):
            raise ValueError("Expected antecedents must be eligible source candidates.")


@dataclass(frozen=True)
class CoreferenceCaseEvaluation:
    case_id: str
    source_text: str
    target_text: str
    expected_antecedents: tuple[str, ...]
    actual_antecedents: tuple[str, ...]
    result: SemanticReferenceResult | None
    error: str | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.error is None):
            raise ValueError("A Coreference evaluation requires exactly one result or error.")


@dataclass(frozen=True)
class CoreferenceBakeoffReport:
    model_id: str
    case_count: int
    exact_case_count: int
    wrong_resolution_count: int
    true_positive_count: int
    false_positive_count: int
    false_negative_count: int
    invalid_output_count: int
    resolved_count: int
    ambiguous_count: int
    unresolved_count: int
    elapsed_milliseconds: int
    evaluations: tuple[CoreferenceCaseEvaluation, ...]

    @property
    def precision(self) -> float:
        denominator = self.true_positive_count + self.false_positive_count
        return self.true_positive_count / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive_count + self.false_negative_count
        return self.true_positive_count / denominator if denominator else 0.0

    @property
    def exact_span_validity(self) -> float:
        return (self.case_count - self.invalid_output_count) / self.case_count

    @property
    def zero_wrong_resolution_gate_passed(self) -> bool:
        return (
            self.model_id == "biu-nlp/f-coref"
            and self.case_count > 0
            and self.resolved_count > 0
            and self.wrong_resolution_count == 0
            and self.invalid_output_count == 0
        )


def evaluate_coreference_proposer(
    *,
    cases: tuple[CoreferenceGoldCase, ...],
    proposer: CoreferenceProposerPort,
    tokenizer: CoreferenceTokenizer,
) -> CoreferenceBakeoffReport:
    """Run one proposer and retain exact data-in/data-out for every frozen case."""
    if not cases:
        raise ValueError("A Coreference bake-off requires at least one Gold case.")
    if len({item.case_id for item in cases}) != len(cases):
        raise ValueError("Coreference Gold case IDs must be distinct.")
    evaluations: list[CoreferenceCaseEvaluation] = []
    true_positives = false_positives = false_negatives = invalid = exact = wrong = 0
    resolved = ambiguous = unresolved = elapsed = 0
    model_ids: set[str] = set()
    for case in cases:
        expected_ranges = {(item.start, item.end) for item in case.expected_antecedents}
        expected_text = tuple(
            case.source_text[item.start : item.end] for item in case.expected_antecedents
        )
        try:
            result = resolve_semantic_reference(
                CoreferenceInput(
                    case.source_segment_id,
                    case.source_text,
                    case.target.start,
                    case.target.end,
                    tuple(
                        CoreferenceAntecedentInput(
                            source_candidate_id=(f"{case.case_id}:candidate:{index}"),
                            start=span.start,
                            end=span.end,
                        )
                        for index, span in enumerate(case.antecedent_candidates, start=1)
                    ),
                ),
                proposer,
                tokenizer,
                _SpecialistCandidateProjection(),
            )
        except (OSError, RuntimeError, ValueError) as error:
            invalid += 1
            false_negatives += len(expected_ranges)
            evaluations.append(
                CoreferenceCaseEvaluation(
                    case.case_id,
                    case.source_text,
                    case.source_text[case.target.start : case.target.end],
                    expected_text,
                    (),
                    None,
                    f"{type(error).__name__}: {error}",
                )
            )
            continue
        model_ids.add(result.observation.model_id)
        elapsed += result.observation.elapsed_milliseconds
        spans = _spans_by_id(result)
        actual = tuple(spans[item] for item in result.decision.antecedent_span_ids)
        actual_ranges = {(item.start, item.end) for item in actual}
        actual_text = tuple(item.text for item in actual)
        true_positives += len(expected_ranges & actual_ranges)
        false_positives += len(actual_ranges - expected_ranges)
        false_negatives += len(expected_ranges - actual_ranges)
        if actual_ranges == expected_ranges:
            exact += 1
        if actual_ranges - expected_ranges:
            wrong += 1
        if result.decision.status is SemanticReferenceStatus.RESOLVED:
            resolved += 1
        elif result.decision.status is SemanticReferenceStatus.AMBIGUOUS:
            ambiguous += 1
        else:
            unresolved += 1
        evaluations.append(
            CoreferenceCaseEvaluation(
                case.case_id,
                case.source_text,
                case.source_text[case.target.start : case.target.end],
                expected_text,
                actual_text,
                result,
                None,
            )
        )
    model_id = next(iter(model_ids)) if len(model_ids) == 1 else "unavailable_or_mixed"
    return CoreferenceBakeoffReport(
        model_id,
        len(cases),
        exact,
        wrong,
        true_positives,
        false_positives,
        false_negatives,
        invalid,
        resolved,
        ambiguous,
        unresolved,
        elapsed,
        tuple(evaluations),
    )


def _spans_by_id(result: SemanticReferenceResult) -> dict[str, CoreferenceSpan]:
    return {item.span.id: item.span for item in result.observation.antecedent_candidates}
