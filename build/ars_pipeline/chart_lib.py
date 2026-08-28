"""Shared ARS chart helpers — one styling source so charts_gen.py and build_ars_gen.py
render matching charts. The take-rate-by-branch chart is used for BOTH the personal slide
(orange bars / navy dashed avg) and the business slide (navy bars / orange dashed avg); they
must be identical in size and layout — see templates/STYLE.md."""
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
NAVY = "#00274C"; ORANGE = "#F47A29"; TICK = "#5A6670"
BRANCH_CAP = 8   # bars take_branch_chart can seat without the labels colliding

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
    ax.bar(range(len(vals)), vals, color=bar_color, width=0.66)
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{v}%", ha="center", va="bottom", color=NAVY, fontweight="bold", fontsize=10)
    ax.axhline(avg, ls="--", color=dash_color, lw=1.5)
    ax.set_xticks(range(len(vals))); ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylim(0, 105); ax.get_yaxis().set_visible(False)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#B8C0CA"); ax.tick_params(colors=TICK, length=0)
    for t in ax.get_xticklabels(): t.set_color(NAVY)
    _letterbox(fig, out_png, w, h)

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
