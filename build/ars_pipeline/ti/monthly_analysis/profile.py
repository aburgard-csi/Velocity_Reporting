# Ported from ARS v5 02-Scripts/ars/monthly_analysis/profile.py at a491b5c (James Gilmore); logic unchanged.
"""Portfolio profile: usage tiers, NSF activity, demographics, new accounts,
activation and survival.

These calculators existed before the scope was narrowed to subsets / DCTR /
Reg E / mailer. They are restored here because the deck needs them: swipe-tier
segmentation, average ticket, NSF trend, the responder age and balance
profile, the whole new-account chapter, and account growth and survival.

Everything is derived from the ODD. Nothing here needs the Workbook.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for, trailing
from ..core.subsets import Subsets, has_debit, is_business, norm, num_col

# Monthly-average swipe tiers. Order is load-bearing for the charts.
TIER_EDGES = [(1, "Non-user"), (5, "1-5"), (10, "6-10"), (15, "11-15"),
              (20, "16-20"), (25, "21-25"), (40, "26-40"), (None, "41+")]
TIER_ORDER = ["No card"] + [label for _, label in TIER_EDGES]

AGE_BANDS = [(0, 25, "<25"), (25, 35, "25-34"), (35, 45, "35-44"),
             (45, 55, "45-54"), (55, 65, "55-64"), (65, 200, "65+")]
BAL_BANDS = [(-1e18, 0, "<= $0"), (0, 500, "$0-500"), (500, 1000, "$500-1k"),
             (1000, 2500, "$1k-2.5k"), (2500, 5000, "$2.5k-5k"),
             (5000, 10000, "$5k-10k"), (10000, 1e18, "$10k+")]
SURVIVAL_POINTS = [6, 12, 24, 36, 60]


def _pct(n, d, digits=1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def _sum(df, cols):
    if not cols:
        return pd.Series(0.0, index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)


def compute(subsets: Subsets, config: dict, warn) -> dict:
    elig = subsets.eligible
    out: dict = {}
    anchor = subsets.anchor

    spend_cols = columns_for(elig.columns, "Spend")
    swipe_cols = columns_for(elig.columns, "Swipes")
    item_cols = columns_for(elig.columns, "MTD")
    carded = has_debit(elig)

    # ---- swipe-tier segmentation ---------------------------------------
    if swipe_cols:
        window = swipe_cols[-3:]
        avg = _sum(elig, window) / len(window)
        spend3 = _sum(elig, spend_cols[-3:]) if spend_cols else pd.Series(0.0, index=elig.index)
        items3 = _sum(elig, item_cols[-3:]) if item_cols else pd.Series(0.0, index=elig.index)

        edges = [-np.inf] + [e for e, _ in TIER_EDGES if e is not None] + [np.inf]
        labels = [lbl for _, lbl in TIER_EDGES]
        tier = pd.Series("No card", index=elig.index, dtype=object)
        binned = pd.cut(avg, bins=edges, labels=labels, right=False,
                        include_lowest=True).astype(object)
        tier[carded] = binned[carded]

        rows, ticket = [], []
        for label in TIER_ORDER:
            mask = tier == label
            n = int(mask.sum())
            sw = float(avg[mask].sum())
            sp = float(spend3[mask].sum()) / 3
            it = float(items3[mask].sum()) / 3
            rows.append([label, n, round(sp), round(sw), round(it)])
            if label != "No card" and sw > 0:
                ticket.append([label, n, round(sp / sw, 2)])
        out["swipe_tier"] = rows
        out["swipe_tier_total"] = [sum(r[1] for r in rows),
                                   sum(r[2] for r in rows),
                                   sum(r[3] for r in rows),
                                   sum(r[4] for r in rows)]
        out["swipe_window"] = [m.tag for m in trailing(anchor, len(window))]

        if ticket:
            out["ticket_by_tier"] = ticket
            total_sw = sum(t[1] * 0 + 0 for t in ticket) or 0
            all_sw = float(avg[carded].sum())
            all_sp = float(spend3[carded].sum()) / 3
            out["ticket_blended"] = round(all_sp / all_sw, 2) if all_sw else 0.0
            out["ticket_highest"] = max(ticket, key=lambda t: t[2])[:1] + \
                [max(t[2] for t in ticket)]
            out["ticket_lowest"] = min(ticket, key=lambda t: t[2])[:1] + \
                [min(t[2] for t in ticket)]

    # ---- tier migration: prior 3-month window vs latest ------------------
    # The legacy engagement section's tail: who moved tiers between the two
    # most recent 3-month windows, and each tier's net gain or loss.
    if swipe_cols and len(swipe_cols) >= 6:
        prior_w, latest_w = swipe_cols[-6:-3], swipe_cols[-3:]
        avg_prior = _sum(elig, prior_w) / len(prior_w)
        avg_latest = _sum(elig, latest_w) / len(latest_w)
        edges = [-np.inf] + [e for e, _ in TIER_EDGES if e is not None] + [np.inf]
        labels = [lbl for _, lbl in TIER_EDGES]

        def tier_of(avg):
            t = pd.Series("No card", index=elig.index, dtype=object)
            binned = pd.cut(avg, bins=edges, labels=labels, right=False,
                            include_lowest=True).astype(object)
            t[carded] = binned[carded]
            return t

        t_prior, t_latest = tier_of(avg_prior), tier_of(avg_latest)
        order = {lbl: i for i, lbl in enumerate(TIER_ORDER)}
        matrix = [[int(((t_prior == a) & (t_latest == b)).sum()) for b in TIER_ORDER]
                  for a in TIER_ORDER]
        out["tier_migration_matrix"] = matrix
        out["tier_migration_tiers"] = TIER_ORDER
        out["tier_migration_windows"] = [[m.tag for m in trailing(anchor.shift(-3), 3)],
                                         [m.tag for m in trailing(anchor, 3)]]
        rank_p = t_prior.map(order)
        rank_l = t_latest.map(order)
        moved = rank_p != rank_l
        n = len(elig)
        out["tier_up_pct"] = _pct(int((rank_l > rank_p).sum()), n)
        out["tier_down_pct"] = _pct(int((rank_l < rank_p).sum()), n)
        out["tier_stay_pct"] = _pct(int((~moved).sum()), n)
        flow = []
        for lbl in TIER_ORDER:
            entered = int(((t_latest == lbl) & (t_prior != lbl)).sum())
            left = int(((t_prior == lbl) & (t_latest != lbl)).sum())
            flow.append([lbl, entered, left, entered - left])
        out["tier_net_flow"] = flow
        out["tier_net_flow_columns"] = ["tier", "entered", "left", "net"]

    # ---- overall swipes and spend over time -----------------------------
    if spend_cols and swipe_cols:
        series = []
        for col in spend_cols[-24:]:
            month = Month.from_tag(col.split()[0])
            sw_col = f"{month.tag} Swipes"
            series.append([
                month.tag,
                round(float(pd.to_numeric(elig[col], errors="coerce").fillna(0).sum())),
                round(float(pd.to_numeric(elig[sw_col], errors="coerce").fillna(0).sum()))
                if sw_col in elig.columns else 0,
            ])
        out["spend_swipe_series"] = series
        if len(series) >= 13:
            latest, prior = series[-1], series[-13]
            out["spend_yoy_pct"] = _pct(latest[1] - prior[1], prior[1], 1) \
                if prior[1] else 0.0
            out["swipes_yoy_pct"] = _pct(latest[2] - prior[2], prior[2], 1) \
                if prior[2] else 0.0

    # ---- NSF / OD activity ----------------------------------------------
    if item_cols:
        series = []
        for col in item_cols[-24:]:
            month = Month.from_tag(col.split()[0])
            values = pd.to_numeric(elig[col], errors="coerce").fillna(0)
            series.append([month.tag, round(float(values.sum())),
                           int((values > 0).sum())])
        out["nsf_series"] = series
        out["nsf_last_items"] = series[-1][1]
        out["nsf_last_accts"] = series[-1][2]
        prior_tag = anchor.shift(-12).tag
        prior = next((s for s in series if s[0] == prior_tag), None)
        if prior and prior[1]:
            out["nsf_yoy"] = round(100 * (series[-1][1] - prior[1]) / prior[1])
        else:
            out["nsf_yoy"] = 0
            warn(f"no {prior_tag} in the NSF series; year-over-year shown as 0")

    # ---- responder profile: age and balance ------------------------------
    responded = (elig["# of Responses"] > 0) if "# of Responses" in elig.columns else None
    offered = (elig["# of Offers"] > 0) if "# of Offers" in elig.columns else None

    if "Account Holder Age" in elig.columns:
        age = pd.to_numeric(elig["Account Holder Age"], errors="coerce")
        valid = age.between(18, 120)
        base = elig[valid]
        out["age_base"] = int(valid.sum())
        rows = []
        for low, high, label in AGE_BANDS:
            mask = valid & age.between(low, high - 0.001)
            n = int(mask.sum())
            r = int((mask & responded).sum()) if responded is not None else 0
            mailed = int((mask & offered).sum()) if offered is not None else 0
            rows.append([label, n, r, _pct(r, mailed)])
        out["age"] = rows
        if rows:
            out["age_u25_rate"] = rows[0][3]
            out["age_o65_rate"] = rows[-1][3]
            out["age_55plus_pct"] = _pct(
                sum(r[1] for r in rows if r[0] in ("55-64", "65+")),
                int(valid.sum()), 0)

    balance = num_col(elig, "Curr Bal")
    if balance is not None and balance.notna().any():
        rows = []
        for low, high, label in BAL_BANDS:
            mask = (balance >= low) & (balance < high)
            n = int(mask.sum())
            r = int((mask & responded).sum()) if responded is not None else 0
            mailed = int((mask & offered).sum()) if offered is not None else 0
            rows.append([label, n, r, _pct(r, mailed)])
        out["balance_profile"] = rows
        if responded is not None:
            out["bal_resp_med"] = round(float(balance[responded].median() or 0))
            out["bal_non_med"] = round(float(
                balance[offered & ~responded].median() or 0))

    # ---- new accounts ----------------------------------------------------
    df = subsets.total
    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce") \
        if "Date Opened" in df.columns else None
    if opened is None or opened.isna().all():
        warn("no Date Opened; new-account and survival sections skipped")
        return out

    start = anchor.shift(-11)
    cutoff = pd.Timestamp(start.year, start.month, 1)
    new = df[opened >= cutoff]
    book = df[opened < cutoff]
    out["new_window"] = [start.tag, anchor.tag]

    if len(new):
        closed = pd.to_datetime(df.get("Date Closed"), errors="coerce") \
            if "Date Closed" in df.columns else None
        still_open = closed.reindex(new.index).isna() if closed is not None \
            else pd.Series(True, index=new.index)
        out["new_total"] = len(new)
        out["new_stillopen_pct"] = _pct(int(still_open.sum()), len(new), 0)

        prod = norm(new.get("Prod Desc"))
        if prod is None:
            prod = norm(new.get("Prod Code"))
        if prod is not None:
            counts = prod.value_counts().head(12)
            out["new_products"] = [[str(k), int(v)] for k, v in counts.items()]
            checking = prod.str.lower().str.contains("checking", na=False)
            out["new_checking_pct"] = _pct(int(checking.sum()), len(new), 0)

            book_prod = norm(book.get("Prod Desc"))
            if book_prod is None:
                book_prod = norm(book.get("Prod Code"))
            new_chk = new[checking]
            book_chk = book[book_prod.str.lower().str.contains("checking", na=False)] \
                if book_prod is not None else book

            if len(new_chk) and len(book_chk):
                nb = pd.to_numeric(new_chk.get("Curr Bal"), errors="coerce")
                ob = pd.to_numeric(book_chk.get("Curr Bal"), errors="coerce")
                out["new_chk_avgbal"] = round(float(nb.mean() or 0))
                out["open_chk_avgbal"] = round(float(ob.mean() or 0))
                out["new_chk_funded_pct"] = _pct(int((nb > 0).sum()), len(new_chk), 0)
                out["new_chk_debit_pct"] = _pct(
                    int(has_debit(new_chk).sum()), len(new_chk))
                out["open_chk_debit_pct"] = _pct(
                    int(has_debit(book_chk).sum()), len(book_chk))
                out["debit_pen_gap"] = round(
                    out["new_chk_debit_pct"] - out["open_chk_debit_pct"], 1)

        # ---- activation: do new cardholders actually use the card? -------
        new_card = new[has_debit(new)]
        book_card = book[has_debit(book)]
        out["new_card_n"] = len(new_card)
        if len(new_card) and swipe_cols:
            latest_sw = swipe_cols[-1]
            latest_sp = spend_cols[-1] if spend_cols else None

            def active_rate(frame):
                if latest_sw not in frame.columns or not len(frame):
                    return 0.0
                values = pd.to_numeric(frame[latest_sw], errors="coerce").fillna(0)
                return _pct(int((values >= 1).sum()), len(frame))

            out["new_active_pct"] = active_rate(new_card)
            out["book_active_pct"] = active_rate(book_card)
            out["activity_month"] = anchor.tag

            if latest_sp:
                def spend_active(frame):
                    if not len(frame):
                        return 0
                    sw = pd.to_numeric(frame[latest_sw], errors="coerce").fillna(0)
                    sp = pd.to_numeric(frame[latest_sp], errors="coerce").fillna(0)
                    live = sw >= 1
                    return round(float(sp[live].mean())) if live.any() else 0
                out["new_spend_active"] = spend_active(new_card)
                out["book_spend_active"] = spend_active(book_card)

            ever = _sum(new_card, swipe_cols) > 0
            out["new_ever_swiped_pct"] = _pct(int(ever.sum()), len(new_card), 0)

            window = swipe_cols[-3:]
            avg_new = _sum(new_card, window) / len(window)
            edges = [-np.inf] + [e for e, _ in TIER_EDGES if e is not None] + [np.inf]
            labels = [lbl for _, lbl in TIER_EDGES]
            seg = pd.cut(avg_new, bins=edges, labels=labels, right=False,
                         include_lowest=True).astype(object)
            counts = seg.value_counts()
            out["new_swipe_seg"] = [
                [lbl, int(counts.get(lbl, 0)),
                 _pct(int(counts.get(lbl, 0)), len(new_card))]
                for lbl in labels]
            out["new_swipe_monthly_pct"] = _pct(
                int((avg_new >= 1).sum()), len(new_card))
            out["new_swipe_heavy_pct"] = _pct(
                int((avg_new >= 26).sum()), len(new_card))

    # ---- growth and survival ---------------------------------------------
    closed = pd.to_datetime(df.get("Date Closed"), errors="coerce") \
        if "Date Closed" in df.columns else None
    months = trailing(anchor, 24)
    openings, running = [], 0
    for m in months:
        m_start = pd.Timestamp(m.year, m.month, 1)
        m_end = m_start + pd.offsets.MonthEnd(0)
        o = int(opened.between(m_start, m_end).sum())
        c = int(closed.between(m_start, m_end).sum()) if closed is not None else 0
        running += o - c
        openings.append([m.tag, o, c, running])
    out["openings"] = openings
    out["open_24"] = sum(r[1] for r in openings)
    out["close_24"] = sum(r[2] for r in openings)
    out["net_24"] = openings[-1][3]

    if closed is not None and closed.notna().any():
        anchor_ts = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
        tenure_m = ((closed.fillna(anchor_ts) - opened).dt.days / 30.44)
        is_closed = closed.notna()
        valid = tenure_m.notna() & (tenure_m >= 0)

        survival = []
        for point in SURVIVAL_POINTS:
            at_risk = valid & (tenure_m >= 0)
            reached = valid & ((tenure_m >= point) | (~is_closed & (tenure_m >= point)))
            survived = valid & ~(is_closed & (tenure_m < point))
            n = int(at_risk.sum())
            survival.append([f"{point} mo", _pct(int(survived.sum()), n)])
        out["survival"] = survival
        out["ret_1yr"] = next((s[1] for s in survival if s[0] == "12 mo"), None)
        out["ret_3yr"] = next((s[1] for s in survival if s[0] == "36 mo"), None)

        closed_life = (tenure_m[is_closed & valid] / 12)
        if len(closed_life):
            out["median_closed_life"] = round(float(closed_life.median()), 1)

        # First-year closure, split by whether the card was used early.
        first_year = valid & is_closed & (tenure_m < 12)
        cohort = valid & (tenure_m >= 12) | first_year
        used = _sum(df, swipe_cols[:6]) > 0 if swipe_cols else None
        if used is not None:
            for label, mask in (("used", used), ("not_used", ~used)):
                group = cohort & mask
                n = int(group.sum())
                if n < 25:
                    continue
                out[f"firstyear_close_{label}_n"] = n
                out[f"firstyear_close_{label}_pct"] = _pct(
                    int((group & first_year).sum()), n)
            a = out.get("firstyear_close_not_used_pct")
            b = out.get("firstyear_close_used_pct")
            if a is not None and b is not None:
                out["firstyear_close_gap_pp"] = round(a - b, 1)
    return out
