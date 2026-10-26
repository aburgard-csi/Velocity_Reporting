# Ported from ARS v5 02-Scripts/core/deposits/streams.py at a491b5c (James Gilmore); logic unchanged.
"""Separating an account's deposit STREAMS before measuring any of them.

The problem this exists to solve, measured on RALLY's real book:

    8,031,130 rows / 156,725 accounts = 51 credits per account per year

That is roughly one a week, which no payroll runs at. Those are mixed credit
types in one undifferentiated stream -- pay, transfers, cash, Zelle, refunds.
`cadence()` computes ONE coefficient of variation across all of them, so a
perfectly steady $800 payroll sitting beside a $20 transfer and a $2,000
windfall produces a CV far above the 0.25 threshold.

The result was a book where 48.9% of accounts are on a visible rhythm and only
4.6% pass the amount test. The payroll is there; the measurement could not see
it through the mixture. The same pollution inflates `windfalls()`, whose median
is dragged down by the small credits until ordinary pay looks like a 5x event.

So: find the account's dominant stream first, then ask the rhythm and
consistency questions of that stream alone.

Method, and its limits. Deposits are binned geometrically, so a bin holds
amounts within `tolerance` of each other at any scale -- a $400 payroll and a
$9,000 one are judged the same way, as elsewhere in this package. The largest
bin is taken, re-centred on its own median, and widened to the tolerance
around that centre; the re-centring matters because a fixed bin edge can split
one payroll across two bins.

This finds ONE stream, the dominant one. An account with two jobs has a second
stream this does not describe -- `stream_share` says how much of the account it
covers, so a low share is visible rather than silent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .behaviour import CADENCE_TARGETS, MIN_DEPOSITS_FOR_CADENCE, RECURRING_CV

# Amounts within 15% of each other are the same stream. Real pay moves with
# overtime and hours -- the same reasoning that put RECURRING_CV at 0.25 rather
# than 0.15 -- but a stream tolerance as wide as the consistency threshold
# would make the consistency test tautological: everything inside the band
# would pass by construction.
STREAM_TOLERANCE = 0.15


# How far the gaps between credits may wander, as a share of the typical gap,
# and still be a rhythm. Twenty-six credits scattered over a year have a
# MEDIAN gap of fourteen days -- fortnightly by the median alone -- which is
# how RALLY's mixed transfers read as payroll. A payroll's gaps barely move:
# fortnightly is 14, 14, 14 with the odd holiday shift (spread near 0.05);
# month-end pay lands on the 28th to the 33rd day (0.03). Thirty transfers
# on no rhythm sit near 0.35 and true scatter above 0.6.
GAP_SPREAD_MAX = 0.25


def rhythmic(median_gap: pd.Series, gap_spread: pd.Series) -> pd.Series:
    """A payroll-shaped rhythm: the typical gap sits on a cadence AND the
    gaps hold it. `gap_spread` is the median absolute deviation of the gaps
    over the median gap."""
    on_cadence = pd.Series(False, index=median_gap.index)
    for target, band in CADENCE_TARGETS:
        on_cadence |= (median_gap - target).abs() <= band
    return on_cadence & (gap_spread.fillna(np.inf) <= GAP_SPREAD_MAX)


def _gap_stats(ordered: pd.DataFrame, keys: list) -> pd.DataFrame:
    """Median gap and its spread per group of an already date-sorted frame."""
    gaps = ordered.groupby(keys)["date"].diff().dt.days
    with_gap = ordered.assign(_gap=gaps)
    median_gap = with_gap.groupby(keys)["_gap"].median().rename("median_gap")
    dev = (with_gap["_gap"] - with_gap.groupby(keys)["_gap"].transform("median")).abs()
    mad = with_gap.assign(_dev=dev).groupby(keys)["_dev"].median()
    spread = (mad / median_gap.replace(0, np.nan)).rename("gap_spread")
    return pd.concat([median_gap, spread], axis=1)


def _rhythmic_bins(binned: pd.DataFrame, sizes: pd.DataFrame) -> pd.Series:
    """Per account: how many amount bins hold at least MIN_DEPOSITS_FOR_CADENCE
    credits arriving on a payroll-shaped rhythm."""
    big = sizes[sizes["n"] >= MIN_DEPOSITS_FOR_CADENCE][["acct", "_bin"]]
    if not len(big):
        return pd.Series(dtype=int)
    members = binned.merge(big, on=["acct", "_bin"], how="inner")
    stats = _gap_stats(members.sort_values(["acct", "_bin", "date"]),
                       ["acct", "_bin"])
    keep = rhythmic(stats["median_gap"], stats["gap_spread"])
    return keep[keep].groupby(level="acct").size()


def dominant_stream(frame: pd.DataFrame, tolerance: float = STREAM_TOLERANCE
                    ) -> pd.DataFrame:
    """Per account: the largest cluster of similar-sized deposits.

    Returns acct, stream_n, stream_median, stream_gap_days, stream_cv,
    stream_share, n_streams.

    `stream_share` is the fraction of the account's deposits the stream covers.
    It is the honesty column: a dominant stream covering 20% of an account's
    credits is a weak claim about that account, and the caller can see it.
    """
    cols = ["acct", "stream_n", "stream_median", "stream_gap_days",
            "stream_gap_spread", "stream_cv", "stream_share", "n_streams"]
    live = frame[frame["dep_amount"] > 0]
    if not len(live):
        return pd.DataFrame(columns=cols)

    binned = live.assign(
        _bin=np.floor(np.log(live["dep_amount"]) / np.log1p(tolerance)))

    # How many deposits sit in each amount bin, per account.
    sizes = binned.groupby(["acct", "_bin"], sort=False).size().rename("n")
    sizes = sizes.reset_index()

    # B5: a distinct recurring stream is a bin with enough deposits to have a
    # rhythm -- AND a payroll-shaped rhythm once its dates are laid out. Size
    # alone counted six $300 credits on random days as a stream, and RALLY
    # read 4+ recurring streams in 41.5% of accounts. Counted before the
    # dominant one is picked.
    n_streams = _rhythmic_bins(binned, sizes).rename("n_streams")

    # The dominant bin is the one that carries the most MONEY, not the most
    # rows. By count, an account with thirty $20 transfers and twenty-six
    # paycheques has a dominant stream of $20 -- and every paycheque then
    # reads as a 40x windfall. Pay is the stream the money comes from; a
    # count tie still breaks toward the larger amount.
    # A single credit is not a stream, however large: one $50,000 deposit
    # must not become the 'usual' credit that hides every windfall. Bins
    # with at least two members are the candidates; a lone credit wins only
    # when nothing repeats at all.
    dollars = (binned.groupby(["acct", "_bin"], sort=False)["dep_amount"]
               .sum().rename("_dollars").reset_index())
    sizes = sizes.merge(dollars, on=["acct", "_bin"], how="left")
    repeats = sizes["acct"].isin(sizes.loc[sizes["n"] >= 2, "acct"])
    candidates = sizes[(sizes["n"] >= 2) | ~repeats]
    best = (candidates.sort_values(["acct", "_dollars", "n", "_bin"])
            .groupby("acct", sort=False).tail(1)[["acct", "_bin"]])

    # Re-centre. A fixed bin edge can split one payroll across two bins, so the
    # band is rebuilt around the dominant bin's own median.
    core = binned.merge(best, on=["acct", "_bin"], how="inner")
    centre = core.groupby("acct")["dep_amount"].median().rename("_centre")

    wide = live.merge(centre, on="acct", how="inner")
    stream = wide[(wide["dep_amount"] >= wide["_centre"] * (1 - tolerance)) &
                  (wide["dep_amount"] <= wide["_centre"] * (1 + tolerance))]
    if not len(stream):
        return pd.DataFrame(columns=cols)

    ordered = stream.sort_values(["acct", "date"])
    gap_stats = _gap_stats(ordered, ["acct"])
    stats = ordered.groupby("acct").agg(
        stream_n=("dep_amount", "size"),
        stream_median=("dep_amount", "median"),
        _mean=("dep_amount", "mean"),
        _sd=("dep_amount", "std"),
    ).reset_index()
    stats["stream_gap_days"] = stats["acct"].map(gap_stats["median_gap"])
    stats["stream_gap_spread"] = stats["acct"].map(gap_stats["gap_spread"])

    stats["stream_cv"] = np.where(
        stats["_mean"] > 0, stats["_sd"] / stats["_mean"].replace(0, np.nan),
        np.nan)

    total = live.groupby("acct").size().rename("_total")
    stats = stats.merge(total, on="acct", how="left")
    stats["stream_share"] = (stats["stream_n"] / stats["_total"]).round(3)
    stats = stats.merge(n_streams, on="acct", how="left")
    stats["n_streams"] = stats["n_streams"].fillna(0).astype(int)
    return stats[cols]


def recurring(frame: pd.DataFrame, tolerance: float = STREAM_TOLERANCE,
              cv_max: float = RECURRING_CV) -> pd.DataFrame:
    """Per account: is the DOMINANT stream a recurring credit.

    Returns acct, probable_direct_deposit, plus the stream columns the verdict
    was drawn from, so the evidence travels with it exactly as it does for the
    whole-account measure.

    Same two tests as `cadence()` -- a payroll-shaped gap and a steady amount --
    asked of one stream instead of the whole mixture. Still PROBABLE: isolating
    the stream makes the inference better, not certain, and the extract still
    carries no direct-deposit flag.
    """
    streams = dominant_stream(frame, tolerance)
    if not len(streams):
        return pd.DataFrame(columns=["acct", "probable_direct_deposit",
                                     "stream_n", "stream_median",
                                     "stream_gap_days", "stream_gap_spread",
                                     "stream_cv", "stream_share", "n_streams"])

    streams["probable_direct_deposit"] = (
        rhythmic(streams["stream_gap_days"], streams["stream_gap_spread"])
        & (streams["stream_n"] >= MIN_DEPOSITS_FOR_CADENCE)
        & (streams["stream_cv"] <= cv_max))
    return streams


# A refund-shaped credit: several times the account's usual pay, landing in
# the window the IRS actually pays in. Timing is what separates it from any
# other windfall -- the amount alone cannot.
REFUND_MONTHS = (2, 3, 4)
REFUND_MULTIPLE = 2.0


def income_shape(frame: pd.DataFrame, tolerance: float = STREAM_TOLERANCE
                 ) -> pd.DataFrame:
    """Per account: what KIND of income this is, not just whether it recurs.

    Returns acct, volatility, pay_step, lump_share, refund_amount, pay_dow,
    pay_dom.

    `volatility` is month-to-month variation in TOTAL inflow, which is a
    different question from `stream_cv`: an account can have a perfectly
    steady payroll and violently uneven months once everything else is
    counted. Salaried and hourly separate here, not in the cadence test.

    `pay_step` compares the dominant stream's second half against its first.
    A rise or a cut holds the rhythm and moves the amount, so `stopped()`
    cannot see it and `cadence()` reads it as inconsistency.
    """
    cols = ["acct", "volatility", "pay_step", "lump_share", "refund_amount",
            "pay_dow", "pay_dom"]
    if not len(frame):
        return pd.DataFrame(columns=cols)

    per_month = frame.assign(
        _m=frame["date"].dt.to_period("M")).groupby(["acct", "_m"])[
        "dep_amount"].sum().reset_index()
    vol = per_month.groupby("acct")["dep_amount"].agg(["mean", "std"])
    volatility = np.where(vol["mean"] > 0, vol["std"] / vol["mean"], np.nan)

    totals = frame.groupby("acct")["dep_amount"].sum()
    biggest = frame.groupby("acct")["dep_amount"].max()
    lump_share = (biggest / totals.replace(0, np.nan)).round(3)

    streams = dominant_stream(frame, tolerance)

    # A tax refund is a windfall with a calendar. Largest Feb-Apr credit that
    # clears a multiple of the account's USUAL credit -- the dominant
    # stream's median where there is one. Against the whole-account median,
    # which on a real book is a small transfer, RALLY read 63% of matched
    # accounts as receiving a refund.
    med = frame.groupby("acct")["dep_amount"].median()
    if len(streams):
        usual = streams.set_index("acct")["stream_median"]
        med = usual.reindex(med.index).where(lambda u: u > 0, med)
    spring = frame[frame["date"].dt.month.isin(REFUND_MONTHS)]
    refund = pd.Series(dtype=float)
    if len(spring):
        cand = spring.groupby("acct")["dep_amount"].max()
        floor = med.reindex(cand.index) * REFUND_MULTIPLE
        refund = cand.where(cand >= floor)
    step = pd.Series(dtype=float)
    dow = dom = pd.Series(dtype=float)
    if len(streams):
        centre = streams.set_index("acct")["stream_median"]
        joined = frame.join(centre, on="acct", rsuffix="_c")
        band = joined[
            (joined["stream_median"] > 0) &
            (joined["dep_amount"] >= joined["stream_median"] * (1 - tolerance)) &
            (joined["dep_amount"] <= joined["stream_median"] * (1 + tolerance))]
        if len(band):
            band = band.sort_values(["acct", "date"])
            half = band.groupby("acct").cumcount() >= \
                band.groupby("acct")["dep_amount"].transform("size") / 2
            early = band[~half].groupby("acct")["dep_amount"].mean()
            late = band[half].groupby("acct")["dep_amount"].mean()
            step = (late / early.replace(0, np.nan)).round(3)
            dow = band.groupby("acct")["date"].agg(
                lambda d: d.dt.dayofweek.mode().iloc[0] if len(d) else np.nan)
            dom = band.groupby("acct")["date"].agg(
                lambda d: d.dt.day.mode().iloc[0] if len(d) else np.nan)

    out = pd.DataFrame({"acct": totals.index})
    out["volatility"] = np.round(pd.Series(volatility, index=vol.index)
                                 .reindex(out["acct"]).values, 3)
    out["pay_step"] = step.reindex(out["acct"]).values
    out["lump_share"] = lump_share.reindex(out["acct"]).values
    out["refund_amount"] = (refund.reindex(out["acct"]).values
                            if len(refund) else np.nan)
    out["pay_dow"] = dow.reindex(out["acct"]).values if len(dow) else np.nan
    out["pay_dom"] = dom.reindex(out["acct"]).values if len(dom) else np.nan
    return out[cols]
