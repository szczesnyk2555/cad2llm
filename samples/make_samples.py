"""Generates the sample files: flange.step (cadquery) and plate.dxf (ezdxf). Run: python samples/make_samples.py"""
from pathlib import Path

import cadquery as cq
import ezdxf

HERE = Path(__file__).parent

# Flange: Ø80 x 12 disc, Ø40 x 20 hub, Ø22 bore, 4x Ø9 holes on a Ø60 bolt circle
flange = (
    cq.Workplane("XY").circle(40).extrude(12)
    .faces(">Z").workplane().circle(20).extrude(20)
    .faces(">Z").workplane().hole(22)
    .faces("<Z").workplane().polarArray(30, 45, 360, 4).hole(9)
)
cq.exporters.export(flange, str(HERE / "flange.step"))

# Plate 120 x 80 mm with 4x Ø10 holes, a Ø30 centre hole, R5 corners, dimensions and a title
doc = ezdxf.new(setup=True, units=ezdxf.units.MM)
msp = doc.modelspace()
doc.layers.add("CONTOUR")
doc.layers.add("DIMS")
w, h, r = 120, 80, 5
DIM = {"dimtxt": 4, "dimasz": 3, "dimexe": 1.5, "dimgap": 1, "dimlfac": 1}  # readable text / arrows at 1:1
msp.add_lwpolyline([(r, 0), (w - r, 0)], dxfattribs={"layer": "CONTOUR"})
msp.add_lwpolyline([(w, r), (w, h - r)], dxfattribs={"layer": "CONTOUR"})
msp.add_lwpolyline([(w - r, h), (r, h)], dxfattribs={"layer": "CONTOUR"})
msp.add_lwpolyline([(0, h - r), (0, r)], dxfattribs={"layer": "CONTOUR"})
for cx, cy, a in ((w - r, r, 270), (w - r, h - r, 0), (r, h - r, 90), (r, r, 180)):
    msp.add_arc((cx, cy), r, a, a + 90, dxfattribs={"layer": "CONTOUR"})
for x, y in ((15, 15), (105, 15), (105, 65), (15, 65)):
    msp.add_circle((x, y), 5, dxfattribs={"layer": "CONTOUR"})
msp.add_circle((60, 40), 15, dxfattribs={"layer": "CONTOUR"})
msp.add_linear_dim(base=(0, -12), p1=(0, 0), p2=(w, 0), dimstyle="EZDXF", override=DIM, dxfattribs={"layer": "DIMS"}).render()
msp.add_linear_dim(base=(-12, 0), p1=(0, 0), p2=(0, h), angle=90, dimstyle="EZDXF", override=DIM, dxfattribs={"layer": "DIMS"}).render()
msp.add_diameter_dim(center=(60, 40), radius=15, angle=45, dimstyle="EZDXF", override=DIM, dxfattribs={"layer": "DIMS"}).render()
msp.add_text("PLYTA 120x80  S235JR  t=10", height=4, dxfattribs={"layer": "DIMS"}).set_placement((0, h + 8))
doc.saveas(HERE / "plate.dxf")
print("written:", HERE / "flange.step", HERE / "plate.dxf")
