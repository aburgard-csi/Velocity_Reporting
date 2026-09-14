"""perf_marks — the square client mark on the performance page's ranked bars.

  * A curated `<id>_mark.png` always wins.
  * A leading icon is cut out of its wordmark; a pure wordmark is never cut mid-letter.
  * A near-square logo is used whole; no logo, or no usable part, is a monogram.
"""
from PIL import Image, ImageDraw

import perf_marks as M

NAVY = (0, 39, 76, 255)


def _quiet(*_a):
    pass


def _logo(folder, name, size, rects):
    im = Image.new("RGBA", size, (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    for r in rects:
        d.rectangle(r, fill=NAVY)
    p = folder / name
    im.save(p)
    return p


def _letters(x0, n):
    """n letter-like blocks, 30 wide with 5px spacing: a wordmark."""
    return [(x0 + i * 35, 20, x0 + i * 35 + 29, 79) for i in range(n)]


def test_monogram_skips_the_words_every_client_shares():
    assert M.monogram("Sugar River Bank") == "SR"
    assert M.monogram("The Summit FCU") == "S"
    assert M.monogram("Altamaha Bank and Trust Company") == "A"
    assert M.monogram("") == "?"


def test_a_leading_icon_is_cut_out_of_its_wordmark(tmp_path):
    p = _logo(tmp_path, "icon.png", (420, 100), [(10, 20, 69, 79)] + _letters(100, 9))
    m = M.mark_for("Austin Bank", p, None, tmp_path / "w")
    assert m["kind"] == "icon" and m["src"].startswith("data:image/png;base64,")


def test_a_pure_wordmark_is_a_monogram_never_a_cut_letter(tmp_path):
    p = _logo(tmp_path, "word.png", (420, 100), _letters(10, 11))
    assert M.mark_for("Brooks Bank", p, None, tmp_path / "w") == \
        {"kind": "monogram", "src": None, "mono": "B", "logo": True}


def test_a_near_square_logo_is_used_whole(tmp_path):
    p = _logo(tmp_path, "sq.png", (130, 100), [(10, 10, 119, 89)])
    assert M.mark_for("Ideal Credit Union", p, None, tmp_path / "w")["kind"] == "whole"


def test_a_curated_mark_wins_and_no_logo_is_a_monogram(tmp_path):
    word = _logo(tmp_path, "word.png", (420, 100), _letters(10, 11))
    cur = _logo(tmp_path, "1537_mark.png", (64, 64), [(8, 8, 55, 55)])
    assert M.mark_for("Brooks Bank", word, cur, tmp_path / "w")["kind"] == "curated"
    assert M.mark_for("Sugar River Bank", None, None, tmp_path / "w") == \
        {"kind": "monogram", "src": None, "mono": "SR", "logo": False}


def test_client_marks_reports_the_gaps_and_picks_up_a_curated_mark(tmp_path, monkeypatch):
    logos = tmp_path / "Logos"
    logos.mkdir()
    _logo(logos, "1537.png", (420, 100), _letters(10, 11))
    _logo(logos, "1204.png", (420, 100), [(10, 20, 69, 79)] + _letters(100, 9))
    monkeypatch.setattr(M, "logos_dir", lambda: logos)
    monkeypatch.setattr(M.R, "client_logo",
                        lambda cid: (logos / ("%s.png" % cid)) if (logos / ("%s.png" % cid)).exists() else None)
    said = []
    clients = [("1537", "Brooks Bank"), ("1204", "First State Bank - Michigan"), ("1038", "Sugar River Bank")]
    marks = M.client_marks(clients, tmp_path / "cache", log=said.append)
    assert [marks[c]["kind"] for c in ("1537", "1204", "1038")] == ["monogram", "icon", "monogram"]
    gaps = [s for s in said if "_mark.png" in s]
    assert gaps and "1537" in gaps[0] and "1038" not in gaps[0], "only a client WITH a logo needs a curated mark"
    # a curated mark added later is picked up past the cache
    _logo(logos, "1537_mark.png", (64, 64), [(8, 8, 55, 55)])
    assert M.client_marks(clients[:1], tmp_path / "cache", log=_quiet)["1537"]["kind"] == "curated"
