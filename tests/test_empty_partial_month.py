"""A month just begun, with nothing in it, is not charted (Aaron, 2026-10-06).

The Austin Bank 2026.10 ICS Referral Trend and MRPC Enrollments by Month both drew Oct'26 (partial) as a
bar of 0 beside a full-height bar for every month before it, which reads as a collapse.
"""
import month_complete as MC


def trend(**kw):
    t = {"months": ["Aug 26", "Sep 26", "Oct 26"], "referrals": [351, 290, 0], "goal": [331, 331, 331],
         "partial_last": True}
    t.update(kw)
    return t


def test_an_empty_partial_month_is_dropped_from_every_parallel_list():
    t = trend()
    assert MC.drop_empty_partial_month(t, "referrals") == "Oct 26"
    assert t["months"] == ["Aug 26", "Sep 26"]
    assert t["referrals"] == [351, 290] and t["goal"] == [331, 331]
    assert t["partial_last"] is False, "the last remaining month is now a complete one"


def test_a_partial_month_with_any_activity_stays():
    t = trend(referrals=[351, 290, 3])
    assert MC.drop_empty_partial_month(t, "referrals") is None
    assert t["months"][-1] == "Oct 26" and t["partial_last"] is True


def test_a_complete_month_at_zero_stays():
    t = trend(partial_last=False)
    assert MC.drop_empty_partial_month(t, "referrals") is None
    assert t["referrals"] == [351, 290, 0]


def test_nothing_to_do_without_a_block_or_with_a_single_month():
    assert MC.drop_empty_partial_month(None, "referrals") is None
    assert MC.drop_empty_partial_month({}, "referrals") is None
    one = {"months": ["Oct 26"], "referrals": [0], "partial_last": True}
    assert MC.drop_empty_partial_month(one, "referrals") is None


def test_the_mrpc_enrollment_series_trims_the_same_way():
    e = {"months": ["Aug 26", "Sep 26", "Oct 26"], "partial_last": True, "totals": [290, 247, 0],
         "gold": [45, 36, 0], "platinum": [207, 173, 0], "business": [38, 38, 0],
         "last_complete": {"label": "Sep 2026", "gold": 36}}
    assert MC.drop_empty_partial_month(e, "totals") == "Oct 26"
    assert e["totals"] == [290, 247] and e["business"] == [38, 38]
    assert e["last_complete"] == {"label": "Sep 2026", "gold": 36}, "not a per-month list"


def test_both_builders_use_the_helper():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("build/ics_pipeline/build_ics_gen.py", "build/mrpc_pipeline/build_mrpc_gen.py"):
        src = open(os.path.join(root, *rel.split("/")), encoding="utf-8").read()
        assert "drop_empty_partial_month" in src, rel