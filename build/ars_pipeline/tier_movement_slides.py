#!/usr/bin/env python3
"""
tier_movement_slides.py — swipe-tier MOVEMENT for the ARS-eligible product base.

The existing "Debit Usage Segmentation by Swipe Tier" slide is cross-sectional:
it shows where accounts sit in one trailing quarter. It cannot answer the
question CoastLife asked — do accounts MOVE between tiers, and in which
direction. That needs the same account measured in two windows.

Basis (matches ticket_calc.py / the workbook Segmentation Legend):
  tier = 3-month average monthly swipes (Sig # + PIN #)
  0 / 1-5 / 6-10 / 11-15 / 16-20 / 21-25 / 26+

Windows are YEAR-OVER-YEAR — the trailing quarter against the same quarter a
year earlier — so seasonality cancels. A sequential comparison would put the
holidays on one side and not the other.

Population is ARS-ELIGIBLE PRODUCTS, not Elig=Yes accounts: every account on a
product code the program can mail. The eligible-product set is derived the same
way excluded_accounts_slide does it (a code with at least one eligible account),
then filtered to codes carrying real volume — 1705 derives CB03 (14 accounts, 1
eligible) and CLRA (1 account, 1 eligible), which are data noise, not products.

TWO HONEST CAVEATS, carried onto the slide face rather than buried:
  * Responders self-select. This is association, not proven causation.
  * The end tiers are mechanically one-directional — tier 0 can only rise, 26+
    can only fall — and 26+ holds ~31% of the base. That is why slide 3 repeats
    the comparison on the middle tiers only, where movement can go either way.

Usage:  python3 tier_movement_slides.py <ODDD.zip|.csv> <out.pptx> [template.pptx]
"""
import collections, csv, io, json, os, re, sys, zipfile

from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, os.pardir))   # build/

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from brand import (
    NAVY_RGB as NAVY, ORANGE_RGB as ORANGE, WHITE_RGB as WHITE,
    TICK_RGB as GREYT, NAVY as _NAVY_HX, ORANGE as _ORANGE_HX,
    LABEL as _GREY_HX, TICK as _TICK_HX, HEAD, BODY,
)
from shapes import (
    textbox as _tb, pill as _pill, tile as _tile, fit_picture as _fit_picture,
    blank_slide as _blank_slide, slide_title as _slide_title,
    move_before as _move_before, renumber as _renumber,
)
from product_mix_slide import _MONFULL, _MIDX
from rpe_env import use_font
from periods import Period

TIER_MONTHS = 3
LOOKBACK = 12            # months between the two windows (year-over-year)
MIN_PRODUCT_ACCOUNTS = 25   # below this a "product" is noise, not a product

SEGDEF = [("0", 0, 0), ("1-5", 1, 5), ("6-10", 6, 10), ("11-15", 11, 15),
          ("16-20", 16, 20), ("21-25", 21, 25), ("26+", 26, 10 ** 9)]
TIERS = [s[0] for s in SEGDEF]
RANK = {k: i for i, k in enumerate(TIERS)}
MIDBAND = TIERS[1:-1]    # 1-5 .. 21-25 — no floor, no ceiling


def seg_of(permo):
    if permo < 1:
        return "0"
    for name, lo, hi in SEGDEF[1:]:
        if lo <= permo <= hi:
            return name
    return "26+"


def num(s):
    s = (s or "").strip().replace(",", "").replace("$", "")
    if not s or s in ("-", "."):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def _open_source(src):
    """Yield a fresh text stream over the ODD csv (mirrors lift_extract)."""
    if src.lower().endswith(".zip"):
        zf = zipfile.ZipFile(src)
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise SystemExit(f"ERROR: no .csv inside {src}")
        odd = [n for n in members if "-odd" in n.lower() or "_v2_" in n.lower()]
        member = odd[0] if odd else max(members, key=lambda n: zf.getinfo(n).file_size)

        def factory():
            raw = io.TextIOWrapper(zf.open(member), encoding="utf-8",
                                   errors="replace", newline="")
            return (line.replace("\0", "") for line in raw)
        return factory, os.path.basename(member)

    def factory():
        raw = open(src, encoding="utf-8", errors="replace", newline="")
        return (line.replace("\0", "") for line in raw)
    return factory, os.path.basename(src)


def _find_header(factory):
    for i, row in enumerate(csv.reader(factory())):
        if any(str(c).strip() == "Acct ID" for c in row):
            return i, [str(c).strip() for c in row]
        if i > 25:
            break
    raise SystemExit("ERROR: could not locate the 'Acct ID' header row")


def _matrix(pop):
    """Full 7x7 transition count, baseline tier -> current tier."""
    c = collections.Counter((x["sb"], x["sc"]) for x in pop)
    return {f"{a}|{b}": c[(a, b)] for a in TIERS for b in TIERS}


def _stats(pop):
    """Movement summary for one population of per-account records."""
    n = len(pop)
    if not n:
        return None
    up = sum(1 for x in pop if RANK[x["sc"]] > RANK[x["sb"]])
    dn = sum(1 for x in pop if RANK[x["sc"]] < RANK[x["sb"]])
    bt = collections.Counter(x["sb"] for x in pop)
    ct = collections.Counter(x["sc"] for x in pop)
    dorm = [x for x in pop if x["sb"] == "0"]
    return dict(
        n=n, up=up, down=dn, same=n - up - dn,
        up_p=up / n, down_p=dn / n, same_p=(n - up - dn) / n, net=(up - dn) / n,
        sw_b=sum(x["b"] for x in pop) / n, sw_c=sum(x["c"] for x in pop) / n,
        sp_b=sum(x["spb"] for x in pop) / n, sp_c=sum(x["spc"] for x in pop) / n,
        base_mix={k: bt[k] for k in TIERS}, cur_mix={k: ct[k] for k in TIERS},
        matrix=_matrix(pop),
        dorm_n=len(dorm),
        dorm_re=sum(1 for x in dorm if x["sc"] != "0"),
    )


def extract_tier_movement(odd_source):
    factory, base_file = _open_source(odd_source)
    hdr_idx, hdr = _find_header(factory)
    idx = {h: i for i, h in enumerate(hdr)}

    months = [m.group(1) for m in
              (re.match(r"^([A-Z][a-z]{2}\d{2}) Sig #$", h) for h in hdr) if m]
    need = LOOKBACK + TIER_MONTHS
    if len(months) < need:
        raise SystemExit(f"ERROR: ODD carries {len(months)} months, need {need}")
    cur_win = months[-TIER_MONTHS:]
    base_win = months[-(LOOKBACK + TIER_MONTHS):-LOOKBACK]

    # The eligibility flag is stamped on the latest month only.
    elig_c = idx.get(f"{months[-1]} Elig")
    if elig_c is None:
        raise SystemExit(f"ERROR: no '{months[-1]} Elig' column in the ODD")
    resp_cols = [idx[m + " Resp"] for m in months[-LOOKBACK:] if m + " Resp" in idx]
    if not resp_cols:
        raise SystemExit("ERROR: no '<Mon> Resp' columns in the trailing 12 months")

    cur_sw = [(idx[m + " Sig #"], idx[m + " PIN #"]) for m in cur_win]
    bas_sw = [(idx[m + " Sig #"], idx[m + " PIN #"]) for m in base_win]
    cur_sp = [(idx[m + " Sig $"], idx[m + " PIN $"]) for m in cur_win]
    bas_sp = [(idx[m + " Sig $"], idx[m + " PIN $"]) for m in base_win]
    pc, pdc = idx["Prod Code"], idx["Prod Desc"]

    reader = csv.reader(factory())
    for _ in range(hdr_idx + 1):
        next(reader, None)

    ncol = len(hdr)
    raw, prod_n, prod_elig, prod_desc = [], collections.Counter(), collections.Counter(), {}
    for row in reader:
        if len(row) < ncol:
            continue
        code = row[pc].strip()
        prod_n[code] += 1
        prod_desc.setdefault(code, row[pdc].strip())
        is_elig = row[elig_c].strip() == "Yes"
        if is_elig:
            prod_elig[code] += 1
        b = sum(num(row[a]) + num(row[x]) for a, x in bas_sw) / TIER_MONTHS
        c = sum(num(row[a]) + num(row[x]) for a, x in cur_sw) / TIER_MONTHS
        raw.append(dict(
            prod=code, elig=is_elig,
            resp=any(row[q].strip() for q in resp_cols),
            sb=seg_of(b), sc=seg_of(c), b=b, c=c,
            spb=sum(num(row[a]) + num(row[x]) for a, x in bas_sp) / TIER_MONTHS,
            spc=sum(num(row[a]) + num(row[x]) for a, x in cur_sp) / TIER_MONTHS))

    # eligible PRODUCTS: a code the program can mail, carrying real volume
    elig_prods = sorted(p for p in prod_elig
                        if prod_elig[p] > 0 and prod_n[p] >= MIN_PRODUCT_ACCOUNTS)
    dropped = sorted(p for p in prod_elig if p not in elig_prods)

    pop = [x for x in raw if x["prod"] in elig_prods]
    resp = [x for x in pop if x["resp"]]
    non = [x for x in pop if not x["resp"]]
    mid = lambda g: [x for x in g if x["sb"] in MIDBAND]

    lm = months[-1]
    return dict(
        source_file=base_file, months=months, base_win=base_win, cur_win=cur_win,
        base_label=_win_label(base_win), cur_label=_win_label(cur_win),
        month_label=Period(lm).label(),
        elig_prods=elig_prods, dropped_prods=dropped,
        prod_rows=[(p, prod_desc.get(p) or "(no description)", prod_n[p], prod_elig[p])
                   for p in elig_prods],
        n_resp_mailings=len(resp_cols),
        base=_stats(pop), resp=_stats(resp), nonresp=_stats(non),
        mid_resp=_stats(mid(resp)), mid_nonresp=_stats(mid(non)),
    )


def _win_label(win):
    """'May–Jul 2026' — collapsed to one year by periods.trailing when it fits."""
    return Period(win[-1]).trailing(len(win))


# ----------------------------------------------------------------------------- charts
def _save(fig, assets_dir, name, dpi=300):
    """Saved WITHOUT bbox_inches='tight' — the slide boxes are a fixed aspect and
    tight-trimming changes it per chart, which left the wide charts under-filling
    their band with white rails on both sides."""
    path = os.path.join(assets_dir, name)
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return path


def _despine(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(_GREY_HX)
    ax.spines["bottom"].set_color(_GREY_HX)
    ax.tick_params(colors=_TICK_HX, labelsize=10.5)


def render_charts(data, assets_dir):
    os.makedirs(assets_dir, exist_ok=True)
    use_font("Carlito")
    out = {}

    # ---- 1. tier mix, baseline vs current (the "nothing moved" picture) ----
    # Figure aspect matches the slide band (12.25 x 2.86) so the chart fills it.
    b, c = data["base"]["base_mix"], data["base"]["cur_mix"]
    n = data["base"]["n"]
    bp = [b[k] / n * 100 for k in TIERS]
    cp = [c[k] / n * 100 for k in TIERS]
    fig = plt.figure(figsize=(12.25, 2.86))
    ax = fig.add_axes([0.048, 0.175, 0.945, 0.700])
    x = range(len(TIERS)); w = 0.34
    ax.bar([i - w / 2 for i in x], bp, w, color=_GREY_HX, label=data["base_label"])
    ax.bar([i + w / 2 for i in x], cp, w, color=_ORANGE_HX, label=data["cur_label"])
    top = max(bp + cp)
    for i, (u, v) in enumerate(zip(bp, cp)):
        ax.text(i - w / 2, u + top * 0.020, f"{u:.1f}%", ha="center",
                fontsize=9.5, color=_TICK_HX)
        ax.text(i + w / 2, v + top * 0.020, f"{v:.1f}%", ha="center",
                fontsize=9.5, color=_ORANGE_HX, fontweight="bold")
        # delta sits ABOVE the pair; putting it below collided with the tier ticks
        ax.text(i, max(u, v) + top * 0.105, f"{v - u:+.1f}pp", ha="center",
                fontsize=11, color=_NAVY_HX, fontweight="bold")
    ax.set_xticks(list(x)); ax.set_xticklabels(TIERS, fontsize=12.5, color=_TICK_HX)
    ax.set_ylabel("% of accounts", fontsize=11, color=_TICK_HX)
    ax.set_xlabel("Monthly swipe tier", fontsize=12, color=_TICK_HX, labelpad=4)
    ax.set_ylim(0, top * 1.30)
    ax.legend(frameon=False, fontsize=11.5, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 1.06))
    _despine(ax)
    out["mix"] = _save(fig, assets_dir, "tm_mix.png")

    # ---- 2. up / held / down, responders vs the rest ----
    fig = plt.figure(figsize=(6.75, 2.80))
    ax = fig.add_axes([0.085, 0.115, 0.895, 0.815])
    groups = [("Responders", data["resp"], _ORANGE_HX),
              ("Non-responders", data["nonresp"], _NAVY_HX)]
    cats = ["Moved up", "Held tier", "Moved down"]
    x = range(len(cats)); w = 0.34
    for gi, (lab, d, col) in enumerate(groups):
        vals = [d["up_p"] * 100, d["same_p"] * 100, d["down_p"] * 100]
        pos = [i + (gi - 0.5) * w for i in x]
        ax.bar(pos, vals, w, color=col, label=f"{lab}  (n={d['n']:,})")
        for q, v in zip(pos, vals):
            ax.text(q, v + 1.6, f"{v:.1f}%", ha="center", fontsize=10.5,
                    color=col, fontweight="bold")
    ax.set_xticks(list(x)); ax.set_xticklabels(cats, fontsize=12, color=_TICK_HX)
    ax.set_ylim(0, 98)
    ax.set_ylabel("% of accounts", fontsize=11, color=_TICK_HX)
    ax.legend(frameon=False, fontsize=10.5, loc="upper left")
    _despine(ax)
    out["split"] = _save(fig, assets_dir, "tm_split.png")

    # ---- 3. dormant reactivation ----
    fig = plt.figure(figsize=(5.30, 2.52))
    ax = fig.add_axes([0.135, 0.105, 0.845, 0.845])
    rr = data["resp"]["dorm_re"] / data["resp"]["dorm_n"] * 100
    nr = data["nonresp"]["dorm_re"] / data["nonresp"]["dorm_n"] * 100
    bars = ax.bar(["Responders", "Non-responders"], [rr, nr], 0.46,
                  color=[_ORANGE_HX, _NAVY_HX])
    for bar, v, d in zip(bars, [rr, nr], [data["resp"], data["nonresp"]]):
        cx = bar.get_x() + bar.get_width() / 2
        ax.text(cx, v + max(rr, nr) * 0.045, f"{v:.1f}%", ha="center",
                fontsize=15, fontweight="bold", color=bar.get_facecolor())
        ax.text(cx, v / 2, f"{d['dorm_re']:,}\nof {d['dorm_n']:,}", ha="center",
                va="center", fontsize=10.5, color="white", fontweight="bold")
    ax.set_ylim(0, max(rr, nr) * 1.30)
    ax.set_ylabel("% back to active swiping", fontsize=10.5, color=_TICK_HX)
    _despine(ax)
    ax.tick_params(labelsize=12)
    out["dormant"] = _save(fig, assets_dir, "tm_dormant.png")

    # ---- 4. like-for-like mid-band: net movement + swipes ----
    fig = plt.figure(figsize=(12.25, 2.86))
    mr, mn = data["mid_resp"], data["mid_nonresp"]
    axl = fig.add_axes([0.105, 0.150, 0.335, 0.700])
    vals = [mr["net"] * 100, mn["net"] * 100]
    # barh draws the first item at the BOTTOM, so feed it reversed to get
    # Responders on top — the order every other slide reads in.
    bars = axl.barh(["Non-responders", "Responders"], vals[::-1], 0.42,
                    color=[_NAVY_HX, _ORANGE_HX])
    vals = vals[::-1]
    span = max(abs(v) for v in vals)
    for bar, v in zip(bars, vals):
        axl.text(v + (span * 0.05 if v >= 0 else -span * 0.05),
                 bar.get_y() + bar.get_height() / 2, f"{v:+.1f}%", va="center",
                 ha="left" if v >= 0 else "right", fontsize=14.5,
                 fontweight="bold", color=bar.get_facecolor())
    axl.axvline(0, color=_TICK_HX, lw=1)
    axl.set_xlim(-span * 1.55, span * 1.55)
    axl.set_title("Net tier movement", fontsize=13, color=_NAVY_HX,
                  fontweight="bold", pad=8)
    for sp in ("top", "right", "bottom"):
        axl.spines[sp].set_visible(False)
    axl.spines["left"].set_color(_GREY_HX)
    axl.tick_params(colors=_TICK_HX, labelsize=12); axl.set_xticks([])

    axr = fig.add_axes([0.585, 0.150, 0.365, 0.700])
    for d, lab, col in ((mr, "Responders", _ORANGE_HX),
                        (mn, "Non-responders", _NAVY_HX)):
        axr.plot([0, 1], [d["sw_b"], d["sw_c"]], "-o", color=col, lw=3.2,
                 markersize=9, label=lab)
        axr.text(-0.05, d["sw_b"], f"{d['sw_b']:.1f}", ha="right", va="center",
                 fontsize=12.5, color=col, fontweight="bold")
        axr.text(1.05, d["sw_c"], f"{d['sw_c']:.1f}", ha="left", va="center",
                 fontsize=12.5, color=col, fontweight="bold")
    axr.set_xlim(-0.38, 1.38)
    axr.set_xticks([0, 1])
    axr.set_xticklabels([data["base_label"], data["cur_label"]],
                        fontsize=11.5, color=_TICK_HX)
    lo = min(mr["sw_b"], mr["sw_c"], mn["sw_b"], mn["sw_c"])
    hi = max(mr["sw_b"], mr["sw_c"], mn["sw_b"], mn["sw_c"])
    axr.set_ylim(lo - (hi - lo) * 0.35, hi + (hi - lo) * 0.30)
    axr.set_title("Average monthly swipes per account", fontsize=13,
                  color=_NAVY_HX, fontweight="bold", pad=8)
    # 'lower left' landed the legend directly on the non-responder start label;
    # the upper-left corner is empty in both series.
    axr.legend(frameon=False, fontsize=10.5, loc="upper left")
    _despine(axr)
    out["midband"] = _save(fig, assets_dir, "tm_midband.png")
    return out


# ----------------------------------------------------------------------------- slides
def _footer(slide, assets_dir, note):
    """Source goes in the notes, never on the slide face (STYLE.md)."""
    slide.notes_slide.notes_text_frame.text = note
    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        slide.shapes.add_picture(logo, Inches(11.28), Inches(6.78),
                                 Inches(1.70), Inches(0.54))


def _head(slide, title, subtitle, pill):
    _tb(slide, 0.5, 0.28, 9.6, 0.9, title, 26, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    _pill(slide, pill)
    _tb(slide, 0.5, 1.12, 12.3, 0.5, subtitle, 14, GREYT, False,
        PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)


def add_tier_movement_slides(prs, data, assets_dir,
                             before_title="Average Ticket by Swipe Segment",
                             renumber=True):
    ch = render_charts(data, assets_dir)
    template = next((s for s in prs.slides
                     if _slide_title(s).startswith(before_title)), prs.slides[0])
    d, r, nr = data["base"], data["resp"], data["nonresp"]
    mr, mn = data["mid_resp"], data["mid_nonresp"]
    src = (f"Source: client ODD, {data['month_label']} snapshot ({data['source_file']}). "
           f"Tier = {TIER_MONTHS}-month average monthly swipes (Sig # + PIN #), the "
           f"Segmentation Legend basis. Windows {data['base_label']} vs "
           f"{data['cur_label']} — year-over-year, so seasonality cancels. Population "
           f"= all accounts on ARS-eligible product codes "
           f"({', '.join(data['elig_prods'])})"
           + (f"; codes {', '.join(data['dropped_prods'])} carry an eligible account "
              f"but under {MIN_PRODUCT_ACCOUNTS} accounts total and are excluded as noise"
              if data["dropped_prods"] else "") + ". ")
    made = []

    # ---------- slide 1: the base barely moved ----------
    s = _blank_slide(prs, template)
    _head(s, "ARS-Eligible Products — Swipe Tier Movement",
          f"{d['n']:,} accounts on {len(data['elig_prods'])} eligible checking products, "
          f"measured in {data['base_label']} and again in {data['cur_label']}. "
          f"Tier = 3-month average monthly swipes.",
          f"{data['cur_label']}")
    for i, (v, l, f) in enumerate([
            (f"{d['n']:,}", "Accounts on eligible products", NAVY),
            (f"{d['up_p']*100:.1f}%", "Moved up a tier", ORANGE),
            (f"{d['same_p']*100:.1f}%", "Held their tier", NAVY),
            (f"{d['net']*100:+.1f}%", "Net movement", NAVY)]):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 1.28, v, l, fill=f)
    _fit_picture(s, ch["mix"], 0.55, 3.10, 12.25, 2.86)
    _tb(s, 0.5, 6.12, 12.3, 0.56,
        f"Across the eligible base the tier mix is essentially unchanged — every tier "
        f"moves less than half a point, and net movement is {d['net']*100:+.1f}%. "
        f"The program's effect is not visible at this level.",
        11.5, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    _footer(s, assets_dir, src + "Net movement = share moving up minus share moving down.")
    made.append(s)

    # ---------- slide 2: two populations pulling apart ----------
    s = _blank_slide(prs, template)
    _head(s, "The Base Is Two Populations",
          f"The same accounts split by whether they responded to any of the last "
          f"{data['n_resp_mailings']} ARS mailings. The two groups move in opposite directions.",
          f"{data['cur_label']}")
    for i, (v, l, f) in enumerate([
            (f"{r['net']*100:+.1f}%", f"Responder net movement (n={r['n']:,})", ORANGE),
            (f"{nr['net']*100:+.1f}%", f"Non-responder net movement (n={nr['n']:,})", NAVY),
            (f"{r['sw_c']/r['sw_b']-1:+.1%}", "Responder swipes/account", ORANGE),
            (f"{nr['sw_c']/nr['sw_b']-1:+.1%}", "Non-responder swipes/account", NAVY)]):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 1.28, v, l, fill=f)
    _fit_picture(s, ch["split"], 0.55, 3.16, 6.75, 2.80)
    _tb(s, 7.55, 3.04, 5.3, 0.34, "Dormant accounts returning to active use",
        13, NAVY, True, PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    _fit_picture(s, ch["dormant"], 7.55, 3.44, 5.3, 2.52)
    _tb(s, 0.5, 6.12, 12.3, 0.56,
        f"Responders moved up {r['up_p']*100:.1f}% of the time against "
        f"{nr['up_p']*100:.1f}% for non-responders, and reactivated dormant accounts at "
        f"{r['dorm_re']/r['dorm_n']*100:.0f}% against "
        f"{nr['dorm_re']/nr['dorm_n']*100:.0f}%. Responders self-select, so this is "
        f"association, not proven causation.",
        11.5, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    _footer(s, assets_dir, src +
            f"Responder = any '<Mon> Resp' flag in the trailing {LOOKBACK} months "
            f"({data['n_resp_mailings']} mailings). Dormant = tier 0 (under 1 swipe/month) "
            f"in the baseline window.")
    made.append(s)

    # ---------- slide 3: like-for-like, floor and ceiling removed ----------
    s = _blank_slide(prs, template)
    _head(s, "Like-for-Like — Tiers 1-5 through 21-25",
          f"Tier 0 can only rise and 26+ can only fall, and 26+ holds "
          f"{d['base_mix']['26+']/d['n']*100:.0f}% of the base. Removing both end tiers "
          f"leaves {mr['n']+mn['n']:,} accounts that were free to move either way.",
          f"{data['cur_label']}")
    for i, (v, l, f) in enumerate([
            (f"{mr['net']*100:+.1f}%", f"Responder net movement (n={mr['n']:,})", ORANGE),
            (f"{mn['net']*100:+.1f}%", f"Non-responder net movement (n={mn['n']:,})", NAVY),
            (f"{mr['sw_c']/mr['sw_b']-1:+.1%}", "Responder swipes/account", ORANGE),
            (f"{mn['sw_c']/mn['sw_b']-1:+.1%}", "Non-responder swipes/account", NAVY)]):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 1.28, v, l, fill=f)
    _fit_picture(s, ch["midband"], 0.55, 3.10, 12.25, 2.86)
    _tb(s, 0.5, 6.12, 12.3, 0.56,
        f"On equal footing the gap holds: responders net {mr['net']*100:+.1f}% against "
        f"{mn['net']*100:+.1f}%, with swipes {mr['sw_b']:.1f} → {mr['sw_c']:.1f} per month "
        f"against {mn['sw_b']:.1f} → {mn['sw_c']:.1f}. Read as association — responders "
        f"choose to respond, and accounts already trending up are likelier to engage.",
        11.5, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    _footer(s, assets_dir, src +
            "Mid-band excludes baseline tier 0 and 26+, where movement is mechanically "
            "one-directional. Spend = (Sig $ + PIN $) monthly average.")
    made.append(s)

    for s in made:
        _move_before(prs, s, before_title)
    if renumber:
        _renumber(prs)
    return made


def build_standalone(odd_source, out_path, template):
    data = extract_tier_movement(odd_source)
    prs = Presentation(template)
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(out_path)), "tm_assets")
    keep = add_tier_movement_slides(prs, data, assets_dir, renumber=False)
    keep_ids = {id(s) for s in keep}
    xml_slides = prs.slides._sldIdLst
    for sldId, slide in list(zip(list(xml_slides), list(prs.slides))):
        if id(slide) not in keep_ids:
            prs.part.drop_rel(sldId.rId)   # unreference the part, not just the id
            xml_slides.remove(sldId)
    prs.save(out_path)
    return data, out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    src, out = sys.argv[1], sys.argv[2]
    tpl = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "templates", "ars_template.pptx")
    data, path = build_standalone(src, out, tpl)
    print(f"{data['source_file']}\n  eligible products  "
          f"{', '.join(data['elig_prods'])}"
          f"{'  (dropped ' + ', '.join(data['dropped_prods']) + ')' if data['dropped_prods'] else ''}"
          f"\n  windows            {data['base_label']} -> {data['cur_label']}"
          f"\n  base               n={data['base']['n']:,}  net {data['base']['net']*100:+.1f}%"
          f"\n  responders         n={data['resp']['n']:,}  net {data['resp']['net']*100:+.1f}%"
          f"\n  non-responders     n={data['nonresp']['n']:,}  net {data['nonresp']['net']*100:+.1f}%"
          f"\n  mid-band resp      n={data['mid_resp']['n']:,}  net {data['mid_resp']['net']*100:+.1f}%"
          f"\n  mid-band non-resp  n={data['mid_nonresp']['n']:,}  net {data['mid_nonresp']['net']*100:+.1f}%"
          f"\n  saved              {path}")
