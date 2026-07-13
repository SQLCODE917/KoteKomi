"""Large-stack subprocess entry point for one authoritative Docling PDF conversion."""
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from typing import cast

from kotekomi_application.pdf_ingest import PdfAccessCredential, PdfParseInput, PdfProcessingError
from kotekomi_domain import Document

from kotekomi_adapters.docling_pdf_parser import (
    DoclingPdfParser,
    DoclingPdfParserConfig,
    _pdf_parse_result_to_payload,
    _raise_stack_limit_for_docling_import,
)


def main() -> None:
    _raise_stack_limit_for_docling_import()
    raw_payload: object = json.loads(sys.stdin.buffer.read())
    if not isinstance(raw_payload, dict):
        raise ValueError("Docling worker request must be an object.")
    payload = cast(dict[str, object], raw_payload)
    document_payload = payload["document"]
    config_payload = payload["config"]
    if not isinstance(document_payload, dict) or not isinstance(config_payload, dict):
        raise ValueError("Docling worker request is malformed.")
    document_payload = cast(dict[str, object], document_payload)
    config_payload = cast(dict[str, object], config_payload)
    credential_payload = payload.get("access_credential")
    if credential_payload is not None and not isinstance(credential_payload, dict):
        raise ValueError("Docling worker credential envelope is malformed.")
    credential_payload = cast(dict[str, object] | None, credential_payload)
    parse_input = PdfParseInput(
        document=Document.model_validate_json(json.dumps(document_payload)),
        raw_bytes=base64.b64decode(str(payload["raw_bytes_base64"]), validate=True),
        policy_id=str(payload["policy_id"]),
        processing_task_fingerprint_id=str(payload["processing_task_fingerprint_id"]),
        parsed_at=datetime.fromisoformat(str(payload["parsed_at"])),
        access_credential=(
            PdfAccessCredential(
                credential_id=str(credential_payload["credential_id"]),
                password=str(credential_payload["password"]),
            )
            if credential_payload is not None
            else None
        ),
        expected_processor_config_digest=(
            str(payload["expected_processor_config_digest"])
            if payload.get("expected_processor_config_digest") is not None
            else None
        ),
    )
    parser = DoclingPdfParser(
        DoclingPdfParserConfig(
            enable_ocr=bool(config_payload["enable_ocr"]),
            enable_table_structure=bool(config_payload["enable_table_structure"]),
            ocr_language=str(config_payload["ocr_language"]),
            ocr_render_scale=int(str(config_payload["ocr_render_scale"])),
            ocr_text_score=float(str(config_payload["ocr_text_score"])),
            worker_timeout_seconds=float(str(config_payload["worker_timeout_seconds"])),
        )
    )
    result = parser.parse(parse_input)
    sys.stdout.write(json.dumps(_pdf_parse_result_to_payload(result), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except PdfProcessingError as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "error": {
                        "code": exc.code,
                        "failure_type": exc.failure_type,
                        "safe_message": exc.safe_message,
                        "retryable": exc.retryable,
                    }
                },
                separators=(",", ":"),
            )
        )
    except Exception as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "error": {
                        "code": "pdf_parser_failure",
                        "failure_type": type(exc).__name__,
                        "safe_message": "PDF parser worker failed before producing a result.",
                        "retryable": True,
                    }
                },
                separators=(",", ":"),
            )
        )
