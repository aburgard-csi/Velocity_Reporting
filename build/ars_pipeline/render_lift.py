"""The ARS Revenue Lift Matrix picture (MM decks): a heat grid of the matrix beside the value per tier.

    python render_lift.py <lift.json> <out.png>

Aaron, 2026-09-16: the two plain tables became a chart in the house style.
  * Left, the Lift Matrix as a heat grid: starting tier down the rows, tier now across the columns,
    one navy ramp (COLD_RAMP) light to dark. A move that cannot happen (a lower tier than the start)
    is a dash, never a blank or $0. The example the slide caption walks through is outlined orange.
  * Right, the Revenue Segmentation block as bars: monthly value per card account by tier, with its
    share of card accounts. The tier with the largest share is orange.

Drawn at the slide's picture aspect (12.7 x 3.9 in, letterboxed by build_ars_gen to 2554 x 784), so
it fills the box without stretching. Import-safe: `example_move` is shared with build_ars_gen's
caption, so the outlined cell and the sentence under the chart always name the same move.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))  # build/

# The move the caption explains (Aaron, 2026-09-16: "use 1-5 to 11-15 as the example").
EXAMPLE = ("1-5", "11-15")


def tier_label(s):
    return {"NU": "Non-User", "NH": "No history", "26 Plus": "26+"}.get(s, s)


def example_move(L):
    """(from tier, to tier, row index, column index, value) for the caption's example.

    EXAMPLE when the client's matrix carries it; otherwise the largest move in the matrix, so a
    workbook with different tier bands still gets a caption that matches an outlined cell.
    """
    cols, rows = L["matrix_cols"], L["matrix_rows"]
    start, now = EXAMPLE
    for i, r in enumerate(rows):
        if r[0] == start and now in cols:
            v = r[1 + cols.index(now)]
            if isinstance(v, (int, float)):
                return start, now, i, cols.index(now), v
    cells = [(v, i, j) for i, r in enumerate(rows) for j, v in enumerate(r[1:]) if isinstance(v, (int, float))]
    v, i, j = max(cells)
    return rows[i][0], cols[j], i, j, v


def tiers(L):
    """Revenue Segmentation rows that carry accounts: (tier, share of card accounts, monthly value)."""
    return [(n, d, v) for n, d, v in L["revseg"]
            if isinstance(d, (int, float)) and d > 0 and isinstance(v, (int, float))]


def render(L, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from rpe_env import use_font
    from brand import NAVY, ORANGE, TICK, GRID, MUTED, COLD_RAMP, WHITE

    use_font("Carlito")
    cols = [tier_label(c) for c in L["matrix_cols"]]
    rows = L["matrix_rows"]
    vmax = max(v for r in rows for v in r[1:] if isinstance(v, (int, float)))
    _, _, ei, ej, _ = example_move(L)

    fig = plt.figure(figsize=(12.7, 3.9), dpi=200)
    fig.patch.set_facecolor("white")

    # ---- left: the heat grid
    ax = fig.add_axes([0.105, 0.06, 0.515, 0.72])
    nr, nc = len(rows), len(cols)
    ax.set_xlim(0, nc); ax.set_ylim(nr, 0); ax.axis("off")
    ramp = COLD_RAMP[:8]                       # dark -> light
    fs = 12.5 if nc <= 6 else 11
    for i, r in enumerate(rows):
        ax.text(-0.12, i + 0.5, tier_label(r[0]), ha="right", va="center", fontsize=fs, color=NAVY, fontweight="bold")
        for j, v in enumerate(r[1:]):
            if not isinstance(v, (int, float)):
                ax.add_patch(Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, facecolor=WHITE, edgecolor=GRID, lw=1.2))
                ax.text(j + 0.5, i + 0.5, "—", ha="center", va="center", fontsize=11, color=MUTED)
                continue
            shade = min(7, max(0, round(7 * (1 - v / vmax))))
            ax.add_patch(Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, facecolor=ramp[shade], edgecolor="none"))
            ax.text(j + 0.5, i + 0.5, f"${v:,.2f}", ha="center", va="center", fontsize=fs, fontweight="bold",
                    color=WHITE if shade <= 4 else NAVY)
    ax.add_patch(Rectangle((ej + 0.02, ei + 0.03), 0.96, 0.94, facecolor="none", edgecolor=ORANGE, lw=3.2))
    for j, c in enumerate(cols):
        ax.text(j + 0.5, -0.18, c, ha="center", va="bottom", fontsize=fs, color=NAVY, fontweight="bold")
    ax.text(-0.12, -0.18, "From ↓   To →", ha="right", va="bottom", fontsize=11.5, color=TICK)
    fig.text(0.015, 0.955, "Monthly revenue added per account, from starting tier to tier now",
             fontsize=14, fontweight="bold", color=NAVY, va="top")

    # ---- right: value per card account by tier, with its share of card accounts
    seg = tiers(L)
    ax2 = fig.add_axes([0.715, 0.06, 0.165, 0.72])
    names = [tier_label(n) for n, _, _ in seg][::-1]
    shares = [d for _, d, _ in seg][::-1]
    values = [v for _, _, v in seg][::-1]
    top = max(range(len(shares)), key=shares.__getitem__) if shares else -1
    ax2.barh(range(len(names)), values, height=0.62, color=[ORANGE if k == top else NAVY for k in range(len(names))])
    ax2.set_yticks(range(len(names)), names, fontsize=12, color=NAVY)
    ax2.tick_params(axis="y", length=0, pad=8)
    vtop = max(values) if values else 1
    ax2.set_xticks([]); ax2.set_xlim(0, vtop * 1.02)
    for s in ("top", "right", "bottom"):
        ax2.spines[s].set_visible(False)
    ax2.spines["left"].set_color(MUTED)
    for y, (v, sh) in enumerate(zip(values, shares)):
        ax2.text(v + vtop * 0.03, y, f"${v:,.2f}", va="center", fontsize=12, fontweight="bold", color=NAVY)
        ax2.text(vtop * 1.58, y, f"{sh:.0%}", va="center", ha="right", fontsize=12, color=TICK, clip_on=False)
    ax2.text(vtop * 1.58, len(names) - 0.45, "of cards", va="bottom", ha="right", fontsize=11, color=TICK, clip_on=False)
    fig.text(0.655, 0.955, "Monthly value per card account, by tier", fontsize=14, fontweight="bold", color=NAVY, va="top")

    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    lift_json, out_png = sys.argv[1:3]
    render(json.load(open(lift_json, encoding="utf-8")), out_png)
    print("wrote", out_png)
