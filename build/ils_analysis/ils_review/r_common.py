"""
Shared pieces for the charts that replace the R / Power BI / Excel pictures.

NEW in the RPE port (not in the analysis team's package). Each chart in `r_fees.py` and
`r_accounts.py` is ONE function that takes the loaded extracts, computes its own numbers from the
raw rows, draws a matplotlib figure in the RPE style and returns a `ChartResult`. The result carries
the figure's numbers, and `write_sidecar` puts them in a JSON file beside the PNG so every figure on
a slide traces back to the extract rows that made it.

Import-safe: nothing here reads a file or touches a share at import time.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import theme as T
from . import charts as C            # registers Carlito with matplotlib (rpe_env.use_font)
import periods                       # noqa: E402  (build/ is on sys.path via theme)

periods.install_month_axis_guard()
plt = C.plt

HEX = T.HEX
NAVY, ORANGE, TEAL = HEX["navy"], HEX["orange"], HEX["teal"]
TICK, GRID, MUTED = HEX["subtle"], HEX["grid"], HEX["muted"]
STEEL, STEEL_SOFT, LABEL = HEX["steel"], HEX["steel_soft"], HEX["label"]
GOLD, SLATE, ROWALT = HEX["gold"], HEX["slate"], HEX["band"]
DEFAULT_REPAYMENT_DAYS = 40         # see scoring_summary.DEFAULT_DAYS_NOTE
ACTIVE_DAYS = 240                  # see Frame.active_open


# ═══════════════════════════ the result of one chart ════════════════════════
@dataclass
class ChartResult:
    key: str                           # stable id, also the file stem
    title: str
    path: Optional[str] = None         # the PNG, or None for a table-only figure
    numbers: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)     # name -> {"headers": [...], "rows": [[...]]}
    parity: list = field(default_factory=list)     # [{"measure","ours","deck","status"}]
    notes: list = field(default_factory=list)
    skipped: str = ""                  # why there is no figure ("" = built)

    @property
    def ok(self):
        return not self.skipped


def skipped(key, title, why):
    return ChartResult(key=key, title=title, skipped=why)


def write_sidecar(res, out_dir, *, source="", client_id="", asof=None):
    """`<key>.json` beside the PNG: the figure's numbers, tables, parity checks and notes."""
    os.makedirs(out_dir, exist_ok=True)
    doc = {
        "key": res.key, "title": res.title, "png": os.path.basename(res.path) if res.path else None,
        "client_id": client_id, "data_as_of": str(asof)[:10] if asof is not None else None,
        "source": source, "numbers": _jsonable(res.numbers), "tables": _jsonable(res.tables),
        "parity_vs_hand_built_deck": _jsonable(res.parity), "notes": res.notes,
        "skipped": res.skipped or None,
    }
    p = os.path.join(out_dir, f"{res.key}.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return p


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o)[:10]
    if isinstance(o, float) and np.isnan(o):
        return None
    return o


def compare(ours, deck, *, tol=0.005, measure=""):
    """One parity entry: our figure against the figure on the hand-built slide (`deck`).

    `tol` is relative (0.5% by default). The status is words, not a boolean, so the sidecar
    reads on its own: "matched" or "off by +1.2%".
    """
    if deck is None or ours is None:
        return {"measure": measure, "ours": ours, "deck": deck, "status": "no reference figure"}
    if deck == 0:
        st = "matched" if abs(ours) < 1e-9 else f"off by {ours:+.4g}"
    else:
        rel = (ours - deck) / abs(deck)
        st = "matched" if abs(rel) <= tol else f"off by {rel * 100:+.1f}%"
    return {"measure": measure, "ours": ours, "deck": deck, "status": st}


# ═══════════════════════════ the derived frame ══════════════════════════════
class Frame:
    """The extracts with the derived columns every chart shares, built once.

    `za` accounts, `zt` ZTrend rows (one item per row, with `accttype`), `notices` ZTrend
    de-duplicated to one row per account per notice date (what the Scoring Summary counts as a
    "notice": Achieva's 216,062 distinct account-days against 317,064 item rows in the window),
    `asof` the data as-of date.
    """

    def __init__(self, loaded, *, default_days=DEFAULT_REPAYMENT_DAYS):
        self.loaded = loaded
        self.asof = pd.Timestamp(loaded.snapshot).normalize()
        self.default_days = default_days
        za = loaded.zaccounts
        self.za = za
        self.client_types = ("Personal", "Business")
        self.dd = loaded.declines
        self.rf = loaded.refunds
        self._zt = None
        self._notices = None

    # ── typed ZTrend ────────────────────────────────────────────────────
    @property
    def zt(self):
        if self._zt is None:
            zt = self.loaded.ztrend
            if zt is None:
                return None
            zt = zt.copy()
            a1 = self.za.drop_duplicates("acctid").set_index("acctid")
            zt["accttype"] = zt["acctid"].map(a1["accttype"])
            self._zt = zt
        return self._zt

    @property
    def has_trend(self):
        return self.loaded.ztrend is not None

    def zt_type(self, accttype):
        z = self.zt
        return None if z is None else z[z["accttype"] == accttype]

    # ── one row per account per notice date ─────────────────────────────
    @property
    def notices(self):
        """De-duplicated notices with the account facts the Scoring Summary bands on."""
        if self._notices is not None:
            return self._notices
        zt = self.zt
        if zt is None:
            return None
        a1 = self.za.drop_duplicates("acctid").set_index("acctid")
        keep = [c for c in ("CollectedFees", "PossibleFees", "Next_Positive_Date", "Last_Positive_Date",
                            "deptotal33", "depcount33", "limit") if c in zt.columns]
        agg = {c: ("sum" if c in ("CollectedFees", "PossibleFees") else "first") for c in keep}
        if "Next_Positive_Date" in agg:
            agg["Next_Positive_Date"] = "min"
        n = zt.groupby(["acctid", "noticedate", "accttype"], observed=True, sort=False).agg(agg).reset_index()
        opened = pd.to_datetime(n["acctid"].map(a1["opendate"]), errors="coerce")
        n["age_days"] = (n["noticedate"] - opened).dt.days
        n["days_to_positive"] = (pd.to_datetime(n.get("Next_Positive_Date"), errors="coerce")
                                 - n["noticedate"]).dt.days
        if "Last_Positive_Date" in n:
            n["days_od"] = (n["noticedate"] - pd.to_datetime(n["Last_Positive_Date"], errors="coerce")).dt.days
        co = a1["Chargeoff_Account"].astype(str).str.lower().isin(("true", "1", "t", "y", "yes"))
        n["co"] = n["acctid"].map(co).fillna(False).astype(bool)
        n["co_amt"] = pd.to_numeric(n["acctid"].map(a1["Chargeoff_Amt_365"]), errors="coerce").fillna(0.0)
        n["windfall"] = pd.to_numeric(n["acctid"].map(a1["WindfallRatio"]), errors="coerce") \
            if "WindfallRatio" in a1.columns else np.nan
        n["is_default"] = n["days_to_positive"] > self.default_days
        self._notices = n
        return n

    # ── windows ──────────────────────────────────────────────────────────
    def trailing(self, days=365, end=None):
        end = pd.Timestamp(end) if end is not None else self.asof
        return end - pd.Timedelta(days=days), end

    def scoring_window(self):
        """The Scoring Summary window: 365 days ending 60 days before the as-of date, so every notice
        has had time to be repaid or not (Achieva: 2025-07-12 to 2026-07-12 for a 2026-09-10 as-of)."""
        end = self.asof - pd.Timedelta(days=60)
        return end - pd.Timedelta(days=365), end

    # ── account subsets ──────────────────────────────────────────────────
    def open_accounts(self, accttype=None):
        z = self.za[self.za["acctstatus"].astype(str).str.upper() == "O"]
        return z if accttype is None else z[z["accttype"] == accttype]

    def active_open(self, accttype):
        """Open accounts that are 'active': a deposit in the trailing ACTIVE_DAYS days, or an NSF/OD item
        in the trailing 365.

        The hand-built deck's 'Open Active' population is defined in the analysis team's SQL, not in the
        extract. This is the closest the extract supports: with 240 days Achieva's personal population
        is 93,670 (deck 93,668) with 71,297 non-users (deck 71,295), and the business population is
        within 0.6% of the deck. The window is calibrated on that one client; the sidecars record the
        comparison and the slides say how the population is defined."""
        o = self.open_accounts(accttype)
        last = pd.to_datetime(o["lastdepdate"], errors="coerce")
        user = pd.to_numeric(o["items365"], errors="coerce").fillna(0) > 0
        return o[(last >= self.asof - pd.Timedelta(days=ACTIVE_DAYS)) | user]


# ═══════════════════════════ figure helpers ═════════════════════════════════
def new_fig(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    return fig, ax


def style_axes(ax, *, grid="y", spines=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in spines)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="both", labelsize=10, colors=TICK, length=3)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def month_ticks(ax, start, end, *, every=3, rot=45):
    """MMM'YY tick labels on a date axis, through periods.mon_yy (the house format)."""
    ticks = pd.date_range(pd.Timestamp(start).replace(day=1), end, freq=f"{every}MS")
    ax.set_xticks(ticks)
    ax.set_xticklabels([periods.mon_yy(f"{t.year}-{t.month:02d}") for t in ticks],
                       rotation=rot, ha="right", fontsize=10, color=TICK)


def money(v, d=0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"${v:,.{d}f}"


def pct(v, d=1):
    return f"{v:.{d}f}%"


def save(fig, out_dir, key):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{key}.png")
    fig.savefig(path, dpi=200, facecolor="white", bbox_inches=None)
    plt.close(fig)
    return path


def smooth(y, frac=0.25):
    """A local-linear smoother (the R `geom_smooth` default is LOESS; this is tricube-weighted local
    linear regression, in numpy, because scipy is not part of the RPE environment)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 8:
        return y
    x = np.arange(n, dtype=float)
    k = max(5, int(n * frac))
    out = np.empty(n)
    for i in range(n):
        lo = min(max(0, i - k // 2), max(0, n - k))
        idx = np.arange(lo, min(n, lo + k))
        d = np.abs(x[idx] - x[i])
        w = (1 - (d / (d.max() + 1e-9)) ** 3) ** 3
        W_ = w.sum()
        xm = (w * x[idx]).sum() / W_
        ym = (w * y[idx]).sum() / W_
        sxx = (w * (x[idx] - xm) ** 2).sum()
        b = (w * (x[idx] - xm) * (y[idx] - ym)).sum() / sxx if sxx > 0 else 0.0
        out[i] = ym + b * (x[i] - xm)
    return out
