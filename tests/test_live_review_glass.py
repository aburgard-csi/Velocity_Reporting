"""Live Review's liquid-glass surfaces (Aaron, 2026-11-04): the tokens exist for both themes, the page works with no blur
and with less transparency asked for, nothing reaches the network, and text stays legible on the translucent layers.

Reads only the bundled stylesheet; nothing here touches the share.
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")]

from review_page.page import render_page                       # noqa: E402

CSS_PATH = os.path.join(REPO, "build", "review_page", "static", "live.css")
GLASS_TOKENS = ["--page", "--stage", "--stage-line", "--card-a", "--card-b", "--rim", "--rim-low", "--glass-shadow", "--sheen",
                "--pill", "--pill-ink", "--tbl", "--gl", "--drawer", "--bar-a", "--bar-b"]


def _css():
    return open(CSS_PATH, encoding="utf-8").read()


def _block(css, opener):
    """The body of the first rule that starts with `opener`, braces balanced."""
    i = css.index(opener) + len(opener)
    depth, j = 1, i
    while depth:
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        j += 1
    return css[i:j - 1]


def _tokens(body):
    return dict(re.findall(r"(--[a-z0-9-]+):([^;]+);", body))


def _themes():
    css = _css()
    light = _tokens(_block(css, ":root{"))
    dark_media = _tokens(_block(_block(css, "@media (prefers-color-scheme:dark){"), ':root:not([data-theme="light"]){'))
    dark_attr = _tokens(_block(css, ':root[data-theme="dark"]{'))
    return light, dark_media, dark_attr


def test_every_glass_token_is_defined_for_light_and_redefined_for_dark():
    light, dark_media, dark_attr = _themes()
    for tok in GLASS_TOKENS:
        assert tok in light, "%s is not defined in :root" % tok
        assert tok in dark_media, "%s is not redefined for prefers-color-scheme: dark" % tok
        assert tok in dark_attr, "%s is not redefined for [data-theme=dark]" % tok
    # the stamped override and the system preference must agree, or the theme button changes the look
    for tok in GLASS_TOKENS:
        assert dark_media[tok].strip() == dark_attr[tok].strip(), tok + " differs between the two dark blocks"


def test_the_palette_is_the_finance_dashboards_blue_glass_and_the_glass_only_adds_surfaces():
    """Aaron, 2026-11-06: "i don't like the orange highlight. use the color scheme from my financial dashboard."
    The highlight token keeps its old name (--orange) but is the dashboard's accent; the second chart series is its amber."""
    light, dark_media, _ = _themes()
    assert light["--orange"].strip().upper() == "#0E6FB0" and light["--navy"].strip().upper() == "#00274C"
    assert dark_media["--orange"].strip().upper() == "#58B6EC"
    assert light["--c-orange"].strip().upper() == "#D08A1A" and dark_media["--c-orange"].strip().upper() == "#E5B15B"
    assert "#F15D22" not in _css().upper().replace("#F15D22;border", "")   # no orange highlight left, but for the title card's deck wedge


def test_blur_has_a_fallback_and_less_transparency_is_honoured():
    css = _css()
    assert css.count("backdrop-filter") == css.count("-webkit-backdrop-filter") * 2   # every blur carries its prefixed twin
    assert "@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px)))" in css
    assert "prefers-reduced-transparency:reduce" in css and "prefers-contrast:more" in css
    assert "prefers-reduced-motion:reduce" in css
    # the fallback surfaces are opaque
    fb = _block(css, "@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){")
    toks = _tokens(_block(fb, ":root{"))
    for tok in ("--stage", "--card-a", "--card-b"):
        assert toks[tok].strip().startswith("#"), tok + " must be a solid color without blur"


def test_the_page_is_inline_and_reaches_nowhere():
    css = _css()
    for ref in re.findall(r"url\(([^)]*)\)", css):
        ref = ref.strip("'\" ")
        assert ref.startswith(("/fonts/", "data:")), "stylesheet loads %r" % ref
    html = render_page({"client": {"id": "9999", "name": "Test Bank"}, "programs": [], "month": "October 2026"}, "tok")
    assert "html::before" in html and "--stage" in html
    assert "http://" not in html.replace("http://www.w3.org", "") and "https://" not in html


# ---- legibility on glass: every translucent layer composited over the page's darkest and brightest points
def _rgba(v):
    v = v.strip()
    if v.startswith("#"):
        h = v[1:]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), 1.0
    m = re.match(r"rgba?\(([^)]*)\)", v)
    p = [x.strip() for x in m.group(1).split(",")]
    return tuple(float(x) for x in p[:3]), float(p[3]) if len(p) > 3 else 1.0


def _over(top, bottom):
    (c, a), b = top, bottom
    return tuple(a * x + (1 - a) * y for x, y in zip(c, b))


def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + .05) / (lb + .05)


# the page behind everything: its darkest corner and its brightest glow, in each theme
# (the darkest corner, the orange glow over the blue, the blue lobe)
BACKDROPS = {"light": [(2, 19, 42), (65, 72, 95), (5, 84, 139)], "dark": [(3, 10, 20), (51, 52, 68), (12, 49, 90)]}


def test_text_keeps_aa_contrast_on_the_stage_and_on_cards_in_both_themes():
    light, dark_media, _ = _themes()
    for name, toks in (("light", light), ("dark", dark_media)):
        for back in BACKDROPS[name]:
            stage = _over(_rgba(toks["--stage"]), back)
            cards = [_over(_rgba(toks["--card-a"]), stage), _over(_rgba(toks["--card-b"]), stage)]
            for surface, label in [(stage, "stage")] + [(c, "card") for c in cards]:
                for role in ("--ink", "--text2", "--navy"):
                    fg, _a = _rgba(toks[role])
                    r = _ratio(fg, surface)
                    assert r >= 4.5, "%s: %s on the %s over %s is %.2f:1" % (name, role, label, back, r)


def _all_blocks(css, opener):
    out, i = [], css.find(opener)
    while i >= 0:
        out.append(_block(css[i:], opener))
        i = css.find(opener, i + len(opener))
    return out


def _product_inks():
    """--p-<product> as the eyebrow uses it: the :root values for light, the dark override for dark."""
    css = _css()
    light = next(b for b in _all_blocks(css, ":root{") if "--pf-rems" in b)
    dark = next(b for b in _all_blocks(css, ':root:not([data-theme="light"]){') if "--p-rems" in b)
    return {"light": _tokens(light), "dark": _tokens(dark)}


def test_the_product_eyebrows_the_orange_ink_and_the_notes_keep_aa_contrast_on_the_glass():
    light, dark_media, _ = _themes()
    inks = _product_inks()
    keys = {k for k in inks["light"] if k.startswith("--p-")}
    assert keys and keys == {k for k in inks["dark"] if k.startswith("--p-")}
    for name, toks in (("light", light), ("dark", dark_media)):
        for back in BACKDROPS[name]:
            stage = _over(_rgba(toks["--stage"]), back)
            cards = [_over(_rgba(toks["--card-a"]), stage), _over(_rgba(toks["--card-b"]), stage)]
            for key in sorted(keys) + ["--orange-ink"]:
                val = inks[name][key] if key in inks[name] else toks[key]
                for surface in [stage] + cards:
                    r = _ratio(_rgba(val)[0], surface)
                    assert r >= 4.5, "%s: %s on the glass over %s is %.2f:1" % (name, key, back, r)
        # a note's text sits on --fill inside the stage
        assert _ratio(_rgba(toks["--warn"])[0], _rgba(toks["--fill"])[0]) >= 4.5, name + ": --warn on --fill"


def test_the_dark_glass_bar_and_the_orange_pill_keep_aa_contrast():
    light, dark_media, _ = _themes()
    for name, toks in (("light", light), ("dark", dark_media)):
        # the bar can sit over the light stage when the page scrolls under it: the worst case
        for back in BACKDROPS[name] + [_over(_rgba(toks["--stage"]), BACKDROPS[name][1])]:
            for key in ("--bar-a", "--bar-b"):
                bar = _over(_rgba(toks[key]), back)
                for fg in ((242, 246, 252), (189, 203, 222)):      # --ink / --text2 as the bar scopes them
                    assert _ratio(fg, bar) >= 4.5, "%s: %s on the bar over %s" % (name, fg, back)
    for stop in ((245, 122, 71), (224, 82, 26)):                    # the active pill's gradient, dark ink on it
        assert _ratio((11, 26, 43), stop) >= 4.5


def test_the_rail_scrolls_under_its_border_not_over_it():
    """Aaron, 2026-11-06: "the item labels should slide under the side bar border, not over it". The rail scrolls its own list. Its
    lit top edge was an inset box-shadow (painted beneath the content) and 18px of padding above the first item was part of the
    scrolling area, so a scrolled label crossed the lit edge. The edge is the border now (content is clipped inside a border), there
    is no padding to scroll into, and the old padding is two spacers that scroll away with the list. The phone's bottom bar has none."""
    css = _css()
    rail = re.search(r"\.rail\{top:90px;[^}]*\}", css).group(0)
    assert "padding:0 10px" in rail
    after = css[css.index(rail):]
    assert ".rail{box-shadow:0 24px 50px -24px rgba(0,0,0,.7);border-top-color:" in after
    assert '.rail::before,.rail::after{content:"";display:block;height:18px}' in after
    narrow = after[after.index("@media (max-width:860px)"):]
    assert ".rail::before,.rail::after{display:none}" in narrow
