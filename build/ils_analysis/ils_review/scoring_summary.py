"""
ILS Scoring Summary — predictor validation slides.

PROVENANCE: the analysis team's `scoring_summary.py`, whose `compute_predictor` was a placeholder
("the computation is supplied separately and pasted in"). It is implemented here, from the
documented definitions where they hold and from the hand-built deck where they do not:

    WHAT EACH SLIDE SHOWS
        A band table:   band | # Notices | Collected Fees | Losses | Default Rate | Loss Rate
        A bubble chart: default rate per band, bubble area = # notices, dashed line at the
                        portfolio average.

    DEFINITIONS (what this implementation does, and where it departs from the README)
        Notice      One account on one notice date. The ZTrend extract has one row per ITEM, and
                    the deck's "# Notices" counts account-days: Achieva's window holds 317,064
                    item rows and 216,062 account-days, and the deck's bands sum to 216,034.
        Window      365 days ending 60 days before the data as-of date (Achieva: 2025-07-12 to
                    2026-07-12 for a 2026-09-10 as-of), so every notice has had time to be repaid.
        Default     A notice whose account next returned to a positive balance MORE THAN
                    `default_days` after the notice. A notice that never returned positive is
                    excluded from the count, not counted as a default.
                    README says 30 days with never-repaid counted as a default. That gives 40% in
                    Achieva's first Days On Book band; the hand-built deck prints 10.1%. A scan
                    of the threshold against the deck's tables lands on 39-40 days with
                    never-repaid excluded (every Days On Book band within 0.3 points), so 40 is
                    the default here and `default_basis="readme"` restores the README rule.
        Losses      The account's charge-off dollars (`Chargeoff_Amt_365`), counted once, in the
                    band of the account's FIRST defaulting notice in the window.
        Loss Rate   Losses / Collected Fees (as the README says; verified against the deck).
        Default     Defaulted notices / notices in the band.
          Rate

    PARITY (Achieva 1544, Days On Book, Personal): # Notices and Collected Fees match the deck
    in 11 of 13 bands to the dollar; default rates are within 0.3 points; Losses match to within
    5% in bands 3-5 and are off in the first band (the deck's loss figures come from a charge-off
    table the extract does not carry). Each figure's comparison is written to its sidecar.

The band edges and labels for the six predictors are in `PREDICTORS` exactly as transcribed by the
analysis team; `DECK_BANDS` overrides the three whose bands in the hand-built deck differ (Days OD,
Windfall Ratio, ILS Limit), and `predictors(basis)` picks the set.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import theme as T
from .ils_data import count, money, pct

DEFAULT_DAYS_NOTE = "40 days, never-repaid excluded (README: 30 days, never-repaid included)"


# ── predictor registry ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Predictor:
    key: str
    title: str                 # slide title suffix
    xlabel: str                # bubble-chart x-axis caption
    source: str                # where the value comes from
    bands: tuple               # ordered band labels
    edges: Optional[tuple] = None   # numeric upper bounds (inclusive) matching `bands`
    note: str = ""
    losses: bool = True        # the Days OD table carries no Losses / Loss Rate columns


PREDICTORS = (
    Predictor(
        "days_on_book", "Days On Book", "ILS Predictor: Days Open @ Time of OD",
        "zaccounts.opendate vs. ztrend.noticedate",
        ("1-30 Days", "31-180 Days", "181 Days - 1 Yr", "1-2 Yrs", "2-3 Yrs", "3-4 Yrs",
         "4-5 Yrs", "5-6 Yrs", "6-7 Yrs", "7-8 Yrs", "8-9 Yrs", "9-10 Yrs", "10+ Yrs"),
        (30, 180, 365, 730, 1095, 1460, 1825, 2190, 2555, 2920, 3285, 3650, np.inf),
        "Account age in days at the time of each notice.",
    ),
    Predictor(
        "dep33_amt", "33 Day Deposits", "ILS Predictor: 33 Day Deposit Total",
        "ztrend.deptotal33",
        ("<= $100", "$101-$250", "$251-$500", "$501-$750", "$751-$1000", "$1001-$1500",
         "$1501-$2000", "$2001-$3000", "$3001-$4000", "$4001-$5000", "$5001-$6000",
         "$6001-$8000", "$8001-$10000", "$10001-$12000", "$12001-$14000",
         "$14000-$15000", "$15001+"),
        (100, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000,
         10000, 12000, 14000, 15000, np.inf),
        "Rolling 33-day deposit total as of each notice.",
    ),
    Predictor(
        "dep33_count", "33 Day Deposit Count", "ILS Predictor: 33 Day Deposit Count",
        "ztrend.depcount33",
        ("0", "1", "2", "3", "4", "5", "6-7", "8-9", "10-12", "13-15", "16-20", "21+"),
        (0, 1, 2, 3, 4, 5, 7, 9, 12, 15, 20, np.inf),
        "Number of deposits in the rolling 33-day window at each notice.",
    ),
    Predictor(
        "days_od", "Days OD", "ILS Predictor: Days Overdrawn",
        "ztrend.noticedate vs. Next_Positive_Date",
        ("0", "1", "2", "3", "4-5", "6-7", "8-10", "11-15", "16-20", "21-30",
         "31-45", "46-60", "60+", "Never repaid"),
        (0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 45, 60, np.inf, None),
        "Days from the notice until the account next returned positive.",
    ),
    Predictor(
        "windfall", "Windfall Ratio", "ILS Predictor: Windfall Ratio",
        "zaccounts.WindfallRatio",
        ("No ratio", "< 0.25", "0.25-0.50", "0.50-0.75", "0.75-1.00", "1.00-1.25",
         "1.25-1.50", "1.50-2.00", "2.00-3.00", "3.00+"),
        (None, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00, np.inf),
        "Ratio of the largest deposit to typical deposit volume.",
    ),
    Predictor(
        "ils_limit", "ILS Limit", "ILS Predictor: ILS Limit @ Time of OD",
        "ztrend.limit (falls back to zaccounts.ODLimit)",
        ("NO SCORE", "1 to 50", "51-100", "101-150", "151-250", "251-350", "351-500",
         "501-750", "751-1000", "1001-1250", "1251-1500", "1500-1750", "1751-2000",
         "2000+"),
        (0, 50, 100, 150, 250, 350, 500, 750, 1000, 1250, 1500, 1750, 2000, np.inf),
        "The ILS-assigned limit in force when the notice fired.",
    ),
)

PREDICTORS_BY_KEY = {p.key: p for p in PREDICTORS}

# The three predictors whose bands on the hand-built (Achieva, Sept. 2026) slides differ from the
# registry above. Days OD there is days since the account last had a positive balance (the deck's
# counts match noticedate - Last_Positive_Date, 157,932 notices, exactly), not days to repayment.
DECK_BANDS = {
    "days_od": dict(
        bands=("<= 0", "<= 1 Day", "2-7 Days", "8-10 Days", "11-15 Days", "16-22 Days", "23-30 Days", "30+ Days"),
        edges=(0, 1, 7, 10, 15, 22, 30, np.inf), losses=False,
        source="ztrend.noticedate minus ztrend.Last_Positive_Date",
        xlabel="ILS Predictor: Days Overdrawn @ Time of OD",
        note="Days since the account last had a positive balance, at each notice."),
    "windfall": dict(
        bands=("0-0.1", "0.1-0.33", "0.33-0.66", "0.66-1.3", "1.3-2.5", "2.5-5", "5+"),
        edges=(0.1, 0.33, 0.66, 1.3, 2.5, 5, np.inf)),
    "ils_limit": dict(
        bands=("NO SCORE", "1 to 50", "51-100", "101-150", "151-250", "251-350", "351-500", "501-750", "751-1000",
               "1001-1250", "1251-1500", "1500-1750", "1751-2000", "2001-2500", "2501+"),
        edges=(0, 50, 100, 150, 250, 350, 500, 750, 1000, 1250, 1500, 1750, 2000, 2500, np.inf)),
}


def predictors(basis="deck"):
    """The six predictors with the deck's bands (basis 'deck') or the analysis team's registry ('readme')."""
    if basis != "deck":
        return PREDICTORS
    out = []
    for p in PREDICTORS:
        o = DECK_BANDS.get(p.key)
        out.append(Predictor(p.key, p.title, o.get("xlabel", p.xlabel), o.get("source", p.source),
                             tuple(o["bands"]), tuple(o["edges"]), o.get("note", p.note),
                             o.get("losses", True)) if o else p)
    return tuple(out)


# ── the result contract ─────────────────────────────────────────────────────
@dataclass
class PredictorResult:
    """What `compute_predictor` returns. All lists are parallel to `bands`; `avg_default_rate` is
    the portfolio-wide rate drawn as the dashed reference line."""
    predictor: Predictor
    bands: list
    notices: list                       # int, # of account-day notices in the band
    collected_fees: list                # float $
    losses: list                        # float $
    default_rate: list                  # float, percent (18.5 means 18.5%)
    loss_rate: list                     # float, percent
    avg_default_rate: Optional[float] = None
    window_label: str = ""
    notes: list = field(default_factory=list)

    def validate(self):
        n = len(self.bands)
        for name in ("notices", "collected_fees", "losses", "default_rate", "loss_rate"):
            if len(getattr(self, name)) != n:
                raise ValueError(
                    f"PredictorResult.{name} has {len(getattr(self, name))} values "
                    f"but there are {n} bands")
        return self


def _band_values(p, n):
    """The predictor's value per notice (a Series aligned to `n`) and a mask of notices it applies to."""
    if p.key == "days_on_book":
        v = n["age_days"]
        return v, (v >= 1)
    if p.key == "dep33_amt":
        return n["deptotal33"].fillna(0.0), pd.Series(True, index=n.index)
    if p.key == "dep33_count":
        return n["depcount33"].fillna(0.0), pd.Series(True, index=n.index)
    if p.key == "days_od":
        if "Last_Positive" in p.source:
            v = n["days_od"]
            return v, v.notna()
        v = n["days_to_positive"]
        return v, pd.Series(True, index=n.index)
    if p.key == "windfall":
        v = n["windfall"]
        return v, v.notna()
    if p.key == "ils_limit":
        v = n["limit"].fillna(0.0)
        return v, pd.Series(True, index=n.index)
    raise KeyError(p.key)


def compute_predictor(predictor, fr, cfg, accttype):
    """One predictor's banded table for one account type, or None when the extract cannot support it.
    `fr` is the shared `r_common.Frame` (the loaded extracts plus the notice-level columns)."""
    n = fr.notices
    if n is None:
        return None
    lo, hi = fr.scoring_window()
    w = n[(n["accttype"] == accttype) & (n["noticedate"] >= lo) & (n["noticedate"] <= hi)]
    if w.empty:
        return None
    val, ok = _band_values(predictor, w)
    keep = ok.to_numpy()
    w, val = w[keep], val[keep]
    if w.empty:
        return None
    edges = [e for e in predictor.edges if e is not None]
    labels = [b for b, e in zip(predictor.bands, predictor.edges) if e is not None]
    idx = np.searchsorted(np.array(edges, dtype=float), val.to_numpy(dtype=float), side="left")
    idx = np.clip(idx, 0, len(labels) - 1)
    w = w.assign(band=idx)
    basis = getattr(cfg, "default_basis", "deck")
    if basis == "readme":
        days = getattr(cfg, "default_repayment_days", 30)
        w["dflt"] = w["days_to_positive"].isna() | (w["days_to_positive"] > days)
    else:
        days = fr.default_days
        w["dflt"] = w["days_to_positive"] > days
    # losses: charge-off dollars once per account, in the band of its first defaulting notice
    first = w[w["dflt"] & w["co"]].sort_values("noticedate").drop_duplicates("acctid", keep="first")
    loss_by = first.groupby("band")["co_amt"].sum()
    g = w.groupby("band").agg(n=("acctid", "size"), fees=("CollectedFees", "sum"), d=("dflt", "sum"))
    rows = [i for i in range(len(labels)) if i in g.index]
    if not rows:
        return None
    res = PredictorResult(
        predictor=predictor, bands=[labels[i] for i in rows],
        notices=[int(g.loc[i, "n"]) for i in rows], collected_fees=[float(g.loc[i, "fees"]) for i in rows],
        losses=[float(loss_by.get(i, 0.0)) for i in rows],
        default_rate=[float(g.loc[i, "d"] / g.loc[i, "n"] * 100) for i in rows],
        loss_rate=[float(loss_by.get(i, 0.0) / g.loc[i, "fees"] * 100) if g.loc[i, "fees"] else 0.0 for i in rows],
        avg_default_rate=float(w["dflt"].mean() * 100),
        window_label=f"{str(lo)[:10]} to {str(hi)[:10]}")
    res.notes.append(f"{predictor.title} ({accttype}): window {res.window_label}; default = repayment more than "
                     f"{days} days after the notice" + ("" if basis == "readme" else ", never-repaid notices excluded") + ".")
    return res.validate()


# ── slide rendering ─────────────────────────────────────────────────────────
# Real inches (the new slides are drawn on the 13.33 x 7.5 canvas, STYLE.md section 4).
BODY_TOP, BODY_BOTTOM = 1.70, 6.72
CHART_L, CHART_W = 0.50, 6.45
TABLE_L, TABLE_W = 7.15, 5.68


def _placeholder_box(slide, x, y, w, h, caption, detail):
    """A dashed drop zone marking where a figure the extract cannot support belongs."""
    from pptx.enum.dml import MSO_LINE_DASH_STYLE
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches
    import shapes
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid()
    box.fill.fore_color.rgb = T.CARD_BG
    box.line.color.rgb = T.GRAY
    box.line.width = T.Pt(1.25)
    box.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    box.shadow.inherit = False
    shapes.textbox(slide, x + 0.2, y + h / 2 - 0.65, w - 0.4, 0.5, caption, 18, T.NAVY, True,
                   T.PP_ALIGN.CENTER, T.HEAD)
    shapes.textbox(slide, x + 0.4, y + h / 2 - 0.05, w - 0.8, 1.2, detail, 16, T.SUBTLE, False,
                   T.PP_ALIGN.CENTER, T.BODY, T.MSO_ANCHOR.TOP)
    return box


def placeholder_slide(dk, title, subtitle, caption, detail, *, section, source=None):
    """A labelled placeholder slide for a figure whose data is not in the client's extracts."""
    s = dk.content(title, subtitle, section=section, source=source)
    _placeholder_box(s, 0.5, BODY_TOP, 12.33, BODY_BOTTOM - BODY_TOP - 0.1, caption, detail)
    return s


def _render_table(dk, slide, result):
    import shapes
    p = result.predictor
    heads = [""] + ["# Notices", "Collected Fees"] + (["Losses"] if p.losses else []) + \
        ["Default Rate"] + (["Loss Rate"] if p.losses else [])
    rows = []
    for i, band in enumerate(result.bands):
        r = [band, count(result.notices[i]), money(result.collected_fees[i])]
        if p.losses:
            r.append(money(result.losses[i]))
        r.append(pct(result.default_rate[i], 2))
        if p.losses:
            r.append(pct(result.loss_rate[i], 2))
        rows.append(r)
    n_rows = len(rows) + 1
    avail = BODY_BOTTOM - BODY_TOP
    row_h = min(0.32, avail / n_rows)
    fs = 11 if row_h >= 0.27 else 10
    data = [heads] + rows
    colw = [2.0] + [1.3, 1.6] + ([1.5] if p.losses else []) + [1.3] + ([1.2] if p.losses else [])
    gf = shapes.add_table(slide, TABLE_L, BODY_TOP, TABLE_W, row_h * n_rows, data, colw, fs=fs)
    tbl = gf.table
    for i in range(1, n_rows):
        c = tbl.cell(i, 0)
        c.fill.solid()
        c.fill.fore_color.rgb = T.BAND
    return tbl


def add_scoring_section(dk, cfg, loaded, accttype, *, section, divider=False, progress=None, frame=None):
    """Scoring Summary slides for one account type. Returns notes."""
    from . import charts as C
    say = progress or (lambda m: None)
    notes = []
    rendered = 0
    fr = frame
    if fr is None or not fr.has_trend:
        return [f"ILS Scoring Summary ({accttype}) was skipped — no ZTrend file, so notices cannot be banded."]
    basis = getattr(cfg, "default_basis", "deck")
    for p in predictors(getattr(cfg, "predictor_bands", "deck")):
        result = None
        try:
            result = compute_predictor(p, fr, cfg, accttype)
        except Exception as exc:                        # one predictor failing must not kill the run
            notes.append(f"Scoring Summary '{p.title}' ({accttype}) failed to compute: {type(exc).__name__}: {exc}")
        if result is None:
            notes.append(f"Scoring Summary '{p.title}' ({accttype}) was skipped: no notices in the window carry a value for it.")
            continue
        say(f"  {accttype}: scoring summary — {p.title}…")
        subtitle = f"{accttype} accounts  ·  {p.note}"
        src = (f"{os.path.basename(str(cfg.ztrend_path))} (notices {result.window_label}) joined to "
               f"{os.path.basename(str(cfg.zaccounts_path))}; {p.source}. Default: "
               f"{DEFAULT_DAYS_NOTE if basis == 'deck' else 'README rule (30 days, never-repaid counted)'}.")
        slide = dk.content(f"Scoring Summary: {p.title}", subtitle, section=section, source=src)
        _render_table(dk, slide, result)
        png = os.path.join(dk.chart_dir, f"scoring_{p.key}_{accttype.lower()}.png")
        C.predictor_bubble(result.bands, result.default_rate, result.notices, png,
                           title=f"% Default Rate by {p.title}  ·  {result.window_label}", xlabel=p.xlabel,
                           avg_line=result.avg_default_rate, figsize=(CHART_W, BODY_BOTTOM - BODY_TOP - 0.05))
        T.image_real(slide, png, CHART_L, BODY_TOP, CHART_W, BODY_BOTTOM - BODY_TOP)
        dk.sidecars.append({"key": f"scoring_{p.key}_{accttype.lower()}",
                            "title": f"Scoring Summary: {p.title} ({accttype})", "png": os.path.basename(png),
                            "numbers": {"window": result.window_label, "bands": result.bands,
                                        "notices": result.notices, "collected_fees": result.collected_fees,
                                        "losses": result.losses, "default_rate_pct": result.default_rate,
                                        "loss_rate_pct": result.loss_rate,
                                        "avg_default_rate_pct": result.avg_default_rate},
                            "notes": result.notes})
        rendered += 1
    if rendered:
        notes.append(f"Scoring Summary ({accttype}): {rendered} predictor slides. Default means repayment more than "
                     f"{fr.default_days} days after the notice, never-repaid notices excluded"
                     if basis == "deck" else
                     f"Scoring Summary ({accttype}): {rendered} predictor slides, README default rule.")
    return notes
