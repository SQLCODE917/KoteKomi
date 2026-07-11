from dataclasses import replace

from kotekomi_application import RepresentationFingerprintInput, deterministic_representation_id


def fingerprint(**changes: str) -> RepresentationFingerprintInput:
    values = {
        "document_id": "doc_representation_fixture",
        "input_blob_digest": "a" * 64,
        "parser_name": "fixture_parser",
        "parser_version": "1",
        "parser_config_digest": "b" * 64,
        "code_revision": "test",
        "representation_schema_version": "1",
    }
    values.update(changes)
    return RepresentationFingerprintInput(**values)


def test_representation_identity_changes_for_every_semantic_fingerprint_field() -> None:
    original = fingerprint()
    original_id = deterministic_representation_id(original)

    assert deterministic_representation_id(original) == original_id
    assert (
        deterministic_representation_id(replace(original, document_id="doc_other"))
        != original_id
    )
    assert (
        deterministic_representation_id(replace(original, input_blob_digest="c" * 64))
        != original_id
    )
    assert (
        deterministic_representation_id(replace(original, parser_name="other_parser"))
        != original_id
    )
    assert deterministic_representation_id(replace(original, parser_version="2")) != original_id
    assert (
        deterministic_representation_id(replace(original, parser_config_digest="d" * 64))
        != original_id
    )
    assert deterministic_representation_id(replace(original, code_revision="other")) != original_id
    assert deterministic_representation_id(
        replace(original, representation_schema_version="2")
    ) != original_id
