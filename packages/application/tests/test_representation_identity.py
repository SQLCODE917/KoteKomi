from kotekomi_application import deterministic_representation_id


def test_representation_identity_derives_from_task_and_output_role() -> None:
    original_id = deterministic_representation_id("ptf_representation_fixture")

    assert deterministic_representation_id("ptf_representation_fixture") == original_id
    assert deterministic_representation_id("ptf_other") != original_id
    assert deterministic_representation_id("ptf_representation_fixture", "verbatim") != original_id
