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


# --- usd_compact -------------------------------------------------------------
# One money formatter, because there were four and they disagreed: the ICS Present
# Value callout divided by a million unconditionally and printed "$0.83M" for
# $830K (Aaron, 2026-09-11), ics_charts_gen fell back to a full "$830,000", and
# build_ars_gen carried both an unconditional m2() and a correct _fmtk.
import pytest as _pytest
from brand import usd_compact


@_pytest.mark.parametrize("value,expected", [
    (1_240_000, "$1.24M"),
    (1_000_000, "$1.00M"),
    (829_523,   "$830K"),      # True Sky's Present Value — the figure that prompted this
    (830_000,   "$830K"),
    (53_868,    "$54K"),
    (1_000,     "$1K"),
    (999,       "$999"),       # below a thousand stays whole: "$1K" for $999 is a lie
    (950,       "$950"),
    (0,         "$0"),
])
def test_the_unit_matches_the_magnitude(value, expected):
    assert usd_compact(value) == expected


def test_rounding_picks_the_unit_not_the_raw_value():
    """$999,999 is not "$1,000K" — a unit nobody writes. Rounding decides."""
    assert usd_compact(999_999) == "$1.00M"
    assert usd_compact(999_499) == "$999K"


@_pytest.mark.parametrize("value,expected", [
    (-1_500_000, "\u2212$1.50M"),
    (-830_000,   "\u2212$830K"),
    (-500,       "\u2212$500"),
])
def test_negatives_use_a_true_minus_outside_the_dollar(value, expected):
    """"$-1.50M" puts the sign in the wrong place; the deck writes −$1.50M."""
    assert usd_compact(value) == expected


def test_decimals_are_adjustable_for_millions_only():
    assert usd_compact(1_240_000, decimals=1) == "$1.2M"
    assert usd_compact(830_000, decimals=1) == "$830K"      # K is always whole


def test_every_builder_uses_the_shared_formatter():
    """No file may divide by a million on its own again."""
    import os, re
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    # The validator is in this list because it was the FIFTH copy and the one that
    # bit: it formatted the EXPECTED value with its own `/1e6:.2f}M` and failed a
    # correct deck the moment the builders started writing $830K (2026-09-11). An
    # expected value formatted differently from the rendered one is not a check.
    for path in ("build/ics_pipeline/build_ics_gen.py",
                 "build/ars_pipeline/build_ars_gen.py",
                 "validation/validate_deck.py",
                 "build/ics_pipeline/ics_charts_gen.py",
                 "build/mrpc_pipeline/build_mrpc_gen.py"):
        # Code only: a comment EXPLAINING the old pattern is not the old pattern,
        # and this test flagged its own docstring in validate_deck.py.
        src = "\n".join(l for l in open(os.path.join(repo, path), encoding="utf-8")
                        if not l.lstrip().startswith("#"))
        for m in re.finditer(r"/\s*1e6:[^}]*\}M", src):
            offenders.append("%s: %s" % (path, m.group(0)))
    assert not offenders, "unconditional millions formatting: %s" % offenders
