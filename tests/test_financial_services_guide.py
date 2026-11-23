"""The Financial Services guide generator (scripts/build_financial_services_guide.py)."""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_financial_services_guide as G  # noqa: E402


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    dest = tmp_path_factory.mktemp("guide") / "g.html"
    assert G.main([str(dest)]) == 0
    return dest.read_text(encoding="utf-8")


class _Ids(HTMLParser):
    VOID = {"meta", "br", "hr", "img", "input", "link"}

    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.stack, self.bad = [], [], [], []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "id" in d:
            self.ids.append(d["id"])
        if tag == "a" and d.get("href", "").startswith("#"):
            self.hrefs.append(d["href"][1:])
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.bad.append(tag)


def test_the_page_is_well_formed_and_every_contents_link_resolves(page):
    p = _Ids()
    p.feed(page)
    assert not p.bad and not p.stack
    assert len(p.ids) == len(set(p.ids))
    assert [h for h in p.hrefs if h not in p.ids] == []


def test_the_categories_come_from_the_dictionary(page):
    cats, _spec = G.categories()
    for c in cats:
        assert c["name"].replace("&", "&amp;") in page or c["name"] in page
    assert f"{len(cats)} categories" in page


def test_the_slide_table_comes_from_the_ledger(page):
    for row in G.finserv_slides():
        assert row[1] in page


def test_the_list_columns_come_from_the_code(page):
    from ti.transaction_intelligence import financial_services as F
    assert ", ".join(F.MASTER_COLUMNS) in page


def test_a_documented_figure_that_disappears_stops_the_build(monkeypatch):
    monkeypatch.setattr(G, "FIGURES", [("x", [("fin_no_such_figure", "gone")])])
    with pytest.raises(SystemExit) as e:
        G.check_figures({"fin_leaking_pct": 1})
    assert "fin_no_such_figure" in str(e.value)


def test_every_documented_figure_is_produced_today():
    G.check_figures(G.smoke_figures())


def test_it_uses_the_member_and_customer_wording(page):
    text = re.sub(r"<[^>]+>", " ", page)
    assert "account holder" in text and "Never" in text      # named only as the words not to use
    assert not re.search(r"\bconsumers\b", text)
