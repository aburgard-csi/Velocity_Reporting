"""CSM Sheila's page draws only defined colours, in the current brand orange, with legible small text (2026-11-02).

Three defects were found reading the page against the Hub sample: the old CSI orange #F47A29 (and its rgba glows)
was still drawn, two rules named variables the page never defined (--rowalt, --muted, so the hover and the report
dialog's labels fell back to nothing), and the label grey --ink3 (#8793A0) measured 3.1:1 on white, below the
4.5:1 small text needs."""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import ars_launcher_web as W  # noqa: E402


def _lum(hx):
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def _ratio(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def _tokens(block):
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", block))


def _light_dark():
    css = W.PAGE.split("<style>", 1)[1].split("</style>", 1)[0]
    light = css.split("@media (prefers-color-scheme: dark)", 1)[0]
    dark = css.split("@media (prefers-color-scheme: dark)", 1)[1].split("*{box-sizing", 1)[0]
    return css, _tokens(light), {**_tokens(light), **_tokens(dark)}


def test_the_old_orange_is_gone():
    css, _, _ = _light_dark()
    assert "F47A29" not in W.PAGE.upper() and "244,122,41" not in W.PAGE.replace(" ", "")
    assert "--orange:#F15D22" in css


def test_every_variable_the_page_uses_is_defined():
    css, _, _ = _light_dark()
    used = set(re.findall(r"var\(--([a-z0-9-]+)", W.PAGE))
    defined = set(re.findall(r"(?<![a-z0-9-])--([a-z0-9-]+)\s*:", W.PAGE))
    assert not (used - defined), sorted(used - defined)


def test_the_label_grey_reads_in_both_themes():
    _, light, dark = _light_dark()
    for theme, grounds in ((light, ("surface", "ground", "soft", "sel", "rule")), (dark, ("surface", "ground", "soft", "sel", "rule"))):
        for bg in grounds:
            assert _ratio(theme["ink3"], theme[bg]) >= 4.5, (theme["ink3"], bg, _ratio(theme["ink3"], theme[bg]))
            assert _ratio(theme["ink2"], theme[bg]) >= 4.5, (theme["ink2"], bg)
