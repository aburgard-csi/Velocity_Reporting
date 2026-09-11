"""The performance page: its CashPlease extractor resolves, and an export stands alone.

Both tests exist because of the same morning (2026-09-11). CashPlease moved into this
repo on 2026-09-10 and `refresh_performance_dashboard` went on looking for the old
standalone checkout, so every CashPlease figure on the page reported missing — for all
eight CP clients — and the refresh still exited `changed`, ready to publish a page with
a hole in it. Nothing failed; the section was simply absent.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "build"))

import refresh_performance_dashboard as RP  # noqa: E402


def test_cp_extractor_resolves_in_repo():
    """The extractor is found, and it is the one in THIS repo.

    Asserting "not None" alone would have passed on the broken morning for anyone
    with a pre-migration checkout beside the repo; the path is what matters.
    """
    p = RP.cp_extractor()
    assert p is not None, "cp_extract.py not found — the CashPlease section would be blank"
    assert p == REPO / "build" / "cashplease_pipeline" / "cp_extract.py", p
    assert p.exists()


def test_cp_extractor_takes_the_workbook_and_out_dir_it_is_given():
    """cp_extract's CLI is 3 or 4 args — workbook, out dir, optional DDA counts.
    The refresh builds that command by hand, so a change on either side breaks quietly."""
    src = (REPO / "build" / "cashplease_pipeline" / "cp_extract.py").read_text(encoding="utf-8")
    assert "len(sys.argv) not in (3, 4)" in src, \
        "cp_extract's argument count changed; refresh_performance_dashboard builds that command"


def _export():
    html = "<title>t</title>\n<style>body{color:red}</style>\n<div class='wrap'>x</div>"
    return RP.standalone(html, "2026.09", exported="2026-09-11 09:00")


def test_export_is_a_whole_document():
    """A file a coworker opens has no publisher to wrap it: it carries its own skeleton."""
    out = _export()
    assert out.startswith("<!doctype html>")
    assert out.rstrip().endswith("</html>")
    head = out.split("</head>", 1)[0]
    # charset before any content, or the em dashes and the · separators render as mojibake
    assert '<meta charset="utf-8">' in head
    assert "<title>RPE Client Performance September 2026</title>" in head
    assert "viewport" in head
    assert out.count("<body>") == 1 and out.count("</body>") == 1


def test_export_says_it_is_a_snapshot():
    """The page's own pill says "Last updated", which reads as a page that keeps
    updating. A copy passed around never will, and cannot be asked when it is from."""
    out = _export()
    assert "Static copy" in out
    assert "September 2026" in out
    assert "2026-09-11 09:00" in out


def test_export_fetches_nothing_but_the_webfont():
    """Self-contained: the dataset is embedded and both charts are hand-built SVG, so a
    file on a share renders with no network beyond the font — which has a fallback stack."""
    tpl = (REPO / "scripts" / "perf_dashboard_template.html").read_text(encoding="utf-8")
    urls = set(re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', tpl))
    assert urls <= {"https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700"
                    "&family=Carlito:ital,wght@0,400;0,700;1,400&display=swap"}, urls
    assert "Carlito,Calibri," in tpl, "the webfont needs a local fallback stack"
