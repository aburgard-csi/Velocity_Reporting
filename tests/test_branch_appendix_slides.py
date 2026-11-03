"""The branch-detail tables in the ARS Appendix (Aaron, 2026-11-02: "I want the full branch performance in
the appendix. We don't need the branch detail in the main deck, just the charts.").

1441 FNB Alaska has 27 branches. Every branch the metric reports must be listed, over as many pages as it
takes, each table must end on the program figure the chart slides state, and the tables must keep their
12 pt through restyle_fonts while the rest of the slide keeps the 16 pt floor.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build", "ars_pipeline"))

import branch_appendix_slides as B                           # noqa: E402

ASSETS = os.path.join(_HERE, os.pardir, "build", "assets")
MONTHS = ["Aug", "Sep", "Oct"]


def _m(n, small=True):
    """n branches in each metric, plus (small=True) a few accounts in branches under the threshold."""
    take = [[str(i + 1), 2, 3, 4, 9, 20, 45] for i in range(n)]
    for r in take:
        r[-1] = round(100 * r[-3] / r[-2])
    cards = sum(r[-3] for r in take) + (6 if small else 0)
    elig = sum(r[-2] for r in take) + (10 if small else 0)
    cols = [sum(r[1 + j] for r in take) + (2 if small else 0) for j in range(3)]
    reg_all = [(str(i + 1), 40, 100, 40) for i in range(n)]
    pool = 100 * n + (30 if small else 0)
    reg_new = [(str(i + 1), 10, 30, 0, 40, 25) for i in range(n)]
    npool = 40 * n + (12 if small else 0)
    return {
        "take_months": MONTHS, "take_branch_monthly": take, "take_col_totals": cols,
        "take_new_cards": cards, "take_new_total": elig,
        "rege_branch": reg_all, "rege_pool": pool, "rege_in": 40 * n + (10 if small else 0),
        "rege_branch_table": reg_new, "rege_new_pool": npool,
        "rege_new_in": 10 * n + (3 if small else 0), "rege_new_out": 30 * n + (9 if small else 0),
        "rege_new_no": (0 if not small else 0), "rege_new_pct": 25, "rege_new_window": ["Nov 2025", "Oct 2026", 12],
    }


def test_27_branches_are_all_listed_over_pages_and_the_total_closes():
    header, body, total, other = B.take_rows(_m(27))
    pages = B.paginate(body, total)
    names = [r[0] for pg in pages for r in pg if r[0] not in ("Total",)]
    assert names == [str(i) for i in range(1, 28)] + ["All other branches"] and other
    assert len(pages) == 2 and all(len(pg) <= B.MAX_ROWS - 1 for pg in pages)
    assert pages[-1][-1][0] == "Total" and pages[0][-1][0] != "Total"


def test_the_remainder_row_makes_the_branch_rows_add_to_the_total():
    header, body, total, _ = B.take_rows(_m(5))
    k = len(MONTHS)
    for j in range(1, k + 1):
        assert sum(int(r[j]) for r in body) == int(total[j])
    cards = lambda r: int(r[k + 1].replace(",", ""))
    elig = lambda r: int(r[k + 2].replace(",", ""))
    assert sum(cards(r) for r in body) == cards(total) and sum(elig(r) for r in body) == elig(total)
    _, body, total, _ = B.rege_new_rows(_m(5))
    for j in range(1, 5):
        assert sum(int(r[j].replace(",", "")) for r in body) == int(total[j].replace(",", ""))
    _, body, total, _ = B.rege_all_rows(_m(5))
    for j in (1, 2):
        assert sum(int(r[j].replace(",", "")) for r in body) == int(total[j].replace(",", ""))


def test_no_remainder_row_when_every_branch_is_in_the_metric():
    for fn in (B.take_rows, B.rege_all_rows, B.rege_new_rows):
        _, body, _, other = fn(_m(4, small=False))
        assert not other and all(r[0] != "All other branches" for r in body)


def test_names_keep_branch_number_order_on_the_take_table():
    m = _m(3, small=False)
    m["branch_name_of"] = {"1": "Zebra", "2": "Alpha", "3": "Mid"}
    for r, n in zip(m["take_branch_monthly"], ("Zebra", "Alpha", "Mid")):
        r[0] = n
    _, body, _, _ = B.take_rows(m)
    assert [r[0] for r in body] == ["Zebra", "Alpha", "Mid"]      # numbers 1, 2, 3, not alphabetical


def test_one_page_when_it_fits():
    pages = B.paginate([["a"]] * 10, ["Total"])
    assert len(pages) == 1 and len(pages[0]) == 11


def _deck(tmp_path, n):
    from pptx import Presentation
    import restyle_fonts
    prs = Presentation(os.path.join(_HERE, os.pardir, "templates", "ars_template.pptx"))
    made = B.add_branch_appendix(prs, _m(n), ASSETS, "October 2026", "11-2025 · 10-2026",
                                 "Nov 2025 – Oct 2026", renumber=False)
    out = str(tmp_path / "t.pptx")
    prs.save(out)
    restyle_fonts.restyle(out)
    return Presentation(out), made


def _title(sl):
    return next(sh.text_frame.text for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.strip())


def test_pages_follow_the_divider_in_order_with_k_of_n_titles(tmp_path):
    prs, made = _deck(tmp_path, 27)
    titles = [_title(s) for s in prs.slides]
    d = titles.index("Appendix")
    fam = titles[d + 1:d + 1 + len(made)]
    assert fam == ["Appendix: Take Rate by Branch (1 of 2)", "Appendix: Take Rate by Branch (2 of 2)",
                   "Appendix: Reg E Opt-In by Branch (1 of 2)", "Appendix: Reg E Opt-In by Branch (2 of 2)",
                   "Appendix: Reg E New Accounts by Branch (1 of 2)", "Appendix: Reg E New Accounts by Branch (2 of 2)"]
    for t in fam:
        assert t in B.BODY_NOTES and B.BODY_NOTES[t]


def test_tables_keep_12pt_and_the_rest_of_the_slide_keeps_the_floor(tmp_path):
    prs, made = _deck(tmp_path, 27)
    title_text = {_title(s) for s in made}
    for sl in prs.slides:
        if _title(sl) not in title_text:
            continue
        for sh in sl.shapes:
            sizes = {r.font.size.pt for sh2 in [sh] if sh2.has_text_frame
                     for p in sh2.text_frame.paragraphs for r in p.runs if r.font.size}
            if sh.has_table:
                sizes = {r.font.size.pt for row in sh.table.rows for c in row.cells
                         for p in c.text_frame.paragraphs for r in p.runs}
                assert sizes == {12.0}, _title(sl)
            elif sizes and not sh.name.startswith("Picture"):
                assert min(sizes) >= 12.0
        subtitle = next(sh for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.startswith(("Selection", "New ", "Selection:")))
        assert min(r.font.size.pt for p in subtitle.text_frame.paragraphs for r in p.runs) >= 16.0


def test_every_table_fits_above_the_footer(tmp_path):
    from pptx.util import Emu
    prs, made = _deck(tmp_path, 27)
    for sl in prs.slides:
        for sh in sl.shapes:
            if sh.has_table and sh.name == B.BRANCH_DETAIL_TABLE:
                assert Emu(sh.top + sh.height).inches <= 6.56
                assert len(sh.table.rows) <= B.MAX_ROWS


def test_a_deck_without_an_appendix_divider_adds_nothing():
    from pptx import Presentation
    prs = Presentation(os.path.join(_HERE, os.pardir, "templates", "mrpc_template.pptx"))
    assert B.add_branch_appendix(prs, _m(3), ASSETS, "October 2026", "p", "w", renumber=False) == []
