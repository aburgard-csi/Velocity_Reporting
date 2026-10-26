# Ported from ARS v5 02-Scripts/ars/monthly_analysis/deposit_behaviour.py at a491b5c (James Gilmore); logic unchanged.
"""Deposit behaviour: what the rolling-365 deposits file says on its own,
and what it says once joined to the ODD.

Named "deposit behaviour", not "deposits", because `deposits` is already
taken: `balance.py` owns balance bands and flight risk under that name, and a
second thing called deposits would collide in the manual, the section router
and the reader's head. Every key here is `dep_*`.

What this can say that nothing else could: `balance.py` admits its own limit --
`bal_delta = Curr Bal - Avg Bal` is "a trend proxy, not a time series ... not
enough to date the decline". This chapter has the series, so it dates it.

Declines with a warn rather than reporting zeros when the file is absent. A
book-wide "nobody has a recurring deposit" reads as a finding, and that exact
failure has already happened once on a real client.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ti.core.deposits import behaviour as B
from ti.core.deposits import streams as S
from ti.core.deposits import trend as T

from .retention import COOLING_RATIO, DECLINING_RATIO

BASE_LABEL = "Open at anchor"
# Same floor stressors.py uses. A signal true of nearly everyone is a failed
# join or a defaulted predicate, never a finding.
SATURATION_PCT = 95.0
# Idle cash: a balance this size that the deposits file has not fed recently.
IDLE_BALANCE = 25_000
IDLE_QUIET_DAYS = 90
# Reporting floor. Below this a percentage is noise dressed as a number.
MIN_COHORT = 30

# Every threshold in this chapter is a DEFAULT, not a law. A floor of 30 is
# right for a book doing 300 a month and wrong for one doing six; the same
# applies to what counts as idle, as a missed cycle, or as one deposit stream.
# Each reads from clients_config.json first and falls back to the value above.
SETTINGS = {
    "DepositMinCohort": ("min_cohort", MIN_COHORT),
    "DepositIdleBalance": ("idle_balance", IDLE_BALANCE),
    "DepositIdleQuietDays": ("idle_quiet_days", IDLE_QUIET_DAYS),
    "DepositStreamTolerance": ("stream_tolerance", S.STREAM_TOLERANCE),
    "DepositRecurringCV": ("recurring_cv", B.RECURRING_CV),
    "DepositSaturationPct": ("saturation_pct", SATURATION_PCT),
}


def _settings(config: dict, warn) -> dict:
    """Read the tunables, falling back to the defaults above.

    A client whose config names a threshold gets it; every other client gets
    the default and the run says which were overridden, because a rate computed
    on a moved threshold is not comparable to one that was not.
    """
    out, named = {}, []
    for key, (name, default) in SETTINGS.items():
        value = (config or {}).get(key)
        if value is None:
            out[name] = default
            continue
        try:
            out[name] = type(default)(value)
            named.append(f"{key}={out[name]}")
        except (TypeError, ValueError):
            out[name] = default
            warn(f"deposit behaviour: {key}={value!r} is not a number; "
                 f"using the default {default}")
    if named:
        warn(f"deposit behaviour: client thresholds in use ({', '.join(named)}) "
             f"-- rates are not comparable to a client on the defaults")
    return out


def _pct(n, d, digits=1):
    """None, never 0.0, on an empty denominator -- unmeasurable is not zero."""
    return round(100 * n / d, digits) if d else None


def _key(series) -> pd.Series:
    """The join key, upper-cased on both sides.

    RALLY's deposits file carries the account hash in upper-case hex. If the
    ODD spells the same hash any other way the join silently matches nothing,
    and every account then reads as having no deposits -- indistinguishable
    from a finding.
    """
    return series.astype(str).str.strip().str.upper()


def _saturated(flag: pd.Series, label: str, warn, floor: float = SATURATION_PCT
               ) -> bool:
    share = 100 * float(flag.mean()) if len(flag) else 0.0
    if share >= floor:
        warn(f"deposit behaviour: '{label}' is true of {share:.1f}% of the "
             f"base, at or above the {floor}% saturation floor. That "
             f"is a failed join or a defaulted predicate, not a finding. "
             f"Excluded.")
        return True
    return False


def _file_facts(raw, monthly, out: dict) -> None:
    out["dep_file_rows"] = int(len(raw))
    out["dep_file_accounts"] = int(raw["acct"].nunique())
    out["dep_file_months"] = int(monthly["date"].nunique()) if len(monthly) else 0
    out["dep_first_date"] = raw["date"].min().strftime("%Y-%m-%d")
    out["dep_last_date"] = raw["date"].max().strftime("%Y-%m-%d")


def _join(base: pd.DataFrame, full: pd.DataFrame, raw, out: dict,
          warn) -> pd.Series | None:
    """Match the file against the base, and report the directions separately.

    Three numbers, not two, because "in the file but not in the book" was one
    number doing two incompatible jobs. The deposits file covers the whole
    institution -- savings, business, closed -- while this chapter scores the
    eligible base. Measuring the file against the base therefore produced a
    huge count (95,504 on RALLY) that looks alarming and means nothing: those
    accounts are supposed to be outside the base.

    The number that CAN mean something is file accounts found nowhere in the
    ODD at all. That is a key mismatch or the wrong institution's file, and it
    was invisible while the expected gap was masking it.
    """
    from ti.core.facts import ID_COLUMNS

    col = next((c for c in ID_COLUMNS if c in base.columns), None)
    if col is None:
        warn("deposit behaviour: no account id column on the base; "
             "the deposits file cannot be joined and the section is skipped")
        return None

    book = _key(base[col]).str.replace(r"\.0$", "", regex=True)
    file_accounts = set(_key(pd.Series(raw["acct"].unique())))
    matched = book.isin(file_accounts)

    out["dep_match_pct"] = _pct(int(matched.sum()), len(book))
    out["dep_matched_n"] = int(matched.sum())
    out["dep_in_book_not_file"] = int((~matched).sum())
    out["dep_file_accounts_n"] = len(file_accounts)
    # Expected: the file is institution-wide, the base is not.
    out["dep_in_file_not_base"] = int(len(file_accounts - set(book)))

    # The real integrity check: present in the file, absent from the ENTIRE ODD.
    if full is not None and col in full.columns:
        everyone = set(_key(full[col]).str.replace(r"\.0$", "", regex=True))
        orphans = file_accounts - everyone
        out["dep_in_file_not_odd"] = int(len(orphans))
        out["dep_file_found_in_odd_pct"] = _pct(
            len(file_accounts) - len(orphans), len(file_accounts))
        if (out["dep_file_found_in_odd_pct"] or 0) < 90:
            warn(f"deposit behaviour: {len(orphans):,} of {len(file_accounts):,} "
                 f"accounts in the deposits file "
                 f"({100 - (out['dep_file_found_in_odd_pct'] or 0):.1f}%) appear "
                 f"nowhere in the ODD. Expected near zero -- a file whose "
                 f"accounts the core does not recognise is a key mismatch or "
                 f"the wrong institution's extract.")
    else:
        out["dep_in_file_not_odd"] = None
        out["dep_file_found_in_odd_pct"] = None

    pct = out["dep_match_pct"] or 0.0
    if pct < 5.0:
        warn(f"deposit behaviour: the deposits file joined only {pct}% of "
             f"accounts. The account key does not line up -- every deposit "
             f"figure below would read as 'nobody deposits'. Check the ODD's "
             f"account id against the file's hashed_account.")
    return book


def _behaviour(raw, asof, base_keys, out: dict, warn, cfg) -> None:
    """Rhythm, stoppage and windfalls, on accounts present in BOTH sides."""
    rhythm = B.cadence(raw)
    rhythm = rhythm[_key(rhythm["acct"]).isin(set(base_keys))]
    n = len(rhythm)
    out["dep_scored_n"] = n
    if n < cfg["min_cohort"]:
        warn(f"deposit behaviour: only {n} accounts matched the file, under "
             f"the {cfg['min_cohort']}-account reporting floor; rates not reported")
        return

    # B1 and B2: the evidence behind B3's verdict. cadence() already computes
    # both and the chapter used to read neither, so the rate was published with
    # nothing under it -- and an implausible rate could not be diagnosed.
    bands = B.cadence_band(rhythm["median_gap_days"], rhythm["n_deposits"])
    order = [lab for lab, _, _ in B.CADENCE_BANDS] + ["irregular",
                                                      "too few deposits"]
    counts = bands.value_counts()
    out["dep_cadence_mix"] = [[lab, int(counts.get(lab, 0)),
                               _pct(int(counts.get(lab, 0)), n)]
                              for lab in order if counts.get(lab, 0)]
    out["dep_cadence_mix_columns"] = ["rhythm", "accounts", "pct_of_matched"]

    cvs = B.cv_band(rhythm["amount_cv"])
    cv_order = [lab for lab, _, _ in B.CV_BANDS] + ["not measurable"]
    cv_counts = cvs.value_counts()
    out["dep_consistency"] = [[lab, int(cv_counts.get(lab, 0)),
                               _pct(int(cv_counts.get(lab, 0)), n)]
                              for lab in cv_order if cv_counts.get(lab, 0)]
    out["dep_consistency_columns"] = ["amount consistency", "accounts",
                                      "pct_of_matched"]
    out["dep_recurring_cv_threshold"] = B.RECURRING_CV

    # B5, and the fix for B3. RALLY runs 51 credits per account per year, so a
    # single CV across all of them cannot see a payroll through the mixture:
    # 48.9% of accounts were rhythmic and only 4.6% passed the amount test.
    # The verdict is now asked of the account's dominant stream.
    streams = S.recurring(raw, tolerance=cfg["stream_tolerance"],
                          cv_max=cfg["recurring_cv"])
    streams = streams[_key(streams["acct"]).isin(set(base_keys))]

    # The whole-account measure is kept beside it. This changes a published
    # number, and a change to a published number has to be provable rather
    # than asserted.
    whole = rhythm["probable_direct_deposit"].fillna(False)
    out["dep_recurring_whole_account_pct"] = _pct(int(whole.sum()), n)

    if len(streams):
        mix = streams["n_streams"].clip(upper=4).value_counts()
        out["dep_streams_mix"] = [
            [("4+" if k == 4 else str(int(k))), int(v), _pct(int(v), len(streams))]
            for k, v in sorted(mix.items())]
        out["dep_streams_mix_columns"] = ["recurring streams", "accounts",
                                          "pct_of_matched"]
        out["dep_stream_share_median"] = round(
            float(streams["stream_share"].median()), 3)

    out["_streams"] = streams
    recurring = streams["probable_direct_deposit"].fillna(False) \
        if len(streams) else pd.Series(dtype=bool)
    if len(recurring) and not _saturated(recurring, "probable direct deposit",
                                         warn):
        out["dep_recurring_n"] = int(recurring.sum())
        out["dep_recurring_pct"] = _pct(int(recurring.sum()), len(streams))
        out["dep_median_amount"] = round(float(
            streams.loc[recurring, "stream_median"].median()), 2) \
            if recurring.any() else None
        out["dep_recurring_basis"] = "dominant stream"

    halted = B.stopped(raw, asof)
    halted = halted[_key(halted["acct"]).isin(set(base_keys))]
    flag = halted["recurring_stopped"].fillna(False)
    if len(halted) and not _saturated(flag, "recurring credit stopped", warn):
        out["dep_stopped_n"] = int(flag.sum())
        out["dep_stopped_pct"] = _pct(int(flag.sum()), len(halted))
        # WHEN, not just how many. The count alone cannot be charted, and a
        # cohort that all stopped in one month is a different story from one
        # that bled out steadily.
        gone = halted[flag & halted["last_deposit"].notna()]
        if len(gone):
            by_month = gone.groupby(
                gone["last_deposit"].dt.to_period("M").dt.strftime("%Y-%m")
            ).size()
            out["dep_stopped_by_month"] = [[month, int(k)]
                                           for month, k in by_month.sort_index().items()]
            out["dep_stopped_by_month_columns"] = ["month_last_paid", "accounts"]

    # windfalls() has been written, tested and never called since it landed.
    usual = (streams.set_index("acct")["stream_median"]
             if len(streams) else None)
    wind = B.windfalls(raw, reference=usual)
    wind = wind[_key(wind["acct"]).isin(set(base_keys))]
    if len(wind):
        has = wind["n_windfalls"].fillna(0) > 0
        # Guarded like every other rate here. On RALLY this fired on 52.5% of
        # matched accounts, which is not a windfall, it is a median dragged
        # down by small credits -- and it reached the report unchecked because
        # the guard was wired to only two of four signals.
        if not _saturated(has, "windfall deposits", warn):
            out["dep_windfall_accounts"] = int(has.sum())
            out["dep_windfall_pct"] = _pct(int(has.sum()), len(wind))
            out["dep_windfall_dollars"] = round(float(
                wind.loc[has, "windfall_dollars"].sum()))



# Bands for the dated events. Quiet days first, because "when did money last
# arrive" is the question a branch can act on.
QUIET_BANDS = ((0, 30, "within 30 days"), (30, 60, "30 - 60 days"),
               (60, 90, "60 - 90 days"), (90, 180, "90 - 180 days"),
               (180, 10**6, "over 180 days"))
GAP_BANDS = ((0, 45, "under 45 days"), (45, 90, "45 - 90 days"),
             (90, 180, "90 - 180 days"), (180, 10**6, "over 180 days"))
ONSET_BANDS = ((0, 30, "within 30 days"), (30, 90, "30 - 90 days"),
               (90, 365, "90 days - 1 year"), (365, 10**6, "over a year"))


def _bands(values, bands, total) -> list:
    out = []
    for low, high, label in bands:
        n = int(((values >= low) & (values < high)).sum())
        if n:
            out.append([label, n, _pct(n, total)])
    return out


def _milestones(raw, asof, base, base_keys, out: dict) -> None:
    """Section C: the dated events, and section E's per-account totals.

    milestones() has computed all of this since the package split and nothing
    read it -- the catalogue said `built` because the engine function existed,
    which is not the same as a number anyone can see.
    """
    marks = B.milestones(raw, asof)
    marks = marks[_key(marks["acct"]).isin(set(base_keys))]
    if not len(marks):
        return
    n = len(marks)

    out["dep_quiet_bands"] = _bands(marks["days_since_last"], QUIET_BANDS, n)
    out["dep_quiet_bands_columns"] = ["last deposit", "accounts", "pct_of_matched"]
    out["dep_gap_bands"] = _bands(marks["longest_gap_days"].fillna(0),
                                  GAP_BANDS, n)
    out["dep_gap_bands_columns"] = ["longest gap", "accounts", "pct_of_matched"]
    gaps = marks["longest_gap_days"].dropna()
    out["dep_gap_median_days"] = int(gaps.median()) if len(gaps) else None
    # The median of each account's LARGEST single credit -- not the largest
    # annual total, which is what a first draft of this line computed.
    biggest = raw.groupby("acct")["dep_amount"].max()
    biggest = biggest[_key(pd.Series(biggest.index)).isin(set(base_keys)).values]
    out["dep_largest_deposit_median"] = round(
        float(biggest.median()), 2) if len(biggest) else None

    # E: annual inflow per account. A proxy for income, and labelled as one.
    out["dep_annual_inflow_median"] = round(
        float(marks["total_dollars"].median()), 2)
    out["dep_annual_inflow_p90"] = round(
        float(marks["total_dollars"].quantile(0.9)), 2)

    # C: time to first deposit, which needs the ODD's open date.
    if "Date Opened" in base.columns:
        from ti.core.facts import ID_COLUMNS

        col = next((c for c in ID_COLUMNS if c in base.columns), None)
        opened = pd.to_datetime(base[col].to_frame().assign(
            _o=pd.to_datetime(base["Date Opened"], errors="coerce"))["_o"],
            errors="coerce")
        opened.index = _key(base[col]).str.replace(r"\.0$", "", regex=True)
        first = marks.set_index(_key(marks["acct"]))["first_deposit"]
        pair = pd.concat([opened.rename("opened"), first.rename("first")],
                         axis=1, join="inner").dropna()
        # Accounts that opened before the file's window cannot have a
        # measurable onset: their first deposit HERE is not their first
        # deposit. The first cut kept every non-negative gap, and an account
        # opened in 2019 read as taking 3,768 days to start depositing.
        window_start = raw["date"].min()
        pair = pair[pair["opened"] >= window_start]
        if len(pair):
            days = (pair["first"] - pair["opened"]).dt.days
            days = days[days >= 0]
            if len(days):
                out["dep_onset_months"] = _bands(days, ONSET_BANDS, len(days))
                out["dep_onset_months_columns"] = ["first deposit after open",
                                                   "accounts", "pct_measured"]
                out["dep_onset_median_days"] = int(days.median())
                out["dep_onset_measured_n"] = int(len(days))



# Month-to-month variation in TOTAL inflow. Salaried pay sits low; hourly and
# gig sit high. A different question from stream_cv, which asks only whether
# ONE credit repeats steadily.
VOLATILITY_BANDS = ((0, 0.20, "steady (< 0.20)"),
                    (0.20, 0.50, "variable (0.20 - 0.50)"),
                    (0.50, 1.00, "uneven (0.50 - 1.00)"),
                    (1.00, 10**6, "very uneven (> 1.00)"))
# A pay change has to clear the noise in an account's own stream to count.
PAY_STEP_UP, PAY_STEP_DOWN = 1.10, 0.90
# One credit carrying this much of a year is a savings vehicle, not a wage.
LUMP_SHARE = 0.50
DOW_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _income_shape(raw, base_keys, out: dict, cfg) -> None:
    """Section L: what KIND of income, not just whether it recurs."""
    shape = S.income_shape(raw, tolerance=cfg["stream_tolerance"])
    shape = shape[_key(shape["acct"]).isin(set(base_keys))]
    n = len(shape)
    if not n:
        return

    out["dep_volatility_bands"] = _bands(shape["volatility"].dropna(),
                                         VOLATILITY_BANDS,
                                         int(shape["volatility"].notna().sum()))
    out["dep_volatility_bands_columns"] = ["month-to-month inflow", "accounts",
                                           "pct_measured"]
    out["dep_volatility_median"] = round(float(shape["volatility"].median()), 3)

    step = shape["pay_step"].dropna()
    if len(step):
        up, down = int((step >= PAY_STEP_UP).sum()), int((step <= PAY_STEP_DOWN).sum())
        out["dep_pay_rise_n"] = up
        out["dep_pay_cut_n"] = down
        out["dep_pay_step_measured_n"] = int(len(step))
        out["dep_pay_change"] = [["pay rose 10%+", up, _pct(up, len(step))],
                                 ["pay fell 10%+", down, _pct(down, len(step))],
                                 ["held", len(step) - up - down,
                                  _pct(len(step) - up - down, len(step))]]
        out["dep_pay_change_columns"] = ["dominant stream", "accounts",
                                         "pct_measured"]

    lump = shape["lump_share"].dropna()
    if len(lump):
        big = int((lump >= LUMP_SHARE).sum())
        out["dep_lump_sum_n"] = big
        out["dep_lump_sum_pct"] = _pct(big, len(lump))
        out["dep_lump_share_median"] = round(float(lump.median()), 3)

    refunds = shape["refund_amount"].dropna()
    if len(refunds):
        out["dep_refund_n"] = int(len(refunds))
        out["dep_refund_pct"] = _pct(len(refunds), n)
        out["dep_refund_median"] = round(float(refunds.median()), 2)
        out["dep_refund_dollars"] = round(float(refunds.sum()))
        out["dep_refund_note"] = ("largest Feb-Apr credit at 2x the account's "
                                  "own median. Inferred from timing, not "
                                  "labelled by the core")

    dow = shape["pay_dow"].dropna()
    if len(dow):
        counts = dow.value_counts().sort_index()
        out["dep_payday_weekday"] = [
            [DOW_NAMES[int(k)] if 0 <= int(k) < 7 else str(k), int(v),
             _pct(int(v), len(dow))] for k, v in counts.items()]
        out["dep_payday_weekday_columns"] = ["payday", "accounts",
                                             "pct_measured"]



# Buffer days: balance divided by daily spend. Under a week is an account one
# missed payday from an overdraft.
BUFFER_BANDS = ((0, 7, "under a week"), (7, 30, "1 - 4 weeks"),
                (30, 90, "1 - 3 months"), (90, 10**6, "over 3 months"))
# Primacy: pay lands here AND the balance is fed. balance.py tiers PFI on
# swipe counts, which is a proxy for the same idea and a weaker one.
PRIMACY_MIN_INFLOW = 12_000


def _liquidity(base, book_keys, streams_frame, out: dict, cfg) -> None:
    """Section M: the ILS argument. Uncomputable before deposit dates existed.

    The ODD carries monthly NSF/OD item columns as `{Mon}{YY} MTD` -- the
    suffix profile.py and odd_transform.py read, and the one REFERENCE.md
    documents. Crossing them with income regularity answers the question the
    whole overdraft programme rests on and which has never been asked of real
    income data: do irregular earners overdraft more.

    The first cut looked for a suffix called `Items`. No ODD has one, so this
    section returned before its first line on every real book.
    """
    from ti.core.periods import columns_for

    item_cols = columns_for(base.columns, "MTD")
    if not item_cols:
        return
    items = base[item_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    od_items = items.sum(axis=1)
    any_od = od_items > 0
    out["dep_od_base_n"] = int(len(base))
    out["dep_od_accounts_n"] = int(any_od.sum())

    if streams_frame is not None and len(streams_frame):
        idx = _key(streams_frame["acct"])
        steady = streams_frame.set_index(idx)["probable_direct_deposit"]
        mapped = book_keys.map(steady).astype("boolean")
        # Three populations, not two. 'Not on a rhythm' once held every
        # account the file never mentioned -- 44,801 on RALLY, mostly
        # secondary accounts that rarely overdraft -- and the comparison read
        # backwards. An account with no deposits is its own row.
        in_file = mapped.notna()
        paid = mapped.fillna(False).astype(bool)
        rows = []
        for label, mask in (("paid on a rhythm", paid),
                            ("not on a rhythm", in_file & ~paid),
                            ("no deposits", ~in_file)):
            k = int(mask.sum())
            if not k:
                continue
            rows.append([label, k, int(any_od[mask].sum()),
                         _pct(int(any_od[mask].sum()), k),
                         round(float(od_items[mask].sum()))])
        out["dep_od_by_rhythm"] = rows
        out["dep_od_by_rhythm_columns"] = ["income", "accounts",
                                           "overdrafting", "pct_overdrafting",
                                           "od_items"]

    # K: the OD programme's own columns against income. Same frame, one more
    # cut -- ILS already reports zero-limit accounts by deposit activity, so
    # this is deliberately the ARS-side view and not a second copy of that.
    if "OD Limit" in base.columns and streams_frame is not None \
            and len(streams_frame):
        limit = pd.to_numeric(base["OD Limit"], errors="coerce")
        idx2 = _key(streams_frame["acct"])
        paid = book_keys.map(
            streams_frame.set_index(idx2)["probable_direct_deposit"]
        ).astype("boolean").fillna(False).astype(bool)
        rows = []
        for label, mask in (("has an OD limit", limit > 0),
                            ("no OD limit", limit.isna() | (limit <= 0))):
            k = int(mask.sum())
            if k:
                rows.append([label, k, int((mask & paid).sum()),
                             _pct(int((mask & paid).sum()), k)])
        if rows:
            out["dep_od_limit_by_income"] = rows
            out["dep_od_limit_by_income_columns"] = [
                "overdraft limit", "accounts", "paid on a rhythm",
                "pct_paid_here"]

    # Buffer days -- balance against the account's own daily spend.
    curr = pd.to_numeric(base.get("Curr Bal"), errors="coerce") \
        if "Curr Bal" in base.columns else pd.Series(np.nan, index=base.index)
    spend_cols = columns_for(base.columns, "Spend")
    if spend_cols:
        daily = (base[spend_cols].apply(pd.to_numeric, errors="coerce")
                 .fillna(0).sum(axis=1) / 365.0)
        buffer_days = pd.Series(
            np.where(daily > 0, curr / daily, np.nan), index=base.index)
        measured = int(buffer_days.notna().sum())
        if measured:
            out["dep_buffer_bands"] = _bands(buffer_days.dropna(),
                                             BUFFER_BANDS, measured)
            out["dep_buffer_bands_columns"] = ["days of spending in the balance",
                                               "accounts", "pct_measured"]
            out["dep_buffer_median_days"] = int(buffer_days.median())


def _primacy(base, book_keys, total, streams_frame, asof, out: dict) -> None:
    """Section N: primacy on where pay lands, not on swipe counts."""
    curr = pd.to_numeric(base.get("Curr Bal"), errors="coerce") \
        if "Curr Bal" in base.columns else pd.Series(np.nan, index=base.index)
    paid_here = pd.Series(False, index=base.index)
    if streams_frame is not None and len(streams_frame):
        idx = _key(streams_frame["acct"])
        paid_here = book_keys.map(
            streams_frame.set_index(idx)["probable_direct_deposit"]
        ).astype("boolean").fillna(False).astype(bool)

    fed = total.fillna(0) >= PRIMACY_MIN_INFLOW
    primary = paid_here & fed
    out["dep_primacy_n"] = int(primary.sum())
    out["dep_primacy_pct"] = _pct(int(primary.sum()), len(base))
    out["dep_primacy_dollars"] = round(float(curr[primary].sum()))
    out["dep_primacy_floor"] = PRIMACY_MIN_INFLOW
    out["dep_primacy_note"] = (
        "pay lands here AND a year's inflow clears the floor. balance.py "
        "tiers PFI on swipe counts, which asks the same question of weaker "
        "evidence")

    # F: inflow against spend, cut by the two dimensions the ODD already
    # carries. profile.py does age and the branch tables do branch; neither
    # could put inflow beside spend until now.
    from ti.core.periods import columns_for

    spend_cols2 = columns_for(base.columns, "Spend")
    if spend_cols2 and total.notna().any():
        spend2 = base[spend_cols2].apply(pd.to_numeric, errors="coerce") \
            .fillna(0).sum(axis=1)
        if "DOB" in base.columns:
            dob = pd.to_datetime(base["DOB"], errors="coerce")
            # Against the run's anchor, never today. An age band read from
            # the wall clock moves a member across a boundary overnight, so
            # the same month re-run in December answers differently.
            age = (asof - dob).dt.days / 365.25
            rows = []
            for label, lo, hi in (("under 25", 0, 25), ("25 - 34", 25, 35),
                                  ("35 - 49", 35, 50), ("50 - 64", 50, 65),
                                  ("65 or over", 65, 120)):
                mask = age.between(lo, hi, inclusive="left") & total.notna()
                k = int(mask.sum())
                if k >= MIN_COHORT:
                    rows.append([label, k,
                                 round(float(total[mask].median()), 2),
                                 round(float(spend2[mask].median()), 2)])
            if rows:
                out["dep_inflow_by_age"] = rows
                out["dep_inflow_by_age_columns"] = [
                    "holder age", "accounts", "median_inflow", "median_spend"]
        if "branch_name" in base.columns or "Branch" in base.columns:
            col = "branch_name" if "branch_name" in base.columns else "Branch"
            grp = base.assign(_i=total, _s=spend2).groupby(
                base[col].astype(str), dropna=False)
            rows = []
            for label, g in grp:
                k = int(g["_i"].notna().sum())
                if k >= MIN_COHORT:
                    rows.append([str(label)[:20], k,
                                 round(float(g["_i"].median()), 2),
                                 round(float(g["_s"].median()), 2)])
            rows.sort(key=lambda r: -r[1])
            if rows:
                out["dep_inflow_by_branch"] = rows[:12]
                out["dep_inflow_by_branch_columns"] = [
                    "branch", "accounts", "median_inflow", "median_spend"]

    # N: does inflow ramp in the first year, by open vintage. cohort.py does
    # this shape for spend; the question for deposits is whether a new member
    # ever starts funding the account at all.
    if "Date Opened" in base.columns:
        opened = pd.to_datetime(base["Date Opened"], errors="coerce")
        tenure = (asof - opened).dt.days / 365.25
        rows = []
        for label, lo, hi in (("under 1 year", 0, 1), ("1 - 2 years", 1, 2),
                              ("2 - 5 years", 2, 5), ("5 years or more", 5, 99)):
            mask = tenure.between(lo, hi, inclusive="left") & total.notna()
            k = int(mask.sum())
            if k >= MIN_COHORT:
                rows.append([label, k, round(float(total[mask].median()), 2)])
        if rows:
            out["dep_inflow_by_vintage"] = rows
            out["dep_inflow_by_vintage_columns"] = ["tenure", "accounts",
                                                    "median_annual_inflow"]

    # H: does the programme move DEPOSITS, not just spend. The ba_* harness
    # measures responder spend lift; nothing asked the same of inflow. Both
    # flags are already on the ODD.
    for flag_col, keys, label in (
            ("DM-REF Source", ("dep_responder_inflow", "dep_responder_note"),
             "responded to a mailing"),
            ("ICS", ("dep_ics_inflow", "dep_ics_note"), "opened through ICS")):
        col = next((c for c in base.columns
                    if flag_col.lower() in str(c).lower()), None)
        if col is None or not total.notna().any():
            continue
        marked = base[col].astype(str).str.strip().replace(
            {"nan": "", "None": ""}) != ""
        rows = []
        for name, mask in ((label, marked), ("everyone else", ~marked)):
            k = int((mask & total.notna()).sum())
            if k >= MIN_COHORT:
                rows.append([name, k, round(float(total[mask].median()), 2)])
        if len(rows) == 2:
            out[keys[0]] = rows
            out[f"{keys[0]}_columns"] = ["cohort", "accounts",
                                         "median_annual_inflow"]
            out[keys[1]] = (
                f"median annual inflow, {label} against everyone else. A "
                f"difference here is an association, not a lift -- these "
                f"cohorts were not randomised and are not age-matched")

    # Reconciliation: does the balance move the way inflow minus spend says.
    from ti.core.periods import columns_for

    spend_cols = columns_for(base.columns, "Spend")
    avg = pd.to_numeric(base.get("Avg Bal"), errors="coerce") \
        if "Avg Bal" in base.columns else pd.Series(np.nan, index=base.index)
    if spend_cols and avg.notna().any():
        spend = base[spend_cols].apply(pd.to_numeric, errors="coerce") \
            .fillna(0).sum(axis=1)
        expected = total.fillna(0) - spend
        actual = curr - avg
        residual = actual - expected
        ok = residual.abs() <= (total.fillna(0).abs() * 0.25 + 500)
        out["dep_reconciled_pct"] = _pct(int(ok.sum()), int(ok.notna().sum()))
        out["dep_reconcile_residual_median"] = round(float(residual.median()), 2)
        out["dep_reconcile_note"] = (
            "balance delta against inflow minus card spend. Cash, transfers "
            "and cheques are in neither source, so a residual is expected -- "
            "its SIZE is the data-quality signal")


def _employers(raw, base_keys, out: dict, cfg) -> None:
    """Section P: a counterparty signal from a file with no counterparty.

    Accounts receiving the same amount on the same day of the month, on the
    same rhythm, repeatedly, share an employer. Inference, and labelled as
    one -- it names a COHORT, never an employer.
    """
    shape = S.income_shape(raw, tolerance=cfg["stream_tolerance"])
    shape = shape[_key(shape["acct"]).isin(set(base_keys))]
    streams = S.dominant_stream(raw, tolerance=cfg["stream_tolerance"])
    streams = streams[_key(streams["acct"]).isin(set(base_keys))]
    if not len(shape) or not len(streams):
        return
    joined = shape.merge(streams[["acct", "stream_median", "stream_n"]],
                         on="acct", how="inner")
    # Parenthesised: `>= 4 & notna()` binds as `>= (4 & notna)`, which is
    # `>= 1`, and RALLY read 99% of matched accounts as sharing an employer.
    joined = joined[(joined["stream_n"] >= B.MIN_DEPOSITS_FOR_CADENCE)
                    & joined["pay_dom"].notna()]
    if not len(joined):
        return
    # Bin the amount so near-identical pay lands together, then group on
    # (amount band, day of month).
    band = np.floor(np.log(joined["stream_median"].clip(lower=1))
                    / np.log1p(cfg["stream_tolerance"]))
    grouped = joined.assign(_b=band).groupby(["_b", "pay_dom"]).size()
    cohorts = grouped[grouped >= 5]
    out["dep_employer_cohorts_n"] = int(len(cohorts))
    out["dep_employer_covered_n"] = int(cohorts.sum())
    out["dep_employer_covered_pct"] = _pct(int(cohorts.sum()), len(joined))
    out["dep_employer_largest"] = int(cohorts.max()) if len(cohorts) else 0
    out["dep_employer_note"] = (
        "accounts sharing an amount and a payday, five or more together. "
        "Inferred: this names a cohort, never an employer")



# Persona features. Deliberately the deposit-side ones only: ars/lab/_cluster
# already owns the clustering, and this chapter's job is to hand it columns it
# could not previously have.
PERSONA_FEATURES = ("stream_cv", "stream_share", "volatility", "lump_share")


def _risk_and_personas(raw, base_keys, streams_frame, out: dict, cfg) -> None:
    """Sections I and J.

    I: a deposit-sourced stressor. `balance_flight` is labelled "Deposits
    leaving" and computed from Curr Bal against Avg Bal -- it has never seen a
    deposit. A recurring credit that STOPPED is a member losing income, which
    is a different event from a balance dipping, and this chapter can see it.

    J: the feature columns a persona clustering could use. Emitted as a
    spec plus their spread rather than as clusters -- ars/lab/_cluster.py owns
    the clustering, and duplicating it here would give two answers.
    """
    if streams_frame is None or not len(streams_frame):
        return
    shape = S.income_shape(raw, tolerance=cfg["stream_tolerance"])
    shape = shape[_key(shape["acct"]).isin(set(base_keys))]
    merged = streams_frame.merge(shape, on="acct", how="left")
    if not len(merged):
        return

    # I: the condition, and what makes it different from balance_flight.
    stopped_n = out.get("dep_stopped_n")
    if stopped_n is not None:
        out["dep_income_loss_n"] = stopped_n
        out["dep_income_loss_note"] = (
            "a recurring credit that stopped. balance_flight is labelled "
            "'Deposits leaving' and is computed from Curr Bal against Avg Bal "
            "-- it has never seen a deposit. This is a member losing income, "
            "not a balance dipping, and the two do not select the same people")

    # I: the deposit chapter's own view of the scored conditions. The stressor
    # chapter computes them and report.py renders none of it, so a reader has
    # no way to see which conditions fired or on how many accounts. These are
    # the two this chapter can speak to, side by side, because the whole point
    # is that they do NOT select the same people.
    rows = []
    if stopped_n is not None:
        rows.append(["income stopped (deposits)", stopped_n,
                     _pct(stopped_n, len(merged))])
    both = out.get("dep_falling_and_slowing_n")
    if both is not None:
        rows.append(["balance falling AND inflow slowing", both, None])
    fall_only = out.get("dep_falling_only_n")
    if fall_only is not None:
        rows.append(["balance falling only (what flight risk sees)",
                     fall_only, None])
    if rows:
        out["dep_risk_signals"] = rows
        out["dep_risk_signals_columns"] = ["signal", "accounts", "pct_of_matched"]
        out["dep_risk_note"] = (
            "the stressor chapter scores six conditions and report.py renders "
            "none of them. These are the two this chapter can see, shown apart "
            "because a balance dipping and a member losing income are "
            "different events on different accounts")

    # J: the columns, and whether each is usable as a clustering input.
    rows = []
    for col in PERSONA_FEATURES:
        if col not in merged.columns:
            continue
        vals = pd.to_numeric(merged[col], errors="coerce").dropna()
        if not len(vals):
            continue
        rows.append([col, int(len(vals)), _pct(len(vals), len(merged)),
                     round(float(vals.median()), 3),
                     round(float(vals.quantile(0.9)), 3)])
    if rows:
        out["dep_persona_features"] = rows
        out["dep_persona_features_columns"] = ["feature", "accounts",
                                               "pct_measured", "median", "p90"]
        out["dep_persona_note"] = (
            "feature columns for ars/lab/_cluster.py, not clusters. The "
            "clustering lives there; computing it twice would give two answers")


def _competition(txn: dict | None, out: dict, warn) -> None:
    """Sections G and O: depositors against where the money goes.

    Reads the transaction chapter's own output rather than the raw file, so
    this cannot disagree with the competition section -- the same rule
    overlay.py follows.

    REFUSES when the transaction load was short. A deposit-against-competitor
    figure drawn on a third of the file is not a smaller version of the
    finding, it is a different and wrong one, and on RALLY nine of twelve
    months were short while the three healthy ones made it look seasonal.
    """
    if not txn:
        return
    rows = txn.get("txn_monthly") or []
    if rows:
        counts = [r[1] for r in rows]
        flat = [c for c in counts if counts.count(c) > 1]
        if flat:
            warn(f"deposit behaviour: the transaction chapter reports "
                 f"{len(flat)} month(s) with identical row counts "
                 f"({flat[0]:,}), which is a short load, not a season. "
                 f"Sections G and O are NOT built -- a deposit-against-"
                 f"competitor figure drawn on a partial file is wrong, not "
                 f"merely small.")
            out["dep_txn_short_months"] = len(flat)
            out["dep_competition_skipped"] = (
                "transaction load incomplete; see dep_txn_short_months")
            return

    comp = txn.get("comp_institutions") or txn.get("comp_top") or []
    spend = txn.get("txn_card_spend")
    if spend:
        out["dep_vs_card_spend"] = [
            ["card spend, year", round(float(spend))],
            ["deposit inflow, year",
             round(float(sum(r[2] for r in (out.get("dep_book_monthly") or []))))],
        ]
        out["dep_vs_card_spend_columns"] = ["measure", "dollars"]
        out["dep_net_position_note"] = (
            "both sides from their own source. Cash, transfers and cheques "
            "are in neither, so this is a direction and not a balance")
    if comp:
        out["dep_competitor_reach"] = len(comp)
        out["dep_competitor_note"] = (
            "named institutions the transaction chapter found. Crossing them "
            "with deposit strength needs the account-level competitor rows, "
            "which live in the TXN run's lists/ rather than in its metrics")


def _trend(raw, monthly, base_keys, out: dict, warn) -> None:
    """Direction of travel, including the month inflow turned."""
    out["dep_book_monthly"] = T.book_monthly(monthly)
    out["dep_book_monthly_columns"] = ["month", "accounts_depositing", "dollars"]

    out["dep_concentration"] = T.concentration(raw)
    out["dep_concentration_columns"] = ["slice", "accounts", "dollars",
                                        "pct_of_inflow"]

    out["dep_distribution"] = T.distribution(raw)
    out["dep_distribution_columns"] = ["decile", "accounts", "floor_dollars",
                                       "median_dollars"]

    # D: seasonality. Twelve months is one cycle -- enough to DESCRIBE a
    # shape, never enough to forecast one, and the label says so.
    series = out.get("dep_book_monthly") or []
    if len(series) >= 6:
        avg = sum(r[2] for r in series) / len(series)
        if avg:
            out["dep_seasonality"] = [[r[0], r[2], round(100 * r[2] / avg, 1)]
                                      for r in series]
            out["dep_seasonality_columns"] = ["month", "dollars",
                                              "pct_of_average"]
            peak = max(series, key=lambda r: r[2])
            low = min(series, key=lambda r: r[2])
            out["dep_seasonality_peak"] = peak[0]
            out["dep_seasonality_trough"] = low[0]
            out["dep_seasonality_note"] = (
                "one cycle of twelve months. Enough to describe a shape, "
                "never enough to forecast one")

    dated = T.decline_month(monthly)
    if not len(dated):
        return
    dated = dated[_key(dated["acct"]).isin(set(base_keys))]
    flag = dated["decline_month"].notna()
    # Guarded: "most of the book is declining" is a broken threshold, not a
    # finding about the book.
    if _saturated(flag, "inflow decline dated", warn):
        return
    found = dated[flag]
    out["dep_declines_dated_n"] = int(len(found))
    out["dep_declines_dated_pct"] = _pct(len(found), len(dated))
    if len(found):
        by_month = found.groupby(
            found["decline_month"].dt.strftime("%Y-%m")).agg(
            accounts=("acct", "size"),
            before=("inflow_before", "sum"), after=("inflow_after", "sum"))
        out["dep_decline_by_month"] = [
            [m, int(r.accounts), round(float(r.before)), round(float(r.after))]
            for m, r in by_month.sort_index().iterrows()]
        out["dep_decline_by_month_columns"] = ["month", "accounts",
                                               "inflow_before", "inflow_after"]


def _against_odd(base, book_keys, raw, monthly, asof, out: dict, cfg) -> None:
    """The ODD pairings: idle cash, balance against inflow, and inflow health.

    Inflow health mirrors retention.py's spend classifier on the same
    thresholds, so "Declining" means the same thing on both series and the two
    can be read side by side.
    """
    marks = B.milestones(raw, asof).set_index(
        _key(B.milestones(raw, asof)["acct"]))
    quiet = book_keys.map(marks["days_since_last"])
    total = book_keys.map(marks["total_dollars"])

    curr = pd.to_numeric(base.get("Curr Bal"), errors="coerce") \
        if "Curr Bal" in base.columns else pd.Series(np.nan, index=base.index)

    # Idle cash: money sitting still that nothing is topping up.
    idle = (curr >= cfg["idle_balance"]) & \
        (quiet.isna() | (quiet >= cfg["idle_quiet_days"]))
    out["dep_idle_balance_floor"] = cfg["idle_balance"]
    out["dep_idle_quiet_days"] = cfg["idle_quiet_days"]
    out["dep_idle_n"] = int(idle.sum())
    out["dep_idle_dollars"] = round(float(curr[idle].sum()))

    # Is the balance being fed, or drawn down. Ratio of a year's inflow to the
    # balance sitting there -- NaN where either side is missing, never 0.
    fed = np.where((curr > 0) & total.notna(), total / curr, np.nan)
    fed = pd.Series(fed, index=base.index)
    out["dep_inflow_to_balance_median"] = (
        round(float(fed.median()), 2) if fed.notna().any() else None)

    # F: the combination signal. Neither number says it on its own -- a
    # balance below its own average is where balance.py stops, and inflow
    # decelerating is where this chapter stops. The accounts doing BOTH are
    # the ones actually draining rather than merely spending a good month.
    avg = pd.to_numeric(base.get("Avg Bal"), errors="coerce") \
        if "Avg Bal" in base.columns else pd.Series(np.nan, index=base.index)
    grid_all = T.wide(monthly)
    if len(grid_all) and grid_all.shape[1] >= 6:
        r3 = grid_all.iloc[:, -3:].mean(axis=1)
        p3 = grid_all.iloc[:, -6:-3].mean(axis=1)
        slowing = pd.Series(np.where(p3 > 0, r3 / p3, np.nan), index=grid_all.index)
        mapped_slow = book_keys.map(slowing)
        falling = (curr < avg) & curr.notna() & avg.notna()
        both = falling & (mapped_slow < DECLINING_RATIO)
        out["dep_falling_and_slowing_n"] = int(both.sum())
        out["dep_falling_and_slowing_pct"] = _pct(int(both.sum()), len(base))
        out["dep_falling_and_slowing_dollars"] = round(float(curr[both].sum()))
        out["dep_falling_only_n"] = int((falling & ~both).sum())
        out["dep_slowing_only_n"] = int(((mapped_slow < DECLINING_RATIO) & ~both).sum())

    # F: net flow. Inflow against the ODD's own spend columns, per account.
    from ti.core.periods import columns_for

    spend_cols = columns_for(base.columns, "Spend")
    if spend_cols and total.notna().any():
        annual_spend = base[spend_cols].apply(pd.to_numeric, errors="coerce") \
            .fillna(0).sum(axis=1)
        net = total.fillna(0) - annual_spend
        out["dep_net_flow_positive_n"] = int((net > 0).sum())
        out["dep_net_flow_positive_pct"] = _pct(int((net > 0).sum()), len(base))
        out["dep_net_flow_median"] = round(float(net.median()), 2)
        out["dep_net_flow_note"] = (
            "inflow from the deposits file minus card spend from the ODD; "
            "cash, transfers and cheques are in neither, so this is a "
            "direction, not a balance")

    grid = T.wide(monthly)
    if len(grid) and grid.shape[1] >= 6:
        recent = grid.iloc[:, -3:].mean(axis=1)
        prior = grid.iloc[:, -6:-3].mean(axis=1)
        ratio = pd.Series(np.where(prior > 0, recent / prior, np.nan),
                          index=grid.index)
        mapped = book_keys.map(ratio)
        health = pd.Series("No deposits", index=base.index, dtype=object)
        health[mapped.notna()] = "Active"
        health[mapped < DECLINING_RATIO] = "Declining"
        health[mapped < COOLING_RATIO] = "Cooling"
        health[mapped.notna() & (recent.reindex(book_keys).values <= 0)] = "Dormant"
        counts = health.value_counts()
        out["dep_inflow_health"] = [
            [str(k), int(v), _pct(int(v), len(health))]
            for k, v in counts.items()]
        out["dep_inflow_health_columns"] = ["inflow_health", "accounts",
                                            "pct_of_base"]


def _unique_accounts(base: pd.DataFrame, warn) -> pd.DataFrame:
    """The base with one row per account id.

    Every section here aligns the deposits file to the book on the account
    key. A duplicated id in the ODD -- RALLY's carries one -- makes that
    alignment raise 'cannot reindex on an axis with duplicate labels', and
    the whole chapter then read as 'no deposits file'. The extract check
    already reports the duplicate; this keeps the first row and says so,
    so one bad row costs one row rather than eleven slides.
    """
    from ti.core.facts import ID_COLUMNS

    col = next((c for c in ID_COLUMNS if c in base.columns), None)
    if col is None:
        return base
    dup = _key(base[col]).duplicated()
    if not dup.any():
        return base
    warn(f"deposit behaviour: {int(dup.sum())} duplicate account id row(s) "
         f"dropped from the base (first row kept); the extract check "
         f"reports the same ids")
    return base[~dup.values]


def compute(subsets, config: dict, warn) -> dict:
    """Section contract: (subsets, config, warn) -> dict of dep_* keys."""
    raw = config.get("_deposit_raw")
    if raw is None or not len(raw):
        # Not built, not zero. run.py already warns when a file was found and
        # parsed to nothing; silence here would look like a clean result.
        return {}

    base = _unique_accounts(subsets.eligible, warn)
    if not len(base):
        return {}

    anchor = subsets.anchor
    asof = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    monthly = config.get("_deposit_monthly")
    if monthly is None or not len(monthly):
        monthly = T.monthly(raw)

    cfg = _settings(config, warn)
    out: dict = {"dep_base": BASE_LABEL, "dep_n": int(len(base))}
    _file_facts(raw, monthly, out)

    book_keys = _join(base, getattr(subsets, 'total', None), raw, out, warn)
    if book_keys is None:
        return out

    # Section A as a TABLE, not just terminal output. Its numbers otherwise
    # live only in one run's scrollback, so nobody can see the deposits file
    # getting better or worse -- which, after four rounds of join failures on
    # this client, is the thing most worth trending.
    out["dep_coverage"] = [[
        out.get("dep_file_rows"), out.get("dep_file_accounts"),
        out.get("dep_file_months"), out.get("dep_first_date"),
        out.get("dep_last_date"), out.get("dep_n"), out.get("dep_matched_n"),
        out.get("dep_match_pct"), out.get("dep_in_book_not_file"),
        out.get("dep_in_file_not_base"), out.get("dep_in_file_not_odd"),
        out.get("dep_file_found_in_odd_pct"),
    ]]
    out["dep_coverage_columns"] = [
        "file_rows", "file_accounts", "file_months", "first_date", "last_date",
        "base_n", "matched_n", "match_pct", "in_base_no_deposits",
        "in_file_not_base", "in_file_not_odd", "file_found_in_odd_pct"]

    _behaviour(raw, asof, book_keys, out, warn, cfg)
    _milestones(raw, asof, base, book_keys, out)
    _income_shape(raw, book_keys, out, cfg)
    _employers(raw, book_keys, out, cfg)
    _trend(raw, monthly, book_keys, out, warn)
    _against_odd(base, book_keys, raw, monthly, asof, out, cfg)

    _competition(config.get("_txn"), out, warn)
    streams_frame = out.pop("_streams", None)
    _risk_and_personas(raw, book_keys, streams_frame, out, cfg)
    marks = B.milestones(raw, asof)
    total = book_keys.map(marks.set_index(_key(marks["acct"]))["total_dollars"])
    _liquidity(base, book_keys, streams_frame, out, cfg)
    _primacy(base, book_keys, total, streams_frame, asof, out)
    return out
