# Ported from v5 02-Scripts/ars/deck/register.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Slide register: every slide, and the source that feeds it.

The storyboard says WHAT is in the deck; the register says WHERE each
slide's content came from, so a change can be traced and tracked:

  - the headline function (``headlines.population``) and its text
  - the chart function and the PNG it wrote (``charts.funnel -> charts/funnel.png``)
  - the metric keys the slide read, grouped by the analysis module that
    WRITES each key (``dctr.py`` for ``dctr_overall``) -- found by a
    static scan of ``monthly_analysis/`` and ``transaction_intelligence/``
  - placement (main path vs appendix) and the chapter it sits in

Two files beside the deck: ``slide_register.md`` for people, and
``slide_register.json`` for diffs between runs.

Attribution of metric reads is by construction window: ``TracedMetrics``
logs every key read, and build.py hands each slide the reads made while
it was the slide under construction. Reads the headline function makes
are captured exactly (``trace_headlines``). The one soft edge is a guard
read (``tiers = m.get("swipe_tier")``) made BEFORE the next slide
registers: it lands on the next slide when the previous slide finished
with a chart, and on the previous slide otherwise. Headline and chart
provenance is exact either way.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path

_WRITE_RE = re.compile(r'\b(?:out|metrics|m|t|res|result)\["([A-Za-z0-9_]+)"\]\s*=(?!=)')
_LITERAL_RE = re.compile(r'^\s*"([a-z][A-Za-z0-9_]+)":\s', re.M)
# out[f"{prefix}_delta"] / out[f"flight_{key}_n"]: keys built at run time
_FSTRING_RE = re.compile(r'\b(?:out|metrics|m|t|res|result)\[f"([^"]+)"\]\s*=(?!=)')
_SCAN = ("monthly_analysis/*.py", "transaction_intelligence/*.py", "workbook.py")


class TracedMetrics(dict):
    """A metrics dict that remembers which keys were read.

    ``reads`` is the full log (order kept, repeats kept); ``take_reads``
    hands back the reads since the last take and clears them, which is
    how build.py assigns a window of reads to one slide.
    """

    def __init__(self, data: dict, source: str = "metrics"):
        super().__init__(data)
        self.source = source
        self.reads: list[str] = []
        self._mark = 0

    def _note(self, key):
        if isinstance(key, str):
            self.reads.append(key)

    def get(self, key, default=None):
        self._note(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._note(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self._note(key)
        return super().__contains__(key)

    def take_reads(self) -> list[str]:
        taken = self.reads[self._mark:]
        self._mark = len(self.reads)
        return list(taken)


class trace_headlines:
    """Proxy for the headlines module: each call records its name and the
    metric keys it read, so the slide that consumes the headline can claim
    them exactly."""

    def __init__(self, module, metrics: TracedMetrics, on_unconsumed=None):
        self._module = module
        self._m = metrics
        self._on_unconsumed = on_unconsumed
        self.last: dict | None = None

    def __getattr__(self, name):
        fn = getattr(self._module, name)
        if not callable(fn):
            return fn

        @functools.wraps(fn)
        def wrapped(*a, **kw):
            if self.last is not None and self._on_unconsumed:
                # the previous headline never reached slide(): it declined,
                # so its reads (and the guard before it) belong to no slide
                self._on_unconsumed(self.last["start"])
                self.last = None
            before = len(self._m.reads)
            out = fn(*a, **kw)
            keys = self._m.reads[before:]
            self.last = {"fn": f"headlines.{name}", "keys": list(keys),
                         "start": before}
            return out
        return wrapped

    def take(self) -> dict | None:
        last, self.last = self.last, None
        return last


def _template_pattern(template: str) -> re.Pattern:
    """``flight_{key}_n`` -> a regex matching any run-time key it can make."""
    parts = re.split(r"\{[^}]*\}", template)
    return re.compile("^" + "[A-Za-z0-9_]+".join(re.escape(p) for p in parts) + "$")


@functools.lru_cache(maxsize=1)
def _scan() -> tuple[dict[str, str], list[tuple[re.Pattern, str]]]:
    root = Path(__file__).resolve().parents[1]
    exact: dict[str, str] = {}
    patterns: list[tuple[re.Pattern, str]] = []
    for glob in _SCAN:
        for py in sorted(root.glob(glob)):
            text = py.read_text(encoding="utf-8", errors="replace")
            # as_posix, not str: on Windows str() yields backslashes and the
            # register becomes a different artefact per platform -- the same
            # run would produce 'monthly_analysis\\dctr.py' there and
            # 'monthly_analysis/dctr.py' here, and nothing downstream that
            # matches on the path would work on both.
            rel = py.relative_to(root).as_posix()
            for key in _WRITE_RE.findall(text) + _LITERAL_RE.findall(text):
                exact.setdefault(key, rel)
            for template in _FSTRING_RE.findall(text):
                patterns.append((_template_pattern(template), rel))
    return exact, patterns


class _Writers(dict):
    """metric key -> the source file that writes it. Exact writes first
    (``out["dctr_overall"] =``); keys assembled from f-strings resolve by
    pattern and are marked ``(pattern)``; anything else is ``unmapped``."""

    def __init__(self):
        exact, patterns = _scan()
        super().__init__(exact)
        self._patterns = patterns

    def get(self, key, default="unmapped"):
        if key in self:
            return self[key]
        for pat, rel in self._patterns:
            if pat.match(key):
                return f"{rel} (pattern)"
        return default


@functools.lru_cache(maxsize=1)
def key_writers() -> dict[str, str]:
    return _Writers()


def _first_text(sl) -> str:
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().splitlines()[0]
    return ""


def _placement(entry: dict, main_path: list[str]) -> str:
    if entry["kind"] == "chapter":
        return "divider"
    tracked = entry.get("tracked")
    if not tracked:
        return "fixed"
    return "main path" if tracked in main_path else "appendix"


def rows(final_slides, placed, gaps, main_path, *,
         client: str, data_month: str) -> dict:
    """The register as data: one row per slide in FINAL deck order."""
    writers = key_writers()
    by_obj = {id(e["sl"]): e for e in placed}
    chapter = "Front matter"
    out: list[dict] = []
    for number, sl in enumerate(final_slides, start=1):
        e = by_obj.get(id(sl))
        if e is None:
            out.append({"number": number, "kind": "fixed",
                        "title": _first_text(sl) or "(untitled)",
                        "id": None, "chapter": chapter, "placement": "fixed"})
            continue
        if e["kind"] == "chapter":
            chapter = e["title"]
            out.append({"number": number, "kind": "divider", "title": e["title"],
                        "id": e["title"], "chapter": chapter,
                        "placement": "divider"})
            continue
        keys = sorted(set(e.get("metric_keys") or []))
        sources = sorted({s for s in (e.get("metric_sources") or [])})
        out.append({
            "number": number, "kind": "slide",
            "title": e["title"], "subhead": e.get("sub"),
            "id": e.get("tracked") or e["title"],
            "chapter": e.get("chapter") or chapter,
            "placement": _placement(e, main_path),
            "headline": e["title"] if e.get("computed") else None,
            "headline_fn": e.get("headline_fn") or (
                "inline" if e.get("computed") else "topic label"),
            "charts": list(e.get("charts") or []),
            "metric_keys": [{"key": k, "writer": writers.get(k, "unmapped")}
                            for k in keys],
            "data_sources": sources,
        })
    return {"client": client, "data_month": data_month,
            "slides": out,
            "not_rendered": [{"title": t, "reason": r} for t, r in gaps]}


def _group_by_writer(keys: list[dict]) -> list[tuple[str, list[str]]]:
    groups: dict[str, list[str]] = {}
    for k in keys:
        groups.setdefault(k["writer"], []).append(k["key"])
    return sorted(groups.items())


def markdown(data: dict) -> str:
    lines = [f"# Slide register - {data['client']}, data through "
             f"{data['data_month']}", "",
             "One section per slide in final deck order. Source lines name "
             "the function that produced the text or chart; metric keys are "
             "grouped by the analysis module that writes them.", ""]
    for r in data["slides"]:
        if r["kind"] != "slide":
            note = ("Chapter divider." if r["kind"] == "divider"
                    else "Fixed slide (cover, closer): no metrics.")
            lines += [f"## {r['number']}. {r['title']}", "", note, ""]
            continue
        lines += [f"## {r['number']}. {r['title']}", ""]
        if r.get("subhead"):
            lines.append(f"_{r['subhead']}_")
            lines.append("")
        lines += [f"- Slide id: `{r['id']}`",
                  f"- Chapter: {r['chapter']}  |  Placement: {r['placement']}",
                  f"- Source: {r['headline_fn']}"]
        for c in r["charts"]:
            target = c["file"] or "(not rendered: dry run)"
            lines.append(f"- Chart: {c['fn']} -> {target}")
        if r["data_sources"]:
            lines.append(f"- Data: {', '.join(r['data_sources'])}")
        if r["metric_keys"]:
            lines.append("- Metric keys:")
            for writer, keys in _group_by_writer(r["metric_keys"]):
                lines.append(f"  - `{writer}`: " + ", ".join(f"`{k}`" for k in keys))
        else:
            lines.append("- Metric keys: none read (layout-only)")
        lines.append("")
    lines += ["## Not rendered", ""]
    if data["not_rendered"]:
        lines += [f"- {g['title']} - {g['reason']}" for g in data["not_rendered"]]
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write(data: dict, out_dir: Path) -> Path:
    md = out_dir / "slide_register.md"
    md.write_text(markdown(data), encoding="utf-8")
    md.with_suffix(".json").write_text(
        json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return md


def chart_label(fn) -> str:
    """``charts.funnel`` / ``txn_slides.lens_bars`` -- module-qualified."""
    mod = (getattr(fn, "__module__", "") or "").rsplit(".", 1)[-1]
    return f"{mod}.{fn.__name__}" if mod else fn.__name__


class ReadLedger:
    """Assigns metric reads to slides as build.py registers them.

    One window per register() call: the reads since the previous call.
    The headline function's reads (from ``trace_headlines``) go to the
    slide being registered; reads after the previous slide's last chart()
    go with them as that slide's guard; everything earlier in the window
    belongs to the previous slide.
    """

    def __init__(self):
        self._dicts: list[TracedMetrics] = []
        self._marks: dict[int, int] = {}
        self._chart_marks: dict[int, int | None] = {}

    def add(self, tm: TracedMetrics) -> TracedMetrics:
        self._dicts.append(tm)
        self._marks[id(tm)] = len(tm.reads)
        self._chart_marks[id(tm)] = None
        return tm

    def chart_seen(self) -> None:
        for tm in self._dicts:
            self._chart_marks[id(tm)] = len(tm.reads)

    @staticmethod
    def _claim(entry: dict | None, tm: TracedMetrics, keys: list[str]) -> None:
        if entry is None or not keys or entry.get("kind") != "slide":
            return
        entry.setdefault("metric_keys", []).extend(keys)
        entry.setdefault("metric_sources", [])
        if tm.source not in entry["metric_sources"]:
            entry["metric_sources"].append(tm.source)

    def _close(self, prev: dict | None, boundary: int | None,
               carry: bool) -> None:
        """Close the window at the previous slide's last chart (or, with
        no chart, at the window end). Reads before the close go to
        ``prev``; reads after it are the next slide's guard and are
        carried forward (``carry``) or dropped (a skip / declined
        headline, whose guard belongs to no slide)."""
        for tm in self._dicts:
            start, end = self._marks[id(tm)], len(tm.reads)
            cut = self._chart_marks[id(tm)]
            keep_to = cut if cut is not None and start <= cut <= end else end
            if boundary is not None and tm is self._dicts[0]:
                keep_to = min(keep_to, max(start, boundary))
            self._claim(prev, tm, tm.reads[start:keep_to])
            restart = keep_to if carry else end
            self._marks[id(tm)] = restart
            self._chart_marks[id(tm)] = restart

    def declined_from(self, prev_fn, start_idx: int) -> None:
        """A headline declined (returned None) before any slide() call."""
        self._close(prev_fn(), start_idx, carry=False)

    def skip_seen(self, prev: dict | None) -> None:
        """A guard failed: the reads since the previous slide's last chart
        were that skipped slide's guard."""
        self._close(prev, None, carry=False)

    def assign(self, prev: dict | None, new: dict | None,
               headline: dict | None, headline_dict: TracedMetrics | None) -> None:
        if new is None:                     # a divider, or the end of the build
            self._close(prev, None, carry=True)
            return
        for tm in self._dicts:
            start, end = self._marks[id(tm)], len(tm.reads)
            self._marks[id(tm)] = end
            hl_start, hl_end = end, end
            if headline and tm is headline_dict:
                hl_start = max(start, headline["start"])
                hl_end = hl_start + len(headline["keys"])
            cut = self._chart_marks[id(tm)]
            self._chart_marks[id(tm)] = None
            if prev is None:
                self._claim(new, tm, tm.reads[start:hl_start])
            elif cut is not None and start <= cut <= hl_start:
                self._claim(prev, tm, tm.reads[start:cut])
                self._claim(new, tm, tm.reads[cut:hl_start])
            else:
                self._claim(prev, tm, tm.reads[start:hl_start])
            self._claim(new, tm, tm.reads[hl_start:end])
        if headline:
            new["headline_fn"] = headline["fn"]
