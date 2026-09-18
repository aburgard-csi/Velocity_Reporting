"""Mail and response.

Wave months come from the Resp column tags, so the code follows the mailing
calendar rather than a list someone typed. Campaigns with no responses yet
are reported as in flight, not as a 0% response rate -- the newest mailing
usually drops days before the file is pulled.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for, trailing
from ..core.subsets import Subsets, has_debit, norm, num_col

# Known response tiers, weakest to strongest, used ONLY to order the display
# when the observed values happen to match. Values outside this list are kept
# and reported -- never silently dropped, which is what turned an unmatched
# tier into a phantom "0 Same, 0 Declined".
KNOWN_TIERS = ["NU 1-4", "NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"]


def tier_group(value: str) -> str:
    """NU | TH | tracked | other.

    Program mechanic: a response is NU 5+ or any TH tier. NU 1-4 is tracked
    but is not a response. Consecutive-wave responses are only possible
    ACROSS groups -- NU 5+ -> TH, or TH -> NU. Back-to-back NU 5+, or any
    TH -> TH, cannot occur by design.
    """
    v = str(value).strip()
    if not v:
        return "other"
    if _TH.match(v):
        return "TH"
    if _NU_PLUS.match(v):
        return "NU"
    if v.upper().startswith("NU"):
        return "tracked"
    return "other"


def observed_tiers(elig, waves, config) -> list[str]:
    """Every response value actually present, in a stable display order.

    Config wins if the client declares an order; otherwise known tiers come
    first in their canonical sequence, then anything else alphabetically.
    """
    declared = [str(t).strip() for t in config.get("ResponseTierOrder", [])]
    seen: set[str] = set()
    for m in waves:
        col = f"{m.tag} Resp"
        if col in elig.columns:
            seen.update(v for v in norm(elig[col]).unique() if v)
    if declared:
        extra = sorted(seen - set(declared))
        return declared + extra
    known = [t for t in KNOWN_TIERS if t in seen]
    return known + sorted(seen - set(known))

_TH = re.compile(r"^TH[\s\-_]?\d+", re.I)
_NU_PLUS = re.compile(r"^NU[\s\-_]?\d+\s*\+", re.I)

ACCOUNT_AGE_BANDS = [(0, 1, "< 1 yr"), (1, 2, "1-2 yr"), (2, 3, "2-3 yr"),
                     (3, 5, "3-5 yr"), (5, 10, "5-10 yr"), (10, 200, "10+ yr")]


def _wave_months(df: pd.DataFrame) -> list[Month]:
    return [Month.from_tag(c.split()[0]) for c in columns_for(df.columns, "Resp")]


def _mailed(df: pd.DataFrame, month: Month) -> pd.Series:
    col = f"{month.tag} Mail"
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].notna() & (norm(df[col]) != "")


def _responded(df: pd.DataFrame, month: Month) -> pd.Series:
    """Uses the Wave Group column written by the transform, so the
    definition of 'responded' matches the enrichment exactly."""
    seg = f"{month.tag} Wave Group"
    if seg in df.columns:
        return df[seg] == "Responder"
    return pd.Series(False, index=df.index)


def _tier(df: pd.DataFrame, month: Month) -> pd.Series:
    col = f"{month.tag} Resp"
    if col not in df.columns:
        return pd.Series("", index=df.index)
    return norm(df[col])


def tier_key(value: str) -> str:
    """A tier's identity, free of its spelling.

    The Mail column and the Resp column do not share a vocabulary: an offer
    is stamped "NU" where the response that answers it comes back "NU 5+"
    (legacy `_helpers.MAILED_SEGMENTS` against `RESPONSE_SEGMENTS`). TH tiers
    spell the same on both sides. Keying on identity lets one tier be
    recognised through either column's spelling.
    """
    v = str(value).strip().upper()
    if not v or v == "NAN":
        return ""
    if v.startswith("NU"):
        return "NU"
    digits = "".join(ch for ch in v if ch.isdigit())
    if v.startswith("TH") and digits:
        return f"TH{digits}"
    return v


def ladder_order(values, config: dict) -> list[str]:
    """Challenge tiers weakest to strongest.

    Config wins when the client declares an order; otherwise the canonical
    ladder first, then anything unrecognised alphabetically. Never sort the
    raw strings -- 'TH-5' would land before 'TH-10'.
    """
    declared = [str(t).strip() for t in config.get("ResponseTierOrder", [])]
    present = {str(v).strip() for v in values if str(v).strip()}
    if declared:
        return [t for t in declared if t in present] + sorted(present - set(declared))
    known = [t for t in KNOWN_TIERS if t in present]
    return known + sorted(present - set(known))


def challenge_segments(frame: pd.DataFrame, index, month: Month,
                       config: dict) -> tuple[pd.Series, list[str]]:
    """Assign every mailed account to a CHALLENGE segment for one wave.

    Legacy assignment priority (legacy 22 / 28_segment_combo_lines):
    a responder takes its own Resp tier; NU 1-4 (tried, missed) falls into
    the NU segment as a non-responder; an account with no Resp value takes
    the tier from its Mail value when the file carries one. Files whose Mail
    column is a bare 'M' leave those accounts unassigned -- they are counted
    nowhere rather than guessed into a tier.

    Returns (assignment, tiers-in-ladder-order).
    """
    resp_raw = frame.loc[index, f"{month.tag} Resp"].astype(str).str.strip()
    responded = _responded(frame, month).loc[index]
    tiers = ladder_order(set(resp_raw[responded]) - {"", "nan"}, config)

    assign = pd.Series("", index=index)
    assign[responded] = resp_raw[responded]
    nu_seg = next((t for t in tiers if t.upper().startswith("NU")), None)
    partial = resp_raw.str.upper().str.startswith("NU") & ~responded
    if nu_seg is not None:
        assign[partial] = nu_seg
    mail_col = f"{month.tag} Mail"
    if mail_col in frame.columns:
        mail_vals = frame.loc[index, mail_col].astype(str).str.strip()
        # Match the offer to its tier by identity, not by spelling. An exact
        # string match dropped every NU-mailed non-responder -- the Mail
        # column stamps "NU", the ladder is built from responses and reads
        # "NU 5+" -- so one row, and only one, came up short: James caught
        # the NU 5+ row reading 1,177 mailed against the workbook's 7,893,
        # with every TH row correct. Values that name no tier, a bare "M"
        # among them, stay unassigned as before.
        by_key: dict[str, str] = {}
        for tier in tiers:
            by_key.setdefault(tier_key(tier), tier)
        mapped = mail_vals.map(lambda v: by_key.get(tier_key(v), ""))
        takes_mail = (assign == "") & (mapped != "")
        assign[takes_mail] = mapped[takes_mail]
    return assign, tiers


def _pct(n, d, digits=1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def compute(subsets: Subsets, config: dict, warn) -> dict:
    elig = subsets.eligible
    waves = _wave_months(subsets.total)
    if not waves:
        warn("no Resp columns; mailer section skipped")
        return {}
    if "# of Responses" not in elig.columns:
        warn("frame is not enriched; mailer section skipped")
        return {}

    out: dict = {}

    # ---- per-wave rates, and which waves are still in flight ----------
    # Counted over the WHOLE file, not the eligible view: an account that
    # responded and later closed or lost eligibility still responded, and
    # the ARS Workbook counts it. Eligible-only counting is what made the
    # ODD's May26 read 502 against the workbook's 639 (issue #17).
    total_frame = subsets.total
    campaigns, in_flight, completed = [], [], []
    tiers_by_wave: dict[str, dict] = {}
    for m in waves:
        mailed = _mailed(total_frame, m)
        responded = _responded(total_frame, m)
        n_mailed = int(mailed.sum())
        if not n_mailed:
            continue
        n_resp = int((mailed & responded).sum())
        if n_resp == 0:
            in_flight.append(m.tag)
            continue
        completed.append(m)
        campaigns.append([m.tag, n_mailed, n_resp, _pct(n_resp, n_mailed)])
        resp_col = f"{m.tag} Resp"
        if resp_col in total_frame.columns:
            vals = total_frame.loc[(mailed & responded).to_numpy(), resp_col]
            counts: dict[str, int] = {}
            for v, cnt in vals.astype(str).str.strip().value_counts().items():
                digits = "".join(ch for ch in str(v) if ch.isdigit())
                key = "NU5" if str(v).upper().startswith("NU") \
                    else (f"TH{digits}" if digits else None)
                if key:
                    counts[key] = counts.get(key, 0) + int(cnt)
            if counts:
                tiers_by_wave[m.tag] = counts

    if not completed:
        warn("no mailing has recorded responses; mailer section skipped")
        return {}

    out["campaign_rates"] = campaigns
    # response EVENTS across completed offers -- the workbook's definition
    # (an account responding to two offers counts twice). The hero leads
    # with this; unique accounts live on the reach slide.
    out["responses_total"] = int(sum(c[2] for c in campaigns))
    out["campaign_base"] = "all mailed accounts (whole file, incl. closed)"
    if tiers_by_wave:
        out["campaign_tiers"] = tiers_by_wave
    out["in_flight_mailings"] = in_flight
    if in_flight:
        warn(f"mailing(s) {', '.join(in_flight)} sent with no responses recorded "
             f"yet; excluded from response rates")

    # The hero rail quotes the SAME row the per-mailer table shows -- the
    # whole-file counts. Recomputing these on the eligible view is what put
    # 12.4% (502/4,064) on the hero beside the table's 11.4% (639/5,595)
    # for the same 1585 May26 wave (James, issue #17).
    latest = completed[-1]
    out["latest_mailing"] = latest.tag
    _, out["latest_mailed"], out["latest_responders"], out["latest_resprate"] = \
        campaigns[-1]

    rates = [c[3] for c in campaigns]
    out["resprate_mean"] = round(float(np.mean(rates)), 1)
    out["resprate_best"] = max(campaigns, key=lambda c: c[3])[:1] + \
        [max(rates)]
    out["resprate_worst"] = min(campaigns, key=lambda c: c[3])[:1] + \
        [min(rates)]
    if len(rates) >= 3:
        slope = float(np.polyfit(np.arange(len(rates)), np.array(rates), 1)[0])
        out["resprate_slope_pp_per_wave"] = round(slope, 2)

    # ---- A15.1: reach ---------------------------------------------------
    responders = subsets.responders
    ever_mailed = elig["# of Offers"] > 0
    out["reach_total"] = len(responders)
    out["reach"] = _pct(len(responders), len(elig))
    out["reach_base"] = "Eligible"
    out["reach_total_unit"] = "unique accounts"
    # responses_total counts EVENTS across the whole file; reach_total counts
    # ACCOUNTS among the eligible. Two drops at once, and no slide separated
    # them. The whole-file account count is the missing rung: events ->
    # accounts is responses_total -> this, and whole file -> eligible is this
    # -> reach_total.
    whole = pd.to_numeric(subsets.total.get("# of Responses"), errors="coerce")
    if whole is not None:
        out["reach_total_whole_file"] = int((whole > 0).sum())
        out["reach_total_whole_file_unit"] = "unique accounts, whole file"
        dropped = out["reach_total_whole_file"] - len(responders)
        if dropped > 0:
            out["reach_ineligible_responders"] = dropped
            warn(f"{dropped:,} account(s) responded but are not currently "
                 f"eligible, so they count in responses_total and in no "
                 f"reach, depth or age figure. Eligibility is read as of "
                 f"today; the response already happened.")
    out["reach_of_mailed"] = _pct(len(responders), int(ever_mailed.sum()))
    out["n_ever_mailed"] = int(ever_mailed.sum())
    out["reach_perml"] = round(len(responders) / max(1, len(completed)), 1)

    # cumulative reach: unique responders as waves accumulate
    seen = pd.Series(False, index=elig.index)
    cumulative = []
    for m in completed:
        seen = seen | (_mailed(elig, m) & _responded(elig, m))
        cumulative.append([m.tag, int(seen.sum()), _pct(int(seen.sum()), len(elig))])
    # Responders the wave loop cannot attribute (first response rides an
    # in-flight or unlisted offer) fold into the FINAL point, so the line
    # ends exactly at reach_total -- one concept, one number. 1776 had 5
    # early responses against an in-flight wave and the consistency
    # fail-safe rightly blocked the deck (issue #45).
    stray = int(len(responders.index.difference(seen[seen].index)))
    if stray and cumulative:
        cumulative[-1][1] += stray
        cumulative[-1][2] = _pct(cumulative[-1][1], len(elig))
        out["reach_cum_unattributed_n"] = stray
        warn(f"{stray} responder(s) tie to an in-flight or unlisted offer; "
             f"folded into the final cumulative-reach point so the series "
             f"ends at the responder total")
    out["reach_cumulative"] = cumulative

    # ---- depth: how many times a responder responded --------------------
    responses = elig["# of Responses"]
    out["depth"] = [int((responses == 1).sum()), int((responses == 2).sum()),
                    int((responses >= 3).sum())]
    out["depth_repeat"] = out["depth"][1] + out["depth"][2]
    out["depth_repeat_pct"] = _pct(out["depth_repeat"], len(responders))
    if "Response Grouping" in elig.columns:
        out["response_grouping"] = elig["Response Grouping"].value_counts().to_dict()

    # Ladder movement, NU conversion and the penalty box are computed in
    # cohort.py from ladder.py, which holds the authoritative tier rules.

    # ---- A14.2: response by account age ---------------------------------
    opened = pd.to_datetime(elig.get("Date Opened"), errors="coerce")
    if opened is not None and opened.notna().any():
        anchor_ts = pd.Timestamp(subsets.anchor.year, subsets.anchor.month, 1) \
            + pd.offsets.MonthEnd(0)
        age_years = (anchor_ts - opened).dt.days / 365.2425
        rows = []
        for low, high, label in ACCOUNT_AGE_BANDS:
            mask = (age_years >= low) & (age_years < high) & ever_mailed
            n = int(mask.sum())
            r = int((mask & (responses > 0)).sum())
            rows.append([label, n, r, _pct(r, n)])
        out["response_account_age"] = rows

        # A responder with an unparseable Date Opened, an age before the
        # anchor, or an age past the last band appears in no row and in no
        # warning -- it simply leaves the slide. Say how many, and why.
        responded_mask = responses > 0
        placed = pd.Series(False, index=elig.index)
        for low, high, _lab in ACCOUNT_AGE_BANDS:
            placed |= (age_years >= low) & (age_years < high) & ever_mailed
        lost = int((responded_mask & ~placed).sum())
        if lost:
            undated = int((responded_mask & opened.isna()).sum())
            negative = int((responded_mask & (age_years < 0)).sum())
            never_mailed = int((responded_mask & ~ever_mailed).sum())
            top = ACCOUNT_AGE_BANDS[-1][1]
            beyond = int((responded_mask & (age_years >= top)).sum())
            out["response_account_age_unplaced"] = lost
            warn(f"response by account age: {lost:,} responder(s) land in no "
                 f"band and are absent from the slide -- {undated:,} with no "
                 f"parseable Date Opened, {negative:,} opened after the "
                 f"anchor, {beyond:,} older than {top:g}y, "
                 f"{never_mailed:,} with no recorded offer")

    # ---- responder profile vs non-responder -----------------------------
    non = subsets.non_responders
    profile: dict = {}
    balance = num_col(elig, "Curr Bal")
    if balance is not None and balance.notna().any():
        profile["balance_median"] = [
            round(float(balance.reindex(responders.index).median() or 0)),
            round(float(balance.reindex(non.index).median() or 0)),
        ]
    if "Account Holder Age" in elig.columns:
        age = pd.to_numeric(elig["Account Holder Age"], errors="coerce")
        profile["holder_age_median"] = [
            round(float(age.reindex(responders.index).median() or 0), 1),
            round(float(age.reindex(non.index).median() or 0), 1),
        ]
    if len(responders):
        profile["debit_pct"] = [
            _pct(int(has_debit(responders).sum()), len(responders)),
            _pct(int(has_debit(non).sum()), len(non)),
        ]
    spend_cols = columns_for(elig.columns, "Spend")
    if spend_cols:
        recent = spend_cols[-3:]
        profile["spend_per_mo"] = [
            round(float(responders[recent].sum(axis=1).mean() / len(recent))
                  if len(responders) else 0),
            round(float(non[recent].sum(axis=1).mean() / len(recent))
                  if len(non) else 0),
        ]
    if profile:
        profile["_columns"] = ["responders", "non-responders"]
        out["responder_profile"] = profile

    # ---- organic vs program activation ------------------------------------
    # Accounts whose FIRST swipe month falls in the last 12 months: had they
    # been mailed on or before that month (program) or never (organic)?
    swipe_cols = columns_for(elig.columns, "Swipes")
    if len(swipe_cols) >= 13:
        sw = elig[swipe_cols].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy()
        ever = sw.sum(axis=1) > 0
        first_idx = np.where(ever, (sw > 0).argmax(axis=1), -1)
        l12m_start = len(swipe_cols) - 12
        activated = ever & (first_idx >= l12m_start)
        swipe_months = [Month.from_tag(c.split()[0]) for c in swipe_cols]
        mail_before = np.zeros(len(elig), dtype=bool)
        for m in waves:
            mailed_m = _mailed(elig, m).to_numpy()
            # mailed at or before the first swipe month
            pos = np.array([sm <= m for sm in swipe_months])  # months <= wave
            cutoff = int(pos.sum())                             # count of months <= wave
            mail_before |= mailed_m & (first_idx >= cutoff - 1)
        # A new account's first swipe is onboarding, not activation. Split
        # by whether the account existed before the 12-month window.
        opened_dt = pd.to_datetime(elig.get("Date Opened"), errors="coerce")
        window_start = swipe_months[l12m_start]
        window_start_ts = pd.Timestamp(window_start.year, window_start.month, 1)
        existing = (opened_dt.isna() | (opened_dt < window_start_ts)).to_numpy() \
            if opened_dt is not None else np.ones(len(elig), dtype=bool)
        program = activated & mail_before
        organic = activated & ~mail_before
        out["activation_l12m_n"] = int(activated.sum())
        out["activation_new_account_n"] = int((activated & ~existing).sum())
        out["activation_existing_n"] = int((activated & existing).sum())
        out["activation_program_n"] = int((program & existing).sum())
        out["activation_organic_n"] = int((organic & existing).sum())
        out["activation_program_pct"] = _pct(out["activation_program_n"],
                                             out["activation_existing_n"])

    # ---- responder share of portfolio spend, L12M ----------------------------
    if "last 12-mon spend" in elig.columns:
        spend12 = pd.to_numeric(elig["last 12-mon spend"], errors="coerce").fillna(0)
        total_spend = float(spend12.sum())
        resp_spend = float(spend12.loc[responders.index].sum()) if len(responders) else 0.0
        out["responder_spend_share_pct"] = _pct(resp_spend, total_spend)
        out["responder_share_of_eligible_pct"] = _pct(len(responders), len(elig))

    # ---- A15.4: pre/post spend around each wave -------------------------
    if spend_cols:
        by_month = {Month.from_tag(c.split()[0]): c for c in spend_cols}
        ordered = sorted(by_month)
        entries = []
        for m in completed:
            if m not in by_month:
                continue
            i = ordered.index(m)
            before = [by_month[x] for x in ordered[max(0, i - 6):i]]
            after = [by_month[x] for x in ordered[i:i + 3]]
            if not before or not after:
                continue
            r = elig[_mailed(elig, m) & _responded(elig, m)]
            c = elig[_mailed(elig, m) & ~_responded(elig, m)]
            if not len(r):
                continue
            entries.append({
                "month": m.tag, "n": len(r),
                "resp_pre": round(float(r[before].sum(axis=1).mean() / len(before))),
                "resp_post": round(float(r[after].sum(axis=1).mean() / len(after))),
                "ctrl_pre": round(float(c[before].sum(axis=1).mean() / len(before))
                                  if len(c) else 0),
                "ctrl_post": round(float(c[after].sum(axis=1).mean() / len(after))
                                   if len(c) else 0),
            })
        if entries:
            out["before_after"] = entries
            out["ba_spend_before"] = round(float(np.mean([e["resp_pre"] for e in entries])))
            out["ba_spend_after"] = round(float(np.mean([e["resp_post"] for e in entries])))
            ctrl_pre = float(np.mean([e["ctrl_pre"] for e in entries]))
            ctrl_post = float(np.mean([e["ctrl_post"] for e in entries]))
            out["ba_control_before"] = round(ctrl_pre)
            out["ba_control_after"] = round(ctrl_post)
            resp_lift = out["ba_spend_after"] - out["ba_spend_before"]
            ctrl_lift = ctrl_post - ctrl_pre
            out["ba_lift_net"] = round(resp_lift - ctrl_lift)
            out["ba_lift_pct"] = _pct(resp_lift, out["ba_spend_before"])
    return out
