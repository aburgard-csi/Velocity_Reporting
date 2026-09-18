"""Swipe-tier migration, a year apart.

Where did each cardholder sit on the swipe ladder twelve months ago, and
where are they now? Tier = trailing-3-month average swipes, binned with
TransformConfig.swipe_bins -- the same definition profile.py uses for the
current swipe-tier table, so "now" here equals that table.

Computed from the monthly Swipes columns, not from any per-wave snapshot the
extract may or may not carry (1615's does not). Six things: the two windows;
the tier mix then and now; moved up / same / down; the then-to-now matrix;
the same split by response status; and non-users then who are swiping now.

Base: eligible accounts holding a debit card now that were already open at
the end of the "then" window. No card = no ladder to climb; opened since =
would read as "entered use" by construction. Both exclusions are reported.
Response status is the transform's "Response Grouping".
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..core.odd_transform import TransformConfig
from ..core.periods import columns_for, split_tag
from ..core.subsets import Subsets, has_debit, norm

WINDOW = 3            # months averaged for a tier, as in profile.py
LOOKBACK = 12         # months between "then" and "now"
GROUPS = [("Responder", ("SO-SR", "MO-SR", "MR")),
          ("Mailed non-responder", ("Non-Responder",)),
          ("Not mailed", ("No Offer",))]
_SWIPES_SUFFIX = re.compile(r"\s*swipes?$", re.I)


def tier_order(cfg: TransformConfig | None = None) -> list[str]:
    """Bottom to top, labels without the ' Swipes' suffix."""
    cfg = cfg or TransformConfig()
    return [_SWIPES_SUFFIX.sub("", label) for _, label in cfg.swipe_bins]


def _rank_swipes(avg: pd.Series, cfg: TransformConfig) -> pd.Series:
    """Monthly-average swipes -> tier index (0 = lowest bin)."""
    edges = [-np.inf] + [b for b, _ in cfg.swipe_bins if b is not None] + [np.inf]
    return pd.Series(np.searchsorted(edges[1:-1], avg.to_numpy(), side="right"),
                     index=avg.index)


def _window_avg(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) / len(cols)


def _pct(part, whole) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _dist(ranks: pd.Series, order: list[str]) -> list[list]:
    n = len(ranks)
    counts = ranks.value_counts()
    return [[label, int(counts.get(i, 0)), _pct(int(counts.get(i, 0)), n)]
            for i, label in enumerate(order)]


def _movement(first: pd.Series, latest: pd.Series) -> dict:
    delta = latest - first
    n = len(delta)
    return {
        "n": n,
        "up_n": int((delta > 0).sum()), "up_pct": _pct(int((delta > 0).sum()), n),
        "same_n": int((delta == 0).sum()), "same_pct": _pct(int((delta == 0).sum()), n),
        "down_n": int((delta < 0).sum()), "down_pct": _pct(int((delta < 0).sum()), n),
        "net_steps": round(float(delta.mean()), 2) if n else 0.0,
    }


def compute(subsets: Subsets, config: dict, warn) -> dict:
    elig = subsets.eligible
    swipe_cols = columns_for(elig.columns, "Swipes")
    if len(swipe_cols) < WINDOW + 1:
        warn(f"only {len(swipe_cols)} monthly Swipes columns; migration needs "
             f"at least {WINDOW + 1}")
        return {}

    now_cols = swipe_cols[-WINDOW:]
    then_end = len(swipe_cols) - LOOKBACK
    if then_end < WINDOW:
        then_end = WINDOW
        warn(f"only {len(swipe_cols)} months of swipes; 'then' window is the "
             f"earliest {WINDOW} months, not {LOOKBACK} months back")
    then_cols = swipe_cols[then_end - WINDOW:then_end]
    if then_cols[-1] == now_cols[-1]:
        warn("not enough history to place 'then' before 'now'; migration skipped")
        return {}

    carded = has_debit(elig)
    # Accounts opened after the "then" window had zero swipes then because
    # they did not exist -- they would all read as "entered use". Exclude and
    # report them rather than let new-account activation pose as migration.
    then_month = split_tag(then_cols[-1])[0]
    then_end_date = pd.Timestamp(then_month.year, then_month.month, 1) + pd.offsets.MonthEnd(0)
    opened = pd.to_datetime(elig.get("Date Opened"), errors="coerce") \
        if "Date Opened" in elig.columns else None
    existed_then = opened.isna() | (opened <= then_end_date) if opened is not None \
        else pd.Series(True, index=elig.index)
    base = elig[carded & existed_then]
    n_base = len(base)
    if not n_base:
        warn("no eligible cardholders open at the 'then' window; migration skipped")
        return {}

    cfg = TransformConfig()
    order = tier_order(cfg)
    rank = {label: i for i, label in enumerate(order)}
    first_rank = _rank_swipes(_window_avg(base, then_cols), cfg)
    latest_rank = _rank_swipes(_window_avg(base, now_cols), cfg)
    move = _movement(first_rank, latest_rank)
    then_tag, now_tag = split_tag(then_cols[-1])[0].tag, split_tag(now_cols[-1])[0].tag
    out: dict = {
        "mig_then_window": [split_tag(c)[0].tag for c in then_cols],
        "mig_now_window": [split_tag(c)[0].tag for c in now_cols],
        "mig_first": then_tag,
        "mig_latest": now_tag,
        "mig_months_apart": len(swipe_cols) - then_end,
        "mig_base": n_base,
        "mig_base_label": "Eligible w/debit, tier from trailing-3 swipes",
        "mig_excluded_no_card_n": int((~carded).sum()),
        "mig_excluded_opened_since_n": int((carded & ~existed_then).sum()),
        "mig_tiers": order,
        "mig_dist_first": _dist(first_rank, order),
        "mig_dist_latest": _dist(latest_rank, order),
        "mig_up_n": move["up_n"], "mig_up_pct": move["up_pct"],
        "mig_same_n": move["same_n"], "mig_same_pct": move["same_pct"],
        "mig_down_n": move["down_n"], "mig_down_pct": move["down_pct"],
        "mig_net_steps": move["net_steps"],
    }

    # ---- matrix: rows = then tier, cols = now tier -----------------------
    k = len(order)
    matrix = np.zeros((k, k), dtype=int)
    np.add.at(matrix, (first_rank.to_numpy(), latest_rank.to_numpy()), 1)
    out["mig_matrix"] = matrix.tolist()

    # ---- entered use: non-user or no card then, swiping now ---------------
    non_user_then = first_rank == rank["Non-user"]
    swiping_now = latest_rank > rank["Non-user"]
    out["mig_nonuser_first_n"] = int(non_user_then.sum())
    out["mig_entered_use_n"] = int((non_user_then & swiping_now).sum())
    out["mig_entered_use_pct"] = _pct(out["mig_entered_use_n"],
                                      out["mig_nonuser_first_n"])

    # ---- by response status -------------------------------------------------
    grouping = base.get("Response Grouping")
    if grouping is None:
        warn("no Response Grouping column; migration by response status skipped")
        return out
    grouping = norm(grouping)
    rows, entered = [], []
    for label, codes in GROUPS:
        mask = grouping.isin(codes)
        if not mask.any():
            continue
        mv = _movement(first_rank[mask], latest_rank[mask])
        rows.append([label, mv["n"], mv["up_pct"], mv["same_pct"],
                     mv["down_pct"], mv["net_steps"]])
        nu = non_user_then & mask
        entered.append([label, int(nu.sum()), int((nu & swiping_now).sum()),
                        _pct(int((nu & swiping_now).sum()), int(nu.sum()))])
    out["mig_by_group"] = rows
    out["mig_entered_use_by_group"] = entered
    resp = next((r for r in rows if r[0] == "Responder"), None)
    ctrl = next((r for r in rows if r[0] == "Mailed non-responder"), None)
    if resp and ctrl:
        out["mig_responder_up_advantage_pp"] = round(resp[2] - ctrl[2], 1)
        out["mig_responder_net_advantage"] = round(resp[5] - ctrl[5], 2)
    return out
