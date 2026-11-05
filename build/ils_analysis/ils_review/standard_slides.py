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
       {"kind": "table",  "title": ..., "subtitle": ..., "source": ..., "headers": [...], "rows": [[...]], "foot": ...}]}
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


def add_industry(dk, cfg, fr, S, *, section, progress=None):
    content, path = load_industry(cfg)
    if content is None:
        return [f"Industry update: skipped, {path}. Put the cycle's industry_<yyyy-mm>.json in that folder to include it."]
    kinds = {"stats": _stats, "points": _points, "table": _table}
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
    """`rows` = [(title, blurb)] in deck order. A numbered list; the slide numbers follow the deck's own order."""
    s = dk.content("Agenda", "What this review covers, in the order it is presented.", section=section,
                   source="Source: agenda for the review; no data.")
    n = len(rows)
    top, bottom = 1.80, 6.65
    rh = min(0.62, (bottom - top) / max(1, n))
    for i, (title, blurb) in enumerate(rows):
        y = top + i * rh
        badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(CS.LEFT), Inches(y + 0.04), Inches(rh - 0.10), Inches(rh - 0.10))
        badge.fill.solid()
        badge.fill.fore_color.rgb = brand.NAVY_RGB
        badge.line.fill.background()
        shapes.textbox(s, CS.LEFT, y + 0.04, rh - 0.10, rh - 0.10, str(i + 1), 15, brand.WHITE_RGB, True, PP_ALIGN.CENTER, brand.HEAD, MSO_ANCHOR.MIDDLE)
        shapes.textbox(s, CS.LEFT + rh + 0.1, y, 5.2, rh, title, 18, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.MIDDLE)
        shapes.textbox(s, CS.LEFT + rh + 5.4, y, CS.FULL_W - rh - 5.4, rh, blurb, 14, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.MIDDLE)
    s.notes_slide.notes_text_frame.text = ("Say first: here is the path through the review: where the program stands, what drives it, where "
                                           "the limit calculates, performs and pulls back, then the matrix.\n" + s.notes_slide.notes_text_frame.text)
    return s
