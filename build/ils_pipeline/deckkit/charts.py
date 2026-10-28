# Ported from v5 02-Scripts/ars/deck/charts.py at 7ba1e63. Logic unchanged; only what deckkit's PGL surface reaches (the brand colours, the figure sizes, _clean and _save, and the module's Agg backend and font setup).
"""Chart renderers for the ODD-only deck.

Charts are PNGs, not native pptx charts, so a slide never carries chart
XML that PowerPoint restyles on open; the picture is the contract.

Palette and typography follow the CSI brand -- navy and orange, with
Montserrat for chart labels. Nothing
here reads a metric by name; each function takes plain values so a chart can
be tested without running the pipeline.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
# CSI Velocity brand. These are the canonical values, matching
# RPE-Workflow's ars_engine/core/brand.py -- the module that declares itself the
# single source of truth for colour. Five of these had drifted: GREY was one hex
# digit off, GRID was a near-miss, RED was a brick (#C0392B) rather than CSI
# Red. Charts built from a drifted palette look almost right, which is why it
# went unnoticed through every deck that shipped --
# test_palette_matches_csi_brand pins them now.
NAVY = "#00274C"
import brand
ORANGE = brand.ORANGE           # v5 wrote the same orange as a literal; RPE keeps colour in brand.py
GREY = "#5B6770"      # brand.py; was one hex digit off
DPI = 150   # 200 was ~2x slower for no visible gain at slide size

# Author each figure at the width of the slot it lands in, so type on the
# slide is the size it was authored at (DESIGN/ spec). Rail slot ~9.28in
# (chart left of the callout rail); full slot ~12in.
FIG_W_RAIL = 8.8
FIG_W_FULL = 11.5
# ...and at the HEIGHT of that slot too. A form that authors a 3.4in canvas
# for a 4.90in band lands an inch and a half short and leaves the spare in
# one lump at the bottom of the slide -- which is what "too much white
# space" was. These are the two content bands of ars/deck/build's grid,
# expressed as the canvas that fills them:
#
#     rail   8.69 x 4.90in   (RAIL_LEFT - RAIL_GUTTER - MARGIN_L, band)
#     full  11.53 x 4.90in   (CONTENT_W, band)
#
# build.py imports this module, so these cannot be imported from the grid
# without a cycle. test_ils_kickoff_deck asserts they still match it.
_BAND_H = 4.90
FIG_H_RAIL = round(FIG_W_RAIL * (_BAND_H / 8.69), 2)     # 4.96
FIG_H_FULL = round(FIG_W_FULL * (_BAND_H / 11.53), 2)    # 4.89


BRAND_FONT = "Montserrat"


def _font() -> str:
    """Return the brand typeface, or say plainly why the deck will look wrong.

    This used to walk a fallback chain (Carlito, Calibri, DejaVu Sans) and take
    whichever happened to be installed. That silently produced a different deck
    on every machine -- the same script, three typefaces, and no error to say so.
    A deck built in the wrong font is not a smaller problem than a deck that
    failed to build, so this warns loudly rather than degrading quietly.

    Install with: brew install --cask font-montserrat
    If matplotlib still cannot see it after installing, its font cache is stale:
    delete ~/.matplotlib/fontlist-*.json and re-run.
    """
    from matplotlib import font_manager

    names = {f.name for f in font_manager.fontManager.ttflist}
    if BRAND_FONT in names:
        return BRAND_FONT
    warnings.warn(
        f"{BRAND_FONT} is not available to matplotlib -- charts will render in "
        f"a substitute and this deck will not match the brand. "
        f"Install it (brew install --cask font-montserrat), and if it is "
        f"already installed delete ~/.matplotlib/fontlist-*.json to clear the "
        f"stale cache.",
        RuntimeWarning, stacklevel=2)
    return "DejaVu Sans"


# font LIST: per-glyph fallback (matplotlib >=3.6) -- Calibri on
# Windows lacks the glyph set (\u25b2 etc.); DejaVu carries them
plt.rcParams.update({"font.family": [_font(), "DejaVu Sans"],
                     "font.size": 12})


_PENDING_CAPTION = None


def _clean(ax, left=False, bottom=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    ax.spines["bottom"].set_color("#B8C0CA")
    ax.tick_params(colors=GREY, length=0)
    ax.set_axisbelow(True)


def _declutter(fig) -> int:
    """Drop data labels that would print on top of another label.

    168 label-placement sites exist across the chart layer and exactly one
    of them measures whether the label fits (_label_if_it_fits); five more
    re-implement the idea against fixed thresholds that hold only at the
    figure size they were written for. Rather than repair 168 call sites,
    the check runs once here, on the laid-out figure, where the true pixel
    extents are finally known and where every chart already passes through.

    Only artists added with ax.text() are considered. Tick labels, titles
    and legends are laid out by matplotlib and are not ours to remove.

    A bigger label wins its space first, then earlier draw order: a callout
    outranks a value label, and among equals the first one placed keeps its
    position. Dropping rather than nudging is deliberate and matches the
    rule _label_if_it_fits already applies to a segment too narrow to hold
    its text -- a moved label points at the wrong mark, which is a worse
    failure than an absent one.

    Returns the number of labels removed. A figure that lays out its own
    labels can opt out with fig._ars_no_declutter = True.
    """
    if getattr(fig, "_ars_no_declutter", False):
        return 0
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # A legend is laid out by matplotlib and is never ours to remove, but it
    # occupies space a value label must not print into (#82, slide 46: a bar
    # label crowding the legend swatch). Seeding the kept list with it makes
    # the legend win by construction.
    kept_fixed = []
    for ax in fig.axes:
        legend = ax.get_legend()
        if legend is not None and legend.get_visible():
            try:
                kept_fixed.append(legend.get_window_extent(renderer))
            except (AttributeError, RuntimeError):
                pass

    candidates = []
    for ax in fig.axes:
        for order, artist in enumerate(ax.texts):
            if not artist.get_visible() or not artist.get_text().strip():
                continue
            if getattr(artist, "_ars_keep", False):
                continue
            candidates.append((-artist.get_fontsize(), order, artist))
    candidates.sort(key=lambda c: (c[0], c[1]))

    kept, removed = list(kept_fixed), 0
    for _size, _order, artist in candidates:
        box = artist.get_window_extent(renderer).expanded(1.0, 1.0)
        if any(box.overlaps(other) for other in kept):
            artist.remove()
            removed += 1
        else:
            kept.append(box)
    return removed


_CAPTION_PT = 9
_CAPTION_PAD_IN = 0.10          # clear air between tick labels and the slate


def _caption_band(fig, text: str, laid_out: bool) -> None:
    """Carve a strip off the bottom of the figure and write the caption in it.

    Measured, not guessed: the strip is the caption's own type height plus a
    fixed pad, expressed as a fraction of THIS figure -- so it holds at any
    canvas size rather than at the one it was written for.
    """
    band_in = _CAPTION_PT / 72.0 + _CAPTION_PAD_IN
    band = band_in / fig.get_figheight()
    if laid_out:
        fig.subplots_adjust(bottom=fig.subplotpars.bottom + band)
    fig.text(0.012, band * 0.28, text, fontsize=_CAPTION_PT, color=GREY,
             fontweight="bold", ha="left", va="bottom")


def _save(fig, path: Path) -> Path:
    """Layout is tightened INSIDE the authored canvas -- never cropped to
    content (bbox_inches='tight' shrank figures unpredictably, so the same
    renderer landed at different on-slide type sizes).

    Also the one place a caption can be applied to every form: see
    set_caption().
    """
    global _PENDING_CAPTION
    caption_text, _PENDING_CAPTION = _PENDING_CAPTION, None
    path.parent.mkdir(parents=True, exist_ok=True)
    laid_out = False
    try:
        # figures with manually placed axes (add_axes) author their own
        # layout; tight_layout would warn and shift them. So do figures that
        # reserved a margin for figure-level text -- tight_layout does not
        # see fig.text and would lay the panels straight over it.
        if getattr(fig, "_ars_layout_authored", False):
            pass
        elif all(ax.get_subplotspec() is not None for ax in fig.axes):
            fig.tight_layout(pad=0.5)
            laid_out = True
    except Exception:
        pass

    # The caption goes on AFTER the layout, never before. It used to be
    # written first and the margin reserved with subplots_adjust -- and then
    # tight_layout ran, recomputed that same margin from the tick labels
    # alone, and discarded the reservation. The caption landed on top of the
    # band names on ten slides of the kickoff deck.
    #
    # tight_layout leaves the axes' bottom exactly where the tick labels
    # need it, so the band the caption needs is carved out BELOW that, by
    # pushing the axes up by the caption's own height.
    if caption_text:
        _caption_band(fig, caption_text, laid_out)
    # After layout, before the render: extents are only true once the axes
    # have their final size.
    _declutter(fig)
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


# ---- the per-mailer summary panel (issue #80, James's legacy slide 1) ----
# Donut of response share, per-tier response rate bars, and the fixed five
# "Inside the Numbers" stats. The three blocks are placed with add_axes on a
# single shared band so they line up -- James called out the misalignment
# when the blocks were laid out independently.
# The three data blocks share one band; the ladder key and the coverage note
# hang below the donut column, which is the layout James approved on the
# mockup. Keeping the key out of the axes leaves the band alignment intact.
_SUMMARY_Y0, _SUMMARY_Y1 = 0.17, 0.79

