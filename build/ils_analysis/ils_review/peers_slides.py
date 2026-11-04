"""
How the client compares with other ILS clients: NSF/OD items per 1,000 open accounts, collected fees per open account and
NSF/OD users as a share of open accounts, one slide per account type (Aaron, 2026-11-04: "create peer comparisons like we did
with the LR set. for very large clients compare to other very large FI. For smaller clients compare within their region").

Built on Live Review's peer arithmetic, `build/peer_compare.py` (MIN_PEERS = 5, quantiles, rank, the +/-2% wording), so a
slide here and a Live Review screen cannot disagree about a median.

WHO IS A PEER, in one place:
  * the pool is every other ILS client in `Client CSM List.csv` (products contains ILS, status Active);
  * a client is VERY LARGE when its assets are VERY_LARGE_ASSETS_M ($10B) or more, or its DDA count is in the top
    VERY_LARGE_TOP_SHARE (10%) of ILS clients (the larger of the two tests names the group);
  * a very large client is compared with the other very large clients; any other client with the other clients in its
    Census region that are not very large (REGION_OF_STATE; Achieva is South, Affinity Northeast);
  * a peer counts only when its extract is current (pulled within PEER_MAX_AGE_MONTHS of this client's data);
  * a measure with fewer than MIN_PEERS peers is not drawn and the slide says so.

WHAT A PEER SHOWS: its CLIENT NUMBER and its value, nothing else (no name, logo, CSM, city or state). On the slide only the
highest and lowest peer carry their number; the speaker notes list every peer's number and value. The values come from each
peer's own newest ZAccounts extract (`peer_pull.py`), read for four columns.
"""
from __future__ import annotations

import csv
import os

import numpy as np

import shapes
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from . import client_slides as CS
from . import r_common as R
from . import theme as T

import peer_compare as PC                                      # noqa: E402  (build/ is on sys.path via theme)
import rpe_env                                                 # noqa: E402

MIN_PEERS = PC.MIN_PEERS                    # five, as Live Review
VERY_LARGE_ASSETS_M = 10_000                # $10B, in millions (the one size constant)
VERY_LARGE_TOP_SHARE = 0.10                 # ... or the top 10% of ILS clients by DDA count
PEER_MAX_AGE_MONTHS = 14

REGION_OF_STATE = {}
for _region, _states in {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}.items():
    for _s in _states.split():
        REGION_OF_STATE[_s] = _region

METRICS = [
    {"key": "items_per_1k", "label": "NSF/OD items per 1,000 open accounts", "fmt": "int", "higher": None},
    {"key": "fees_per_acct", "label": "Collected fees per open account", "fmt": "usd2", "higher": None},
    {"key": "users_pct", "label": "NSF/OD users, share of open accounts", "fmt": "pct1", "higher": None},
]


# ═════════════════════════════ the pool ═════════════════════════════════════════
def _f(v):
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def read_directory(path=None):
    """ILS clients from the Client CSM List: [{id, state, region, assets_m, dda}], product ILS, status Active."""
    p = path or rpe_env.csm_list_file()
    rows = []
    if not p or not os.path.isfile(str(p)):
        return rows
    for r in csv.DictReader(open(str(p), encoding="utf-8-sig")):
        if "ILS" not in [x.strip() for x in (r.get("products") or "").split(";")]:
            continue
        if (r.get("velocity_status") or "").strip().lower() not in ("active", ""):
            continue
        st = (r.get("state") or "").strip().upper()
        rows.append({"id": str(r["client_id"]).strip(), "state": st, "region": REGION_OF_STATE.get(st), "assets_m": _f(r.get("assets_millions")),
                     "dda": _f(r.get("dda_accounts"))})
    return rows


def dda_threshold(directory):
    d = sorted(x["dda"] for x in directory if x["dda"])
    if not d:
        return None
    return float(np.quantile(d, 1 - VERY_LARGE_TOP_SHARE))


def is_very_large(row, thr):
    return bool((row.get("assets_m") or 0) >= VERY_LARGE_ASSETS_M or (thr is not None and (row.get("dda") or 0) >= thr and row.get("dda")))


def peer_group(client_id, directory):
    """-> (group label, [peer client ids], note) for the client; ids are those that SHOULD be peers, before data currency."""
    me = next((r for r in directory if r["id"] == str(client_id)), None)
    if me is None:
        return None, [], f"client {client_id} is not in the Client CSM List as an ILS client, so no peer group can be named"
    thr = dda_threshold(directory)
    others = [r for r in directory if r["id"] != me["id"]]
    if is_very_large(me, thr):
        ids = [r["id"] for r in others if is_very_large(r, thr)]
        return "very large ILS clients", ids, ""
    if not me["region"]:
        return None, [], f"client {client_id} has no state in the Client CSM List, so its Census region is unknown"
    ids = [r["id"] for r in others if r["region"] == me["region"] and not is_very_large(r, thr)]
    return f"ILS clients in the {me['region']} region", ids, ""


def read_metrics(path=None):
    """{(client_id, accttype): row} from the peer metrics table."""
    from . import peer_pull
    files = [path] if path else peer_pull.metrics_files()
    out = {}
    for p in files:
        if os.path.isfile(p):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                out[(r["client_id"], r["accttype"])] = r
    return out


def own_metrics(fr, t):
    o = fr.open_accounts(t)
    if o.empty:
        return None
    import pandas as pd
    items = pd.to_numeric(o["items365"], errors="coerce").fillna(0)
    fees = pd.to_numeric(o["CollectedFees365"], errors="coerce").fillna(0.0)
    return {"open_accounts": len(o), "items365": float(items.sum()), "fees365": float(fees.sum()), "users365": int((items > 0).sum())}


def values(m):
    n = float(m["open_accounts"])
    if n <= 0:
        return None
    return {"items_per_1k": float(m["items365"]) / n * 1000.0, "fees_per_acct": float(m["fees365"]) / n, "users_pct": float(m["users365"]) / n * 100.0}


def _months_between(a, b):
    return abs((int(a[:4]) - int(b[:4])) * 12 + int(a[4:6]) - int(b[4:6]))


# ═════════════════════════════ the strip plots ═════════════════════════════════
def render_strips(items, out_png, w_in, h_in, who="Another client"):
    """One strip per metric: peers as dots, the middle half shaded, the median ticked, this client in orange; the highest and
    lowest peer carry their client number."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from brand import NAVY, ORANGE, TICK, LABEL, STEEL, GRID
    rpe_env.use_font("Carlito")
    n = len(items)
    legend_h = 0.42
    row_h = (h_in - legend_h) / max(n, 1)
    fig = plt.figure(figsize=(w_in, h_in))
    for k, it in enumerate(items):
        c, spec = it["c"], it["spec"]
        f = PC.formatter(spec["fmt"])
        top = 1 - (k * row_h) / h_in
        ax = fig.add_axes([0.03, top - row_h / h_in + 0.02 / h_in * 4, 0.94, (row_h - 0.12) / h_in])
        vals = list(c["dots"]) + [c["client"]]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or max(abs(hi), 1.0)
        pad = span * 0.12
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(-1.7, 3.4)
        ax.axis("off")
        ax.plot([lo, hi], [0, 0], color=GRID, lw=2, zorder=1, solid_capstyle="round")
        ax.add_patch(Rectangle((c["q1"], -0.45), max(c["q3"] - c["q1"], span * 0.004), 0.9, facecolor=LABEL, edgecolor="none", zorder=2))
        order = sorted(range(len(c["dots"])), key=lambda i: c["dots"][i])
        ys = [(((j * 0.6180339887) % 1.0) - 0.5) * 0.62 for j in range(len(order))]
        ax.scatter([c["dots"][i] for i in order], ys, s=70, color=STEEL, alpha=0.9, edgecolors="white", linewidths=0.8, zorder=3)
        ids = c.get("dot_ids")
        if ids:
            for i, ha in ((order[0], "left"), (order[-1], "right")):
                ax.text(c["dots"][i], -1.05, f"Client {ids[i]}", ha=ha, va="top", fontsize=12, color=TICK)
        ax.plot([c["median"]] * 2, [-0.62, 0.62], color=NAVY, lw=3.2, zorder=4, solid_capstyle="butt")
        ax.scatter([c["client"]], [0], s=330, color=ORANGE, edgecolors="white", linewidths=2.2, zorder=5)
        ax.text(c["client"], 0.5, f(c["client"]), ha="center", va="bottom", fontsize=17, fontweight="bold", color=ORANGE, zorder=6)
        ax.text(lo - pad, 3.4, spec["label"], ha="left", va="top", fontsize=15, fontweight="bold", color=NAVY)
        ax.text(c["median"], -0.78, f"median {f(c['median'])}", ha="center", va="top", fontsize=12.5, color=TICK)
    kx = fig.add_axes([0.03, 0.0, 0.94, legend_h / h_in])
    kx.set_xlim(0, 1)
    kx.set_ylim(0, 1)
    kx.axis("off")
    kx.scatter([0.015], [0.5], s=70, color=STEEL, edgecolors="white", linewidths=0.8)
    kx.text(0.035, 0.5, who, va="center", fontsize=13, color=TICK)
    kx.add_patch(Rectangle((0.255, 0.22), 0.045, 0.56, facecolor=LABEL, edgecolor="none"))
    kx.text(0.31, 0.5, "Middle half of peers", va="center", fontsize=13, color=TICK)
    kx.plot([0.605, 0.605], [0.18, 0.82], color=NAVY, lw=3.2, solid_capstyle="butt")
    kx.text(0.62, 0.5, "Median", va="center", fontsize=13, color=TICK)
    kx.scatter([0.74], [0.5], s=150, color=ORANGE, edgecolors="white", linewidths=1.6)
    kx.text(0.76, 0.5, "This client", va="center", fontsize=13, color=TICK)
    fig.savefig(out_png, dpi=200, facecolor="white")
    plt.close(fig)
    return out_png


def _rank_text(c):
    # the metrics here have no better direction, so say where the client sits, highest first
    return f"{PC.ordinal(c['rank'])} highest of {int(c['total'])} clients"


# ═════════════════════════════ the slides ═══════════════════════════════════════
def add_peers(dk, cfg, fr, S, *, section, progress=None):
    notes = []
    pool = getattr(cfg, "peer_pool", None)
    directory = pool["directory"] if pool else read_directory()
    table = pool["metrics"] if pool else read_metrics()
    group, ids, why = peer_group(cfg.client_id, directory)
    if group is None:
        return [f"Peer comparison skipped: {why}."]
    asof = f"{fr.asof.year}{fr.asof.month:02d}"
    for t in ("Personal", "Business"):
        mine = own_metrics(fr, t)
        if mine is None:
            continue
        mv = values(mine)
        by_metric = {m["key"]: ([], []) for m in METRICS}
        stamps = []
        for cid in ids:
            row = table.get((cid, t))
            if not row or _months_between(str(row["as_of"])[:6], asof) > PEER_MAX_AGE_MONTHS:
                continue
            pv = values({"open_accounts": float(row["open_accounts"]), "items365": float(row["items365"]),
                         "fees365": float(row["fees365"]), "users365": float(row["users365"])})
            if pv is None:
                continue
            stamps.append(str(row["as_of"]))
            for m in METRICS:
                by_metric[m["key"]][0].append(pv[m["key"]])
                by_metric[m["key"]][1].append(cid)
        items = []
        for m in METRICS:
            vals_, pids = by_metric[m["key"]]
            c = PC.compare_values(m, mv[m["key"]], vals_, pids)
            if c is not None:
                items.append({"spec": m, "c": c})
        n_have = len(by_metric[METRICS[0]["key"]][0])
        title = f"{t} accounts against {n_have} {group}" if items else f"{t} accounts: peer comparison not shown"
        sub = (f"Open {t.lower()} accounts per client, 365 days to each client's own data date; {len(ids)} other clients are in the group, {n_have} have current data."
               if items else f"Fewer than {MIN_PEERS} other clients in the group ({group}) have current data for this account type.")
        s = dk.content(title, sub, section=section,
                       source=CS._src(cfg, fr, "za", extra=f"Peers: {group}; {n_have} of {len(ids)} with an extract pulled within {PEER_MAX_AGE_MONTHS} months "
                                      f"({min(stamps) if stamps else 'n/a'} to {max(stamps) if stamps else 'n/a'}); metric values from each peer's own ZAccounts "
                                      f"extract (open accounts, items365, CollectedFees365); client numbers only."))
        if items:
            h = min(4.55, 1.6 * len(items) + 0.42)
            png = os.path.join(dk.chart_dir, f"peers_{t.lower()}.png")
            render_strips(items, png, 7.9, h)
            shapes.fit_picture(s, png, CS.LEFT, CS.BODY_T + 0.05, 7.9, h)
            row_h = (h - 0.42) / len(items)
            for k, it in enumerate(items):
                c = it["c"]
                f = PC.formatter(it["spec"]["fmt"])
                y = CS.BODY_T + 0.05 + k * row_h + 0.25
                shapes.textbox(s, 8.7, y, 4.1, 0.4, _rank_text(c), 18, T.ORANGE, True, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
                rel = PC.relation_phrase(c, f)
                shapes.textbox(s, 8.7, y + 0.4, 4.1, 0.9, rel[0].upper() + rel[1:] + ".", 15, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
            CS.caption(s, f"each dot is one other client in the group; the highest and lowest are labelled with their client numbers. "
                          f"A measure needs {MIN_PEERS} peers with current data.", T0=6.45, size=12)
            CS.say_first(s, f"This is where {t.lower()} sits against similar ILS clients on items, fees and users per open account.")
            lines = [f"Peer group: {group}. Very large = assets of ${VERY_LARGE_ASSETS_M / 1000:.0f}B or more, or in the top {VERY_LARGE_TOP_SHARE:.0%} of ILS clients by DDA count; "
                     f"other clients are compared within their Census region. Peers need an extract pulled within {PEER_MAX_AGE_MONTHS} months."]
            for it in items:
                c = it["c"]
                f = PC.formatter(it["spec"]["fmt"])
                lines.append(f"{it['spec']['label']}: client {f(c['client'])}; peers n = {c['n']}, median {f(c['median'])}, middle half {f(c['q1'])} to {f(c['q3'])}. "
                             "Peers by client number: " + "; ".join(f"{i} {f(v)}" for i, v in sorted(zip(c["dot_ids"], c["dots"]), key=lambda x: x[1])) + ".")
            s.notes_slide.notes_text_frame.text += "\n" + "\n".join(lines)
            dk.sidecars.append({"key": f"peers_{t.lower()}", "title": f"Peer comparison, {t}", "png": f"peers_{t.lower()}.png",
                                "numbers": {"group": group, "group_size": len(ids), "with_current_data": n_have,
                                            "client": mv, "metrics": {it["spec"]["key"]: {"n": it["c"]["n"], "median": it["c"]["median"], "q1": it["c"]["q1"],
                                                                                           "q3": it["c"]["q3"], "rank": it["c"]["rank"], "peer_ids": it["c"]["dot_ids"],
                                                                                           "peer_values": it["c"]["dots"]} for it in items}}})
        else:
            msg = (f"Not enough peers to compare: only {n_have} of the {len(ids)} other {group} have an ILS extract on file that is current "
                   f"(pulled within {PEER_MAX_AGE_MONTHS} months). Five are needed. This slide fills in when their extracts are pulled; nothing is estimated.")
            shapes.textbox(s, CS.LEFT + 0.2, 2.3, CS.FULL_W - 0.4, 2.0, msg, 22, T.NAVY, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
            CS.say_first(s, "We cannot show this comparison yet; here is why.")
            notes.append(f"Peer comparison, {t}: {n_have} peers with current data in {group}, {MIN_PEERS} needed.")
    if not any(sc.get("key", "").startswith("peers_") for sc in dk.sidecars):
        notes.append("Peer comparison: the peer metrics table has no current peers for this client's group; run `python -m ils_review.peer_pull`.")
    return notes
