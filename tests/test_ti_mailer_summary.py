# Ported from ARS v5 02-Scripts/tests/test_mailer_summary.py at a491b5c (James Gilmore); logic unchanged.
"""The per-mailer pair James's legacy deck carried (issue #80).

Slide 1 is the mailer summary; slide 2 is responders versus their own
challenge segment. These tests pin the metric layer behind both.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import ti_v5_harness as harness  # noqa: E402  (RPE: v5's harness pieces, tests/ti_v5_harness.py)
from ti.core.odd_transform import transform_odd  # noqa: E402
from ti_v5_harness import compute  # noqa: E402  (RPE: stands in for v5's metrics.compute)


def _metrics(anchor="Jul26", drop_segmentation=False, blank_resp=0.0):
    """`blank_resp` reproduces the real 1615 shape: an account is mailed
    (Mail == "M") but carries no Resp value at all, so it cannot be placed
    in a challenge tier."""
    raw = harness.make_odd(anchor)
    if drop_segmentation:
        raw = raw.drop(columns=[c for c in raw.columns
                                if c.endswith(" Segmentation")])
    if blank_resp:
        import numpy as np
        rng = np.random.default_rng(11)
        for col in [c for c in raw.columns if c.endswith(" Resp")]:
            wipe = (rng.random(len(raw)) < blank_resp) & raw[col].notna()
            raw.loc[wipe, col] = None
    enriched, _ = transform_odd(raw)
    m, _w = compute(enriched, harness.CONFIG)
    return m


@__import__("pytest").mark.skip(reason="reads mailer_detail's figures: switches on with G9-03")
def test_responder_grid_survives_without_swipe_segmentation():
    """The challenge-tier grid must not be gated on the swipe-category
    segmentation it never uses.

    On 1615 the ODD carries no '{tag} Segmentation' column, so every wave
    bailed out before the responder work ran and the whole offer chapter
    silently vanished -- James saw only the pooled aggregate.
    """
    m = _metrics(drop_segmentation=True)
    assert m.get("mailer_resp_detail"), (
        "responder-vs-segment detail disappeared when the swipe-category "
        "segmentation was absent")


def test_summary_exists_for_every_completed_wave_and_ties_out():
    """Slide 1's headline trio: mailed, responded, rate -- and the per-tier
    rows must add back up to it, the way James's Apr26 slide does
    (5 tiers summing to 2,093 responders on 18,735 mailed)."""
    m = _metrics()
    summary = m["mailer_summary"]
    assert summary, "no mailer summary produced"
    for tag, s in summary.items():
        assert s["responded"] > 0, tag
        assert s["mailed"] >= s["responded"], tag
        assert abs(s["rate"] - round(100 * s["responded"] / s["mailed"], 1)) < 0.05
        by_tier = s["by_tier"]
        assert by_tier, tag
        assert sum(t["responded"] for t in by_tier.values()) == s["responded"], tag
        # tier rows reconcile to the PLACEABLE part of the wave, and that
        # part plus the unplaceable remainder is the whole wave
        assert sum(t["mailed"] for t in by_tier.values()) == s["mailed_assigned"], tag
        assert s["mailed_assigned"] + s["mailed_unassigned"] == s["mailed"], tag
        assert abs(sum(t["share"] for t in by_tier.values()) - 100) < 0.6, tag


def test_summary_carries_the_five_inside_the_numbers_stats():
    """The fixed five (James, 2026-08-24: 'it can be fixed'). Each is a
    percentage, and each reports the denominator it was taken over so the
    slide never prints a rate off a handful of accounts."""
    m = _metrics()
    for tag, s in m["mailer_summary"].items():
        inside = s["inside"]
        for key in ("new_account_pct", "age_60_plus_pct", "rege_optin_pct",
                    "first_time_pct", "moved_up_pct"):
            assert key in inside, f"{tag} missing {key}"
            value = inside[key]
            assert value is None or 0 <= value <= 100, f"{tag} {key}={value}"
        assert inside["first_time_n"] + inside["repeat_n"] == s["responded"], tag
        # the ladder stat is taken over REPEAT responders, not all of them
        assert inside["moved_up_denominator"] == inside["repeat_n"], tag


def test_first_wave_responders_are_all_first_time():
    """Nobody can be a repeat responder in the earliest wave in the file."""
    m = _metrics()
    first_tag = list(m["mailer_summary"])[0]
    inside = m["mailer_summary"][first_tag]["inside"]
    assert inside["repeat_n"] == 0, first_tag
    assert inside["first_time_pct"] == 100.0, first_tag
    assert inside["moved_up_pct"] is None, "no repeat responders to rate"


def test_summary_mailed_agrees_with_the_campaign_table():
    """James caught this by eye: the summary slide said 10k mailed while an
    earlier slide said 17k for the same wave.

    The summary was reporting only the accounts it could place in a
    challenge tier. Two slides in one deck must not disagree about how many
    people were mailed -- the headline is the WHOLE wave, and the tier rows
    account for the part that could be placed.
    """
    m = _metrics(blank_resp=0.45)
    campaign = {row[0]: (row[1], row[2], row[3]) for row in m["campaign_rates"]}
    for tag, s in m["mailer_summary"].items():
        assert tag in campaign, tag
        mailed, responded, rate = campaign[tag]
        assert s["mailed"] == mailed, (
            f"{tag}: summary says {s['mailed']:,} mailed, the campaign table "
            f"says {mailed:,}")
        assert s["responded"] == responded, tag
        assert abs(s["rate"] - rate) < 0.05, tag
        # and the tier rows must still reconcile to the whole
        assert (s["mailed_assigned"] + s["mailed_unassigned"]) == s["mailed"], tag
        assert sum(t["mailed"] for t in s["by_tier"].values()) == s["mailed_assigned"], tag


def _warnings(blank_resp=0.6):
    raw = harness.make_odd("Jul26")
    import numpy as np
    rng = np.random.default_rng(5)
    for col in [c for c in raw.columns if c.endswith(" Resp")]:
        wipe = (rng.random(len(raw)) < blank_resp) & raw[col].notna()
        raw.loc[wipe, col] = None
    enriched, _ = transform_odd(raw)
    _m, warns = compute(enriched, harness.CONFIG)
    return [w for w in warns if "challenge tier" in w and "mailer summary" in w]


def test_untiered_warning_does_not_report_a_cross_wave_sum_as_accounts():
    """1776 reported '52,999 mailed account(s) carry no challenge tier'.

    That figure was summed ACROSS waves, so an account mailed six times
    counted six times -- it read as a headcount and was not one. The
    warning must name a wave and a share, not a bare running total.
    """
    warns = _warnings()
    assert warns, "no untiered warning raised"
    text = warns[0]
    assert "%" in text, f"no share given: {text}"
    # a wave tag anchors the number to something the reader can check
    assert any(tag in text for tag in
               ("Aug25", "Oct25", "Dec25", "Feb26", "Apr26", "Jun26", "Aug26")), text


def test_untiered_warning_counts_distinct_accounts_not_account_waves():
    warns = _warnings()
    text = warns[0]
    import re
    numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", text)
               if n.strip(",")]
    # nothing quoted may exceed the size of the book itself
    assert max(numbers) <= 800, f"a figure exceeds the 800-account book: {text}"


def _offer_shaped(anchor="Jul26", seed=7):
    """The real ODD shape: the Mail column carries the OFFER segment, and
    Resp is blank unless the account actually responded.

    Legacy `_helpers.MAILED_SEGMENTS` is ["NU", "TH-10", "TH-15", "TH-20",
    "TH-25"] against `RESPONSE_SEGMENTS` ["NU 5+", "TH-10", ...] -- the two
    columns do NOT share a vocabulary for the NU tier. The harness's own
    make_odd stamps a bare "M", so it cannot expose this.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    raw = harness.make_odd(anchor)
    offers = ["NU", "TH-10", "TH-15", "TH-20", "TH-25"]
    responds_as = {"NU": "NU 5+", "TH-10": "TH-10", "TH-15": "TH-15",
                   "TH-20": "TH-20", "TH-25": "TH-25"}
    rate = {"NU": .032, "TH-10": .102, "TH-15": .205,
            "TH-20": .238, "TH-25": .296}
    for mail_col in [c for c in raw.columns if c.endswith(" Mail")]:
        tag = mail_col.split()[0]
        mailed = raw[mail_col].notna().to_numpy()
        offer = rng.choice(offers, len(raw), p=[.42, .29, .12, .09, .08])
        raw[mail_col] = np.where(mailed, offer, None)
        draw = rng.random(len(raw))
        responded = mailed & (draw < np.array([rate[o] for o in offer]))
        # NU offers tried but missed carry the tracked (non-response) value
        tried = mailed & ~responded & (offer == "NU") & (draw < .18)
        resp = np.where(responded, [responds_as[o] for o in offer], None)
        raw[f"{tag} Resp"] = np.where(tried, "NU 1-4", resp)
    enriched, _ = transform_odd(raw)
    m, _w = compute(enriched, harness.CONFIG)
    return enriched, m


def test_tier_rows_tie_to_the_offer_stamped_in_the_mail_column():
    """James (2026-08-26): the NU 5+ row said 1,177 mailed where the
    workbook said 7,893; every TH row was right.

    An offer is stamped "NU" in the Mail column but a response comes back
    "NU 5+", so matching the Mail value against the response vocabulary by
    exact string dropped every NU-mailed non-responder. TH-10..25 spell the
    same on both sides, which is why one row -- and only one -- was short.
    """
    enriched, m = _offer_shaped()
    for tag, s in m["mailer_summary"].items():
        mail_vals = enriched[f"{tag} Mail"].astype(str).str.strip()
        for tier, row in s["by_tier"].items():
            offer = "NU" if tier.upper().startswith("NU") else tier
            expected = int((mail_vals == offer).sum())
            assert row["mailed"] == expected, (
                f"{tag} {tier}: summary says {row['mailed']:,} mailed, the "
                f"Mail column stamps {expected:,}")


def test_an_offer_stamped_file_leaves_nobody_untiered():
    """Where the Mail column carries the offer, every mailed account is
    placeable -- the unassigned remainder exists for bare-'M' files."""
    _enriched, m = _offer_shaped()
    for tag, s in m["mailer_summary"].items():
        assert s["mailed_unassigned"] == 0, (
            f"{tag}: {s['mailed_unassigned']:,} of {s['mailed']:,} mailed "
            f"carry an offer but landed in no tier row")
        assert s["mailed_assigned"] == s["mailed"], tag
