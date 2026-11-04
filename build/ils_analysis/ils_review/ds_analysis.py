"""
Deposit Score output analysis.

Computes the distribution of the 0–5 Deposit Score and how that output aligns
to the variables the regression matrix actually uses, plus the closure and
charge-off outcomes that validate the score is ordering risk correctly.

Carried over from the Deposit Score Validation tool, with two changes: it reads
the already-loaded frames rather than re-reading the CSVs, and it reports
`available` so the build can skip the section cleanly when the export doesn't
populate `Deposit_Score` (which is common — the column ships empty for clients
whose matrix is limit-tiered rather than score-driven).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .ils_data import num

# Deposit Score colour ramp: 1 (weakest / highest risk) -> 5 (strongest).
# Score 1 (highest risk) to 5, in brand colours: red, orange, gold, soft steel, teal; 0 = not scored.
SCORE_COLORS = {1: "#EB2A2E", 2: "#F15D22", 3: "#E7A93B", 4: "#9DB8CC",
                5: "#0D9488", 0: "#B8C0CA"}
SCORE_ORDER = [1, 2, 3, 4, 5, 0]
SCORE_LABEL = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 0: "Not scored"}

# Risk tier is derived from each score's OBSERVED charge-off rate, so the
# categorisation can never contradict the rates printed beside it.
RISK_TIER_BINS = [(1.0, "Very low risk"), (5.0, "Low risk"), (15.0, "Moderate risk"),
                  (30.0, "Elevated risk"), (float("inf"), "High risk")]
RISK_BAND = {5: "Lower risk (3–5)", 4: "Lower risk (3–5)", 3: "Lower risk (3–5)",
             2: "Higher risk (1–2)", 1: "Higher risk (1–2)", 0: "Unscored"}


def _tier_from_rate(co_rate):
    for hi, label in RISK_TIER_BINS:
        if co_rate < hi:
            return label
    return "High risk"


def _truthy(series):
    return series.astype(str).str.strip().str.lower().isin(("1", "true", "t", "y", "yes"))


# ── banding ─────────────────────────────────────────────────────────────────
def _band_age(days):
    return pd.cut(days, bins=[-1, 89, 179, 364, 729, 1824, np.inf],
                  labels=["< 90 days", "90–179 days", "180–364 days", "1–2 yrs",
                          "2–5 yrs", "5 yrs +"])


def _band_balance(bal):
    return pd.cut(bal, bins=[-np.inf, 0, 999.99, 4999.99, 8999.99, 24999.99, np.inf],
                  labels=["≤ $0", "$1–999", "$1k–5k", "$5k–9k", "$9k–25k", "$25k +"])


def _band_dep33(dep):
    return pd.cut(dep, bins=[-np.inf, 0, 425, 850, 1700, 6800, np.inf],
                  labels=["$0", "$1–425", "$426–850", "$851–1,700",
                          "$1,701–6,800", "$6,800 +"])


def _band_windfall(wf):
    return pd.cut(wf, bins=[-np.inf, 0.5, 1.0, 1.5, 2.0, np.inf],
                  labels=["< 0.5", "0.5–1.0", "1.0–1.5", "1.5–2.0", "2.0 +"])


def _band_notice(n):
    return pd.cut(n, bins=[-0.5, 0.5, 2.5, 5.5, np.inf], labels=["0", "1–2", "3–5", "6 +"])


def _band_depcount(dc):
    return pd.cut(dc, bins=[-0.5, 0.5, 2.5, 5.5, 9.5, np.inf],
                  labels=["0", "1–2", "3–5", "6–9", "10 +"])


def _band_days(d):
    return pd.cut(d, bins=[-np.inf, 7, 14, 21, 30, np.inf],
                  labels=["≤ 7", "8–14", "15–21", "22–30", "30 +"])


_VAR_ALIASES = {
    "Age of Account": ["age of account"],
    "Relationship Balance": ["relationship balance"],
    "Deposits (33 days)": ["deposits (33 days)", "deposits(33 days)",
                           "actual monthly deposits", "monthly deposits"],
    "Deposit Count (33 days)": ["deposit count", "actual monthly deposit count",
                                "number of deposits", "monthly deposit count"],
    "Auto Deposit": ["auto deposit"],
    "Windfall Ratio": ["windfall ratio", "windfall"],
    "RDI (66 days)": ["rdi (66 days)", "rdi (33 days)", "rdi"],
    "Notice Items (66 days)": ["notice items (66 days)", "notice items", "notice item"],
    "Avg Days Between Deposits": ["average days between deposits",
                                  "avg days between deposits", "days since last deposit"],
}
DEFAULT_VAR_ORDER = ["Age of Account", "Relationship Balance", "Deposits (33 days)",
                     "Auto Deposit", "Windfall Ratio", "Notice Items (66 days)"]


def _canonical_var(raw):
    n = re.sub(r"\s+", " ", str(raw).strip().lower()).strip("[]")
    for canon, aliases in _VAR_ALIASES.items():
        for a in aliases:
            if n == a or n.startswith(a) or a in n:
                return canon
    return None


# ── result containers ───────────────────────────────────────────────────────
class Banded:
    """A variable discretised into ordered bands, with per-band score mix."""

    def __init__(self, name, source_desc, band_labels, comp, mean_score, note=None):
        self.name = name
        self.source_desc = source_desc
        self.band_labels = band_labels
        self.comp = comp                 # {band: {score: count}}
        self.mean_score = mean_score      # {band: mean of 1-5 scores}
        self.note = note
        self.chart = None


@dataclass
class Analysis:
    available: bool = True
    reason: str = ""
    snapshot: Optional[object] = None
    account_type: Optional[str] = None
    n_accounts: int = 0
    n_open: int = 0
    overall_dist: dict = field(default_factory=dict)
    overall_scope_label: str = ""
    overall_n: int = 0
    by_type_dist: dict = field(default_factory=dict)
    pct_scored: float = 0.0
    mean_score: float = 0.0
    variables: list = field(default_factory=list)
    charts: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    rule_vars: list = field(default_factory=list)
    risk_rows: list = field(default_factory=list)
    risk_bands: dict = field(default_factory=dict)
    outcome_totals: dict = field(default_factory=dict)
    rdi: Optional[dict] = None
    has_rules: bool = True
    active_rules_label: str = ""


# ── availability & scoping ──────────────────────────────────────────────────
def score_series(za):
    """Deposit_Score as int 1-5, NaN -> 0 (Not scored)."""
    if "Deposit_Score" not in za.columns:
        return None
    s = num(za["Deposit_Score"])
    s = s.where(s.between(1, 5))
    return s.fillna(0).astype(int)


def is_available(za):
    """(available, reason) — whether a Deposit Score analysis can be produced."""
    if "Deposit_Score" not in za.columns:
        return False, ("The ZAccounts export has no Deposit_Score column, so the deposit "
                       "score output analysis was skipped.")
    s = num(za["Deposit_Score"])
    n = int(s.between(1, 5).sum())
    if n == 0:
        return False, ("Deposit_Score is present but empty for every account in this "
                       "export (0 of {:,} rows carry a 1–5 score), so the deposit score "
                       "output analysis was skipped. This is expected for clients whose "
                       "matrix is limit-tiered rather than score-driven."
                       .format(len(za)))
    if n < 200:
        return False, (f"Only {n:,} accounts carry a Deposit Score in this export — too "
                       f"few for a meaningful distribution, so the section was skipped.")
    return True, ""


def scored_types(za, *, min_count=200, min_share=0.02, order=("Personal", "Business")):
    """Account types carrying a material scored population."""
    s = score_series(za)
    if s is None or "accttype" not in za.columns:
        return []
    counts = za[s.between(1, 5)]["accttype"].value_counts()
    total = int(counts.sum()) or 1
    keep = [t for t, c in counts.items() if c >= min_count and c / total >= min_share]
    lead = [t for t in order if t in keep]
    return lead + [t for t in counts.index if t in keep and t not in lead]


def notice_counts_66(zt, snapshot):
    """OD/NSF notices per account in the trailing 66 days — a derived variable."""
    if zt is None or "noticedate" not in zt.columns:
        return None
    cutoff = pd.Timestamp(snapshot) - pd.Timedelta(days=66)
    recent = zt[(zt["noticedate"] > cutoff) & (zt["noticedate"] <= pd.Timestamp(snapshot))]
    if recent.empty:
        return None
    return recent.groupby("acctid").size()


# ── variable construction ───────────────────────────────────────────────────
def _composition(band, score):
    comp, mean = {}, {}
    if hasattr(band, "cat"):
        labels = list(band.cat.categories)
    else:
        labels = list(pd.unique(pd.Series(band).dropna()))
    for b in labels:
        m = pd.Series(band).reset_index(drop=True) == b
        sc = score.reset_index(drop=True)[m]
        comp[b] = {k: int((sc == k).sum()) for k in SCORE_ORDER}
        scored = sc[sc.between(1, 5)]
        mean[b] = float(scored.mean()) if len(scored) else np.nan
    return labels, comp, mean


def _banded(name, source, band_series, score_series_, note=None):
    labels, comp, mean = _composition(band_series, score_series_)
    return Banded(name, source, labels, comp, mean, note=note)


def _has_data(df, cols):
    return any(c in df.columns and num(df[c]).notna().any() for c in cols)


def _build_variable(name, scope, sscore, snap, notice66, za):
    """(Banded|None, source_label, populated, note) for a canonical driver."""
    if name == "Age of Account":
        od = scope.get("opendate")
        if od is None or pd.to_datetime(od, errors="coerce").notna().sum() == 0:
            return None, "opendate", False, "opendate not populated."
        age = (pd.Timestamp(snap) - pd.to_datetime(od, errors="coerce")).dt.days
        return (_banded(name, "opendate → days as of snapshot", _band_age(age), sscore),
                "opendate", True, "")
    if name == "Relationship Balance":
        for c in ("AvgCollectedBalance", "balance"):
            if c in scope.columns and num(scope[c]).notna().any():
                return (_banded(name, c, _band_balance(num(scope[c])), sscore), c, True, "")
        return None, "AvgCollectedBalance / balance", False, "Balance not populated."
    if name == "Deposits (33 days)":
        if "DepAmt33" in scope.columns:
            dep = num(scope["DepAmt33"]).fillna(0)
            return (_banded(name, "DepAmt33 (blank → $0)", _band_dep33(dep), sscore),
                    "DepAmt33", True, "")
        return None, "DepAmt33", False, "Column not present."
    if name == "Deposit Count (33 days)":
        if "DepCount33" in scope.columns:
            dc = num(scope["DepCount33"]).fillna(0)
            return (_banded(name, "DepCount33 (blank → 0)", _band_depcount(dc), sscore),
                    "DepCount33", True, "")
        return None, "DepCount33", False, "Column not present."
    if name == "Auto Deposit":
        if "autodeposit" in scope.columns:
            ad = np.where(_truthy(scope["autodeposit"]), "Auto deposit: Yes",
                          "Auto deposit: No")
            ad = pd.Categorical(ad, categories=["Auto deposit: No", "Auto deposit: Yes"],
                                ordered=True)
            return (_banded(name, "autodeposit", pd.Series(ad), sscore),
                    "autodeposit", True, "")
        return None, "autodeposit", False, "Column not present."
    if name == "Windfall Ratio":
        if "WindfallRatio" in scope.columns and num(scope["WindfallRatio"]).notna().any():
            return (_banded(name, "WindfallRatio", _band_windfall(num(scope["WindfallRatio"])),
                            sscore, note="Blank Windfall Ratio (no deposit history) is "
                                         "excluded from the bands."),
                    "WindfallRatio", True, "")
        return None, "WindfallRatio", False, "Not populated."
    if name == "Avg Days Between Deposits":
        c = "avgdaysbetweendeposits"
        if c in scope.columns and num(scope[c]).notna().any():
            return (_banded(name, c, _band_days(num(scope[c])), sscore), c, True, "")
        return None, c, False, "Not populated."
    if name == "RDI (66 days)":
        return (None, "RDI33 / RDIAmt33 / RDI90Days",
                _has_data(za, ["RDI33", "RDIAmt33", "RDI90Days"]),
                "Returned-deposit indicator not populated in this export — not chartable.")
    if name == "Notice Items (66 days)":
        if notice66 is not None and "acctid" in scope.columns:
            n66 = scope["acctid"].astype(str).str.strip().map(notice66).fillna(0)
            return (_banded(name, "derived: OD/NSF notices per account in ZTrend, "
                                  "trailing 66 days",
                            _band_notice(n66), sscore),
                    "derived from ZTrend", True, "Derived (no direct column).")
        return None, "derived from ZTrend", False, "ZTrend notices unavailable."
    return None, "—", False, ("Used by a rule but not mapped to a data column — "
                              "not charted.")


# ── outcomes ────────────────────────────────────────────────────────────────
def _compute_outcomes(A, scope, score):
    df = scope.copy()
    df["_score"] = score.values
    co = _truthy(df["Chargeoff_Account"]) if "Chargeoff_Account" in df \
        else pd.Series(False, index=df.index)
    closed = df["closeddate"].notna() if "closeddate" in df \
        else pd.Series(False, index=df.index)
    notopen = (df["acctstatus"].astype(str).str.upper().ne("O")
               if "acctstatus" in df else closed)
    odl = num(df["ODLimit"]) if "ODLimit" in df else pd.Series(np.nan, index=df.index)
    co_amt = num(df["Chargeoff_Amt_365"]) if "Chargeoff_Amt_365" in df \
        else pd.Series(np.nan, index=df.index)

    total = len(df) or 1
    band_acc = {}
    for k in SCORE_ORDER:
        m = df["_score"] == k
        n = int(m.sum())
        if n == 0:
            continue
        co_rate = float(co[m].mean() * 100)
        row = {"score": k, "label": SCORE_LABEL[k],
               "tier": "Unscored" if k == 0 else _tier_from_rate(co_rate),
               "n": n, "pct": n / total * 100, "co_rate": co_rate,
               "co_n": int(co[m].sum()),
               "closed_rate": float(closed[m].mean() * 100),
               "notopen_rate": float(notopen[m].mean() * 100),
               "mean_odl": float(np.nanmean(odl[m].values)) if n else float("nan"),
               "co_amt_365": float(np.nansum(co_amt[m].values))}
        A.risk_rows.append(row)
        acc = band_acc.setdefault(RISK_BAND[k], {"n": 0, "co_n": 0})
        acc["n"] += n
        acc["co_n"] += row["co_n"]
    for acc in band_acc.values():
        acc["pct"] = acc["n"] / total * 100
        acc["co_rate"] = acc["co_n"] / acc["n"] * 100 if acc["n"] else 0.0
    A.risk_bands = band_acc
    A.outcome_totals = {"n": len(df), "co_rate": float(co.mean() * 100),
                        "closed_rate": float(closed.mean() * 100),
                        "notopen_rate": float(notopen.mean() * 100),
                        "co_amt_365": float(np.nansum(co_amt.values))}
    ns = next((r for r in A.risk_rows if r["score"] == 0), None)
    if ns and ns["notopen_rate"] > 70:
        A.notes.append("Closed and charged-off accounts are generally not re-scored, so the "
                       "'Not scored' bucket is dominated by already-closed accounts. Read "
                       "the closure rate as directional and the charge-off rate as the "
                       "cleaner signal.")


def _compute_rdi(A, za):
    """RDI = returned deposit items. None when the export doesn't populate it."""
    if "RDI33" not in za.columns:
        A.rdi = None
        return
    r33 = num(za["RDI33"]).fillna(0)
    ramt = num(za["RDIAmt33"]) if "RDIAmt33" in za.columns \
        else pd.Series(np.nan, index=za.index)
    has = r33 > 0
    n = int(has.sum())
    if n == 0:
        A.rdi = None
        return
    scored = za["_score"].between(1, 5)

    def mean_score(mask):
        s = za.loc[mask & scored, "_score"]
        return float(s.mean()) if len(s) else float("nan")

    co = _truthy(za["Chargeoff_Account"]) if "Chargeoff_Account" in za.columns \
        else pd.Series(False, index=za.index)
    dist = {k: int(((za["_score"] == k) & has).sum()) for k in [1, 2, 3, 4, 5]}
    A.rdi = {"n": n, "pct": n / len(za) * 100,
             "amt_sum": float(np.nansum(ramt.values)),
             "amt_med": float(ramt[has].median()) if ramt.notna().any() else 0.0,
             "items_sum": float(r33[has].sum()),
             "mean_with": mean_score(has), "mean_without": mean_score(~has),
             "co_with": float(co[has].mean() * 100),
             "co_without": float(co[~has].mean() * 100),
             "dist": dist,
             "max_score": max([k for k in [1, 2, 3, 4, 5] if dist[k] > 0], default=0),
             "by_type": za.loc[has, "accttype"].value_counts().to_dict()
             if "accttype" in za.columns else {}}


# ── driver ──────────────────────────────────────────────────────────────────
def analyze(za, zt, snapshot, *, scope_type=None, variables=None, has_rules=True,
            notice66=None, active_rules_label=""):
    """Analyse the Deposit Score output for one account-type scope."""
    A = Analysis(has_rules=has_rules, active_rules_label=active_rules_label)
    ok, reason = is_available(za)
    if not ok:
        A.available = False
        A.reason = reason
        return A

    A.snapshot = snapshot
    za = za.assign(_score=score_series(za))
    A.n_accounts = len(za)
    if "acctstatus" in za.columns:
        A.n_open = int((za["acctstatus"].astype(str).str.upper() == "O").sum())

    by_type_scored = za[za["_score"].between(1, 5)]["accttype"].value_counts() \
        if "accttype" in za.columns else pd.Series(dtype=int)
    primary = scope_type or (by_type_scored.index[0] if len(by_type_scored) else None)
    A.account_type = primary

    scope = za[za["accttype"] == primary] if primary else za
    A.overall_scope_label = f"{primary} accounts" if primary else "All accounts"
    A.overall_dist = {k: int((scope["_score"] == k).sum()) for k in SCORE_ORDER}
    A.overall_n = len(scope)
    n_scored = sum(A.overall_dist[k] for k in [1, 2, 3, 4, 5])
    A.pct_scored = n_scored / len(scope) * 100 if len(scope) else 0.0
    sc = scope["_score"][scope["_score"].between(1, 5)]
    A.mean_score = float(sc.mean()) if len(sc) else 0.0

    if "accttype" in za.columns:
        for t in za["accttype"].dropna().unique():
            sub = za[za["accttype"] == t]
            A.by_type_dist[t] = {k: int((sub["_score"] == k).sum()) for k in SCORE_ORDER}

    if notice66 is None:
        notice66 = notice_counts_66(zt, snapshot)

    scope_reset = scope.reset_index(drop=True)
    sscore = scope_reset["_score"]

    if variables:
        order, unmapped = [], []
        for raw in variables:
            canon = _canonical_var(raw)
            if canon and canon not in order:
                order.append(canon)
            elif canon is None and str(raw).strip():
                unmapped.append(str(raw).strip())
        # Union with the standard driver set: rule text can be truncated in the
        # export, so a used driver may be missing or garbled — appending the
        # populated defaults keeps a meaningful driver from being silently lost.
        for d in DEFAULT_VAR_ORDER:
            if d not in order:
                order.append(d)
    else:
        order, unmapped = list(DEFAULT_VAR_ORDER), []

    empty_rdi = False
    for name in order:
        banded, src, populated, note = _build_variable(
            name, scope_reset, sscore, snapshot, notice66, za)
        if banded is not None:
            A.variables.append(banded)
        A.rule_vars.append((name, src, populated, note))
        if name == "RDI (66 days)" and not populated:
            empty_rdi = True
    for raw in unmapped:
        A.rule_vars.append((raw, "—", False,
                            "Used by a rule but not mapped to a data column — not charted."))

    if empty_rdi:
        A.notes.append("RDI (66 days) is referenced by the score but is not populated in "
                       "this export, so it is not represented in the alignment charts.")
    if not has_rules:
        A.notes.append("The matrix export did not include the Deposit Score Matrix rules, so "
                       "the rule-logic slides were omitted and the alignment below uses the "
                       "standard deposit-score drivers rather than variables parsed from "
                       "the rules.")

    _compute_outcomes(A, scope_reset, sscore)
    _compute_rdi(A, za.reset_index(drop=True))
    return A


def render_charts(A, img_dir):
    """Render the analysis charts to `img_dir`. Returns the charts dict."""
    from . import ds_charts
    os.makedirs(img_dir, exist_ok=True)
    return ds_charts.render_all(A, img_dir)
