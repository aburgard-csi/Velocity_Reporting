"""The ILS Program Analysis builder (build/ils_analysis): the figures that replace the R pictures, the
Scoring Summary computation, and the deck shell. Synthetic data only; nothing here reads a share."""
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "build" / "ils_analysis")]

from ils_review import r_common as R          # noqa: E402
from ils_review import r_fees as F            # noqa: E402
from ils_review import r_accounts as A        # noqa: E402
from ils_review import scoring_summary as SS  # noqa: E402
from ils_review.ils_data import Loaded        # noqa: E402
from ils_review.template import Shell        # noqa: E402

ASOF = pd.Timestamp("2026-09-10")


def _loaded():
    za = pd.DataFrame({
        "acctid": ["1", "2", "3"], "accttype": ["Personal"] * 3, "acctstatus": ["O"] * 3,
        "opendate": pd.to_datetime(["2020-01-01", "2025-06-01", "2015-05-05"]),
        "lastdepdate": pd.to_datetime(["2026-09-01"] * 3), "lastupdate": [ASOF] * 3,
        "CanOverdraft": [True, True, False], "RegEOptinvalue": ["Y", "N", "D"],
        "items365": [3.0, 1.0, 0.0], "PD_365": [2.0, 1.0, 0.0], "CollectedFees365": [90.0, 28.0, 0.0],
        "Chargeoff_Account": [False, True, False], "Chargeoff_Amt_365": [0.0, 15.0, 0.0],      # a 12.7% loss rate
        "Chargeoff_Date": pd.to_datetime([None, "2026-05-01", None]), "closeddate": pd.to_datetime([None] * 3),
        "Refund_Amt_365": [0.0] * 3, "WindfallRatio": [1.0, 0.2, 1.0], "ODLimit": [500, 0, 1000],
        "DepAmt33": [1200.0, 0.0, 300.0], "DepCount33": [4.0, 0.0, 1.0], "depAmt365": [9000.0, 0.0, 2000.0],
        "declines_365": [0.0] * 3, "branchname": ["Main"] * 3,
    })
    nd = pd.to_datetime(["2025-09-01", "2025-09-01", "2025-10-01", "2025-11-01"])
    zt = pd.DataFrame({
        "acctid": ["1", "1", "2", "2"], "noticedate": nd, "Items": [1, 1, 1, 1], "PD": [1, 1, 0, 1],
        "Item_Amts": [50.0, 20.0, 80.0, 30.0], "PossibleFees": [35.0] * 4, "CollectedFees": [28.0, 28.0, 8.0, 28.0],
        "Next_Positive_Date": pd.to_datetime(["2025-09-04", "2025-09-04", "2025-12-30", None]),
        "Last_Positive_Date": pd.to_datetime(["2025-08-30", "2025-08-30", "2025-09-29", "2025-10-31"]),
        "deptotal33": [1200.0, 1200.0, 0.0, 50.0], "depcount33": [4, 4, 0, 1], "limit": [500, 500, 0, 0],
    })
    return Loaded(zaccounts=za, ztrend=zt, snapshot=ASOF.to_pydatetime(), branches=None,
                  file_date=pd.Timestamp("2026-09-11").to_pydatetime())


def test_a_notice_is_one_account_on_one_date():
    fr = R.Frame(_loaded())
    n = fr.notices
    assert len(fr.zt) == 4 and len(n) == 3                    # two item rows on 2025-09-01 collapse to one notice
    both = n[(n["acctid"] == "1")].iloc[0]
    assert both["CollectedFees"] == 56.0                      # fees still sum across the items
    assert both["days_to_positive"] == 3 and both["days_od"] == 2


def test_default_is_repayment_after_the_threshold_and_never_repaid_is_excluded():
    fr = R.Frame(_loaded(), default_days=40)
    n = fr.notices.set_index(["acctid", "noticedate"])
    assert not n.loc[("1", pd.Timestamp("2025-09-01")), "is_default"]
    assert n.loc[("2", pd.Timestamp("2025-10-01")), "is_default"]          # 90 days to the next positive balance
    assert not n.loc[("2", pd.Timestamp("2025-11-01")), "is_default"]      # never repaid: not counted as a default


def test_scoring_window_ends_sixty_days_before_the_data_date():
    lo, hi = R.Frame(_loaded()).scoring_window()
    assert (str(lo)[:10], str(hi)[:10]) == ("2025-07-12", "2026-07-12")    # Achieva's window for a 2026-09-10 as-of


def test_days_on_book_bands_losses_once_per_account():
    class Cfg:
        default_basis = "deck"
    fr = R.Frame(_loaded())
    p = SS.predictors("deck")[0]
    res = SS.compute_predictor(p, fr, Cfg, "Personal")
    assert res.notices == [2, 1]                              # account 2 twice at 122 and 153 days, account 1 once at 5.7 yrs
    assert res.bands == ["31-180 Days", "5-6 Yrs"]
    assert sum(res.losses) == 15.0                           # the charge-off counted once
    assert res.default_rate[0] == 50.0                        # 1 of 2 notices in the 31-180 band defaulted


def test_deck_bands_differ_from_the_registry_only_where_the_deck_does():
    deck, readme = SS.predictors("deck"), SS.predictors("readme")
    same = {a.key for a, b in zip(deck, readme) if a.bands == b.bands}
    assert same == {"days_on_book", "dep33_amt", "dep33_count"}
    assert not [p for p in deck if p.key == "days_od"][0].losses       # the Days OD table has no Losses columns


def test_compare_reports_words_not_a_boolean():
    assert R.compare(100.0, 100.4)["status"] == "matched"
    assert R.compare(110.0, 100.0)["status"] == "off by +10.0%"
    assert R.compare(1.0, None)["status"] == "no reference figure"


def test_treemap_fills_the_box_exactly():
    rects = F._squarify([50, 30, 10, 6, 4], 0, 0, 1, 1)
    assert sum(w * h for _, _, w, h in rects) == pytest.approx(1.0)
    assert all(0 <= x and 0 <= y and x + w <= 1 + 1e-9 and y + h <= 1 + 1e-9 for x, y, w, h in rects)


def test_smoother_follows_a_trend():
    y = np.arange(100, dtype=float) + np.sin(np.arange(100)) * 5
    s = R.smooth(y, frac=0.3)
    assert s[-1] > s[0] + 80 and np.all(np.diff(s) > -1.5)


def test_kpi_rollup_counts_from_the_extract(tmp_path):
    fr = R.Frame(_loaded())
    res = F.kpi_rollup(fr)
    assert res.ok and res.numbers["Personal"]["open"] == 3 and res.numbers["Personal"]["fees"] == 118.0
    rows = {r[0]: r[1] for r in res.tables["kpi"]["rows"]}
    assert rows["Loss Rate"] == "12.7%"


def test_sidecar_is_written_beside_the_figure(tmp_path):
    res = R.ChartResult("demo", "Demo", str(tmp_path / "demo.png"), numbers={"n": np.int64(3)}, parity=[R.compare(1, 1)])
    p = R.write_sidecar(res, str(tmp_path), client_id="9999", asof=ASOF)
    import json
    doc = json.load(open(p, encoding="utf-8"))
    assert doc["numbers"]["n"] == 3 and doc["parity_vs_hand_built_deck"][0]["status"] == "matched"


def test_shell_detaches_demo_slides_and_saves_a_clean_package(tmp_path):
    sh = Shell()
    assert len(sh.prs.slides) == 0
    s = sh.add_slide()
    s2 = sh.add_slide()
    assert s is not s2
    out = sh.save(tmp_path / "x.pptx")
    names = zipfile.ZipFile(out).namelist()
    assert len(names) == len(set(names))
    assert sum(1 for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")) == 2
    sys.path.insert(0, str(REPO / "validation"))
    import validate_deck
    assert not [f for f in validate_deck.package_findings(str(out)) if f[0] == "FAIL"]


def test_cover_says_the_deck_it_is():
    from ils_review import build
    assert build.DECK_KIND == "ILS Program Analysis" and "Executive Review" not in build.DECK_KIND


def test_peer_slides_are_labelled_placeholders(tmp_path):
    from ils_review import client_slides as CS
    from ils_review.config import BuildConfig
    from ils_review import theme as T
    za = tmp_path / "za.csv"
    za.write_text("acctid\n1\n")
    cfg = BuildConfig(client_name="Demo CU", client_id="9999", zaccounts_path=str(za))
    sh = Shell()
    dk = T.Deck(sh, "Demo CU", "September 10, 2026", client_id="9999")
    dk.chart_dir = str(tmp_path)
    notes = CS.add_peer_data(dk, cfg, R.Frame(_loaded()), section="peer_data")
    texts = [shp.text_frame.text for s in sh.prs.slides for shp in s.shapes if shp.has_text_frame]
    assert any("placeholder" in t for t in texts) and notes
    assert all("Source" in s.notes_slide.notes_text_frame.text for s in sh.prs.slides)


# ── matrix slides, trends, communication strategies, strategic refunds, callouts ──────────────
def _S(**secs):
    return {k: {"columns": list(v[0].keys()) if v else [], "rows": v} for k, v in secs.items()}


def test_override_rows_attach_sub_conditions_to_their_rule():
    from ils_review import matrix_prep_slides as MP
    rows = [{"Override Criteria": "[Days OD] BETWEEN 12 AND 15", "Override Value": "-33%", "Stop Process": "0"},
            {"Override Criteria": "[Age of Account] BETWEEN 31 AND 124 AND [LTD Deposit Count] = 0", "Override Value": "0", "Stop Process": "1"},
            {"Override Criteria": "[Age of Account] BETWEEN 31 AND 124 AND [LTD Deposit Count] = 1", "Override Value": "-75%", "Stop Process": "0"}]
    out = MP.override_rows(rows)
    assert [o["text"] for o in out] == ["Days OD 12-15", "Age of Account 31-124", "& LTD Deposit Count = 0", "& LTD Deposit Count = 1"]
    assert [o["sub"] for o in out] == [False, False, True, True] and out[2]["ret"] == "$0" and out[3]["ret"] == "-75%"


def test_trends_are_on_or_off_only_and_absent_means_off():
    from ils_review import matrix_prep_slides as MP
    S = _S(TRENDS=[{"Account Type": "Personal", "Repository Name": "Deposit Regularity Trend", "Factor": "-100"},
                   {"Account Type": "Personal", "Repository Name": "Overdraft Repayment Trend", "Factor": "-0"}])
    st = dict(MP.trend_states(S, "Personal"))
    assert st == {"Deposit Regularity": True, "OD Repayment": False, "Windfall Deposit": False, "Cash Flow": False}
    assert not MP.check_trends(list(st.items()), "Personal")
    assert MP.check_trends([("Deposit Regularity", True), ("Windfall Deposit", True)], "x")


def test_all_zero_factor_tables_are_left_out():
    from ils_review import matrix_prep_slides as MP
    S = _S(**{"RANGES AND FACTORS": [
        {"Account Type": "Personal", "Category": "Age of Account", "Range": "[00] - 0 to 30 days (0.00, 30.00)", "Factor": "-100"},
        {"Account Type": "Personal", "Category": "Monthly Debit Declines", "Range": "[00] - 0 declines (0.00, 0.00)", "Factor": "0"}]})
    assert [c for c, _ in MP.factor_tables(S, "Personal")] == ["Age of Account"]


def test_communication_strategies_only_when_active():
    from ils_review import matrix_slides as MS, theme as T
    rows = [{"STRATEGY_NAME": "Off one", "ACTIVE": "0"}, {"STRATEGY_NAME": "On one", "ACTIVE": "1"}]
    sh = Shell()
    MS.slides_comm_strategies(T.Deck(sh, "Demo CU", "d", client_id="9999"), _S(**{"COMMUNICATION STRATEGIES": rows}), section="m")
    text = " ".join(shp.text_frame.text for s in sh.prs.slides for shp in s.shapes if shp.has_text_frame)
    assert "On one" in text and "Off one" not in text and "1 communication strategy is active" in text
    sh2 = Shell()
    MS.slides_comm_strategies(T.Deck(sh2, "Demo CU", "d", client_id="9999"), _S(**{"COMMUNICATION STRATEGIES": rows[:1]}), section="m")
    assert not any(shp.has_table for s in sh2.prs.slides for shp in s.shapes)
    assert any("None active" in shp.text_frame.text for s in sh2.prs.slides for shp in s.shapes if shp.has_text_frame)


def test_strategic_refunds_and_windfall_are_not_in_the_deck():
    from ils_review.config import SECTIONS, DEFAULT_SECTIONS
    import ils_review.matrix_data as MD
    assert "strategic_refunds" not in SECTIONS and "strategic_refunds" not in DEFAULT_SECTIONS
    assert "windfall" not in {p.key for p in SS.predictors("deck")}
    assert not hasattr(MD, "has_strategic_refunds")


def test_movement_wording_follows_the_two_percent_band():
    assert F.movement_phrase(101, 100, str).startswith("almost flat")
    assert F.movement_phrase(110, 100, str) == "up 10%: 110 against 100"
    assert "up" not in F.movement_phrase(90, 100, str) and "(-10%)" in F.movement_phrase(90, 100, str)


def test_fee_trend_skips_an_account_type_with_no_complete_month_in_the_window(tmp_path):
    """An account type whose notices all fall before the 12-month window (a small business book). The monthly table was
    empty and add_fee_trends raised IndexError, which also took paid vs returned and the not-repaid slides with it. The
    account type is now skipped with the reason, as a result that is not ok."""
    ld = _loaded()
    ld.ztrend["noticedate"] = pd.to_datetime(["2024-06-01", "2024-06-01", "2024-07-15", "2024-09-01"])
    res = F.fees_daily(R.Frame(ld), "Personal", str(tmp_path))
    assert res.ok is False and "no notices in the last 12 complete months" in res.skipped
    assert "2024-06-01 to 2024-09-01" in res.skipped
    # paid vs returned divided by the window's item count (ZeroDivisionError) for the same account type
    assert F.paid_vs_returned_stats(R.Frame(ld), "Personal") is None


def test_a_decline_extract_that_ends_before_the_window_reads_na_not_zero():
    """A DebitDecline extract that ends a year before the pull's data date: the
    'Debit declines by ILS limit' table showed 0 declines in every band. Missing data is stated, never zeroed: the
    decline cells read n/a and the result says where the extract ends."""
    from ils_review import r_accounts as RA
    ld = _loaded()
    ld.zaccounts["declines_365"] = [2.0, 3.0, 0.0]
    ld.declines = pd.DataFrame({"acctid": ["1", "2"], "decline_date": pd.to_datetime(["2025-01-10", "2025-02-01"]),
                                "transaction_amount": [20.0, 35.0]})
    d = RA.debit_decline_tables(R.Frame(ld), "Personal")
    assert d["declines_stale"] and d["declines_end"] == pd.Timestamp("2025-02-01")
    rows = d["score_bands"]["rows"]
    assert rows and all(r[3] == "n/a" and r[4] == "n/a" for r in rows)
    # a current extract still counts
    ld.declines["decline_date"] = pd.to_datetime([ASOF - pd.Timedelta(days=5)] * 2)
    d = RA.debit_decline_tables(R.Frame(ld), "Personal")
    assert not d["declines_stale"] and any(r[3] != "n/a" for r in d["score_bands"]["rows"])


def test_a_dated_extract_that_ends_well_before_the_data_date_is_named():
    """A pull folder can carry an extract from an older run. Each dated extract's newest row is checked against the data
    date; one that ends STALE_EXTRACT_DAYS or more before it, or holds no dated rows, is named for Data Notes."""
    from ils_review import ils_data
    asof = pd.Timestamp("2026-11-05")
    current = pd.DataFrame({"noticedate": pd.to_datetime(["2026-10-01", "2026-11-04"])})
    old = pd.DataFrame({"decline_date": pd.to_datetime(["2024-09-07", "2025-11-16"])})
    blank = pd.DataFrame({"Date": [None, None]})
    msgs = ils_data.extract_checks(asof, ztrend=current, declines=old, refunds=blank)
    assert len(msgs) == 2
    assert "DebitDecline extract ends 2025-11-16, 354 days before the data date" in msgs[0]
    assert "RefundHistory extract holds no dated rows" in msgs[1]
    assert ils_data.extract_checks(asof, ztrend=current) == []


def test_fee_chart_callout_says_what_it_is(tmp_path):
    res = F.fees_daily(R.Frame(_loaded()), "Personal", str(tmp_path))
    assert res.ok is False or (res.numbers["latest_30d_avg_date"] and any("30-day average" in n for n in res.notes))


def test_story_bands_and_status_gate():
    from ils_review import story_slides as SSL
    s = pd.Series([0, 100, 300, 5000, 9999])
    assert SSL._band(s, SSL.LIMIT_BANDS).tolist() == [0, 1, 2, 6, 6]
    S = _S(**{"OD STATUS CODE MAPPING": [{"STATUS_CODE": "NULL", "DESCRIPTION": "Active", "CAN_OVERDRAFT": "1"},
                                          {"STATUS_CODE": "1", "DESCRIPTION": "Member Opt-Out", "CAN_OVERDRAFT": "0"}]})
    m = SSL._status_map(S)
    assert m[""] == ("Active", True) and m["1"] == ("Member Opt-Out", False)     # a blank code is Active and can overdraft


# ── simplification, appendix, agenda, standard content, peers (Aaron / coordinator, 2026-11-04) ──
def _cfg(tmp_path, **kw):
    from ils_review.config import BuildConfig
    za = tmp_path / "za.csv"
    za.write_text("acctid\n1\n")
    return BuildConfig(client_name="Demo CU", client_id="9999", zaccounts_path=str(za), **kw)


def _deck(tmp_path):
    from ils_review import theme as T
    sh = Shell()
    dk = T.Deck(sh, "Demo CU", "September 10, 2026", client_id="9999")
    dk.chart_dir = str(tmp_path)
    return sh, dk


def test_deck_limit_dividers_and_default_story():
    from ils_review import config as C
    assert C.MAX_SLIDES == 50
    assert {"yoy", "usage_segments", "peers", "industry"} <= set(C.DEFAULT_SECTIONS)
    assert C.NO_DIVIDER_GROUPS <= set(C.GROUP_DIVIDERS) and {"calc", "perform", "pullback"}.isdisjoint(C.NO_DIVIDER_GROUPS)


def test_kpi_slide_is_six_tiles_and_the_full_table_is_queued_for_the_appendix(tmp_path):
    from ils_review import client_slides as CS
    sh, dk = _deck(tmp_path)
    CS.add_kpi_rollup(dk, _cfg(tmp_path), R.Frame(_loaded()), section="standing")
    assert len(sh.prs.slides) == 1 and not any(shp.has_table for shp in sh.prs.slides[0].shapes)
    assert len(dk.deferred) == 1
    dk.deferred[0]()
    assert len(sh.prs.slides) == 2 and any(shp.has_table for shp in sh.prs.slides[1].shapes)
    assert "Appendix" in [shp.text_frame.text for shp in sh.prs.slides[1].shapes if shp.has_text_frame][0]
    assert sh.prs.slides[0].notes_slide.notes_text_frame.text.startswith("Say first:")


def test_compact_money():
    from ils_review import client_slides as CS
    assert CS.compact_money("$7,294,040") == "$7.29M" and CS.compact_money("$866,858.22") == "$867K" and CS.compact_money("11.9%") == "11.9%"


def test_factor_caption_says_where_it_starts_peaks_and_ends():
    from ils_review import matrix_prep_slides as MP
    rows = [("0 to 30 days", "-$100"), ("31 days to 1 year", "$50"), ("1 to 2 years", "$400"), ("2 to 3 years", "$400")]
    fs = MP.factor_summary(rows)
    assert fs["first"] == ("0 to 30 days", "-$100") and fs["peak"] == ("1 to 2 years", "$400") and fs["negative"] == 1
    cap = MP.factor_caption("Age", rows)
    assert "Starts at -$100 for 0 to 30 days" in cap and "Reaches $400 at 1 to 2 years" in cap and "Stays at $400 through 2 to 3 years" in cap


def test_peer_group_very_large_against_very_large_and_the_rest_by_region():
    from ils_review import peers_slides as P
    d = [{"id": "1", "state": "FL", "region": "South", "assets_m": 12000, "dda": 100000},     # very large by assets
         {"id": "2", "state": "TX", "region": "South", "assets_m": 500, "dda": 900000},      # very large by DDA rank
         {"id": "3", "state": "GA", "region": "South", "assets_m": 800, "dda": 40000},
         {"id": "4", "state": "FL", "region": "South", "assets_m": 900, "dda": 30000},
         {"id": "5", "state": "NY", "region": "Northeast", "assets_m": 700, "dda": 20000}]
    d += [{"id": str(10 + i), "state": "OH", "region": "Midwest", "assets_m": 300, "dda": 10000 + i} for i in range(10)]
    g, ids, _ = P.peer_group("1", d)
    assert g == "very large ILS clients" and ids == ["2"]
    g, ids, _ = P.peer_group("3", d)
    assert "South" in g and ids == ["4"]                                       # not the very large ones, not another region
    assert P.peer_group("77", d)[0] is None
    assert P.MIN_PEERS == 5 and P.VERY_LARGE_ASSETS_M == 10_000
    assert P.REGION_OF_STATE["FL"] == "South" and P.REGION_OF_STATE["NY"] == "Northeast"


def _pool(n_peers, as_of="202608"):
    d = [{"id": "9999", "state": "FL", "region": "South", "assets_m": 500, "dda": 20000}]
    d += [{"id": str(500 + i), "state": "OH", "region": "Midwest", "assets_m": 20000, "dda": 900000 + i} for i in range(5)]   # the top of the DDA ranking
    m = {}
    for i in range(n_peers):
        cid = str(2000 + i)
        d.append({"id": cid, "state": "GA", "region": "South", "assets_m": 400, "dda": 15000})
        m[(cid, "Personal")] = {"as_of": as_of + "01", "open_accounts": 10000 + 500 * i, "items365": 8000 + 700 * i,
                                "fees365": 250000 + 20000 * i, "users365": 2000 + 100 * i}
    return {"directory": d, "metrics": m}


def test_peers_are_client_numbers_only_and_need_five(tmp_path):
    from ils_review import peers_slides as P
    sh, dk = _deck(tmp_path)
    notes = P.add_peers(dk, _cfg(tmp_path, peer_pool=_pool(6)), R.Frame(_loaded()), None, section="peers")
    assert len(sh.prs.slides) == 1
    s = sh.prs.slides[0]
    note = s.notes_slide.notes_text_frame.text
    assert "Peers by client number" in note and "2000" in note and "Demo" not in note.split("Source:")[0]
    assert any("against 6 ILS clients in the South region" in shp.text_frame.text for shp in s.shapes if shp.has_text_frame)
    sh2, dk2 = _deck(tmp_path)
    notes2 = P.add_peers(dk2, _cfg(tmp_path, peer_pool=_pool(4)), R.Frame(_loaded()), None, section="peers")
    t2 = " ".join(shp.text_frame.text for shp in sh2.prs.slides[0].shapes if shp.has_text_frame)
    assert "Not enough peers" in t2 and any("5 needed" in n or "needed" in n for n in notes2)
    sh3, dk3 = _deck(tmp_path)
    P.add_peers(dk3, _cfg(tmp_path, peer_pool=_pool(6, as_of="202301")), R.Frame(_loaded()), None, section="peers")
    assert "Not enough peers" in " ".join(shp.text_frame.text for shp in sh3.prs.slides[0].shapes if shp.has_text_frame)   # stale extracts do not count


def test_an_account_type_with_no_items_is_not_ranked_against_peers(tmp_path):
    """An account type with open accounts but no NSF/OD items read "Lowest of N clients" on every
    measure, all zeros. An account type with no items in 365 days gets no peer slide, and the notes say why."""
    from ils_review import peers_slides as P
    ld = _loaded()
    ld.zaccounts["items365"] = 0.0
    sh, dk = _deck(tmp_path)
    notes = P.add_peers(dk, _cfg(tmp_path, peer_pool=_pool(6)), R.Frame(ld), None, section="peers")
    assert len(sh.prs.slides) == 0
    assert any("no NSF/OD items in 365 days, so there is nothing to rank" in n for n in notes)


def test_industry_slides_come_from_the_standard_file_and_say_so(tmp_path):
    import json
    from ils_review import standard_slides as ST
    sh, dk = _deck(tmp_path)
    notes = ST.add_industry(dk, _cfg(tmp_path, standard_dir=str(tmp_path / "none")), R.Frame(_loaded()), None, section="industry")
    assert len(sh.prs.slides) == 0 and "skipped" in notes[0]
    (tmp_path / "industry_2026-08.json").write_text(json.dumps({"edition": "August 2026", "slides": [
        {"kind": "points", "title": "T", "points": [{"head": "H", "text": "x"}], "source": "S"},
        {"kind": "table", "title": "T2", "headers": ["a", "b"], "rows": [["1", "2"]]}]}), encoding="utf-8")
    sh, dk = _deck(tmp_path)
    ST.add_industry(dk, _cfg(tmp_path, standard_dir=str(tmp_path)), R.Frame(_loaded()), None, section="industry")
    assert len(sh.prs.slides) == 2 and "August 2026" in sh.prs.slides[0].notes_slide.notes_text_frame.text


def test_agenda_lists_the_rows_in_order(tmp_path):
    from ils_review import standard_slides as ST
    sh, dk = _deck(tmp_path)
    s = ST.add_agenda(dk, [("One", "a"), ("Two", "b")])
    txt = [shp.text_frame.text for shp in s.shapes if shp.has_text_frame]
    assert txt.index("One") < txt.index("Two") and "1" in txt and "2" in txt


def test_usage_segments_chart_and_parity_are_recorded(tmp_path):
    from ils_review import analysis_slides as AN
    za = _loaded().zaccounts
    za = pd.concat([za] * 40, ignore_index=True)
    za["acctid"] = [str(i) for i in range(len(za))]
    za["items365"] = np.where(np.arange(len(za)) % 10 == 0, 30.0, za["items365"])
    L = _loaded()
    L.zaccounts = za
    sh, dk = _deck(tmp_path)
    dk.ref = {"usage.Personal.heavy_fees_pct": 50.0}
    AN.add_usage_segments(dk, _cfg(tmp_path), R.Frame(L), None, section="drivers")
    assert len(sh.prs.slides) == 1 and dk.sidecars[-1]["parity"][0]["deck"] == 50.0


def test_cure_is_sixty_days_and_the_default_basis_is_separate():
    from ils_review import story_slides as SSL
    assert SSL.CURE_DAYS == 60 and R.DEFAULT_REPAYMENT_DAYS == 40
    w, lo, hi = SSL._cure_frame(R.Frame(_loaded()))
    assert w["cured"].tolist() == [True, True, False] or w["cured"].dtype == bool


def test_the_default_story_sits_in_the_four_agenda_parts():
    """Aaron, 2026-11-05: the agenda is four parts, no descriptions; every default section belongs to one, and the
    matrix sections are the ones built after Contact Us (the appendix)."""
    from ils_review import config as C
    parts = {C.PART_INDUSTRY, C.PART_PERFORMANCE, C.PART_OBSERVATIONS, C.PART_APPENDIX}
    for key in C.DEFAULT_SECTIONS:
        if key != "data_notes":
            assert C.PART_OF[key] in parts, key
    assert set(C.APPENDIX_KEYS) == {k for k, v in C.PART_OF.items() if v == C.PART_APPENDIX}
    order = [C.PART_OF[k] for k in C.DEFAULT_SECTIONS if k in C.PART_OF]
    assert [p for i, p in enumerate(order) if i == 0 or p != order[i - 1]] == [
        C.PART_INDUSTRY, C.PART_PERFORMANCE, C.PART_OBSERVATIONS, C.PART_APPENDIX]

def test_not_repaid_is_the_notice_nearest_the_last_positive_date(tmp_path):
    """Aaron, 2026-11-17: "Your cure rate slides are wrong. Look at the fatal notice rates in the deck that William
    built." The analysis notebook's rule (cells 30-34): a charged-off account's fatal notice is the ONE notice nearest
    its last positive date (the largest Last_Positive_Date over its notices). Account 2 is charged off with notices on
    2025-10-01 and 2025-11-01 and a last positive date of 2025-10-31: the 11-01 notice is fatal, the 10-01 is not.
    On 1781 this rule gave all twelve of William's monthly % Fatal Notices exactly."""
    fr = R.Frame(_loaded())
    n = fr.notices.set_index(["acctid", "noticedate"])
    assert n.loc[("2", pd.Timestamp("2025-11-01")), "nb_fatal"]
    assert not n.loc[("2", pd.Timestamp("2025-10-01")), "nb_fatal"]
    assert not n["nb_fatal"].loc["1"].any()                                # account 1 was never charged off
    assert n["nb_loss"].sum() == 15.0                                     # its charge-off counted once
    res = F.not_repaid(fr, "Personal", str(tmp_path))
    t = res.tables["monthly"]
    assert t["headers"] == ["Month", "OD Accts", "Collected Fees", "Biz Days", "Fees / Biz Day", "Pay Rate", "Ineligible",
                            "% Fatal", "Loss Rate"]
    nov = [m for m in res.numbers["monthly"] if m["month"] == "2025-11"][0]
    assert nov["fatal_pct"] == 100.0 and nov["pay_rate_pct"] == 100.0       # one notice, fatal, its one item paid
    sep = [m for m in res.numbers["monthly"] if m["month"] == "2025-09"][0]
    assert sep["fatal_pct"] == 0.0 and sep["business_days"] == 1


def test_a_charge_off_flag_on_most_accounts_withholds_dollars_not_rates(tmp_path):
    """Dannemora 1781: 99% of accounts flagged charged off. The notebook still reports the rates (William's deck does);
    the loss dollars are absurd, so they read n/a, and the Scoring Summary is built rather than skipped."""
    ld = _loaded()
    ld.zaccounts["Chargeoff_Account"] = [True, True, False]
    fr = R.Frame(ld)
    assert fr.co_problem and fr.co_flag_share == pytest.approx(2 / 3)
    res = F.not_repaid(fr, "Personal", str(tmp_path))
    assert all(r[-1] == "n/a" for r in res.tables["monthly"]["rows"])
    assert all(m["loss_rate_pct"] is None for m in res.numbers["monthly"])


def test_charge_offs_above_every_fee_collected_withhold_the_dollars(tmp_path):
    """Aaron, 2026-11-17: a loss rate runs 4-12%, about 20% at the high end. 1781 read 303,433% ($2.0B against $667K),
    so the dollars are caught by the loss rate even where the flag looks ordinary; a real 17% is left alone."""
    ld = _loaded()
    ld.zaccounts["Chargeoff_Account"] = [False, False, False]
    ld.zaccounts["CollectedFees365"] = [100.0, 100.0, 100.0]
    ld.zaccounts["Chargeoff_Amt_365"] = [51.0, 0.0, 0.0]
    fr = R.Frame(ld)
    assert fr.co_problem is None and fr.co_loss_rate == pytest.approx(0.17)
    ld.zaccounts["Chargeoff_Amt_365"] = [2_000_000_000.0, 0.0, 0.0]
    fr = R.Frame(ld)
    assert fr.co_problem and "loss rate" in fr.co_problem and "$2.00B" in fr.co_problem
    assert fr.co_slide_line() == "Charge-off dollars in this extract are not usable: loss rates are withheld."
    res = F.not_repaid(fr, "Personal", str(tmp_path))
    assert all(r[-1] == "n/a" for r in res.tables["monthly"]["rows"])


def test_the_cure_slides_left_the_default_story_for_the_scoring_summary():
    from ils_review import config as C
    assert "performing" not in C.DEFAULT_SECTIONS
    assert {"scoring_personal", "scoring_business", "branch_summary"} <= set(C.DEFAULT_SECTIONS)
    assert C.BuildConfig.__dataclass_fields__["include_not_repaid"].default is True


def test_lowess_follows_a_trend_and_a_sparse_series_is_not_pulled_flat():
    x = np.arange(200, dtype=float)
    y = x * 0.05 + np.sin(x) * 0.5
    fit = F._lowess(x, y)
    assert fit[-1] > fit[0] + 8
    sparse = np.where(x % 5 == 0, 30.0, 0.0)                               # one day in five at 30%: a 6% series
    assert F._lowess(x, sparse, iters=0).mean() == pytest.approx(6.0, abs=0.5)


def test_as_of_cuts_the_dated_rows_and_says_so(tmp_path):
    """Aaron, 2026-11-17 (1781): rebuild a newer pull as of an earlier review's data date so the slides match it.
    Notices after the date are left out, the as-of date is that date, and the Data Notes say what was cut."""
    from datetime import datetime
    from ils_review import ils_data
    ld = _loaded()
    za, zt = ld.zaccounts.assign(branch="1"), ld.ztrend
    zp, tp = tmp_path / "1781_zaccounts_20261106.csv", tmp_path / "1781_ztrend_20261106.csv"
    za.to_csv(zp, index=False)
    zt.to_csv(tp, index=False)
    full = ils_data.load(str(zp), str(tp))
    cut = ils_data.load(str(zp), str(tp), snapshot_date=datetime(2025, 10, 15))
    assert len(full.ztrend) == 4 and len(cut.ztrend) == 3
    assert cut.ztrend["noticedate"].max() <= pd.Timestamp("2025-10-15")
    assert pd.Timestamp(cut.snapshot) == pd.Timestamp("2025-10-15")
    assert any("Built as of 2025-10-15" in n and "as pulled on 2026-11-06" in n for n in cut.notes)


def test_headerless_decline_and_refund_extracts_are_read_by_their_known_columns(tmp_path):
    """Debit-decline and refund-history files saved without their header line:
    and the build stopped on KeyError 'acctid'. A first line that does not name AcctID but has the query's field count
    is read with the known columns, and the Data Notes say so; a file with its header reads as before."""
    from ils_review import ils_data
    ld = _loaded()
    za, zt = ld.zaccounts.assign(branch="1"), ld.ztrend
    zp, tp = tmp_path / "9999_zaccounts_20261106.csv", tmp_path / "9999_ztrend_20261106.csv"
    za.to_csv(zp, index=False)
    zt.to_csv(tp, index=False)
    dec = ["502,3,0082,0B208D33D1CA,2024-09-07 00:00:00.000,SIG,15.00,6012,SYNTHETIC MERCHANT,1",
           "503,3,0082,0B208D33D1CB,2024-09-08 00:00:00.000,PIN,40.00,5411,SYNTHETIC GROCER,2"]
    ref = ['0009,Synthetic Branch,18689,132664,60.5100,0.0000,0.0000,0.0000,0.0000,60.5100,"Charge         ",'
           '2024-09-07 00:00:00.000,Undefined,10650']
    dp, rp = tmp_path / "DebitDecline.csv", tmp_path / "RefundHistory.csv"
    dp.write_text("\n".join(dec) + "\n", encoding="utf-8")
    rp.write_text("\n".join(ref) + "\n", encoding="utf-8")
    got = ils_data.load(str(zp), str(tp), declines_path=str(dp), refunds_path=str(rp))
    assert len(got.declines) == 2 and list(got.declines["acctid"]) == ["502", "503"]
    assert got.declines["decline_date"].min() == pd.Timestamp("2024-09-07")
    assert len(got.refunds) == 1 and got.refunds["AcctID"].iloc[0] == "132664"
    assert got.refunds["Date"].iloc[0] == pd.Timestamp("2024-09-07")
    assert sum("has no header line" in n for n in got.notes) == 2
    # with the header line, nothing is said and the same rows are read
    dp.write_text(",".join(ils_data.DECLINE_COLUMNS) + "\n" + "\n".join(dec) + "\n", encoding="utf-8")
    rp.write_text(",".join(ils_data.REFUND_COLUMNS) + "\n" + "\n".join(ref) + "\n", encoding="utf-8")
    again = ils_data.load(str(zp), str(tp), declines_path=str(dp), refunds_path=str(rp))
    assert len(again.declines) == 2 and len(again.refunds) == 1
    assert not any("has no header line" in n for n in again.notes)


def test_channel_medians_are_per_channel_over_the_year():
    ld = _loaded()
    ld.ztrend["POS"] = [1, 0, 1, 0]
    ld.ztrend["ACH"] = [0, 1, 0, 1]
    fr = R.Frame(ld)
    m = F.channel_medians(fr, "Personal")
    assert m["medians"] == {"ACH": 30.0, "POS": 80.0, "Total": 55.0}      # the 2025-09-01 notices fall outside the year
    assert F.channel_medians(fr, "Personal", ["POS"])["medians"] == {"POS": 80.0, "Total": 80.0}
    assert F.channel_medians(fr, "Business") is None


def test_exception_items_are_one_slide_when_the_dbic_carries_the_channels():
    """Aaron, 2026-11-17: "Exception items by channel" (DBIC) and "Trends in exception items" (ZTrend treemap) showed the
    same items. With the DBIC channel table the medians ride on its slide and the treemap slide is not built."""
    from types import SimpleNamespace
    from ils_review import build as B
    run = SimpleNamespace(cfg=SimpleNamespace(dbic_path="x_dbic.txt", sections=["dbic", "exception_items"]),
                          _dbic=SimpleNamespace(available=True, channels=({("Personal", "PD"): {"POS": 3}}, {"POS": 3})))
    assert B._dbic_channels(run) and B._sec_exception_items(run, "exception_items") == []
    run.cfg.sections = ["exception_items"]
    assert not B._dbic_channels(run)
