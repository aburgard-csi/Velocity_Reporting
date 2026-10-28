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


def test_each_card_has_a_place_for_its_progress():
    """Every presentation is a card (2026-10-28); a build's progress draws inside its own card, after the
    button and the checks."""
    card = _between(W.PAGE, "function deckCard(o)", "function renderStatus(s)")
    for box in ('<div id="job"></div>', '<div id="jobti"></div>', '<div id="jobcomp"></div>'):
        assert box in card
    assert card.index("${act}") < card.index("${fold}") < card.index("${jobBox}")
    assert 'key: "ti", id: "tipanel"' in _between(W.PAGE, "function tiPanel(s)", "async function buildTI")
    assert 'key: "comp", id: "comppanel"' in _between(W.PAGE, "function companionPanel(s)", "async function buildComp")


def test_passed_checks_are_folded_and_the_rest_stay_visible():
    card = _between(W.PAGE, "function deckCard(o)", "function renderStatus(s)")
    assert 'const needs = r => r.level === "stop" || r.level === "warn";' in card
    assert "<details class=\"fold\"><summary>" in card
    assert "Rebuild only if something changed" not in W.PAGE        # the instruction text is gone
    assert "Last build from this tool" not in W.PAGE                # said once, on the card's fact line


def test_a_ti_job_draws_in_the_panel_and_clears_the_other_place():
    render = _between(W.PAGE, "function renderJob(j)", "// ----")
    assert '(j.ti && $("#jobti")) || (j.companion && $("#jobcomp")) || $("#job")' in render
    assert 'for (const o of [$("#job"), $("#jobti"), $("#jobcomp")]) if (o && o !== box) o.innerHTML = ""' in render


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


def test_one_button_when_the_plain_and_combined_builds_are_the_same_deck():

    """1585 is ARS + CP with no ICS or MRPC: both buttons built that one deck, and the two labels read as a

    choice (Aaron, 2026-10-28). The page shows one button, and two only where combined adds programs."""

    page = W.PAGE

    assert 'const sameDeck = !!b.combined && b.ars_only && baseList.join("+") === b.combined.join("+");' in page

    assert "const two = b.ars_only && !!b.combined && !sameDeck;" in page
    assert 'sameDeck ? `${plain}, one deck`' in page           # the card's subtitle says so

    assert "if (b.combined && !sameDeck) h += `" in page          # the combined button is dropped, not hidden

