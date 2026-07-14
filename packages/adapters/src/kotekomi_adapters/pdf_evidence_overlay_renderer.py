"""Subprocess-isolated PDFium renderer for reviewer evidence overlays."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from importlib.metadata import version

from kotekomi_application import (
    PdfEvidenceOverlaySpec,
    PdfPixelRectangle,
    RenderedPdfEvidenceOverlay,
)


class PdfiumEvidenceOverlayRenderer:
    def __init__(self, scale: float = 2.0, timeout_seconds: float = 60.0) -> None:
        if scale <= 0 or timeout_seconds <= 0:
            raise ValueError("PDF evidence overlay scale and timeout must be positive.")
        self._scale = scale
        self._timeout_seconds = timeout_seconds

    def render(
        self, spec: PdfEvidenceOverlaySpec, archived_pdf_bytes: bytes
    ) -> RenderedPdfEvidenceOverlay:
        request = {
            "pdf_bytes": base64.b64encode(archived_pdf_bytes).decode("ascii"),
            "page_number": spec.page_number,
            "scale": self._scale,
            "rectangles": [
                {
                    "left": rectangle.left,
                    "top": rectangle.top,
                    "right": rectangle.right,
                    "bottom": rectangle.bottom,
                }
                for rectangle in spec.rectangles
            ],
        }
        environment = {
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "kotekomi_adapters.pdf_evidence_overlay_worker"],
                input=json.dumps(request, separators=(",", ":")).encode(),
                capture_output=True,
                check=False,
                env=environment,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("PDF evidence overlay worker did not complete.") from exc
        if completed.returncode != 0:
            raise RuntimeError("PDF evidence overlay worker failed.")
        try:
            response = json.loads(completed.stdout)
            image_width = int(response["image_width"])
            image_height = int(response["image_height"])
            png_bytes = base64.b64decode(response["png_bytes"], validate=True)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("PDF evidence overlay worker returned an invalid result.") from exc
        expected_width = round(spec.page_width * self._scale)
        expected_height = round(spec.page_height * self._scale)
        if image_width != expected_width or image_height != expected_height:
            raise ValueError("Rendered PDF dimensions disagree with authoritative page geometry.")
        pixel_rectangles = tuple(
            PdfPixelRectangle(
                rectangle.source_region_id,
                round(rectangle.left * self._scale),
                round(rectangle.top * self._scale),
                round(rectangle.right * self._scale),
                round(rectangle.bottom * self._scale),
            )
            for rectangle in spec.rectangles
        )
        return RenderedPdfEvidenceOverlay(
            spec=spec,
            renderer_id=f"pypdfium2_overlay_v1:{version('pypdfium2')}:scale={self._scale}",
            image_width=image_width,
            image_height=image_height,
            pixel_rectangles=pixel_rectangles,
            png_bytes=png_bytes,
            png_digest=hashlib.sha256(png_bytes).hexdigest(),
        )
