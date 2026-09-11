#!/usr/bin/env python3
"""
brand.py — the Velocity deck palette and type roles, defined once.

Before this module the palette was re-declared in SEVEN files under FOUR naming
conventions for the same hex:

    chart_lib.py:9            NAVY / ORANGE / TICK
    ticket_chart.py:8         NAVY / ORANGE / STEEL / TICK
    render_lift.py:8          NAVY / GREY / TICK
    product_mix_slide.py:74   _NAVY_HX / _ORANGE_HX / _GREY_HX / _TICK_HX
    product_mix_slide.py:67   NAVY / ORANGE / ... again, as RGBColor
    build_ars_onepager.py:46  NAVY_HEX / ORANGE_HEX / TICK_HEX / GRID_HEX
    mrpc_charts_gen.py:30     NAVY / STEEL / ORANGE / LIGHT / TICK / GREY

Navy and orange happened to agree everywhere. The GREYS had already drifted —
#CFDBE8, #EEF2F7, #B8C0CA, #E4EAF1 and #C9D6E3 were all in service as "the light
grey", and STEEL meant #7B9BB8 in ARS but #9DB8CC in MRPC.

This module is a CONSOLIDATION, NOT A RESTYLE. Every value below is one that was
already in use, kept under a name that says what it is for. Two colors that
collided under one name (STEEL) are kept as two distinct entries so no rendered
chart changes. Anything that should actually be recolored is a separate,
deliberate change against STYLE.md — not a side effect of this move.

Two representations of each color:
  * bare name  -> "#RRGGBB" string, for matplotlib
  * _RGB suffix -> pptx RGBColor, for shape fills and run colors

Import under whatever local name a module already uses so call sites don't churn:

    from brand import NAVY, ORANGE, TICK                 # chart renderer
    from brand import NAVY_RGB as NAVY, HEAD, BODY       # pptx builder
"""
from pptx.dml.color import RGBColor

# ----------------------------------------------------------------- core palette
NAVY   = "#00274C"   # primary — titles, tiles, bars, table headers
ORANGE = "#F47A29"   # accent — the current period, the highlighted row, pills
WHITE  = "#FFFFFF"

# ----------------------------------------------------------------- greys, by ROLE
# These are the five distinct values that were in use. Naming them by role is
# what stops the next one from being invented.
TICK   = "#5A6670"   # axis ticks, body text grey        (was TICK / _TICK_HX / GREYT)
LABEL  = "#CFDBE8"   # light label on navy, neutral bar  (was GREYB / _GREY_HX)
ROWALT = "#EEF2F7"   # alternating table row, pale fill  (was ROWALT / render_lift GREY)
GRID   = "#E4EAF1"   # chart gridlines                   (was GRID_HEX, one-pager)
MUTED  = "#B8C0CA"   # axis spine grey                   (was mrpc GREY)
PEACH  = "#F6B284"   # section-bar topic text            (one-pager)
TILE   = "#ECF0F4"   # light tile fill                   (one-pager)

# ----------------------------------------------------------------- secondary series
# STEEL meant two different colors in two places: ARS drew #7B9BB8, while ICS and
# MRPC both drew #9DB8CC. Both are kept — collapsing them would silently restyle
# either the ARS ticket chart or the ICS/MRPC tier charts. Which one wins is a
# STYLE.md decision, not a refactor decision.
STEEL      = "#7B9BB8"   # ARS secondary series (ticket_chart)
STEEL_SOFT = "#9DB8CC"   # ICS + MRPC secondary (MRPC Platinum tier)
LIGHT      = "#C9D6E3"   # ICS + MRPC tertiary
GOLD       = "#E7A93B"   # ARS Gold tier series (charts_gen)
HAIRLINE   = "#D9DEE5"   # lightest axis spine (ARS + MRPC left spine)
SLATE      = "#5A7590"   # MRPC 4th categorical series
# A series line drawn OVER navy bars. Navy-on-navy is invisible, and the fix is
# the LINE'S COLOUR, not a white stroke under it (Aaron, 2026-09-01 — casing was
# tried and rejected). Teal clears WCAG's 3:1 non-text contrast against BOTH
# backgrounds the line crosses: 4.02:1 on #00274C and 3.74:1 on white. That is
# near the best any flat colour can manage against those two extremes (3.88:1),
# which is why the earlier attempts reached for a stroke instead.
TEAL       = "#0D9488"   # series line over navy bars (MRPC Enrollments, Still Active)

# ----------------------------------------------------------------- ramps
# Cold ramp for donut slices that are NOT program-eligible (product_mix_slide).
COLD_RAMP = ["#00274C", "#12406E", "#245C8C", "#3D74A0", "#6E93B4", "#9DB4C8",
             "#C0D0DD", "#DDE6ED", "#EAF0F4", "#F2F5F8"]
# Warm ramp for eligible slices — orange at three tints.
WARM_RAMP = ["#F47A29", "#F79552", "#FBB27E"]
# MRPC cancellation-reason categories.
CANCEL_RAMP = ["#00274C", "#B9C7D6", "#5A7590", "#C9D6E3", "#F47A29",
               "#D9B44A", "#C98B8B"]


def _rgb(hx):
    return RGBColor(int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16))


NAVY_RGB   = _rgb(NAVY)
ORANGE_RGB = _rgb(ORANGE)
WHITE_RGB  = _rgb(WHITE)
TICK_RGB   = _rgb(TICK)
LABEL_RGB  = _rgb(LABEL)
ROWALT_RGB = _rgb(ROWALT)
GRID_RGB   = _rgb(GRID)
PEACH_RGB  = _rgb(PEACH)
TILE_RGB   = _rgb(TILE)
STEEL_SOFT_RGB = _rgb(STEEL_SOFT)

# ----------------------------------------------------------------- type roles
# Mirrors restyle_fonts.py, which enforces these on the finished deck:
#   headings, callouts, KPI tiles, pills, chips, badges -> HEAD
#   body copy, captions, table cells, source lines      -> BODY
# Calibri is named rather than Carlito because PowerPoint resolves Calibri on
# both machines; Carlito is the metric-compatible face matplotlib draws with.
HEAD = "Montserrat"
BODY = "Calibri"
CHART_FONT = "Carlito"


# ---------------------------------------------------------------- money
def usd_compact(v, decimals=2):
    """A dollar figure at deck scale: `$1.24M` at a million and up, `$830K` below.

    ONE definition, because there were four and they disagreed (Aaron, 2026-09-11).
    `build_ics_gen`'s Present Value callout divided by a million unconditionally and
    printed **$0.83M** for $830K; `ics_charts_gen` fell back to a full `$830,000`;
    `build_ars_gen` had both an unconditional `m2()` and a correct `_fmtk` two
    hundred lines apart. A reader should not have to learn which slide they are on
    to read a number.

    Below $1,000 the figure is written in full: "$0K" says nothing, and a rounded
    "$1K" for $950 is worse than the four characters it saves.
    """
    a = abs(v)
    sign = "−" if v < 0 else ""          # true minus, not a hyphen, and OUTSIDE the $
    # Rounding decides the unit, not the raw value: $999,999 is "$1,000K" if you
    # pick the unit first, which is a unit nobody writes.
    if a < 1e6 and round(a / 1000) >= 1000:
        a = 1e6
    if a >= 1e6:
        return f"{sign}${a/1e6:,.{decimals}f}M"
    if a >= 1000:
        return f"{sign}${a/1000:,.0f}K"
    return f"{sign}${a:,.0f}"
