# Ported from ARS v5 02-Scripts/ars/monthly_analysis/cohort.py at a491b5c (James Gilmore); logic unchanged.
"""Mailer cohort analysis: what a response is actually worth.

Every account-wave pair is placed in a cohort and its spend measured at
offsets relative to that wave's mail month, so waves from different calendar
months stack on a common axis. That alignment is the whole point: without it,
a Dec mailer and a Jun mailer average into noise.

Three cohorts per wave:

    responders          mailed, responded
    mailed non-resp     mailed, did not respond   <- the tight control
    not mailed          eligible, not in this wave <- the loose control

The mailed non-responder is the control that matters. Both groups were
selected by the same targeting rule and both received the same offer, so the
difference between them is the response, not the selection.

PROGRAM RULE (penalty box): after responding at a tier, the account must move
up or down the ladder to respond again. The same tier cannot repeat until 3
mailers (6 months) have passed. Same-tier repeats inside that window are
validated and reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for
from ..core.subsets import Subsets, norm

# Offsets from the mail month. 0 is the mail month itself. The lookback runs
# well past the selection window so the account's true normal is visible.
# -12 before to +36 after (James, #62: 'my lines' -- covered offsets
# still follow the data, so a young book simply shows less tail)
TRAJECTORY_OFFSETS = list(range(-12, 37))
HORIZONS = (1, 3, 6, 12)
PENALTY_BOX_WAVES = 3          # 3 mailers = 6 months

# TWO baselines, for two different jobs.
#
# PROGRAM_BASELINE is how the mailer itself works: the offer is sized from
# the trailing 3-month swipe average. Mail in Apr26 -> Jan26..Mar26.
#
# MEASUREMENT_BASELINE is what lift must be measured against. Accounts are
# SELECTED because the trailing 3 months dipped, so comparing post-mail spend
# to that window measures regression to the mean, not the mailer. Stepping
# back past the selection window recovers the account's own normal.
PROGRAM_BASELINE = [-3, -2, -1]
MEASUREMENT_BASELINE = list(range(-12, -3))      # -12 .. -4

from .ladder import (build_history, group as tier_group, is_response,
                     ladder_movement, nu_conversion, penalty_box)


@dataclass
class Accumulator:
    """Sum and count per offset, pooled across waves."""

    total: dict[int, float] = field(default_factory=dict)
    n: dict[int, int] = field(default_factory=dict)

    def add(self, offset: int, values: pd.Series) -> None:
        if not len(values):
            return
        self.total[offset] = self.total.get(offset, 0.0) + float(values.sum())
        self.n[offset] = self.n.get(offset, 0) + len(values)

    def mean(self, offset: int) -> float | None:
        count = self.n.get(offset, 0)
        return round(self.total[offset] / count, 2) if count else None

    def window_mean(self, offsets) -> float | None:
        """Average monthly spend across a set of offsets."""
        totals = sum(self.total.get(o, 0.0) for o in offsets if o in self.n)
        counts = sum(self.n.get(o, 0) for o in offsets if o in self.n)
        return round(totals / counts, 2) if counts else None


def _metric_columns(df: pd.DataFrame, suffix: str) -> dict[Month, str]:
    return {Month.from_tag(c.split()[0]): c
            for c in columns_for(df.columns, suffix)}


def compute(subsets: Subsets, config: dict, warn) -> dict:
    elig = subsets.eligible
    resp_cols = columns_for(subsets.total.columns, "Resp")
    if not resp_cols:
        return {}

    spend_by_month = _metric_columns(elig, "Spend")
    swipe_by_month = _metric_columns(elig, "Swipes")
    if not spend_by_month:
        warn("no monthly Spend columns; cohort analysis skipped")
        return {}

    waves = [Month.from_tag(c.split()[0]) for c in resp_cols]

    def mailed(m: Month) -> pd.Series:
        col = f"{m.tag} Mail"
        if col not in elig.columns:
            return pd.Series(False, index=elig.index)
        return elig[col].notna() & (norm(elig[col]) != "")

    def responded(m: Month) -> pd.Series:
        col = f"{m.tag} Resp"
        if col not in elig.columns:
            return pd.Series(False, index=elig.index)
        return elig[col].map(is_response)

    # Only waves with recorded responses -- a mailer that dropped last week
    # has no outcome yet and would drag every average toward zero.
    live = [m for m in waves if int((mailed(m) & responded(m)).sum()) > 0]
    if not live:
        warn("no mailing has recorded responses; cohort analysis skipped")
        return {}

    out: dict = {"cohort_waves": [m.tag for m in live]}

    # ---- pooled trajectories -------------------------------------------
    cohorts = {
        "responders": Accumulator(),
        "mailed_nonresp": Accumulator(),
        "not_mailed": Accumulator(),
    }
    swipes = {k: Accumulator() for k in cohorts}
    per_wave_n: dict[str, int] = {k: 0 for k in cohorts}
    # per-tier responder trajectories (James, #62): spend and swipes per
    # segment around the mail, against the pooled control
    tier_spend: dict[str, Accumulator] = {}
    tier_swipes: dict[str, Accumulator] = {}
    tier_pairs: dict[str, int] = {}
    # legacy combo-line grouping: the ODD's {tag} Segmentation bands,
    # ALL MAILED accounts pooled per band (James: 'remember legacy
    # combo line')
    seg_spend: dict[str, Accumulator] = {}
    seg_swipes: dict[str, Accumulator] = {}
    seg_pairs: dict[str, int] = {}

    for wave in live:
        m_mask = mailed(wave)
        r_mask = m_mask & responded(wave)
        n_mask = m_mask & ~r_mask
        u_mask = ~m_mask
        tcol_w = f"{wave.tag} Resp"
        wave_tiers = (elig[tcol_w].astype(str).str.strip()
                      if tcol_w in elig.columns else None)
        if wave_tiers is not None:
            for t, cnt in wave_tiers[r_mask].value_counts().items():
                tier_pairs[str(t)] = tier_pairs.get(str(t), 0) + int(cnt)
        scol_w = f"{wave.tag} Segmentation"
        wave_segs = (elig[scol_w].astype(str).str.strip()
                     if scol_w in elig.columns else None)
        if wave_segs is not None:
            for g, cnt in wave_segs[m_mask].value_counts().items():
                if str(g) and str(g) != "nan":
                    seg_pairs[str(g)] = seg_pairs.get(str(g), 0) + int(cnt)

        per_wave_n["responders"] += int(r_mask.sum())
        per_wave_n["mailed_nonresp"] += int(n_mask.sum())
        per_wave_n["not_mailed"] += int(u_mask.sum())

        for offset in TRAJECTORY_OFFSETS:
            month = wave.shift(offset)
            col = spend_by_month.get(month)
            if col is None:
                continue
            values = elig[col]
            cohorts["responders"].add(offset, values[r_mask])
            cohorts["mailed_nonresp"].add(offset, values[n_mask])
            cohorts["not_mailed"].add(offset, values[u_mask])

            scol = swipe_by_month.get(month)
            if scol is not None:
                sv = elig[scol]
                swipes["responders"].add(offset, sv[r_mask])
                swipes["mailed_nonresp"].add(offset, sv[n_mask])
                swipes["not_mailed"].add(offset, sv[u_mask])
            if wave_tiers is not None:
                for t in wave_tiers[r_mask].unique():
                    t_mask = r_mask & (wave_tiers == t)
                    tier_spend.setdefault(str(t), Accumulator()).add(
                        offset, values[t_mask])
                    if scol is not None:
                        tier_swipes.setdefault(str(t), Accumulator()).add(
                            offset, elig[scol][t_mask])
            if wave_segs is not None:
                for g in wave_segs[m_mask].unique():
                    g_s = str(g)
                    if not g_s or g_s == "nan":
                        continue
                    g_mask = m_mask & (wave_segs == g)
                    seg_spend.setdefault(g_s, Accumulator()).add(
                        offset, values[g_mask])
                    if scol is not None:
                        seg_swipes.setdefault(g_s, Accumulator()).add(
                            offset, elig[scol][g_mask])

    covered = [o for o in TRAJECTORY_OFFSETS
               if cohorts["responders"].n.get(o, 0) > 0]
    out["cohort_offsets"] = covered
    out["cohort_n"] = per_wave_n

    out["cohort_spend"] = {
        name: [acc.mean(o) for o in covered] for name, acc in cohorts.items()
    }
    out["cohort_swipes"] = {
        name: [acc.mean(o) for o in covered] for name, acc in swipes.items()
    }
    if tier_spend:
        out["cohort_spend_by_tier"] = {
            t: [acc.mean(o) for o in covered]
            for t, acc in tier_spend.items()}
        out["cohort_swipes_by_tier"] = {
            t: [acc.mean(o) for o in covered]
            for t, acc in tier_swipes.items()}
        out["cohort_tier_n"] = tier_pairs
    if seg_spend:
        seg_order = ["No card", "Non-user", "1-5", "6-10", "11-15",
                     "16-20", "21-25", "26-40", "41+"]
        segments = sorted(seg_spend,
                          key=lambda s: (seg_order.index(s)
                                         if s in seg_order else 99, s))
        out["cohort_seg_detail"] = {
            "offsets": covered,
            "segments": segments,
            "spend": {s: [seg_spend[s].mean(o) for o in covered]
                      for s in segments},
            "swipes": {s: [seg_swipes[s].mean(o) for o in covered]
                       if s in seg_swipes else [None] * len(covered)
                       for s in segments},
            "counts": seg_pairs,
        }

    # ---- indexed to the pre-mail baseline -------------------------------
    # Each cohort indexed to its OWN pre-period average, so groups that
    # started at different spend levels are still comparable. Index 100 is
    # that cohort's own baseline; divergence after month 0 is the effect.
    program_window = [o for o in PROGRAM_BASELINE if o in covered]
    measure_window = [o for o in MEASUREMENT_BASELINE if o in covered]
    if not measure_window:
        measure_window = [o for o in covered if o < 0]
        warn("not enough history for a pre-selection baseline; lift is measured "
             "against the selection window and will overstate the effect")
    pre = measure_window

    out["baseline_windows"] = {
        "program": program_window,
        "measurement": measure_window,
    }
    baselines = {name: acc.window_mean(measure_window)
                 for name, acc in cohorts.items()}
    program_baselines = {name: acc.window_mean(program_window)
                         for name, acc in cohorts.items()}
    out["cohort_baseline"] = baselines
    out["cohort_baseline_program"] = program_baselines

    # How far the selection window sits below the account's true normal.
    # This is the size of the regression-to-the-mean effect that any lift
    # measured against the selection window would silently absorb.
    r_true = baselines.get("responders")
    r_sel = program_baselines.get("responders")
    if r_true and r_sel:
        out["selection_dip_abs"] = round(r_sel - r_true, 2)
        out["selection_dip_pct"] = round(100 * (r_sel - r_true) / r_true, 1)
        if r_sel < r_true * 0.9:
            warn(
                f"responders were selected on a dip: their trailing-3 spend "
                f"(${r_sel:,.0f}) sits {abs(out['selection_dip_pct'])}% below "
                f"their 12-month normal (${r_true:,.0f}). Lift is measured "
                f"against the 12-month normal, not the selection window."
            )
    out["cohort_indexed"] = {}
    for name, acc in cohorts.items():
        base = baselines.get(name)
        if not base:
            continue
        out["cohort_indexed"][name] = [
            round(100 * acc.mean(o) / base, 1) if acc.mean(o) is not None else None
            for o in covered
        ]

    # ---- lift at each horizon -------------------------------------------
    lift_rows = []
    for horizon in HORIZONS:
        window = [o for o in range(1, horizon + 1) if o in covered]
        if not window:
            continue
        r = cohorts["responders"].window_mean(window)
        n = cohorts["mailed_nonresp"].window_mean(window)
        u = cohorts["not_mailed"].window_mean(window)
        r_pre = cohorts["responders"].window_mean(pre)
        n_pre = cohorts["mailed_nonresp"].window_mean(pre)

        # Difference-in-differences: the responder change minus the control
        # change, so a market-wide move does not read as a mailer effect.
        did = None
        if None not in (r, n, r_pre, n_pre):
            did = round((r - r_pre) - (n - n_pre), 2)

        lift_rows.append({
            "horizon_months": horizon,
            "months_covered": len(window),
            "responders": r,
            "mailed_nonresp": n,
            "not_mailed": u,
            "vs_nonresp_abs": round(r - n, 2) if None not in (r, n) else None,
            "vs_nonresp_pct": round(100 * (r - n) / n, 1)
            if n else None,
            "vs_notmailed_abs": round(r - u, 2) if None not in (r, u) else None,
            "vs_notmailed_pct": round(100 * (r - u) / u, 1) if u else None,
            "diff_in_diff": did,
        })
    out["cohort_lift"] = lift_rows

    # ---- per-tier cohorts ------------------------------------------------
    tiers_seen: set[str] = set()
    for wave in live:
        col = f"{wave.tag} Resp"
        if col in elig.columns:
            m_mask = mailed(wave) & responded(wave)
            tiers_seen.update(v for v in norm(elig[col][m_mask]).unique() if v)

    tier_rows = []
    for tier in sorted(tiers_seen):
        acc = Accumulator()
        count = 0
        for wave in live:
            col = f"{wave.tag} Resp"
            if col not in elig.columns:
                continue
            mask = mailed(wave) & responded(wave) & (norm(elig[col]) == tier)
            if not mask.any():
                continue
            count += int(mask.sum())
            for offset in TRAJECTORY_OFFSETS:
                scol = spend_by_month.get(wave.shift(offset))
                if scol is not None:
                    acc.add(offset, elig[scol][mask])
        if not count:
            continue
        base = acc.window_mean(pre)
        row = {
            "tier": tier,
            "group": tier_group(tier),
            "n": count,
            "pre_spend": base,
        }
        for horizon in HORIZONS:
            window = [o for o in range(1, horizon + 1) if o in acc.n]
            value = acc.window_mean(window) if window else None
            row[f"post_{horizon}"] = value
            row[f"lift_{horizon}_pct"] = (
                round(100 * (value - base) / base, 1)
                if value is not None and base else None)
        tier_rows.append(row)
    tier_rows.sort(key=lambda r: -r["n"])
    out["cohort_by_tier"] = tier_rows

    # ---- segment cohorts: wave x offer segment x responder status --------
    # Feeds the per-wave trajectory panels (spend on one row, swipes on the
    # other, one column per segment, responder vs non-responder in each).
    #
    # Non-responders carry a segment too, so the segment cannot come from the
    # Resp value -- it comes from the OFFER. Detect whether the Mail column
    # holds a tier; if it is only a presence flag, fall back to the response
    # tier for responders and a single pooled segment for non-responders.
    mail_values: set[str] = set()
    for wave in live:
        col = f"{wave.tag} Mail"
        if col in elig.columns:
            mail_values.update(v for v in norm(elig[col]).unique() if v)
    mail_carries_segment = len(mail_values) > 1
    out["segment_source"] = "Mail (offer tier)" if mail_carries_segment else "Resp tier"
    out["segment_values_seen"] = sorted(mail_values)[:12]

    def segment_of(wave: Month) -> pd.Series:
        if mail_carries_segment:
            col = f"{wave.tag} Mail"
            return norm(elig[col]) if col in elig.columns else pd.Series(
                "", index=elig.index)
        col = f"{wave.tag} Resp"
        if col not in elig.columns:
            return pd.Series("", index=elig.index)
        values = norm(elig[col])
        return values.where(values != "", "Mailed")

    segment_rows = []
    for wave in live:
        m_mask = mailed(wave)
        if not m_mask.any():
            continue
        seg = segment_of(wave)
        r_mask = m_mask & responded(wave)

        for segment in sorted(v for v in seg[m_mask].unique() if v):
            in_segment = m_mask & (seg == segment)
            for status, mask in (("Responder", in_segment & r_mask),
                                 ("Non-Responder", in_segment & ~r_mask)):
                count = int(mask.sum())
                if count < 5:            # tiny cells make unstable lines
                    continue
                spend_track, swipe_track = {}, {}
                for offset in TRAJECTORY_OFFSETS:
                    month = wave.shift(offset)
                    scol = spend_by_month.get(month)
                    if scol is not None:
                        spend_track[offset] = round(
                            float(elig.loc[mask, scol].mean()), 2)
                    wcol = swipe_by_month.get(month)
                    if wcol is not None:
                        swipe_track[offset] = round(
                            float(elig.loc[mask, wcol].mean()), 2)
                segment_rows.append({
                    "wave": wave.tag,
                    "segment": segment,
                    "status": status,
                    "n": count,
                    "spend": spend_track,
                    "swipes": swipe_track,
                })
    out["segment_cohorts"] = segment_rows

    # Compact summary: per segment, pooled across waves, pre vs post lift for
    # each status and the difference between them.
    # Baseline must match the rest of the section: the account's own normal,
    # measured BEFORE the selection window, not the dip it was selected on.
    seg_pre_offsets = set(measure_window)
    seg_post_offsets = set(range(1, 7))
    summary = {}
    for row in segment_rows:
        key = (row["segment"], row["status"])
        bucket = summary.setdefault(key, {"n": 0, "pre": 0.0, "post": 0.0,
                                          "pre_n": 0, "post_n": 0})
        bucket["n"] += row["n"]
        for offset, value in row["spend"].items():
            if offset in seg_pre_offsets:
                bucket["pre"] += value * row["n"]
                bucket["pre_n"] += row["n"]
            elif offset in seg_post_offsets:
                bucket["post"] += value * row["n"]
                bucket["post_n"] += row["n"]

    seg_summary = []
    segments = sorted({k[0] for k in summary})
    for segment in segments:
        entry = {"segment": segment}
        for status in ("Responder", "Non-Responder"):
            bucket = summary.get((segment, status))
            if not bucket or not bucket["pre_n"] or not bucket["post_n"]:
                continue
            pre_avg = bucket["pre"] / bucket["pre_n"]
            post_avg = bucket["post"] / bucket["post_n"]
            key = "resp" if status == "Responder" else "non"
            entry[f"{key}_n"] = bucket["n"]
            entry[f"{key}_pre"] = round(pre_avg, 2)
            entry[f"{key}_post"] = round(post_avg, 2)
            entry[f"{key}_delta"] = round(post_avg - pre_avg, 2)
        # Response rate for the segment, and how much of the DiD comes from
        # the control declining rather than the responders rising.
        offered = entry.get("resp_n", 0) + entry.get("non_n", 0)
        if offered:
            entry["response_rate"] = round(100 * entry.get("resp_n", 0) / offered, 1)
            entry["offered_n"] = offered
        if "resp_delta" in entry and "non_delta" in entry:
            entry["did"] = round(entry["resp_delta"] - entry["non_delta"], 2)
            if entry["did"]:
                entry["did_from_control_pct"] = round(
                    100 * (-entry["non_delta"]) / entry["did"], 1)
        # Efficiency: what a response costs in mailings, and what the whole
        # segment returns per thousand pieces. Response value is flat across
        # tiers, so this is where the tiers actually differ.
        if entry.get("response_rate") and entry.get("did") is not None:
            entry["mailings_per_response"] = round(
                100 / entry["response_rate"], 1)
            # DiD is per responding account per month; scale to the segment.
            entry["did_per_1000_mailed"] = round(
                1000 * (entry["response_rate"] / 100) * entry["did"])
        seg_summary.append(entry)

    # Translate spend into what the institution actually earns.
    ic_raw = str(config.get("ICRate", "")).strip()
    ic_rate = None
    if ic_raw:
        try:
            ic_rate = float(ic_raw)
        except ValueError:
            warn(f"ICRate {ic_raw!r} is not numeric; revenue view skipped")
    if ic_rate:
        for entry in seg_summary:
            if entry.get("did_per_1000_mailed") is not None:
                entry["ic_per_1000_mailed"] = round(
                    entry["did_per_1000_mailed"] * ic_rate, 2)
            if entry.get("did") is not None:
                entry["ic_per_response_mo"] = round(entry["did"] * ic_rate, 2)
    out["segment_ic_rate"] = ic_rate
    out["segment_summary"] = seg_summary
    out["segment_pre_window"] = sorted(seg_pre_offsets)

    # A control that declines is a finding, not a footnote -- part of the
    # measured lift is the mailer arresting decay rather than creating spend.
    declining = [e for e in seg_summary if e.get("non_delta", 0) < 0]
    if declining and len(declining) == len(seg_summary):
        share = [e.get("did_from_control_pct", 0) for e in seg_summary
                 if e.get("did_from_control_pct") is not None]
        if share:
            warn(
                f"non-responders declined in every segment; "
                f"{min(share):.0f}-{max(share):.0f}% of each DiD figure comes "
                f"from the control falling rather than responders rising. "
                f"Report it as decline arrested, not spend created."
            )

    # ---- transaction increase over the ask -------------------------------
    # The challenge asks for N more swipes. This is the distribution of what
    # responders actually delivered above their own prior run rate, which is
    # what the "over the ask" slide reports.
    swipe_by_month = _metric_columns(elig, "Swipes")
    pairs = []
    for wave in live:
        mask = mailed(wave) & responded(wave)
        if not mask.any():
            continue
        post_col = swipe_by_month.get(wave.shift(1)) or swipe_by_month.get(wave)
        pre_cols = [swipe_by_month[wave.shift(o)] for o in measure_window
                    if wave.shift(o) in swipe_by_month]
        if post_col is None or not pre_cols:
            continue
        baseline = elig.loc[mask, pre_cols].mean(axis=1)
        post = pd.to_numeric(elig.loc[mask, post_col], errors="coerce").fillna(0)
        d = (post - baseline).dropna()
        tcol = f"{wave.tag} Resp"
        tiers = (elig.loc[mask, tcol].astype(str).str.strip()
                 .reindex(d.index).fillna("?")
                 if tcol in elig.columns
                 else pd.Series("?", index=d.index))
        pairs.append(pd.DataFrame({"d": d.to_numpy(),
                                   "tier": tiers.to_numpy()}))

    # ---- swipe-high beats (#39) ----------------------------------------
    # Did the responder EXCEED their own previous personal high after the
    # mail? Prior high = the highest monthly swipe count across ALL months
    # BEFORE the mail month (the full history, not the selection window);
    # a beat is any post-mail month STRICTLY above it. Equalling the high
    # is not a beat. Measured history only, no prediction.
    swipe_months = sorted(mo for mo in swipe_by_month)
    beat_frames = []
    for wave in live:
        mask = mailed(wave) & responded(wave)
        if not mask.any():
            continue
        pre_cols_all = [swipe_by_month[mo] for mo in swipe_months
                        if mo < wave]
        post_cols_all = [swipe_by_month[mo] for mo in swipe_months
                         if mo > wave]
        if not pre_cols_all or not post_cols_all:
            continue
        pre_v = elig.loc[mask, pre_cols_all].apply(
            pd.to_numeric, errors="coerce")
        post_v = elig.loc[mask, post_cols_all].apply(
            pd.to_numeric, errors="coerce")
        # a pair is measurable only when both sides have at least one
        # observed month -- an account with no history has no high to beat
        ok = pre_v.notna().any(axis=1) & post_v.notna().any(axis=1)
        if not ok.any():
            continue
        beat = post_v.max(axis=1) > pre_v.max(axis=1)
        tcol = f"{wave.tag} Resp"
        tiers_b = (elig.loc[mask, tcol].astype(str).str.strip()
                   if tcol in elig.columns
                   else pd.Series("?", index=elig.index[mask]))
        beat_frames.append(pd.DataFrame({"beat": beat[ok].to_numpy(),
                                         "tier": tiers_b[ok].to_numpy()}))
    beat_by_tier: dict[str, float] = {}
    if beat_frames:
        bdf = pd.concat(beat_frames, ignore_index=True)
        out["dot_beat_high_base"] = int(len(bdf))
        out["dot_beat_high_n"] = int(bdf["beat"].sum())
        out["dot_beat_high_pct"] = round(
            100 * out["dot_beat_high_n"] / out["dot_beat_high_base"], 1)
        beat_by_tier = {t: round(100 * float(g["beat"].mean()), 1)
                        for t, g in bdf.groupby("tier")}

    if pairs:
        df = pd.concat(pairs, ignore_index=True)
        df = df[np.isfinite(df["d"])]
        delta = df["d"]
        if len(delta):
            out["dot_n"] = int(len(delta))
            out["dot_mean"] = round(float(delta.mean()), 1)
            out["dot_std"] = round(float(delta.std()), 1)
            out["dot_median"] = round(float(delta.median()), 1)
            # the honest zero: responders BELOW their own baseline get
            # their own 'fell' bin (-1) instead of being clipped up into
            # the zero bar (James, #17: 'why would we have a big zero?')
            rounded = delta.round().astype(int)
            out["dot_fell_n"] = int((rounded < 0).sum())
            out["dot_hist"] = ([[-1, out["dot_fell_n"]]]
                               + [[k, int((rounded == k).sum())]
                                  for k in range(40)]
                               + [[40, int((rounded >= 40).sum())]])
            out["dot_tail40"] = int((delta >= 40).sum())
            out["dot_positive_pct"] = round(100 * float((delta > 0).mean()), 1)
            # who delivers the lift: the same distribution per response
            # tier (NU 5+ / TH-10..25) -- 'are non-users swiping forty
            # times, or the 25+?'
            seg_order = ["NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"]
            seg_rows = []
            for tier, g in df.groupby("tier"):
                seg_rows.append([str(tier), int(len(g)),
                                 round(float(g["d"].mean()), 1),
                                 round(float(g["d"].median()), 1),
                                 round(100 * float((g["d"] > 0).mean()), 1),
                                 int((g["d"] >= 40).sum()),
                                 beat_by_tier.get(str(tier))])
            seg_rows.sort(key=lambda r: seg_order.index(r[0])
                          if r[0] in seg_order else 99)
            out["dot_by_segment"] = seg_rows
            out["dot_by_segment_columns"] = [
                "tier", "pairs", "mean_lift", "median_lift",
                "pct_increased", "at_40_plus", "beat_high_pct"]

    # ---- sustained activity: months still above baseline ------------------
    sustained = []
    for offset in range(1, 13):
        vals, base = [], []
        for wave in live:
            mask = mailed(wave) & responded(wave)
            col = spend_by_month.get(wave.shift(offset))
            pre = [spend_by_month[wave.shift(o)] for o in measure_window
                   if wave.shift(o) in spend_by_month]
            if col is None or not pre or not mask.any():
                continue
            vals.append(float(elig.loc[mask, col].sum()))
            base.append(float(elig.loc[mask, pre].mean(axis=1).sum()))
        if vals and sum(base):
            sustained.append([offset, round(100 * sum(vals) / sum(base) - 100, 1)])
    if sustained:
        out["sustained_index"] = sustained
        above = [s for s in sustained if s[1] > 0]
        out["sustained_months_above"] = len(above)

    # ---- ladder, NU conversion, penalty box ------------------------------
    history = build_history(elig, waves, lambda w: f"{w.tag} Resp")
    tags = [w.tag for w in waves]

    out.update(ladder_movement(history, tags))
    out.update(nu_conversion(elig, waves, lambda w: f"{w.tag} Resp"))

    pb = penalty_box(history, tags)
    out.update(pb)
    if pb.get("penalty_box_violations"):
        warn(
            f"penalty box: {pb['penalty_box_violations']:,} responses repeated "
            f"the same tier within {pb['penalty_box_waves']} mailers "
            f"(6 months), which the program does not allow. By tier: "
            f"{pb['penalty_box_by_tier'][:4]}"
        )

    # ---- counterfactual: portfolio spend without the program --------------
    # Apply the non-responder change ratio to each responder's own pre-spend.
    # The gap between actual and that line is what responder activation held
    # onto -- a control-anchored figure, not a raw before/after.
    months = sorted(spend_by_month)
    if months and cohorts["mailed_nonresp"].window_mean(measure_window):
        nr_pre = cohorts["mailed_nonresp"].window_mean(measure_window)
        post = [o for o in covered if 1 <= o <= 6]
        nr_post = cohorts["mailed_nonresp"].window_mean(post) if post else None
        ratio = (nr_post / nr_pre) if (nr_pre and nr_post) else 1.0

        actual, counterfactual = [], []
        responded_by_month: dict[Month, pd.Series] = {}
        for wave in live:
            mask = mailed(wave) & responded(wave)
            pre_cols = [spend_by_month[wave.shift(o)] for o in measure_window
                        if wave.shift(o) in spend_by_month]
            if not pre_cols or not mask.any():
                continue
            baseline = elig[pre_cols].mean(axis=1)
            for month in months:
                offset = (month.year - wave.year) * 12 + (month.month - wave.month)
                if offset >= 1:
                    existing = responded_by_month.setdefault(
                        month, pd.Series(np.nan, index=elig.index))
                    existing[mask] = baseline[mask] * ratio

        for month in months:
            col = spend_by_month[month]
            values = pd.to_numeric(elig[col], errors="coerce").fillna(0)
            actual.append([month.tag, round(float(values.sum()))])
            replacement = responded_by_month.get(month)
            if replacement is None:
                counterfactual.append([month.tag, round(float(values.sum()))])
            else:
                cf = values.copy()
                usable = replacement.notna() & (replacement > 0)
                cf[usable] = replacement[usable]
                counterfactual.append([month.tag, round(float(cf.sum()))])

        out["counterfactual_actual"] = actual
        out["counterfactual_without"] = counterfactual
        out["counterfactual_ratio"] = round(ratio, 4)
        gap = actual[-1][1] - counterfactual[-1][1]
        out["counterfactual_gap_latest"] = gap
        out["counterfactual_gap_total"] = sum(
            a[1] - c[1] for a, c in zip(actual, counterfactual))

        # The gap is SPEND. The institution earns interchange on it -- report
        # both so the headline number cannot be mistaken for income.
        rate = out.get("segment_ic_rate")
        if rate:
            out["counterfactual_ic_latest"] = round(
                out["counterfactual_gap_latest"] * rate)
            out["counterfactual_ic_total"] = round(
                out["counterfactual_gap_total"] * rate)

    return out
