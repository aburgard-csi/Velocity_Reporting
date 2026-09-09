#!/usr/bin/env python3
"""
before_after.py — the responder before/after measure, defined ONCE.

Two things report "responder debit spend before vs after the mailing": the
monthly deck (`metrics_gen` → the Responder Activity slides) and the Executive
Summit one-pager (`responder_activity` → `build_ars_onepager`). They must agree
— the same client, the same extract, the same measure — and they did not.
`responder_activity`'s own docstring said it "mirrors the method in metrics_gen
so the one-pager agrees with the client's deck instead of restating it", and it
differed in four ways at once (Aaron, 2026-09-08 — "the Summits and the regular
delivery decks should use the same logic"):

| | deck | one-pager |
| --- | --- | --- |
| cohort | every personal responder | only those still `Elig=Yes` at the snapshot |
| after window | 6 fixed months | every month to the end of the extract |
| winsorizing | ONE cap over before+after | a separate cap per window |
| headline | pooled over responder-observations | mean of the per-mailing means |

Each difference pushes the same direction: the one-pager's eligibility filter
drops the responders who closed or went quiet (on Austin 1075 that is 0.8% of
the newest mailing's responders and 21.9% of the oldest — it lifted the reported
gain from +53% to +62%, which is survivorship, not program lift), and a separate
cap per window lets the cap itself move the delta. A Summit attendee could have
been shown a number their own monthly deck contradicted.

Written as a plain function over rows + an `odd_rows.accessors` namespace, and
import-safe: `metrics_gen` reads `sys.argv` at module scope, so importing IT runs
it, which is why the one-pager re-implemented all of this in the first place.

Everything the two callers publish comes out of `compute()`. Nothing here reads a
file, a month constant, or `sys.argv`.
"""
import datetime
import statistics

RESP_MET = {"NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"}

# 3 months before the mailing against the 6 months after it (Aaron, 2026-09-08).
#
# The after side moved 3 -> 6 because the gain DECAYS and three months does not
# show it: measured across all nine ARS clients on the mailings every window
# supports, the pooled Threshold gain falls about 9 points between the 3-month and
# 6-month window (True Sky +97% -> +86%, Texas Bay +93% -> +83%) and keeps falling
# to the end of the extract. Six months still shows the lift holding well clear of
# baseline, which is the durable claim; three months reads closest to a spike.
#
# The windows are FIXED-LENGTH. "After" used to run to the end of the extract, so
# an old mailing compared 3 months against 32 while the newest compared 3 against
# 2 — the bars were not measuring the same thing, and a series of them slopes
# downward by arithmetic alone. A mailing without a full post window is excluded
# rather than charted on a short one.
BEFORE_MONTHS = 3
AFTER_MONTHS = 6

# Fewer than this many responders to a mailing and that mailing is not charted:
# a mean over four accounts is one account's month.
MIN_RESPONDERS = 5


def mkey(token):
    """'Jul26' -> datetime. The ODD's monthly column prefix."""
    return datetime.datetime.strptime(token, "%b%y")


def label(token):
    """'Jul26' -> 'Jul 2026'. Chart axes reformat to MMM'YY via periods.mon_yy."""
    return mkey(token).strftime("%b %Y")


def windows(smonths, mature, before=BEFORE_MONTHS, after=AFTER_MONTHS):
    """-> (before_len, after_len, mailings) — the widest window this extract supports.

    A young program may not have 6 months after any mailing (Wellworth 1549's only
    mailing is one month before the extract ends), so fall back down a ladder that
    shrinks the AFTER side first: the baseline is what the comparison is anchored
    to, so it gives ground last. Both lengths are returned and every caller states
    them, so a 3-and-1 comparison is never passed off as a 3-and-6 one.
    """
    def fits(bw, aw):
        return [m for m in mature
                if m in smonths
                and smonths.index(m) >= bw
                and smonths.index(m) + 1 + aw <= len(smonths)]

    ladder = [(before, w) for w in range(after, 0, -1)] + [(2, 1), (1, 1)]
    for bw, aw in ladder:
        got = fits(bw, aw)
        if got:
            return bw, aw, got
    return before, after, []


def wins_pair(a, b):
    """Winsorize both windows at ONE cap from their combined distribution.

    Capping each window at its own mean+3sd gave before and after different
    thresholds, so the cap itself moved the delta — which is what the one-pager
    was doing.
    """
    allv = a + b
    if not allv:
        return a, b
    cap = statistics.mean(allv) + 3 * statistics.pstdev(allv)
    return [min(v, cap) for v in a], [min(v, cap) for v in b]


def offer_group(g, row, month):
    """'nu' | 'th' | None, keyed on what was MAILED.

    Never on how they responded, which would put a responder in a group whose
    baseline does not contain them.
    """
    o = g(row, f"{month} Mail")
    if o == "NU":
        return "nu"
    if o.startswith("TH"):
        return "th"
    return None


def compute(rows, odd, smonths, mature,
            before=BEFORE_MONTHS, after=AFTER_MONTHS, on_warning=None):
    """The whole measure, for one client's ODD rows.

    `rows`   every row of the extract (personal accounts are selected here)
    `odd`    an `odd_rows.accessors(H)` namespace
    `smonths`/`mature`  the extract's month tokens and the mailings with a month
                        following them

    Cohort = ALL personal responders to the mailing (Aaron, 2026-08-27), NOT
    those still eligible at the snapshot: a present-tense filter on a historical
    cohort is a survivorship filter.

    Returns the keys both callers publish, so neither computes any of it.
    """
    g, spend, nsf, personal = odd.g, odd.spend, odd.nsf, odd.personal
    pop = [r for r in rows if personal(r)]
    bw, aw, mailings = windows(smonths, mature, before, after)
    if not mailings and on_warning:
        on_warning("before/after: no mailing has a full month on both sides — "
                   "the Responder Activity slides will report that the "
                   "comparison is not available yet")

    ba = []
    pool_sb, pool_sa, pool_nb, pool_na = [], [], [], []
    split = []
    grp_pool = {"nu": [[], []], "th": [[], []]}

    for m in mailings:
        i = smonths.index(m)
        pre = smonths[i - bw:i]
        post = smonths[i + 1:i + 1 + aw]

        def means(rs, fn, months):
            return [statistics.mean([fn(r, x) for x in months]) for r in rs]

        rs = [r for r in pop if g(r, f"{m} Resp") in RESP_MET]
        if len(rs) >= MIN_RESPONDERS:
            sb = means(rs, spend, pre); sa = means(rs, spend, post)
            nb = means(rs, nsf, pre);   na = means(rs, nsf, post)
            sbw, saw = wins_pair(sb, sa)
            pool_sb += sb; pool_sa += sa
            # NSF/OD pooled the same way but NOT winsorized — the chart's NSF panel
            # plots the raw means, and the slide's NSF clause has to agree with the
            # panel beside it.
            pool_nb += nb; pool_na += na
            od = [j for j in range(len(rs)) if nb[j] > 0 or na[j] > 0]
            ba.append({
                "m": label(m), "n": len(rs),
                "sb_mean": round(statistics.mean(sbw)),
                "sa_mean": round(statistics.mean(saw)),
                "sb_sd": round(statistics.pstdev(sbw)),
                "sa_sd": round(statistics.pstdev(saw)),
                "nb_mean": round(statistics.mean(nb), 2),
                "na_mean": round(statistics.mean(na), 2),
                "nb_sd": round(statistics.pstdev(nb), 2),
                "na_sd": round(statistics.pstdev(na), 2),
                "sb_med": round(statistics.median(sb)),
                "sa_med": round(statistics.median(sa)),
                "nb_med": round(statistics.median([nb[j] for j in od]), 2) if od else 0,
                "na_med": round(statistics.median([na[j] for j in od]), 2) if od else 0,
            })

        # ---- split by the offer that was mailed ----
        # NU asks a non-user to start using the card, TH asks an existing user to
        # reach a threshold. Pooling them hides which one moves (Aaron, 2026-08-28).
        row = {"m": label(m)}
        for key in ("nu", "th"):
            grs = [r for r in pop
                   if g(r, f"{m} Resp") in RESP_MET and offer_group(g, r, m) == key]
            if len(grs) < MIN_RESPONDERS:
                row[key] = {"n": len(grs), "before": 0, "after": 0, "gain": 0}
                continue
            gsb = means(grs, spend, pre); gsa = means(grs, spend, post)
            gsbw, gsaw = wins_pair(gsb, gsa)
            grp_pool[key][0] += gsb; grp_pool[key][1] += gsa
            b_, a_ = statistics.mean(gsbw), statistics.mean(gsaw)
            row[key] = {"n": len(grs), "before": round(b_), "after": round(a_),
                        "gain": round(100 * (a_ - b_) / b_) if b_ else 0}
        split.append(row)

    # Headlines pool every responder-observation rather than averaging the
    # per-mailing figures, which let a 2,688-responder mailing count as much as a
    # 5,065-responder one. (A responder who answered several mailings contributes
    # once per mailing — inherent to per-mailing cohorts, and the pooled figure is
    # still "per responder per mailing".)
    headline = {}
    for key in ("nu", "th"):
        pb, pa = grp_pool[key]
        if pb:
            b_, a_ = wins_pair(pb, pa)
            mb, ma = statistics.mean(b_), statistics.mean(a_)
            headline[key] = {"n": len(pb), "before": round(mb), "after": round(ma),
                             "gain": round(100 * (ma - mb) / mb) if mb else 0}
        else:
            headline[key] = {"n": 0, "before": 0, "after": 0, "gain": 0}

    hb, ha = wins_pair(pool_sb, pool_sa)
    return {
        "before_after": ba,
        "before_after_split": split,
        "ba_split_headline": headline,
        "ba_before_months": bw,
        "ba_after_months": aw,
        "ba_n_mailings": len(ba),
        "ba_spend_before": round(statistics.mean(hb)) if hb else 0,
        "ba_spend_after": round(statistics.mean(ha)) if ha else 0,
        # A TRUE median across responders. This was the mean of the per-mailing
        # medians, which is not the median of anything.
        "ba_spend_med_before": round(statistics.median(pool_sb)) if pool_sb else 0,
        "ba_spend_med_after": round(statistics.median(pool_sa)) if pool_sa else 0,
        # NSF/OD items per responder per month. The slide said "NSF/OD activity
        # stayed roughly flat" as CANNED text next to this very chart — the
        # sentence behind Aaron's +/-2% rule (2026-08-31) and the Marine FCU
        # correction. A claim needs a figure, so here is the figure.
        "ba_nsf_before": round(statistics.mean(pool_nb), 2) if pool_nb else 0,
        "ba_nsf_after": round(statistics.mean(pool_na), 2) if pool_na else 0,
    }


def pct_change(before, after):
    """Signed % change, or 0 when there is no baseline to change from."""
    return round(100 * (after - before) / before, 1) if before else 0
