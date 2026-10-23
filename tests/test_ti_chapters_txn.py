"""The Transaction Intelligence and Competition chapters (build/ars_pipeline/ti/chapters_txn.py).

Pinned: the two chapters carry v5's 61 transaction builders less its two attrition slides, in v5's
order; every builder has a title for a stated slide; a client with no transaction figures gets one
stated slide per chapter; the ICS lens narrows the lens list and the ARS lens leaves it as v5 drew it.
"""
import os
import sys

from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline", "validation"):
    sys.path.insert(0, os.path.join(REPO, p))

import build_ti_gen as G  # noqa: E402
import validate_deck as vd  # noqa: E402
from test_ti_shell import CLIENT, NAME, PACK, TEMPLATE, contacts  # noqa: E402,F401
from ti import chapters_txn as X  # noqa: E402
from ti import cut  # noqa: E402
from ti.deck import txn_slides  # noqa: E402


def test_the_chapters_carry_v5s_builders_in_v5s_order():
    v5 = [b.__name__ for b in txn_slides.BUILDERS]
    ours = [b.__name__ for b in X.TI_BUILDERS + X.COMP_BUILDERS + X.ATTRITION_BUILDERS]
    assert sorted(ours) == sorted(v5) and len(v5) == 61
    for chapter in (X.TI_BUILDERS, X.COMP_BUILDERS):
        names = [b.__name__ for b in chapter]
        assert names == [n for n in v5 if n in names], "kept in v5's own order"
    assert len(X.TI_BUILDERS) == 39 and len(X.COMP_BUILDERS) == 20


def test_every_builder_has_a_title_for_a_stated_slide():
    for b in X.TI_BUILDERS + X.COMP_BUILDERS + X.ATTRITION_BUILDERS:
        assert X.TITLES.get(b.__name__), b.__name__


def test_the_chapters_are_registered_in_deck_order():
    assert [c.code for c in cut.CHAPTERS][:2] == ["TI_TXN", "TI_COMP"]


def test_ics_lens_narrows_the_lens_list_and_ars_leaves_it():
    m = {"lenses": [["all", "All", 9], ["responders", "R", 3], ["ics", "ICS", 2], ["ics_dm", "DM", 1]]}
    assert X.lens_view(m, cut.lens("ars")) is m
    assert [r[0] for r in X.lens_view(m, cut.lens("ics"))["lenses"]] == ["all", "ics", "ics_dm"]


def test_no_transaction_figures_is_one_stated_slide_per_chapter(tmp_path, contacts):
    prs = Presentation(TEMPLATE)
    G.build(prs, dict(PACK, metrics={}), "ars", list(cut.CHAPTERS[:2]), art_dir=str(tmp_path))
    out = tmp_path / cut.deck_name(CLIENT, "2026.10", NAME, "ars")
    G.save(prs, out)
    deck = Presentation(str(out))
    titles = [G._title(s) for s in deck.slides]
    # cover, summit, agenda, then divider + one stated slide per chapter, then Q&A and contact
    assert len(titles) == 3 + 2 * 2 + 2, titles
    stated = [s for s in deck.slides if "transaction files for this period are not on hand" in
              " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)]
    assert len(stated) == 2
    fails = [f for f in vd.run(str(out)) if f[0] == "FAIL"]
    assert fails == [], fails
