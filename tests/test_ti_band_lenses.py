"""R5: leakage and competitor use by member age band, account-age band and branch.

James, 2026-11-05: "it would be nice to have the age band lens, maybe branch lens. account age
lens". Pinned here: the age_band / tenure_band lens families band members on the card slides' cut
points and decline (empty, stated) when the ODD lacks the column; financial_services writes
fin_by_age_band / fin_by_tenure_band / fin_by_branch and competition writes comp_by_age_band /
comp_by_tenure_band on one basis, so a band's two rows divide by the same accounts; the three
slides draw from those rows and say only what the rows show.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

import test_ti_competition as base                                           # noqa: E402
from ti.core import account_lenses as AL                                 # noqa: E402
from ti.deck import charts, txn_leakage as L                             # noqa: E402
from ti.transaction_intelligence import band_lenses as BL                # noqa: E402
from ti.transaction_intelligence import competition, financial_services  # noqa: E402
from ti.transaction_intelligence import merchant_profiles as MP          # noqa: E402
from ti.transaction_intelligence.lens import Lenses                      # noqa: E402

ANCHOR = pd.Timestamp("2026-07-31")
#            A1   A2   A3   A4   A5   A6    A7    A8    B1
AGES = [30, 30, 40, 40, 70, 70, None, 17, 50]
TENURE = [0.1, 2, 2, 5, 5, 12, 12, None, 2]
BRANCH = ["01", "01", "01", "02", "02", "02", "03", "03", "03"]


def _lenses(drop=()):
    lenses = base.make_lenses()
    attrs = lenses.attrs.copy()
    attrs["Account Holder Age"] = AGES
    attrs["tenure_years"] = TENURE
    attrs["Branch"] = BRANCH
    attrs = attrs.drop(columns=list(drop))
    return Lenses(key_column=lenses.key_column, accounts=lenses.accounts,
                  masks=lenses.masks, attrs=attrs)


def _run(lenses, monkeypatch, floor=1):
    monkeypatch.setattr(BL, "MIN_ACCOUNTS", floor)
    df = base.make_frame()
    fin_spec = financial_services.load_patterns(CONFIG_DIR, base.CLIENT_CFG)
    rows = financial_services.classify_rows(df, fin_spec)
    warnings = []
    personal = lenses.ids("personal")
    fin, _ = financial_services.compute(df, lenses, fin_spec, ANCHOR, None, warnings.append,
                                        account_filter=personal, classification=rows)
    spec = competition.load_config(CONFIG_DIR, base.CLIENT_CFG)
    comp, _ = competition.compute(df, lenses, spec, rows, ANCHOR, None, warnings.append,
                                  account_filter=personal, key_prefix="comp_")
    return fin, comp, warnings


# ------------------------------------------------------------------ the families

def test_the_bands_are_the_card_slides_own():
    assert MP.AGE_BANDS is AL.AGE_BANDS and MP.TENURE_BANDS is AL.TENURE_BANDS
    assert [b[2] for b in AL.AGE_BANDS] == ["18-25", "26-35", "36-45", "46-55", "56-64", "65+"]


def test_age_and_tenure_families_band_in_order_and_skip_blanks():
    lenses = _lenses()
    age = lenses.family("age_band")
    assert list(age) == ["26-35", "36-45", "46-55", "65+"]          # band order, empty bands absent
    assert list(age["26-35"]) == ["A1", "A2"]
    assert sum(len(v) for v in age.values()) == 7                   # A7 blank and A8 (17) in no band
    tenure = lenses.family("tenure_band")
    assert list(tenure) == ["< 3 mo", "1-3 yrs", "3-10 yrs", "10+ yrs"]
    assert list(tenure["1-3 yrs"]) == ["A2", "A3", "B1"]            # low <= v < high


def test_a_family_whose_column_is_missing_is_empty_not_an_error():
    lenses = _lenses(drop=("Account Holder Age", "tenure_years", "Branch"))
    for fam in ("age_band", "tenure_band", "branch"):
        assert lenses.family(fam) == {}


# ------------------------------------------------------------------ the figures

def test_financial_services_writes_three_cuts_with_columns_and_basis(monkeypatch):
    fin, _comp, _w = _run(_lenses(), monkeypatch)
    for key in ("fin_by_age_band", "fin_by_tenure_band", "fin_by_branch"):
        assert fin[key], key
        assert fin[key + "_columns"] == ["band", "accounts", "paying", "paying_pct",
                                         "dollars_per_payer", "top_category",
                                         "top_category_accounts"]
        assert "window" in fin[key + "_basis"]
    young = fin["fin_by_age_band"][0]
    # A1 pays Chase and Capital One cards, A2 Capital One: both leak, cards lead
    assert young[:4] == ["26-35", 2, 2, 100.0] and young[5:] == ["Credit Cards", 2]
    old = next(r for r in fin["fin_by_age_band"] if r[0] == "65+")
    assert old[2:] == [0, 0.0, 0, None, 0]                          # A5 (Venmo) is adjacency, not leakage


def test_dollars_per_payer_divide_by_the_accounts_that_pay(monkeypatch):
    fin, _c, _w = _run(_lenses(), monkeypatch)
    df = base.make_frame()
    a12 = df[df["primary_account_num"].isin(["A1", "A2"])]
    leak = a12[a12["merchant_name"].str.contains("CHASE|CAPITAL ONE")]["amount"].abs().sum()
    assert fin["fin_by_age_band"][0][4] == round(leak / 2)


def test_competition_cuts_age_and_tenure_on_the_same_accounts_and_not_branch_again(monkeypatch):
    fin, comp, _w = _run(_lenses(), monkeypatch)
    for fam in ("age_band", "tenure_band"):
        f, c = fin[f"fin_by_{fam}"], comp[f"comp_by_{fam}"]
        assert [(r[0], r[1]) for r in f] == [(r[0], r[1]) for r in c]   # same bands, same bases
        assert comp[f"comp_by_{fam}_columns"][5] == "top_institution"
    assert comp["comp_by_age_band"][0][5] == "Capital One"            # both 26-35 accounts pay it
    # branch stays competition's own table (comp_by_branch); nothing here writes a second one
    assert not any(k.startswith("comp_by_branch") and k not in (
        "comp_by_branch", "comp_by_branch_columns", "comp_by_branch_basis") for k in comp)


def test_a_missing_column_is_stated_and_the_rest_still_compute(monkeypatch):
    fin, comp, warnings = _run(_lenses(drop=("Account Holder Age",)), monkeypatch)
    assert "fin_by_age_band" not in fin and "comp_by_age_band" not in comp
    assert fin["fin_by_tenure_band"] and comp["comp_by_tenure_band"]
    assert any("fin_by_age_band unavailable" in w and "Account Holder Age" in w for w in warnings)
    assert any("comp_by_age_band unavailable" in w for w in warnings)


def test_thin_bands_are_left_out_and_counted(monkeypatch):
    fin, _c, warnings = _run(_lenses(), monkeypatch, floor=3)
    assert [r[0] for r in fin["fin_by_branch"]] == ["01", "02", "03"]
    assert [r[0] for r in fin["fin_by_tenure_band"]] == ["1-3 yrs"]
    assert any("fin_by_tenure_band: 5 transacting account(s)" in w for w in warnings), warnings


def test_branches_keep_the_largest_by_accounts(monkeypatch):
    monkeypatch.setattr(BL, "TOP_BRANCHES", 2)
    rows, left_out = BL.cut({"a": pd.Index(["1", "2", "3"]), "b": pd.Index(["4"]),
                             "c": pd.Index(["5", "6"])},
                            pd.Index([str(i) for i in range(1, 7)]),
                            pd.DataFrame({"acct": ["1", "5"], "category": ["X", "Y"],
                                          "dollars": [10.0, 30.0]}),
                            "category", min_accounts=1, top=2)
    assert [r[0] for r in rows] == ["a", "c"] and left_out == 1
    assert rows[0][2:] == [1, 33.3, 10, "X", 1]


# ------------------------------------------------------------------ the slides

class _Harness(dict):
    def __init__(self):
        super().__init__()
        self.slides, self.charts, self.rails = [], [], []
        self["slide"] = lambda hs, title: (self.slides.append((hs, title)) or (object(), 1.5))
        self["chart"] = self._chart
        self["chart_left"] = lambda *a, **k: None
        self["rail"] = lambda _s, rows, **_k: self.rails.append(rows)

    def _chart(self, name, fn, *args, **kwargs):
        self.charts.append({"name": name, "fn": fn.__name__, "args": args, "kw": kwargs})


def _figures(monkeypatch):
    fin, comp, _w = _run(_lenses(), monkeypatch)
    return {**fin, **comp}


def test_the_age_slide_leads_with_the_band_that_leaks_most(monkeypatch):
    t = _figures(monkeypatch)
    h = _Harness()
    assert L.leakage_by_member_age(h, t, "personal accounts") is None
    (head, sub), title = h.slides[0]
    assert title == "Leakage by member age"
    # 26-35, 36-45 and 46-55 all sit at 100%: a tie is said as a tie, not handed to one band
    assert head == ("Three age bands tie for the most leakage — 100% of accounts in each pay "
                    "an outside financial product")
    assert "a year" not in head + sub and "over the window" in sub
    chart = h.charts[0]
    assert chart["fn"] == "grouped_bars"
    labels_, fin_pct, comp_pct = chart["args"][:3]
    assert labels_ == [r[0] for r in t["fin_by_age_band"]]
    assert fin_pct == [r[3] for r in t["fin_by_age_band"]]
    assert comp_pct == [r[3] for r in t["comp_by_age_band"]]
    tiles = {k: (v, note) for k, v, note in h.rails[0]}
    assert tiles["Top competitor"][0] == "Capital One"


def test_the_tenure_and_branch_slides_draw(monkeypatch):
    t = _figures(monkeypatch)
    h = _Harness()
    assert L.leakage_by_account_tenure(h, t, "personal accounts") is None
    assert h.slides[0][0][0].startswith("Accounts open < 3 mo and 1-3 yrs leak the most — 100%")
    t["comp_by_branch"] = [["01", 3, 2, 66.7, 100, 33, "Capital One"]]
    h = _Harness()
    assert L.leakage_by_branch(h, t, "personal accounts") is None
    (head, _sub), title = h.slides[0]
    assert title == "Leakage by branch" and head == (
        "01 leaks the most — 100% of its accounts pay an outside financial product")
    assert h.charts[0]["args"][2] == [66.7, 0, 0]                   # branches 02/03 had no comp row


def test_the_slides_decline_without_rows():
    for fn in (L.leakage_by_member_age, L.leakage_by_account_tenure, L.leakage_by_branch):
        why = fn(_Harness(), {}, "personal accounts")
        assert why and "fewer than two" in why


def test_the_grouped_chart_renders_percentages(tmp_path):
    path = charts.grouped_bars(["26-35", "36-45"], [41.0, 30.5], [20.0, 0],
                               "outside financial product", "named competitor",
                               tmp_path / "bands.png", fmt="{:.0f}%")
    assert pathlib.Path(path).exists()
