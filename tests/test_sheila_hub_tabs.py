"""The tabs of CSM Sheila's Hub layout: what each one draws and the routes it uses (2026-11-02).

The logic behind each tab is pinned where it always was (test_sheila_issues, test_sheila_lift_matrix,
test_slide_votes); these pin the page side, which moved from the old page when Sheila moved to the Hub layout.
"""
import os
import re
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import sheila_hub as H  # noqa: E402


def between(text, a, b):
    return text[text.index(a):text.index(b, text.index(a))]


@pytest.mark.parametrize("module,tab", [("sheila_hub_feedback", "reported"), ("sheila_hub_issues", "issues")])
def test_each_tab_module_is_complete_and_assembled_once(module, tab):
    import importlib
    m = importlib.import_module(module)
    assert m.TAB == tab and m.NAME and m.VIEW.strip() and m.CSS.strip() and m.JS.strip()
    assert H.PAGE.count(f'id="v-{tab}"') == 1 and f'registerTab("{tab}"' in H.PAGE
    assert f'data-tab="{tab}" href="#{tab}"' in H.PAGE, "linked in the sidebar to its own address, not another page"
    assert module in H.TAB_MODULES


def test_feedback_lists_reports_and_sends_one_with_a_toast():
    page = H.PAGE
    assert '"/api/reports"' in page and '"/api/report"' in page
    send = between(page, "async function send(ev)", "function move(d)")
    assert 'toast("Reported.' in send and "page: \"reported\"" in send, "a short form and a success toast"
    assert "Ctrl  Enter" in page and "requestSubmit" in page
    assert "queued" in page and "recorded, not on GitHub yet" in page, "a queued report is not mistaken for a filed one"
    assert '$("#reportbtn").addEventListener("click", focusForm)' in page and 'id="reportbtn"' in page


def test_the_change_log_page_wears_the_hubs_colours_and_links_back():
    import ars_launcher_web as W
    css = W.CHANGELOG_CSS
    assert "#F47A29" not in css and "#F15D22" not in css and "--link:#15627E" in css and "prefers-color-scheme:dark" in css
    md = os.path.join(REPO, "CHANGELOG.md")
    page = W.changelog_page(md)
    assert 'aria-label="Two stacked slides"' in page and 'href="/"' in page and "Back to Sheila" in page and 'rel="icon"' in page


def test_data_issues_marks_complete_in_one_click_and_keeps_the_counts_in_the_sidebar():
    page = H.PAGE
    for route in ('"/api/issues"', '"/api/issues/mark"', '"/api/code-sheet"'):
        assert route in page
    mark = between(page, "async function mark(btn)", "function select(id)")
    assert "await loadIssues(true); paint();" in mark and 'toast(done ? "Marked complete.' in mark
    assert '${si("ok")}Mark complete' in page and 'data-done="0">Undo' in page, "one click to mark, one to undo"
    assert 'id="b-issues"' in page and "function paintIssueBadge()" in page and "paintIssueBadge();" in between(page, "function setCsm(v)", "function csmPick()")
    # a mark that a newer workbook reopened says so, with the date and the workbook that arrived
    assert "a new workbook has arrived since" in page and "It stays complete until a new workbook arrives for this client." in page
    # grouped by client: a list with counts beside the cards; the open client again goes back to all of them
    assert "function select(id) { I.cur = I.cur === id ? null : id;" in page and 'data-iall' in page
    assert '"1  2  3  4  5  6"' in page


def test_the_links_row_is_the_same_wherever_a_client_is_named():
    page = H.PAGE
    row = between(page, "function linksRowHTML(", "async function clientLinks(")
    for part in ("Open code sheet", "Show it in File Explorer", "Deck checks", "Lift Matrix", "No data issues"):
        assert part in row
    assert 'clientLinks(s.client, "decks", $("#clientlinks"))' in page, "on the Decks client page too"
    assert 'if (t === "decks") { go("decks"); openClient(c); } else go(t, {client: c});' in page
