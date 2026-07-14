"""Native PDFium worker for one reviewer overlay render."""
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import base64
import json
import sys
from io import BytesIO
from typing import Any, cast

import pypdfium2 as pdfium  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image, ImageDraw


def main() -> None:
    payload = cast(dict[str, Any], json.loads(sys.stdin.buffer.read()))
    pdf_bytes = base64.b64decode(str(payload["pdf_bytes"]), validate=True)
    page_number = int(payload["page_number"])
    scale = float(payload["scale"])
    rectangles = cast(list[dict[str, float]], payload["rectangles"])
    pdf = pdfium.PdfDocument(BytesIO(pdf_bytes))
    if page_number < 1 or page_number > len(pdf):
        raise ValueError("PDF evidence overlay page is absent from archived bytes.")
    page = cast(Any, pdf[page_number - 1])
    bitmap = page.render(scale=scale)
    image = cast(Image.Image, bitmap.to_pil().convert("RGB"))
    draw = ImageDraw.Draw(image)
    for rectangle in rectangles:
        draw.rectangle(
            (
                round(rectangle["left"] * scale),
                round(rectangle["top"] * scale),
                round(rectangle["right"] * scale),
                round(rectangle["bottom"] * scale),
            ),
            outline=(255, 0, 0),
            width=max(2, round(scale * 2)),
        )
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    sys.stdout.write(
        json.dumps(
            {
                "image_width": image.width,
                "image_height": image.height,
                "png_bytes": base64.b64encode(output.getvalue()).decode("ascii"),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
