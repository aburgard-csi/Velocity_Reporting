"""
The STANDARD slides of the ILS Program Analysis deck: the agenda, and the industry / regulatory update that is the
same for every client in a cycle (the analysis team's "Regulatory Analysis, <month year>" block and the consumer
survey slide).

The industry content is DATA, not code: it changes every cycle and it is not a client figure, so it lives in
`<Build Artifacts>/ils_analysis/standard/industry_<yyyy-mm>.json` (the newest file wins) and is read through
`rpe_env.build_artifacts()`. A deck with no such file has no industry section and says so on the Data Notes page;
nothing is invented. Every slide's speaker note names the file and the edition, and carries the source line the
content gave. This module checks nothing about the law: the figures and dates are the analysis team's, as delivered
in their annual review decks, and are reproduced as given.

File shape::

    {"edition": "August 2026", "origin": "analysis team's Regulatory Analysis, August 2026",
     "slides": [
       {"kind": "stats",  "title": ..., "subtitle": ..., "source": ..., "stats": [{"value": "70%", "label": ...}, ...]},
       {"kind": "points", "title": ..., "subtitle": ..., "source": ..., "points": [{"head": ..., "text": ...}, ...]},
       {"kind": "table",  "title": ..., "subtitle": ..., "source": ..., "headers": [...], "rows": [[...]], "foot": ...},
       # November 2026 kinds, after the analysis team's Northwest Bank review slides:
       {"kind": "cards", ..., "cards": [{"status": "enacted|signed|proposed|pending", "label": ..., "head": ..., "bullets": [...]}]},
       {"kind": "hero_table", ..., "heroes": [{"value": ..., "label": ...}], "list_head": ..., "list": [...],
        "headers": [...], "rows": [[...]], "col_share": [...]},
       {"kind": "chips", ..., "intro": ..., "chips_head": ..., "chips": [...]},
       {"kind": "dated", ..., "items": [[date, text], ...]}]}
"""
from __future__ import annotations

import glob
import json
import os

import shapes
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

from . import client_slides as CS
from . import theme as T

import brand                                                    # noqa: E402  (build/ is on sys.path via theme)
import rpe_env                                                  # noqa: E402

MAX_POINTS = 5
MAX_TABLE_ROWS = 8


def standard_dir(cfg):
    d = getattr(cfg, "standard_dir", None)
    if d:
        return str(d)
    return os.path.join(str(rpe_env.build_artifacts()), "ils_analysis", "standard")


def load_industry(cfg):
    """(content dict, path) of the newest industry_*.json, or (None, reason)."""
    folder = standard_dir(cfg)
    files = sorted(glob.glob(os.path.join(folder, "industry_*.json")))
    if not files:
        return None, f"no industry_<yyyy-mm>.json in {folder}"
    path = files[-1]
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), path
    except (OSError, ValueError) as exc:
        return None, f"{os.path.basename(path)} could not be read ({type(exc).__name__}: {exc})"


def _notes(slide, say, content, path, source):
    slide.notes_slide.notes_text_frame.text = (
        f"Say first: {say}\n"
        f"Source: {source or 'the analysis team industry update'}. Standard content for every client in the cycle, edition "
        f"{content.get('edition', 'n/a')}, read from {os.path.basename(path)}; reproduced as delivered in the analysis team's "
        f"decks and not verified independently. Not legal advice. No client data on this slide.")


def _stats(dk, cfg, c, path, spec, section):
    stats = spec.get("stats", [])[:3]
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    n = max(1, len(stats))
    gap = 0.3
    w = (CS.FULL_W - (n - 1) * gap) / n
    for i, st in enumerate(stats):
        x = CS.LEFT + i * (w + gap)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.1), Inches(w), Inches(3.0))
        card.fill.solid()
        card.fill.fore_color.rgb = T.BAND
        card.line.fill.background()
        shapes.shadow(card)
        shapes.textbox(s, x, 2.3, w, 1.2, st["value"], 54, T.NAVY, True, PP_ALIGN.CENTER, T.HEAD, MSO_ANCHOR.MIDDLE)
        shapes.textbox(s, x + 0.25, 3.6, w - 0.5, 1.3, st["label"], 18, T.SUBTLE, False, PP_ALIGN.CENTER, T.BODY, MSO_ANCHOR.TOP)
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 5.6, CS.FULL_W, 0.4, "Source: " + spec["source"], 13, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "Consumers value the overdraft service, which is the backdrop for this review."), c, path, spec.get("source"))
    return s


def _points(dk, cfg, c, path, spec, section):
    pts = spec.get("points", [])[:MAX_POINTS]
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    y = 1.80
    h = (6.55 - y) / max(1, len(pts))
    for p in pts:
        shapes.textbox(s, CS.LEFT, y, CS.FULL_W, 0.34, p["head"], 17, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
        shapes.textbox(s, CS.LEFT, y + 0.36, CS.FULL_W, h - 0.40, p["text"], 14, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
        y += h
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 6.62, CS.FULL_W, 0.3, "Sources: " + spec["source"], 11, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "These are the points that matter for overdraft this cycle."), c, path, spec.get("source"))
    return s


def _table(dk, cfg, c, path, spec, section):
    rows = spec.get("rows", [])[:MAX_TABLE_ROWS]
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    bottom = CS.table(s, {"headers": spec["headers"], "rows": rows}, CS.LEFT, 1.85, CS.FULL_W, 4.3, max_fs=15)
    for shp in s.shapes:                                    # text columns read left to right, not centred
        if shp.has_table:
            for row in shp.table.rows:
                for cell in row.cells:
                    for para in cell.text_frame.paragraphs:
                        para.alignment = PP_ALIGN.LEFT
    if spec.get("foot"):
        shapes.textbox(s, CS.LEFT, min(6.15, bottom + 0.12), CS.FULL_W, 0.55, spec["foot"], 14, T.NAVY, True, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 6.68, CS.FULL_W, 0.3, "Sources: " + spec["source"], 11, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "This is the regulatory picture for the cycle."), c, path, spec.get("source"))
    return s


# status label colours: in force (teal), signed (navy), proposed or still moving (orange)
TONES = {"enacted": T.TEAL, "signed": T.NAVY, "proposed": T.ORANGE, "pending": T.ORANGE}


def _card_bg(slide, x, y, w, h, fill=None):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.adjustments[0] = 0.06
    card.fill.solid()
    card.fill.fore_color.rgb = fill or T.BAND
    card.line.fill.background()
    shapes.shadow(card)
    return card


def _pill(slide, x, y, text, fill, w=None):
    """A status label: white bold text on a coloured rounded bar (Tim's state cards' 'ENACTED — EFF. JAN 1, 2026')."""
    from textfit import text_width_in
    w = w or min(4.6, text_width_in(text, 11, "Montserrat", True) + 0.45)
    p = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.30))
    p.adjustments[0] = 0.5
    p.fill.solid()
    p.fill.fore_color.rgb = fill
    p.line.fill.background()
    shapes.textbox(slide, x, y, w, 0.30, text, 11, brand.WHITE_RGB, True, PP_ALIGN.CENTER, T.HEAD, MSO_ANCHOR.MIDDLE)
    return w


def _bullets(slide, x, y, w, h, items, size, color=None):
    color = color or T.SUBTLE
    T.bullets_real(slide, x, y, w, h, items, size=size, min_size=11)


def _cards(dk, cfg, c, path, spec, section):
    """Up to four cards in a 2 x 2 grid: a status label, a heading and three or four bullets each (the analysis team's
    State-Level Overdraft Rulemaking slide, November 2026)."""
    cards = spec.get("cards", [])[:4]
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    gap = 0.28
    cw = (CS.FULL_W - gap) / 2
    top, bottom = 1.80, 6.55
    ch = (bottom - top - gap) / 2
    for i, cd in enumerate(cards):
        x = CS.LEFT + (i % 2) * (cw + gap)
        y = top + (i // 2) * (ch + gap)
        _card_bg(s, x, y, cw, ch)
        _pill(s, x + 0.22, y + 0.18, cd.get("status", ""), TONES.get(cd.get("tone"), T.NAVY))
        shapes.textbox(s, x + 0.22, y + 0.56, cw - 0.44, 0.40, cd["head"], 17, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
        _bullets(s, x + 0.22, y + 1.00, cw - 0.44, ch - 1.08, cd.get("bullets", []), 13)
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 6.62, CS.FULL_W, 0.3, "Sources: " + spec["source"], 11, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "State activity is where overdraft rules are moving now."), c, path, spec.get("source"))
    return s


def _hero_table(dk, cfg, c, path, spec, section):
    """A navy panel with one or two headline figures and a short list, beside a table (the analysis team's Overdraft
    Class Action Settlements slide, November 2026)."""
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    pw, top, bottom = 3.35, 1.80, 6.55
    _card_bg(s, CS.LEFT, top, pw, bottom - top, fill=brand.NAVY_RGB)
    y = top + 0.22
    for h in spec.get("heroes", [])[:2]:
        shapes.textbox(s, CS.LEFT + 0.15, y, pw - 0.3, 0.72, h["value"], 40, brand.PEACH_RGB, True, PP_ALIGN.CENTER, T.HEAD, MSO_ANCHOR.MIDDLE)
        shapes.textbox(s, CS.LEFT + 0.2, y + 0.74, pw - 0.4, 0.62, h["label"], 13, brand.WHITE_RGB, False, PP_ALIGN.CENTER, T.BODY, MSO_ANCHOR.TOP)
        y += 1.50
    if spec.get("list"):
        shapes.textbox(s, CS.LEFT + 0.25, y, pw - 0.5, 0.32, spec.get("list_head", ""), 13, brand.PEACH_RGB, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
        T.bullets_real(s, CS.LEFT + 0.25, y + 0.36, pw - 0.5, bottom - y - 0.45, spec["list"], size=12, min_size=11,
                       color=brand.WHITE_RGB)
    # Cells WRAP here (unlike client_slides.table, which sizes columns so nothing wraps and so fell to 10 pt on the
    # long "Key detail" column): the panel's height is the room, so rows take it and the type stays at 13 pt.
    tx = CS.LEFT + pw + 0.30
    tw = CS.LEFT + CS.FULL_W - tx
    data = [spec["headers"]] + [[str(v) for v in r] for r in spec.get("rows", [])[:MAX_TABLE_ROWS]]
    nc = len(data[0])
    share = spec.get("col_share") or ([0.22, 0.24, 0.11, 0.43] if nc == 4 else [1 / nc] * nc)
    head_h = 0.50
    row_h = min(0.95, (bottom - top - head_h) / max(1, len(data) - 1))
    gf = shapes.add_table(s, tx, top, tw, head_h + row_h * (len(data) - 1), data, share, fs=13)
    tb = gf.table
    tb.rows[0].height = Inches(head_h)
    for i in range(1, len(data)):
        tb.rows[i].height = Inches(row_h)
        for cell in tb.rows[i].cells:
            for para in cell.text_frame.paragraphs:
                para.alignment = PP_ALIGN.LEFT
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 6.62, CS.FULL_W, 0.3, "Sources: " + spec["source"], 11, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "Litigation, not regulation, is the operative check on fee practice."), c, path, spec.get("source"))
    return s


def _chips(dk, cfg, c, path, spec, section):
    """An intro paragraph and a grid of chips (the analysis team's ILS Best Practices slide, November 2026)."""
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    y = 1.85
    if spec.get("intro"):
        shapes.textbox(s, CS.LEFT, y, CS.FULL_W, 1.05, spec["intro"], 16, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
        y += 1.15
    if spec.get("chips_head"):
        shapes.textbox(s, CS.LEFT, y, CS.FULL_W, 0.36, spec["chips_head"], 16, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
        y += 0.50
    chips = spec.get("chips", [])[:10]
    gap = 0.22
    cw = (CS.FULL_W - gap) / 2
    for i, ch in enumerate(chips):
        x = CS.LEFT + (i % 2) * (cw + gap)
        yy = y + (i // 2) * 0.62
        _card_bg(s, x, yy, cw, 0.50)
        shapes.textbox(s, x + 0.2, yy, cw - 0.4, 0.50, ch, 15, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.MIDDLE)
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 6.62, CS.FULL_W, 0.3, "Source: " + spec["source"], 11, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "Review the new best practices with the team."), c, path, spec.get("source"))
    return s


def _dated(dk, cfg, c, path, spec, section):
    """A dated record in two columns, oldest first (the analysis team's Recent Client Alerts slide)."""
    items = spec.get("items", [])
    s = dk.content(spec["title"], spec.get("subtitle"), section=section, source="x")
    half = (len(items) + 1) // 2
    cols = [items[:half], items[half:]]
    gap = 0.4
    cw = (CS.FULL_W - gap) / 2
    top, bottom = 1.80, 6.55
    rh = (bottom - top) / max(1, half)
    for k, col in enumerate(cols):
        x = CS.LEFT + k * (cw + gap)
        for j, (when, what) in enumerate(col):
            y = top + j * rh
            shapes.textbox(s, x, y, 1.15, rh, when, 12, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
            shapes.textbox(s, x + 1.15, y, cw - 1.15, rh, what, 12, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    if spec.get("source"):
        shapes.textbox(s, CS.LEFT, 6.62, CS.FULL_W, 0.3, "Source: " + spec["source"], 11, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    _notes(s, spec.get("say", "Every alert we have sent on overdraft since 2022, for reference."), c, path, spec.get("source"))
    return s


def add_industry(dk, cfg, fr, S, *, section, progress=None):
    content, path = load_industry(cfg)
    if content is None:
        return [f"Industry update: skipped, {path}. Put the cycle's industry_<yyyy-mm>.json in that folder to include it."]
    kinds = {"stats": _stats, "points": _points, "table": _table, "cards": _cards, "hero_table": _hero_table,
             "chips": _chips, "dated": _dated}
    n = 0
    for spec in content.get("slides", []):
        fn = kinds.get(spec.get("kind"))
        if fn is None:
            continue
        fn(dk, cfg, content, path, spec, section)
        n += 1
    dk.sidecars.append({"key": "industry_update", "title": "Industry update (standard content)", "numbers":
                        {"edition": content.get("edition"), "file": os.path.basename(path), "slides": n}})
    return [f"Industry update: {n} standard slide(s), edition {content.get('edition', 'n/a')}, from {os.path.basename(path)}; "
            f"the content is the analysis team's, reproduced as delivered."]


# ═════════════════════════════ the agenda ═══════════════════════════════════════
def add_agenda(dk, rows, *, section="agenda"):
    """`rows` = [(title, ignored)] in deck order. A numbered list of the agenda items, with no description lines
    (Aaron, 2026-11-05: "remove the descriptions of the agenda items"); the subtitle names the review."""
    s = dk.content("Agenda", "ILS\u00ae Program Analysis", section=section, source="Source: agenda for the review; no data.")
    n = len(rows)
    top, bottom = 1.95, 6.55
    rh = min(0.95, (bottom - top) / max(1, n))
    # the badge keeps room for its number: with eight parts rh - 0.22 left a 0.36 in circle, and its 18 pt digit
    # (inside the textbox's 0.1 in insets) wrapped
    d = min(0.73, max(rh - 0.22, rh - 0.08 if n > 5 else rh - 0.22))
    pad = (rh - d) / 2
    num_pt = 18 if d >= 0.55 else 16
    for i, row in enumerate(rows):
        title = row[0] if isinstance(row, (tuple, list)) else row
        y = top + i * rh
        badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(CS.LEFT), Inches(y + pad), Inches(d), Inches(d))
        badge.fill.solid()
        badge.fill.fore_color.rgb = brand.NAVY_RGB
        badge.line.fill.background()
        shapes.textbox(s, CS.LEFT - 0.1, y + pad, d + 0.2, d, str(i + 1), num_pt, brand.WHITE_RGB, True, PP_ALIGN.CENTER, brand.HEAD, MSO_ANCHOR.MIDDLE)
        shapes.textbox(s, CS.LEFT + d + 0.25, y, CS.FULL_W - d - 0.25, rh, title, 24, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.MIDDLE)
    s.notes_slide.notes_text_frame.text = ("Say first: here is the path through the review: the industry update, how the program is "
                                           "performing, what we observe and what we would do about it, then the appendix with the "
                                           "matrix validation.\n" + s.notes_slide.notes_text_frame.text)
    return s
