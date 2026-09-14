#!/usr/bin/env python3
"""
perf_marks.py — the square client mark beside each name on the performance page's ranked bars.

Aaron chose concept A, a favicon-sized mark per client (2026-09-14). Client logos are
wordmarks far more often than square icons (the roster runs 1.56 to 8.8 wide-to-tall), so
the mark is CHOSEN, in this order:

  1. curated   `Inputs/Logos/<id>_mark.png`, a square mark made for this. Always wins.
  2. icon      the logo leads with an icon set apart from its wordmark by a clear gap;
               the icon alone is used.
  3. whole     the whole logo, when it is near enough to square (<= 1.6:1) to read at 22px.
  4. monogram  the client's initials. A wide wordmark shrunk to 22px cannot be read, and
               cropping its left edge cuts a letter in half: the concepts page showed exactly
               that on Brooks Bank.

A client that has a logo but still falls to a monogram is reported by the refresh, because
a curated mark is the fix. Marks are cached in `<cache>/marks.json`, keyed on each logo
file's name, size and time, so a morning refresh does not re-read 6,000-pixel artwork.
"""
import base64
import io
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "build") not in sys.path:
    sys.path.insert(0, str(REPO / "build"))
import rpe_env as R                                              # noqa: E402

MARK_VERSION = "1"          # bump when the choice below changes, so cached marks rebuild
MARK_PX = 48                # drawn at 22 CSS px; 48 keeps it sharp on a 2x screen
WHOLE_MAX_ASPECT = 1.6
KINDS = ("curated", "icon", "whole", "monogram")
_STOP = {"bank", "credit", "union", "fcu", "cu", "ccu", "the", "of", "and", "trust",
         "company", "federal", "na", "sb"}


def monogram(name):
    """One or two initials, skipping the words every bank and credit union shares."""
    words = [w for w in re.split(r"[\s\-&/,.]+", str(name or "")) if w and w.lower() not in _STOP]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    if words:
        return words[0][0].upper()
    return "?"


def _ink(im):
    """An L mask of the pixels that are artwork: visible and not near-white."""
    from PIL import ImageChops
    r, g, b, a = im.convert("RGBA").split()
    white = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v > 235 else 0),
                                                    g.point(lambda v: 255 if v > 235 else 0)),
                                b.point(lambda v: 255 if v > 235 else 0))
    return ImageChops.multiply(a.point(lambda v: 255 if v > 40 else 0), ImageChops.invert(white))


def _tight(im):
    box = _ink(im).getbbox()
    return im.crop(box) if box else im


def find_icon(im):
    """(left, right) pixel columns of a leading icon in a tightly cropped logo, or None.

    Scans the artwork at 64px tall from the left for the first clear vertical gap: at least
    12% of the height, wider than the spacing between letters. What sits before that gap
    is an icon if it is roughly square (0.45 to 1.6 times the height) and more artwork
    follows. Only the LEADING element is considered; a first word is too wide to qualify.
    """
    from PIL import Image
    h = 64
    w = max(1, round(im.width * h / im.height))
    mask = _ink(im).resize((w, h), Image.BILINEAR).load()
    cols = [any(mask[x, y] > 0 for y in range(h)) for x in range(w)]
    gap_min = max(3, round(0.12 * h))
    x = 0
    while x < w and not cols[x]:
        x += 1
    start, run = x, 0
    while x < w:
        if cols[x]:
            run = 0
        else:
            run += 1
            if run >= gap_min:
                seg_end = x - run + 1
                seg = seg_end - start
                if 0.45 * h <= seg <= 1.6 * h and any(cols[x:]) and (w - seg_end) >= 0.5 * h:
                    k = im.width / w
                    return int(start * k), int(round(seg_end * k))
                return None
        x += 1
    return None


def _square_uri(im):
    from PIL import Image
    im = im.convert("RGBA")
    side = max(im.width, im.height)
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    canvas = canvas.resize((MARK_PX, MARK_PX), Image.LANCZOS)
    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def mark_for(name, logo, curated, work):
    """{"kind", "src", "mono", "logo"} for one client. Never raises: a bad file is a monogram."""
    from PIL import Image
    mono = monogram(name)
    if curated:
        try:
            with Image.open(curated) as im:
                return {"kind": "curated", "src": _square_uri(_tight(im.convert("RGBA"))),
                        "mono": mono, "logo": True}
        except Exception:
            pass
    if not logo:
        return {"kind": "monogram", "src": None, "mono": mono, "logo": False}
    try:
        os.makedirs(str(work), exist_ok=True)
        with Image.open(R.trim_logo(str(logo), str(work))) as im0:
            im = _tight(im0.convert("RGBA"))
        icon = find_icon(im)
        if icon:
            return {"kind": "icon", "src": _square_uri(_tight(im.crop((icon[0], 0, icon[1], im.height)))),
                    "mono": mono, "logo": True}
        if im.width / im.height <= WHOLE_MAX_ASPECT:
            return {"kind": "whole", "src": _square_uri(im), "mono": mono, "logo": True}
    except Exception:
        pass
    return {"kind": "monogram", "src": None, "mono": mono, "logo": True}


def logos_dir():
    """The folder `rpe_env.client_logo` reads, where a curated `<id>_mark.png` sits too."""
    try:
        return R.data_root() / "Inputs" / "Logos"
    except SystemExit:
        return None


def _stamp(p):
    if not p:
        return "-"
    try:
        st = os.stat(p)
        return "%s:%d:%d" % (Path(p).name, st.st_size, int(st.st_mtime))
    except OSError:
        return "-"


def client_marks(clients, cache_dir, log=print):
    """{id: mark} for an iterable of (id, name), cached in `<cache_dir>/marks.json`."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    idx_p = cache_dir / "marks.json"
    try:
        idx = json.loads(idx_p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        idx = {}
    folder = logos_dir()
    out, fresh = {}, {}
    for cid, name in clients:
        logo = R.client_logo(cid)
        cur = (folder / ("%s_mark.png" % cid)) if folder else None
        cur = cur if cur is not None and cur.is_file() else None
        sig = "|".join([MARK_VERSION, str(name), _stamp(logo), _stamp(cur)])
        hit = idx.get(cid)
        mark = hit["mark"] if isinstance(hit, dict) and hit.get("sig") == sig else mark_for(name, logo, cur, cache_dir / "trim")
        out[cid] = mark
        fresh[cid] = {"sig": sig, "mark": mark}
    tmp = idx_p.with_suffix(".json.part")
    tmp.write_text(json.dumps(fresh), encoding="utf-8")
    tmp.replace(idx_p)
    log("marks: " + ", ".join("%d %s" % (sum(m["kind"] == k for m in out.values()), k) for k in KINDS))
    need = sorted(cid for cid, m in out.items() if m["kind"] == "monogram" and m["logo"])
    if need:
        log("marks: logo on file but no square mark could be cut from it; add "
            "Inputs/Logos/<id>_mark.png for: " + " ".join(need))
    return out
