"""cad2llm - extract measurements from CAD files and drawings (STEP, DXF, PDF) and ask an OpenAI model to describe the part."""
from pathlib import Path

SUPPORTED = {".step": "step", ".stp": "step", ".dxf": "dxf", ".pdf": "pdf"}


class CadError(Exception):
    """Unsupported file or parse failure - message is shown to the user as-is."""


def analyze(path: str | Path, image: bool = True) -> tuple[dict, bytes | None]:
    """Returns (measurements, preview PNG or None). Format is detected by extension."""
    path = Path(path)
    kind = SUPPORTED.get(path.suffix.lower())
    if kind is None:
        hint = " Convert DWG to DXF first." if path.suffix.lower() == ".dwg" else ""
        raise CadError(f"Unsupported file type '{path.suffix}'. Use .step, .stp, .dxf or .pdf.{hint}")

    if kind == "step":
        from . import step_extract as mod
    elif kind == "dxf":
        from . import dxf_extract as mod
    else:
        from . import pdf_extract as mod
    return mod.extract(path, image=image)


def rnd(value):
    """Round all floats in a nested structure to 3 decimals."""
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {k: rnd(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [rnd(v) for v in value]
    return value
