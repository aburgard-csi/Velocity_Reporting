# Ported from ARS v5 02-Scripts/ars/monthly_analysis/ics.py at a491b5c (James Gilmore); logic unchanged.
"""ICS acquisition cohorts -- GATED on the ODD carrying an ICS flag.

The legacy ICS_cohort section tracked accounts acquired through ICS (new-
member checking acquisition) by open-month cohort: how fast they activate,
whether they survive, and how they compare with accounts opened outside the
program in the same months. None of that is computable until the ODD carries
the flag; the section declines with one warn until it does, and the day the
column appears every metric below lights up with no code change.

Flag columns tried in order: "ICS Account" (documented schema), "DM-REF
Source" (any non-blank value counts as ICS-sourced).
Keys: ics_* .
"""

from __future__ import annotations

import pandas as pd

from ..core.periods import Month, columns_for, trailing
from ..core.subsets import Subsets, is_business, norm

FLAG_COLUMNS = ("ICS Account", "DM-REF Source")
YES = {"Y", "YES", "1", "TRUE"}
COHORT_MONTHS = 24
GRID_OFFSETS = list(range(1, 25))          # M1..M24 since open
SURVIVAL_POINTS = [6, 12, 24]

# Every survival horizon is measured on its OWN matured base (maturity >= k),
# so the base shrinks as k grows and the deepest horizons fall to the oldest
# cohort alone. On 1776 that left month 18 resting on 17 accounts and printing
# 94.1% straight after month 16's 84.2% -- a survival curve that RISES, which
# cannot happen and reads as broken on the slide. A horizon this thin is noise,
# not a rate: below the floor the point declines rather than print a number.
SURVIVAL_MIN_BASE = 30


def _pct(n, d, digits=1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def _flag(df: pd.DataFrame) -> tuple[pd.Series | None, str | None]:
    for col in FLAG_COLUMNS:
        if col in df.columns:
            values = norm(df[col])
            if col == "ICS Account":
                return values.str.upper().isin(YES), col
            return values.notna() & (values.str.strip() != ""), col
    return None, None


def compute(subsets: Subsets, config: dict, warn) -> dict:
    df = subsets.total
    flag, source = _flag(df)
    if flag is None:
        warn("ICS cohorts: no ICS flag column in the ODD "
             f"(looked for {list(FLAG_COLUMNS)}); section gated until it exists")
        return {}
    out: dict = {"ics_flag_column": source, "ics_flagged_n": int(flag.sum())}
    if source == "DM-REF Source":
        # the source split James's workflow produces (#74): DM+REF
        # accounts count in both -- each program claims its acquisition
        vals = df[source].astype(str).str.upper()
        out["ics_source_counts"] = {
            "DM": int(vals.str.contains("DM").sum()),
            "REF": int(vals.str.contains("REF").sum()),
        }
    # Stat code against the programme (legacy ICS_cohort 20, #245): the
    # engine never read the status code for ICS before this.
    if "Stat Code" in df.columns and flag.any():
        code = df["Stat Code"].astype(str).str.strip().str.upper()
        ics_codes = code[flag].value_counts()
        non_codes = code[~flag].value_counts()
        n_ics, n_non = int(flag.sum()), int((~flag).sum())
        out["ics_cmp_stat_code"] = [
            [c, int(ics_codes.get(c, 0)), _pct(int(ics_codes.get(c, 0)), n_ics),
             int(non_codes.get(c, 0)), _pct(int(non_codes.get(c, 0)), n_non)]
            for c in sorted(set(ics_codes.index) | set(non_codes.index)) if c and c != "NAN"]
        out["ics_cmp_stat_code_columns"] = ["stat_code", "ics_n", "ics_pct",
                                            "non_ics_n", "non_ics_pct"]
    if not flag.any():
        warn(f"ICS cohorts: {source} present but no account is flagged")
        return out

    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce")
    closed = pd.to_datetime(df.get("Date Closed"), errors="coerce") \
        if "Date Closed" in df.columns else pd.Series(pd.NaT, index=df.index)
    if opened is None or opened.isna().all():
        warn("ICS cohorts: no Date Opened; section skipped")
        return out
    anchor = subsets.anchor
    anchor_end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    window = trailing(anchor, COHORT_MONTHS)
    start = pd.Timestamp(window[0].year, window[0].month, 1)
    in_window = opened.between(start, anchor_end)
    ics = flag & in_window
    ctrl = ~flag & in_window
    out["ics_cohort_window"] = [window[0].tag, anchor.tag]
    out["ics_opened_in_window"] = int(ics.sum())
    out["ics_share_of_openings_pct"] = _pct(int(ics.sum()), int(in_window.sum()))

    # ---- per open-month cohort: n, still open, activated ------------------
    swipe_cols = columns_for(df.columns, "Swipes")
    swipe_by_month = {Month.from_tag(c.split()[0]): c for c in swipe_cols}
    rows = []
    for m in window:
        m_start = pd.Timestamp(m.year, m.month, 1)
        m_end = m_start + pd.offsets.MonthEnd(0)
        cohort = ics & opened.between(m_start, m_end)
        n = int(cohort.sum())
        if not n:
            continue
        still = int((cohort & closed.isna()).sum())
        col = swipe_by_month.get(m.shift(1)) or swipe_by_month.get(m)
        activated = None
        if col:
            sw = pd.to_numeric(df.loc[cohort, col], errors="coerce").fillna(0)
            activated = _pct(int((sw >= 1).sum()), n)
        rows.append([m.tag, n, still, _pct(still, n), activated])
    out["ics_cohorts"] = rows
    out["ics_cohorts_columns"] = ["open_month", "accounts", "still_open",
                                  "still_open_pct", "activated_next_month_pct"]

    # ---- M1..M24 activity grid (any swipe at offset o after open) ---------
    grid = []
    for o in GRID_OFFSETS:
        num = den = 0
        for m in window:
            col = swipe_by_month.get(m.shift(o))
            if col is None:
                continue
            m_start = pd.Timestamp(m.year, m.month, 1)
            cohort = ics & opened.between(m_start, m_start + pd.offsets.MonthEnd(0))
            if not cohort.any():
                continue
            sw = pd.to_numeric(df.loc[cohort, col], errors="coerce").fillna(0)
            den += int(cohort.sum())
            num += int((sw >= 1).sum())
        if den:
            grid.append([o, den, _pct(num, den)])
    if grid:
        out["ics_activity_grid"] = grid
        out["ics_activity_grid_columns"] = ["months_since_open", "accounts_observed", "active_pct"]

    # ---- survival vs same-month non-ICS openings --------------------------
    surv = []
    for point in SURVIVAL_POINTS:
        row = [f"{point} mo"]
        for group in (ics, ctrl):
            mature = group & (opened <= anchor_end - pd.DateOffset(months=point))
            n = int(mature.sum())
            alive = mature & (closed.isna() | (closed > opened + pd.DateOffset(months=point)))
            row.append(_pct(int(alive.sum()), n) if n else None)
        surv.append(row)
    out["ics_survival"] = surv
    out["ics_survival_columns"] = ["horizon", "ics_pct", "non_ics_pct"]
    twelve = next((r for r in surv if r[0] == "12 mo"), None)
    if twelve and twelve[1] is not None and twelve[2] is not None:
        out["ics_survival_gap_12mo_pp"] = round(twelve[1] - twelve[2], 1)

    # the comparison block runs on the FILE'S FULL COVERAGE, not the
    # trailing-24 window -- referral programs predate it (James: 1,658
    # list accounts, comparisons silently showed fewer). The measurable
    # filter inside keeps behavior math honest per account.
    out.update(_compare_block(df, flag, ~flag, opened, closed, anchor,
                              swipe_by_month, config, warn))
    return out


def _compare_block(df, ics, ctrl, opened, closed, anchor,
                   swipe_by_month, config, warn) -> dict:
    """The seven-slide chapter's numbers (#74): ICS vs SAME-WINDOW
    non-ICS openings, maturity-honest -- an immature cell is None,
    never a projection. All keys ics_cmp_*."""
    months = sorted(swipe_by_month, key=lambda m: m.year * 12 + m.month)
    if not months:
        return {}
    spend_by_month = {Month.from_tag(c.split()[0]): c
                      for c in columns_for(df.columns, "Spend")}
    last_ord = months[-1].year * 12 + months[-1].month
    first_ord = months[0].year * 12 + months[0].month
    open_ord = opened.dt.year * 12 + opened.dt.month
    # offsets only measurable for accounts opened inside file coverage
    measurable = open_ord.between(first_ord, last_ord)
    maturity = (last_ord - open_ord).where(measurable)

    sw = df[[swipe_by_month[m] for m in months]].apply(
        pd.to_numeric, errors="coerce").fillna(0)
    sw.columns = range(len(months))
    sp = (df[[spend_by_month[m] for m in months]].apply(
        pd.to_numeric, errors="coerce").fillna(0)
        if spend_by_month else sw * 0)
    if spend_by_month:
        sp.columns = range(len(months))

    col_of = {months[i].year * 12 + months[i].month: i
              for i in range(len(months))}

    def first_offset(row_idx):
        o = open_ord.loc[row_idx]
        if pd.isna(o) or not measurable.loc[row_idx]:
            return None
        for off in range(int(last_ord - o) + 1):
            ci = col_of.get(int(o) + off)
            if ci is not None and sw.at[row_idx, ci] > 0:
                return off
        return -1                                    # matured, never swiped

    ttfs = {i: first_offset(i) for i in df.index[(ics | ctrl) & measurable]}
    ics_idx = [i for i in ttfs if ics.loc[i]]
    non_idx = [i for i in ttfs if ctrl.loc[i]]
    stamped_total = int(ics.sum())
    out: dict = {"ics_cmp_bases": {
        "ics": len(ics_idx), "non": len(non_idx),
        "stamped_total": stamped_total,
        "out_of_coverage": stamped_total - len(ics_idx)}}
    if stamped_total - len(ics_idx) > 0:
        warn(f"ICS compare: {stamped_total - len(ics_idx)} stamped accounts "
             f"opened before the file's first month -- in totals, excluded "
             f"from behavior comparisons (no observable history)")

    def median_act(idxs):
        vals = sorted(ttfs[i] for i in idxs if ttfs[i] is not None
                      and ttfs[i] >= 0)
        if not vals:
            return None
        n = len(vals)
        return (vals[n // 2] if n % 2 else
                (vals[n // 2 - 1] + vals[n // 2]) / 2)

    def bucket(off):
        if off is None:
            return None
        if off < 0:
            return "never"
        if off == 0:
            return "same month"
        if off <= 2:
            return f"{off} mo"
        if off <= 6:
            return "3-6 mo"
        return "7+ mo"

    labels = ["same month", "1 mo", "2 mo", "3-6 mo", "7+ mo", "never"]
    rows = []
    for lab in labels:
        r = [lab]
        for idxs in (ics_idx, non_idx):
            mature7 = [i for i in idxs if (maturity.loc[i] or 0) >= 7]
            n = sum(1 for i in mature7 if bucket(ttfs[i]) == lab)
            r.append(round(100 * n / len(mature7), 1) if mature7 else None)
        rows.append(r)
    out["ics_cmp_ttfs"] = {"ics_median_mo": median_act(ics_idx),
                           "non_median_mo": median_act(non_idx),
                           "buckets": rows}

    def cum_pct(idxs, k):
        base = [i for i in idxs if (maturity.loc[i] or -1) >= k]
        if not base:
            return None
        hit = sum(1 for i in base if ttfs[i] is not None
                  and 0 <= ttfs[i] <= k)
        return round(100 * hit / len(base), 1)

    out["ics_cmp_activation_cum"] = [
        [k, cum_pct(ics_idx, k), cum_pct(non_idx, k)] for k in range(1, 13)]

    # milestone grid by opening MONTH, ICS only (James: months, not
    # quarters -- the legacy grain)
    mcols = [1, 3, 6, 9, 12, 18, 24]
    grid_rows = []
    trend = []
    for o in sorted({int(open_ord.loc[i]) for i in ics_idx}):
        idxs = [i for i in ics_idx if int(open_ord.loc[i]) == o]
        label = Month((o - 1) // 12, (o - 1) % 12 + 1).tag
        grid_rows.append([label, len(idxs)]
                         + [cum_pct(idxs, k) for k in mcols])
        trend.append([label, len(idxs)])
    out["ics_cmp_milestones"] = {"cols": [f"M{k}" for k in mcols],
                                 "rows": grid_rows}
    out["ics_cmp_openings_monthly"] = trend

    # survival curve + closure durations
    closed_mo = ((closed.dt.year * 12 + closed.dt.month) - open_ord)

    def surv_pct(idxs, k):
        base = [i for i in idxs if (maturity.loc[i] or -1) >= k]
        if len(base) < SURVIVAL_MIN_BASE:
            return None
        alive = sum(1 for i in base
                    if pd.isna(closed_mo.loc[i]) or closed_mo.loc[i] > k)
        return round(100 * alive / len(base), 1)

    surv_months = sorted(set(range(0, 25, 2)) | {12})
    ics_curve = [surv_pct(ics_idx, k) for k in surv_months]
    non_curve = [surv_pct(non_idx, k) for k in surv_months]
    deepest = max((k for k, v in zip(surv_months, ics_curve) if v is not None),
                  default=None)
    if deepest is not None and deepest < max(surv_months):
        warn(f"ICS retention: curve stops at month {deepest} -- deeper "
             f"horizons have fewer than {SURVIVAL_MIN_BASE} matured ICS "
             f"accounts (the program is younger than the 24-month frame)")
    out["ics_cmp_survival_curve"] = {
        "months": surv_months,
        "ics": ics_curve,
        "non": non_curve,
        "min_base": SURVIVAL_MIN_BASE,
        "deepest_ics_month": deepest}
    cdur = {"<3 mo": 0, "3-6 mo": 0, "7-12 mo": 0, "12+ mo": 0}
    for i in ics_idx:
        d = closed_mo.loc[i]
        if pd.isna(d):
            continue
        key = ("<3 mo" if d < 3 else "3-6 mo" if d <= 6
               else "7-12 mo" if d <= 12 else "12+ mo")
        cdur[key] += 1
    out["ics_cmp_closure_duration"] = [[k, v] for k, v in cdur.items()]

    # ---- first-year closure, split by whether the card was ever used ------
    # The bridge between the activation chapter and the retention chapter:
    # portfolio-wide an account that used its card closes at 0.9% in year one
    # and one that never did at 6.5% (firstyear_close_*). ICS puts far more of
    # its accounts on the used side of that line, so this says whether the
    # activation lead converts into a retention lead. Both arms are same-window
    # openings matured to 12 months, so the exposure matches.
    def firstyear_close(idxs):
        base = [i for i in idxs if (maturity.loc[i] or -1) >= 12]
        if len(base) < SURVIVAL_MIN_BASE:
            return None
        row = {"n": len(base)}
        for label, want_used in (("used", True), ("never_used", False)):
            grp = [i for i in base
                   if (ttfs[i] is not None and ttfs[i] >= 0) is want_used]
            row[f"{label}_n"] = len(grp)
            if len(grp) < SURVIVAL_MIN_BASE:
                row[f"{label}_pct"] = None
                continue
            shut = sum(1 for i in grp if not pd.isna(closed_mo.loc[i])
                       and closed_mo.loc[i] <= 12)
            row[f"{label}_pct"] = round(100 * shut / len(grp), 1)
        return row

    fy_ics, fy_non = firstyear_close(ics_idx), firstyear_close(non_idx)
    if fy_ics or fy_non:
        out["ics_cmp_firstyear_close"] = {"ics": fy_ics, "non": fy_non}

    # ---- closure hazard by tenure bucket ---------------------------------
    # Discrete hazard, the same shape as attrition_hazard: of the accounts
    # that reached the START of a bucket AND had time to live through it,
    # what share closed inside it. Never a raw closure rate -- a younger
    # cohort would win one of those on exposure alone.
    HAZARD_BUCKETS = [("0-6 mo", 0, 6), ("6-12 mo", 6, 12), ("12-18 mo", 12, 18)]

    def hazard(idxs):
        rows = []
        for label, lo, hi in HAZARD_BUCKETS:
            base = [i for i in idxs
                    if (maturity.loc[i] or -1) >= hi
                    and (pd.isna(closed_mo.loc[i]) or closed_mo.loc[i] > lo)]
            if len(base) < SURVIVAL_MIN_BASE:
                rows.append([label, len(base), None])
                continue
            shut = sum(1 for i in base if not pd.isna(closed_mo.loc[i])
                       and lo < closed_mo.loc[i] <= hi)
            rows.append([label, len(base), round(100 * shut / len(base), 1)])
        return rows

    out["ics_cmp_hazard"] = {
        "columns": ["tenure", "reached_and_resolved", "closed_in_bucket_pct"],
        "ics": hazard(ics_idx), "non": hazard(non_idx)}

    # usage per ACTIVE account by month-since-open
    def usage_series(idxs):
        sw_sum, sp_sum, n_act = {}, {}, {}
        for i in idxs:
            o = int(open_ord.loc[i])
            for off in range(min(int(maturity.loc[i] or -1), 23) + 1):
                ci = col_of.get(o + off)
                if ci is None or sw.at[i, ci] <= 0:
                    continue
                sw_sum[off] = sw_sum.get(off, 0) + sw.at[i, ci]
                sp_sum[off] = sp_sum.get(off, 0) + sp.at[i, ci]
                n_act[off] = n_act.get(off, 0) + 1
        return sw_sum, sp_sum, n_act
    isw, isp, ina = usage_series(ics_idx)
    nsw, nsp, nna = usage_series(non_idx)
    offs = sorted(set(ina) | set(nna))
    def per(d, n, off):
        return round(d[off] / n[off], 1) if n.get(off) else None
    tot_i, tot_n = sum(ina.values()), sum(nna.values())
    out["ics_cmp_usage"] = {
        "months": offs,
        "ics_swipes": [per(isw, ina, o) for o in offs],
        "non_swipes": [per(nsw, nna, o) for o in offs],
        "ics_spend": [per(isp, ina, o) for o in offs],
        "non_spend": [per(nsp, nna, o) for o in offs],
        "ics_mean_swipes": round(sum(isw.values()) / tot_i, 1) if tot_i else None,
        "non_mean_swipes": round(sum(nsw.values()) / tot_n, 1) if tot_n else None,
        "ics_mean_spend": round(sum(isp.values()) / tot_i, 1) if tot_i else None,
        "non_mean_spend": round(sum(nsp.values()) / tot_n, 1) if tot_n else None,
    }

    # balance tiers (open accounts only)
    bal = pd.to_numeric(df.get("Curr Bal"), errors="coerce")
    tiers = [("<$500", 0, 500), ("$500-2.5K", 500, 2500),
             ("$2.5-10K", 2500, 10000), ("$10K+", 10000, float("inf"))]
    def tier_pcts(idxs):
        open_i = [i for i in idxs if pd.isna(closed.loc[i])
                  and pd.notna(bal.loc[i])]
        if not open_i:
            return {t[0]: None for t in tiers}
        return {t[0]: round(100 * sum(1 for i in open_i
                                      if t[1] <= bal.loc[i] < t[2])
                            / len(open_i), 1) for t in tiers}
    ti, tn = tier_pcts(ics_idx), tier_pcts(non_idx)
    out["ics_cmp_balance_tiers"] = [[t[0], ti[t[0]], tn[t[0]]] for t in tiers]

    # ---- composition: WHO the programme brings in -------------------------
    # The money column runs low and the balance tiers show it without
    # explaining it. These cuts are the explanation: a programme that acquires
    # younger, newer, thinner-product accounts will read exactly this way, and
    # that is a segment portrait rather than a disappointment.
    #
    # Every share is over the accounts CARRYING a value, and the base is
    # published beside it -- a cut taken over half a cohort is not a fact
    # about the cohort unless the reader can see how much of it answered.
    anchor_end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)

    def _one_series(values):
        """A duplicated column name makes df[name] a DataFrame rather than a
        Series -- an ODD that ships a column the transform also derives does
        exactly that. Take the first and carry on: losing one cut is a cost,
        losing the whole chapter to a TypeError is not."""
        if isinstance(values, pd.DataFrame):
            return values.iloc[:, 0]
        return values

    def _banded(idxs, values, bands):
        v = pd.to_numeric(_one_series(values).reindex(idxs),
                          errors="coerce").dropna()
        if not len(v):
            return None, 0
        return ([round(100 * int(((v >= lo) & (v < hi)).sum()) / len(v), 1)
                 for _lab, lo, hi in bands], len(v))

    def _band_rows(key, values, bands, label):
        ics_pct, ics_n = _banded(ics_idx, values, bands)
        non_pct, non_n = _banded(non_idx, values, bands)
        if ics_pct is None or non_pct is None:
            warn(f"ICS composition: no {label} on either cohort; cut skipped")
            return
        out[key] = [[b[0], ics_pct[j], non_pct[j]]
                    for j, b in enumerate(bands)]
        out[key + "_base"] = [ics_n, non_n]
        out[key + "_coverage_pct"] = [
            _pct(ics_n, len(ics_idx)), _pct(non_n, len(non_idx))]

    HOLDER_AGE_BANDS = [("18-29", 18, 30), ("30-44", 30, 45),
                        ("45-59", 45, 60), ("60-74", 60, 75), ("75+", 75, 121)]
    TENURE_BANDS = [("< 6 mo", 0, 0.5), ("6-12 mo", 0.5, 1),
                    ("1-2 yr", 1, 2), ("2+ yr", 2, 200)]

    if "Account Holder Age" in df.columns:
        _band_rows("ics_cmp_holder_age", df["Account Holder Age"],
                   HOLDER_AGE_BANDS, "holder age")
    tenure = (anchor_end - _one_series(opened)).dt.days / 365.2425
    _band_rows("ics_cmp_tenure", tenure, TENURE_BANDS, "tenure")

    # Product mix: the rows are the products that matter to EITHER cohort, so
    # neither side is judged on a list drawn from the other.
    prod = df.get("Prod Desc")
    if prod is None:
        prod = df.get("Prod Code")
    if prod is not None:
        pv = _one_series(prod).astype(str).str.strip()
        pv = pv.where(pv.str.lower().ne("nan") & pv.ne(""), other=None)
        ics_v, non_v = pv.reindex(ics_idx).dropna(), pv.reindex(non_idx).dropna()
        if len(ics_v) and len(non_v):
            top = list(dict.fromkeys(
                list(ics_v.value_counts().head(6).index)
                + list(non_v.value_counts().head(6).index)))[:8]
            rows = [[t, round(100 * int((ics_v == t).sum()) / len(ics_v), 1),
                     round(100 * int((non_v == t).sum()) / len(non_v), 1)]
                    for t in top]
            covered_i = sum(r[1] for r in rows)
            covered_n = sum(r[2] for r in rows)
            rows.append(["Other", round(100 - covered_i, 1),
                         round(100 - covered_n, 1)])
            out["ics_cmp_product"] = rows
            out["ics_cmp_product_base"] = [len(ics_v), len(non_v)]

    if "Business?" in df.columns:
        biz = _one_series(is_business(df))
        out["ics_cmp_business_pct"] = [
            _pct(int(biz.reindex(ics_idx, fill_value=False).sum()), len(ics_idx)),
            _pct(int(biz.reindex(non_idx, fill_value=False).sum()), len(non_idx))]

    # the value gap: interchange on the active-month spend gap
    icrate = float(config.get("ICRate") or 0)
    u = out["ics_cmp_usage"]
    open_ics_n = sum(1 for i in ics_idx if pd.isna(closed.loc[i]))
    if icrate and u["ics_mean_spend"] is not None             and u["non_mean_spend"] is not None:
        gap = round((u["ics_mean_spend"] - u["non_mean_spend"])
                    * 12 * icrate, 2)
        out["ics_cmp_value"] = {
            "ic_gap_per_acct_yr": gap,
            "open_ics_n": open_ics_n,
            "total_yr": round(gap * open_ics_n, 2),
            "basis": "interchange at config ICRate on the active-month "
                     "spend gap x 12"}
    else:
        warn("ICS compare: no ICRate in config; value gap skipped")

    # branch rows (mapped names, never raw codes; min 25 ICS accounts)
    mapping = {str(k): v for k, v in
               (config.get("BranchMapping") or {}).items()}
    br = df.get("Branch")
    if br is not None:
        names = br.astype(str).str.strip().map(lambda c: mapping.get(c, c))
        rows = []
        for name in sorted({names.loc[i] for i in ics_idx}):
            idxs = [i for i in ics_idx if names.loc[i] == name]
            if len(idxs) < 25:
                continue
            rows.append([name, len(idxs), cum_pct(idxs, 1),
                         surv_pct(idxs, 12)])
        out["ics_cmp_branch"] = rows

    # source split
    src = df.get("DM-REF Source")
    if src is not None:
        vals = src.astype(str).str.upper()
        srows = []
        for source in ("DM", "REF"):
            idxs = [i for i in ics_idx if source in vals.loc[i]]
            if idxs:
                srows.append([source, len(idxs), cum_pct(idxs, 1),
                              surv_pct(idxs, 12)])
        out["ics_cmp_source"] = srows

    # ---- activation personas ---------------------------------------------
    # Legacy cells 37/38, rebuilt. Theirs gated on membership of the rolling
    # activity window rather than on data availability, so a 69-month-old
    # account was labelled "Too New (<3 Months)" and the bucket swallowed
    # every older cohort -- the error then propagated into branch success
    # rates and the exec summary.
    #
    # The gate here is maturity: an account is classified only once its own
    # month 3 has actually happened. Everything else is a real answer.
    PERSONA_GATE = 2                  # offsets 0..2 must exist
    MIN_PERSONA_BASE = 30

    def _swipes_at(i, off):
        ci = col_of.get(int(open_ord.loc[i]) + off)
        return float(sw.at[i, ci]) if ci is not None else 0.0

    def _persona(i):
        m0, m3 = _swipes_at(i, 0), _swipes_at(i, PERSONA_GATE)
        if m0 > 0 and m3 > 0:
            return "Fast activator"
        if m0 == 0 and m3 > 0:
            return "Slow burner"
        if m0 > 0 and m3 == 0:
            return "One and done"
        return "Never activated"

    PERSONA_ORDER = ["Fast activator", "Slow burner", "One and done",
                     "Never activated"]

    def _persona_shares(idxs):
        mature = [i for i in idxs
                  if pd.notna(maturity.loc[i]) and maturity.loc[i] >= PERSONA_GATE]
        if len(mature) < MIN_PERSONA_BASE:
            return None, len(mature)
        counts = {p: 0 for p in PERSONA_ORDER}
        for i in mature:
            counts[_persona(i)] += 1
        return ({p: round(100 * counts[p] / len(mature), 1)
                 for p in PERSONA_ORDER}, len(mature))

    ics_p, ics_pn = _persona_shares(ics_idx)
    non_p, non_pn = _persona_shares(non_idx)
    if ics_p and non_p:
        out["ics_cmp_personas"] = [[p, ics_p[p], non_p[p]] for p in PERSONA_ORDER]
        out["ics_cmp_personas_base"] = [ics_pn, non_pn]
        out["ics_cmp_personas_basis"] = (
            f"share of each cohort's accounts matured to month "
            f"{PERSONA_GATE + 1}; an account too new to have reached it is "
            f"excluded rather than bucketed as never activating")
        too_new = len(ics_idx) - ics_pn
        if too_new:
            out["ics_personas_too_new"] = too_new
            warn(f"ICS personas: {too_new:,} ICS account(s) have not reached "
                 f"month {PERSONA_GATE + 1} and are in no persona row -- "
                 f"counted in the cohort, classified nowhere")

        # By channel. This is the cut worth having: DM and REF are the two
        # things the client can actually spend money on.
        src = df.get("DM-REF Source")
        if src is not None:
            vals = src.astype(str).str.upper()
            crows = []
            for channel in ("DM", "REF"):
                idxs = [i for i in ics_idx if channel in vals.loc[i]]
                shares, base = _persona_shares(idxs)
                if shares:
                    crows.append([channel, base]
                                 + [shares[p] for p in PERSONA_ORDER])
            if crows:
                out["ics_personas_by_channel"] = crows
                out["ics_personas_by_channel_columns"] = (
                    ["channel", "base"] + PERSONA_ORDER)

    # ---- quality lenses (James, 2026-08-24: "do all") -------------------
    def _q(idxs, fn, gate=lambda i: True):
        vals = [fn(i) for i in idxs if gate(i)]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    def _gated_n(idxs, gate):
        return sum(1 for i in idxs if gate(i))

    def _pctq(idxs, pred, gate=lambda i: True):
        base = [i for i in idxs if gate(i)]
        if not base:
            return None
        return round(100 * sum(1 for i in base if pred(i)) / len(base), 1)

    def consistency(i):
        mat = maturity.loc[i]
        if pd.isna(mat) or mat < 1:
            return None
        o = int(open_ord.loc[i])
        horizon = int(min(mat, 11))
        active = sum(1 for off in range(horizon + 1)
                     if (ci := col_of.get(o + off)) is not None
                     and sw.at[i, ci] > 0)
        return 100 * active / (horizon + 1)

    def max_swipes(i, lo, hi):
        o = int(open_ord.loc[i])
        vals = [sw.at[i, ci] for off in range(lo, hi + 1)
                if (ci := col_of.get(o + off)) is not None]
        return max(vals) if vals else 0

    def mean_swipes(i, lo, hi):
        o = int(open_ord.loc[i])
        vals = [sw.at[i, ci] for off in range(lo, hi + 1)
                if (ci := col_of.get(o + off)) is not None]
        return sum(vals) / len(vals) if vals else 0

    def life_value(i):
        o = int(open_ord.loc[i])
        mat = maturity.loc[i]
        if pd.isna(mat):
            return None
        total = sum(sp.at[i, ci] for off in range(int(mat) + 1)
                    if (ci := col_of.get(o + off)) is not None)
        return total * icrate_q if icrate_q else None

    icrate_q = float(config.get("ICRate") or 0)
    mat12 = lambda i: (maturity.loc[i] or -1) >= 12
    q = {
        # All five habit measures share one gate. Three of them did not, and
        # they biased in OPPOSITE directions: a short horizon scores higher
        # on consistency (fewer months available to miss) and lower on the
        # swipe tiers (less time to reach 11 or 21). One dumbbell invited a
        # reader to compare five bars that were not on the same footing.
        "ics_consistency_pct": _q(ics_idx, consistency, gate=mat12),
        "non_consistency_pct": _q(non_idx, consistency, gate=mat12),
        "ics_tier11_pct": _pctq(ics_idx, lambda i: max_swipes(i, 0, 24) >= 11,
                                gate=mat12),
        "non_tier11_pct": _pctq(non_idx, lambda i: max_swipes(i, 0, 24) >= 11,
                                gate=mat12),
        "ics_tier21_pct": _pctq(ics_idx, lambda i: max_swipes(i, 0, 24) >= 21,
                                gate=mat12),
        "non_tier21_pct": _pctq(non_idx, lambda i: max_swipes(i, 0, 24) >= 21,
                                gate=mat12),
        "ics_ramp_hold_pct": _pctq(
            ics_idx, lambda i: mean_swipes(i, 9, 12) >= mean_swipes(i, 1, 3)
            and mean_swipes(i, 1, 3) > 0, gate=mat12),
        "non_ramp_hold_pct": _pctq(
            non_idx, lambda i: mean_swipes(i, 9, 12) >= mean_swipes(i, 1, 3)
            and mean_swipes(i, 1, 3) > 0, gate=mat12),
        "ics_new_high_pct": _pctq(
            ics_idx, lambda i: max_swipes(i, 6, 12) > max_swipes(i, 0, 5),
            gate=mat12),
        "non_new_high_pct": _pctq(
            non_idx, lambda i: max_swipes(i, 6, 12) > max_swipes(i, 0, 5),
            gate=mat12),
        "habit_gate": "accounts with 12 full months of maturity",
        "habit_unit": ("share of first-year months carrying a swipe, "
                       "averaged across accounts"),
        "ics_habit_base": _gated_n(ics_idx, mat12),
        "non_habit_base": _gated_n(non_idx, mat12),
        "ics_habit_excluded": len(ics_idx) - _gated_n(ics_idx, mat12),
        "non_habit_excluded": len(non_idx) - _gated_n(non_idx, mat12),
        "value_basis": "interchange at config ICRate on each account's "
                       "own lifetime spend -- delivered to date, never "
                       "projected",
    }
    # The gate is what makes the five bars comparable, but it is also most of
    # the book: ICS openings start five months into the 24-month window and
    # then ramp, so the young accounts it drops are the majority. Say so
    # rather than letting the base quietly become a third of what it was.
    if q["ics_habit_excluded"] or q["non_habit_excluded"]:
        warn(f"ICS habit measures run on accounts with 12 full months only: "
             f"{q['ics_habit_base']:,} ICS "
             f"({q['ics_habit_excluded']:,} too new) against "
             f"{q['non_habit_base']:,} control "
             f"({q['non_habit_excluded']:,} too new). A shorter horizon "
             f"scores higher on consistency and lower on the swipe tiers, so "
             f"an ungated comparison biases in two directions at once.")
    if icrate_q:
        q["ics_value_to_date"] = _q(ics_idx, life_value)
        q["non_value_to_date"] = _q(non_idx, life_value)
    # Reg E opt-in (pattern: 'Y' or OPT IN prefix; stated basis)
    rege_col = f"{anchor.tag} Reg E Code"
    if rege_col in df.columns:
        rv = df[rege_col].astype(str).str.strip().str.upper()
        opted = rv.eq("Y") | rv.str.startswith("OPT IN")
        q["ics_rege_pct"] = _pctq(ics_idx, lambda i: bool(opted.loc[i]))
        q["non_rege_pct"] = _pctq(non_idx, lambda i: bool(opted.loc[i]))
    # balance holding: median Curr/Avg ratio
    avg = df.get("Avg Bal")
    if avg is not None:
        avg = pd.to_numeric(avg, errors="coerce")
    if avg is not None and avg.notna().any():
        ratio = (pd.to_numeric(df.get("Curr Bal"), errors="coerce")
                 / avg.where(avg > 0))
        def med(idxs):
            vals = sorted(ratio.loc[i] for i in idxs
                          if pd.notna(ratio.loc[i]))
            return round(vals[len(vals) // 2], 2) if vals else None
        q["ics_bal_ratio"] = med(ics_idx)
        q["non_bal_ratio"] = med(non_idx)
    # ARS synergy: of ever-mailed accounts, ever responded
    mail_cols = columns_for(df.columns, "Mail")
    resp_cols = columns_for(df.columns, "Resp")
    if mail_cols and resp_cols:
        mailed = df[mail_cols].notna().any(axis=1) &             df[mail_cols].astype(str).apply(
                lambda c: c.str.strip().ne("") & c.str.upper().ne("NAN")
            ).any(axis=1)
        respd = df[resp_cols].notna().any(axis=1) &             df[resp_cols].astype(str).apply(
                lambda c: c.str.strip().ne("") & c.str.upper().ne("NAN")
            ).any(axis=1)
        q["ics_ars_response_pct"] = _pctq(
            ics_idx, lambda i: bool(respd.loc[i]),
            gate=lambda i: bool(mailed.loc[i]))
        q["non_ars_response_pct"] = _pctq(
            non_idx, lambda i: bool(respd.loc[i]),
            gate=lambda i: bool(mailed.loc[i]))
    out["ics_cmp_quality"] = q

    # CAC payback -- config-gated: needs the acquisition cost per source
    src_col = df.get("DM-REF Source")
    if icrate_q and src_col is not None:
        vals_src = src_col.astype(str).str.upper()
        pb = {}
        for source, key in (("DM", "ICSDMCost"), ("REF", "ICSRefCost")):
            cost = config.get(key)
            if not cost:
                continue
            idxs = [i for i in ics_idx if source in vals_src.loc[i]]
            monthly = _q(idxs, lambda i: (life_value(i) or 0)
                         / max(float(maturity.loc[i] or 0) + 1, 1))
            if monthly:
                pb[source] = {"cost": float(cost),
                              "months": round(float(cost) / monthly, 1),
                              "monthly_ic": monthly}
        if pb:
            out["ics_cmp_payback"] = pb

    # debit take
    deb = df.get("Debit?")
    if deb is not None:
        d = deb.astype(str).str.strip().str.lower() == "yes"
        def dp(idxs):
            return round(100 * sum(1 for i in idxs if d.loc[i])
                         / len(idxs), 1) if idxs else None
        out["ics_cmp_debit"] = {"ics_pct": dp(ics_idx), "non_pct": dp(non_idx)}
    return out
