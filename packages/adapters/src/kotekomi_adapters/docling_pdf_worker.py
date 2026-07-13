"""Large-stack subprocess entry point for one authoritative Docling PDF conversion."""
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime

from kotekomi_application.pdf_ingest import PdfParseInput
from kotekomi_domain import Document

from kotekomi_adapters.docling_pdf_parser import (
    DoclingPdfParser,
    DoclingPdfParserConfig,
    _pdf_parse_result_to_payload,
    _raise_stack_limit_for_docling_import,
)


def main() -> None:
    _raise_stack_limit_for_docling_import()
    payload = json.loads(sys.stdin.buffer.read())
    if not isinstance(payload, dict):
        raise ValueError("Docling worker request must be an object.")
    document_payload = payload["document"]
    config_payload = payload["config"]
    if not isinstance(document_payload, dict) or not isinstance(config_payload, dict):
        raise ValueError("Docling worker request is malformed.")
    parse_input = PdfParseInput(
        document=Document.model_validate_json(json.dumps(document_payload)),
        raw_bytes=base64.b64decode(payload["raw_bytes_base64"], validate=True),
        policy_id=str(payload["policy_id"]),
        processing_task_fingerprint_id=str(payload["processing_task_fingerprint_id"]),
        parsed_at=datetime.fromisoformat(str(payload["parsed_at"])),
    )
    parser = DoclingPdfParser(
        DoclingPdfParserConfig(
            enable_ocr=bool(config_payload["enable_ocr"]),
            enable_table_structure=bool(config_payload["enable_table_structure"]),
            ocr_language=str(config_payload["ocr_language"]),
            ocr_render_scale=int(config_payload["ocr_render_scale"]),
            ocr_text_score=float(config_payload["ocr_text_score"]),
        )
    )
    result = parser.parse(parse_input)
    sys.stdout.write(json.dumps(_pdf_parse_result_to_payload(result), separators=(",", ":")))


if __name__ == "__main__":
    main()
