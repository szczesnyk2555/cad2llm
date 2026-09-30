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

# Shaft drawing as a vector PDF with a text layer (like a PDF exported from CAD), A4 landscape, 1:1 in mm
import pymupdf  # noqa: E402

MM = 72 / 25.4
pdf = pymupdf.open()
page = pdf.new_page(width=297 * MM, height=210 * MM)
x0, cy = 50, 90                                    # left end, axis height (mm from top)
steps = [(40, 25), (100, 40), (40, 30)]            # (length, diameter): Ø25h6 x 40, Ø40 x 100, Ø30k6 x 40
x = x0
for length, dia in steps:
    page.draw_rect(pymupdf.Rect(x * MM, (cy - dia / 2) * MM, (x + length) * MM, (cy + dia / 2) * MM), width=0.7)
    x += length
page.draw_line(pymupdf.Point((x0 - 5) * MM, cy * MM), pymupdf.Point((x + 5) * MM, cy * MM), width=0.3, dashes="[6 2 1 2] 0")
page.draw_line(pymupdf.Point(x0 * MM, 130 * MM), pymupdf.Point(x * MM, 130 * MM), width=0.3)   # overall dimension line


def label(text, xmm, ymm, size=9):
    # insert_htmlbox has built-in Unicode fallback fonts (Polish characters); text stays a real text layer
    page.insert_htmlbox(pymupdf.Rect(xmm * MM, (ymm - size * 0.9) * MM, (xmm + 120) * MM, (ymm + 3) * MM),
                        text, css=f"* {{font-family: sans-serif; font-size: {size}pt;}}")


label("180 ±0,1", 118, 128)
label("Ø25h6", 58, 64)
label("Ø40", 115, 66)
label("Ø30k6", 197, 64)
label("40", 66, 118)
label("100", 125, 118)
label("40", 206, 118)
label("Ra 1,6", 60, 56)
label("2x 1x45°", 35, 110)
label("M10 x 1,5 - gwint w osi, gł. 20", 200, 148)
label("R1", 88, 108)
label("Uwagi: tolerancje ogólne ISO 2768-m. Stępić ostre krawędzie.", 20, 170)
page.draw_rect(pymupdf.Rect(190 * MM, 174 * MM, 287 * MM, 207 * MM), width=0.5)
label("Nazwa: WAŁEK STOPNIOWANY", 193, 181)
label("Nr rys.: PV-1001-A   Skala 1:1", 193, 189)
label("Materiał: C45 (1.0503)   Ilość: 50 szt.", 193, 196)
label("Rysował: cad2llm demo", 193, 203)
pdf.save(HERE / "shaft.pdf")
print("written:", HERE / "shaft.pdf")
