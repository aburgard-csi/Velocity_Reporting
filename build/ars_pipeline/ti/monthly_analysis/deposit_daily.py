"""Daily deposits, and what leaves an account in the days after a deposit (R7, 2026-11-05).

James: "we should have daily [deposit] amounts (aggregate count and amount), we could tie up with
large txns around bnpl or something"; "i meant daily deposit amounts (the daily aggregate
amount)"; "r7 daily deposit amount could be overlayed with any and all spend categories".

Keys are dep_daily_* (the deposits file alone) and dep_timing_* (deposits against the transaction
file). The arithmetic is `ti/core/deposits/daily.py`; this module only decides what is stated:

  * no deposits file: nothing (the deposit chapter's slides already decline "no deposits file");
  * a deposits file and no transaction file: the daily series, and dep_timing_skipped saying why;
  * both: the series, the timing table, and a daily series per category for the overlay slides.
"""

from __future__ import annotations

from ti.core.deposits import daily as D


def compute(config: dict, warn, txn=None, card_category=None, fin_category=None) -> dict:
    raw = config.get("_deposit_raw")
    if raw is None or not len(raw):
        return {}
    out: dict = {}
    d = D.daily(raw)
    if not len(d):
        warn("deposit daily: the deposits file holds no positive amounts; no daily series")
        return out
    out["dep_daily"] = D.rows(d)
    out["dep_daily_columns"] = ["date", "deposits", "dollars", "accounts"]
    for k, v in D.summary(d).items():
        out[f"dep_daily_{k}"] = v
    pattern_cols = ["days", "avg_deposits", "avg_dollars", "pct_of_average"]
    out["dep_daily_weekday"] = D.weekday(d)
    out["dep_daily_weekday_columns"] = ["weekday"] + pattern_cols
    out["dep_daily_dom"] = D.day_of_month(d)
    out["dep_daily_dom_columns"] = ["day_of_month"] + pattern_cols
    out["dep_daily_top"] = D.top_days(d)
    out["dep_daily_top_columns"] = ["date", "weekday", "deposits", "dollars", "accounts"]
    out["dep_daily_note"] = ("every calendar day from the file's first to its last date, a day "
                             "with nothing posted counted as zero; credits only")

    if txn is None or not len(txn):
        out["dep_timing_skipped"] = "no transaction files for this period"
        return out
    f = D.flows(txn, card_category, fin_category)
    t = D.timing(raw, f)
    if not t:
        out["dep_timing_skipped"] = ("no account is in both the deposits file and the transaction "
                                     "file on the days both cover")
        warn(f"deposit timing: {out['dep_timing_skipped']}; the deposit-timing slides are not built")
        return out
    out["dep_timing"] = t["rows"]
    out["dep_timing_columns"] = ["category", "family", "accounts", "txns", "dollars",
                                 "pct_dollars_in_window", "pct_expected", "ratio", "shown"]
    out["dep_timing_accounts"] = t["accounts"]
    out["dep_timing_start"] = t["start"]
    out["dep_timing_end"] = t["end"]
    out["dep_timing_expected_pct"] = t["expected"]
    out["dep_timing_window_days"] = D.WINDOW_DAYS
    out["dep_timing_min_accounts"] = D.MIN_ACCOUNTS
    out["dep_timing_min_txns"] = D.MIN_TXNS
    out["dep_timing_large_rule"] = (f"above the account's own {int(D.LARGE_PCTL * 100)}th "
                                    f"percentile outflow, accounts with {D.LARGE_MIN_TXNS} or more "
                                    f"outflows")
    out["dep_timing_note"] = (
        f"accounts in both files, {t['start']} to {t['end']}. Share of each category's dollars spent "
        f"0-{D.WINDOW_DAYS} days after one of the account's own deposits, against the share an even "
        f"spread over the account's days would put there (weighted by the account's dollars in the "
        f"category). Ratio shown only on {D.MIN_ACCOUNTS}+ accounts and {D.MIN_TXNS}+ transactions")
    keep = D.kept_categories(t["rows"])
    by_cat = D.category_daily(f, keep, out["dep_daily_first"], out["dep_daily_last"])
    if by_cat:
        out["dep_daily_by_category"] = by_cat
        out["dep_daily_by_category_columns"] = ["date", "txns", "dollars"]
    return out
