"""PDF drawings: page sizes, text layer, dimension-like values found in the text, preview of the first page (PyMuPDF).

A PDF exported from CAD has a text layer (dimensions, title block, notes) - those values are exact.
A scanned PDF has none: only the image goes to the model, which then reads values from the picture.
"""
import re
from collections import Counter
from pathlib import Path

from . import CadError, rnd

PT_TO_MM = 25.4 / 72
MAX_TEXT = 6000     # characters of raw text sent to the model
MAX_ITEMS = 100

NUM = r"\d+(?:[.,]\d+)?"
PATTERNS = {
    "diameters": rf"[Ø⌀∅] ?{NUM}(?:[A-Za-z]{{1,2}}\d{{1,2}})?",                 # Ø40, Ø25h6
    "radii": rf"(?<![A-Za-z])R ?{NUM}",
    "threads": rf"(?<![A-Za-z])M{NUM}(?: ?[x×] ?{NUM})?",
    "fits": r"(?<=\d)[A-HJKMNPR-Za-hjkmnpr-wyz]{1,2}\d{1,2}(?![\d°])",            # 25h6, 12H7 (ISO 286 letters)
    "tolerances": rf"± ?{NUM}|[+-]{NUM} ?/ ?[+-]?{NUM}",
    "roughness": rf"R[az] ?{NUM}",
    "chamfers": rf"{NUM} ?[x×] ?{NUM} ?°",
    "angles": rf"(?<![\d.,x×]){NUM} ?°",
}


def _found(text: str) -> dict[str, dict[str, int]]:
    out = {}
    for key, pattern in PATTERNS.items():
        counts = Counter(re.sub(r"\s+", "", m).replace(",", ".") for m in re.findall(pattern, text))
        if counts:
            out[key] = dict(counts.most_common(MAX_ITEMS))
    return out


def extract(path: Path, image: bool = True) -> tuple[dict, bytes | None]:
    import pymupdf

    if path.read_bytes()[:5] != b"%PDF-":
        raise CadError(f"{path.name} is not a PDF file.")
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        raise CadError(f"Cannot read PDF file {path.name}: {e}") from e

    pages, texts, vector_items, images = [], [], 0, 0
    for page in doc:
        pages.append({"width_mm": page.rect.width * PT_TO_MM, "height_mm": page.rect.height * PT_TO_MM})
        texts.append(page.get_text().strip())
        vector_items += len(page.get_drawings())
        images += len(page.get_images())
    text = "\n".join(t for t in texts if t)

    data = {
        "file": path.name,
        "format": "PDF",
        "units": "mm (as written on the drawing)",
        "pages": len(pages),
        "page_sizes_mm": pages,
        "text_layer": bool(text),
        "kind": "vector drawing (exported from CAD)" if vector_items and text else
                "scan / image only - values must be read from the picture" if not text else "text document",
        "vector_items": vector_items,
        "images": images,
        "found_in_text": _found(text),
        "text": text[:MAX_TEXT],
    }

    png = None
    if image and len(doc):
        page = doc[0]
        zoom = min(2.0, 2400 / max(page.rect.width, page.rect.height))  # ~2400 px on the long side
        png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")
    doc.close()
    return rnd(data), png
