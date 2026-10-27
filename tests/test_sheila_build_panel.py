"""Sheila's build progress: no separate "Full output" box, and a Transaction Intelligence build shows its
progress inside the Transaction Intelligence panel (Aaron, 2026-10-26)."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "build")]
import ars_launcher_web as W  # noqa: E402


def _between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


def test_the_full_output_box_is_gone():
    for gone in ("Full output", "termtext", "jobview", "logOpen", "termLine", 'class="term"'):
        assert gone not in W.PAGE, gone


def test_the_transaction_intelligence_panel_has_a_place_for_its_progress():
    panel = _between(W.PAGE, "function tiPanel(s)", "async function buildTI")
    assert '<div id="jobti"></div>' in panel
    # after the verdict (the button), before the last-build line
    assert panel.index("${verdict}") < panel.index('id="jobti"') < panel.index("${last}")


def test_a_ti_job_draws_in_the_panel_and_clears_the_other_place():
    render = _between(W.PAGE, "function renderJob(j)", "// ----")
    assert '(j.ti && $("#jobti")) || $("#job")' in render
    assert 'other.innerHTML = ""' in render


def test_the_launchers_lines_after_the_steps_are_part_of_the_result():
    """They were visible only in the log box. A STOP line is already the reason shown, so it is not repeated."""
    render = _between(W.PAGE, "function renderJob(j)", "// ----")
    assert 'marks.filter(x => x.level !== "STOP")' in render
    assert render.count("${notesHtml}") == 2          # the success result and the failure result


def test_a_finished_build_redraws_the_page_around_it():
    # The buttons and verdicts were drawn before the build started. Without a fresh status the TI button
    # stayed "Building..." and the previous failure notice stayed over a "Done" result (1075, 2026-10-27).
    follow = _between(W.PAGE, "function follow(id)", "function renderJob")
    done = follow[follow.index("if (body.done)"):]
    assert "recheckQuietly(id)" in done.split("}")[0]
