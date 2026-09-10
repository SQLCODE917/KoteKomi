"""HP-2 orchestration over one immutable HP-1 Preview."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, cast, overload

from kotekomi_domain import DocumentRepresentationBundle

from kotekomi_application.context_planning import (
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextTokenizer,
    build_context_manifest,
    load_analysis_unit,
    load_context_manifest,
    verify_context_manifest,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    build_hybrid_reference_preview,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_sha256,
)
from kotekomi_application.hybrid_mention_interpretation import (
    PreviewStore,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    parse_semantic_reference_challenge_output,
    semantic_reference_challenge_schema_bytes,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    parse_semantic_reference_candidate_validation_output,
    semantic_reference_candidate_validation_schema_bytes,
)
from kotekomi_application.semantic_references import (
    CoreferenceAntecedentCandidate,
    CoreferenceProposerPort,
    CoreferenceTokenizer,
    SemanticReferenceCandidateLabelBinding,
    SemanticReferenceCandidateValidationExecution,
    SemanticReferenceCandidateValidationInput,
    SemanticReferenceChallengeExecution,
    SemanticReferenceChallengeInput,
    SemanticReferenceChallengerPort,
)
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    BoundedExtractionOutcome,
    ExecutionSetting,
    ModelExecutionSpec,
    ModelOutputArchive,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    run_bounded_extraction,
)

SEMANTIC_REFERENCE_CHALLENGE_PROMPT_ID = "semantic_reference_challenge_v4"
SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID = "semantic_reference_challenge_text_v2"
SEMANTIC_REFERENCE_VALIDATION_PROMPT_ID = "semantic_reference_candidate_validation_v1"
SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID = "semantic_reference_candidate_validation_text_v1"
_CANDIDATE_CONTEXT_CHARACTER_LIMIT = 64


class HybridReferenceLedger(StagedExtractionLedger, Protocol):
    pass


class HybridReferenceReadLedger(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class HybridReferenceReadArchive(PreviewStore, Protocol):
    def put_hybrid_reference_preview(
        self,
        preview: HybridReferencePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes: ...


class HybridReferenceArchive(HybridReferenceReadArchive, ModelOutputArchive, Protocol):
    pass


@dataclass(frozen=True)
class HybridReferencePreviewCommand:
    parent_preview_id: str
    model_profile: ContextModelProfile | None = None
    generation_parameters: tuple[ExecutionSetting, ...] = ()


@dataclass(frozen=True)
class HybridReferencePreviewResult:
    preview: HybridReferencePreview
    sha256: str
    archive_path: str


@overload
def run_hybrid_reference_preview(
    *,
    command: HybridReferencePreviewCommand,
    ledger: HybridReferenceReadLedger,
    archive: HybridReferenceReadArchive,
    coreference_proposer: None = None,
    coreference_tokenizer: None = None,
    model_runtime: None = None,
    model_run_id_factory: None = None,
    challenge_prompt_bytes: None = None,
    validation_prompt_bytes: None = None,
) -> HybridReferencePreviewResult: ...


@overload
def run_hybrid_reference_preview(
    *,
    command: HybridReferencePreviewCommand,
    ledger: HybridReferenceLedger,
    archive: HybridReferenceArchive,
    coreference_proposer: CoreferenceProposerPort,
    coreference_tokenizer: CoreferenceTokenizer,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    challenge_prompt_bytes: bytes,
    validation_prompt_bytes: bytes,
) -> HybridReferencePreviewResult: ...


def run_hybrid_reference_preview(
    *,
    command: HybridReferencePreviewCommand,
    ledger: HybridReferenceReadLedger,
    archive: HybridReferenceReadArchive,
    coreference_proposer: CoreferenceProposerPort | None = None,
    coreference_tokenizer: CoreferenceTokenizer | None = None,
    model_runtime: ModelTaskRuntime | None = None,
    model_run_id_factory: ModelRunIdFactory | None = None,
    challenge_prompt_bytes: bytes | None = None,
    validation_prompt_bytes: bytes | None = None,
) -> HybridReferencePreviewResult:
    """Run deterministic HP-2 resolution and publish one immutable Preview."""
    parent_payload = archive.read_hybrid_extraction_preview(command.parent_preview_id)
    parent = hybrid_extraction_preview_from_bytes(parent_payload)
    if parent.id != command.parent_preview_id:
        raise ValueError("HP-2 parent Preview identity does not match its Archive path.")
    if canonical_hybrid_extraction_preview_bytes(parent) != parent_payload:
        raise ValueError("HP-2 parent Preview does not use canonical encoding.")
    parent_sha256 = hashlib.sha256(parent_payload).hexdigest()
    bundle = ledger.get_document_representation_bundle(parent.representation_id)
    if bundle is None:
        raise ValueError("HP-2 parent Preview references a missing representation.")
    challenge_values = (
        command.model_profile,
        model_runtime,
        model_run_id_factory,
        challenge_prompt_bytes,
        validation_prompt_bytes,
    )
    if coreference_proposer is not None and any(value is None for value in challenge_values):
        raise ValueError(
            "HP-2 semantic coreference requires model profile, runtime, run IDs, and prompts."
        )
    challenger: SemanticReferenceChallengerPort | None = None
    if coreference_proposer is not None:
        assert command.model_profile is not None
        assert model_runtime is not None
        assert model_run_id_factory is not None
        assert challenge_prompt_bytes is not None
        assert validation_prompt_bytes is not None
        staged_ledger = cast(HybridReferenceLedger, ledger)
        staged_archive = cast(HybridReferenceArchive, archive)
        challenger = _BoundedReferenceChallenger(
            source_id=_source_id(bundle, staged_ledger),
            document_id=bundle.representation.document_id,
            representation_id=bundle.representation.id,
            selection_manifest=_reference_manifest(
                parent.context_manifest_id,
                bundle,
                command.model_profile,
                prompt_id=SEMANTIC_REFERENCE_CHALLENGE_PROMPT_ID,
                prompt_bytes=challenge_prompt_bytes,
                schema_id=SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID,
                schema_bytes=semantic_reference_challenge_schema_bytes(),
                renderer_version="semantic_reference_challenge_context_v4",
                ledger=staged_ledger,
                tokenizer=model_runtime,
            ),
            validation_manifest=_reference_manifest(
                parent.context_manifest_id,
                bundle,
                command.model_profile,
                prompt_id=SEMANTIC_REFERENCE_VALIDATION_PROMPT_ID,
                prompt_bytes=validation_prompt_bytes,
                schema_id=SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID,
                schema_bytes=semantic_reference_candidate_validation_schema_bytes(),
                renderer_version="semantic_reference_candidate_validation_context_v1",
                ledger=staged_ledger,
                tokenizer=model_runtime,
            ),
            generation_parameters=command.generation_parameters,
            selection_prompt_bytes=challenge_prompt_bytes,
            validation_prompt_bytes=validation_prompt_bytes,
            ledger=staged_ledger,
            archive=staged_archive,
            runtime=model_runtime,
            model_run_id_factory=model_run_id_factory,
        )
    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=parent_sha256,
        bundle=bundle,
        coreference_proposer=coreference_proposer,
        coreference_tokenizer=coreference_tokenizer,
        semantic_reference_challenger=challenger,
    )
    payload = canonical_hybrid_reference_preview_bytes(preview)
    digest = hybrid_reference_preview_sha256(preview)
    archive.put_hybrid_reference_preview(preview, payload, digest)
    return HybridReferencePreviewResult(
        preview=preview,
        sha256=digest,
        archive_path=f"extraction/reference-previews/{preview.id}.json",
    )


class _SemanticReferenceSchemaRegistry:
    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id == SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id=schema_id,
                canonical_schema_bytes=semantic_reference_challenge_schema_bytes(),
                output_contract_version=SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID,
                parse=parse_semantic_reference_challenge_output,
            )
        if schema_id == SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id=schema_id,
                canonical_schema_bytes=semantic_reference_candidate_validation_schema_bytes(),
                output_contract_version=SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID,
                parse=parse_semantic_reference_candidate_validation_output,
            )
        raise ValueError(f"Unsupported semantic-reference task schema: {schema_id}")


@dataclass(frozen=True)
class _BoundedReferenceChallenger:
    source_id: str
    document_id: str
    representation_id: str
    selection_manifest: ContextManifest
    validation_manifest: ContextManifest
    generation_parameters: tuple[ExecutionSetting, ...]
    selection_prompt_bytes: bytes
    validation_prompt_bytes: bytes
    ledger: HybridReferenceLedger
    archive: HybridReferenceArchive
    runtime: ModelTaskRuntime
    model_run_id_factory: ModelRunIdFactory

    def validate(
        self, request: SemanticReferenceCandidateValidationInput
    ) -> SemanticReferenceCandidateValidationExecution:
        registry: TaskSchemaRegistry = _SemanticReferenceSchemaRegistry()
        schema = registry.resolve(SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID)
        task_input = semantic_reference_candidate_validation_task_input(request)
        outcome, rendered = self._run(
            manifest=self.validation_manifest,
            prompt_bytes=self.validation_prompt_bytes,
            schema=schema,
            task_input=task_input,
            task_type="semantic_reference_specialist_validation",
            validator_version="semantic_reference_candidate_validation_validator_v1",
            input_candidate_ids=(request.antecedent_candidate.id,),
            registry=registry,
        )
        return SemanticReferenceCandidateValidationExecution(
            validation=outcome.semantic_reference_candidate_validation,
            candidate_id=request.antecedent_candidate.id,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            model_status=outcome.model_run.status,
            producer_id=self.runtime.configured_identity.name,
            model_visible_task=rendered,
            raw_output_sha256=outcome.model_run.output_digest,
        )

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution:
        registry: TaskSchemaRegistry = _SemanticReferenceSchemaRegistry()
        schema = registry.resolve(SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID)
        candidate_label_bindings = _semantic_reference_candidate_label_bindings(request)
        task_input = _semantic_reference_challenge_task_input(
            request,
            candidate_label_bindings,
        )
        outcome, rendered = self._run(
            manifest=self.selection_manifest,
            prompt_bytes=self.selection_prompt_bytes,
            schema=schema,
            task_input=task_input,
            task_type=f"semantic_reference_{request.mode.value}",
            validator_version="semantic_reference_challenge_validator_v3",
            input_candidate_ids=tuple(item.id for item in request.antecedent_candidates),
            registry=registry,
        )
        return SemanticReferenceChallengeExecution(
            selection=outcome.semantic_reference_challenge,
            candidate_label_bindings=candidate_label_bindings,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            model_status=outcome.model_run.status,
            producer_id=self.runtime.configured_identity.name,
            model_visible_task=rendered,
            raw_output_sha256=outcome.model_run.output_digest,
            mode=request.mode,
        )

    def _run(
        self,
        *,
        manifest: ContextManifest,
        prompt_bytes: bytes,
        schema: PinnedTaskSchema,
        task_input: bytes,
        task_type: str,
        validator_version: str,
        input_candidate_ids: tuple[str, ...],
        registry: TaskSchemaRegistry,
    ) -> tuple[BoundedExtractionOutcome, bytes]:
        rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=self.source_id,
                document_id=self.document_id,
                representation_id=self.representation_id,
                context_manifest_id=manifest.id,
                prompt_bytes=prompt_bytes,
                execution_spec=ModelExecutionSpec(
                    model_profile_id=manifest.model_profile_id,
                    model_identity=self.runtime.configured_identity,
                    generation_parameters=self.generation_parameters,
                    prompt_id=manifest.prompt_id,
                    prompt_digest=manifest.prompt_digest,
                    schema_id=schema.schema_id,
                    schema_digest=schema.digest,
                    context_manifest_id=manifest.id,
                    context_manifest_digest=manifest.manifest_digest,
                    rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
                    output_contract_version=schema.output_contract_version,
                ),
                validator_version=validator_version,
                task_type=task_type,
                input_candidate_ids=input_candidate_ids,
                task_local_input=task_input,
            ),
            self.ledger,
            self.archive,
            self.runtime,
            self.model_run_id_factory,
            self.runtime,
            registry,
        )
        return outcome, rendered


def _reference_manifest(
    parent_manifest_id: str,
    bundle: DocumentRepresentationBundle,
    profile: ContextModelProfile,
    *,
    prompt_id: str,
    prompt_bytes: bytes,
    schema_id: str,
    schema_bytes: bytes,
    renderer_version: str,
    ledger: HybridReferenceLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    parent = load_context_manifest(parent_manifest_id, ledger, verified_bundle=bundle)
    unit = load_analysis_unit(parent.analysis_unit_id, ledger)
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id=prompt_id,
            prompt_bytes=prompt_bytes,
            schema_id=schema_id,
            schema_bytes=schema_bytes,
            renderer_version=renderer_version,
            evidence_selection_policy_id=parent.evidence_selection_policy_id,
            source_segment_policy_id=parent.source_segment_policy_id,
            source_segment_label=parent.source_segment_label,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "HP-2 semantic-reference ContextManifest is not ready: "
            f"{planning.manifest.blocked_reason or planning.manifest.status.value}"
        )
    verify_context_manifest(planning.manifest.id, ledger, tokenizer, prompt_bytes, schema_bytes)
    return planning.manifest


def semantic_reference_challenge_task_input(
    request: SemanticReferenceChallengeInput,
) -> bytes:
    """Render one visibly delimited target and its source-owned candidate choices."""
    return _semantic_reference_challenge_task_input(
        request,
        _semantic_reference_candidate_label_bindings(request),
    )


def semantic_reference_candidate_validation_task_input(
    request: SemanticReferenceCandidateValidationInput,
) -> bytes:
    """Render one target and exactly one source-owned specialist candidate."""
    candidate = request.antecedent_candidate
    before, after = _candidate_occurrence_context(request.source_text, candidate)
    lines = [
        "task: validate_one_specialist_antecedent",
        f"source_context_before_target: {request.source_text[: request.target_span.start]}",
        f"target_reference: {request.target_span.text}",
        f"source_context_after_target: {request.source_text[request.target_span.end :]}",
        f"candidate_expression: {json.dumps(candidate.span.text, ensure_ascii=False)}",
        f"candidate_context_before: {json.dumps(before, ensure_ascii=False)}",
        f"candidate_context_after: {json.dumps(after, ensure_ascii=False)}",
        "legal_verdicts: supported, unsupported, unclear",
        f"validate_only_target: {request.target_span.text}",
    ]
    return "\n".join(lines).encode()


def _semantic_reference_challenge_task_input(
    request: SemanticReferenceChallengeInput,
    candidate_label_bindings: tuple[SemanticReferenceCandidateLabelBinding, ...],
) -> bytes:
    left_context = request.source_text[: request.target_span.start]
    right_context = request.source_text[request.target_span.end :]
    lines = [
        "task: resolve_one_semantic_reference",
        f"source_context_before_target: {left_context}",
        f"target_reference: {request.target_span.text}",
        f"source_context_after_target: {right_context}",
        "antecedent_candidate_catalog:",
    ]
    lines.extend(
        _semantic_reference_candidate_catalog_line(
            source_text=request.source_text,
            binding=binding,
            candidate=candidate,
        )
        for binding, candidate in zip(
            candidate_label_bindings,
            request.antecedent_candidates,
            strict=True,
        )
    )
    legal_outcomes = [
        *(item.label for item in candidate_label_bindings),
        "unresolved",
    ]
    if len(request.antecedent_candidates) >= 2:
        legal_outcomes.append("ambiguous")
    lines.append(f"legal_outcomes: {', '.join(legal_outcomes)}")
    lines.append(f"resolve_only_target: {request.target_span.text}")
    return "\n".join(lines).encode()


def _semantic_reference_candidate_catalog_line(
    *,
    source_text: str,
    binding: SemanticReferenceCandidateLabelBinding,
    candidate: CoreferenceAntecedentCandidate,
) -> str:
    before, after = _candidate_occurrence_context(source_text, candidate)
    return (
        f"{binding.label} | expression="
        f"{json.dumps(candidate.span.text, ensure_ascii=False)} | before="
        f"{json.dumps(before, ensure_ascii=False)} | after="
        f"{json.dumps(after, ensure_ascii=False)}"
    )


def _candidate_occurrence_context(
    source_text: str,
    candidate: CoreferenceAntecedentCandidate,
) -> tuple[str, str]:
    before = source_text[
        max(0, candidate.span.start - _CANDIDATE_CONTEXT_CHARACTER_LIMIT) : candidate.span.start
    ]
    after = source_text[
        candidate.span.end : candidate.span.end + _CANDIDATE_CONTEXT_CHARACTER_LIMIT
    ]
    return before, after


def _semantic_reference_candidate_label_bindings(
    request: SemanticReferenceChallengeInput,
) -> tuple[SemanticReferenceCandidateLabelBinding, ...]:
    return tuple(
        SemanticReferenceCandidateLabelBinding(
            label=f"a{ordinal}",
            candidate_id=candidate.id,
        )
        for ordinal, candidate in enumerate(request.antecedent_candidates, start=1)
    )


def _source_id(bundle: DocumentRepresentationBundle, ledger: HybridReferenceLedger) -> str:
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-2 representation references a missing Document.")
    return document.source_id
