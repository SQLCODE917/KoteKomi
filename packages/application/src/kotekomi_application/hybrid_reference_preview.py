"""HP-2 orchestration over one immutable HP-1 Preview."""

from __future__ import annotations

import hashlib
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
from kotekomi_application.semantic_references import (
    CoreferenceProposerPort,
    CoreferenceTokenizer,
    SemanticReferenceChallengeExecution,
    SemanticReferenceChallengeInput,
    SemanticReferenceChallengerPort,
)
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
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

SEMANTIC_REFERENCE_CHALLENGE_PROMPT_ID = "semantic_reference_challenge_v1"
SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID = "semantic_reference_challenge_text_v1"


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
    )
    if coreference_proposer is not None and any(value is None for value in challenge_values):
        raise ValueError(
            "HP-2 semantic coreference requires model profile, runtime, run IDs, and prompt."
        )
    challenger: SemanticReferenceChallengerPort | None = None
    if coreference_proposer is not None:
        assert command.model_profile is not None
        assert model_runtime is not None
        assert model_run_id_factory is not None
        assert challenge_prompt_bytes is not None
        staged_ledger = cast(HybridReferenceLedger, ledger)
        staged_archive = cast(HybridReferenceArchive, archive)
        challenger = _BoundedReferenceChallenger(
            source_id=_source_id(bundle, staged_ledger),
            document_id=bundle.representation.document_id,
            representation_id=bundle.representation.id,
            manifest=_challenge_manifest(
                parent.context_manifest_id,
                bundle,
                command.model_profile,
                challenge_prompt_bytes,
                staged_ledger,
                model_runtime,
            ),
            generation_parameters=command.generation_parameters,
            prompt_bytes=challenge_prompt_bytes,
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


class _ReferenceChallengeSchemaRegistry:
    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID:
            raise ValueError(f"Unsupported semantic-reference challenge schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=schema_id,
            canonical_schema_bytes=semantic_reference_challenge_schema_bytes(),
            output_contract_version=SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID,
            parse=parse_semantic_reference_challenge_output,
        )


@dataclass(frozen=True)
class _BoundedReferenceChallenger:
    source_id: str
    document_id: str
    representation_id: str
    manifest: ContextManifest
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_bytes: bytes
    ledger: HybridReferenceLedger
    archive: HybridReferenceArchive
    runtime: ModelTaskRuntime
    model_run_id_factory: ModelRunIdFactory

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution:
        registry: TaskSchemaRegistry = _ReferenceChallengeSchemaRegistry()
        schema = registry.resolve(SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID)
        task_input = _challenge_task_input(request)
        rendered = self.manifest.rendered_input + b"\n\n[task]\n" + task_input
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=self.source_id,
                document_id=self.document_id,
                representation_id=self.representation_id,
                context_manifest_id=self.manifest.id,
                prompt_bytes=self.prompt_bytes,
                execution_spec=ModelExecutionSpec(
                    model_profile_id=self.manifest.model_profile_id,
                    model_identity=self.runtime.configured_identity,
                    generation_parameters=self.generation_parameters,
                    prompt_id=self.manifest.prompt_id,
                    prompt_digest=self.manifest.prompt_digest,
                    schema_id=schema.schema_id,
                    schema_digest=schema.digest,
                    context_manifest_id=self.manifest.id,
                    context_manifest_digest=self.manifest.manifest_digest,
                    rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
                    output_contract_version=schema.output_contract_version,
                ),
                validator_version="semantic_reference_challenge_validator_v1",
                task_type="semantic_reference_challenge",
                input_candidate_ids=tuple(item.id for item in request.antecedent_candidates),
                task_local_input=task_input,
            ),
            self.ledger,
            self.archive,
            self.runtime,
            self.model_run_id_factory,
            self.runtime,
            registry,
        )
        return SemanticReferenceChallengeExecution(
            selection=outcome.semantic_reference_challenge,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            model_status=outcome.model_run.status,
            producer_id=self.runtime.configured_identity.name,
            model_visible_task=rendered,
            raw_output_sha256=outcome.model_run.output_digest,
        )


def _challenge_manifest(
    parent_manifest_id: str,
    bundle: DocumentRepresentationBundle,
    profile: ContextModelProfile,
    prompt_bytes: bytes,
    ledger: HybridReferenceLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    parent = load_context_manifest(parent_manifest_id, ledger, verified_bundle=bundle)
    unit = load_analysis_unit(parent.analysis_unit_id, ledger)
    schema = semantic_reference_challenge_schema_bytes()
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id=SEMANTIC_REFERENCE_CHALLENGE_PROMPT_ID,
            prompt_bytes=prompt_bytes,
            schema_id=SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID,
            schema_bytes=schema,
            renderer_version="semantic_reference_challenge_context_v1",
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
    verify_context_manifest(planning.manifest.id, ledger, tokenizer, prompt_bytes, schema)
    return planning.manifest


def _challenge_task_input(request: SemanticReferenceChallengeInput) -> bytes:
    lines = [
        "task: resolve_one_semantic_reference",
        f"source_context: {request.source_text}",
        f"target_reference: {request.target_span.text}",
        "antecedent_candidate_catalog:",
    ]
    lines.extend(f"{item.id} | {item.span.text}" for item in request.antecedent_candidates)
    lines.append(f"resolve_only_target: {request.target_span.text}")
    return "\n".join(lines).encode()


def _source_id(bundle: DocumentRepresentationBundle, ledger: HybridReferenceLedger) -> str:
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-2 representation references a missing Document.")
    return document.source_id
