"""rpe_env.trim_logo: crop to the artwork without cutting the artwork (2026-09-15).

1776 CoastHills' transparent logo runs to all four edges. trim_logo took the full-canvas alpha box
as an opaque canvas, sampled the border (the green lettering) as the background and cropped the
lettering off: the agenda slide showed a 1600x294 slice of a 1600x384 logo. 21 of 122 logos in
Inputs/Logos were clipped the same way. The first two cases here are the ones that must keep working.
"""
import os
import sys

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
import rpe_env as R  # noqa: E402

GREEN = (0, 103, 71, 255)
BLUE = (108, 196, 234, 255)


def size_after_trim(path, tmp_path):
    out = R.trim_logo(str(path), str(tmp_path / "out"))
    return Image.open(out).size


def test_an_opaque_white_canvas_is_trimmed_to_the_logo(tmp_path):
    # 1549 Wellworth: artwork in one corner of an opaque white canvas.
    im = Image.new("RGBA", (1000, 500), (255, 255, 255, 255))
    ImageDraw.Draw(im).rectangle((20, 20, 219, 119), fill=GREEN)
    p = tmp_path / "canvas.png"
    im.save(p)
    w, h = size_after_trim(p, tmp_path)
    assert w < 300 and h < 200


def test_transparent_padding_is_trimmed_to_the_alpha_box(tmp_path):
    # 1676 True Sky: most of the canvas is transparent margin.
    im = Image.new("RGBA", (1000, 500), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((300, 200, 599, 299), fill=GREEN)
    p = tmp_path / "padded.png"
    im.save(p)
    w, h = size_after_trim(p, tmp_path)
    assert 300 <= w <= 320 and 100 <= h <= 110


def test_a_transparent_logo_touching_every_edge_is_not_clipped(tmp_path):
    # 1776 CoastHills: green lettering at the top, bottom and sides, a blue swoosh, transparent around it.
    im = Image.new("RGBA", (1600, 384), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in range(0, 1600, 160):
        d.rectangle((x, 0, x + 60, 383), fill=GREEN)        # letter stems run edge to edge
    d.line((0, 383, 1599, 120), fill=BLUE, width=14)
    p = tmp_path / "edge_to_edge.png"
    im.save(p)
    w, h = size_after_trim(p, tmp_path)
    assert w >= 1590 and h >= 380, f"logo clipped to {w}x{h}"
