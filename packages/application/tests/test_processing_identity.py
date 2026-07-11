from kotekomi_application import BuildIdentity, processing_task_fingerprint


def _task(
    *,
    input_digest: str = "a" * 64,
    processor_version: str = "1",
    processor_config_digest: str = "b" * 64,
    build_identity: BuildIdentity | None = None,
    policy_id: str = "policy_1",
    output_contract_version: str = "1",
):
    return processing_task_fingerprint(
        task_kind="fixture_task",
        document_id="doc_fixture",
        blob_id="blb_fixture",
        input_digest=input_digest,
        processor_name="fixture",
        processor_version=processor_version,
        processor_config_digest=processor_config_digest,
        build_identity=build_identity or BuildIdentity("package", "revision", "c" * 64, "1"),
        policy_id=policy_id,
        output_contract_version=output_contract_version,
    )


def test_processing_task_fingerprint_is_stable_for_equal_work() -> None:
    assert _task() == _task()


def test_processing_task_fingerprint_changes_for_every_identity_dimension() -> None:
    original = _task()
    variants = (
        _task(input_digest="d" * 64),
        _task(processor_version="2"),
        _task(processor_config_digest="e" * 64),
        _task(build_identity=BuildIdentity("package", "revision-2", "c" * 64, "1")),
        _task(policy_id="policy_2"),
        _task(output_contract_version="2"),
    )

    assert all(variant.id != original.id for variant in variants)
    assert all(variant.fingerprint_digest != original.fingerprint_digest for variant in variants)
