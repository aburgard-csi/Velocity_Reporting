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
        "Chargeoff_Account": [False, True, False], "Chargeoff_Amt_365": [0.0, 500.0, 0.0],
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
    assert sum(res.losses) == 500.0                           # the charge-off counted once
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
    assert rows["Loss Rate"] == "423.7%"


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
