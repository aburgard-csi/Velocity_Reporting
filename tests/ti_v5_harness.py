"""
ti_v5_harness.py — the two pieces of v5's `tests/test_month_independence.py` that v5's section tests
import, for the cut's ported tests (not itself a test module).

`CONFIG` and `make_odd` are copied verbatim from v5 at a491b5c (the synthetic raw ODD whose newest
month is any anchor). v5's file is a script that runs its whole harness on import, so it is not
ported as it stands. `compute` stands in for v5's `metrics.compute`, which the cut does not port: the
same steps (data month, account bases, sections in v5's order, then the leak post-passes), over the
v5 sections the cut has ported so far. A section not ported yet is simply absent, as it is from the
cut.
"""
import importlib
import importlib.util

import numpy as np, pandas as pd  # noqa: E401
from ti.core.periods import Month, data_month, trailing
from ti.core.subsets import build_subsets

# v5's metrics.SECTIONS order at a491b5c (lifecycle is lifecycle_report.compute there too)
_V5_ORDER = ["extract_check", "overview", "dctr", "rege", "od_limit", "migration", "mailer",
             "mailer_detail", "mailer_summary", "cohort", "profile", "attrition", "balance",
             "interchange", "retention", "stressors", "deposit_behaviour", "lifecycle_report",
             "value", "ics"]


def compute(df, config, anchor=None):
    """(metrics, warnings) over the ported sections, as v5's metrics.compute builds them."""
    warnings = []
    resolved = anchor or data_month(df.columns)
    if resolved is None:
        return {}, ["no month-tagged transaction columns; nothing computed"]
    subsets = build_subsets(df, config, resolved)
    warnings.extend(subsets.warnings)
    metrics = {"data_month": resolved.iso, "anchor_tag": resolved.tag, **subsets.sizes()}
    for name in _V5_ORDER:
        if importlib.util.find_spec(f"ti.monthly_analysis.{name}") is None:
            continue
        mod = importlib.import_module(f"ti.monthly_analysis.{name}")
        try:
            metrics.update(mod.compute(subsets, config, warnings.append))
        except Exception as exc:
            warnings.append(f"{name} failed: {type(exc).__name__}: {exc}")
    if importlib.util.find_spec("ti.monthly_analysis.leaks") is not None:
        from ti.monthly_analysis import leaks, value
        metrics.update(leaks.compute(metrics, config, warnings.append))
        metrics.update(value.apply_to_leaks(metrics))
    return metrics, warnings


CONFIG = {
    "ClientID": "1441", "ICRate": "0.0076", "NSF_OD_Fee": "33",
    "EligibleStatusCodes": ["O", "D", "I"], "IneligibleStatusCodes": ["C"],
    "EligibleProductCodes": ["301010110", "301020110"],
    "IneligibleProductCodes": ["301100110"],
    "RegEOptInCode": ["Y"],
    "EligibleMailCode": "M", "IneligibleMailCode": "X",
    "BranchMapping": {"1": "Metro", "2": "Northern Lights", "3": "Eastchester"},
}

def make_odd(anchor_tag, n=800, seed=3):
    """Synthetic raw ODD whose newest transaction month is `anchor_tag`."""
    rng = np.random.default_rng(seed)
    anchor = Month.from_tag(anchor_tag)
    anchor_end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    months = trailing(anchor, 16)
    mail_months = [m for m in trailing(anchor.shift(1), 13) if m.month % 2 == 0]

    d = {
        "Acct ID": range(n),
        "Branch": rng.choice(["1", "2", "3"], n),
        "Prod Code": rng.choice(["301010110", "301020110", "301100110"], n, p=[.5, .3, .2]),
        "Prod Desc": rng.choice(["Free Checking", "Money Market"], n, p=[.8, .2]),
        "Business?": rng.choice(["Y", "N"], n, p=[.1, .9]),
        "Stat Code": rng.choice(["O", "D", "I", "C"], n, p=[.75, .1, .05, .1]),
        "Debit?": rng.choice(["Yes", "No"], n, p=[.62, .38]),
        "DOB": pd.to_datetime(rng.integers(-25000, -7000, n), unit="D", origin=anchor_end),
        "Date Opened": pd.to_datetime(rng.integers(-8000, -20, n), unit="D", origin=anchor_end),
        "Date Closed": [pd.NaT] * n,
        "Curr Bal": rng.gamma(2, 1500, n).round(2),
        "Avg Bal": rng.gamma(2, 1500, n).round(2),
    }
    # Elig is the ARS program flag. OD Limit carries its own eligibility:
    # blank where not OD-eligible, 0 for eligible with no limit, otherwise
    # one of the tiers a client typically uses.
    d[f"{anchor.tag} Elig"] = rng.choice(["Y", "N"], n)
    od_elig = rng.random(n) < .8
    od_tier = rng.choice([0, 300, 500, 750, 1000], n, p=[.35, .2, .25, .1, .1])
    for m in months:
        t = m.tag
        d[f"{t} OD Limit"] = np.where(od_elig, od_tier, np.nan)
        d[f"{t} Reg E Code"] = rng.choice(["Y", "N", ""], n, p=[.5, .4, .1])
        d[f"{t} Sig #"] = rng.poisson(7, n)
        d[f"{t} Sig $"] = rng.gamma(2, 55, n).round(2)
        d[f"{t} PIN #"] = rng.poisson(4, n)
        d[f"{t} PIN $"] = rng.gamma(2, 28, n).round(2)
        d[f"{t} MTD"] = rng.poisson(1, n)
        d[f"{t} YTD"] = rng.poisson(12, n)
    # The ODD's own "<Mon> Segmentation": the swipe category at each mailing,
    # derived here from the three months of swipes before the mail month.
    swipe_edges = [1, 5, 10, 15, 20, 25, 40]
    swipe_labels = ["Non-user", "1-5", "6-10", "11-15", "16-20", "21-25",
                    "26-40", "41+"]
    no_card = pd.Series(d["Debit?"]) == "No"
    for m in mail_months:
        t = m.tag
        prior = [p.tag for p in trailing(m.shift(-1), 3)
                 if f"{p.tag} Sig #" in d]
        if prior:
            avg = sum(np.asarray(d[f"{p} Sig #"]) + np.asarray(d[f"{p} PIN #"])
                      for p in prior) / len(prior)
            idx = np.searchsorted(swipe_edges, avg, side="right")
            seg = np.array(swipe_labels, dtype=object)[idx]
            seg[no_card.to_numpy()] = "No card"
            d[f"{t} Segmentation"] = seg
        mailed = rng.random(n) < .6
        d[f"{t} Mail"] = pd.Series(np.where(mailed, "M", None), dtype=object)
        d[f"{t} Resp"] = pd.Series(np.where(
            mailed, rng.choice(["NU 1-4", "NU 5+", "TH-10", "TH-15"], n,
                               p=[.55, .2, .15, .1]), None), dtype=object)
    return pd.DataFrame(d)

