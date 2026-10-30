"""The two charts a Key Performance Metrics page carries, drawn at the band's slot size (3.63 x 1.55 in).

usage: python kpm_charts.py <charts.json> <out_dir>

charts.json is a list of {"file": "m1075.png", "type": "yoy" | "bars", "title": "...", ...}:

  yoy  : {"items": [["MRPC enrollments (Jan-Sep)", 25.1], ...]}          horizontal bars of year-over-year change, largest in orange
  share: {"items": [["Online Banking", 48], ...]}                         the same bars labelled as plain percentages ("48%"), for conversion or share
  bars : {"labels": ["May", "Jun"], "values": [1, 31], "every": 1}      vertical bars, the last one in orange

Fonts and colours come from build/brand.py and rpe_env.use_font (it raises rather than let matplotlib substitute a face).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
sys.path.insert(0, os.path.join(REPO, "build"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from brand import GRID, HEAD, NAVY, TICK  # noqa: E402
from rpe_env import use_font  # noqa: E402

ORANGE = "#F15D22"
W, H = 3.63, 1.55
use_font(HEAD)


def yoy(path, title, items, fmt="+{v:.1f}%"):
    items = sorted(items, key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(W, H), dpi=300)
    ax.set_title(title, fontsize=8, fontweight="bold", color=NAVY, loc="left", pad=5, x=-0.02)
    for sp in ("top", "right", "left", "bottom"):
        ax.spines[sp].set_visible(False)
    ys = range(len(items))
    ax.barh(list(ys), [v for _, v in items], color=[ORANGE if i == len(items) - 1 else NAVY for i in ys], height=0.62)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([label for label, _ in items], fontsize=6.2, color=NAVY)
    ax.set_xticks([])
    ax.tick_params(length=0)
    top = max(v for _, v in items)
    for i, (_, v) in enumerate(items):
        ax.text(v + top * 0.02, i, fmt.format(v=v), va="center", fontsize=6.6, fontweight="bold", color=NAVY)
    ax.set_xlim(0, top * 1.25)
    fig.subplots_adjust(left=0.46, right=0.99, top=0.88, bottom=0.03)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def bars(path, title, labels, values, every=1):
    fig, ax = plt.subplots(figsize=(W, H), dpi=300)
    ax.set_title(title, fontsize=8, fontweight="bold", color=NAVY, loc="left", pad=5, x=-0.02)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, labelsize=6.2, colors=TICK)
    ax.set_yticks([])
    ax.bar(range(len(values)), values, color=[ORANGE if i == len(values) - 1 else NAVY for i in range(len(values))], width=0.66)
    ax.set_xticks(range(0, len(values), every))
    ax.set_xticklabels([labels[i] for i in range(0, len(values), every)])
    top = max(values)
    for i, v in enumerate(values):
        ax.text(i, v + top * 0.03, str(v), ha="center", fontsize=6.6, fontweight="bold", color=NAVY)
    ax.set_ylim(0, top * 1.2)
    fig.subplots_adjust(left=0.02, right=0.99, top=0.88, bottom=0.14)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main(spec_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for c in json.load(open(spec_path, encoding="utf-8")):
        path = os.path.join(out_dir, c["file"])
        if c["type"] == "yoy":
            yoy(path, c["title"], c["items"])
        elif c["type"] == "share":
            yoy(path, c["title"], c["items"], "{v:.0f}%")
        elif c["type"] == "bars":
            bars(path, c["title"], c["labels"], c["values"], c.get("every", 1))
        else:
            raise SystemExit("Unknown chart type %r (yoy, share or bars)" % c["type"])
        print(path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
