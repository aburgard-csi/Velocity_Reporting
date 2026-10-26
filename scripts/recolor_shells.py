"""Recolour the literal brand colours inside the template shells (the .pptx files, not the builders).

The shells carry their colours as literal `srgbClr` values, not theme colours (their theme is the stock Office
one), so changing `build/brand.py` alone leaves every shape and table the shells draw in the old colour. This
rewrites each shell's XML parts with the colour changes in RECOLOR and copies every other part byte for byte.
Idempotent: a second run finds nothing to change.

    python scripts/recolor_shells.py            # rewrite templates/*.pptx and build/assets/summit_slide.pptx
    python scripts/recolor_shells.py --check    # change nothing; exit 1 if any shell still holds an old colour

First use: the Sept. 2026 brand template moves CSI Orange from F47A29 to F15D22 (Aaron, 2026-10-26).
"""
import argparse
import glob
import os
import re
import shutil
import sys
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECOLOR = {"F47A29": "F15D22"}                 # old -> new, six hex digits, upper case
EXTRA = [os.path.join("build", "assets", "summit_slide.pptx")]
_PARTS = re.compile(r"^ppt/.+\.xml$")           # slides, layouts, masters, theme, charts, notes ...


def shells():
    return sorted(glob.glob(os.path.join(REPO, "templates", "*.pptx"))) + [os.path.join(REPO, p) for p in EXTRA]


def _recolour(xml):
    n = 0
    for old, new in RECOLOR.items():
        xml, k = re.subn(old, new, xml, flags=re.I)
        n += k
    return xml, n


def count_old(path):
    """How many old-colour literals the shell still holds."""
    total = 0
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if _PARTS.match(n):
                text = z.read(n).decode("utf-8", "ignore")
                total += sum(len(re.findall(old, text, flags=re.I)) for old in RECOLOR)
    return total


def recolor(path):
    """Rewrite `path` in place. Returns the number of literals changed."""
    changed = 0
    fd, tmp = tempfile.mkstemp(suffix=".pptx", dir=os.path.dirname(path))
    os.close(fd)
    try:
        with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if _PARTS.match(info.filename):
                    text = data.decode("utf-8")
                    text, k = _recolour(text)
                    if k:
                        data, changed = text.encode("utf-8"), changed + k
                zout.writestr(info, data, compress_type=info.compress_type)
        if changed:
            shutil.move(tmp, path)
        else:
            os.remove(tmp)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if an old colour remains")
    a = ap.parse_args(argv)
    left = 0
    for p in shells():
        if not os.path.exists(p):
            continue
        name = os.path.relpath(p, REPO)
        if a.check:
            k = count_old(p)
            left += k
            print(f"{name}: {k} old-colour literal(s)")
        else:
            print(f"{name}: {recolor(p)} changed")
    return 1 if (a.check and left) else 0


if __name__ == "__main__":
    sys.exit(main())
