# Ported from ARS v5 02-Scripts/tests/test_swipe_high.py at a491b5c (James Gilmore); logic unchanged.
"""#39: the swipe-high beat rate.

James (slide-11 note, #28): "We should also measure previous swipe highs
and if we succeeded post-mail." For each responder x offer pair: the
account's highest monthly swipe count BEFORE the mail month is its prior
personal high; the pair "beats" it when ANY post-mail month strictly
exceeds that high. Measured history only, no prediction.

Surfaces under test:
- metrics: dot_beat_high_n / dot_beat_high_base / dot_beat_high_pct
- per tier: a beat_high_pct column appended to dot_by_segment
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import ti_v5_harness as harness                    # noqa: E402
from ti.core.odd_transform import transform_odd             # noqa: E402
from ti.core.periods import Month, columns_for              # noqa: E402
from ti.core.subsets import build_subsets                   # noqa: E402
from ti.monthly_analysis.ladder import is_response          # noqa: E402
from ti_v5_harness import compute             # noqa: E402


def _run(anchor="Jul26"):
    raw = harness.make_odd(anchor)
    enriched, _ = transform_odd(raw)
    m, _warns = compute(enriched, harness.CONFIG)
    return m, enriched


def _mirror_beat(enriched, config, anchor_tag):
    """The definition, computed independently of cohort.py: per live
    responder x wave pair, max(post months) > max(pre months)."""
    anchor = Month.from_tag(anchor_tag)
    subsets = build_subsets(enriched, config, anchor)
    elig = subsets.eligible
    swipe_cols = {Month.from_tag(c.split()[0]): c
                  for c in columns_for(elig.columns, "Swipes")}
    months = sorted(swipe_cols)
    beat = base = 0
    for rc in columns_for(elig.columns, "Resp"):
        wave = Month.from_tag(rc.split()[0])
        mail_col = f"{wave.tag} Mail"
        if mail_col not in elig.columns:
            continue
        m_mask = elig[mail_col].notna() & \
            (elig[mail_col].astype(str).str.strip() != "")
        r_mask = m_mask & elig[rc].map(is_response)
        if not int(r_mask.sum()):
            continue                      # not a live wave
        pre = [swipe_cols[mo] for mo in months if mo < wave]
        post = [swipe_cols[mo] for mo in months if mo > wave]
        if not pre or not post:
            continue
        pre_v = elig.loc[r_mask, pre].apply(pd.to_numeric, errors="coerce")
        post_v = elig.loc[r_mask, post].apply(pd.to_numeric, errors="coerce")
        ok = pre_v.notna().any(axis=1) & post_v.notna().any(axis=1)
        base += int(ok.sum())
        beat += int((post_v.max(axis=1) > pre_v.max(axis=1))[ok].sum())
    return beat, base


def test_beat_metric_exists_and_is_bounded():
    m, _ = _run()
    assert "dot_beat_high_pct" in m, "the #39 metric is not computed"
    n, base, pct = (m["dot_beat_high_n"], m["dot_beat_high_base"],
                    m["dot_beat_high_pct"])
    assert 0 < base, "synthetic book has responders; base cannot be zero"
    assert 0 <= n <= base
    assert pct == round(100 * n / base, 1)


def test_beat_rate_matches_the_plain_definition():
    m, enriched = _run()
    beat, base = _mirror_beat(enriched, harness.CONFIG, "Jul26")
    assert m["dot_beat_high_base"] == base
    assert m["dot_beat_high_n"] == beat


def test_segment_rows_carry_the_beat_column():
    m, _ = _run()
    cols = m["dot_by_segment_columns"]
    assert cols[-1] == "beat_high_pct"
    for row in m["dot_by_segment"]:
        assert len(row) == len(cols)
        v = row[-1]
        assert v is None or 0 <= v <= 100
    # at least one tier in the synthetic book has a measurable rate
    assert any(row[-1] is not None for row in m["dot_by_segment"])


def test_equalling_the_prior_high_is_not_a_beat():
    """Surgical three-account book, one Apr26 wave. A beats its high
    (9 > 8), B only EQUALS it (10 == 10, not a beat), C falls short.
    Strictly-greater is the rule: 1 of 3."""
    from ti.core.subsets import Subsets
    from ti.monthly_analysis import cohort

    months = [Month(2026, mo) for mo in range(1, 8)]      # Jan..Jul 26
    swipes = {                     # Jan Feb Mar | Apr | May Jun Jul
        "A": [5, 8, 6, 2, 9, 3, 1],
        "B": [10, 4, 7, 1, 10, 2, 6],
        "C": [10, 6, 9, 2, 4, 3, 1],
    }
    d = {"Acct ID": list(swipes)}
    for i, mo in enumerate(months):
        d[f"{mo.tag} Swipes"] = [swipes[a][i] for a in swipes]
        d[f"{mo.tag} Spend"] = [float(swipes[a][i]) * 10 for a in swipes]
    d["Apr26 Mail"] = ["M", "M", "M"]
    d["Apr26 Resp"] = ["TH-10", "TH-10", "TH-10"]
    frame = pd.DataFrame(d)

    subs = Subsets(total=frame, open_accounts=frame, eligible=frame,
                   eligible_personal=frame, eligible_business=frame.iloc[:0],
                   eligible_with_debit=frame, personal_with_debit=frame,
                   l12m_open=frame, l12m_eligible=frame, responders=frame,
                   non_responders=frame.iloc[:0], anchor=Month(2026, 7))
    m = cohort.compute(subs, dict(harness.CONFIG), lambda *_: None)
    assert m["dot_beat_high_base"] == 3
    assert m["dot_beat_high_n"] == 1
    assert m["dot_beat_high_pct"] == 33.3
    # and the single TH-10 segment row carries the same rate
    row = [r for r in m["dot_by_segment"] if r[0] == "TH-10"][0]
    assert row[-1] == 33.3


def test_trajectories_span_to_36_months_and_split_by_tier():
    """James (#62): 'my lines' -- spend and swipes up to 12 months before
    and up to 3 years after the mail, per segment, vs the control. The
    engine must carry offsets to +36 (data permitting) and emit per-tier
    responder series alongside the pooled control."""
    from ti.core.subsets import Subsets
    from ti.monthly_analysis import cohort

    assert cohort.TRAJECTORY_OFFSETS[0] == -12
    assert cohort.TRAJECTORY_OFFSETS[-1] == 36

    months = [Month(2026, mo) for mo in range(1, 8)]      # Jan..Jul 26
    swipes = {"A": [5, 8, 6, 2, 9, 3, 1], "B": [10, 4, 7, 1, 10, 2, 6],
              "C": [10, 6, 9, 2, 4, 3, 1], "D": [3, 3, 3, 3, 3, 3, 3]}
    tiers = {"A": "TH-10", "B": "TH-10", "C": "NU 5+", "D": None}
    d = {"Acct ID": list(swipes)}
    for i, mo in enumerate(months):
        d[f"{mo.tag} Swipes"] = [swipes[a][i] for a in swipes]
        d[f"{mo.tag} Spend"] = [float(swipes[a][i]) * 10 for a in swipes]
    d["Apr26 Mail"] = ["M", "M", "M", "M"]
    d["Apr26 Resp"] = ["TH-10", "TH-10", "NU 5+", None]   # D = control
    frame = pd.DataFrame(d)
    subs = Subsets(total=frame, open_accounts=frame, eligible=frame,
                   eligible_personal=frame, eligible_business=frame.iloc[:0],
                   eligible_with_debit=frame, personal_with_debit=frame,
                   l12m_open=frame, l12m_eligible=frame, responders=frame,
                   non_responders=frame.iloc[:0], anchor=Month(2026, 7))
    m = cohort.compute(subs, dict(harness.CONFIG), lambda *_: None)
    offs = m["cohort_offsets"]
    assert offs[0] == -3 and offs[-1] == 3        # covered follows the data
    spend_t = m["cohort_spend_by_tier"]
    swipe_t = m["cohort_swipes_by_tier"]
    assert set(spend_t) == {"TH-10", "NU 5+"}
    assert all(len(v) == len(offs) for v in spend_t.values())
    # TH-10 spend at offset +1 (May26): A=90, B=100 -> mean 95.0
    assert spend_t["TH-10"][offs.index(1)] == 95.0
    assert swipe_t["NU 5+"][offs.index(1)] == 4.0
    assert m["cohort_tier_n"]["TH-10"] == 2


def test_pooled_segmentation_combo_detail():
    """James: 'remember legacy combo line' -- the ODD's {tag} Segmentation
    bands, pooled across offers on the extended window, in the exact
    dict shape charts.combo_lines already consumes."""
    from ti.core.subsets import Subsets
    from ti.monthly_analysis import cohort

    months = [Month(2026, mo) for mo in range(1, 8)]
    swipes = {"A": [5, 8, 6, 2, 9, 3, 1], "B": [10, 4, 7, 1, 10, 2, 6],
              "C": [2, 1, 2, 0, 4, 3, 1]}
    d = {"Acct ID": list(swipes)}
    for i, mo in enumerate(months):
        d[f"{mo.tag} Swipes"] = [swipes[a][i] for a in swipes]
        d[f"{mo.tag} Spend"] = [float(swipes[a][i]) * 10 for a in swipes]
    d["Apr26 Mail"] = ["M", "M", "M"]
    d["Apr26 Resp"] = ["TH-10", "TH-10", None]        # C mailed, no resp
    d["Apr26 Segmentation"] = ["6-10", "6-10", "Non-user"]
    frame = pd.DataFrame(d)
    subs = Subsets(total=frame, open_accounts=frame, eligible=frame,
                   eligible_personal=frame, eligible_business=frame.iloc[:0],
                   eligible_with_debit=frame, personal_with_debit=frame,
                   l12m_open=frame, l12m_eligible=frame, responders=frame,
                   non_responders=frame.iloc[:0], anchor=Month(2026, 7))
    m = cohort.compute(subs, dict(harness.CONFIG), lambda *_: None)
    det = m["cohort_seg_detail"]
    offs = det["offsets"]
    assert offs == m["cohort_offsets"]
    assert set(det["segments"]) == {"6-10", "Non-user"}
    assert det["counts"]["6-10"] == 2 and det["counts"]["Non-user"] == 1
    # ALL MAILED accounts pool per segment (legacy behavior):
    # 6-10 spend at +1 (May26): A 90, B 100 -> 95.0
    assert det["spend"]["6-10"][offs.index(1)] == 95.0
    assert det["swipes"]["Non-user"][offs.index(1)] == 4.0
