"""brand — the palette is one source, and its roles stay distinct.

The drift this guards against is real: before consolidation the same hex was
declared in seven files under four naming conventions, and five different values
were all in service as "the light grey".
"""
import re
import pytest
import brand

HEX = re.compile(r"^#[0-9A-F]{6}$")
COLOR_NAMES = [n for n in dir(brand)
               if n.isupper() and isinstance(getattr(brand, n), str)
               and getattr(brand, n).startswith("#")]


@pytest.mark.parametrize("name", sorted(COLOR_NAMES))
def test_every_color_is_uppercase_six_digit_hex(name):
    assert HEX.match(getattr(brand, name)), f"{name} = {getattr(brand,name)!r}"


def test_core_palette_values():
    assert brand.NAVY == "#00274C"
    assert brand.ORANGE == "#F47A29"
    assert brand.WHITE == "#FFFFFF"


def test_type_roles():
    assert brand.HEAD == "Montserrat"
    assert brand.BODY == "Calibri"
    assert brand.CHART_FONT == "Carlito"


def test_role_colors_are_distinct():
    """Two roles sharing a value means one of them is about to drift."""
    roles = {n: getattr(brand, n) for n in
             ("NAVY", "ORANGE", "TICK", "LABEL", "ROWALT", "GRID", "MUTED",
              "HAIRLINE", "STEEL", "STEEL_SOFT", "LIGHT", "GOLD", "SLATE")}
    dupes = {}
    for n, v in roles.items():
        dupes.setdefault(v, []).append(n)
    collisions = {v: ns for v, ns in dupes.items() if len(ns) > 1}
    assert not collisions, f"roles sharing a value: {collisions}"


def test_the_two_steels_are_still_two():
    """Collapsing them would silently restyle ARS or ICS/MRPC — a STYLE.md call."""
    assert brand.STEEL != brand.STEEL_SOFT


@pytest.mark.parametrize("hexname,rgbname", [
    ("NAVY", "NAVY_RGB"), ("ORANGE", "ORANGE_RGB"), ("WHITE", "WHITE_RGB"),
    ("TICK", "TICK_RGB"), ("LABEL", "LABEL_RGB"), ("ROWALT", "ROWALT_RGB"),
    ("GRID", "GRID_RGB"), ("PEACH", "PEACH_RGB"), ("TILE", "TILE_RGB"),
    ("STEEL_SOFT", "STEEL_SOFT_RGB"),
])
def test_rgb_variants_match_their_hex(hexname, rgbname):
    hx = getattr(brand, hexname)
    rgb = getattr(brand, rgbname)
    assert str(rgb).upper() == hx[1:].upper(), f"{rgbname} != {hexname}"


@pytest.mark.parametrize("ramp", ["COLD_RAMP", "WARM_RAMP", "CANCEL_RAMP"])
def test_ramps_are_lists_of_hex(ramp):
    vals = getattr(brand, ramp)
    assert isinstance(vals, list) and vals
    for v in vals:
        assert HEX.match(v), f"{ramp} carries {v!r}"
