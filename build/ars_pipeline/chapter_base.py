#!/usr/bin/env python3
"""
chapter_base.py — what every ported v5 chapter shares when it is drawn on Aaron's template.

A v5 chapter body draws through a small set of closures (`new`, `slide`, `chart`, `register`,
`divider`, `skip`, `n`, `_title`, `_headed`). `Chapter` supplies them on Aaron's grid: his
header, pill and selection line on every slide; the v5 headline and sub-line as his 16pt
caption band, placed under whatever the slide drew and sent to the note when there is no
room; a source note on every slide; an inventory entry per slide, drawn or declined with the
reason; placement of the main path at a chapter's anchor in Aaron's deck and of everything
else at the end of the appendix under a cloned section divider (James, 2026-09-30: see
everything, then whittle).

Subclasses set: SOURCE (the note's first sentence), PILL, MAIN_CUT (v5 labels on the main
path), anchor_for(chapter) -> the Aaron title the chapter's main slides go before,
appendix_title_for(chapter) -> the appendix divider's title, main_divider_for(chapter) ->
(title, subtitle) or None, and _selection() -> the selection-line candidates.
"""
import os
import re
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from combined_insight_slides import _find, _new_slide, _header, _caption     # noqa: E402
import figures as _figs                                                       # noqa: E402
import shapes as SH                                                           # noqa: E402
import ti_layout as L                                                         # noqa: E402
import periods                                                                # noqa: E402

SECTION_LIKE = "Debit Card Review"        # the template section slide the dividers are cloned from
LAYOUT_ANCHOR = "Reg E Review"
CUT_ENV = "RPE_ANALYSIS_CUT"              # all (default) | main
BOTTOM = 6.95                             # the caption band ends above the slide-number band
_SMALL = {"a", "an", "the", "of", "for", "and", "by", "to", "in", "on", "at", "vs", "or",
          "with", "from", "against", "is", "as", "versus"}
_CU = re.compile(r"credit union|\bF?CU\b", re.I)


def member_term(client_name):
    """A credit union has members; a bank has account holders (1441 FNB Alaska, 2026-09-30)."""
    return "members" if _CU.search(client_name or "") else "account holders"


def wording(text, term):
    if not text:
        return text
    text = re.sub(r"\bmembers\b", term, text)
    text = re.sub(r"\bmember\b", term[:-1] if term.endswith("s") else term, text)
    return house_words(text)


# Aaron's banned words (validate_deck.BANNED, CLAUDE.md writing style) and the house word for
# each. v5 measures "lift" everywhere; on this deck the measure is a gain over control.
HOUSE_WORDS = [("lifted", "gained"), ("lift", "gain"), ("robust", "reliable"),
               ("comprehensive", "complete"), ("leverage", "use"), ("seamless", "smooth"),
               ("delve", "look"), ("ramping", "growing"), ("ramp", "growth"), ("healthy", "sound"),
               ("predominantly", "mostly"), ("companion", "matching"), ("seasoned book", "established book"),
               ("annuity", "recurring revenue")]
_HOUSE = [(re.compile(r"\b" + re.escape(a) + r"\b", re.I), b) for a, b in HOUSE_WORDS]


def house_words(text):
    """Every banned word swapped for the house word, case of the first letter kept."""
    if not isinstance(text, str) or not text:
        return text

    def swap(m, b):
        w = m.group(0)
        return b[:1].upper() + b[1:] if w[:1].isupper() else b
    for pat, b in _HOUSE:
        text = pat.sub(lambda m, b=b: swap(m, b), text)
    return text


def title_case(text):
    """Aaron's titles are Title Case; v5's are sentence case. Small words stay down."""
    out = []
    for i, w in enumerate(text.split()):
        low = w.lower()
        if w.isupper() and len(w) > 1:
            out.append(w)                      # KPIs, NSF, ODD
        else:
            out.append(low if (i and low in _SMALL) else w[:1].upper() + w[1:])
    return " ".join(out)


def _sentence(text):
    text = str(text).strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def _clip_to(text, width, holds, top=L.CAPTION_TOP):
    """Clipped at a word until it fits `holds` lines by measure AND by the validator's own
    cruder estimate of where a bottom caption ends."""
    shown = text

    def fits(t):
        return L.lines_for(t, width) <= holds and L.est_caption_bottom(t, width, top) <= 7.05
    while not fits(shown + "…") and len(shown) > 8:
        shown = shown[:shown.rfind(" ")].rstrip() if " " in shown else shown[:-4]
    return shown + "…"


class house_month_axes:
    """v5 charts label month axes from the engine's tags ("Aug24"); Aaron's rule is MMM'YY
    (STYLE.md, periods.mon_yy) and his guard fails any other form. Inside this context every
    tick label a chart sets goes through mon_yy first and then through the guard, so the v5
    charts draw his format without 40 renderers being edited. Scoped to the one chart call:
    outside it the guard is exactly Aaron's (tests/test_chart_axes.py holds it to that)."""

    def __enter__(self):
        from matplotlib.axes import Axes
        periods.install_month_axis_guard()
        self.saved = {name: getattr(Axes, name) for name in ("set_xticklabels", "set_yticklabels")}
        for name, orig in self.saved.items():
            def housed(self_, labels, *a, _orig=orig, **kw):
                fixed = []
                for t in labels or ():
                    txt = str(t.get_text() if hasattr(t, "get_text") else t)
                    fixed.append(periods.mon_yy(txt) if periods.parse_month(txt) else t)
                return _orig(self_, fixed, *a, **kw)
            housed.__name__ = name
            setattr(Axes, name, housed)
        return self

    def __exit__(self, *exc):
        from matplotlib.axes import Axes
        for name, orig in self.saved.items():
            setattr(Axes, name, orig)
        return False


def parse_skip(why):
    m = re.match(r"^(.*?) \((.*)\)$", why)
    return (m.group(1), m.group(2)) if m else (why, "")


class Chapter:
    SOURCE = "Source: the client's files."
    PILL = "{as_of} Data"
    MAIN_CUT = ()
    DEFAULT_CHAPTER = "Analysis"

    def __init__(self, prs, ctx):
        self.prs, self.ctx = prs, ctx
        self.assets = Path(ctx["assets"])
        self.term = member_term(ctx.get("client_name", ""))
        self.like = _find(prs, SECTION_LIKE)
        self.anchor = _find(prs, LAYOUT_ANCHOR)
        if self.like is None or self.anchor is None:
            raise RuntimeError(f"chapter: template has no '{SECTION_LIKE}' / '{LAYOUT_ANCHOR}' slide")
        self.pending = None
        self.slides = []            # (slide, v5 label, chapter)
        self.inventory = []
        self.chapter_now = [self.DEFAULT_CHAPTER]
        self.source = self.SOURCE
        self.m = {}
        self.finished = []

    # ------------------------------------------------------------------ the closures
    @property
    def helpers(self):
        return {"new": self.new, "slide": self.slide, "chart": self.chart, "chart_left": self.chart_left,
                "rail": self.rail, "divider": self.divider, "register": self.register, "skip": self.skip,
                "n": self.n, "title": self.title, "headed": self.headed, "chapter_now": self.chapter_now,
                "RIGHT_EDGE": L.RIGHT_EDGE}

    def new(self, layout=None):
        return _new_slide(self.prs, self.anchor)

    def divider(self, *args, **kw):
        """v5 calls divider(title, subtitle) or divider(prs, new, title, subtitle)."""
        title = args[2] if len(args) >= 3 else args[0]
        self.flush()
        self.chapter_now[0] = title
        return None

    def register(self, sl, kind, title, sub=None, computed=True, tracked=False):
        if kind != "slide":
            return
        self.flush()
        label = tracked if isinstance(tracked, str) and tracked else title
        self._start(sl, label)

    def _start(self, s, label):
        title = title_case(wording(label, self.term))
        _header(s, title, self.PILL.format(as_of=self.ctx["as_of_long"]), self._selection())
        self.pending = {"slide": s, "title": title, "label": label, "pair": None, "rail": False,
                        "chart": None, "no_chart": None, "detail": [], "chapter": self.chapter_now[0]}

    def slide(self, pair, fallback):
        self.flush()
        s = _new_slide(self.prs, self.anchor)
        self._start(s, fallback)
        self.pending["pair"] = pair
        return s, L.CHART_TOP

    def title(self, s, title, subtitle=None):
        """v5 `_title` on a slide registered a moment before; the headline becomes the caption."""
        if not self.pending or self.pending["slide"] is not s:
            self.flush()
            self._start(s, title[:60])
        self.pending["pair"] = (title, subtitle) if subtitle else (title,)

    def headed(self, s, pair, fallback):
        if not self.pending or self.pending["slide"] is not s:
            self.flush()
            self._start(s, fallback)
        self.pending["pair"] = pair
        return L.CHART_TOP

    def skip(self, title, *keys, reason=None):
        label, parsed = parse_skip(title)
        reason = reason or parsed or ("missing " + ", ".join(keys))
        self.inventory.append({"title": None, "v5_title": label, "chapter": self.chapter_now[0],
                               "cut": "main" if label in self.MAIN_CUT else "appendix",
                               "status": "skipped", "chart": None, "reason": reason})

    def n(self, key, default=0):
        return self.m.get(key, default) or default

    def chart(self, name, fn, *a, **kw):
        target = self.assets / f"{self.PREFIX}{name}.png"
        try:
            with house_month_axes():
                path = fn(*a, target, **kw)
        except Exception as exc:                                  # one chart, not the deck
            if self.pending:
                self.pending["no_chart"] = f"{name} ({type(exc).__name__}: {exc})"
            return None
        if self.pending:
            self.pending["chart"] = (name, getattr(fn, "__name__", "chart"), os.path.basename(str(path)))
        return path

    def chart_left(self, slide, image, top, right_edge, max_h=4.9):
        L.picture_left(slide, image, top, right_edge, max_h)

    def rail(self, slide, items, top=1.75, left=None, width=None, scope=None):
        right, detail = L.rail_tiles(slide, items, top=L.RAIL_TOP, scope=scope, record=_figs.log.record)
        if self.pending:
            self.pending["rail"] = True
            self.pending["detail"].extend(detail)
        return right

    # ------------------------------------------------------------------ finishing a slide
    def _selection(self):
        return ["Selection: see the note."]

    def flush(self):
        """Close the slide under construction. Its caption, note and inventory entry are
        written by finalize(): v5 can still draw on it after moving to the next slide."""
        p, self.pending = self.pending, None
        if p:
            self.finished.append(p)

    def finalize(self):
        for p in self.finished:
            self._finish(p)
        self.finished = []

    def _finish(self, p):
        s = p["slide"]
        notes = [self.source]
        head = wording(p["pair"][0], self.term) if p["pair"] else ""
        sub = wording(p["pair"][1], self.term) if p["pair"] and len(p["pair"]) > 1 and p["pair"][1] else ""
        if p["no_chart"]:
            notes.append(f"No chart: {p['no_chart']}.")
            head = head or "The chart for this view could not be drawn"
            sub = sub or p["no_chart"]
        has_picture = L.has_chart_picture(s)
        empty = not has_picture and not L.has_figure_shape(s)
        if p["no_chart"] and has_picture:       # the failed chart was another slide's (v5 draws two at once)
            head, sub = (wording(p["pair"][0], self.term) if p["pair"] else head), \
                        (wording(p["pair"][1], self.term) if p["pair"] and len(p["pair"]) > 1 and p["pair"][1] else "")
        if empty:                               # v5 drew nothing; Aaron's rule: say so
            sub = ((_sentence(sub) + " ") if sub else "") + "No figures for this view were produced for this period."
        placed = self._caption(s, head, sub, p["rail"], notes, empty=empty)
        if p["chart"]:
            notes.append(f"Chart: {p['chart'][1]} ({p['chart'][2]}).")
        notes.extend(p["detail"])
        notes.extend(L.drain_notes(s))
        s.notes_slide.notes_text_frame.text = " ".join(notes)
        self.slides.append((s, p["label"], p["chapter"]))
        self.inventory.append({"title": p["title"], "v5_title": p["label"], "chapter": p["chapter"],
                               "cut": "main" if p["label"] in self.MAIN_CUT else "appendix",
                               "status": ("drawn empty" if empty else "drawn"
                                          if has_picture or p["chart"] or not p["no_chart"]
                                          else "drawn without chart"),
                               "chart": p["chart"][1] if p["chart"] else None,
                               "reason": p["no_chart"] or "", "caption": placed})

    def _caption(self, s, head, sub, rail, notes, empty=False):
        """The v5 headline as Aaron's caption band, under whatever the slide drew (in the
        content area when nothing was). Returns where it went: 'band', 'short' (sub-line in
        the note), 'clipped', 'notes' or ''."""
        if not head:
            return ""
        width = L.CAPTION_W_RAIL if rail else L.CAPTION_W_FULL
        if empty:
            top, avail = L.CHART_TOP, 1.2
        else:
            top = max(L.CAPTION_TOP, L.content_bottom(s, L.MARGIN_L + width) + 0.06)
            avail = BOTTOM - top
        holds = L.box_holds(avail) if avail >= L._line_in(L.FLOOR_PT) else 0
        full = _sentence(head) + (" " + _sentence(sub) if sub else "")
        if holds == 0:
            notes.append("Caption (no room on the slide): " + full)
            return "notes"
        text, where = full, "band"
        if L.lines_for(text, width) > holds and sub:
            notes.append("Detail: " + _sentence(sub))
            text, where = _sentence(head), "short"
        if L.lines_for(text, width) > holds or L.est_caption_bottom(text, width, top) > 7.05:
            notes.append("Caption in full: " + full)
            text, where = _clip_to(text, width, holds, top), "clipped"
        _caption(s, text, width=width, top=top, height=avail)
        return where

    # ------------------------------------------------------------------ placement
    def anchor_for(self, chapter):
        return LAYOUT_ANCHOR

    def appendix_title_for(self, chapter):
        return f"{title_case(chapter)} Detail", "Appendix"

    def main_divider_for(self, chapter):
        return None

    def place(self, cut):
        self.flush()
        self.finalize()
        main = [(s, label, ch) for s, label, ch in self.slides if label in self.MAIN_CUT]
        appx = [(s, label, ch) for s, label, ch in self.slides if label not in self.MAIN_CUT]
        made = []
        for chapter in _ordered({ch for _, _, ch in main}, self.slides):
            anchor = _find(self.prs, self.anchor_for(chapter))
            if anchor is None:
                raise RuntimeError(f"chapter {chapter!r}: no anchor slide {self.anchor_for(chapter)!r}")
            group = [s for s, _, ch in main if ch == chapter]
            div = self.main_divider_for(chapter)
            if div:
                d = L.section_slide(self.prs, self.like, *div)
                group.insert(0, d)
                made.append((d, div[0], chapter))
            for s in group:
                L.move_before(self.prs, s, anchor)
        if cut == "main":
            for s, _, _ in appx:
                self._drop(s)
            for e in self.inventory:
                if e["cut"] == "appendix" and e["status"].startswith("drawn"):
                    e["status"] = "not built (RPE_ANALYSIS_CUT=main)"
            self.slides = main
        else:
            for chapter in _ordered({ch for _, _, ch in appx}, self.slides):
                first = next(s for s, _, ch in appx if ch == chapter)
                title, sub = self.appendix_title_for(chapter)
                d = L.section_slide(self.prs, self.like, title, sub)
                L.move_before(self.prs, d, first)
                made.append((d, title, chapter))
        self.slides = made + self.slides

    def _drop(self, slide):
        lst = self.prs.slides._sldIdLst
        sid = SH.sldid_of(self.prs, slide)
        self.prs.part.drop_rel(sid.rId)
        lst.remove(sid)


def _ordered(chapters, slides):
    seen = []
    for _, _, ch in slides:
        if ch in chapters and ch not in seen:
            seen.append(ch)
    return seen


def summary_lines(name, inventory):
    """The build-log lines: what was drawn, where it went, what declined and why."""
    drawn = [e for e in inventory if e["status"].startswith("drawn")]
    main = sum(1 for e in drawn if e["cut"] == "main")
    out = [f"{name}: {len(drawn)} of {len(inventory)} slides drawn "
           f"({main} main path, {len(drawn) - main} appendix)"]
    for e in inventory:
        if not e["status"].startswith("drawn"):
            out.append(f"  {e['status']:>8}  {e['v5_title']}: {e['reason']}")
    return out


def cut_from(ctx):
    return ctx.get("cut") or os.environ.get(CUT_ENV, "all")
