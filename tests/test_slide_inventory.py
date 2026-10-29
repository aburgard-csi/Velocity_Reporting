"""The slide inventory: every program's slides from the templates and the builders, never from a deck
(Aaron, 2026-10-29: "the decks all carry the same slides, because they're all built using the same
processes. We shouldn't need to scan the decks")."""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "scripts")]
import slide_inventory as SI  # noqa: E402


def _titles(prog):
    return [r["title"] for r in SI.inventory()[prog]]


def test_every_program_has_a_list_and_no_shell_slide_is_in_it():
    inv = SI.inventory()
    assert set(inv) == set(SI.PROGRAMS)
    for prog, rows in inv.items():
        assert rows, prog
        assert [r["n"] for r in rows] == list(range(1, len(rows) + 1))
        for r in rows:
            low = r["title"].lower()
            assert not low.startswith(("questions", "contact us", "agenda", "the executive summit")), (prog, r)
            assert "union financial" not in low, (prog, r)
            assert r["source"], (prog, r)


def test_the_ars_list_is_the_shell_with_the_builders_slides_where_the_builder_puts_them():
    t = _titles("ARS")
    assert t.index("Excluded Accounts") == t.index("Product Mix & ARS Eligibility") + 1
    assert t.index("Revenue Guarantee") == t.index("ARS Financial Performance") + 1
    assert t.index("Reg E Opt-In by Branch") == t.index("Reg E Opt-In — Opened in Last 12 Months") + 1
    assert t.index("Branch Reference") == t.index("Program Reach — Cumulative Responders") - 1
    assert "ARS Response — <month> Mailer" in t                      # the template's month is a placeholder
    assert "Responder Activity: Before vs After by Offer" in t      # the builder retitles the shell's Median slide
    assert "Responder Activity: Before vs After (Median)" not in t
    assert not any("anchor not found" in r["source"] for r in SI.inventory()["ARS"])


def test_the_ics_list_is_the_full_workbook_shape_whatever_the_newest_decks_carry():
    """Aaron, 2026-10-29: the ICS list must be the full list, not the referrals-only shape."""
    t = _titles("ICS")
    for title in ("The Power of Referrals", "Performance of ICS Accounts", "ICS Revenue", "ICS Financial Summary",
                  "Comparisons", "Appendix: Monthly Detail", "Direct Mail New Accounts"):
        assert title in t, title
    branch = next(i for i, x in enumerate(t) if SI._same(x, "Results by Branch — Year to Date"))   # the shell's own dash
    assert t.index("Direct Mail New Accounts") == branch + 1
    assert not any("anchor not found" in r["source"] for r in SI.inventory()["ICS"])


def test_the_mrpc_and_cashplease_lists_name_the_client_as_the_client():
    assert "MRPC Revenue by Year to the client" in _titles("MRPC")
    cp = _titles("CP")
    assert cp[:2] == ["CashPlease Program Overview", "CashPlease Program Settings"]
    assert "CashPlease Peer Comparison" in cp


def test_the_ti_list_is_the_cuts_register_kept_slides_in_chapter_order():
    reg = json.loads(open(os.path.join(REPO, "build", "ars_pipeline", "ti", "slides.json"), encoding="utf-8").read())
    expected = [t for ch, titles in reg["_by_chapter"].items() if reg["chapters"].get(ch, "keep") == "keep"
                for t in titles if reg["slides"].get(t, "keep") == "keep"]
    assert _titles("TI") == expected
    assert SI.inventory()["TI"][0]["source"].endswith("chapter Transaction Intelligence")


def test_the_companion_list_is_the_james_views_titles_as_the_modules_write_them():
    t = _titles("COMP")
    for title in ("Revenue by Mailing", "Branch Scorecard", "Revenue Build by Mailing", "Program Cascade",
                  "Debit Spend per Cardholder", "Sustained Activity: Non-User vs Threshold"):
        assert title in t, title
    assert len(t) == len(set(t))
    # each title is a literal in the module the inventory names, so a renamed slide fails here
    for r in SI.inventory()["COMP"]:
        src = open(os.path.join(REPO, r["source"]), encoding="utf-8").read()
        assert r["title"] in src, r


def test_a_lost_anchor_is_said_not_silent():
    rows = SI._splice(["A", "B"], [("X", "after", "Gone", "mod.py")])
    assert rows[-1][0] == "X" and "anchor not found" in rows[-1][1]
    rows = SI._splice(["Reg E Opt-In – Opened"], [("By Branch", "after", "Reg E Opt-In — Opened", "mod.py")])
    assert [t for t, _ in rows] == ["Reg E Opt-In – Opened", "By Branch"]       # an en dash matches an em dash


def test_the_inventory_is_cached_until_a_source_file_changes(monkeypatch):
    SI.inventory()
    calls = []
    monkeypatch.setattr(SI, "template_titles", lambda p: calls.append(p) or ["x"])
    SI.inventory()
    assert calls == []
    monkeypatch.setattr(SI, "_stamp", lambda: ("changed",))
    SI.inventory()
    assert calls, "a changed source file is read again"
    SI._cache.update(stamp=None, doc=None)
