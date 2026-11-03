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
    assert brand.ORANGE == "#F15D22"
    assert brand.WHITE == "#FFFFFF"


def test_type_roles():
    assert brand.HEAD == "Montserrat"
    assert brand.BODY == "Calibri"
    assert brand.CHART_FONT == "Carlito"


def test_role_colors_are_distinct():
    """Two roles sharing a value means one of them is about to drift."""
    roles = {n: getattr(brand, n) for n in
             ("NAVY", "ORANGE", "TICK", "LABEL", "ROWALT", "GRID", "MUTED",
              "STEEL", "STEEL_SOFT", "GOLD", "SLATE")}
    dupes = {}
    for n, v in roles.items():
        dupes.setdefault(v, []).append(n)
    collisions = {v: ns for v, ns in dupes.items() if len(ns) > 1}
    assert not collisions, f"roles sharing a value: {collisions}"


def test_five_greys_one_per_job():
    """The deck greys are TICK, LABEL, ROWALT, GRID, MUTED and no others (Aaron, 2026-11-02).

    TILE, HAIRLINE and LIGHT used to be three more values a few points from ROWALT, GRID and
    LABEL doing the same jobs. They survive as ALIASES so an old import works; a new grey needs
    a new job, and a new job is a STYLE.md decision."""
    assert (brand.TICK, brand.LABEL, brand.ROWALT, brand.GRID, brand.MUTED) == (
        "#5A6670", "#CFDBE8", "#EEF2F7", "#E4EAF1", "#B8C0CA")
    assert brand.TILE == brand.ROWALT
    assert brand.HAIRLINE == brand.GRID
    assert brand.LIGHT == brand.LABEL


def test_grey_roles_stay_visibly_apart():
    """Five greys is only worth it if each reads as itself: no two within a hair of each other."""
    def lum(hx):
        v = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        v = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in v]
        return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]
    greys = sorted(lum(getattr(brand, n)) for n in ("TICK", "LABEL", "ROWALT", "GRID", "MUTED"))
    assert all(b - a > 0.02 for a, b in zip(greys, greys[1:]))


_RETIRED_GREYS = ("ECF0F4", "D9DEE5", "C9D6E3", "5A6778", "F2F5F8")


def test_no_builder_declares_a_retired_grey():
    """A literal near-grey in a builder is how eight greys became the deck's look.

    Builders import the role from brand.py. A line that must name a retired value (reading it
    back from a template shell that still carries it) says so with `retired-grey-ok`."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "build"
    skip = ("_v5", "kickoff", "deckkit", "brand.py")        # ported v5 code keeps v5's own values
    found = []
    for py in root.rglob("*.py"):
        if any(s in py.as_posix() for s in skip) or "ti/deck" in py.as_posix():
            continue
        for n, line in enumerate(py.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "retired-grey-ok" in line:
                continue
            up = line.upper()
            if any(h in up for h in _RETIRED_GREYS):
                found.append(f"{py.relative_to(root)}:{n}")
    assert not found, f"retired grey literal: {found}"


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


# ---------------------------------------------------------------- bar labels (2026-10-26)
def test_bar_labels_stay_full_when_they_fit_and_shorten_all_alike_when_one_would_not():
    """KEMBA CU's composition chart: twelve five-digit totals 0.74 in apart ran together."""
    vals = [12260, 12118, 12558, 10845, 8708, 6937, 4587, 3002, 4052, 3241, 980, 483]
    wide = brand.bar_labels(vals, slot_in=2.0, pt=16)
    assert wide[:3] == ["$12,260", "$12,118", "$12,558"]
    tight = brand.bar_labels(vals, slot_in=0.74, pt=16)
    assert tight[:3] == ["$12.3K", "$12.1K", "$12.6K"] and tight[-1] == "$483"
    # one form per chart: every label took the compact form, not only the wide ones
    assert all(t == brand.usd_compact(v, decimals=1, k_decimals=1) for t, v in zip(tight, vals))


def test_bar_labels_use_millions_and_keep_cents_on_small_figures():
    assert brand.bar_labels([1_240_000, 830_000], slot_in=0.6, pt=16) == ["$1.2M", "$830.0K"]
    assert brand.bar_labels([0.52, 0.61], slot_in=0.74, pt=16, cents=True) == ["$0.52", "$0.61"]


def test_usd_compact_k_decimals_is_opt_in():
    assert brand.usd_compact(17200) == "$17K"                 # the ARS and MRPC charts, unchanged
    assert brand.usd_compact(17200, k_decimals=1) == "$17.2K"
