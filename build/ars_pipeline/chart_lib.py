"""Shared ARS chart helpers — one styling source so charts_gen.py and build_ars_gen.py
render matching charts. The take-rate-by-branch chart is used for BOTH the personal slide
(orange bars / navy dashed avg) and the business slide (navy bars / orange dashed avg); they
must be identical in size and layout — see templates/STYLE.md."""
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

def take_branch_chart(out_png, labels, vals, avg, bar_color, dash_color, w=1383, h=540):
    """Take-rate-by-branch bar chart with identical geometry for personal & business.
    Only the colors differ (personal orange/navy, business navy/orange)."""
    # This geometry seats about eight bars; past that the branch labels run together and
    # the value labels touch (1549 arrived with 19, 1075 with 37 — Aaron, 2026-08-20).
    # Callers cap the list; this is the backstop so a new caller can't reintroduce it.
    if len(vals) > BRANCH_CAP:
        raise ValueError(f"take_branch_chart got {len(vals)} bars; cap the caller's list at "
                         f"{BRANCH_CAP} or the branch labels will collide")
    a = w / h; H = 3.2
    fig, ax = plt.subplots(figsize=(H * a, H))
    ax.bar(range(len(vals)), vals, color=bar_color, width=_BAR_W)
    # White halo so the dashed average passes BEHIND a value label rather than
    # striking through it — the bars cluster around the average once they are
    # ranked by take rate.
    _halo = dict(boxstyle="square,pad=0.10", facecolor="white", edgecolor="none")
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{v}%", ha="center", va="bottom", color=NAVY,
                fontweight="bold", fontsize=10, bbox=_halo, zorder=5)
    ax.axhline(avg, ls="--", color=dash_color, lw=1.5)
    ax.set_xticks(range(len(vals))); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 105); ax.get_yaxis().set_visible(False)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(MUTED); ax.tick_params(colors=TICK, length=0)
    for t in ax.get_xticklabels(): t.set_color(NAVY)
    _letterbox(fig, out_png, w, h)

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
