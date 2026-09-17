"""Gold evaluation for the source-grounded proposition-scope experiment."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_application import (
    PropositionFragmentCandidate,
    PropositionFragmentReason,
    SourceGroundedPropositionScope,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.event_entity_connection_stage_local import ConnectionGoldEntity

_SHA256 = r"^[a-f0-9]{64}$"


class PropositionGoldReviewStatus(StrEnum):
    """Human-review state of the proposition Gold catalog."""

    PROPOSED = "proposed"
    APPROVED = "approved"


class PropositionGoldFragmentRequirement(StrEnum):
    """Evaluation-only source meaning carried by one exact Gold fragment."""

    CORE_EVENT = "core_event"
    ATTRIBUTION = "attribution"
    NEGATION = "negation"
    MODALITY = "modality"
    PURPOSE = "purpose"
    COMPARISON = "comparison"
    TEMPORAL = "temporal"


class PropositionGoldFragment(BaseModel):
    """One reviewed exact source range required by an Event proposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fragment_id: Annotated[str, Field(pattern=r"^PGF-TGE-[0-9]{3}-[0-9]{2}$")]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    requirements: tuple[PropositionGoldFragmentRequirement, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Proposition Gold fragment range does not match its text.")
        if self.requirements != tuple(sorted(set(self.requirements), key=lambda item: item.value)):
            raise ValueError("Proposition Gold requirements must be ordered and distinct.")
        if not self.requirements:
            raise ValueError("Proposition Gold fragment requires one meaning classification.")
        return self


class PropositionGoldEvent(BaseModel):
    """Reviewed complete source meaning for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    phase: Literal["development", "validation"]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    event_meaning: Annotated[str, Field(min_length=1)]
    fragments: tuple[PropositionGoldFragment, ...]
    review_rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Proposition Gold SourceSegment digest does not match its text.")
        if not self.fragments:
            raise ValueError("Proposition Gold Event requires one exact fragment.")
        if tuple(sorted(self.fragments, key=lambda item: (item.start, item.end))) != self.fragments:
            raise ValueError("Proposition Gold fragments must use source order.")
        if len({item.fragment_id for item in self.fragments}) != len(self.fragments):
            raise ValueError("Proposition Gold Event repeats one fragment ID.")
        if any(
            prior.end > current.start
            for prior, current in zip(self.fragments, self.fragments[1:], strict=False)
        ):
            raise ValueError("Proposition Gold fragments must not overlap.")
        if any(
            item.end > len(self.source_text) or self.source_text[item.start : item.end] != item.text
            for item in self.fragments
        ):
            raise ValueError("Proposition Gold fragment does not replay its SourceSegment.")
        if not any(
            PropositionGoldFragmentRequirement.CORE_EVENT in item.requirements
            for item in self.fragments
        ):
            raise ValueError("Proposition Gold Event requires a core Event fragment.")
        return self


class PropositionGoldCatalog(BaseModel):
    """Human-reviewed 20/20 experiment oracle."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["source_grounded_proposition_gold_v1"] = (
        "source_grounded_proposition_gold_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    review_status: PropositionGoldReviewStatus
    connection_gold_path: Annotated[str, Field(min_length=1)]
    connection_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    trigger_gold_path: Annotated[str, Field(min_length=1)]
    trigger_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    events: tuple[PropositionGoldEvent, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.events) != 40:
            raise ValueError("Proposition Gold requires exactly forty Events.")
        if len({item.event_id for item in self.events}) != len(self.events):
            raise ValueError("Proposition Gold repeats one Event ID.")
        phases = [item.phase for item in self.events]
        if phases.count("development") != 20 or phases.count("validation") != 20:
            raise ValueError("Proposition Gold requires a 20/20 phase split.")
        if tuple(sorted(self.events, key=lambda item: (item.phase, item.event_id))) != self.events:
            raise ValueError("Proposition Gold Events must use canonical phase and ID order.")
        return self


class PropositionScopePreflight(BaseModel):
    """Candidate-generation coverage before any model invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: str
    candidate_ids: tuple[str, ...]
    gold_compatible_candidate_ids: tuple[str, ...]
    gold_overreaching_candidate_ids: tuple[str, ...]
    blocking_candidate_ids: tuple[str, ...]
    covered_fragment_ids: tuple[str, ...]
    missing_fragment_ids: tuple[str, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Proposition preflight candidates", self.candidate_ids)
        _ordered_distinct(
            "Proposition preflight Gold-compatible candidates",
            self.gold_compatible_candidate_ids,
        )
        _ordered_distinct(
            "Proposition preflight Gold-overreaching candidates",
            self.gold_overreaching_candidate_ids,
        )
        _ordered_distinct(
            "Proposition preflight blocking candidates",
            self.blocking_candidate_ids,
        )
        _ordered_distinct("Proposition preflight covered fragments", self.covered_fragment_ids)
        _ordered_distinct("Proposition preflight missing fragments", self.missing_fragment_ids)
        compatible = set(self.gold_compatible_candidate_ids)
        overreaching = set(self.gold_overreaching_candidate_ids)
        if compatible & overreaching or compatible | overreaching != set(self.candidate_ids):
            raise ValueError("Proposition preflight Gold compatibility must partition candidates.")
        if not set(self.blocking_candidate_ids) <= overreaching:
            raise ValueError("Proposition preflight blockers must be Gold-overreaching candidates.")
        if set(self.covered_fragment_ids) & set(self.missing_fragment_ids):
            raise ValueError("Proposition preflight fragment results overlap.")
        if self.passed != (not self.missing_fragment_ids and not self.blocking_candidate_ids):
            raise ValueError("Proposition preflight status drifted from exact representability.")
        return self


class PropositionScopeCaseEvaluation(BaseModel):
    """Exact data-in/data-out comparison for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: str
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    gold_fragment_ids: tuple[str, ...]
    selected_fragment_ids: tuple[str, ...]
    exact_fragment_match_count: Annotated[int, Field(ge=0)]
    required_character_count: Annotated[int, Field(ge=0)]
    selected_character_count: Annotated[int, Field(ge=0)]
    true_positive_character_count: Annotated[int, Field(ge=0)]
    false_positive_character_count: Annotated[int, Field(ge=0)]
    false_negative_character_count: Annotated[int, Field(ge=0)]
    qualification_fragment_count: Annotated[int, Field(ge=0)]
    retained_qualification_fragment_count: Annotated[int, Field(ge=0)]
    expected_entity_count: Annotated[int, Field(ge=0)]
    retained_entity_count: Annotated[int, Field(ge=0)]
    unresolved_candidate_count: Annotated[int, Field(ge=0)]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.true_positive_character_count + self.false_negative_character_count != (
            self.required_character_count
        ):
            raise ValueError("Proposition evaluation required-character counts drifted.")
        if self.true_positive_character_count + self.false_positive_character_count != (
            self.selected_character_count
        ):
            raise ValueError("Proposition evaluation selected-character counts drifted.")
        if self.retained_qualification_fragment_count > self.qualification_fragment_count:
            raise ValueError("Proposition evaluation over-counted qualification fragments.")
        if self.retained_entity_count > self.expected_entity_count:
            raise ValueError("Proposition evaluation over-counted expected entities.")
        expected_passed = (
            self.false_positive_character_count == 0
            and self.false_negative_character_count == 0
            and self.retained_qualification_fragment_count == self.qualification_fragment_count
            and self.retained_entity_count == self.expected_entity_count
            and self.unresolved_candidate_count == 0
        )
        if self.passed != expected_passed:
            raise ValueError("Proposition case status drifted from its exact evaluation.")
        return self


class PropositionScopeMetrics(BaseModel):
    """Aggregate exact-character and semantic-preservation metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    true_positive_character_count: Annotated[int, Field(ge=0)]
    false_positive_character_count: Annotated[int, Field(ge=0)]
    false_negative_character_count: Annotated[int, Field(ge=0)]
    precision: Annotated[float, Field(ge=0, le=1)]
    recall: Annotated[float, Field(ge=0, le=1)]
    f1: Annotated[float, Field(ge=0, le=1)]
    qualification_fragment_count: Annotated[int, Field(ge=0)]
    retained_qualification_fragment_count: Annotated[int, Field(ge=0)]
    qualification_recall: Annotated[float, Field(ge=0, le=1)]
    expected_entity_count: Annotated[int, Field(ge=0)]
    retained_entity_count: Annotated[int, Field(ge=0)]
    entity_recall: Annotated[float, Field(ge=0, le=1)]


class PropositionScopePhaseReport(BaseModel):
    """Complete typed result for one experiment phase and repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["source_grounded_proposition_scope_report_v1"] = (
        "source_grounded_proposition_scope_report_v1"
    )
    catalog_id: str
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    phase: Literal["development", "validation"]
    repetition: Annotated[int, Field(ge=1)]
    cases: tuple[PropositionScopeCaseEvaluation, ...]
    metrics: PropositionScopeMetrics
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != 20:
            raise ValueError("Proposition phase report requires twenty Events.")
        if tuple(sorted(self.cases, key=lambda item: item.event_id)) != self.cases:
            raise ValueError("Proposition phase report Events must use canonical order.")
        expected_metrics = _aggregate_metrics(self.cases)
        if self.metrics != expected_metrics:
            raise ValueError("Proposition phase metrics drifted from case evidence.")
        expected_passed = all(item.passed for item in self.cases)
        if self.passed != expected_passed:
            raise ValueError("Proposition phase status drifted from case evidence.")
        expected_fingerprint = proposition_scope_result_fingerprint(
            catalog_sha256=self.catalog_sha256,
            phase=self.phase,
            cases=self.cases,
        )
        if self.result_fingerprint != expected_fingerprint:
            raise ValueError("Proposition phase fingerprint drifted from case evidence.")
        return self


def load_proposition_gold_catalog(path: Path, *, repository_root: Path) -> PropositionGoldCatalog:
    """Load Gold and prove its parent files and reviewed Event inventory."""
    payload = path.read_bytes()
    catalog = PropositionGoldCatalog.model_validate_json(payload)
    connection_path = repository_root / catalog.connection_gold_path
    trigger_path = repository_root / catalog.trigger_gold_path
    if hashlib.sha256(connection_path.read_bytes()).hexdigest() != catalog.connection_gold_sha256:
        raise ValueError("Proposition Gold Connection Gold digest drifted.")
    if hashlib.sha256(trigger_path.read_bytes()).hexdigest() != catalog.trigger_gold_sha256:
        raise ValueError("Proposition Gold Trigger Gold digest drifted.")
    connection = json.loads(connection_path.read_bytes())
    parent_by_id = {item["event_id"]: item for item in connection["events"]}
    if set(parent_by_id) != {item.event_id for item in catalog.events}:
        raise ValueError("Proposition Gold Event inventory drifted from Connection Gold.")
    for event in catalog.events:
        parent = parent_by_id[event.event_id]
        if (
            parent["phase"] != event.phase
            or parent["source_text_sha256"] != event.source_text_sha256
            or parent["event_meaning"] != event.event_meaning
        ):
            raise ValueError("Proposition Gold Event binding drifted from Connection Gold.")
    return catalog


def evaluate_proposition_candidate_preflight(
    gold: PropositionGoldEvent,
    candidates: tuple[PropositionFragmentCandidate, ...],
) -> PropositionScopePreflight:
    """Prove whole-candidate decisions can reproduce every meaningful Gold character."""
    gold_positions = _meaningful_positions(
        gold.source_text,
        tuple((item.start, item.end) for item in gold.fragments),
    )
    compatible = tuple(
        item
        for item in candidates
        if _meaningful_positions(
            gold.source_text,
            ((item.start, item.end),),
        )
        <= gold_positions
    )
    compatible_ids = {item.id for item in compatible}
    overreaching = tuple(item for item in candidates if item.id not in compatible_ids)
    blocking = tuple(
        item for item in overreaching if PropositionFragmentReason.EVENT_EXPRESSION in item.reasons
    )
    compatible_positions = _meaningful_positions(
        gold.source_text,
        tuple((item.start, item.end) for item in compatible),
    )
    covered = tuple(
        item.fragment_id
        for item in gold.fragments
        if _meaningful_positions(gold.source_text, ((item.start, item.end),))
        <= compatible_positions
    )
    missing = tuple(
        item.fragment_id for item in gold.fragments if item.fragment_id not in set(covered)
    )
    return PropositionScopePreflight(
        event_id=gold.event_id,
        candidate_ids=tuple(sorted(item.id for item in candidates)),
        gold_compatible_candidate_ids=tuple(sorted(item.id for item in compatible)),
        gold_overreaching_candidate_ids=tuple(sorted(item.id for item in overreaching)),
        blocking_candidate_ids=tuple(sorted(item.id for item in blocking)),
        covered_fragment_ids=tuple(sorted(covered)),
        missing_fragment_ids=tuple(sorted(missing)),
        passed=not missing and not blocking,
    )


def evaluate_proposition_scope_case(
    *,
    gold: PropositionGoldEvent,
    scope: SourceGroundedPropositionScope,
    expected_entities: tuple[ConnectionGoldEntity, ...],
) -> PropositionScopeCaseEvaluation:
    """Compare selected exact characters with Gold without normalized paraphrases."""
    if scope.source_text_sha256 != gold.source_text_sha256 or any(
        gold.source_text[item.start : item.end] != item.text for item in scope.fragments
    ):
        raise ValueError("Proposition scope does not replay its Gold SourceSegment.")
    gold_positions = _meaningful_positions(
        gold.source_text,
        tuple((item.start, item.end) for item in gold.fragments),
    )
    selected_positions = _meaningful_positions(
        gold.source_text,
        tuple((item.start, item.end) for item in scope.fragments),
    )
    true_positive = gold_positions & selected_positions
    false_positive = selected_positions - gold_positions
    false_negative = gold_positions - selected_positions
    selected_ranges = {(item.start, item.end, item.text) for item in scope.fragments}
    exact_count = sum(
        (item.start, item.end, item.text) in selected_ranges for item in gold.fragments
    )
    qualification = tuple(
        item
        for item in gold.fragments
        if any(
            requirement is not PropositionGoldFragmentRequirement.CORE_EVENT
            for requirement in item.requirements
        )
    )
    retained_qualification = sum(
        _meaningful_positions(gold.source_text, ((item.start, item.end),)) <= selected_positions
        for item in qualification
    )
    retained_entities = sum(
        _expected_entity_retained(gold.source_text, selected_positions, item)
        for item in expected_entities
    )
    passed = (
        not false_positive
        and not false_negative
        and retained_qualification == len(qualification)
        and retained_entities == len(expected_entities)
        and not scope.unresolved_candidate_ids
    )
    return PropositionScopeCaseEvaluation(
        event_id=gold.event_id,
        source_text_sha256=gold.source_text_sha256,
        gold_fragment_ids=tuple(item.fragment_id for item in gold.fragments),
        selected_fragment_ids=tuple(item.id for item in scope.fragments),
        exact_fragment_match_count=exact_count,
        required_character_count=len(gold_positions),
        selected_character_count=len(selected_positions),
        true_positive_character_count=len(true_positive),
        false_positive_character_count=len(false_positive),
        false_negative_character_count=len(false_negative),
        qualification_fragment_count=len(qualification),
        retained_qualification_fragment_count=retained_qualification,
        expected_entity_count=len(expected_entities),
        retained_entity_count=retained_entities,
        unresolved_candidate_count=len(scope.unresolved_candidate_ids),
        passed=passed,
    )


def build_proposition_scope_phase_report(
    *,
    catalog: PropositionGoldCatalog,
    catalog_sha256: str,
    phase: Literal["development", "validation"],
    repetition: int,
    cases: tuple[PropositionScopeCaseEvaluation, ...],
) -> PropositionScopePhaseReport:
    """Build one report whose aggregates are derived from typed case evidence."""
    ordered = tuple(sorted(cases, key=lambda item: item.event_id))
    return PropositionScopePhaseReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        phase=phase,
        repetition=repetition,
        cases=ordered,
        metrics=_aggregate_metrics(ordered),
        result_fingerprint=proposition_scope_result_fingerprint(
            catalog_sha256=catalog_sha256,
            phase=phase,
            cases=ordered,
        ),
        passed=all(item.passed for item in ordered),
    )


def proposition_scope_result_fingerprint(
    *,
    catalog_sha256: str,
    phase: str,
    cases: tuple[PropositionScopeCaseEvaluation, ...],
) -> str:
    payload = {
        "catalog_sha256": catalog_sha256,
        "cases": [item.model_dump(mode="json") for item in cases],
        "phase": phase,
        "scoring_policy": "source_grounded_proposition_character_exact_v1",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def render_proposition_gold_review(catalog: PropositionGoldCatalog) -> str:
    """Render compact human review without changing the structured oracle."""
    lines = [
        "# Source-Grounded Proposition Scope Gold Review",
        "",
        f"Review status: `{catalog.review_status.value}`",
        "",
        "## Review contract",
        "",
        (
            "Gold records the source meaning required at this boundary, not the current "
            "model's convenience, a final knowledge graph, or unqualified world truth."
        ),
        "",
        (
            "KoteKomi supplies the authoritative SourceSegment, one exact Event "
            "expression, and one exact Fragment Candidate."
        ),
        "",
        (
            "Stanza supplies tokenization, part-of-speech, lemma, and dependency evidence; "
            "it does not decide semantic truth, proposition scope, or chronology."
        ),
        "",
        (
            "QANom proposes whether a noun is eventive; it does not decide participants, "
            "time, truth, or proposition scope."
        ),
        "",
        (
            "GLiNER proposes entity spans and type hints, ReFinED proposes external "
            "identity, and F-Coref proposes antecedent links; none of them decides "
            "proposition scope."
        ),
        "",
        (
            "Qwen2.5 receives the complete SourceSegment, one marked Event expression, "
            "and one marked Fragment Candidate, then answers only `Y`, `N`, or `U` about "
            "semantic membership."
        ),
        "",
        (
            "Qwen2.5 does not construct KoteKomi identifiers, source offsets, Domain Core "
            "records, semantic roles, Event-to-Event edges, or a timeline."
        ),
        "",
        (
            "KoteKomi validates source characters, maps each answer to its supplied "
            "candidate, constructs records, and preserves data-in/data-out traces."
        ),
        "",
        "Human review defines Gold and authorizes any later accepted Ledger state.",
        "",
        (
            "A candidate-generation gap and a semantic-judgment error are different "
            "failures and must remain separately measurable."
        ),
        "",
        (
            "Gold can require an exact fragment-membership decision only when "
            "deterministic candidates can represent that fragment."
        ),
        "",
        (
            "Gold does not require normalized semantic roles, Event-to-Event edges, "
            "external world knowledge, or temporal ordering beyond this experiment's "
            "boundary."
        ),
        "",
        (
            "A temporal phrase belongs to an Event proposition only when the "
            "SourceSegment's grammar binds that phrase to the Event."
        ),
        "",
        (
            "Nested Event mentions remain distinct: an outer Event can include a nested "
            "Event expression without proving a date, role, or independent occurrence "
            "that the Source does not establish."
        ),
        "",
    ]
    for event in catalog.events:
        lines.extend(
            (
                f"## {event.event_id} — {event.phase}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {event.source_text}",
                "",
                f"Expected meaning: {event.event_meaning}",
                "",
                "Required exact fragments:",
                "",
            )
        )
        for fragment in event.fragments:
            requirements = ", ".join(item.value for item in fragment.requirements)
            lines.append(f"- `{fragment.text}` — {requirements} — `{fragment.fragment_id}`")
        lines.extend(("", f"Review rationale: {event.review_rationale}", ""))
    return "\n".join(lines).rstrip() + "\n"


def _meaningful_positions(
    source_text: str,
    ranges: tuple[tuple[int, int], ...],
) -> set[int]:
    positions: set[int] = set()
    for start, end in ranges:
        if start < 0 or end > len(source_text) or start >= end:
            raise ValueError("Proposition evaluation range leaves its SourceSegment.")
        positions.update(index for index in range(start, end) if not source_text[index].isspace())
    return positions


def _expected_entity_retained(
    source_text: str,
    selected_positions: set[int],
    entity: ConnectionGoldEntity,
) -> bool:
    return any(
        _meaningful_positions(source_text, ((item.start, item.end),)) <= selected_positions
        for item in entity.accepted_source_occurrences
    )


def _aggregate_metrics(
    cases: tuple[PropositionScopeCaseEvaluation, ...],
) -> PropositionScopeMetrics:
    tp = sum(item.true_positive_character_count for item in cases)
    fp = sum(item.false_positive_character_count for item in cases)
    fn = sum(item.false_negative_character_count for item in cases)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    qualification = sum(item.qualification_fragment_count for item in cases)
    retained_qualification = sum(item.retained_qualification_fragment_count for item in cases)
    entities = sum(item.expected_entity_count for item in cases)
    retained_entities = sum(item.retained_entity_count for item in cases)
    return PropositionScopeMetrics(
        true_positive_character_count=tp,
        false_positive_character_count=fp,
        false_negative_character_count=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        qualification_fragment_count=qualification,
        retained_qualification_fragment_count=retained_qualification,
        qualification_recall=_ratio(retained_qualification, qualification),
        expected_entity_count=entities,
        retained_entity_count=retained_entities,
        entity_recall=_ratio(retained_entities, entities),
    )


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 1.0


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"{label} must be ordered and distinct.")
