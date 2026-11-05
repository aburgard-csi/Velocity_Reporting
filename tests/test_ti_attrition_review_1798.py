"""Sheila's 1798 slide review (2026-10-30), the Attrition, Deposits and ICS rows.

Each test pins one row of the review so the defect cannot come back:
  * no rail tile or table cell reads "n/a", and no tile is drawn with an empty value ("" / "built");
    what is missing is stated in a note instead (67, 74, 75);
  * the hazard headline reads "at 5-10 years", not "in year 5-10 yr" (70);
  * the cohort chart's month labels are MMM'YY, so the month-axis guard renders it (69);
  * the two stressor counts are one slide with both bases (combine group J, 68 + 75);
  * attrition by branch and by group are one slide (combine group I, 66 + 72);
  * no footnote under 10.5pt (66, 72);
  * every Deposits and ICS slide declines through Deck.declined when the client has no deposits
    file or no ICS accounts, so the deck can hide them and drop the chapter (76-89).

The figures are 1798's own, from its ti_pack.json, trimmed.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import attrition_inline as I  # noqa: E402
from ti.deck import attrition_slides as P  # noqa: E402
from ti.deck import txn_attrition as T  # noqa: E402
from ti.deck.txn_common import absent_note  # noqa: E402


class _Harness(dict):
    """Records slides, tables, rails, charts and text boxes (with their size)."""

    def __init__(self):
        super().__init__()
        self.slides, self.tables, self.rails, self.charts, self.texts = [], [], [], [], []
        self["slide"] = lambda pair, fallback: (self.slides.append((pair, fallback)) or object(), 1.75)
        self["table"] = lambda s, rows, *a, **k: self.tables.append(rows)
        self["rail"] = lambda s, items, **k: self.rails.append(items) or 9.9
        self["chart"] = lambda name, fn, *a, **k: self.charts.append((name, fn.__name__, a)) or None
        self["chart_left"] = lambda *a, **k: None
        self["picture"] = lambda *a, **k: None
        self["text"] = lambda s, l, t, w, hh, text, size=14, **k: self.texts.append((text, size))
        self["charts"] = __import__("ti.deck.charts", fromlist=["x"])
        from ti.deck import helpers
        self.update(MARGIN_L=helpers.MARGIN_L, RIGHT_EDGE=helpers.RIGHT_EDGE,
                    CONTENT_W=helpers.CONTENT_W, NAVY=helpers.NAVY, GREY=helpers.GREY)

    def tiles(self):
        return [item for items in self.rails for item in items]

    def everything(self):
        out = [str(x) for pair, fb in self.slides for x in (pair or ()) if x]
        out += [str(x) for item in self.tiles() for x in item if x is not None]
        out += [str(c) for rows in self.tables for row in rows for c in row]
        out += [t for t, _ in self.texts]
        return "\n".join(out)


M1798 = {
    "life_decline": [[0, 12852, 83.56, 1073893, 12.6], [1, 12385, 251.15, 3110522, 22.0],
                     [2, 12005, 349.13, 4191254, 28.8]],
    "life_control": [[0, 97970, 938.54, 91949042, 51.7], [1, 97970, 986.53, 96650450, 51.6],
                     [2, 97970, 953.72, 93436371, 51.5]],
    "life_divergence_month": 12, "life_divergence_ratio": 0.8,
    "life_divergence_by_tenure": [["month 1", 3, None], ["month 2", 4, None], ["month 3", 14, None],
                                  ["month 4", 14, None], ["1-3 yr", 2373, 12], ["3-5 yr", 2316, 7],
                                  ["5-10 yr", 4323, 12]],
    "leak_curve": [[0, 4405, 19.61, 86391, 4.5], [1, 4037, 53.84, 217334, 8.5],
                   [11, 300, 92.64, 27791, 16.0], [12, 0, None, None, None]],
    "leak_curve_columns": ["offset_months", "n", "mean_competitor_dollars", "total", "pct_with_any"],
    "leak_control": [[0, 0, None, None, None], [1, 0, None, None, None],
                     [11, 0, None, None, None], [12, 0, None, None, None]],
    "leak_divergence_month": None,
    "stress_base": "Open at anchor", "stress_2plus_n": 908, "stress_2plus_pct": 1.0,
    "stress_2plus_deposits": 3067480,
    "stress_available": ["Spend health declining", "Deposits leaving", "Gone quiet",
                         "In the hazard-peak tenure band"],
    "stress_skipped": ["Banking elsewhere", "Deposits slowing"],
    "stress_by_count": [[0, 36519, 40.9, 161108392], [1, 51846, 58.1, 186211185],
                        [2, 906, 1.0, 2425911], [3, 2, 0.0, 641569]],
    "stress_txn_base": "Open at anchor, transacting join", "stress_txn_2plus_n": 20991,
    "stress_txn_2plus_pct": 21.4, "stress_txn_2plus_deposits": 41920458,
    "stress_txn_2plus_competitor_dollars": 10075344,
    "stress_txn_available": ["Spend health declining", "Deposits leaving", "Gone quiet",
                             "Banking elsewhere", "In the hazard-peak tenure band"],
    "stress_txn_skipped": ["Deposits slowing"],
    "stress_txn_by_count": [[0, 23503, 24.0, 110465639], [1, 53476, 54.6, 198751043],
                            [2, 19816, 20.2, 40027258], [3, 1175, 1.2, 1893201]],
    "attrition_rate": 4.3,
    "attrition_by_product": [["Business Premier Share Draft", 1000, 77, 7.7]],
    "attrition_hazard": [["0-6 mo", 108503, 1000, 0.9], ["5-10 yr", 48737, 3745, 7.7],
                         ["10+ yr", 100, 0, None]],
    "attrition_hazard_peak": ["5-10 yr", 7.7],
    "attrition_cohort_survival": [["Oct24", 702, 596, 106, 84.9], ["Sep26", 487, 484, 3, 99.4]],
    "attrition_cohort_first_year_rate": 8.6, "attrition_cohort_first_year_base": 8212,
    "attrition_by_branch": [["305", 19868, 827, 4.2], ["301", 6988, 199, 2.8], ["313", 603, 36, 6.0]],
    "attrition_branch_best": ["301", 2.8, 6988], "attrition_branch_worst": ["313", 6.0, 603],
    "attrition_by_lens": [["all", "All accounts", 102364, 4405, 4.3, 97012.5, 4.5],
                          ["responders", "Responders", 24331, 760, 3.1, 23816.7, 3.2],
                          ["mailed_nonresp", "Mailed non-responders", 23901, 1372, 5.7, 22354.9, 6.1]],
}


def _no_empty_tiles(h):
    for label, value, note in h.tiles():
        assert value not in ("", None, "n/a"), (label, value, note)
        assert note not in ("built", "n/a"), (label, value, note)
    assert "n/a" not in h.everything()


def test_months_of_warning_has_no_na_tile_and_states_the_quiet_bands():
    h = _Harness()
    assert P.months_of_warning(h, M1798) is None
    _no_empty_tiles(h)
    labels = [t[0] for t in h.tiles()]
    assert "1-3 yr" in labels and "3-5 yr" in labels and "month 1" not in labels
    notes = " ".join(t for t, _ in h.texts)
    assert "No sustained fade was detectable" in notes and "month 1" in notes


def test_months_of_warning_drops_an_unmeasured_month_and_says_so():
    m = dict(M1798, life_control=[[0, 97970, None, None, None]] + M1798["life_control"][1:])
    h = _Harness()
    P.months_of_warning(h, m)
    assert "n/a" not in h.everything()
    assert [r[0] for r in h.tables[0][1:]] == [1, 2]
    assert any("no measured spend" in t for t, _ in h.texts)


def test_spend_before_closure_reads_the_month_before_close_and_never_na():
    h = _Harness()
    assert T.spend_before_closure(h, M1798, "personal accounts") is None
    _no_empty_tiles(h)
    first = h.tiles()[0]
    assert first[0] == "Month before close" and first[1] == "$54"
    (head, sub), _ = h.slides[-1]
    assert "no still-open control" in sub
    assert any("12 months before close" in t for t, _ in h.texts)
    name, fn, args = h.charts[-1]
    assert 12 not in args[0], "a month with no closers measured is left off the chart"


def test_stresses_across_files_alone_has_no_valueless_tiles():
    h = _Harness()
    m = {k: v for k, v in M1798.items() if not k.startswith("stress_") or k.startswith("stress_txn")}
    assert T.stresses_across_files(h, m, "accounts") is None
    _no_empty_tiles(h)


def test_hazard_headline_reads_at_5_10_years():
    h = _Harness()
    assert P.product_and_hazard(h, M1798) is None
    (head, _), _ = h.slides[-1]
    assert "at 5-10 years" in head and "year 5-10" not in head and "yr" not in head
    assert "n/a" not in h.everything()
    assert any("10+ yr" in t for t, _ in h.texts), "the unmeasured band is stated"


def test_band_phrase():
    assert P.band_phrase("5-10 yr") == "5-10 years"
    assert P.band_phrase("0-6 mo") == "0-6 months"
    assert P.band_phrase("< 1 yr") == "under 1 year"
    assert P.band_phrase("10+ yr") == "10+ years"
    assert P.band_phrase("something else") == "something else"


def test_cohort_chart_months_pass_the_month_axis_guard(tmp_path):
    """The chart rendered nothing on 1798: v5's "Oct24" fails periods' guard. Render it for real."""
    h = _Harness()
    path = {}

    def chart(name, fn, *a, **k):
        path["p"] = fn(*a, tmp_path / f"{name}.png", **k)
        return path["p"]

    h["chart"] = chart
    assert P.cohort_survival(h, M1798) is None
    assert path["p"].exists()
    assert "Opened Oct'24" in [t[0] for t in h.tiles()]


def test_one_stressor_slide_shows_both_bases():
    h = _Harness()
    assert P.concurrent_stressors(h, M1798) is None
    assert len(h.slides) == 1
    (head, sub), title = h.slides[0]
    assert title == "Accounts under several stresses"
    assert "908" in head and "20,991" in head
    assert len(head) <= 90, "past 90 characters the frame splits a headline at a clause"
    assert "Open at anchor" in sub and "transacting join" in sub
    assert h.tables[0][0] == ["Stressors", "ODD only", "% of base", "With transactions", "% of base"]
    assert h.tables[0][3][1] == "906" and h.tables[0][3][3] == "19,816"
    notes = " ".join(t for t, _ in h.texts)
    assert "With transactions adds: Banking elsewhere" in notes
    _no_empty_tiles(h)


def test_one_stressor_slide_falls_back_to_the_base_on_hand():
    odd_only = {k: v for k, v in M1798.items() if not k.startswith("stress_txn")}
    h = _Harness()
    assert P.concurrent_stressors(h, odd_only) is None
    assert "908" in h.slides[0][0][0] and "20,991" not in h.everything()
    _no_empty_tiles(h)
    txn_only = {k: v for k, v in M1798.items() if k.startswith("stress_txn")}
    h = _Harness()
    assert P.concurrent_stressors(h, txn_only) is None
    assert h.slides[0][1] == "Stresses across both files"
    assert P.concurrent_stressors(_Harness(), {})


def test_branch_and_group_on_one_slide_with_footnote_at_10_5():
    h = _Harness()
    assert I.attrition_branch_and_group(h, M1798) is None
    assert len(h.slides) == 1 and h.slides[0][1] == "Attrition by branch"
    assert h.charts[0][0] == "attrition_branch"
    table = h.tables[0]
    assert table[0] == ["Group", "Rate / yr", "At risk"]
    assert [r[0] for r in table[1:]] == ["All accounts", "Mailed non-responders", "Responders"]
    assert all(size >= 10.5 for _, size in h.texts)


def test_branch_and_group_falls_back_to_the_cut_on_hand():
    h = _Harness()
    no_groups = dict(M1798, attrition_by_lens=[])
    assert I.attrition_branch_and_group(h, no_groups) is None
    assert h.slides[0][1] == "Attrition by branch" and not h.tables
    h = _Harness()
    no_branch = dict(M1798, attrition_by_branch=[])
    assert I.attrition_branch_and_group(h, no_branch) is None
    assert h.slides[0][1] == "Attrition by group"
    assert I.attrition_branch_and_group(_Harness(), {})


def test_v5_footnotes_are_at_least_10_5():
    for fn in (I.attrition_branch, I.attrition_by_group):
        h = _Harness()
        fn(h, M1798)
        assert h.texts and all(size >= 10.5 for _, size in h.texts), fn.__name__


def test_no_literal_footnote_under_10_5_in_these_files():
    import re
    deck = HERE.parent / "build" / "ars_pipeline" / "ti" / "deck"
    for name in ("attrition_slides.py", "attrition_inline.py", "txn_attrition.py",
                 "deposit_slides.py", "ics_slides.py"):
        text = (deck / name).read_text(encoding="utf-8")
        small = [m.group(0) for m in re.finditer(r"\bsize=(\d+(?:\.\d+)?)\b", text)
                 if float(m.group(1)) < 10.5]
        assert not small, (name, small)


def test_absent_note():
    assert absent_note(["a", "b"]) == "a, b"
    assert absent_note([f"month {i}" for i in range(1, 13)], "tenure bands") == \
        "12 tenure bands, month 1 ... month 12"


def test_chapter_draws_the_combined_slides_not_the_pairs():
    from ti.chapters import attrition as C
    import inspect
    src = inspect.getsource(C.build)
    assert "attrition_branch_and_group" in src and "attrition_by_group" not in src
    assert C.TXN_TITLES == ("spend_before_closure",)


# ---- Deposits and ICS decline through the standard path ----------------------------------------

class _Ctx:
    def __init__(self, tmp_path, metrics):
        from pptx import Presentation
        self.prs = Presentation(str(HERE.parent / "templates" / "ars_template.pptx"))
        self.art_dir = str(tmp_path)
        self.pill = "October 2026 Data"
        self.pack = {"client_id": "9999", "client_name": "Test CU", "sources": {"odd": "x.zip"},
                     "metrics": metrics}
        self.lens = type("L", (), {"label": "ARS lens"})()


def _capture(monkeypatch):
    """Every Deck built during the call, so its declines and slides can be read."""
    from ti.deck import helpers
    made = []
    orig = helpers.Deck.__init__

    def init(self, *a, **k):
        orig(self, *a, **k)
        made.append(self)
    monkeypatch.setattr(helpers.Deck, "__init__", init)
    return made


def test_every_deposit_slide_declines_without_a_deposits_file(tmp_path, monkeypatch):
    from ti.chapters import deposits
    made = _capture(monkeypatch)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    deposits.build(_Ctx(tmp_path, {}))
    deck = made[-1]
    # a pair drawn as one slide (ti/deck/combine.py) declines as one, under the combined topic
    merged = {t for pair in deposits.COMBINED for t in (deposits.TITLES[pair[0]], deposits.TITLES[pair[1]])}
    expected = (set(deposits.TITLES.values()) - merged) | {pair[2] for pair in deposits.COMBINED}
    assert len(deck.declines) == len(expected) == len(deck.slides)
    assert {title for title, _ in deck.declines} == expected
    assert all(reason == "no deposits file" for _, reason in deck.declines)


def test_ics_chapter_declines_without_ics_accounts(tmp_path, monkeypatch):
    from ti.chapters import ics
    made = _capture(monkeypatch)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    ics.build(_Ctx(tmp_path, {}))
    deck = made[-1]
    assert len(deck.slides) == len(deck.declines) == 1
    assert deck.declines[0][0] == "ICS accounts"
