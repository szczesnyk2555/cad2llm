"""STEP/STP: units, bounding box, volume, area, face/edge counts, cylinder diameters (cadquery / OpenCascade)."""
import re
from collections import Counter
from pathlib import Path

from . import CadError, rnd


def declared_units(raw: str) -> str:
    """Length unit declared in the STEP header (the geometry itself is normalized to mm on import)."""
    if re.search(r"CONVERSION_BASED_UNIT\s*\(\s*'INCH'", raw, re.I):
        return "inch"
    m = re.search(r"SI_UNIT\s*\(\s*(\.\w+\.|\$)\s*,\s*\.METRE\.\s*\)", raw, re.I)
    if m:
        prefix = m.group(1).strip(".").upper()
        return {"$": "m", "MILLI": "mm", "CENTI": "cm", "MICRO": "um"}.get(prefix, prefix.lower() + "m")
    return "unknown"


def _diameters(shape) -> dict[float, int]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    counts: Counter = Counter()
    for face in shape.Faces():
        if face.geomType() == "CYLINDER":
            counts[round(2 * BRepAdaptor_Surface(face.wrapped).Cylinder().Radius(), 3)] += 1
    return dict(sorted(counts.items()))


def _volume(shape) -> float:
    """Sum over the solids rather than shape.Volume(): cadquery 2.8 raises
    StopIteration on a compound whose first child is an empty compound (an empty
    sub-assembly, which some CAD exporters write). Same number otherwise."""
    return sum(s.Volume() for s in shape.Solids())


def _measure(shape) -> dict:
    bb = shape.BoundingBox()
    return {
        "bounding_box_mm": {"x": bb.xlen, "y": bb.ylen, "z": bb.zlen},
        "volume_mm3": _volume(shape),
        "surface_area_mm2": shape.Area(),
        "faces": len(shape.Faces()),
        "edges": len(shape.Edges()),
        # diameter -> number of cylindrical faces with it (holes, shafts, fillets on round parts)
        "cylinder_diameters_mm": {str(d): n for d, n in _diameters(shape).items()},
    }


def extract(path: Path, image: bool = True) -> tuple[dict, bytes | None]:
    import cadquery as cq

    raw = path.read_text(errors="ignore")
    if "ISO-10303-21" not in raw[:200]:
        raise CadError(f"{path.name} is not a STEP file (missing ISO-10303-21 header).")
    try:
        shape = cq.importers.importStep(str(path)).val()
    except Exception as e:  # OCP raises plain exceptions with little detail
        raise CadError(f"Cannot read STEP file {path.name}: {e}") from e

    solids = shape.Solids()
    data = {
        "file": path.name,
        "format": "STEP",
        "declared_units": declared_units(raw),
        "output_units": "mm (geometry is normalized to millimetres on import)",
        "solids": len(solids),
        **_measure(shape),
    }
    if len(solids) > 1:
        data["per_solid"] = [_measure(s) for s in solids]

    png = None
    if image:
        from .render import render_shape
        png = render_shape(shape)
    return rnd(data), png
