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


@pytest.mark.parametrize("module,tab", [("sheila_hub_feedback", "reported")])
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
