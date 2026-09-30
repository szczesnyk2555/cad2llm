"""DXF: units, extents, dimensions, circles, arcs, line/polyline lengths, texts, layers (ezdxf)."""
import math
from collections import Counter
from pathlib import Path

from . import CadError, rnd

# $INSUNITS codes
UNITS = {0: "unitless", 1: "inch", 2: "feet", 4: "mm", 5: "cm", 6: "m"}
MAX_ITEMS = 100  # keep the JSON compact for the model


def _entities(layout):
    """All entities, with geometry inside block references (INSERT) expanded."""
    for e in layout:
        if e.dxftype() == "INSERT":
            try:
                yield from _entities(e.virtual_entities())
            except Exception:
                continue
        else:
            yield e


def _counted(values) -> dict[str, int]:
    counts = Counter(round(v, 3) for v in values)
    return {str(k): n for k, n in sorted(counts.items())[:MAX_ITEMS]}


def extract(path: Path, image: bool = True) -> tuple[dict, bytes | None]:
    import ezdxf
    from ezdxf import bbox

    try:
        doc = ezdxf.readfile(path)
    except (IOError, ezdxf.DXFStructureError) as e:
        raise CadError(f"Cannot read DXF file {path.name}: {e}") from e
    msp = doc.modelspace()

    dims, circles, arcs, lines, polylines, texts = [], [], [], [], [], []
    for e in _entities(msp):
        t = e.dxftype()
        if t == "DIMENSION":
            try:
                value = e.get_measurement()
                value = value if isinstance(value, (int, float)) else math.degrees(value.angle)
            except Exception:
                value = None
            override = e.dxf.get("text", "")
            dims.append({"value": value, "text": override if override not in ("", "<>") else None})
        elif t == "CIRCLE":
            circles.append(2 * e.dxf.radius)
        elif t == "ARC":
            arcs.append(e.dxf.radius)
        elif t == "LINE":
            lines.append(e.dxf.start.distance(e.dxf.end))
        elif t == "LWPOLYLINE":
            pts = [p[:2] for p in e.get_points("xy")]
            if e.closed and pts:
                pts.append(pts[0])
            polylines.append([math.dist(a, b) for a, b in zip(pts, pts[1:])])  # straight segments (bulges as chords)
        elif t == "TEXT":
            texts.append(e.dxf.text)
        elif t == "MTEXT":
            texts.append(e.plain_text())

    ext = bbox.extents(msp)
    size = ext.size if ext.has_data else None
    data = {
        "file": path.name,
        "format": "DXF",
        "units": UNITS.get(doc.header.get("$INSUNITS", 0), f"code {doc.header.get('$INSUNITS')}"),
        "extents": {"width": size.x, "height": size.y} if size else None,
        "dimensions": dims[:MAX_ITEMS],
        "circle_diameters": _counted(circles),     # diameter -> count
        "arc_radii": _counted(arcs),               # radius -> count
        "line_lengths": _counted(lines),           # length -> count
        "polyline_segments": [p for p in polylines[:MAX_ITEMS]],
        "texts": [s.strip() for s in texts if s.strip()][:MAX_ITEMS],
        "layers": sorted(layer.dxf.name for layer in doc.layers),
    }

    png = None
    if image:
        from .render import render_dxf
        png = render_dxf(doc)
    return rnd(data), png
