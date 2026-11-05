"""
combine.py — two one-chart slides of the Transaction Intelligence cut drawn as ONE slide, two charts
side by side (Aaron, 2026-11-02: "charts that can be combined into one slide").

Nothing is recomputed and no chart is shrunk: each v5 builder is run against a probe that records
what it asked for (its headline, its one chart, its footnotes) instead of drawing it, and the two
charts are then drawn again at half the slide's width. Their type size stays the one every chart in
the cut keeps (charts.CHART_MIN_PT), because the figure is authored at the width it lands at, not
scaled down afterwards.

    combine("Where the card is used", "...", (a_builder, "Topic A"), (b_builder, "Topic B"), "where_card_used")

returns a builder with the same `(h, *args)` signature as any other, for a chapter's builder list.
It falls back, and says so in the build log, rather than drawing a worse slide:
  * one side declines for this client  -> the other is drawn as it always was, and the declined side
                                          is recorded as declined (build_ti_gen hides it);
  * a side draws a table, tiles of its own, or more than one chart, so cannot be re-laid
                                        -> both are drawn as they always were;
  * the half-width charts would land under MIN_SCALE of their authored size (their type would read
    under 11pt on the slide)           -> both are drawn as they always were.
The rail of key figures is not carried to the combined slide: each panel's caption is its builder's
own headline, which carries the figure the rail repeated.
"""
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import matplotlib.pyplot as plt

from ti.deck import helpers as H

HALF_FIG_W = 6.3          # a figure authored for one half of the content width (two panels and a gap)
HALF_FIG_H = 4.5          # and for the band left under the title, the panel caption and above the logo
GAP = 0.30
MIN_SCALE = 0.86          # 13pt chart type lands at 11.2pt at this scale; the cut's typical scale is 0.92
CAPTION_PT = 14
CAPTION_H = 0.62          # two lines of 14pt: each panel's own headline
FOOT_FROM = 6.0           # text from here down is a footnote


class NotMergeable(Exception):
    pass


@contextmanager
def half_width():
    """Every `FIG_W_*` / `FIG_H_*` in the deck modules is half a slide while the block runs.

    Chart functions read these at call time, and several modules took their own copy with
    `from .charts import FIG_W_FULL, ...`, so every `ti.deck` module that has one is set, and each is
    put back afterwards."""
    values = {"FIG_W_RAIL": HALF_FIG_W, "FIG_W_FULL": HALF_FIG_W,
              "FIG_H_RAIL": HALF_FIG_H, "FIG_H_FULL": HALF_FIG_H}
    saved = []
    for name, mod in list(sys.modules.items()):
        if mod is None or not (name == "ti.deck" or name.startswith("ti.deck.")):
            continue
        for attr, v in values.items():
            if hasattr(mod, attr):
                saved.append((mod, attr, getattr(mod, attr)))
                setattr(mod, attr, v)
    # a figure authored taller than the band (4.6, 4.8, 5.2in) is drawn at the band's height instead:
    # scaled down afterwards, its type would land under the cut's floor
    real = {"subplots": plt.subplots, "figure": plt.figure}

    def capped(fn):
        def wrapper(*a, **kw):
            fs = kw.get("figsize")
            if fs:
                kw["figsize"] = (fs[0], min(fs[1], HALF_FIG_H))
            return fn(*a, **kw)
        return wrapper

    plt.subplots, plt.figure = capped(real["subplots"]), capped(real["figure"])
    try:
        yield
    finally:
        plt.subplots, plt.figure = real["subplots"], real["figure"]
        for mod, attr, v in saved:
            setattr(mod, attr, v)


class _Probe:
    """What one builder asked its helper bundle to draw, recorded and not drawn."""

    def __init__(self, h):
        self._h = h
        self.pair = None
        self.seen = False
        self.topic = None
        self.charts = []          # (name, fn, args, kwargs)
        self.texts = []
        self.rail = None
        self.declined = None

    def helpers(self):
        h = dict(self._h)
        h["slide"] = self._slide
        h["chart"] = self._chart
        h["chart_left"] = h["picture"] = h["fit_picture"] = lambda *a, **k: None
        h["rail"] = self._rail
        h["text"] = self._text
        h["kicker"] = lambda *a, **k: None
        h["declined"] = self._declined
        for name in ("table", "kpi", "new"):
            h[name] = self._refuse(name)
        return h

    def _slide(self, pair, fallback):
        if self.seen:
            raise NotMergeable("the builder draws more than one slide")
        self.seen, self.pair, self.topic = True, pair, fallback
        return mock.MagicMock(), 1.72

    def _chart(self, name, fn, *a, **kw):
        self.charts.append((name, fn, a, kw))
        return Path(f"{name}.png")             # truthy: the builder goes on to place it

    def _rail(self, _slide, items, **_k):
        self.rail = list(items)
        return H.RAIL_LEFT - 0.25

    def _text(self, _slide, _l, top, _w, _h, text, **_k):
        self.texts.append((top, str(text)))

    def _declined(self, title, reason):
        self.declined = reason

    @staticmethod
    def _refuse(name):
        def refuse(*_a, **_k):
            raise NotMergeable(f"the builder draws a {name}")
        return refuse


def _probe(h, builder, args):
    """('ok', probe) | ('declined', reason) | ('unmergeable', why) for one builder."""
    p = _Probe(h)
    try:
        why = builder(p.helpers(), *args)
    except NotMergeable as exc:
        return "unmergeable", str(exc)
    except Exception as exc:                    # the real run reports it the way Deck.run does
        return "unmergeable", f"{type(exc).__name__}: {exc}"
    if why:
        return "declined", str(why)
    if p.declined:
        return "declined", str(p.declined)
    if not p.seen:
        return "declined", "the figures it needs are not in this client's files"
    if len(p.charts) != 1:
        return "unmergeable", f"the builder draws {len(p.charts)} charts"
    return "ok", p


def _placed(path, max_w, max_h):
    """(width, height, authored width) in inches of the picture as it would be placed."""
    from PIL import Image
    with Image.open(path) as img:
        w, hgt = img.size
    dpi = 150                                   # charts.DPI
    aspect = w / hgt
    height = min(max_h, max_w / aspect)
    return height * aspect, height, w / dpi


def _reason(why):
    """A builder's decline without the label v5 puts in front of it: "<title> (<reason>)"."""
    hit = re.fullmatch(r"[^()]+ \((.+)\)", str(why).strip())
    return hit.group(1) if hit else str(why)


def _clean_caption(text):
    return " ".join(str(text).split())


def combine(topic, title, subtitle, part_a, part_b, name):
    """A builder drawing the two builders as the two panels of one slide whose topic is `topic`.

    `part_a` and `part_b` are (builder, that builder's own topic); `title` and `subtitle` are the
    slide's static headline and the line under it; `name` is the builder's name and prefixes the two
    charts' file names."""
    (a, topic_a), (b, topic_b) = part_a, part_b
    panels = (topic_a, topic_b)

    def merged(h, *args):
        with half_width():
            outcome = [_probe(h, bld, args) for bld in (a, b)]
        kinds = [o[0] for o in outcome]

        def separately(reason):
            """Both builders as they always were; one that declines is recorded as declined."""
            if reason:
                print(f"  [..]   not combined: {topic}: {reason}", flush=True)
            for bld, own, (kind, got) in zip((a, b), panels, outcome):
                if kind == "declined":
                    h["declined"](own, _reason(got))
                    continue
                why = bld(h, *args)
                if why:
                    h["declined"](own, _reason(why))
            return None

        if kinds == ["declined", "declined"]:
            return "; ".join(dict.fromkeys(_reason(o[1]) for o in outcome))
        if "unmergeable" in kinds:
            return separately("; ".join(o[1] for o in outcome if o[0] == "unmergeable"))
        if "declined" in kinds:
            return separately("the other half is declined for this client")

        probes = [o[1] for o in outcome]
        panel_w = (H.CONTENT_W - GAP) / 2
        top0 = 1.72 + CAPTION_H + 0.05
        paths = []
        with half_width():
            for i, p in enumerate(probes):
                cname, fn, a_, kw = p.charts[0]
                path, err = h["try_chart"](f"{name}_{i}", fn, *a_, **kw)
                if err:
                    return separately(f"a half-width chart did not draw ({err[:90]})")
                paths.append(path)
        fits = [_placed(pth, panel_w, H.CONTENT_FLOOR - top0) for pth in paths]
        scales = [w / authored for w, _h, authored in fits]
        if min(scales) < MIN_SCALE:
            return separately(f"the charts would land at {min(scales):.2f} of their authored size")

        s, top = h["slide"]((title, subtitle), topic)
        top = max(top, 1.72) + CAPTION_H + 0.05
        notes = []
        for i, (p, pth) in enumerate(zip(probes, paths)):
            left = H.MARGIN_L + i * (panel_w + GAP)
            caption = _clean_caption(p.pair[0] if p.pair else p.topic)
            h["text"](s, left, top - CAPTION_H - 0.05, panel_w, CAPTION_H, caption,
                      size=CAPTION_PT, bold=True, color=h["NAVY"])
            h["fit_picture"](s, pth, left + (panel_w - fits[i][0]) / 2, top,
                             max_w=panel_w, max_h=H.CONTENT_FLOOR - top)
            notes.append(f"{panels[i]} ({caption})")
        # a footnote is text at the foot of the slide; text higher up is a figure of the builder's own
        # (a row of counts) that a combined slide does not carry
        foot = " ".join(dict.fromkeys(t for p in probes for top, t in p.texts
                                     if top >= FOOT_FROM and t.strip()))
        if foot:
            h["text"](s, H.MARGIN_L + 0.02, 6.50, H.CONTENT_W, 0.28, foot, size=12, color=h["GREY"])
        _add_to_notes(s, "Combined slide, two panels. " + " | ".join(notes))
        return None

    merged.__name__ = name
    merged.topic = topic
    merged.parts = (a, b)
    return merged


def _add_to_notes(slide, text):
    tf = slide.notes_slide.notes_text_frame
    tf.text = f"{tf.text} {text}".strip()


def apply(builders, titles, pairs):
    """`builders` with each pair in `pairs` drawn as one combined slide at the first one's place.

    A pair is (first builder name, second builder name, combined topic, headline, subtitle,
    combined builder name). A name that is not in `builders` leaves that pair alone, so a chapter
    whose list changes never breaks here. `titles` (builder name -> topic) gains the combined
    builder's own entry, which Deck.run reads when the combined slide declines. Returns
    (builders, titles): the chapter's own `titles` dict is never changed, because a chapter's tests
    and v5's parity walk it as the list of v5's builders."""
    out = list(builders)
    titles = dict(titles)
    by_name = {getattr(b, "__name__", ""): b for b in out}
    for first, second, topic, headline, subtitle, name in pairs:
        a, b = by_name.get(first), by_name.get(second)
        if a is None or b is None:
            continue
        built = combine(topic, headline, subtitle, (a, titles.get(first, first)),
                        (b, titles.get(second, second)), name)
        titles[name] = topic
        out[out.index(a)] = built
        out.remove(b)
    return out, titles
