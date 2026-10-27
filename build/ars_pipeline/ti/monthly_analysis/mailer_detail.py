# Ported from ARS v5 02-Scripts/ars/monthly_analysis/mailer_detail.py at a491b5c (James Gilmore); logic unchanged.
"""Per-offer segment behavior: the 'combo lines' the client asked for.

For every completed offer, each mailed segment's average swipes and spend
per account, month by month around the mail month. The segment is the
ODD's own '{tag} Segmentation' -- the swipe category the account was IN
when the offer went out (Non-user, 1-5, ..., 41+), so the lines answer
'who moved after this specific mailing'.

Counted over the whole file (the campaign counting law): a mailed
account that later closed still belongs to its offer's story.
"""

from __future__ import annotations

import pandas as pd

from ..core.periods import Month
from .mailer import _mailed, _responded, _wave_months, challenge_segments

# months shown around the mail month: the FULL horizon, matching the
# pooled trajectory (-12..+36). The usable-months filter below clips each
# offer to the history the file actually has, so a young offer shows its
# +3 months and an old one its +36 -- measured history only (James,
# 2026-08-24: each individual mailing gets the long combo chart, not a
# fixed +-6 crop).
WINDOW_BEFORE = 12
WINDOW_AFTER = 36
MIN_SEGMENT_ACCOUNTS = 25
SEGMENT_ORDER = ["No card", "Non-user", "1-5", "6-10", "11-15",
                 "16-20", "21-25", "26-40", "41+"]


def _monthly_cols(df: pd.DataFrame, month: Month):
    swipes, spend = [], []
    for metric, bucket in (("Sig #", swipes), ("PIN #", swipes),
                           ("Sig $", spend), ("PIN $", spend)):
        col = f"{month.tag} {metric}"
        if col in df.columns:
            bucket.append(col)
    return swipes, spend


def compute(subsets, config: dict, warn) -> dict:
    frame = subsets.total
    waves = _wave_months(frame)
    out: dict = {}
    detail: dict = {}
    resp_detail: dict = {}

    for wave in waves:
        mailed = _mailed(frame, wave)
        if not int(mailed.sum()):
            continue
        if not _responded(frame, wave).any():
            continue                       # in flight -- nothing to show yet
        rows = frame.loc[mailed.to_numpy()]
        seg_col = f"{wave.tag} Segmentation"
        seg = (rows[seg_col].astype(str).str.strip()
               if seg_col in frame.columns else None)

        offsets = list(range(-WINDOW_BEFORE, WINDOW_AFTER + 1))
        months = [wave.shift(o) for o in offsets]
        usable = [(o, m) for o, m in zip(offsets, months)
                  if _monthly_cols(frame, m)[0]]
        if len(usable) < 4 or 0 not in [o for o, _m in usable]:
            # an offer mailed past the data month has no behavior to show
            continue

        segments = [] if seg is None else [
            s for s in SEGMENT_ORDER
            if int((seg == s).sum()) >= MIN_SEGMENT_ACCOUNTS]
        swipes_by_seg = {s: [] for s in segments}
        spend_by_seg = {s: [] for s in segments}
        for _o, m in usable:
            sw_cols, sp_cols = _monthly_cols(frame, m)
            sw = rows[sw_cols].apply(pd.to_numeric, errors="coerce") \
                .fillna(0).sum(axis=1)
            sp = rows[sp_cols].apply(pd.to_numeric, errors="coerce") \
                .fillna(0).sum(axis=1) if sp_cols else sw * 0
            for s in segments:
                mask = (seg == s).to_numpy()
                swipes_by_seg[s].append(round(float(sw[mask].mean()), 2))
                spend_by_seg[s].append(round(float(sp[mask].mean()), 2))

        if segments:
            detail[wave.tag] = {
                "offsets": [o for o, _m in usable],
                "segments": segments,
                "counts": {s: int((seg == s).sum()) for s in segments},
                "swipes": swipes_by_seg,
                "spend": spend_by_seg,
            }

        # the legacy per-mailer slide, CORRECTED to the legacy spec
        # (28_segment_combo_lines): per CHALLENGE SEGMENT, responders vs
        # that segment's own non-responders. Assignment priority (legacy
        # 22): responder -> its Resp tier; NU 1-4 (tried, missed) -> the
        # NU segment as non-responder; null Resp -> tier from the Mail
        # value when the file carries one.
        responded = _responded(frame, wave).loc[rows.index]
        seg_assign, tiers = challenge_segments(frame, rows.index, wave, config)

        seg_data = {}
        for tier in tiers:
            in_seg = seg_assign == tier
            r_mask = (in_seg & responded).to_numpy()
            n_mask = (in_seg & ~responded).to_numpy()
            if int(r_mask.sum()) < 10 or int(n_mask.sum()) < 10:
                continue
            sw_s = {"Responders": [], "Non-responders": []}
            sp_s = {"Responders": [], "Non-responders": []}
            for _o, mth in usable:
                sw_cols, sp_cols = _monthly_cols(frame, mth)
                sw = rows[sw_cols].apply(pd.to_numeric, errors="coerce") \
                    .fillna(0).sum(axis=1)
                sp = rows[sp_cols].apply(pd.to_numeric, errors="coerce") \
                    .fillna(0).sum(axis=1) if sp_cols else sw * 0
                for label, mask in (("Responders", r_mask),
                                    ("Non-responders", n_mask)):
                    sw_s[label].append(round(float(sw[mask].mean()), 2))
                    sp_s[label].append(round(float(sp[mask].mean()), 2))
            seg_data[tier] = {
                "counts": {"Responders": int(r_mask.sum()),
                           "Non-responders": int(n_mask.sum())},
                "swipes": sw_s, "spend": sp_s}
        if seg_data:
            resp_detail[wave.tag] = {
                "offsets": [o for o, _m in usable],
                "segments": list(seg_data),
                "data": seg_data}

    if resp_detail:
        out["mailer_resp_detail"] = resp_detail
    if detail:
        out["mailer_detail"] = detail
        out["mailer_detail_note"] = (
            "per mailed account, by the segment at mail time; whole file")
    return out
