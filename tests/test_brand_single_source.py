"""The brand orange is defined once (build/brand.py), and the template shells carry the current one.

Two builders wrote their own `RGBColor(0xF4, 0x7A, 0x29)`, so when the Sept. 2026 brand template moved the
orange they kept drawing the old one: six MRPC pills and the Contact slide's accent came out in the retired colour
on a deck whose every other orange had changed (found 2026-10-26 by counting colours in a rebuilt deck).
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "scripts")]
import brand  # noqa: E402
import recolor_shells  # noqa: E402


def _forms(hex6):
    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return [hex6, f"0x{r:02X}, ?0x{g:02X}, ?0x{b:02X}", rf"\({r}, ?{g}, ?{b}\)"]


def test_no_builder_writes_the_orange_itself():
    """Everything but brand.py reaches the orange by name (brand.ORANGE / ORANGE_RGB)."""
    patterns = [p for hx in (brand.ORANGE.lstrip("#"), *recolor_shells.RECOLOR) for p in _forms(hx.upper())]
    rx = re.compile("|".join(patterns), re.I)
    offenders = []
    for path in sorted((REPO / "build").rglob("*.py")):
        if path.name == "brand.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if rx.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{n}")
    assert not offenders, "orange written as a literal; use brand.ORANGE_RGB / brand.ORANGE:\n" + "\n".join(offenders)


def test_the_template_shells_hold_no_retired_colour():
    left = {Path(p).name: recolor_shells.count_old(p) for p in recolor_shells.shells() if Path(p).exists()}
    assert not any(left.values()), f"run scripts/recolor_shells.py: {left}"


def test_the_shells_use_the_orange_brand_defines():
    assert brand.ORANGE.lstrip("#").upper() == "F15D22"
    assert "F15D22" not in recolor_shells.RECOLOR            # the new colour is a target, never a source
    assert recolor_shells.RECOLOR and all(new == brand.ORANGE.lstrip("#").upper() for new in recolor_shells.RECOLOR.values())


def test_recolor_rewrites_the_colours_and_copies_every_other_part_unchanged(tmp_path):
    import zipfile
    old, new = next(iter(recolor_shells.RECOLOR.items()))
    p = tmp_path / "shell.pptx"
    blob = bytes(range(256)) * 4
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/slides/slide1.xml", f'<a:srgbClr val="{old}"/><a:srgbClr val="{old.lower()}"/><a:srgbClr val="00274C"/>')
        z.writestr("ppt/media/image1.png", blob)
    assert recolor_shells.count_old(str(p)) == 2
    assert recolor_shells.recolor(str(p)) == 2
    with zipfile.ZipFile(p) as z:
        xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
        assert xml.count(new) == 2 and old.lower() not in xml.lower() and "00274C" in xml
        assert z.read("ppt/media/image1.png") == blob and z.read("[Content_Types].xml") == b"<Types/>"
        assert z.testzip() is None
    assert recolor_shells.recolor(str(p)) == 0                      # idempotent
    assert not list(tmp_path.glob("*.part"))                       # no half-written leftover
