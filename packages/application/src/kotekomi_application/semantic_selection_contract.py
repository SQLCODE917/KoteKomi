"""Deterministic R17 semantic selection contract.

R17 pins the four selection decisions — eligibility, the complete selected set,
``NONE`` justification, and the five independent acceptance signals — into one
versioned, digest-bound record the Application Layer validates without invoking a
model.

The renderer writes the eligibility rule into the task instruction.  The loader
verifies each reference policy record's author, reviewer, review evidence, and
source, pool, and policy-body digests before any signal is computed.  The
evaluator parses each observed raw response once through the R16 strict parser for
its route, then applies five independent signals that never merge into one score.
The runner seals one report with zero model executions and zero canonical writes.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
import types
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

import kotekomi_application.corrective_reselection_execution as _reselection_module
import kotekomi_application.decontextualization_composition as _composition_module
from kotekomi_application.calibrated_residual_ownership import EventFrame
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentSourceRange,
)
from kotekomi_application.corrective_reselection_execution import (
    parse_corrective_reselection_answer,
)
from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
    DecontextualizationStatus,
    DecontextualizedProposition,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.hybrid_event_semantics import EventModality, EventPolarity
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
)
from kotekomi_application.residual_selection_failure_closure import ResidualClosureRoute

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]
_Label = Annotated[str, Field(pattern=r"^C[1-9][0-9]*$")]

SEMANTIC_SELECTION_CONTRACT_VERSION = 1

_SELECTION_FORMAT_INSTRUCTION = "Return a comma-separated subset of the Candidate labels, or NONE."

_ELIGIBILITY_RULE = (
    "Select only Candidates that supply source-exact content one required role demands. "
    "Selectable roles: subject, object, time, place, polarity, modality. "
    "Syntax attachment establishes availability, never eligibility."
)

_COMPLETE_SELECTED_SET_RULES = (
    "Exactly one eligible Candidate per required role the pool can represent; "
    "coordination may require multiple.",
    "Overlapping Candidates reduce to the narrowest source-exact canonical boundary.",
    "A Candidate is redundant only when it adds no required content beyond the canonical boundary.",
    "Separate source occurrences stay distinct even when their text matches.",
    "A select-all answer fails when the pool holds ineligible or redundant Candidates.",
)

_NONE_RULE = (
    "A justified NONE means the task is complete and no eligible Candidate exists. "
    "An observed NONE is an abstention judged against the expected eligible set, never "
    "assumed justified."
)

_CANONICAL_BOUNDARY_RULES = (
    "The canonical boundary is the narrowest source-exact span containing the role's "
    "argument head and all content the role requires, and no content a different role "
    "requires.",
    "A Candidate equal to the canonical boundary is not redundant because a larger "
    "Candidate contains it.",
)


def content_digest(value: object) -> str:
    """Return the canonical UTF-8 JSON digest of one structured value."""
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def file_digest(path: Path) -> str:
    """Return the SHA-256 digest of one file's raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _function_source_digest(functions: tuple[types.FunctionType, ...]) -> str:
    """Bind one digest to the current source of the functions that implement a behavior.

    Binding implemented behavior, not its instruction strings, means a digest can only
    stay green while the code that renders or evaluates stays byte-identical.
    """
    source = "\n\n".join(inspect.getsource(function) for function in functions)
    return hashlib.sha256(source.encode()).hexdigest()


def _module_source_digest(modules: tuple[types.ModuleType, ...]) -> str:
    """Bind one digest to the current source of the modules that implement a behavior."""
    source = "\n\n".join(inspect.getsource(module) for module in modules)
    return hashlib.sha256(source.encode()).hexdigest()


def _implementation_binding_payload() -> dict[str, object]:
    """Return the runtime state the scoring digest binds.

    Readiness and evaluation depend on module constants (``_ARGUMENT_ROLES``), module
    helpers, and the shared R4 composer and R16 parser.  Binding those dependencies,
    not three function bodies alone, means any drift in the constants or the modules
    the evaluator runs fails its frozen digest.
    """
    return {
        "argument_roles": sorted(_ARGUMENT_ROLES),
        "contract_module_sha256": _module_source_digest((sys.modules[__name__],)),
        "composition_module_sha256": _module_source_digest((_composition_module,)),
        "reselection_module_sha256": _module_source_digest((_reselection_module,)),
    }


class SemanticSelectionSignalName(StrEnum):
    """The five independent acceptance signals, in evaluation order."""

    ANSWER_GRAMMAR = "answer_grammar"
    SEMANTIC_SELECTION = "semantic_selection"
    BOUNDARY_COVERAGE = "boundary_coverage"
    ABSTENTION_CORRECTNESS = "abstention_correctness"
    COMPOSITION_READINESS = "composition_readiness"


SIGNAL_VALUES: dict[SemanticSelectionSignalName, tuple[str, ...]] = {
    SemanticSelectionSignalName.ANSWER_GRAMMAR: ("valid", "invalid"),
    SemanticSelectionSignalName.SEMANTIC_SELECTION: ("met", "unmet", "not_applicable"),
    SemanticSelectionSignalName.BOUNDARY_COVERAGE: ("met", "gap"),
    SemanticSelectionSignalName.ABSTENTION_CORRECTNESS: (
        "justified",
        "unjustified",
        "not_applicable",
    ),
    SemanticSelectionSignalName.COMPOSITION_READINESS: (
        "ready",
        "not_ready",
        "not_applicable",
    ),
}


class SignalDefinition(BaseModel):
    """One named signal definition with its legal values and its not-applicable rule."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: SemanticSelectionSignalName
    values: tuple[str, ...]
    not_applicable_when: Annotated[str, Field(min_length=1)]


SIGNAL_DEFINITIONS = (
    SignalDefinition(
        name=SemanticSelectionSignalName.ANSWER_GRAMMAR,
        values=("valid", "invalid"),
        not_applicable_when="never - always computed",
    ),
    SignalDefinition(
        name=SemanticSelectionSignalName.SEMANTIC_SELECTION,
        values=("met", "unmet", "not_applicable"),
        not_applicable_when="the strict-parse result is rejected",
    ),
    SignalDefinition(
        name=SemanticSelectionSignalName.BOUNDARY_COVERAGE,
        values=("met", "gap"),
        not_applicable_when="never - source- and pool-bound",
    ),
    SignalDefinition(
        name=SemanticSelectionSignalName.ABSTENTION_CORRECTNESS,
        values=("justified", "unjustified", "not_applicable"),
        not_applicable_when="the answer is not NONE",
    ),
    SignalDefinition(
        name=SemanticSelectionSignalName.COMPOSITION_READINESS,
        values=("ready", "not_ready", "not_applicable"),
        not_applicable_when="the reference selected set or composition inputs are absent",
    ),
)


class SemanticSelectionSignalResult(BaseModel):
    """One signal result for one (reference policy record, observed answer) pair."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: SemanticSelectionSignalName
    value: str
    explanation: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_legal_value(self) -> Self:
        if self.value not in SIGNAL_VALUES[self.name]:
            raise ValueError(
                f"Signal {self.name.value!r} rejects value {self.value!r}; "
                f"legal values are {SIGNAL_VALUES[self.name]}"
            )
        return self


class ContractBinding(BaseModel):
    """Content digests that freeze one contract version to its inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    policy_records_sha256: Annotated[str, Field(pattern=_SHA256)]
    renderer_sha256: Annotated[str, Field(pattern=_SHA256)]
    scoring_rules_sha256: Annotated[str, Field(pattern=_SHA256)]
    thresholds_sha256: Annotated[str, Field(pattern=_SHA256)]


class SemanticSelectionContract(BaseModel):
    """The versioned, digest-bound semantic selection contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Annotated[int, Field(ge=1)]
    eligibility_rule: Annotated[str, Field(min_length=1)]
    complete_selected_set_rules: tuple[Annotated[str, Field(min_length=1)], ...]
    none_rule: Annotated[str, Field(min_length=1)]
    canonical_boundary_rules: tuple[Annotated[str, Field(min_length=1)], ...]
    signal_definitions: tuple[SignalDefinition, ...]
    binding: ContractBinding

    @model_validator(mode="after")
    def validate_decisions(self) -> Self:
        if not self.complete_selected_set_rules:
            raise ValueError("A contract requires at least one complete-selected-set rule.")
        if not self.canonical_boundary_rules:
            raise ValueError("A contract requires at least one canonical-boundary rule.")
        if not self.signal_definitions:
            raise ValueError("A contract requires at least one signal definition.")
        return self


def compute_contract_binding(
    *,
    records: object,
    eligibility_rule: str = _ELIGIBILITY_RULE,
    complete_selected_set_rules: tuple[str, ...] = _COMPLETE_SELECTED_SET_RULES,
    none_rule: str = _NONE_RULE,
    canonical_boundary_rules: tuple[str, ...] = _CANONICAL_BOUNDARY_RULES,
    signal_definitions: tuple[SignalDefinition, ...] = SIGNAL_DEFINITIONS,
) -> ContractBinding:
    """Recompute the four binding digests from current decisions and implemented behavior.

    ``renderer_sha256`` binds the source of ``render_selection_task`` and
    ``scoring_rules_sha256`` binds the implemented evaluation and readiness behavior,
    including its module constants, helpers, and the shared R4 composer and R16 parser
    modules, so drifting the implemented rendering or evaluation behavior — not just its
    instruction strings — fails the check.  ``thresholds_sha256`` binds every decision
    text the evaluation honors, including the NONE and canonical-boundary rules.
    """
    return ContractBinding(
        policy_records_sha256=content_digest(records),
        renderer_sha256=_function_source_digest((render_selection_task,)),
        scoring_rules_sha256=content_digest(_implementation_binding_payload()),
        thresholds_sha256=content_digest(
            {
                "eligibility_rule": eligibility_rule,
                "complete_selected_set_rules": complete_selected_set_rules,
                "none_rule": none_rule,
                "canonical_boundary_rules": canonical_boundary_rules,
                "signal_definitions": [
                    (definition.name.value, definition.values, definition.not_applicable_when)
                    for definition in signal_definitions
                ],
            }
        ),
    )


def frozen_semantic_selection_contract(*, directory: Path) -> SemanticSelectionContract:
    """Load the persisted version-1 contract with its frozen content digests."""
    payload = _read_json(directory / "semantic_selection_contract.json")
    _require(
        payload["schema_version"] == "r17_semantic_selection_contract_v1",
        "Unknown semantic selection contract format.",
    )
    return SemanticSelectionContract.model_validate_json(
        json.dumps(payload["contract"], ensure_ascii=False, allow_nan=False, sort_keys=True)
    )


def verify_policy_records_binding(*, contract: SemanticSelectionContract, records: object) -> None:
    """Fail fast when the policy-record content drifted from the frozen version."""
    if content_digest(records) != contract.binding.policy_records_sha256:
        raise ValueError("Policy-record content drifted from the frozen contract version.")


class FileHandle(BaseModel):
    """One repository-relative file path plus its SHA-256 digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=_SHA256)]


class InputBinding(BaseModel):
    """One policy record's frozen input digests and route."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    input_file: FileHandle
    source_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_pool_sha256: Annotated[str, Field(pattern=_SHA256)]
    task_sha256: Annotated[str, Field(pattern=_SHA256)]
    frozen_route: ResidualClosureRoute


class ExpectedSourceRange(BaseModel):
    """One required source range, recorded independently of the Candidate pool."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: Annotated[str, Field(min_length=1)]
    expected_source_range: AttachmentSourceRange
    canonical_candidate_label: _Label | None
    eligibility_explanation: Annotated[str, Field(min_length=1)]
    covering_candidate_labels: tuple[_Label, ...]
    boundary_coverage: Literal["met", "gap"]


class NonePolicy(BaseModel):
    """The human-reviewed NONE justification for one policy record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    justified: bool
    explanation: Annotated[str, Field(min_length=1)]


class CompositionReadiness(BaseModel):
    """The reference selected set's review-independent readiness judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    value: Literal["ready", "not_ready", "not_applicable"]
    reasons: tuple[str, ...]
    basis: Annotated[str, Field(min_length=1)]


class ReferenceAttributionRequirement(BaseModel):
    """The reviewed attribution content one proposition construction needs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["source_narrator", "targeted"]
    reporter: Annotated[str, Field(min_length=1)] | None = None
    reporting_carrier: AttachmentSourceRange | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.kind == "targeted":
            if self.reporter is None or self.reporting_carrier is None:
                raise ValueError("A targeted attribution requires a reporter and a carrier.")
        elif self.reporter is not None or self.reporting_carrier is not None:
            raise ValueError("A source-narrator attribution cannot name a reporter or carrier.")
        return self


class ReferencePropositionRequirements(BaseModel):
    """The reviewed polarity, modality, and attribution the composed content must carry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    polarity: EventPolarity
    modality: EventModality
    attribution: ReferenceAttributionRequirement


class ReferencePolicyRecord(BaseModel):
    """One human-reviewed policy record resolved with its frozen inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    record_id: Annotated[str, Field(min_length=1)]
    event_id: _EventId
    input_binding: InputBinding
    policy_body_sha256: Annotated[str, Field(pattern=_SHA256)]
    expected_selected_set: tuple[_Label, ...]
    expected_source_ranges: tuple[ExpectedSourceRange, ...]
    eligibility_explanation: Annotated[str, Field(min_length=1)]
    none_policy: NonePolicy
    composition_readiness: CompositionReadiness
    author_identity: Annotated[str, Field(min_length=1)]
    reviewer_identity: Annotated[str, Field(min_length=1)]
    review_mode: Annotated[str, Field(min_length=1)]
    review_date: Annotated[str, Field(min_length=1)]
    review_commit: str | None
    review_evidence: FileHandle
    adopted_policy_body_sha256: Annotated[str, Field(pattern=_SHA256)]
    adopted_input_sha256: Annotated[str, Field(pattern=_SHA256)]

    # Resolved by the loader from the frozen, digest-verified input file.
    task: ConstituentSelectionTask
    inventory: ConstituentCandidateInventory
    source_text: Annotated[str, Field(min_length=1)]
    frame: EventFrame
    composition_tokens: tuple[EventEntityLinguisticToken, ...]
    composition_entities: tuple[DecontextualizationEntityRef, ...]
    proposition_requirements: ReferencePropositionRequirements


class ObservedAnswer(BaseModel):
    """One frozen observed answer kept distinct from its reference policy record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    observation_id: Annotated[str, Field(min_length=1)]
    event_id: _EventId
    route: ResidualClosureRoute
    origin: Annotated[str, Field(min_length=1)]
    raw_response: str
    raw_response_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_run_artifact: FileHandle | None
    parsed_answer: ConstituentSelectionAnswer
    note: str | None
    fixture_body_sha256: Annotated[str, Field(pattern=_SHA256)]
    reviewer_identity: Annotated[str, Field(min_length=1)]
    review_mode: Annotated[str, Field(min_length=1)]
    review_date: Annotated[str, Field(min_length=1)]
    review_commit: str | None
    reviewed_fixture_body_sha256: Annotated[str, Field(pattern=_SHA256)]
    review_evidence: FileHandle


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


def _typed[T: BaseModel](model: type[T], value: object) -> T:
    return model.model_validate_json(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def build_semantic_selection_contract(
    *, version: int, binding: ContractBinding
) -> SemanticSelectionContract:
    """Assemble one contract from the pinned decision texts and an explicit binding."""
    return SemanticSelectionContract(
        version=version,
        eligibility_rule=_ELIGIBILITY_RULE,
        complete_selected_set_rules=_COMPLETE_SELECTED_SET_RULES,
        none_rule=_NONE_RULE,
        canonical_boundary_rules=_CANONICAL_BOUNDARY_RULES,
        signal_definitions=SIGNAL_DEFINITIONS,
        binding=binding,
    )


def render_selection_task(
    *,
    contract: SemanticSelectionContract,
    frame: EventFrame,
    inventory: ConstituentCandidateInventory,
    source_text: str,
) -> ConstituentSelectionTask:
    """Render one Constituent Selection Task whose instruction names the eligibility rule."""
    if frame.event_id != inventory.event_id:
        raise ValueError("Selection renderer received a frame and inventory for different Events.")
    if hashlib.sha256(source_text.encode()).hexdigest() != inventory.source_text_sha256:
        raise ValueError("Selection renderer source digest does not match the inventory.")
    labels = tuple(f"C{ordinal}" for ordinal in range(1, len(inventory.constituents) + 1))
    lines = [
        _SELECTION_FORMAT_INSTRUCTION,
        f"Eligibility: {contract.eligibility_rule}",
        f"Event: {frame.trigger.text}",
        "Passage:",
        source_text,
        "Candidates:",
    ]
    for label, constituent in zip(labels, inventory.constituents, strict=True):
        lines.append(f"{label}: {constituent.constituent_range.text}")
    rendered = "\n".join(lines)
    return ConstituentSelectionTask(
        event_id=inventory.event_id,
        source_text_sha256=inventory.source_text_sha256,
        source_text=source_text,
        constituent_labels=labels,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
    )


def _covering_labels(
    inventory: ConstituentCandidateInventory, role: ExpectedSourceRange
) -> tuple[str, ...]:
    """Return the ordered labels whose constituent spans cover one expected range."""
    return tuple(
        f"C{ordinal}"
        for ordinal, candidate in enumerate(inventory.constituents, 1)
        if candidate.constituent_range.start <= role.expected_source_range.start
        and role.expected_source_range.end <= candidate.constituent_range.end
    )


def load_reference_policy_records(
    *,
    contract: SemanticSelectionContract,
    directory: Path,
) -> tuple[ReferencePolicyRecord, ...]:
    """Load and verify the frozen, digest-bound reference policy record set."""
    document = _read_json(directory / "reference_policy_records.json")
    _require(
        document["schema_version"] == "r17_reference_policy_records_v1", "Unknown policy format"
    )
    _require(
        document["contract_version"] == contract.version,
        "Policy records bind a different contract version.",
    )
    records_raw = cast(list[dict[str, Any]], document["records"])
    verify_policy_records_binding(contract=contract, records=records_raw)
    return tuple(
        _build_reference_policy_record(record, contract=contract, directory=directory)
        for record in records_raw
    )


def _build_reference_policy_record(
    record: dict[str, Any],
    *,
    contract: SemanticSelectionContract,
    directory: Path,
) -> ReferencePolicyRecord:
    policy_body = cast(dict[str, Any], record["policy_body"])
    _require(
        content_digest(policy_body) == record["policy_body_sha256"],
        "Policy-body digest differs from its content.",
    )
    adoption = cast(dict[str, Any], record["human_adoption"])
    review = cast(dict[str, Any], record["human_review"])
    _require(
        adoption["author_identity"] == review["reviewer_identity"],
        "Policy author and reviewer identities differ.",
    )
    _require(bool(review["reviewer_identity"]), "Policy record lacks a reviewer identity.")
    _require(bool(adoption["author_identity"]), "Policy record lacks an author identity.")
    _require(
        adoption["adopted_policy_body_sha256"] == record["policy_body_sha256"],
        "Adopted policy-body digest differs.",
    )
    _require(
        review["reviewed_policy_body_sha256"] == record["policy_body_sha256"],
        "Reviewed policy-body digest differs.",
    )
    _require(adoption["evidence"] == review["evidence"], "Policy review evidence differs.")
    review_evidence = _typed(FileHandle, review["evidence"])

    input_binding = _typed(InputBinding, record["input_binding"])
    root = directory.resolve().parents[1]
    input_path = (root / input_binding.input_file.path).resolve()
    _require(input_path.is_relative_to(root), "Policy input handle escapes the repository.")
    _require(
        file_digest(input_path) == input_binding.input_file.sha256, "Policy input digest drift."
    )
    frozen_input = _read_json(input_path)
    source_text = cast(str, frozen_input["source_text"])
    _require(
        hashlib.sha256(source_text.encode()).hexdigest() == input_binding.source_sha256,
        "Policy source digest drift.",
    )
    _require(
        content_digest(frozen_input["candidate_inventory"]) == input_binding.candidate_pool_sha256,
        "Policy candidate-pool digest drift.",
    )
    _require(
        content_digest(frozen_input["selection_task"]) == input_binding.task_sha256,
        "Policy task digest drift.",
    )
    _require(
        frozen_input["frozen_task_route"] == input_binding.frozen_route.value,
        "Policy input route disagrees with its binding.",
    )
    inventory = _typed(ConstituentCandidateInventory, frozen_input["candidate_inventory"])
    frame = _typed(EventFrame, frozen_input["event_frame"])
    task = render_selection_task(
        contract=contract, frame=frame, inventory=inventory, source_text=source_text
    )

    expected_ranges = tuple(
        _typed(ExpectedSourceRange, item) for item in policy_body["expected_source_ranges"]
    )
    composition_body = cast(dict[str, Any], frozen_input["composition_inputs"])
    composition_tokens = tuple(
        _typed(EventEntityLinguisticToken, item) for item in composition_body["tokens"]
    )
    composition_entities = tuple(
        _typed(DecontextualizationEntityRef, item) for item in composition_body["entities"]
    )
    proposition_requirements = _typed(
        ReferencePropositionRequirements, policy_body["proposition_inputs"]
    )
    built = ReferencePolicyRecord(
        record_id=cast(str, record["record_id"]),
        event_id=cast(str, record["event_id"]),
        input_binding=input_binding,
        policy_body_sha256=cast(str, record["policy_body_sha256"]),
        expected_selected_set=tuple(policy_body["expected_selected_set"]),
        expected_source_ranges=expected_ranges,
        eligibility_explanation=cast(str, policy_body["eligibility_explanation"]),
        none_policy=_typed(NonePolicy, policy_body["none_policy"]),
        composition_readiness=_typed(CompositionReadiness, policy_body["composition_readiness"]),
        author_identity=cast(str, adoption["author_identity"]),
        reviewer_identity=cast(str, review["reviewer_identity"]),
        review_mode=cast(str, review["review_mode"]),
        review_date=cast(str, review["review_date"]),
        review_commit=cast(str | None, review["review_commit"]),
        review_evidence=review_evidence,
        adopted_policy_body_sha256=cast(str, adoption["adopted_policy_body_sha256"]),
        adopted_input_sha256=cast(str, adoption["adopted_input_sha256"]),
        task=task,
        inventory=inventory,
        source_text=source_text,
        frame=frame,
        composition_tokens=composition_tokens,
        composition_entities=composition_entities,
        proposition_requirements=proposition_requirements,
    )
    for role in built.expected_source_ranges:
        covering = _covering_labels(built.inventory, role)
        _require(
            covering == role.covering_candidate_labels, "Coverage labels differ from the pool."
        )
        _require(
            role.boundary_coverage == ("met" if covering else "gap"),
            "Coverage judgment differs from the pool.",
        )
        _require(
            role.canonical_candidate_label is None or role.canonical_candidate_label in covering,
            "Canonical candidate does not cover its expected range.",
        )
    _require(
        compute_composition_readiness(policy_record=built) == built.composition_readiness.value,
        "Computed composition readiness does not reproduce the reviewed value.",
    )
    return built


def _answer_fixture_body(observation: dict[str, Any]) -> dict[str, Any]:
    """Return the reviewed subset one observed-answer fixture digest binds."""
    return {
        key: observation[key]
        for key in (
            "observation_id",
            "event_id",
            "route",
            "origin",
            "raw_response",
            "raw_response_sha256",
            "source_run_artifact",
            "parsed_answer",
            "note",
            "expected_signals",
        )
    }


def build_observed_answer(
    *,
    observation: dict[str, Any],
    task: ConstituentSelectionTask,
    frozen_route: ResidualClosureRoute,
    approval_evidence: FileHandle,
    approved_fixture_body_sha256: str,
    root: Path,
) -> ObservedAnswer:
    """Verify and build one observed answer against its frozen task route and approval.

    The reviewed fixture digest, the archived response bytes, the review evidence
    handle, and the human-approved answer fixture are verified here, so an altered
    historical answer cannot be admitted by re-hashing its raw response while leaving
    the original reviewed digest or approval membership in place.
    """
    route = ResidualClosureRoute(observation["route"])
    _require(
        route is frozen_route,
        "Observed answer route differs from its frozen task route.",
    )
    _require(
        observation["event_id"] == task.event_id,
        "Observed answer Event differs from its frozen task.",
    )
    _require(
        content_digest(_answer_fixture_body(observation)) == observation["fixture_body_sha256"],
        "Observed-answer fixture digest differs from its reviewed body.",
    )
    review = cast(dict[str, Any], observation["human_review"])
    _require(
        review["reviewed_fixture_body_sha256"] == observation["fixture_body_sha256"],
        "Observed-answer review digest differs from its fixture body.",
    )
    _require(
        _typed(FileHandle, review["evidence"]) == approval_evidence,
        "Observed-answer review evidence differs from the approval binding.",
    )
    raw_response = cast(str, observation["raw_response"])
    _require(
        hashlib.sha256(raw_response.encode()).hexdigest() == observation["raw_response_sha256"],
        "Observed raw response digest differs.",
    )
    artifact = observation["source_run_artifact"]
    if artifact is not None:
        source_path = (root / cast(str, artifact["path"])).resolve()
        _require(source_path.is_relative_to(root), "Answer artifact handle escapes the repository.")
        _require(
            file_digest(source_path) == cast(str, artifact["sha256"]),
            "Archived response digest drifted.",
        )
        _require(
            source_path.read_text() == raw_response,
            "Archived response differs from the observed raw response.",
        )
    parsed = parse_corrective_reselection_answer(raw_response, task, route)
    _require(
        parsed == _typed(ConstituentSelectionAnswer, observation["parsed_answer"]),
        "Stored strict parse differs from a fresh parse.",
    )
    _require(
        observation["fixture_body_sha256"] == approved_fixture_body_sha256,
        "Observed-answer fixture digest is not the approved answer fixture.",
    )
    return ObservedAnswer(
        observation_id=cast(str, observation["observation_id"]),
        event_id=cast(str, observation["event_id"]),
        route=route,
        origin=cast(str, observation["origin"]),
        raw_response=raw_response,
        raw_response_sha256=cast(str, observation["raw_response_sha256"]),
        source_run_artifact=_typed(FileHandle, artifact) if artifact is not None else None,
        parsed_answer=parsed,
        note=cast(str | None, observation["note"]),
        fixture_body_sha256=cast(str, observation["fixture_body_sha256"]),
        reviewer_identity=cast(str, review["reviewer_identity"]),
        review_mode=cast(str, review["review_mode"]),
        review_date=cast(str, review["review_date"]),
        review_commit=cast(str | None, review["review_commit"]),
        reviewed_fixture_body_sha256=cast(str, review["reviewed_fixture_body_sha256"]),
        review_evidence=_typed(FileHandle, review["evidence"]),
    )


def load_observed_answers(
    *,
    contract: SemanticSelectionContract,
    directory: Path,
    records: tuple[ReferencePolicyRecord, ...],
) -> tuple[ObservedAnswer, ...]:
    """Load and verify the observed answers kept distinct from the policy records."""
    del contract  # the contract carries the version; the route binding is per policy record.
    document = _read_json(directory / "observed_answers.json")
    _require(document["schema_version"] == "r17_observed_answers_v1", "Unknown answer format")
    approval_evidence = _typed(FileHandle, document["human_approval"])
    observations = cast(list[dict[str, Any]], document["observations"])
    by_event = {record.event_id: record for record in records}
    _require(
        set(by_event) == {item["event_id"] for item in observations},
        "Observed-answer coverage differs from the policy records.",
    )
    root = directory.resolve().parents[1]
    approval_path = (root / approval_evidence.path).resolve()
    _require(approval_path.is_relative_to(root), "Approval handle escapes the repository.")
    _require(
        file_digest(approval_path) == approval_evidence.sha256,
        "Approval file digest drift.",
    )
    approval_document = _read_json(approval_path)
    _require(
        approval_document["schema_version"] == "r17_operator_review_attestation_v1",
        "Unknown approval format.",
    )
    approved_fixtures = {
        cast(str, item["observation_id"]): cast(str, item["fixture_body_sha256"])
        for item in cast(list[dict[str, Any]], approval_document["approved_answer_fixtures"])
    }
    return tuple(
        build_observed_answer(
            observation=observation,
            task=by_event[observation["event_id"]].task,
            frozen_route=by_event[observation["event_id"]].input_binding.frozen_route,
            approval_evidence=approval_evidence,
            approved_fixture_body_sha256=_require_approved_fixture_digest(
                approved_fixtures, cast(str, observation["observation_id"])
            ),
            root=root,
        )
        for observation in observations
    )


def _require_approved_fixture_digest(approved_fixtures: dict[str, str], observation_id: str) -> str:
    """Return one approved answer fixture digest or fail fast when it is absent."""
    _require(
        observation_id in approved_fixtures,
        "Observed answer is not in the approved answer fixtures.",
    )
    return approved_fixtures[observation_id]


def _compose_reference_proposition(
    *, policy_record: ReferencePolicyRecord
) -> DecontextualizedProposition:
    """Re-run the deterministic R4 composer over the reviewed reference selected set."""
    raw = (
        ",".join(policy_record.expected_selected_set)
        if policy_record.expected_selected_set
        else "NONE"
    )
    answer = parse_corrective_reselection_answer(
        raw, policy_record.task, policy_record.input_binding.frozen_route
    )
    return build_decontextualized_proposition(
        event_id=policy_record.event_id,
        source_text=policy_record.source_text,
        source_text_sha256=policy_record.input_binding.source_sha256,
        inventory=policy_record.inventory,
        answer=answer,
        trigger_head_start=policy_record.frame.trigger.start,
        trigger_head_end=policy_record.frame.trigger.end,
        tokens=policy_record.composition_tokens,
        entities=policy_record.composition_entities,
    )


def _composed_content_preserved(
    *, policy_record: ReferencePolicyRecord, composed: DecontextualizedProposition
) -> bool:
    """Return whether the composed result carries the reviewed required content.

    The reviewed reference proposition states the polarity, modality, and attribution
    the selected content is required to supply, and the reviewed source ranges state
    which subject/object argument roles must be represented at which source span.  A
    composed result that emits different polarity, modality, or attribution — or that
    drops or rewrites a required argument span — has lost required content even when it
    still matches the reviewed attribution kind.  A targeted attribution must name the
    reviewed reporter and carrier span, not merely the attribution kind.
    """
    requirements = policy_record.proposition_requirements
    if composed.polarity is None or composed.modality is None or composed.attribution is None:
        return False
    if composed.polarity != requirements.polarity:
        return False
    if composed.modality != requirements.modality:
        return False
    if composed.attribution.kind.value != requirements.attribution.kind:
        return False
    if not _argument_roles_preserved(policy_record=policy_record, composed=composed):
        return False
    if requirements.attribution.kind == "targeted" and not _targeted_attribution_preserved(
        policy_record=policy_record, composed=composed
    ):
        return False
    return True


def _argument_roles_preserved(
    *, policy_record: ReferencePolicyRecord, composed: DecontextualizedProposition
) -> bool:
    """Return whether each required subject/object role is present at its source span."""

    for requirement in policy_record.expected_source_ranges:
        if (
            requirement.role not in _CONTENT_ARGUMENT_ROLES
            or requirement.boundary_coverage != "met"
        ):
            continue
        role = composed.subject if requirement.role == "subject" else composed.object
        if role is None or role.exact_fragment != requirement.expected_source_range:
            return False
    return True


def _targeted_attribution_preserved(
    *, policy_record: ReferencePolicyRecord, composed: DecontextualizedProposition
) -> bool:
    """Return whether a targeted attribution names the reviewed reporter and carrier span."""

    requirement = policy_record.proposition_requirements.attribution
    attribution = composed.attribution
    if (
        attribution is None
        or attribution.kind.value != "targeted"
        or requirement.reporter is None
        or requirement.reporting_carrier is None
    ):
        return False
    reporter = next(
        (
            entity
            for entity in policy_record.composition_entities
            if entity.entity_id == attribution.reporter_ref
        ),
        None,
    )
    return (
        reporter is not None
        and reporter.canonical_name == requirement.reporter
        and attribution.exact_carrier == requirement.reporting_carrier
    )


#: The span-carrying argument roles the R4 composer can hold. The composer emits at most
#: one ``subject`` and one ``object`` role, so a reference that demands more than two
#: span-carrying roles loses required content and is not ready to compose.
_ARGUMENT_ROLES = frozenset({"subject", "object", "time", "place"})


#: The content-triple roles the R4 composer materializes as a ``DecontextualizedRole``.
#: Each reviewed source-range requirement naming one of these roles must be represented
#: in the composed result at its reviewed source span.
_CONTENT_ARGUMENT_ROLES = frozenset({"subject", "object"})


def compute_composition_readiness(*, policy_record: ReferencePolicyRecord) -> str:
    """Deterministically compute the reference selected set's composition readiness.

    Readiness is derived from the resolved composition inputs (tokens and entity
    references) and the re-run R4 composition result, never copied from the reviewed
    annotation. The composed result is compared with the reviewed polarity, modality,
    and attribution requirements, and the argument-span count is capped at the two roles
    the composer can hold. Removing the entity references from an otherwise composable
    reference turns ``ready`` into ``not_ready`` while the semantic-selection judgment
    stays met.
    """
    ranges = policy_record.expected_source_ranges
    if (
        not policy_record.composition_tokens
        and not policy_record.composition_entities
        and not ranges
        and not policy_record.expected_selected_set
    ):
        return "not_applicable"
    if not policy_record.expected_selected_set:
        return "not_ready"
    if any(role.boundary_coverage == "gap" for role in ranges):
        return "not_ready"
    composed = _compose_reference_proposition(policy_record=policy_record)
    if composed.status is not DecontextualizationStatus.PROPOSITION:
        return "not_ready"
    content_span_count = sum(
        1 for role in ranges if role.role in _ARGUMENT_ROLES and role.boundary_coverage == "met"
    )
    if content_span_count > 2:
        return "not_ready"
    if not _composed_content_preserved(policy_record=policy_record, composed=composed):
        return "not_ready"
    return "ready"


def check_boundary_coverage(*, policy_record: ReferencePolicyRecord) -> str:
    """Return ``met`` when every expected range is covered, otherwise ``gap``."""
    for role in policy_record.expected_source_ranges:
        if not _covering_labels(policy_record.inventory, role):
            return "gap"
    return "met"


def evaluate_selection(
    *,
    contract: SemanticSelectionContract,
    policy_record: ReferencePolicyRecord,
    observed_answer: ObservedAnswer,
) -> tuple[SemanticSelectionSignalResult, ...]:
    """Parse one observed answer once and apply the five independent signals."""
    _require(
        observed_answer.event_id == policy_record.event_id,
        "Observed answer Event differs from its policy record.",
    )
    _require(
        observed_answer.route is policy_record.input_binding.frozen_route,
        "Observed answer route disagrees with its policy record.",
    )
    del contract  # the signals bind to the policy record and the observed answer.
    parsed = parse_corrective_reselection_answer(
        observed_answer.raw_response, policy_record.task, observed_answer.route
    )
    grammar = "invalid" if parsed.status is ConstituentSelectionStatus.REJECTED else "valid"
    if parsed.status is ConstituentSelectionStatus.REJECTED:
        semantic = "not_applicable"
        abstention = "not_applicable"
    else:
        selected = tuple(f"C{i}" for i in parsed.selected_label_indexes)
        semantic = "met" if selected == policy_record.expected_selected_set else "unmet"
        abstention = (
            "not_applicable"
            if parsed.status is not ConstituentSelectionStatus.NONE
            else ("justified" if policy_record.none_policy.justified else "unjustified")
        )
    coverage = check_boundary_coverage(policy_record=policy_record)
    readiness = compute_composition_readiness(policy_record=policy_record)
    return (
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.ANSWER_GRAMMAR,
            value=grammar,
            explanation="Strict R16 route grammar applied once to the raw response.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.SEMANTIC_SELECTION,
            value=semantic,
            explanation="Observed label set compared with the reviewed expected selected set.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.BOUNDARY_COVERAGE,
            value=coverage,
            explanation="Expected source ranges compared with the frozen Candidate pool.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.ABSTENTION_CORRECTNESS,
            value=abstention,
            explanation="Observed NONE judged against the reviewed expected eligible set.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.COMPOSITION_READINESS,
            value=readiness,
            explanation="Readiness evaluates the reference selected set, not the observed answer.",
        ),
    )


class EvaluationItem(BaseModel):
    """One observed answer's five signal results for one policy record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    observation_id: Annotated[str, Field(min_length=1)]
    event_id: _EventId
    route: ResidualClosureRoute
    signals: tuple[SemanticSelectionSignalResult, ...]

    @model_validator(mode="after")
    def validate_signals(self) -> Self:
        names = tuple(signal.name for signal in self.signals)
        if names != tuple(SemanticSelectionSignalName):
            raise ValueError("An evaluation must cover the five signals in order.")
        return self


class SemanticSelectionReport(BaseModel):
    """One sealed, model-free semantic selection report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    contract_version: Annotated[int, Field(ge=1)]
    policy_record_count: Annotated[int, Field(ge=0)]
    observed_answer_count: Annotated[int, Field(ge=0)]
    evaluation_count: Annotated[int, Field(ge=0)]
    evaluations: tuple[EvaluationItem, ...]
    model_execution_count: Literal[0]
    canonical_write_count: Literal[0]
    proposed_change_count: Literal[0]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.evaluation_count != len(self.evaluations):
            raise ValueError("Report evaluation count drifted from its evaluations.")
        ids = tuple(item.observation_id for item in self.evaluations)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("Report evaluations must be ordered and distinct by observation ID.")
        return self


def semantic_selection_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one report, excluding its own fingerprint."""
    if isinstance(value, BaseModel):
        payload: object = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def build_semantic_selection_report(
    *,
    contract: SemanticSelectionContract,
    policy_records: tuple[ReferencePolicyRecord, ...],
    observed_answers: tuple[ObservedAnswer, ...],
    evaluations: tuple[EvaluationItem, ...],
) -> SemanticSelectionReport:
    """Assemble and seal one report with zero executions and zero writes."""
    ordered = tuple(sorted(evaluations, key=lambda item: item.observation_id))
    draft = SemanticSelectionReport.model_construct(
        contract_version=contract.version,
        policy_record_count=len(policy_records),
        observed_answer_count=len(observed_answers),
        evaluation_count=len(ordered),
        evaluations=ordered,
        model_execution_count=0,
        canonical_write_count=0,
        proposed_change_count=0,
        result_fingerprint="0" * 64,
    )
    return SemanticSelectionReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=semantic_selection_report_fingerprint(draft),
    )


def verify_contract_binding(
    *,
    contract: SemanticSelectionContract,
    records: object,
) -> None:
    """Fail fast when any of the four binding digests drifted from the contract version."""
    recomputed = compute_contract_binding(
        records=records,
        eligibility_rule=contract.eligibility_rule,
        complete_selected_set_rules=contract.complete_selected_set_rules,
        none_rule=contract.none_rule,
        canonical_boundary_rules=contract.canonical_boundary_rules,
        signal_definitions=contract.signal_definitions,
    )
    if recomputed != contract.binding:
        raise ValueError("Contract binding drifted from its frozen content digests.")
