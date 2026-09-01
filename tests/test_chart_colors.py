"""A chart mark is never drawn in the canvas color.

The MRPC Retention "Still Active" line was drawn `color='white'` on a white
canvas (STYLE.md said to, so it would read over the navy bars). Over the bars it
did; across the gaps BETWEEN bars, and above any bar top, it vanished. Every
2026.08 MRPC deck shipped a retention line that was invisible for its whole
length -- only the ringed markers survived, and the legend swatch was blank too.

The same mistake had a second form one layer down: the Enrollments VALUE LABELS
on MRPC Performance vs Goal were white as well, so on Capital Bank 1502 the five
zero-enrollment months -- which have no bar behind them -- printed white on white.

Both fixed 2026-09-01 by casing the mark (navy core, white stroke) instead of
coloring it. This test is the check that would have caught them: it reads the
renderers rather than the rendered PNGs, so it needs no client data and no
fixture month.
"""
import re
from pathlib import Path

import pytest

BUILD = Path(__file__).resolve().parent.parent / "build"

RENDERERS = sorted(p for p in BUILD.rglob("*.py") if "chart" in p.name)

_WHITE = r"""['"](?:white|\#fff|\#ffffff)['"]"""

# `color=` / `c=` on a call that DRAWS a mark, set to the canvas color. Marker
# faces (mfc=), bbox and patch fills (fc=), and wedge/bar edges (edgecolor=) are
# deliberately white -- a white marker with a navy ring, a white pad masking a
# line behind a label, a white separator between stacked segments are all
# legible by design -- so only the color of the mark itself is policed.
CANVAS_COLOR = re.compile(
    r"""\b(?:ax\d?|plt)\.(?:plot|fill_between|step|axhline|axvline|text|annotate)\(
        [^\n]*?
        (?<![a-z])(?:color|c)\s*=\s*""" + _WHITE,
    re.IGNORECASE | re.VERBOSE,
)


def test_there_are_renderers_to_check():
    """A rename that empties the list must fail loudly, not pass vacuously."""
    assert RENDERERS, f"no chart renderers found under {BUILD}"


@pytest.mark.parametrize("path", RENDERERS, ids=lambda p: p.name)
def test_no_mark_is_drawn_in_the_canvas_color(path):
    hits = [
        f"{path.name}:{i}: {line.strip()}"
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if CANVAS_COLOR.search(line)
    ]
    assert not hits, (
        "mark drawn in the canvas color -- invisible wherever it is not over a "
        "dark bar. Case it instead (navy core + white stroke), as "
        "mrpc_charts_gen._overlay_line / _cased_text do:\n  " + "\n  ".join(hits)
    )
