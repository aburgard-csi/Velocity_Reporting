"""
competition_layers_modules.py — the analyses on the layered competition figures.

New to RPE (not a v5 port). Pure functions on the matched card rows `competition_layers.compute` leaves on
the context; each returns plain lists and dicts for the pack. A module that cannot be computed for a client
(no closure dates, no branch column) is absent from the figures and said in the build warnings, never zeroed.

  trend         card dollars, active accounts, PIN share and competitor share, by month and by group
  movement      relationships first seen / last seen in the last 90 days, per institution and per tier
  depth         the share of an account's card dollars each relationship takes (under 5%, 5-20%, 20%+)
  multi         how many distinct institutions each account pays
  recency       when each relationship was last paid
  distance      competitor dollars by the distance of the institution's nearest branch to a client branch
  winback       heavy (20%+) relationships still live, by institution and group (counts only)
  attrition     closure in the second half of the window by whether the account paid a competitor in the first
  branches      per ODD branch: transacting accounts, competitor share by tier, 12-month closure rate
  nearby        the competitor branches within the local radius of a client branch, for the map
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import competition_layers as CL

BANDS = ["under 5%", "5-20%", "20%+"]
RECENCY = ["live (30d)", "cooling (31-90d)", "quiet (91-180d)", "dormant (180d+)"]
WINBACK_TIERS = (CL.LOCAL, CL.LOCAL_MARKET, CL.REGIONAL, CL.STATE)


def branch_label(v) -> str:
    """An ODD branch as a person writes it: no decimal on a number, '(no branch)' when it is missing."""
    if (not isinstance(v, str) and pd.isna(v)) or str(v).strip().lower() in ("", "nan", "none"):
        return "(no branch)"
    t = str(v).strip()
    return t[:-2] if t.endswith(".0") else t


def _i(v):
    return int(v)


def trend(sub, sets):
    """Monthly card dollars, active accounts, PIN share and competitor share: the whole base, then each group."""
    d = pd.to_datetime(sub["date"])
    mc = (d.dt.year * 12 + d.dt.month).to_numpy()
    months = np.unique(mc)
    mi = np.searchsorted(months, mc)
    cat = pd.Categorical(sub["acct"])
    codes, cats = cat.codes.astype(np.int64), cat.categories
    amt = sub["amt"].to_numpy(dtype=float)
    pin = (sub["type"].astype(str).str.upper() == "PIN").to_numpy()
    comp = np.where(sub["inst"].notna().to_numpy(), amt, 0.0)
    rows = []
    for g, ids in [("all", None)] + list(sets.items()):
        mask = np.ones(len(amt), dtype=bool) if ids is None else cats.isin(list(ids))[codes]
        dollars = np.bincount(mi[mask], weights=amt[mask], minlength=len(months))
        pind = np.bincount(mi[mask], weights=(amt * pin)[mask], minlength=len(months))
        compd = np.bincount(mi[mask], weights=comp[mask], minlength=len(months))
        pair = np.unique(mi[mask].astype(np.int64) * len(cats) + codes[mask])
        active = np.bincount(pair // len(cats), minlength=len(months))
        for k, m in enumerate(months):
            y, mo = divmod(int(m) - 1, 12)
            rows.append({"month": f"{y}-{mo + 1:02d}", "group": g, "active": _i(active[k]), "dollars": round(float(dollars[k])),
                         "per_active": round(float(dollars[k]) / max(int(active[k]), 1), 1),
                         "pin_pct": round(float(pind[k]) / max(float(dollars[k]), 1.0) * 100, 1),
                         "competitor_dollars": round(float(compd[k])),
                         "competitor_pct": round(float(compd[k]) / max(float(dollars[k]), 1.0) * 100, 2)})
    return rows


def _pairs(matched, acct_total):
    p = matched.groupby(["inst", "acct"]).agg(dollars=("amt", "sum"), first=("date", "min"), last=("date", "max")).reset_index()
    p["tier"] = p["inst"].map(matched.groupby("inst")["tier"].first())
    p["share"] = p["dollars"] / p["acct"].map(acct_total).clip(lower=1.0)
    p["band"] = pd.cut(p["share"], [-1, 0.05, 0.20, 100], labels=BANDS, right=False)
    return p


def movement(matched, end, days=90):
    """Per institution: relationships, new and stopped in the last `days`, live in the last 30; and per tier."""
    p = matched.groupby(["inst", "acct"]).agg(first=("date", "min"), last=("date", "max")).reset_index()
    cut = end - pd.Timedelta(days=days)
    p["new"], p["stopped"] = p["first"] > cut, p["last"] <= cut
    p["live"] = p["last"] > end - pd.Timedelta(days=30)
    g = p.groupby("inst").agg(relationships=("acct", "size"), new_90=("new", "sum"), stopped_90=("stopped", "sum"), live_30=("live", "sum"))
    g["tier"] = matched.groupby("inst")["tier"].first()
    inst = [{"inst": k, "tier": r["tier"], "relationships": _i(r["relationships"]), "new_90": _i(r["new_90"]),
             "stopped_90": _i(r["stopped_90"]), "live_30": _i(r["live_30"])} for k, r in g.iterrows()]
    t = g.groupby("tier")[["relationships", "new_90", "stopped_90", "live_30"]].sum().astype(int)
    tiers = [{"tier": k, **{c: _i(r[c]) for c in t.columns}, "net_90": _i(r["new_90"] - r["stopped_90"])} for k, r in t.iterrows()]
    return inst, sorted(tiers, key=lambda r: -r["relationships"])


def depth(matched, acct_total):
    """(per tier, per institution): relationships by the share of the account's card dollars they take."""
    p = _pairs(matched, acct_total)
    w = p.groupby(["tier", "band"], observed=False).size().unstack(fill_value=0).reindex(columns=BANDS, fill_value=0)
    tiers = [{"tier": k, **{b: _i(r[b]) for b in BANDS}, "relationships": _i(r.sum()),
              "heavy_pct": round(r["20%+"] / max(r.sum(), 1) * 100, 1)} for k, r in w.iterrows()]
    g = p.groupby("inst").agg(tier=("tier", "first"), relationships=("acct", "size"),
                              median_share_pct=("share", lambda s: round(float(s.median()) * 100, 2)),
                              heavy=("band", lambda s: _i((s == "20%+").sum())), mid=("band", lambda s: _i((s == "5-20%").sum())))
    inst = [{"inst": k, "tier": r["tier"], "relationships": _i(r["relationships"]), "median_share_pct": float(r["median_share_pct"]),
             "heavy": _i(r["heavy"]), "mid": _i(r["mid"])} for k, r in g.iterrows()]
    return sorted(tiers, key=lambda r: -r["relationships"]), sorted(inst, key=lambda r: -r["heavy"])


def multi(matched, active, sets):
    """How many distinct institutions each active account pays (0 / 1 / 2 / 3+): the base, then each group."""
    n = matched.groupby("acct")["inst"].nunique().reindex(list(active)).fillna(0).astype(int)
    b = n.clip(upper=3).map({0: "0", 1: "1", 2: "2", 3: "3+"})
    rows = []
    for g, ids in [("all", None)] + list(sets.items()):
        s = b if ids is None else b[b.index.isin(ids)]
        tot = max(len(s), 1)
        for k in ("0", "1", "2", "3+"):
            rows.append({"group": g, "institutions": k, "accounts": _i((s == k).sum()), "pct": round((s == k).sum() / tot * 100, 1)})
    return rows


def recency(matched, end):
    p = matched.groupby(["inst", "acct"]).agg(last=("date", "max")).reset_index()
    p["tier"] = p["inst"].map(matched.groupby("inst")["tier"].first())
    age = (end - p["last"]).dt.days
    p["band"] = pd.cut(age, [-1, 30, 90, 180, 100000], labels=RECENCY)
    w = p.groupby(["tier", "band"], observed=False).size().unstack(fill_value=0).reindex(columns=RECENCY, fill_value=0)
    rows = [{"tier": k, **{b: _i(r[b]) for b in RECENCY}, "relationships": _i(r.sum())} for k, r in w.iterrows()]
    return sorted(rows, key=lambda r: -r["relationships"])


def distance(inst_rows):
    """Dollars, accounts and institutions by the distance of the institution's nearest branch to a client branch."""
    labels = ["0-5 mi", "5-25 mi", "25-50 mi", "50-100 mi", "no branch near"]
    acc = {k: {"institutions": 0, "relationships": 0, "dollars": 0} for k in labels}
    for r in inst_rows:
        d = r.get("nearest_mi")
        k = labels[4] if d is None else labels[0] if d <= 5 else labels[1] if d <= 25 else labels[2] if d <= 50 else labels[3]
        acc[k]["institutions"] += 1
        acc[k]["relationships"] += r["accounts"]
        acc[k]["dollars"] += r["dollars"]
    return [{"band": k, **v} for k, v in acc.items() if v["institutions"]]


def winback(matched, acct_total, sets, end, top=15):
    """Counts only (no account lists): heavy relationships still live, by institution and group."""
    p = _pairs(matched, acct_total)
    p = p[p["tier"].isin(WINBACK_TIERS)]
    p["live"] = p["last"] > end - pd.Timedelta(days=30)
    heavy = p[(p["band"] == "20%+") & p["live"]]
    if not len(heavy):
        return []
    out = heavy.groupby("inst").agg(tier=("tier", "first"), heavy_live=("acct", "nunique")).reset_index()
    out["live"] = out["inst"].map(p[p["live"]].groupby("inst")["acct"].nunique()).fillna(0).astype(int)
    out["accounts"] = out["inst"].map(p.groupby("inst")["acct"].nunique()).astype(int)
    rows = []
    for _, r in out.sort_values("heavy_live", ascending=False).head(top).iterrows():
        h = heavy[heavy["inst"] == r["inst"]]
        rows.append({"inst": r["inst"], "tier": r["tier"], "heavy_live": _i(r["heavy_live"]), "live": _i(r["live"]), "accounts": _i(r["accounts"]),
                     "by_group": {g: _i(h["acct"].isin(ids).sum()) for g, ids in sets.items()}})
    return rows


def attrition(matched, active_first_half, closed, mid, end):
    """Closure in the second half of the window by whether the account paid a competitor in the first half.
    The cohort is the accounts with card activity before `mid` that had not closed by then. An association."""
    cohort = set(active_first_half)
    closed = closed.dropna()
    cohort -= set(closed[closed < mid].index)
    shut = set(closed[(closed >= mid) & (closed <= end + pd.Timedelta(days=31))].index) & cohort
    first = matched[matched["date"] < mid]
    rows = []

    def line(label, exposed):
        exposed = exposed & cohort
        un = cohort - exposed
        ce, cu = len(shut & exposed), len(shut & un)
        re_, ru = ce / max(len(exposed), 1), cu / max(len(un), 1)
        rows.append({"exposed_to": label, "exposed": len(exposed), "closed": ce, "closure_pct": round(re_ * 100, 2),
                     "unexposed": len(un), "unexposed_closure_pct": round(ru * 100, 2),
                     "relative_risk": round(re_ / ru, 2) if ru else None})
    line("ANY depository competitor", set(first["acct"]))
    for t, g in first.groupby("tier"):
        line(t, set(g["acct"]))
    return rows


def branches(matched, active, branch, closed, end, min_accounts=50):
    """Per ODD branch with `min_accounts` or more transacting accounts: the competitor share by tier and the
    closure rate over the last 12 months."""
    b = branch.reindex(list(active)).map(branch_label)
    base = b.groupby(b).size()
    one = matched.drop_duplicates("acct")["acct"]

    def share(tiers=None):
        m = one if tiers is None else matched[matched["tier"].isin(tiers)].drop_duplicates("acct")["acct"]
        return (m.map(b).value_counts() / base * 100).round(1)
    cl = closed.dropna()
    cl = cl[(cl > end - pd.DateOffset(months=12)) & (cl <= end + pd.Timedelta(days=31))]
    shut = cl.index.to_series().map(b).value_counts()
    df = pd.DataFrame({"accounts": base, "any_pct": share(), "local_pct": share([CL.LOCAL, CL.LOCAL_MARKET]),
                       "national_pct": share([CL.NATIONAL]), "digital_pct": share([CL.DIGITAL]), "closed_12m": shut}).fillna(0)
    df = df[df["accounts"] >= min_accounts]
    df["closure_pct"] = (df["closed_12m"] / df["accounts"] * 100).round(1)
    return [{"branch": k, "accounts": _i(r["accounts"]), "any_pct": float(r["any_pct"]), "local_pct": float(r["local_pct"]),
             "national_pct": float(r["national_pct"]), "digital_pct": float(r["digital_pct"]), "closed_12m": _i(r["closed_12m"]),
             "closure_pct": float(r["closure_pct"])} for k, r in df.sort_values("any_pct", ascending=False).iterrows()]


def nearby(book, points, radius, seen_tier_by_name):
    """Competitor branches within `radius` miles of a client branch: [lat, lon, institution, tier or None]; a
    branch's tier is its institution's tier when the institution appears in the card spending (matched by name)."""
    found = {}
    for lat, lon in points:
        for b in book.index.near(lat, lon, radius):
            found[(round(b.lat, 5), round(b.lon, 5), b.inst_key)] = b
    names = {k.lower(): t for k, t in seen_tier_by_name.items()}

    def tier_of(n):
        k = str(n).lower()
        if k in names:
            return names[k]
        return next((t for nm, t in names.items() if len(nm) >= 4 and nm in k), None)
    return [[round(b.lat, 4), round(b.lon, 4), b.inst_name, tier_of(b.inst_name)] for b in found.values()]


def compute(ctx_parts, frame, lenses, anchor_ts, book, points, local_miles, inst_rows, key_prefix="cl_"):
    """The analyses for one client. `ctx_parts` is what `competition_layers.compute` left on the context:
    (sub, matched, active, sets). Returns (figures, warnings)."""
    K = key_prefix
    sub, matched, active, sets = ctx_parts
    out, warns = {}, []
    if matched is None or not len(matched):
        return out, ["competition layers: no institution matched, so the analyses are not computed"]
    end = pd.Timestamp(anchor_ts) if anchor_ts is not None else pd.Timestamp(sub["date"].max())
    mid = end - pd.DateOffset(months=6)
    total = sub.groupby("acct")["amt"].sum()
    out[K + "trend"] = trend(sub, sets)
    mv_inst, mv_tier = movement(matched, end)
    out[K + "movement"], out[K + "tier_movement"] = mv_inst, mv_tier
    d_tier, d_inst = depth(matched, total)
    out[K + "depth_tiers"], out[K + "depth_institutions"] = d_tier, d_inst
    out[K + "multi"] = multi(matched, active, sets)
    out[K + "recency"] = recency(matched, end)
    out[K + "distance"] = distance(inst_rows)
    out[K + "winback"] = winback(matched, total, sets, end)
    key = getattr(lenses, "key_column", None)
    cols = list(getattr(frame, "columns", []))
    if frame is not None and key in cols and "Date Closed" in cols:
        closed = pd.Series(pd.to_datetime(frame["Date Closed"], errors="coerce").to_numpy(), index=frame[key].astype(str).to_numpy())
        closed = closed[~closed.index.duplicated()]
        first_half = set(sub.loc[sub["date"] < mid, "acct"].unique())
        out[K + "attrition"] = attrition(matched, first_half, closed, mid, end)
        if "Branch" in cols:
            br = pd.Series(frame["Branch"].to_numpy(), index=frame[key].astype(str).to_numpy())
            br = br[~br.index.duplicated()]
            out[K + "branches"] = branches(matched, active, br, closed, end)
        else:
            warns.append("competition layers: the ODD has no Branch column; the branch table is not computed")
    else:
        warns.append("competition layers: the ODD has no Date Closed column; competition and attrition and the branch table are not computed")
    if book is not None and points:
        seen = {r["inst"]: r["tier"] for r in inst_rows}
        out[K + "map"] = {"client": [[round(a, 4), round(b, 4)] for a, b in points], "radius": local_miles,
                          "branches": nearby(book, points, local_miles, seen)}
    return out, warns
