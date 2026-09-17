"""Shared ARS chart helpers — one styling source so charts_gen.py and build_ars_gen.py
render matching charts. `branch_chart` draws all FOUR branch charts (personal take rate,
business take rate, and both Reg E charts): accounts in the bars, rate on the line.
Only the two colours differ — orange bars / navy line for personal and Reg E, navy bars /
teal line for business. They must be identical in size and layout — see templates/STYLE.md."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))  # build/
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from brand import NAVY, ORANGE, TICK, MUTED
BRANCH_CAP = 12  # bars take_branch_chart can seat without the labels colliding
_BAR_W = 0.55    # narrower than the old 0.66 — that is what buys the extra bars

def _letterbox(fig, out_png, tw, th):
    tmp = out_png + ".__t.png"
    fig.savefig(tmp, dpi=200, bbox_inches="tight", transparent=False, facecolor="white", pad_inches=0.06)
    plt.close(fig)
    im = Image.open(tmp).convert("RGB"); iw, ih = im.size
    sc = min(tw / iw, th / ih); nw, nh = max(1, round(iw * sc)), max(1, round(ih * sc))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), "white"); canvas.paste(im2, ((tw - nw) // 2, (th - nh) // 2))
    canvas.save(out_png); os.remove(tmp)

def branch_chart(out_png, rows, bar_color, rate_color, w=1383, h=540,
                 acct_label="Accounts opened", rate_label="Take rate"):
    """Volume in the bars, rate on the line — all four branch charts (Aaron, 2026-09-08).

    The bars used to BE the rate, and a rate drawn without its denominator is not
    readable: a branch with 15 accounts and 4 opt-ins stood exactly as tall as one
    with 900 accounts at the same percentage, so the chart said nothing about where
    the book actually is. Accounts opened now set the bar height and the rate rides
    above on its own axis, which is the comparison the slide is for.

    `rows` are (branch, numerator, accounts, pct) — the shape every branch metric
    carries — already selected and ordered by `top_branches`.

    No program-average line: that figure is the donut beside the Reg E charts and
    the tile beside the take-rate charts, so a dashed rule was a third rendering of
    a number already twice on the slide (Aaron, 2026-09-08). The captions no longer
    name one.

    One renderer for the personal take rate, the business take rate and both Reg E
    charts, so they cannot drift apart: only the two colours differ.
    """
    # This geometry seats about eight bars; past that the branch labels run together and
    # the value labels touch (1549 arrived with 19, 1075 with 37 — Aaron, 2026-08-20).
    # Callers cap the list; this is the backstop so a new caller can't reintroduce it.
    if len(rows) > BRANCH_CAP:
        raise ValueError(f"branch_chart got {len(rows)} bars; cap the caller's list at "
                         f"{BRANCH_CAP} or the branch labels will collide")
    labels = [str(r[0]) for r in rows]
    accts = [r[2] for r in rows]
    rates = [r[3] for r in rows]
    x = range(len(rows))
    # The figure's WIDTH in inches is what decides how much room the tick labels
    # have. Sizing it from the height alone (H * aspect) made the figure NARROWER
    # when the Reg E box was made taller — same 10pt labels, less width — and
    # "3,825" met "2,434" under the bars (Aaron, 2026-09-10). Never render
    # narrower than the box the PNG lands in: DIM is chosen to match that box's
    # aspect at 200 px/inch, so w/200 is its width.
    a = w / h; H = 3.2
    fig_w = max(H * a, w / 200.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_w / a))

    ax.bar(x, accts, color=bar_color, width=_BAR_W)
    ax.set_ylim(0, max(accts) * 1.62)      # bottom ~62% for the bars, the rest for the line
    ax.get_yaxis().set_visible(False)
    # The count goes UNDER the axis, beneath its branch number, not above the bar
    # or inside it. Above the bar is where the rate line and its labels live, and
    # the two collide the moment a big branch has a low rate — which is the case
    # worth reading: True Sky's branch 1004 is the largest at 513 accounts and the
    # worst at 8%, so its bar and its rate label landed on each other.
    ax.set_xticks(list(x))
    _ax_w = ax.get_position().width * fig_w             # the plot area, measured, not assumed
    _ticks, _tsize = branch_tick_labels(labels, accts, _ax_w / max(1, len(rows)))
    ax.set_xticklabels(_ticks, fontsize=_tsize)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(MUTED); ax.tick_params(colors=TICK, length=0)
    for t in ax.get_xticklabels(): t.set_color(NAVY)

    ax2 = ax.twinx()
    ax2.plot(x, rates, color=rate_color, lw=2.2, marker="o", mfc="white",
             mec=rate_color, ms=6, mew=2, zorder=6)
    _rtop = max(rates) * 1.30
    ax2.set_ylim(0, _rtop)
    # The value labels sit in ONE BAND ABOVE THE LINE, not each above its own
    # marker (Aaron, 2026-09-09). Riding the marker put them in the gap between
    # the line and the bars, and that gap closes exactly where a branch is both
    # large and typical: True Sky's 377-account branch topped out a hair under
    # its own 81% label. A constant height cannot collide with a bar, because the
    # bars are held to the lower band by their own headroom, and each label is
    # still directly above the branch it belongs to.
    #
    # A halo remains: the line runs beneath the band on a chart whose rates are
    # near the top, and it must pass behind a number rather than through it.
    _halo = dict(boxstyle="square,pad=0.10", facecolor="white", edgecolor="none")
    _band = _rtop * 0.955
    for i, v in enumerate(rates):
        ax2.text(i, _band, f"{v}%", ha="center", va="center", color=NAVY,
                 fontweight="bold", fontsize=10, bbox=_halo, zorder=7)
    ax2.set_ylabel(rate_label, color=NAVY, fontsize=10)
    ax2.yaxis.set_major_formatter(lambda v, _p: f"{v:.0f}%")
    # Headroom for the value labels is not a claim that the rate can go there: the
    # personal take rate peaks at 99%, and 1.30x headroom printed ticks up to 120%
    # on an axis where 100% is the ceiling.
    ax2.set_yticks([t for t in ax2.get_yticks() if 0 <= t <= min(100, _rtop)])
    ax2.tick_params(colors=TICK, length=0, labelsize=9)
    ax2.spines["top"].set_visible(False); ax2.spines["left"].set_visible(False)
    ax2.spines["right"].set_color(MUTED)

    ax.set_xlabel(f"Branch  ·  {acct_label.lower()} (bars)", color=TICK, fontsize=9)
    _letterbox(fig, out_png, w, h)

def branch_tick_labels(names, counts, slot_in, pt=10.0, min_pt=7.0, family="Carlito"):
    """(tick labels, font size) for branch bars whose labels may be NAMES, not numbers.

    Test branch (Aaron, 2026-09-17: branch names on the branch charts). A number fits under
    its bar; "North Stafford" or "Camp Lejeune" does not, and twelve of them ran into one
    another. Each name is set on one line when it fits the bar's slot, else split at the word
    break that makes the longer line shortest (two lines at most); one font size for every
    label, the largest from `pt` down to `min_pt` at which all of them fit, measured with the
    bundled font (textfit), never guessed. The account count stays on the last line.
    """
    try:
        from textfit import text_width_in
    except Exception:                                   # pragma: no cover
        text_width_in = lambda t, size, family=None: len(t) * size / 72.0 * 0.5
    room = slot_in * 0.82                             # a clear gap between neighbours

    def lines_for(name, size):
        name = str(name)
        if text_width_in(name, size, family) <= room or " " not in name:
            return [name]
        words = name.split()
        best = None
        for i in range(1, len(words)):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            wide = max(text_width_in(a, size, family), text_width_in(b, size, family))
            if best is None or wide < best[0]:
                best = (wide, [a, b])
        return best[1]

    size = pt
    while True:
        wrapped = [lines_for(n, size) for n in names]
        widest = max((text_width_in(l, size, family) for ls in wrapped for l in ls), default=0)
        if widest <= room or size <= min_pt:
            break
        size = round(size - 0.5, 1)
    tall = max(len(ls) for ls in wrapped) if wrapped else 1
    labels = []
    for ls, n in zip(wrapped, counts):
        ls = ls + [""] * (tall - len(ls))              # counts line up across bars
        labels.append("\n".join(ls + [f"{n:,}"]))
    return labels, size


def top_branches(rows, cap=None, acct=2, pct=3):
    """The branches a branch chart should show, in the order it should show them.

    SELECTION is by accounts opened, so the chart describes the branches that
    actually carry the book. RANKING is by the success measure, best to worst, so
    the shape of the bars is the story (Aaron, 2026-09-02).

    Both were wrong before, in different ways. `rege_branch` arrives sorted by
    OPT-IN RATE and the chart took the first six, so it showed the six best
    performers and called them the branch picture — a branch with 12 accounts and
    one opt-in outranked a branch with 900. The take-rate charts selected by size
    correctly but then re-sorted by branch NUMBER, which is not a measure of
    anything.

    Tuples are (branch, <measure>, accounts, pct) for every caller — rege_branch,
    take_branch and the business branches all share that shape.
    """
    sel = sorted(rows, key=lambda r: -r[acct])
    if cap:
        sel = sel[:cap]
    return sorted(sel, key=lambda r: -r[pct])


def branch_order(rows, key=lambda r: r[0]):
    """Sort already-selected branch rows by branch NUMBER for display.

    Applied AFTER the top-N slice so the chart still shows the largest branches — only
    their left-to-right order changes (Aaron, 2026-08-27). Non-numeric ids (Texas Bay 1509
    carries ids like 707221, and a client could use letters) sort after the numeric ones
    instead of raising.
    """
    def k(r):
        v = str(key(r))
        return (0, int(v), "") if v.isdigit() else (1, 0, v)
    return sorted(rows, key=k)
