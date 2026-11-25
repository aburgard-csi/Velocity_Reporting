"""CSM Sheila's design changes of 2026-11-25 (Aaron picked six of eight proposals drawn from public design guidance):
a finished build is noticeable when Sheila is in the background, one quiet screen-reader line instead of whole lists
read aloud, the Lift Matrix overview keeps its header and client column in view, an expected "not yet" is not drawn in
red, single-key shortcuts can be turned off, and the glass goes solid when Windows' transparency effects are off."""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import sheila_hub as H  # noqa: E402
import sheila_hub_lift as LIFT  # noqa: E402
import sheila_hub_live as LIVE  # noqa: E402

PAGE = H.PAGE
CSS = PAGE.split("<style>", 1)[1].split("</style>", 1)[0]


def fn(name):
    """The body of one top-level JS function in the page (up to the next line that starts a declaration)."""
    m = re.search(r"\n(?:async )?function " + name + r"\(.*?(?=\n(?:async function|function|let|const|//|\$\(|document|window)\b)", PAGE, re.S)
    assert m, name
    return m.group(0)


# ------------------------------------------------------------------ 2. a finished build is noticed
def test_a_build_that_finishes_in_the_background_flags_the_tab_and_keeps_its_toast():
    done = fn("buildFinished")
    assert "away()" in done and "FLAG =" in done and "paintTitle()" in done
    assert 'ok && !bg ? 6000 : 0' in done, "a failure, or news while away, stays until closed"
    assert "celebrate()" in done and "!bg" in done, "no confetti for a page nobody is looking at"
    assert 'addEventListener("focus", clearFlag)' in PAGE and '"visibilitychange", clearFlag' in PAGE


def test_the_title_goes_through_one_painter_so_a_tab_change_keeps_the_flag():
    assert len(re.findall(r"document\.title\s*=", PAGE)) == 1
    assert "BASE_TITLE = id ===" in PAGE


def test_a_toast_kept_open_has_a_close_button_and_others_still_fade():
    t = fn("toast")
    assert "ms === 0" in t and 'aria-label", "Dismiss"' in t and "setTimeout(() => t.remove(), ms || 3800)" in t
    assert re.search(r"\.toast button\.x\{[^}]*min-width:24px;min-height:24px", CSS), "a 24px target (WCAG 2.5.8)"


def test_both_ways_a_build_ends_use_the_same_notice_and_say_how_it_ended():
    assert "buildFinished(id, true," in fn("follow") and "buildFinished(id, false," in fn("follow")
    other = fn("finishedElsewhere")
    assert '/api/job?client=' in other and "CELEBRATED" in other
    assert "finishedElsewhere(was.building)" in fn("pollQueue")


# ------------------------------------------------------------------ 3. one screen-reader line
def test_no_list_or_card_is_a_live_region_only_the_toasts_and_the_status_line():
    pages = [PAGE] + [getattr(__import__(m), "VIEW", "") for m in ("sheila_hub_issues", "sheila_hub_votes", "sheila_hub_feedback")]
    live = [re.search(r'id="([^"]+)"', tag).group(1) for p in pages for tag in re.findall(r"<[^>]*aria-live=[^>]*>", p)]
    assert sorted(live) == ["sr", "toasts"], live
    assert re.search(r'<div id="sr" class="sr" role="status"', PAGE)


def test_filters_and_a_recalculation_are_announced_once():
    assert "sayCount()" in PAGE and "setTimeout(sayCount, 700)" in PAGE, "typing in the search box is announced once it settles"
    assert 'say("Figures updated.")' in LIFT.JS and "L.saying = true" in LIFT.JS


# ------------------------------------------------------------------ 5. the Lift Matrix overview keeps its bearings
def test_the_lift_overview_header_and_client_column_stay_in_view_on_a_solid_ground():
    css = LIFT.CSS
    assert re.search(r"#lm-ov \.lmwrap\{[^}]*max-height:[^}]*overflow:auto", css), "the table scrolls in its card, so sticky works"
    assert re.search(r"#lm-table thead th\{position:sticky;top:0;[^}]*background:var\(--sheet\)", css)
    assert re.search(r"#lm-table tbody td:first-child\{position:sticky;left:0;[^}]*background:var\(--sheet\)", css)
    assert "scroll-padding-top" in css, "a focused row is not hidden under the sticky header (WCAG 2.4.11)"


# ------------------------------------------------------------------ 6. red is for what broke
def test_live_reviews_expected_not_yet_is_neutral_and_never_outlined_red():
    js = LIVE.JS
    assert 'chip k-idle">${si("idle")}Nothing to show yet' in js
    assert "stopc" not in js
    assert 'chip k-blocked">${si("blocked")}Could not open' in js, "a real failure keeps its red chip"


# ------------------------------------------------------------------ 7. single-key shortcuts can be turned off
def test_single_key_shortcuts_can_be_turned_off_and_ctrl_k_still_works():
    handler = PAGE.split('document.addEventListener("keydown", e => {', 1)[1]
    ctrl_k, gate = handler.index('e.key.toLowerCase() === "k"'), handler.index("if (!KEYS_ON && k.length === 1)")
    assert ctrl_k < gate, "Ctrl K and Esc are handled before the switch is consulted"
    assert gate < handler.index("TABS[TAB].key(e) === true"), "a tab's own letter keys are switched off too"
    assert 'id="keyson"' in PAGE and 'recall("hub-keys") !== "off"' in PAGE
    assert "Turn single-key shortcuts off" in PAGE, "the way back is in Ctrl K, which never turns off"
    assert ':root[data-keys="off"] .btn kbd' in CSS, "no letter hints promising keys that do nothing"


# ------------------------------------------------------------------ 8. solid glass when transparency is off
def test_reduced_transparency_makes_the_glass_solid_in_both_themes():
    block = CSS.split("@media (prefers-reduced-transparency:reduce){", 1)[1]
    assert ":root:root:root{--glass:var(--sheet);--surface:var(--sheet)}" in block, \
        "outranks the dark theme's :root:not([data-theme=light]) so both themes go solid"
    assert "backdrop-filter:none!important" in block
