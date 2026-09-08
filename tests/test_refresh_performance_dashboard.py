"""refresh_performance_dashboard — the rules that decide whether the artifact is
republished, and what period it claims.

  * The period is the newest ARS workbook on Drive, not today's month: the page
    rolls forward when the workbooks are copied, not before.
  * "Changed" means the figures moved. The generation date is excluded from the
    hash, or every daily rebuild would republish an identical page.
  * No dataset value can close the page's script tag.
"""
import json

import pytest

import refresh_performance_dashboard as P


# ------------------------------------------------------------------ period
def test_period_is_the_newest_ars_workbook():
    names = [
        "1038-2026.08-Sugar River-Workbook_v2_1_0.xlsx",
        "1075-2026.09-Austin-Workbook_v2_1_0.xlsx",
        "1509-2026.09-Texas Bay-Invitation Checking Workbook v1.7.1.xlsx",   # ICS, ignored
        "1075-2026.10-Austin-DCO v2_2.xlsx",                                  # not a workbook
        "~$1204-2026.11-First State Bank-MI-Workbook_v2_1_0.xlsx",            # lock file
    ]
    assert P.derive_period("unused", names) == "2026.09"


def test_no_workbooks_means_no_period():
    assert P.derive_period("unused", ["1075-2026.08-Austin-DCO v2_2.xlsx"]) is None


# ------------------------------------------------------------------ roster
ROSTER = """
## Active clients
| 1038 | Sugar River Bank | SM | yes | — | — | ARS |

### CashPlease roster — BUILD ONLY THESE

| ID | Client | Build | Loans | Ships as | Note |
| --- | --- | --- | --- | --- | --- |
| 1131 | People's Bank AL | yes | 10,507 | standalone module | |
| 1658 | Truliant FCU | **no** | 8,296 | — | cancelled |
| 1734 | Altamaha Bank and Trust Company | yes | 646 | ICS-CP | |

## Something else
| 9999 | Not a CashPlease client | yes | | | |
"""


def test_cashplease_roster_reads_build_yes_rows_only():
    assert P.cashplease_roster(ROSTER) == {"1131": "People's Bank AL",
                                           "1734": "Altamaha Bank and Trust Company"}


def test_cashplease_roster_absent_is_empty():
    assert P.cashplease_roster("# nothing here") == {}


# ------------------------------------------------------------------ render / hash
def test_render_injects_and_escapes_script_close():
    tpl = "<title>x</title><script>const DATA = __DATA__;</script>"
    html = P.render({"a": "</script><b>"}, tpl)
    assert "__DATA__" not in html
    assert "</script><b>" not in html.split("const DATA = ", 1)[1].split(";</script>")[0]
    assert r"<\/script>" in html


def test_render_refuses_a_template_without_the_placeholder():
    with pytest.raises(SystemExit):
        P.render({}, "<p>no slot</p>")


def test_hash_ignores_the_generation_date_but_not_figures():
    a = {"generated": "2026-09-08", "period": "2026.08", "clients": [{"id": "1", "x": 1}]}
    b = dict(a, generated="2026-09-09")
    c = dict(a, clients=[{"id": "1", "x": 2}])
    assert P.content_hash(a) == P.content_hash(b)
    assert P.content_hash(a) != P.content_hash(c)


def test_repo_template_has_the_slot_and_a_title():
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert t.count(P.PLACEHOLDER) == 1
    assert "<title>RPE Client Performance</title>" in t


# ------------------------------------------------------------------ state
def test_mark_published_refuses_before_a_build(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path)
    with pytest.raises(SystemExit):
        P.main(["--mark-published"])


def test_mark_published_records_the_built_hash(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path)
    P.write_state(tmp_path / "state.json", {"hash": "abc123"})
    assert P.main(["--mark-published"]) == 0
    s = json.loads((tmp_path / "state.json").read_text())
    assert s["published_hash"] == "abc123" and s["published_at"]
