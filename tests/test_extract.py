"""Extractors on the sample files (no API calls)."""
from pathlib import Path

import pytest

from cad2llm import CadError, analyze
from cad2llm.step_extract import declared_units

SAMPLES = Path(__file__).parent.parent / "samples"


def test_step_flange():
    data, png = analyze(SAMPLES / "flange.step")
    assert data["declared_units"] == "mm"
    assert data["solids"] == 1
    assert data["bounding_box_mm"] == {"x": 80.0, "y": 80.0, "z": 32.0}
    assert data["cylinder_diameters_mm"] == {"9.0": 4, "22.0": 1, "40.0": 1, "80.0": 1}
    assert data["volume_mm3"] > 0 and data["faces"] > 0
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_dxf_plate():
    data, png = analyze(SAMPLES / "plate.dxf")
    assert data["units"] == "mm"
    assert [d["value"] for d in data["dimensions"]] == [120.0, 80.0, 30.0]
    assert data["circle_diameters"] == {"10.0": 4, "30.0": 1}
    assert data["arc_radii"] == {"5.0": 4}
    assert "PLYTA 120x80  S235JR  t=10" in data["texts"]
    assert {"CONTOUR", "DIMS"} <= set(data["layers"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_image():
    _, png = analyze(SAMPLES / "plate.dxf", image=False)
    assert png is None


def test_unsupported(tmp_path):
    dwg = tmp_path / "part.dwg"
    dwg.write_bytes(b"AC1032")
    with pytest.raises(CadError, match="DWG"):
        analyze(dwg)


def test_not_a_step(tmp_path):
    bad = tmp_path / "bad.step"
    bad.write_text("hello")
    with pytest.raises(CadError, match="not a STEP"):
        analyze(bad)


@pytest.mark.parametrize("raw, unit", [
    ("#1=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));", "mm"),
    ("#1=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT($,.METRE.));", "m"),
    ("#2=CONVERSION_BASED_UNIT('INCH',#3);", "inch"),
    ("nothing", "unknown"),
])
def test_declared_units(raw, unit):
    assert declared_units(raw) == unit
