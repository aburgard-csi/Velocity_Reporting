"""The RPE Client Performance page hands over the command that starts Live Review (Aaron, 2026-11-03).

Live Review is served on 127.0.0.1 with a fresh port and token, so the page cannot link to it. These
tests pin what it can do: a column of per-client commands, one script for the clients listed, the
checkout the commands run from, and a box to copy from when the artifact sandbox blocks the clipboard.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = (REPO / "scripts" / "perf_dashboard_template.html").read_text(encoding="utf-8")
REFRESH = (REPO / "scripts" / "refresh_performance_dashboard.py").read_text(encoding="utf-8")


def test_roster_has_a_live_review_column_and_a_script_button():
    assert 'data-lr="' in TEMPLATE
    assert "data-lr-all" in TEMPLATE
    assert '<th class="l">Live Review</th>' in TEMPLATE


def test_commands_use_the_checkout_in_the_dataset_not_a_path_in_the_page():
    assert "DATA.live_review" in TEMPLATE
    assert '"live_review": {"repo"' in REFRESH
    assert "RPE_REPO" in REFRESH
    # no machine path is written into the page itself
    assert "C:" + chr(92) + "Projects" not in TEMPLATE


def test_only_a_numeric_client_and_a_yyyy_mm_period_reach_a_command():
    assert r"/^\d{3,6}$/" in TEMPLATE
    assert r"/^\d{4}\.\d{2}$/" in TEMPLATE


def test_blocked_clipboard_falls_back_to_a_box_to_copy_from():
    assert "navigator.clipboard.writeText" in TEMPLATE
    assert 'id="lrbox"' in TEMPLATE or "lrbox" in TEMPLATE
