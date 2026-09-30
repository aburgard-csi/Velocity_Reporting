#!/usr/bin/env python3
"""
ti_chapter.py — James's v5 transaction chapter (engine/deck/txn_*.py: 34 slides) drawn onto
Aaron's template by Aaron's rules, opt-in (RPE_ANALYSIS_SLIDES=1).

The v5 chapter modules draw through a dict of seven helpers (new, slide, chart, chart_left,
rail, divider, RIGHT_EDGE). This module supplies those helpers on Aaron's grid: his header,
pill and selection line; the v5 headline and sub-line as his 16pt caption band; v5's callout
rail as his tiles, every line measured at the 16pt floor; the chapter divider cloned from the
template's own section slide; a source note on every slide; every tile in the figure sidecar.
The data and the chart forms are James's; the slide is Aaron's.

Placement (James, 2026-09-30, "I need to see everything created, then whittle"): the v5 main
path (MAIN_CUT) goes into the deck before "Reg E Review" under a "Transaction Intelligence"
divider; every other slide is still built and lands at the end of the appendix under its own
divider. RPE_ANALYSIS_CUT=main keeps the main path only. Nothing is dropped silently: a
builder that declines is listed with its reason in the inventory the build writes.

    add_ti_chapter(prs, txn, ctx) -> (slides, inventory)
        ctx: as_of_long, assets, txn_src, client_name, cut (optional)
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
import ti_layout as L                                                         # noqa: E402
from engine.deck import txn_slides                                            # noqa: E402

ANCHOR_BEFORE = "Reg E Review"
SECTION_LIKE = "Debit Card Review"        # the template section slide the dividers are cloned from
PILL = "{as_of} Data"
MAIN_TITLE, MAIN_SUB = "Transaction Intelligence", "Where the Money Goes • Competition • Card Spend"
APPX_TITLE, APPX_SUB = "Transaction Intelligence Detail", "Leakage • Competition • Card Behaviour"
CUT_ENV = "RPE_ANALYSIS_CUT"              # all (default) | main

# The v5 deck manifest's main path, transaction rows (0_Config/deck_manifest.json, 2026-09-30),
# keyed by the v5 slide label the builders pass as `fallback`.
MAIN_CUT = ("How the money moves", "Where the money goes", "Their financial life", "Who they pay",
            "What leakers hold with us", "Who competes for our members",
            "Which competitors to work first", "Where the outflow goes", "How members spend",
            "The responder profile", "What the banker actually opens")
BUILDERS = 34                             # txn_slides.add_chapter's builder list

_SMALL = {"a", "an", "the", "of", "for", "and", "by", "to", "in", "on", "at", "vs", "or",
          "with", "from", "against", "is", "as"}
_CU = re.compile(r"credit union|\bF?CU\b", re.I)


def member_term(client_name):
    """A credit union has members; a bank has account holders (1441 FNB Alaska, 2026-09-30)."""
    return "members" if _CU.search(client_name or "") else "account holders"


def wording(text, term):
    if not text:
        return text
    text = re.sub(r"\bmembers\b", term, text)
    return re.sub(r"\bmember\b", term[:-1] if term.endswith("s") else term, text)


def title_case(text):
    """Aaron's titles are Title Case; v5's are sentence case. Small words stay down."""
    words = text.split()
    out = []
    for i, w in enumerate(words):
        low = w.lower()
        out.append(low if (i and low in _SMALL) else w[:1].upper() + w[1:])
    return " ".join(out)


def _sentence(text):
    text = text.strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def _clip_to(text, width, holds):
    """A caption that cannot fit its band is clipped visibly; the full text goes to the notes."""
    shown = text
    while L.lines_needed(shown + "…", width) > holds and len(shown) > 8:
        shown = shown[:shown.rfind(" ")].rstrip() if " " in shown else shown[:-4]
    return shown + "…"


def _parse_skip(why):
    m = re.match(r"^(.*?) \((.*)\)$", why)
    return (m.group(1), m.group(2)) if m else (why, "")


class _Chapter:
    def __init__(self, prs, txn, ctx):
        self.prs, self.txn, self.ctx = prs, txn, ctx
        self.assets = Path(ctx["assets"])
        self.term = member_term(ctx.get("client_name", ""))
        self.like = _find(prs, SECTION_LIKE)
        self.anchor = _find(prs, ANCHOR_BEFORE)
        if self.like is None or self.anchor is None:
            raise RuntimeError(f"transaction chapter: template has no '{SECTION_LIKE}' / '{ANCHOR_BEFORE}' slide")
        self.pending = None
        self.slides = []            # (slide, v5 label)
        self.inventory = []
        self.main_divider = None
        files = ", ".join(txn.get("txn_files_loaded") or [])[:300] or "no files"
        self.source = (f"Source: {ctx.get('txn_src') or 'the client transaction files'} — {files} "
                       f"({txn.get('txn_rows', 0):,} rows, {txn.get('txn_months_covered', 0)} month(s)); "
                       f"ODD join {txn.get('txn_odd_match_pct', 'n/a')}% on {txn.get('txn_odd_join_key', 'n/a')}; "
                       f"figures from txn_metrics.json.")

    # ------------------------------------------------------------------ the seven helpers
    @property
    def helpers(self):
        return {"new": self.new, "slide": self.slide, "chart": self.chart, "chart_left": self.chart_left,
                "rail": self.rail, "divider": self.divider, "RIGHT_EDGE": L.RIGHT_EDGE}

    def new(self, layout=None):
        return _new_slide(self.prs, self.anchor)

    def divider(self, prs, new, title, subtitle=None):
        self.flush()
        self.main_divider = L.section_slide(self.prs, self.like, MAIN_TITLE, MAIN_SUB)
        return self.main_divider

    def slide(self, pair, fallback):
        self.flush()
        s = _new_slide(self.prs, self.anchor)
        title = title_case(wording(fallback, self.term))
        _header(s, title, PILL.format(as_of=self.ctx["as_of_long"]), self._selection())
        self.pending = {"slide": s, "title": title, "label": fallback, "pair": pair,
                        "rail": False, "chart": None, "no_chart": None, "detail": []}
        return s, L.CHART_TOP

    def chart(self, name, fn, *a, **kw):
        target = self.assets / f"ti_{name}.png"
        try:
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
        t = self.txn
        personal, every = t.get("fin_accounts_total"), t.get("txn_accounts")
        base, label = ((personal, "transacting personal accounts") if isinstance(personal, int) and personal
                       else (every, "transacting accounts"))
        if not isinstance(base, int):
            return ["Selection: transacting accounts."]
        return [f"Selection: {label} ({base:,}); {t.get('txn_window_months', 12)}-month window "
                f"ending {t.get('txn_anchor', '')}.", f"Selection: {label} ({base:,})."]

    def flush(self):
        p, self.pending = self.pending, None
        if not p:
            return
        s = p["slide"]
        width = L.CAPTION_W_RAIL if p["rail"] else L.CAPTION_W_FULL
        head = wording(p["pair"][0], self.term) if p["pair"] else ""
        sub = wording(p["pair"][1], self.term) if p["pair"] and len(p["pair"]) > 1 else ""
        notes = [self.source]
        if p["no_chart"]:
            notes.append(f"No chart: {p['no_chart']}.")
            head = head or "The chart for this view could not be drawn"
            sub = sub or f"{p['no_chart']}"
        text = _sentence(head) + (" " + _sentence(sub) if sub else "")
        need, holds = L.caption_fit(text, width)
        if need > holds and sub:
            notes.append("Detail: " + _sentence(sub))
            text = _sentence(head)
            need, holds = L.caption_fit(text, width)
        if need > holds or L.est_caption_bottom(text, width) > 7.05:
            notes.append("Caption in full: " + text)
            text = _clip_to(text, width, holds)
        if text:
            _caption(s, text, width=width)
        if p["chart"]:
            notes.append(f"Chart: {p['chart'][1]} ({p['chart'][2]}).")
        notes.extend(p["detail"])
        s.notes_slide.notes_text_frame.text = " ".join(notes)
        self.slides.append((s, p["label"]))
        self.inventory.append({"title": p["title"], "v5_title": p["label"],
                               "cut": "main" if p["label"] in MAIN_CUT else "appendix",
                               "status": "drawn" if p["chart"] else "drawn without chart",
                               "chart": p["chart"][1] if p["chart"] else None,
                               "reason": p["no_chart"] or ""})

    # ------------------------------------------------------------------ placement
    def place(self, cut):
        reg_e = _find(self.prs, ANCHOR_BEFORE)
        main = [s for s, label in self.slides if label in MAIN_CUT]
        appx = [s for s, label in self.slides if label not in MAIN_CUT]
        for s in [self.main_divider] + main:
            if s is not None:
                L.move_before(self.prs, s, reg_e)
        if cut == "main":
            for s in appx:
                self._drop(s)
            self.slides = [(s, label) for s, label in self.slides if label in MAIN_CUT]
            for e in self.inventory:
                if e["cut"] == "appendix" and e["status"].startswith("drawn"):
                    e["status"] = "not built (RPE_ANALYSIS_CUT=main)"
        elif appx:
            div = L.section_slide(self.prs, self.like, APPX_TITLE, APPX_SUB)
            L.move_before(self.prs, div, appx[0])
            self.slides.append((div, APPX_TITLE))
        if self.main_divider is not None:
            self.slides.insert(0, (self.main_divider, MAIN_TITLE))

    def _drop(self, slide):
        lst = self.prs.slides._sldIdLst
        sid = _figs_sldid(self.prs, slide)
        self.prs.part.drop_rel(sid.rId)
        lst.remove(sid)


def _figs_sldid(prs, slide):
    import shapes as SH
    return SH.sldid_of(prs, slide)


def add_ti_chapter(prs, txn, ctx):
    """Build every v5 transaction slide the data supports, place the main path before
    "Reg E Review" and the rest in the appendix. Returns ([slides], inventory)."""
    ch = _Chapter(prs, txn, ctx)
    cut = ctx.get("cut") or os.environ.get(CUT_ENV, "all")
    if not txn.get("fin_by_category"):
        s, _ = ch.slide(("The transaction files in this window carry no financial-services rows, "
                         "so the chapter is not drawn for this period",
                         "check the files under Inputs/Txn Files and the financial services dictionary"),
                        "Transaction intelligence")
        ch.flush()
        L.move_before(prs, s, ch.anchor)
        ch.inventory[0]["status"] = "no data"
        for e in ch.inventory:
            e["cut"] = "main"
        return [s], ch.inventory
    skipped = txn_slides.add_chapter(prs, ch.helpers, txn, ch.assets)
    ch.flush()
    for why in skipped:
        label, reason = _parse_skip(why)
        ch.inventory.append({"title": None, "v5_title": label, "cut": "main" if label in MAIN_CUT else "appendix",
                             "status": "skipped", "chart": None, "reason": reason})
    ch.place(cut)
    return [s for s, _ in ch.slides], ch.inventory


def summary_lines(inventory):
    """The build-log lines: what was drawn, where it went, what declined and why."""
    drawn = [e for e in inventory if e["status"].startswith("drawn")]
    main = sum(1 for e in drawn if e["cut"] == "main")
    out = [f"transaction chapter: {len(drawn)} of {len(inventory)} slides drawn "
           f"({main} main path, {len(drawn) - main} appendix)"]
    for e in inventory:
        if not e["status"].startswith("drawn"):
            out.append(f"  {e['status']:>8}  {e['v5_title']}: {e['reason']}")
    return out
